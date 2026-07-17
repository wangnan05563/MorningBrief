## 编码写入方法规范

用 PowerShell 操作文件编码时，**写入方法的选择至关重要**，错误的方法会导致 BOM 丢失或编码错误。

### 方法对照表

| 目标编码 | 编码对象构造 | 正确写入方法 | 错误写入方法（BOM 丢失） |
|----------|-------------|-------------|------------------------|
| GBK 无 BOM | `[System.Text.Encoding]::GetEncoding(936)` | `WriteAllText(path, text, enc)` | — |
| UTF-8 with BOM | `New-Object System.Text.UTF8Encoding($true)` | `WriteAllText(path, text, enc)` | `enc.GetBytes(text)` + `WriteAllBytes`（BOM 丢失） |
| UTF-8 无 BOM | `New-Object System.Text.UTF8Encoding($false)` | `WriteAllText(path, text, enc)` | — |

### 关键规则

1. **`UTF8Encoding($true).GetBytes(text)` 不会自动添加 BOM**：`emitBOM` 参数只在 `WriteAllText` / `WriteAllBytes` 配合 preamble 时生效。必须用 `[System.IO.File]::WriteAllText($path, $text, $utf8WithBom)` 才能正确写入 BOM。

2. **`GetEncoding(936)` 在 PS 5.1 不支持 3 参数重载**：`GetEncoding(int, EncoderFallback, DecoderFallback)` 在 PS 5.1 的 .NET API 中不可用。改用默认的 `GetEncoding(936)`（带 `DecoderReplacementFallback`），通过检查解码结果是否含 `U+FFFD` 替换字符判断合法性。

3. **`System.Text.Encoding` 是抽象基类不能实例化**：`New-Object System.Text.Encoding` 会报错。必须用静态方法 `[System.Text.Encoding]::GetEncoding()` 或 `[System.Text.Encoding]::UTF8`。

4. **行尾转换**：写入前必须将 LF 转为 CRLF：`$crlf = $text -replace "`r?`n", "`r`n"`

### 写入纯 ASCII .bat 文件的完整模式（首选）

```powershell
# 1. 准备内容（纯 ASCII，不含任何非 ASCII 字符）
$content = @'
@echo off
echo Build started
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
'@

# 2. 转换行尾为 CRLF
$crlf = $content -replace "`r?`n", "`r`n"

# 3. 用 ASCII 编码写入（无 BOM）
# ASCII 编码天然无 BOM，且 Write/Edit 工具默认 UTF-8 也兼容纯 ASCII
$ascii = [System.Text.Encoding]::ASCII
[System.IO.File]::WriteAllText($targetPath, $crlf, $ascii)
```

**注意**：纯 ASCII 内容用 Write 工具直接创建也可（UTF-8 编码的 ASCII 子集与纯 ASCII 字节相同）。

### 写入 GBK .bat 文件的完整模式（备选，仅当 .bat 必须含中文时）

```powershell
# 1. 准备内容（UTF-8 字符串，含中文）
$content = @'
@echo off
chcp 936 >nul 2>&1
echo 中文提示
'@

# 2. 转换行尾为 CRLF
$crlf = $content -replace "`r?`n", "`r`n"

# 3. 用 GBK 编码写入（无 BOM）
# ⚠️ Write/Edit 工具不支持 GBK，必须用 PowerShell WriteAllText
$gbk = [System.Text.Encoding]::GetEncoding(936)
[System.IO.File]::WriteAllText($targetPath, $crlf, $gbk)
```

### 写入中文 .ps1 文件的完整模式

```powershell
# 1. 准备内容
$content = @'
Write-Host "中文提示"
'@

# 2. 转换行尾为 CRLF
$crlf = $content -replace "`r?`n", "`r`n"

# 3. 用 UTF-8 with BOM 编码写入
$utf8WithBom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($targetPath, $crlf, $utf8WithBom)
```

### Edit 工具修改后的 BOM 检查流程

用 Edit 工具修改 .ps1 文件后，**必须**检查 BOM 是否丢失（Edit 工具默认 UTF-8 无 BOM 写回）。同时检测 null 字节残留（前次 BOM 修复失败可能留下 `00 00 00` 前缀）：

```powershell
# 1. 读取修改后文件的前 6 字节（检测 BOM + null 残留）
$bytes = [System.IO.File]::ReadAllBytes($ps1Path)
$head = "{0:X2} {1:X2} {2:X2} {3:X2} {4:X2} {5:X2}" -f $bytes[0], $bytes[1], $bytes[2], $bytes[3], $bytes[4], $bytes[5]

# 2. 检测 null 字节残留（前次 BOM 修复失败导致 00 00 00 前缀）
#    根因：[byte[]](0xEF,0xBB,0xBF) 在 PS 5.1 创建 null 数组（陷阱 36），写入后留 null 字节
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0 -and $bytes[1] -eq 0 -and $bytes[2] -eq 0) {
    Write-Host "[WARN] 检测到 null 字节残留（00 00 00 前缀），清理中..." -ForegroundColor Yellow
    # 移除前 3 个 null 字节
    $bytes = $bytes[3..($bytes.Length - 1)]
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $content = $utf8NoBom.GetString($bytes)
    # 重新写入（暂无 BOM，下一步添加）
    [System.IO.File]::WriteAllText($ps1Path, $content, $utf8NoBom)
    # 重新读取
    $bytes = [System.IO.File]::ReadAllBytes($ps1Path)
}

# 3. 检查 BOM 是否丢失，如丢失则重新添加
$bom = "{0:X2} {1:X2} {2:X2}" -f $bytes[0], $bytes[1], $bytes[2]
if ($bom -ne "EF BB BF") {
    # 用 UTF-8 无 BOM 读取当前内容（避免二次转码损坏）
    $content = [System.IO.File]::ReadAllText($ps1Path, [System.Text.UTF8Encoding]::new($false))
    # 用 UTF-8 with BOM 重新写入（必须用 WriteAllText，不能用 GetBytes+WriteAllBytes，见陷阱 11）
    $utf8WithBom = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($ps1Path, $content, $utf8WithBom)
}

# 4. 验证 BOM 已恢复
$bytes2 = [System.IO.File]::ReadAllBytes($ps1Path)
$bom2 = "{0:X2} {1:X2} {2:X2}" -f $bytes2[0], $bytes2[1], $bytes2[2]
if ($bom2 -eq "EF BB BF") { Write-Host "BOM preserved" } else { Write-Host "BOM STILL MISSING" -ForegroundColor Red }
```

**关键规则**：
- 检查 BOM 时用 `ReadAllBytes` 读字节，不要用 `Get-Content`（Get-Content 会自动解码）
- **先检测 null 残留再检测 BOM**：null 字节（`00 00 00`）会干扰 BOM 判断，必须先清理
- 重新添加 BOM 时用 `UTF8Encoding($false)` 读取当前内容（避免用错误编码读取已损坏内容）
- 用 `UTF8Encoding($true)` + `WriteAllText` 写回（不能用 `GetBytes` + `WriteAllBytes`，见陷阱 11）
- **不要用 `[byte[]](0xEF,0xBB,0xBF)` 创建 BOM 字节数组**：PS 5.1 中此语法创建 null 数组（陷阱 36），必须用 `New-Object 'byte[]' 3` + 逐字节赋值

---