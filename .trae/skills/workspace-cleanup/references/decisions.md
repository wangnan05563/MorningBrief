# 决策逻辑详解

> 本文详解 workspace-cleanup skill 中 7 个核心判断的逻辑推导与边界处理。
> 决策 1-4 为基础判断，决策 5-7 为 2026-07-05 第五轮清理复盘后新增的增强判断。
---

## 决策 1：文件是否属于垃圾？
### 判断流程

输入文件 X，依次判断：
1. X 命中 garbage_patterns？-> 是=垃圾，否-> Q2
2. X 在根目录？-> 否=保留，是-> Q3
3. X 在白名单（root_allowlist.files/extensions）？-> 是=保留，否=垃圾(trash模式)

### 关键边界
- .env 在白名单，但内容为乱码则按疑似垃圾标红
- 空文件(0字节)：默认不视为垃圾（如 .gitkeep），但若符合 redirect_artifacts 模式则视为垃圾
- 大文件(>10MB)在根目录：触发误重定向大文件高优先级判断，要求显式确认
- 配置未覆盖的新型文件：进入决策 7（模式推断）

---

## 决策 2：文件是否属于脚本？
### 判断流程

输入文件 X，依次判断：
1. X.ext 在 script_extensions？-> 否=非脚本，是-> Q2
2. X.path 在 script_exclude_dirs？-> 是=源码/测试，否-> Q3
3. X 是配置/数据文件？（按 content sniff）-> 是=非脚本，否=散落脚本-> Move

### 关键边界
- scripts/ 下的脚本：已就位，不动
- scripts/tests/ 下的脚本测试：是脚本的单元测试，保留
- 源码目录下的脚本（如 src/.../module.py）：是代码模块，不算散落脚本
- 同名 .py 在 src/ 和根目录：源码不动，根目录的若是工具脚本则 Move

---

## 决策 3：服务是否在运行？（三重检测 + 文件占用兜底）
### 判断流程

依次执行 4 项检测，任一命中即判定为运行中：
1. PID 文件：检查 service_indicators.pid_files -> 读 PID -> 验证进程存在
2. 端口监听：检查 service_indicators.ports -> netstat/lsof/ss
3. 进程名：检查 service_indicators.process_names / process_name_patterns
4. 文件占用探测（兜底）：检查 service_indicators.file_occupancy_probes -> 文件被占用=服务运行

### 关键边界
- PID 文件存在但进程已死 -> 记录 stale PID file 警告
- 多个 service_indicator 配置 -> 逐项检查，任一命中即判定运行中
- 文件占用检测失败（权限不足）-> 降级为仅用 PID+端口+进程名

### 检测优先级
PID 文件 > 端口监听 > 进程名 > 文件占用(兜底)

---

## 决策 4：操作是否安全？
### 判断流程

1. 置信度检查：文件匹配 confidence >= safety.min_confidence_to_delete？-> 否=标记可疑，需用户确认
2. 大文件检查：文件大小 > safety.large_file_threshold_mb MB？-> 是=二次确认
3. 批量检查：本次删除文件数 > safety.max_files_per_batch？-> 是=分批执行

### 关键边界
- min_confidence_to_delete=1.0：仅自动删除置信度100%的文件，其余全部需确认
- min_confidence_to_delete=0.8：置信度>=0.8自动删除，<0.8标记可疑
- large_file_threshold_mb=0：禁用大文件二次确认
- max_files_per_batch=0：不分批，一次性执行

---

## 决策 5：后台进程是否在持续创建文件？（新增）
### 背景
清理完成后，若存在并发 AI 会话或服务进程，可能在 wait_seconds 内重新生成垃圾文件，导致清理复发。

### 判断流程

1. 删除完成后记录文件快照 snapshot_after
2. 等待 stability_check.wait_seconds 秒
3. 复扫根目录得到 snapshot_now
4. 比较 snapshot_now - snapshot_after，检测新创建的文件
5. 匹配 recurrence_patterns 判断是否为已知后台进程产物
6. 按 recurrence_action 策略处理（warn/stop/soft_delete）
7. 超过 max_recurrence 次强制停止，提示用户排查后台进程

### 处理策略（recurrence_action）
- warn：仅记录警告，继续清理
- stop：尝试停止产生文件的进程
- soft_delete：将新文件重命名为 .trash 后缀

### 关键边界
- wait_seconds=0：跳过稳定性检查
- max_recurrence=0：不检查复发
- 有并发 AI 会话的项目：后台进程持续创建文件，清理后复发 -> 先排查并停止所有后台会话

---

## 决策 6：异常文件名如何处理？（新增）
### 背景
PowerShell 直接路径字符串在含特殊字符（逗号、空格、引号等）的文件名上可能失败。

### 判断流程

1. 扫描待删除文件，检查文件名是否含特殊字符（, . ! @ # $ % ^ & * ( )等）
2. 若有，且 safety.special_filename_handling = safe：
   - 使用 Get-ChildItem -File | Where-Object 匹配
   - 删除时用 Remove-Item -LiteralPath .FullName -Force
3. 若 safety.special_filename_handling = direct：
   - 直接使用路径字符串删除（适用于简单文件名）

### 安全处理模板（safe 模式）
`powershell
# 不要直接使用路径字符串
#  = Join-Path  "not enabled, try to fix it now."
# Remove-Item   # 可能因特殊字符失败

# 使用 Get-ChildItem + Where-Object 匹配
 = Get-ChildItem -Path  -File | Where-Object { .Name -like "not enabled*" }
if () { Remove-Item -LiteralPath .FullName -Force }
`

### 关键边界
- 误重定向产物常含特殊字符（如 <project_name>、<project_name>frontend）
- safe 模式比 direct 模式慢，但更可靠
- 若文件名含单引号/双引号，需用 -LiteralPath 而非 -Path

---

## 决策 7：配置缺失时如何推断垃圾模式？（新增）
### 背景
garbage_patterns 无法穷举所有可能的垃圾文件类型。当配置未覆盖某文件时，启用 detection 模式基于文件名特征自动推断。

### 判断流程

对未匹配 garbage_patterns 的根目录文件，依次检查：
1. name_patterns 匹配（如 test_*.py、run_*.py）-> 置信度 0.9
2. prefix_indicators 匹配（如 _、.tmp_ 前缀）-> 置信度 0.8
3. name_keywords 匹配（如 debug/diag/trace/verify）-> 置信度 0.7
4. 多源同时命中 -> 置信度 1.0

### 置信度评估

| 置信度 | 来源 | 处理 |
|---|---|---|
| 1.0 | 多源同时匹配 | 自动删除 |
| 0.9 | name_patterns 匹配 | 自动删除 |
| 0.8 | prefix_indicators 匹配 | 自动删除 |
| 0.7 | name_keywords 匹配 | 标记为疑似垃圾，需用户确认 |
| < 0.7 | 不匹配 | 保留 |

### 关键边界
- 置信度低于 infer_confidence_threshold 的文件仅标记，不自动删除
- 白名单优先：即使匹配推断模式，若在 root_allowlist 中则保留
- 推断模式不自动加入 garbage_patterns：避免污染配置，仅用于本次清理
- auto_add_inferred_to_gitignore: true 时，自动将推断模式加入 .gitignore

### 推断模式示例
`yaml
# 第五轮清理中通过推断识别的模式（已加入 .gitignore）
detection:
  name_patterns:
    - test_*.py        # 临时测试脚本（非 tests/ 目录）
    - run_*.py         # 临时运行脚本
    - run_*.js         # 临时运行 JS
    - git_*.py         # git 调试脚本
    - verify_*.py      # 验证脚本
    - _*.log           # _ 前缀日志
`

---

## 决策总结

| 决策 | 输入 | 输出 | 配置依赖 |
|---|---|---|---|
| 1. 是否垃圾 | 文件元数据 | Delete / Keep | garbage_patterns, root_allowlist |
| 2. 是否脚本 | 文件元数据 | Move / Keep | script_extensions, script_exclude_dirs |
| 3. 服务运行 | 服务状态 | Running / Stopped | service_indicators |
| 4. 操作安全 | 操作 + 文件 | Safe / Unsafe | safety |
| 5. 后台进程 | 文件快照对比 | Stable / Recurrence | stability_check |
| 6. 异常文件名 | 文件名 | Safe handling / Direct | safety.special_filename_handling |
| 7. 模式推断 | 文件元数据 | Inferred garbage / Keep | detection |

所有决策均通过配置驱动，无硬编码判断逻辑。