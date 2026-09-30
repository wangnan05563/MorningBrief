# -*- coding: utf-8 -*-
"""Mirror scripts/tests/bat-encoding.Tests.ps1 byte-level assertions for the
startup batch (the .bat that references start.ps1). Pure offline check so we get
a deterministic signal independent of the sandbox's safe-delete wrapper on the
test's temp-dir cleanup step.
"""
import os
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def find_startup_bat():
    for fn in os.listdir(SCRIPTS):
        if not fn.lower().endswith(".bat"):
            continue
        p = os.path.join(SCRIPTS, fn)
        data = open(p, "rb").read()
        try:
            s = data.decode("gbk")
        except Exception:
            s = data.decode("latin-1")
        if "start.ps1" in s:
            return p, data
    return None, None


def main():
    p, data = find_startup_bat()
    if not p:
        print("FAIL: could not locate startup batch (contains start.ps1)")
        return 1
    print("checking:", os.path.basename(p), len(data), "bytes")

    # 1. no UTF-8 BOM
    if data[:3] == b"\xef\xbb\xbf":
        print("FAIL: UTF-8 BOM present")
        return 1
    # 2. no isolated LF
    isolated = 0
    for i, b in enumerate(data):
        if b == 0x0A and (i == 0 or data[i - 1] != 0x0D):
            isolated += 1
    if isolated != 0:
        print("FAIL: %d isolated LF line endings (CRLF required)" % isolated)
        return 1
    # 3. starts with @echo off CRLF chcp 936
    if not data.startswith(b"@echo off\r\nchcp 936"):
        print("FAIL: does not start with '@echo off CRLF chcp 936'")
        return 1
    # 4. ASCII-only (no byte > 0x7F)
    non_ascii = sum(1 for b in data if b > 0x7F)
    if non_ascii != 0:
        print("FAIL: %d non-ASCII bytes (must be ASCII-only)" % non_ascii)
        return 1
    # 5. ends with pause >nul CRLF exit /b 0
    text = data.decode("ascii")
    if "pause >nul\r\nexit /b 0" not in text:
        print("FAIL: missing 'pause >nul CRLF exit /b 0' tail")
        return 1

    print("[PASS] byte-level encoding/line-ending/ascii assertions")

    # 6. cmd.exe smoke test with a stub start.ps1
    smoke = tempfile.mkdtemp(prefix="mb-bat-smoke-")
    try:
        bat = os.path.join(smoke, "start-service.bat")
        with open(bat, "wb") as f:
            f.write(data)
        with open(os.path.join(smoke, "start.ps1"), "w", encoding="ascii") as f:
            f.write("exit 0\r\n")
        proc = subprocess.run(
            ["cmd.exe", "/d", "/c", "(echo.)", "|", "call", bat],
            capture_output=True, text=True, shell=False,
        )
        out = proc.stdout + proc.stderr
        if proc.returncode != 0:
            print("FAIL: cmd.exe smoke test exit=%d\n%s" % (proc.returncode, out[-2000:]))
            return 1
        if "not recognized" in out or "\n'" in out:
            print("FAIL: cmd.exe split a batch line\n%s" % out[-2000:])
            return 1
        print("[PASS] cmd.exe smoke test (exit 0, well-formed)")
    finally:
        # best-effort cleanup; ignore sandbox safe-delete errors here
        try:
            for root, dirs, files in os.walk(smoke, topdown=False):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except Exception:
                        pass
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root, d))
                    except Exception:
                        pass
            os.rmdir(smoke)
        except Exception:
            pass
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
