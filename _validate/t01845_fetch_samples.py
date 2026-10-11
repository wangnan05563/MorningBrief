"""T01845 样本采集：只读拉取本项目已发布的成品音频（评估口径要求用真实产物而非合成信号）。

只发 HTTPS GET，不写库、不改任何配置；URL 来自 backend/data/news.db 的 episode.audio_url。

用法：backend/.venv/Scripts/python.exe _validate/t01845_fetch_samples.py --limit 2
"""
import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "backend", "data", "news.db")
OUT = os.path.join(HERE, "t01845_samples")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT id, duration, audio_url FROM episode "
        "WHERE audio_url IS NOT NULL AND audio_url != '' ORDER BY id DESC LIMIT ?",
        (args.limit,),
    ).fetchall()
    con.close()

    got = []
    for eid, dur, url in rows:
        p = urllib.parse.urlsplit(url)
        u = urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), "", ""))
        try:
            with urllib.request.urlopen(  # NOSONAR: 只读本项目自有的公开 COS 成品地址
                urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30
            ) as r:
                blob = r.read()
        except Exception as e:
            print(f"[失败] ep{eid}: {type(e).__name__}: {str(e)[:120]}")
            continue
        path = os.path.join(OUT, f"ep{eid}.mp3")
        with open(path, "wb") as f:
            f.write(blob)
        got.append({"episode_id": eid, "db_duration_sec": dur, "bytes": len(blob), "path": path})
        print(f"[拉取] ep{eid} {len(blob)/1e6:.2f}MB -> {path}")
    with open(os.path.join(HERE, "t01845_samples.json"), "w", encoding="utf-8") as f:
        json.dump(got, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
