"""T01925 取证二步：①相同 size 的疑似「同一份音频被发布到多个 key」做内容指纹比对；
②用 ffmpeg 全解码计数样本，拿「真实内容时长」——ffprobe 对无 Xing 的 CBR MP3 会给
size/bitrate 推算值，不能当实测时长用。

只读：Range GET（首/尾各 256KB）+ ffmpeg 解码到 null，不写库、不落盘音频。
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "backend", "data", "news.db")
FFMPEG = os.path.join(ROOT, "backend", "ffmpeg", "bin", "ffmpeg.exe")
URLS_482 = [15, 16, 18, 22, 23, 24, 25, 43, 48, 50, 52, 53, 58, 60]
URLS_720 = [26, 32, 44, 46]
CONTROL = [3, 19, 21, 87, 100]


def url_of(eid: int) -> str:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    u = con.execute("SELECT audio_url FROM episode WHERE id=?", (eid,)).fetchone()[0]
    con.close()
    p = urllib.parse.urlsplit(u)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), "", ""))


def range_get(u: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(u, headers={"Range": f"bytes={start}-{end}",
                                             "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:  # NOSONAR: 本项目自有 COS 只读
        return r.read()


def head_tail_md5(u: str, size: int) -> str:
    n = min(262144, size)
    return hashlib.md5(range_get(u, 0, n - 1) + range_get(u, size - n, size - 1)).hexdigest()


def decoded_seconds(u: str) -> float:
    """全解码计数：ffmpeg -f null 末尾 time= 是解码器实际吐出的最后时间戳。"""
    r = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-nostdin", "-i", u,
                        "-f", "null", "-"], capture_output=True, text=True,
                       errors="replace", timeout=900)
    m = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", r.stderr or "")
    if not m:
        raise RuntimeError((r.stderr or "")[-300:])
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    sizes = dict(con.execute(
        "SELECT e.id, x.sz FROM episode e JOIN "
        "(SELECT id AS i, 0 AS sz FROM episode) x ON 1=1 WHERE 0"))
    con.close()
    audit = {r["id"]: r for r in
             json.load(open(os.path.join(HERE, "t01925_duration_audit.json"),
                            encoding="utf-8"))["rows"] if r["status"] == "ok"}

    out = {"fingerprint": {}, "decode": {}}
    for label, ids in (("482", URLS_482), ("720", URLS_720), ("control", CONTROL)):
        print(f"--- {label} 首尾 256KB md5 ---")
        for i in ids:
            u = url_of(i)
            try:
                h = head_tail_md5(u, audit[i]["size"])
            except Exception as e:
                h = f"FAIL:{type(e).__name__}"
            out["fingerprint"][str(i)] = h
            print(f"ep{i} size={audit[i]['size']} md5={h[:16]} {h[-8:]}")

    print("--- 全解码真实时长 ---")
    for i in CONTROL + [15, 58]:
        u = url_of(i)
        try:
            d = round(decoded_seconds(u), 2)
        except Exception as e:
            d = f"FAIL:{type(e).__name__}:{str(e)[:80]}"
        out["decode"][str(i)] = {"ffprobe": audit.get(i, {}).get("duration"),
                                 "decoded": d, "db": audit.get(i, {}).get("db_duration")}
        print(f"ep{i} ffprobe={audit.get(i, {}).get('duration')} decoded={d} db={audit.get(i, {}).get('db_duration')}")

    with open(os.path.join(HERE, "t01925_fingerprint.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
