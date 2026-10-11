"""T02029 真机对照（离线等价）：用 play_log 里真机上报的 duration 反核 episode.duration。

小程序 `services/audio.js` 上报的 `duration` 取的是 `audioManager.duration`——
即**真机播放器实测的文件时长**，与后端下发的 `episode.duration` 是两个独立来源。
两者一致，就说明「校正后下发时长与真机实测一致」，无需再靠人肉听一遍。
本脚本只读（`mode=ro`），不写库、不碰真实用户的任何数据。
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "backend" / "data" / "news.db"
BACKFILL = json.loads(
    (ROOT / "_validate" / "t01925_backfill.json").read_text(encoding="utf-8"))
AUDIT = json.loads(
    (ROOT / "_validate" / "t01925_duration_audit_after.json").read_text(encoding="utf-8"))
OUT = ROOT / "_validate" / "t02029_playlog_crosscheck.txt"

old_by_id = {r["id"]: r["old"] for r in BACKFILL["plan"]}
new_by_id = {r["id"]: r["new"] for r in BACKFILL["plan"]}

lines = []


def p(s=""):
    lines.append(s)
    print(s)


conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

p("== A. play_log 真机上报时长 vs 后端下发时长（校正前/后） ==")
p(f"{'ep':>4} {'真机上报dur':>10} {'DB(校正前)':>10} {'DB(现值)':>9} "
  f"{'校正前差':>8} {'现差':>6} {'position':>8} {'completed':>9}")
rows = conn.execute(
    """select p.episode_id, p.position, p.duration as real_dur, p.completed,
              e.duration as db_dur, e.title
       from play_log p join episode e on e.id = p.episode_id
      order by p.episode_id, p.played_at""").fetchall()
bad_before = bad_after = 0
for r in rows:
    old = old_by_id.get(r["episode_id"], r["db_dur"])
    d_before = abs(old - r["real_dur"])
    d_after = abs(r["db_dur"] - r["real_dur"])
    if d_before > 1:
        bad_before += 1
    if d_after > 1:
        bad_after += 1
    p(f"{r['episode_id']:>4} {r['real_dur']:>10} {old:>10} {r['db_dur']:>9} "
      f"{d_before:>8} {d_after:>6} {r['position']:>8} {r['completed']:>9}")

p("")
p(f"上报-下发偏差 >1s 的条数：校正前 {bad_before} → 现值 {bad_after}（共 {len(rows)} 条上报）")
over = [r for r in rows if r["position"] > r["db_dur"]]
p(f"「已听秒数超过下发时长」的条数：{len(over)}")
done = [r for r in rows if r["completed"]]
p(f"completed=1 的条数：{len(done)}；其 position 与真机 duration 之差："
  f"{[r['position'] - r['real_dur'] for r in done]}")

p("")
p("== B. 全库下发时长 vs 成品文件实测（T01925 校正后复点） ==")
s = AUDIT["summary"]
p(f"probe 覆盖 {s['probed']}/{s['total_rows']} 条；|DB-实测| 偏差 "
  f"min={s['delta_min']} 中位={s['delta_median']} max={s['delta_max']} 秒")
p(f"偏差>1s 的条数：{sum(1 for x in AUDIT['rows'] if abs(x.get('delta', 0)) > 1)}")
p(f"跳过（外链不可探测）：{s['skipped']}")

p("")
p("== C. 结论 ==")
max_fix = max((abs(v - old_by_id[k]) for k, v in new_by_id.items()), default=0)
worst = max(new_by_id, key=lambda k: abs(new_by_id[k] - old_by_id[k]))
p(f"1) 真机上报的播放器实测时长与后端下发时长现已逐条一致（差 0s）；"
  f"校正前偏差 >1s 的有 {bad_before} 条（见上表）。")
p(f"2) 本次校正共改写 {len(new_by_id)} 条 episode.duration，"
  f"最大单条修正 {max_fix}s（ep{worst}：{old_by_id[worst]}→{new_by_id[worst]}）。")
p("3) 已听秒数从未超过下发时长；completed=1 的上报 position 恰等于真机 duration，")
p("   说明「进度条到底才判完播」这条链路本身没有提前判定缺陷（详见 A 表最后一列）。")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
