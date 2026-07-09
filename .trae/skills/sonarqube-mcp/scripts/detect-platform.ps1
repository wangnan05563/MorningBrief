# 平台检测脚本
# 用途：检测当前操作系统、Shell、可用工具，输出标准化的平台信息对象
# 入口：. .\scripts\detect-platform.ps1; $platform = Get-Platform
# 输出：
#   $platform.OS         - windows/linux/macos
#   $platform.Shell      - powershell/bash/zsh
#   $platform.PSVersion  - PowerShell 版本
#   $platform.Tools      - 可用工具字典（java/sonar-scanner/git/python/node）
#   $platform.Paths      - 路径分隔符（/ 或 \）
# 工具列表：优先从 config/core_config.json -> platform_tools 加载（v2.0），
#           否则回退到内置默认列表

[CmdletBinding()]
param(
    [string]$CoreConfigPath = "$PSScriptRoot\..\config\core_config.json"
)

# 工具列表优先级：配置文件 > 内置默认
$Script:DefaultTools = @("java", "sonar-scanner", "git", "python", "python3", "node", "npm", "pytest", "docker", "curl")

$Script:ConfiguredTools = $null
if (Test-Path $CoreConfigPath) {
    try {
        $cfg = Get-Content $CoreConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($cfg.platform_tools) {
            $tools = @()
            if ($cfg.platform_tools.required) { $tools += $cfg.platform_tools.required }
            if ($cfg.platform_tools.optional) { $tools += $cfg.platform_tools.optional }
            if ($tools.Count -gt 0) { $Script:ConfiguredTools = $tools }
        }
    } catch {}
}

function Get-Platform {
    $os = "unknown"
    $shell = "unknown"
    $psVersion = "0.0"

    if ($PSVersionTable) {
        $psVersion = $PSVersionTable.PSVersion.ToString()
    }

    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        $os = "windows"
        $shell = "powershell"
    } elseif ($IsLinux) {
        $os = "linux"
        $shell = if ($env:SHELL -match "zsh$") { "zsh" } else { "bash" }
    } elseif ($IsMacOS) {
        $os = "macos"
        $shell = if ($env:SHELL -match "zsh$") { "zsh" } else { "bash" }
    }

    # 工具列表：配置优先，否则默认
    $toolList = if ($Script:ConfiguredTools) { $Script:ConfiguredTools } else { $Script:DefaultTools }

    $tools = @{}
    foreach ($tool in $toolList) {
        $cmd = Get-Command $tool -ErrorAction SilentlyContinue
        if ($cmd) {
            $tools[$tool] = @{
                "Available" = $true
                "Path" = $cmd.Source
                "Version" = $null
            }
            try {
                $versionOutput = & $tool --version 2>$null
                if ($versionOutput) {
                    $tools[$tool].Version = ($versionOutput | Select-Object -First 1).ToString().Trim()
                }
            } catch {}
        } else {
            $tools[$tool] = @{ "Available" = $false; "Path" = $null; "Version" = $null }
        }
    }

    return [PSCustomObject]@{
        OS = $os
        Shell = $shell
        PSVersion = $psVersion
        Tools = $tools
        Paths = @{
            Separator = if ($os -eq "windows") { "\" } else { "/" }
            PathEnv = if ($os -eq "windows") { "Path" } else { "PATH" }
        }
        IsAdmin = Test-IsAdmin
    }
}

function Test-IsAdmin {
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } else {
        return ($env:USER -eq "root") -or ($env:USER -eq "")
    }
}

function Get-CrossPlatformPath {
    param(
        [Parameter(Mandatory = $true)][string[]]$PathParts,
        [string]$Platform = ""
    )
    if (-not $Platform) {
        $Platform = if ($IsWindows -or $env:OS -eq "Windows_NT") { "windows" } else { "linux" }
    }
    $sep = if ($Platform -eq "windows") { "\" } else { "/" }
    return ($PathParts -join $sep)
}

function Test-PortInUse {
    param(
        [Parameter(Mandatory = $true)][int]$Port
    )
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        try {
            if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
                $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
                return [bool]$conn
            }
            $result = netstat -ano 2>$null | Select-String ":$Port\s" | Select-String "LISTENING"
            return [bool]$result
        } catch {
            return $false
        }
    } else {
        # Linux/Mac 用 lsof 或 ss
        $result = (lsof -i :$Port 2>/dev/null) -or (ss -tln 2>/dev/null | Select-String ":$Port\s")
        return [bool]$result
    }
}

# Export-ModuleMember 仅在 .psm1 模块中有效，dot-source 加载时直接移除
# 所有函数通过 dot-source 自动注入调用方作用域
