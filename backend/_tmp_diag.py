"""查 wf-0005 的 script 数据，分析 LLM 达成率。"""
import sqlite3
import json
from pathlib import Path

DB = Path(__file__).parent / "data" / "news.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

for wf in ["wf-20260714-0003", "wf-20260714-0004", "wf-20260714-0005"]:
    cur.execute(
        "SELECT total_words, segments FROM script WHERE workflow_id=?",
        (wf,),
    )
    row = cur.fetchone()
    if not row:
        print(f"{wf}: 无 script")
        continue
    tw, segs = row
    seg_list = json.loads(segs) if segs else []
    actual = sum(len(s.get("content", "")) for s in seg_list)
    body_segs = [s for s in seg_list if s.get("title") not in ("开场白", "结尾")]
    body_actual = sum(len(s.get("content", "")) for s in body_segs)
    body_count = len(body_segs)
    avg_per_seg = body_actual // body_count if body_count else 0

    print(f"\n{wf}:")
    print(f"  total_words字段={tw} 实际字数={actual} 正文段数={body_count} 正文总字数={body_actual} 平均{avg_per_seg}/段")
    for i, s in enumerate(seg_list):
        print(f"    seg{i}: {s.get('title','')[:25]} chars={len(s.get('content',''))}")

# 查各 wf 的计算参数
print("\n===== 计算参数对比 =====")
print("wf-0003: WORDS_PER_MINUTE=210, target=900, rate=1.5")
print("  calc=4725, actual=3141, ratio=67%")
print("wf-0004: WORDS_PER_MINUTE=300, target=900, rate=1.5, prompt='至少'")
print("  calc=6750, actual=9125, ratio=135%")
print("wf-0005: WORDS_PER_MINUTE=300, target=900, rate=1.5, prompt='±10%'")
calc = 6750
print(f"  calc={calc}, actual=? ratio=?")

# 目标达成率分析
print("\n===== WORDS_PER_MINUTE 校准 =====")
actual_wpm = 454  # +50% 实测
base_wpm = 303  # +0% 实测
target = 900
rate = 1.5
low, high = int(target*0.85), int(target*1.15)

# 要让 LLM 80% 达成时刚好 900s
# actual_words = calc_words * 0.8
# actual_dur = actual_words / actual_wpm * 60 = 900
# actual_words = 900 * actual_wpm / 60 = 6810
# calc_words = 6810 / 0.8 = 8512
# WORDS_PER_MINUTE = calc_words * 60 / (target * rate) = 8512 * 60 / (900 * 1.5) = 378
for wpm in [300, 330, 350, 375]:
    calc = int(target * wpm * rate / 60)
    for ratio in [0.7, 0.8, 0.9, 1.0, 1.1]:
        actual_words = int(calc * ratio)
        dur = actual_words / actual_wpm * 60
        ok = "PASS" if low <= dur <= high else "FAIL"
        print(f"  WPM={wpm} calc={calc} ratio={ratio:.0%} words={actual_words} dur={dur:.0f}s [{ok}]")

conn.close()
