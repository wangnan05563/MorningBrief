
import sys
path = r'D:/code/otherProjects/20_News/scripts/build-exe.ps1'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 293-312 (1-indexed) = indices 292-311 (0-indexed)
new_block = '''# 5.3.0 Sync DB from backend to dist
Write-Host "  [5.3.0] Sync DB..."
$dbSrc = "$repoRoot\\backend\\data\\news.db"
$dbDst = "$distDir\\data\\news.db"
if ((Test-Path $dbSrc) -and (Test-Path "$distDir\\data")) {
    $srcLen = (Get-Item $dbSrc).Length
    $dstLen = (Test-Path $dbDst) ? (Get-Item $dbDst).Length : 0
    if ($srcLen -ge 1MB -and $srcLen -ne $dstLen) {
        Copy-Item $dbSrc $dbDst -Force
        Write-OK "DB synced ($([math]::Round($srcLen/1MB,1)) MB)"
    }
}

# 5.3.1 Seed admin user
Write-Host "  [5.3.1] Seed admin..."
$seedSrc = "$repoRoot\\backend\\seed_admin.py"
if (Test-Path $seedSrc) {
    & $buildPython $seedSrc
    Write-OK "admin seeded"
}

# 5.3.2 Copy BGM preset files
Write-Host "  [5.3.2] Copy BGM preset files..."
$bgmSrc = "$repoRoot\\backend\\data\\bgm\\preset"
$bgmDst = "$distDir\\data\\bgm\\preset"
if (Test-Path $bgmSrc) {
    New-Item -ItemType Directory -Force (Split-Path $bgmDst) | Out-Null
    Copy-Item -Recurse -Force "$bgmSrc\\*" $bgmDst
    $bgmCount = (Get-ChildItem $bgmDst -File).Count
    Write-OK "BGM preset copied ($bgmCount files)"
} else {
    Write-Warn "BGM preset source not found: $bgmSrc"
}
'''

# Replace lines 292-311 (0-indexed) with new block
result = lines[:292] + [new_block + '
'] + lines[312:]
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(result)
print('Fixed build-exe.ps1')
print('Total lines:', len(result))
