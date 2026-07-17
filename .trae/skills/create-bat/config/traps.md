### 陷阱 1：UTF-8 BOM 让 .bat 的 @echo off 失效
- **现象**：所有命令被回显，`>echo ===` 出现在输出
- **根因**：BOM 字节 `EF BB BF` 让 `@` 不在行首
- **规避**：.bat 文件**永远不要 BOM**

### 陷阱 2：.ps1 无 BOM 在 PS 5.1 中文乱码
- **现象**：`Missing property name after reference operator` + 中文乱码
- **根因**：PS 5.1 按 GBK 解析无 BOM 的 .ps1，UTF-8 中文被错误拆分，`$var.prop` 被误判为属性引用
- **规避**：.ps1 含中文时**必须 UTF-8 with BOM**

### 陷阱 3：chcp 65001 不能修复 .bat 乱码
- **现象**：加了 `chcp 65001` 仍报 `'脚本' is not recognized`
- **根因**：`chcp` 只改控制台输出代码页，**不影响 cmd 解析 .bat 文件本身**（cmd 始终按系统 ANSI 解析）
- **规避**：.bat 文件改纯 ASCII（首选），或转 GBK + chcp 936（备选，需 PowerShell WriteAllText）

### 陷阱 4：LF 行尾让中文行被切分
- **现象**：`'up' is not recognized`（来自 "Setup" 被切断）
- **根因**：cmd 不依赖 LF 作行边界，多字节字符 + LF 导致错误切分
- **规避**：强制 CRLF，生成后验证孤立 LF 数 = 0

### 陷阱 5：PATH 中旧版工具优先
- **现象**：winget 装了 Node 24，但 `npm --version` 显示 6.14（nodejs14 优先）
- **根因**：PATH 中旧版路径排序在前
- **规避**：工具查找优先用已验证版本的 $toolExe 同目录推导，不依赖 PATH

### 陷阱 6：传递依赖冲突
- **现象**：pip install A 后，B 报 version conflict
- **根因**：A 的依赖 C 要求 B<version，但项目锁定 B 更高版本
- **规避**：安装可能引入冲突的包后，显式降级冲突包；requirements.txt 同步更新

### 陷阱 7：lockfileVersion 与 npm 版本不匹配
- **现象**：npm ci 报 `Cannot read property 'X' of undefined`
- **根因**：lockfileVersion 3 需 npm 7+，npm 6 的 lock-verify 不兼容
- **规避**：检查 lockfileVersion，确保 npm 版本兼容

### 陷阱 8：winget 装到用户目录
- **现象**：winget 报"已成功安装"但找不到工具
- **根因**：winget 默认用户级安装到 `$env:LOCALAPPDATA\Programs\...`
- **规避**：Find-Tool 必须包含用户级路径

### 陷阱 9：pip 卸载残留 ~前缀目录
- **现象**：`Ignoring invalid distribution ~etuptools`
- **根因**：pip 卸载包时先重命名为 ~xxx，中断后残留
- **规避**：setup 脚本中加自动清理逻辑（`Get-ChildItem -Filter '~*'`）

### 陷阱 10：冒烟测试覆盖不全
- **现象**：setup 成功但运行时报 ImportError
- **根因**：冒烟测试只测 5 个包，遗漏的包安装失败不报警
- **规避**：冒烟测试覆盖所有直接 import 的第三方包

### 陷阱 11：UTF8Encoding.GetBytes 不写入 BOM
- **现象**：用 `UTF8Encoding($true).GetBytes(text)` + `WriteAllBytes` 写入后，验证 BOM=False
- **根因**：`emitBOM` 参数只在 `WriteAllText` 配合 preamble 时生效，`GetBytes()` 不会自动添加 BOM 字节
- **规避**：必须用 `[System.IO.File]::WriteAllText($path, $text, $utf8WithBom)` 写入

### 陷阱 12：GetEncoding 3 参数重载在 PS 5.1 不支持
- **现象**：`Cannot find an overload for "GetEncoding" and the argument count: "3"`
- **根因**：PS 5.1 的 .NET API 不支持 `GetEncoding(int, EncoderFallback, DecoderFallback)` 重载
- **规避**：改用默认的 `GetEncoding(936)`（带 DecoderReplacementFallback），通过检查解码结果是否含 U+FFFD 替换字符判断合法性

### 陷阱 13：System.Text.Encoding 抽象基类不能实例化
- **现象**：`New-Object System.Text.Encoding` 报 "A constructor was not found"
- **根因**：`System.Text.Encoding` 是抽象基类，不能直接实例化
- **规避**：用静态方法 `[System.Text.Encoding]::GetEncoding(936)` 或 `[System.Text.Encoding]::UTF8`

### 陷阱 14：启动命令未重定向日志导致无法排查
- **现象**：启动失败提示"请查看 logs\web.log"，但该文件不存在
- **根因**：启动命令 `start "..." cmd /c "... 2>&1 & pause"` 把输出留在弹出的 cmd 窗口里，未重定向到文件
- **规避**：启动命令必须重定向 `> logs\<service>.log 2>&1`；启动前清空旧日志；失败时自动输出日志尾部

### 陷阱 15：端口释放延迟导致绑定失败
- **现象**：杀掉旧进程后立即启动新进程，报 `Errno 10048` / `Address already in use`
- **根因**：Windows TCP 栈释放端口有延迟，`taskkill` 后端口不会立即可用
- **规避**：端口清理后增加等待释放循环（`netstat` 检测端口是否仍被占用，最多等待 N 秒）

### 陷阱 16：Sandbox 阻止 cmd /c 导致无法验证 .bat
- **现象**：`cmd /c <script>.bat` 报 "invalid command: The use of 'cmd /c' is blocked"
- **根因**：受限环境安全策略禁止 cmd /c 调用
- **规避**：改用 PowerShell 直接读取文件字节，用 GBK/UTF-8 编码对象解码显示，验证中文正确性

### 陷阱 17：临时 .ps1 脚本无 BOM 导致自身中文乱码
- **现象**：临时验证脚本中的中文输出乱码，或报 `TerminatorExpectedAtEndOfString`
- **根因**：PS 5.1 按 GBK 解析无 BOM 的 .ps1，中文被错误拆分导致语法错误
- **规避**：临时脚本全用英文代码；需输出中文路径时用 `[char]0xXXXX` 构造（如 `启动服务.bat` = `[char]0x542F + [char]0x52A8 + [char]0x670D + [char]0x52A1 + '.bat'`）

### 陷阱 18：内联 PowerShell 命令 $变量 被外层 shell 吞掉
- **现象**：`powershell -Command "$var = ..."` 中 `$var` 变为空值
- **根因**：外层 shell（如 bash/安全包装器）先解析了 `$var`，PowerShell 收到的是空字符串
- **规避**：改用临时 .ps1 脚本文件（`-File` 参数），避免内联命令的转义问题

### 陷阱 19：cmd 重定向语法在 PowerShell 终端不兼容
- **现象**：`taskkill /F /IM python.exe >nul 2>&1` 在 PowerShell 终端报错
- **根因**：PowerShell 不支持 cmd 的 `>nul` 重定向语法，`nul` 被当作文件名
- **规避**：在 PowerShell 终端中用 `2>&1 | Out-Null` 或 `*> $null`

### 陷阱 20：Write 工具默认 UTF-8 无 BOM，不适合写中文 .bat
- **现象**：用 Write 工具创建含中文 echo 的 .bat 文件，执行报错 `'哄共鍑€' 不是内部或外部命令`
- **根因**：Write 工具默认 UTF-8 无 BOM 编码，cmd 按系统 ANSI（GBK）解析 .bat 文件字节流，UTF-8 中文被错误拆分为 GBK 字节序列
- **规避**：含中文的 .bat 文件必须用 PowerShell `[System.IO.File]::WriteAllText(path, text, [System.Text.Encoding]::GetEncoding(936))` 写入；纯英文 .bat 可用 Write 工具但建议统一用 PowerShell 写入保持一致性

### 陷阱 21：扫描正则误报（sha256 hash 片段匹配 API Key 模式）
- **现象**：扫描 PyInstaller 产物时中止构建，报"在 torch RECORD 中发现疑似 API Key 痕迹"
- **根因**：第三方库 dist-info/RECORD 文件含 sha256 hash（如 `9szU7E4S6KxiPatLJsk-trKzjJE0tUMSAsSlfOiR_3c`），其中 `sk-trKzjJE0tUMSAsSlfOiR_3c`（24 字符）匹配 `sk-[A-Za-z0-9]{20,}` 正则
- **规避**：扫描逻辑按目录层级区分递归策略——项目级文件（exe 同级）不递归（避免进入 `_internal/` 第三方库目录），项目子目录（config/scripts/static）递归；或扫描时排除 `*_RECORD` / `*.dist-info` 文件

### 陷阱 22：用错误编码读取已损坏内容后转码（二次破坏）
- **现象**：.ps1 文件丢失 BOM 后中文乱码，用 GBK 读取再转 UTF-8 BOM 后文件内容彻底损坏
- **根因**：文件已被错误编码解码后，中文字符已变为乱码 Unicode 码点，再转 UTF-8 BOM 只是给乱码内容加了 BOM 头，无法恢复原始中文
- **规避**：文件内容损坏时必须从版本控制恢复（`git checkout <file>`），不要尝试用编码转换修复已损坏的内容；转码前先验证源文件编码正确（读前 3 字节判 BOM + 用对应编码解码验证中文显示）

### 陷阱 23：Edit 工具修改 .ps1 后丢失 BOM
- **现象**：用 Edit 工具修改 build-exe.ps1 后，BOM 从 `EF BB BF` 变为 `23 20 73`（文件首字节，即 `# ` 的 UTF-8 编码）
- **根因**：Edit 工具默认以 UTF-8 无 BOM 编码写回文件，不保留原文件的 BOM
- **规避**：用 Edit 工具修改 .ps1 文件后，必须检查 BOM 是否丢失——读前 3 字节，如不是 `EF BB BF` 则用 `[System.IO.File]::WriteAllText(path, content, [New-Object System.Text.UTF8Encoding($true)])` 重新写入

### 陷阱 24：wmic 查询进程命令行输出为空
- **现象**：`wmic process where "ProcessId=<PID>" get CommandLine /format:list` 输出为空
- **根因**：wmic 在某些 Windows 版本/权限下可能不返回结果，且 wmic 在 Windows 11 22H2+ 已被标记为弃用
- **规避**：优先用 PowerShell 的 `Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" | Select-Object ProcessId, Name, CommandLine | Format-List`

### 陷阱 25：replace_all 替换格式遗漏
- **现象**：用 `replace_all` 替换 `:8000` → `:8001` 后，发现 `port 8000`、`8000 端口`、`LocalPort 8000`、`port=8000`、`port: 8000` 等格式未被替换
- **根因**：`replace_all` 只替换精确匹配的字符串，不同上下文的端口引用格式不同（冒号前缀、空格前缀、等号前缀、中文描述等）
- **规避**：批量替换端口号时，不能用单一模式 `replace_all`，必须先用 Grep 扫描所有出现位置，逐一确认上下文后精确替换；或对每种格式分别执行 `replace_all`

### 陷阱 26：subagent 并行修改同一文件竞争
- **现象**：subagent 并行修改同一文件的多个位置时，部分修改被覆盖丢失（如 14 处修改只生效了 3 处）
- **根因**：对同一文件的并行 Edit 存在竞争条件——后写入的 Edit 基于旧版文件内容，覆盖了先写入的 Edit
- **规避**：同一文件的多个 Edit 必须顺序执行（前一个完成后再执行下一个）；不同文件的 Edit 可并行。使用 subagent 时明确告知此约束

### 陷阱 27：全局参数变更扫描遗漏代码默认值
- **现象**：端口从 8000 改为 8001 后，第一轮扫描和修改完成，但最终验证发现 `yaml_config.py` 中 `port: int = 8000`（ServerConfig 默认值）、`templates.py` 中 `port = 8000`（config 读取失败时的 fallback）、`app.py` 注释中的启动示例、测试断言 `assert cfg.port == 8000` 均未修改
- **根因**：扫描时只关注了配置文件和脚本，忽略了代码中的默认值、fallback 值、注释、测试断言
- **规避**：全局参数变更时，必须参照「全局参数变更扫描检查清单」逐项检查，特别关注：Pydantic/BaseModel 字段默认值、typer.Option 默认值、try/except 中的兜底值、模块文档字符串中的启动示例、测试断言

### 陷阱 28：netstat 多进程监听同一端口不同地址
- **现象**：杀掉占用 `127.0.0.1:8000` 的旧进程后，端口仍被 `0.0.0.0:8000` 的另一个进程监听
- **根因**：netstat 可能返回多个进程监听同一端口的不同地址。`127.0.0.1:8000` 优先接收连接，掩盖了 `0.0.0.0:8000` 的存在。杀掉前者后，后者的 `0.0.0.0:8000` 暴露出来
- **规避**：`netstat -aon | findstr ":<PORT>.*LISTENING"` 返回多行时，提取所有 PID（去重），逐一查询进程命令行判断归属后处理

### 陷阱 29：Edit 工具修改 .bat 文件后修改未持久化
- **现象**：用 Edit 工具修改 `启动服务.bat` 第 78 行后，重新读取发现修改未生效
- **根因**：Edit 工具默认 UTF-8 编码写回，而 .bat 文件需要 GBK 编码。编码不匹配可能导致文件写入异常或内容被覆盖
- **规避**：.bat 文件改用纯 ASCII 编码后，Edit 工具可正常修改（ASCII 是 UTF-8 的子集，无编码冲突）。若 .bat 必须含中文（GBK），Edit 工具修改后必须重新读取验证，未持久化时用 PowerShell `WriteAllText` 以 GBK 编码写入

### 陷阱 30：chcp 65001 不能让 cmd.exe 用 UTF-8 解析 .bat 文件
- **现象**：.bat 文件含中文，加了 `chcp 65001`，仍报 `'绔瀯寤哄畬鎴?echo' 不是内部或外部命令`
- **根因**：`chcp 65001` 只改变控制台输出代码页，**不影响 cmd.exe 读取 .bat 文件内容的编码方式**。cmd.exe 始终按系统默认 ANSI（中文 Win 为 GBK）解析 .bat 文件字节流。UTF-8 编码的中文字节被 GBK 错误解码，导致命令被截断和乱码
- **规避**：.bat 文件不含中文（纯 ASCII），中文输出委托给 .ps1（UTF-8 BOM）。不要依赖 `chcp 65001` 解决 .bat 文件编码问题

### 陷阱 31：Write 工具无法创建 GBK 编码的 .bat 文件
- **现象**：用 Write 工具创建含中文 echo 的 .bat 文件，执行报错 `'哄共鍑€' 不是内部或外部命令`
- **根因**：Write 工具默认 UTF-8 无 BOM 编码写入文件，不支持 GBK 编码。cmd.exe 按系统 ANSI（GBK）解析 .bat 文件，UTF-8 中文被错误拆分为 GBK 字节序列
- **规避**：.bat 文件用纯 ASCII（Write 工具可直接创建）。若 .bat 必须含中文（GBK），必须用 PowerShell `[System.IO.File]::WriteAllText(path, text, [System.Text.Encoding]::GetEncoding(936))` 写入

### 陷阱 32：UTF-8 无 BOM + chcp 65001 仍导致 .bat 中文乱码
- **现象**：.bat 文件转为 UTF-8 无 BOM，设置 `chcp 65001`，移除了 BOM，但中文行仍被当作命令执行
- **根因**：cmd.exe 解析 .bat 文件内容的编码不受 `chcp` 影响（陷阱 30）。`chcp 65001` 只改变控制台输出代码页。即使移除 BOM，UTF-8 编码的中文仍被 cmd.exe 按 GBK 错误解码
- **规避**：.bat 文件不含非 ASCII 字符（纯 ASCII），从源头消除编码问题。三种组合都不可靠：UTF-8+BOM（BOM 破坏 @echo off）、UTF-8 无 BOM+chcp 65001（cmd 仍按 GBK 解析）、UTF-8 无 BOM 无 chcp（同前）

### 陷阱 33：ESM 模式下 __dirname 未定义
- **现象**：Node.js 项目 `package.json` 声明 `"type": "module"` 后，运行时报 `ReferenceError: __dirname is not defined`
- **根因**：ESM 模式下 Node.js 不提供 `__dirname` 和 `__filename` 全局变量，它们是 CJS 模式的专有变量
- **规避**：用 `import.meta.url` 派生 `__dirname`，并兼容 CJS 模式：
  ```typescript
  declare const __dirname: string;
  const dirname = typeof __dirname !== 'undefined'
    ? __dirname
    : path.dirname(fileURLToPath(import.meta.url));
  ```

### 陷阱 34：BOM 修复失败导致 null 字节残留
- **现象**：修复 .ps1 BOM 后，文件前 3 字节为 `00 00 00`，PS 5.1 报 `ParserError` 或中文仍乱码
- **根因**：用 `[byte[]](0xEF,0xBB,0xBF)` 创建 BOM 字节数组时，PS 5.1 将字面量列表解释为类型转换而非数组构造，结果创建了一个长度为 3 的 null 数组（所有元素为 0）。写入文件后留下 `00 00 00` 前缀，后续 BOM 检测看到 `00 00 00` 而非 `EF BB BF`，误判 BOM 仍丢失
- **规避**：BOM 修复流程必须先检测 null 残留（前 3 字节为 `00 00 00`）并移除，再添加 BOM。创建 BOM 字节数组用 `New-Object 'byte[]' 3` + 逐字节赋值（`$b[0]=0xEF; $b[1]=0xBB; $b[2]=0xBF`），不要用 `[byte[]](...)` 字面量语法

### 陷阱 35：.bat chcp 与 .ps1 输出编码不匹配导致中文乱码
- **现象**：.bat 设置 `chcp 65001`，.ps1 用 `Write-Host` 输出中文，cmd 窗口显示乱码（如 `锘?` 或 `???`）
- **根因**：.bat 的 `chcp 65001` 只改变 cmd 控制台的输出代码页为 UTF-8，但 .ps1 从 cmd.exe 调用时默认按系统 ANSI（GBK）输出到控制台。控制台用 UTF-8 解码 GBK 字节流，导致乱码。反方向（.bat chcp 936 + .ps1 UTF-8 输出）同样乱码
- **规避**：.ps1 开头必须强制对齐输出编码，与 .bat 的 chcp 匹配：
  - .bat `chcp 65001` ↔ .ps1 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
  - .bat `chcp 936` ↔ .ps1 `[Console]::OutputEncoding = [System.Text.Encoding]::GetEncoding(936)`
  - 用 try-catch 包裹（ISE/VS Code 终端等宿主不支持设置输出编码）

### 陷阱 36：PS 5.1 中 [byte[]](0xEF,0xBB,0xBF) 创建 null 数组
- **现象**：`$bom = [byte[]](0xEF,0xBB,0xBF); $bom.Length` 返回 3，但 `$bom[0]` 为 0（应为 0xEF）。用此数组写入文件后前 3 字节为 `00 00 00`
- **根因**：PS 5.1 的类型转换语义中，`[byte[]](0xEF,0xBB,0xBF)` 将整数字面量列表转换为 byte 数组时，发生隐式类型转换异常，结果创建为全 0 数组而非预期的 `[0xEF, 0xBB, 0xBF]`
- **规避**：用 `New-Object 'byte[]' 3` 创建数组 + 逐字节赋值：
  ```powershell
  $bomBytes = New-Object 'byte[]' 3
  $bomBytes[0] = 0xEF
  $bomBytes[1] = 0xBB
  $bomBytes[2] = 0xBF
  ```
  或直接用 `[System.IO.File]::WriteAllText(path, content, [New-Object System.Text.UTF8Encoding($true)])` 避免 byte 数组操作

### 陷阱 37：修复后的文件被还原为旧乱码版本
- **现象**：修复 .bat 乱码后（已转为纯 ASCII + chcp 65001），重新检查发现文件又变回旧的 GBK 乱码版本
- **根因**：可能原因——(1) 其他工具/脚本（如 git checkout、IDE 文件监视器、自动化构建）覆盖了修复后的文件；(2) subagent 并行修改同一文件时后写入覆盖先写入（陷阱 26 的变体）；(3) 桌面快捷方式指向旧路径，用户实际运行的是旧文件
- **规避**：
  1. 修复后立即用 `Read` 工具重新读取文件前 3 字节验证（不要假设修复已持久化）
  2. 多文件批量修复时，同一文件的多次修改必须顺序执行
  3. 检查桌面快捷方式（.lnk）的目标路径：`$sh = New-Object -ComObject WScript.Shell; $lnk = $sh.CreateShortcut('<lnk_path>'); $lnk.TargetPath`
  4. 如文件被 git 跟踪，用 `git status` 确认修改未被回滚

---