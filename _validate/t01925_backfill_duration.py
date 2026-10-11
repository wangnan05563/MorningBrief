"""T01925 历史数据时长重算：把 episode.duration 校正为成品实测时长。

变更类脚本，默认 dry-run 只打印将要改什么，不落库。真跑必须先备份库：
    cp backend/data/news.db backend/data/news.db.bak-t01925
    backend/.venv/Scripts/python.exe _validate/t01925_backfill_duration.py --apply

只按 episode.audio_url 探测（ffprobe 直连 https，单次 ~0.9s，不整段下载）；
本地相对路径（/audio/...）无法探测，跳过并如实记录。
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "backend", "data", "news.db")
FFPROBE = os.path.join(ROOT, "backend", "ffmpeg", "bin", "ffprobe.exe")
OUT = os.path.join(HERE, "t01925_backfill.json")


def probe(url: str):
    p = urllib.parse.urlsplit(url)
    u = urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), "", ""))
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", u],
                       capture_output=True, text=True, errors="replace", timeout=60)
    if r.returncode != 0:
        return None
    try:
        return int(round(float(r.stdout.strip())))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写库（跑前先备份 news.db）")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（试跑用）")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT id, duration, audio_url FROM episode "
        "WHERE audio_url IS NOT NULL AND audio_url != '' ORDER BY id"
    ).fetchall()
    if args.limit:
        rows = rows[: args.limit]

    plan, skipped, failed = [], [], []
    for eid, cur, url in rows:
        if not url.startswith(("http://", "https://")):
            skipped.append({"id": eid, "reason": "local_path", "url": url})
            continue
        real = probe(url)
        if real is None:
            failed.append({"id": eid, "url": url})
            continue
        if real != (cur or 0):
            plan.append({"id": eid, "old": cur, "new": real})
            print(f"ep{eid} {cur} -> {real}")

    print(f"\n需校正 {len(plan)} 条 / 共 {len(rows)} 条，"
          f"跳过本地路径 {len(skipped)}，探测失败 {len(failed)}")

    if not args.apply:
        print("[dry-run] 未写库。加 --apply 才执行（先备份 news.db）。")
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"mode": "dry-run", "plan": plan, "skipped": skipped,
                       "failed": failed}, f, ensure_ascii=False, indent=2)
        print("[落盘]", OUT)
        return

    if not os.path.exists(DB + ".bak-t01925"):
        raise SystemExit("缺少备份 backend/data/news.db.bak-t01925，拒绝写库。")
    with con:
        con.executemany("UPDATE episode SET duration=? WHERE id=?",
                        [(r["new"], r["id"]) for r in plan])
    print(f"[已写库] {len(plan)} 条 duration 校正完成")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"mode": "apply", "plan": plan, "skipped": skipped,
                   "failed": failed}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
