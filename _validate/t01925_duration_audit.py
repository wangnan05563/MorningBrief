"""T01925 全量时长偏差盘点：库里的 episode.duration vs 成品实际时长。

只读取证：对自有 COS 公开成品地址走 ffprobe 直连 https（Range 语义已在 T01922 验过，
单次 ~0.9s，不整段下载），不写库、不改任何配置。

用法：backend/.venv/Scripts/python.exe _validate/t01925_duration_audit.py
"""
import json
import os
import sqlite3
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = os.path.join(ROOT, "backend", "data", "news.db")
FFPROBE = os.path.join(ROOT, "backend", "ffmpeg", "bin", "ffprobe.exe")
OUT = os.path.join(HERE, "t01925_duration_audit.json")


def probe(url):
    p = urllib.parse.urlsplit(url)
    u = urllib.parse.urlunsplit((p.scheme, p.netloc, urllib.parse.quote(p.path), "", ""))
    r = subprocess.run(
        [FFPROBE, "-v", "quiet", "-show_entries", "format=duration,size,bit_rate",
         "-of", "json", u], capture_output=True, text=True, errors="replace", timeout=60)
    try:
        f = (json.loads(r.stdout or "{}").get("format")) or {}
    except Exception:
        return None
    if not f.get("duration"):
        return None
    return {
        "duration": round(float(f["duration"]), 3),
        "size": int(f.get("size") or 0),
        "bit_rate": int(f.get("bit_rate") or 0),
    }


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT id, duration, audio_url, created_at, published_at, channel_id, date, "
        "workflow_id, hls_url FROM episode "
        "WHERE audio_url IS NOT NULL AND audio_url != '' ORDER BY id"
    ).fetchall()
    con.close()

    recs = []
    for eid, db_dur, url, created, published, chid, date, wfid, hls in rows:
        rec = {"id": eid, "db_duration": db_dur, "created_at": created,
               "published_at": published, "channel_id": chid, "date": date,
               "workflow_id": wfid, "has_hls": bool(hls),
               "url_kind": url.split("://", 1)[0] if "://" in url else "local"}
        if rec["url_kind"] == "local":
            rec["status"] = "skipped_local_path"
            recs.append(rec)
            continue
        try:
            p = probe(url)
        except Exception as e:
            rec["status"] = f"probe_failed:{type(e).__name__}"
            recs.append(rec)
            continue
        if not p:
            rec["status"] = "probe_empty"
            recs.append(rec)
            continue
        rec.update(p)
        rec["delta_sec"] = round(p["duration"] - (db_dur or 0), 2)
        rec["delta_pct"] = round((p["duration"] - (db_dur or 0)) / max(1.0, p["duration"]) * 100, 2)
        rec["status"] = "ok"
        recs.append(rec)
        print(f'ep{eid} db={db_dur} real={p["duration"]} delta={rec["delta_sec"]} '
              f'{p["bit_rate"]//1000}kbps')

    ok = [r for r in recs if r["status"] == "ok"]
    deltas = sorted(r["delta_sec"] for r in ok)
    summary = {
        "total_rows": len(recs),
        "probed": len(ok),
        "skipped": [r["id"] for r in recs if r["status"] != "ok"],
        "delta_min": deltas[0] if deltas else None,
        "delta_median": deltas[len(deltas) // 2] if deltas else None,
        "delta_max": deltas[-1] if deltas else None,
        "delta_p25": deltas[len(deltas) // 4] if deltas else None,
        "delta_p75": deltas[len(deltas) * 3 // 4] if deltas else None,
        "count_zeroish": sum(1 for d in deltas if abs(d) <= 1.0),
        "count_negative": sum(1 for d in deltas if d < 0),
        "count_positive": sum(1 for d in deltas if d > 0),
        "bitrates": sorted({r["bit_rate"] // 1000 for r in ok}),
        "by_created_batch": {},
    }
    for r in ok:
        batch = (r["created_at"] or "")[:10]
        g = summary["by_created_batch"].setdefault(batch, {"n": 0, "sum": 0.0, "min": 1e9, "max": -1e9})
        g["n"] += 1
        g["sum"] += r["delta_sec"]
        g["min"] = min(g["min"], r["delta_sec"])
        g["max"] = max(g["max"], r["delta_sec"])
    for b, g in summary["by_created_batch"].items():
        g["avg"] = round(g["sum"] / g["n"], 2)
        del g["sum"]

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": recs}, f, ensure_ascii=False, indent=2)
    print("[落盘]", OUT)
    print("[汇总]", json.dumps(summary, ensure_ascii=False)[:800])


if __name__ == "__main__":
    main()
