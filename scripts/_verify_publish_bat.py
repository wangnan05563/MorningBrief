# -*- coding: utf-8 -*-
"""Validation for the MorningBrief one-click publish script.

Covers T02347 "ensure the script passes verification". Mirrors the byte-level
contract enforced by scripts/tests/bat-encoding.Tests.ps1 and
scripts/_verify_bat.py, then exercises the publish logic without building or
touching GitHub:

  1) 一键发布.bat byte contract: no UTF-8 BOM, CRLF only, ASCII-only,
     starts with '@echo off CRLF chcp 936', contains 'pause >nul CRLF exit /b 0'.
  2) publish-release.py compiles (py_compile).
  3) publish-release.py DRY_RUN prints the intended plan without network.
  4) cmd.exe smoke of 一键发布.bat with GH_DRY_RUN=1 + MB_SKIP_BUILD=1
     (uses the real existing installer, never uploads).
"""
import glob
import os
import py_compile
import re
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS)
BAT = os.path.join(SCRIPTS, "一键发布.bat")
PY = os.path.join(SCRIPTS, "publish-release.py")


def check(cond, msg):
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)
    print("[PASS]", msg)


def newest_setup():
    """Mirror the bat's `dir /b /o:-d` pick: newest installer wins."""
    files = glob.glob(os.path.join(REPO, "release", "MorningBrief-Setup-v*.exe"))
    return max(files, key=os.path.getmtime) if files else None


def version_of(path):
    m = re.match(r"^MorningBrief-Setup-v(.+)\.exe$", os.path.basename(path))
    return m.group(1) if m else None


def main():
    # ---- 1) .bat byte contract ----
    data = open(BAT, "rb").read()
    print("checking:", os.path.basename(BAT), len(data), "bytes")
    check(not data.startswith(b"\xef\xbb\xbf"), "no UTF-8 BOM")
    isolated = sum(1 for i, b in enumerate(data)
                   if b == 0x0A and (i == 0 or data[i - 1] != 0x0D))
    check(isolated == 0, "CRLF only (no isolated LF)")
    check(data.startswith(b"@echo off\r\nchcp 936"),
          "starts with '@echo off CRLF chcp 936'")
    check(sum(1 for b in data if b > 0x7F) == 0, "ASCII-only (no byte > 0x7F)")
    text = data.decode("ascii")
    check("pause >nul\r\nexit /b 0" in text,
          "contains 'pause >nul CRLF exit /b 0' tail")

    # ---- 2) publish-release.py compiles ----
    py_compile.compile(PY, doraise=True)
    print("[PASS] publish-release.py compiles")

    # ---- 3) functional DRY_RUN of the publisher (no network) ----
    with tempfile.TemporaryDirectory() as td:
        asset = os.path.join(td, "MorningBrief-Setup-v1.0.0.exe")
        open(asset, "wb").write(b"stub-asset-bytes")
        notes = os.path.join(td, "release-notes-1.0.0.md")
        open(notes, "w", encoding="utf-8").write("# MorningBrief 1.0.0\n\nstub notes\n")
        env = dict(os.environ, GH_DRY_RUN="1", GH_REPO="test/repo",
                   GH_TAG="1.0.0", GH_API_BASE="http://127.0.0.1:9")
        r = subprocess.run(
            [sys.executable, PY, asset, notes, "MorningBrief-Setup-v1.0.0.exe"],
            capture_output=True, text=True, env=env, timeout=60)
        out = r.stdout + r.stderr
        check(r.returncode == 0, "publish-release.py DRY_RUN exits 0 (rc=%d)" % r.returncode)
        check("DRY-RUN" in out, "publish-release.py prints DRY-RUN plan")
        check("test/repo" in out and "1.0.0" in out, "DRY-RUN plan shows repo+tag")

    # ---- 4) cmd.exe smoke of the full bat (build skipped, upload skipped) ----
    # The notes-generation branch only runs when no curated notes file exists for
    # the installer's version. Park any curated file so the "generate, then hand
    # the generated path to the publisher" path is actually exercised: with the
    # redirect pointing at the pre-block value the old bat wrote the curated
    # .md and handed the publisher a .auto.md that never existed.
    setup = newest_setup()
    check(setup is not None, "found an installer under release\\ to smoke against")
    ver = version_of(setup)
    check(ver is not None, "parsed version from %s" % os.path.basename(setup))
    plain = os.path.join(REPO, "release-notes-%s.md" % ver)
    auto = os.path.join(REPO, "release-notes-%s.auto.md" % ver)
    parked = None
    if os.path.isfile(plain):
        parked = plain + ".parked"
        os.replace(plain, parked)
    if os.path.isfile(auto):
        os.remove(auto)

    try:
        before = set(os.listdir(REPO))
        env = dict(os.environ, GH_DRY_RUN="1", MB_SKIP_BUILD="1",
                   GH_REPO="wangnan05563/MorningBrief", GH_TAG=ver)
        # cmd.exe runs under chcp 936 (GBK); decode console output as GBK.
        r = subprocess.run(
            ["cmd.exe", "/d", "/c", "(echo.)", "|", "call", BAT],
            capture_output=True, encoding="gbk", errors="replace", env=env, timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        check(r.returncode == 0, "cmd.exe smoke of 一键发布.bat exits 0 (rc=%d)" % r.returncode)
        check("DRY-RUN" in out, "smoke reaches DRY-RUN publish step")
        check("Locating installer" in out and "Version :" in out,
              "smoke locates installer + parses version")
        check("Publish Complete" in out, "smoke reaches Publish Complete")
        check(os.path.isfile(auto), "smoke wrote generated notes to %s" % os.path.basename(auto))
        check(not os.path.isfile(plain), "generated notes did not land in the curated .md")
        body = open(auto, encoding="utf-8").read() if os.path.isfile(auto) else ""
        check(re.search(r"^[0-9a-f]{7} ", body, re.M) is not None,
              "generated notes carry git log commits (stderr redirect not passed to git)")

        # cleanup any release-notes-*.auto.md generated during the smoke
        after = set(os.listdir(REPO))
        for f in (after - before):
            if f.startswith("release-notes-") and f.endswith(".auto.md"):
                try:
                    os.remove(os.path.join(REPO, f))
                    print("cleaned up generated notes:", f)
                except OSError:
                    pass
    finally:
        if parked:
            os.replace(parked, plain)
        if os.path.isfile(auto):
            os.remove(auto)

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
