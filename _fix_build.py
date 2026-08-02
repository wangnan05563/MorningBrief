import sys
sys.stdout.reconfigure(encoding='utf-8')
c = open(r'D:\code\otherProjects\20_News\scripts\build-exe.ps1', 'r', encoding='utf-8').read()
old = '# 5.3.2 Copy BGM preset files\nWrite-Host "  [5.3.2] Copy BGM preset files..."\n = "\\backend\\data\\bgm\\preset"\n = "\\data\\bgm\\preset"\nif (Test-Path ) {\n    New-Item -ItemType Directory -Force (Split-Path ) | Out-Null\n    Copy-Item -Recurse -Force "\\*" \n     = (Get-ChildItem  -File).Count\n    Write-OK "BGM preset copied ( files)"\n} else {\n    Write-Warn "BGM preset source not found: "\n}'
new = '# 5.3.2 Copy BGM preset files\nWrite-Host "  [5.3.2] Copy BGM preset files..."\n = "\\backend\\data\\bgm\\preset"\n = "\\data\\bgm\\preset"\nif (Test-Path ) {\n    # Remove existing file with same name (from previous buggy build) before creating directory\n    if (Test-Path  -PathType Leaf) { Remove-Item -Force  }\n    New-Item -ItemType Directory -Force (Split-Path ) | Out-Null\n    Copy-Item -Recurse -Force "\\*" \n     = (Get-ChildItem  -File).Count\n    Write-OK "BGM preset copied ( files)"\n} else {\n    Write-Warn "BGM preset source not found: "\n}'
if old in c:
    c = c.replace(old, new)
    open(r'D:\code\otherProjects\20_News\scripts\build-exe.ps1', 'w', encoding='utf-8').write(c)
    print('Fixed build script')
else:
    print('Pattern not found')
    # Try to find and show the actual content
    idx = c.find('5.3.2')
    print(repr(c[idx:idx+500]))
