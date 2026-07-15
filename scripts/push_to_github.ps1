# MorningBrief push to GitHub via Git Database API (batch commit)
# Strategy: 1) Use Contents API to init repo with .gitignore (handles empty repo)
#           2) Use Git Database API (blobs/tree/commit) to push all files in one commit
# Usage: powershell -ExecutionPolicy Bypass -File scripts\push_to_github.ps1 -Token <PAT>

param(
    [Parameter(Mandatory=$true)]
    [string]$Token,
    [string]$Owner = "wangnan05563",
    [string]$Repo  = "MorningBrief",
    [string]$Branch = "main",
    [string]$CommitMessage = "chore: init MorningBrief project"
)

$ErrorActionPreference = "Stop"
$ApiBase = "https://api.github.com/repos/$Owner/$Repo"
$Headers = @{
    "Authorization" = "Bearer $Token"
    "Accept"        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

Write-Host "=== Push MorningBrief to GitHub ===" -ForegroundColor Cyan
Write-Host "Repo: $Owner/$Repo (branch: $Branch)"
Write-Host ""

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$ExcludePatterns = @(
    '\.git[\\/]',
    '__pycache__',
    '\.env$',
    '\.pyc$',
    'node_modules[\\/]',
    '[\\/]dist[\\/]',
    '[\\/]build[\\/]',
    '\.npm[\\/]',
    '\.pnpm-store[\\/]',
    'scripts[\\/]push_to_github\.ps1$',
    'scripts[\\/]files_meta\.json$'
)

$AllFiles = Get-ChildItem -Path $ProjectRoot -Recurse -File -Force |
    Where-Object {
        $rel = $_.FullName.Substring($ProjectRoot.Length + 1)
        $skip = $false
        foreach ($p in $ExcludePatterns) { if ($rel -match $p) { $skip = $true; break } }
        -not $skip
    } | Sort-Object FullName

Write-Host "[1/6] Files collected: $($AllFiles.Count)" -ForegroundColor Yellow

# 2. Check if repo is empty; if empty, initialize with .gitignore via Contents API
Write-Host "[2/6] Checking repo state..." -ForegroundColor Yellow
$repoEmpty = $false
try {
    $refResp = Invoke-RestMethod -Uri "$ApiBase/git/refs/heads/$Branch" -Method Get -Headers $Headers
    $parentSha = $refResp.object.sha
    Write-Host "  Repo has commits, parent: $parentSha" -ForegroundColor DarkGray
} catch {
    $repoEmpty = $true
    Write-Host "  Repo is empty, initializing with .gitignore via Contents API..." -ForegroundColor DarkGray
    $gitignoreFile = $AllFiles | Where-Object { $_.FullName.Substring($ProjectRoot.Length + 1) -eq '.gitignore' } | Select-Object -First 1
    if (-not $gitignoreFile) { throw ".gitignore not found" }
    $content = [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($gitignoreFile.FullName))
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($content))
    $initBody = @{ message = "init repo"; content = $b64 } | ConvertTo-Json -Compress
    $initResp = Invoke-RestMethod -Uri "$ApiBase/contents/.gitignore" -Method Put -Headers $Headers -Body $initBody -ContentType "application/json"
    $parentSha = $initResp.commit.sha
    Write-Host "  Repo initialized, parent commit: $parentSha" -ForegroundColor DarkGray
    # Remove .gitignore from file list (already committed)
    $AllFiles = $AllFiles | Where-Object { $_.FullName -ne $gitignoreFile.FullName }
    Write-Host "  Remaining files: $($AllFiles.Count)" -ForegroundColor DarkGray
}

# 3. Create Git Blobs for all remaining files
Write-Host "[3/6] Creating Git Blobs..." -ForegroundColor Yellow
$Blobs = @()
$i = 0
foreach ($file in $AllFiles) {
    $i++
    $relPath = $file.FullName.Substring($ProjectRoot.Length + 1) -replace '\\','/'
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName)
    $b64 = [Convert]::ToBase64String($bytes)

    $body = @{ content = $b64; encoding = "base64" } | ConvertTo-Json -Compress
    try {
        $resp = Invoke-RestMethod -Uri "$ApiBase/git/blobs" -Method Post -Headers $Headers -Body $body -ContentType "application/json"
        $Blobs += @{ path = $relPath; sha = $resp.sha; mode = "100644"; type = "blob" }
        if ($i % 10 -eq 0 -or $i -eq $AllFiles.Count) {
            Write-Host "  [$i/$($AllFiles.Count)] done" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "  [$i/$($AllFiles.Count)] $relPath FAILED: $($_.Exception.Message)" -ForegroundColor Red
        throw
    }
}

# 4. Create Git Tree from all blobs (base on parent tree)
Write-Host "[4/6] Creating Git Tree..." -ForegroundColor Yellow
$TreeBody = @{ base_tree = $parentSha; tree = $Blobs } | ConvertTo-Json -Depth 5 -Compress
$treeResp = Invoke-RestMethod -Uri "$ApiBase/git/trees" -Method Post -Headers $Headers -Body $TreeBody -ContentType "application/json"
Write-Host "  Tree SHA: $($treeResp.sha)" -ForegroundColor DarkGray

# 5. Create Commit with parent
Write-Host "[5/6] Creating Commit..." -ForegroundColor Yellow
$commitBody = @{
    message = $CommitMessage
    tree    = $treeResp.sha
    parents = @($parentSha)
} | ConvertTo-Json -Depth 5 -Compress
$commitResp = Invoke-RestMethod -Uri "$ApiBase/git/commits" -Method Post -Headers $Headers -Body $commitBody -ContentType "application/json"
Write-Host "  Commit SHA: $($commitResp.sha)" -ForegroundColor DarkGray

# 6. Update branch ref to new commit
Write-Host "[6/6] Updating branch $Branch..." -ForegroundColor Yellow
$refBody = @{ sha = $commitResp.sha; force = $false } | ConvertTo-Json -Compress
$updateResp = Invoke-RestMethod -Uri "$ApiBase/git/refs/heads/$Branch" -Method Patch -Headers $Headers -Body $refBody -ContentType "application/json"
Write-Host "  Branch updated to $($commitResp.sha)" -ForegroundColor DarkGray

Write-Host ""
Write-Host "=== Push Complete ===" -ForegroundColor Green
Write-Host "URL: https://github.com/$Owner/$Repo" -ForegroundColor Cyan
Write-Host "Files: $($AllFiles.Count + $(if ($repoEmpty) {1} else {0}))" -ForegroundColor Cyan
Write-Host "Commit: $CommitMessage" -ForegroundColor Cyan
