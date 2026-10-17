#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic GitHub Release publisher (zero dependencies, Python standard library only).

Atomically performs: create Release + attach notes (read from a Markdown file)
+ upload asset. Token is read from local .env (GH_TOKEN) first, then falls back
to the git credential store (git credential fill); it is never printed and never
committed (the .env is git-ignored).

Usage:
    python publish-release.py <asset-path> <notes-md-path> [asset-display-name]

Environment variables (all optional, auto-detected when missing):
    GH_REPO         repo slug owner/name. Default: inferred from
                    `git remote get-url origin`.
    GH_TAG          Release tag (= version). Default: `git describe --tags --abbrev=0`.
    GH_TOKEN        GitHub token. Read from local .env first, then from the git
                    credential store.
    GH_TARGET       target branch/commit. Default: current branch.
    GH_DRAFT       1 = draft. Default 0 (published).
    GH_PRERELEASE  1 = pre-release. Default 0.
    GH_API_BASE    API domain, default https://api.github.com.

Idempotent: existing Release is reused; existing asset is skipped. Network
jitters auto-retry.

Example (run from repo root):
    GH_TAG=1.2.3 GH_REPO=me/myapp python scripts/publish-release.py \
        release/MorningBrief-Setup-v1.2.3.exe release-notes-1.2.3.md
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def _load_dotenv():
    """Read config (GitHub Token, etc.) from local .env without overwriting
    existing environment variables.

    Search order: current working directory (repo root, bat has cd'd there)
    -> script directory. .env is git-ignored and never committed; for the
    in-repo template use .env.example.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    for d in (os.getcwd(), here):
        p = os.path.join(d, ".env")
        if p not in candidates:
            candidates.append(p)
    for p in candidates:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if len(v) >= 2 and v[0] in ("'", '"') and v[-1] == v[0]:
                        v = v[1:-1]
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


def _read_text(path):
    """Read a text file with encoding fallback: utf-8 -> gbk -> system default.

    Compatible with .md notes saved as GBK by Notepad on Chinese Windows.
    """
    import locale
    for enc in ("utf-8", "gbk", None):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, encoding=locale.getpreferredencoding(False)) as f:
        return f.read()


_load_dotenv()

API_BASE = os.environ.get("GH_API_BASE", "https://api.github.com").rstrip("/")
REPO = (os.environ.get("GH_REPO") or "").strip()
TAG = (os.environ.get("GH_TAG") or "").strip()
TOKEN = (os.environ.get("GH_TOKEN") or "").strip()
TARGET = (os.environ.get("GH_TARGET") or "").strip()
DRAFT = os.environ.get("GH_DRAFT", "0") == "1"
PRERELEASE = os.environ.get("GH_PRERELEASE", "0") == "1"
DRY_RUN = os.environ.get("GH_DRY_RUN", "0") == "1"


def sh(cmd):
    """Run a shell command, return stdout (empty string on failure, no throw)."""
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def detect_repo():
    url = sh("git remote get-url origin")
    # support both https and ssh formats
    url = url.replace("git@github.com:", "https://github.com/").replace(".git", "")
    if "github.com/" in url:
        return url.split("github.com/", 1)[1].strip("/")
    return ""


def detect_tag():
    return sh("git describe --tags --abbrev=0")


def detect_branch():
    b = sh("git rev-parse --abbrev-ref HEAD")
    return b or "master"


def fetch_token():
    """Reuse the github.com password (your PAT/credential) from the git
    credential store.

    Must feed stdin via a Python subprocess directly; do NOT rely on shell
    `printf | git credential fill` (native CMD on Windows has no printf, fails
    in a .bat environment).
    """
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, timeout=30,
        )
        for line in (proc.stdout or "").splitlines():
            if line.startswith("password="):
                return line[len("password="):].strip()
    except Exception:
        pass
    return ""


def api(path, data=None, method=None, base=None):
    base = base or API_BASE
    body = json.dumps(data).encode("utf-8") if data is not None else None
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                base + path, data=body,
                method=method or ("POST" if body else "GET"),
                headers={
                    "Authorization": "Bearer " + TOKEN,
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "publish-release",
                    "Content-Type": "application/json",
                })
            with urllib.request.urlopen(req, timeout=90) as r:
                txt = r.read().decode("utf-8")
                return r.status, (json.loads(txt) if txt else None)
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(payload) if payload else None
            except Exception:
                parsed = None
            last = (e.code, parsed or payload)
            # 409/422: tag or release already exists -> caller reuses it
            if e.code in (409, 422):
                return e.code, parsed
            if e.code in (403, 429, 500, 502, 503):
                time.sleep(10)
                continue
            return last
        except Exception as e:  # connection reset / empty response
            last = ("EXC", str(e))
            time.sleep(10)
    return last


def get_existing_release_by_tag(tag):
    st, resp = api(f"/repos/{REPO}/releases/tags/{tag}")
    if st == 200 and isinstance(resp, dict):
        return resp
    return None


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: python publish-release.py <asset-path> <notes-md-path> [asset-display-name]")
    asset = os.path.abspath(sys.argv[1])
    notes = os.path.abspath(sys.argv[2])
    display_name = sys.argv[3] if len(sys.argv) > 3 else os.path.basename(asset)

    global REPO, TAG, TOKEN, TARGET
    if not REPO:
        REPO = detect_repo()
    if not TAG:
        TAG = detect_tag()
    if not TOKEN:
        TOKEN = fetch_token()
    if not TARGET:
        TARGET = detect_branch()

    if not REPO:
        sys.exit("cannot determine repo (GH_REPO unset and git remote has no github.com origin)")
    if not TAG:
        sys.exit("cannot determine tag (GH_TAG unset and no git tag)")
    if not os.path.isfile(asset):
        sys.exit(f"asset not found: {asset}")
    if not os.path.isfile(notes):
        sys.exit(f"notes file not found: {notes}")

    print(f"repo={REPO}  tag={TAG}  target={TARGET}  draft={DRAFT} prerelease={PRERELEASE}")
    print(f"asset={asset}\nnotes={notes}")

    body = _read_text(notes)

    # ---- 0) DRY-RUN: only print the intended actions, never touch GitHub ----
    if DRY_RUN:
        size = os.path.getsize(asset)
        print("\n[DRY-RUN] the following actions will [NOT] actually execute:")
        print(f"  POST /repos/{REPO}/releases")
        print(f"    tag_name   = {TAG}")
        print(f"    target     = {TARGET}")
        print(f"    name       = {display_name}")
        print(f"    draft      = {DRAFT}  prerelease = {PRERELEASE}")
        print(f"    body length= {len(body)} chars")
        print(f"  UPLOAD asset = {display_name}  ({size} bytes)")
        print("  (set GH_DRY_RUN=0 or clear it and rerun to actually publish)")
        return

    if len(TOKEN) < 20:
        sys.exit("GH_TOKEN missing (git credential store has no github.com credential either)")

    # ---- 1) create Release (reuse if it already exists) ----
    st, resp = api(f"/repos/{REPO}/releases", {
        "tag_name": TAG,
        "target_commitish": TARGET,
        "name": display_name,
        "body": body,
        "draft": DRAFT,
        "prerelease": PRERELEASE,
    })
    if st not in (200, 201) and st not in (409, 422):
        print("create release failed:", st, json.dumps(resp, ensure_ascii=False)[:800])
        sys.exit(1)

    if isinstance(resp, dict) and "upload_url" in resp:
        release = resp
    else:
        # creation conflict -> fetch existing Release by tag
        release = get_existing_release_by_tag(TAG)
        if not release:
            print("cannot fetch existing Release, exiting.", json.dumps(resp, ensure_ascii=False)[:400])
            sys.exit(1)
    print("release id:", release.get("id"), "html:", release.get("html_url"))

    # ---- 2) upload asset (skip if it already exists) ----
    assets = release.get("assets") or []
    already = {a.get("name") for a in assets}
    if display_name in already:
        print("asset already exists, skipping upload:", display_name)
        return

    upload_url = release["upload_url"].split("{")[0] + "?name=" + urllib.parse.quote(display_name)
    size = os.path.getsize(asset)
    data = open(asset, "rb").read()
    print("uploading", display_name, f"{size} bytes ...")
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                upload_url, data=data, method="POST",
                headers={
                    "Authorization": "Bearer " + TOKEN,
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "publish-release",
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(size),
                })
            with urllib.request.urlopen(req, timeout=1800) as r:
                j = json.loads(r.read().decode("utf-8"))
                print("asset uploaded:", r.status, j.get("name"), j.get("size"), j.get("browser_download_url"))
            return
        except Exception as e:
            last = e
            print(f"  upload attempt {attempt + 1} failed: {str(e)[:200]}")
            time.sleep(15)
    sys.exit(f"asset upload failed: {last}")


if __name__ == "__main__":
    main()
