## Sandbox 限制处理策略

在受限环境中执行脚本验证时，可能遇到以下限制及对应处理方式：

| 限制 | 现象 | 处理方式 |
|------|------|----------|
| `cmd /c` 被阻止 | "invalid command: The use of 'cmd /c' is blocked" | 改用 PowerShell 直接读取文件字节 + 编码对象解码验证中文 |
| 嵌套 `powershell.exe` 被阻止 | 无法 Start-Job 或嵌套调用 | 在当前会话用 `&` 直接执行，用临时文件捕获输出 |
| 内联 `$变量` 被外层 shell 吞掉 | 变量值为空 | 改用临时 .ps1 脚本文件（全英文代码避免 BOM 问题） |
| `>nul` 重定向不兼容 | PowerShell 终端中 cmd 重定向报错 | 改用 `2>&1 \| Out-Null` |
| 临时 .ps1 无 BOM 中文乱码 | PS 5.1 按 GBK 解析无 BOM 脚本 | 临时脚本全用英文代码；需中文时用 `[char]0xXXXX` 构造 |

### 验证中文显示的替代方案（无法用 cmd /c 时）

```powershell
# 读取文件字节，用对应编码解码显示，验证中文正确性
$gbk = [System.Text.Encoding]::GetEncoding(936)
$utf8 = New-Object System.Text.UTF8Encoding($true)

$targets = @(
    @{ Path = '<BAT_FILE>'; Enc = $gbk },     # .bat 用 GBK 解码
    @{ Path = '<PS1_FILE>'; Enc = $utf8 }     # .ps1 用 UTF-8 BOM 解码
)

foreach ($t in $targets) {
    $b = [System.IO.File]::ReadAllBytes($t.Path)
    $text = $t.Enc.GetString($b)
    $lines = $text -split "`r`n"
    $lines | Select-Object -First 8 | ForEach-Object { Write-Host $_ }
}
```

---

## 常见陷阱与规避