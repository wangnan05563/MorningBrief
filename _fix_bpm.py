import sys
sys.stdout.reconfigure(encoding='utf-8')
c = open(r'D:\code\otherProjects\20_News\scripts\build-exe.ps1', 'r', encoding='utf-8').read()
old = '    New-Item -ItemType Directory -Force (Split-Path ) | Out-Null\n    Copy-Item -Recurse -Force'
new = '    # Remove existing file with same name (from previous buggy build) before creating directory\n    if (Test-Path  -PathType Leaf) { Remove-Item -Force  }\n    New-Item -ItemType Directory -Force (Split-Path ) | Out-Null\n    Copy-Item -Recurse -Force'
if old in c:
    c = c.replace(old, new)
    open(r'D:\code\otherProjects\20_News\scripts\build-exe.ps1', 'w', encoding='utf-8').write(c)
    print('Fixed')
else:
    print('Not found')
