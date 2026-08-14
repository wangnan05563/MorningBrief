import ctypes, os, sys
kernel32 = ctypes.windll.kernel32
target = os.path.abspath('dist-verify')
failed = 0
def rm_file(p):
    global failed
    if not kernel32.DeleteFileW(p):
        failed += 1
def rm_dir(p):
    global failed
    if not kernel32.RemoveDirectoryW(p):
        failed += 1
if os.path.exists(target):
    for root, dirs, files in os.walk(target, topdown=False):
        for f in files:
            rm_file(os.path.join(root, f))
        for d in dirs:
            rm_dir(os.path.join(root, d))
    rm_dir(target)
# self delete
try:
    kernel32.DeleteFileW(os.path.abspath(__file__))
except Exception:
    pass
print('cleaned dist-verify; failed:', failed)
