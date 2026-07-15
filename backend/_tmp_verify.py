"""验证 wf-0006 的最终数据。"""
import sqlite3
import json
from pathlib import Path

DB = Path(__file__).parent / "data" / "news.db"
WF = "wf-20260714-0006"

conn = sqlite3.connect(DB)
cur = conn.cursor()

# script
print(f"===== {WF} script =====")
cur.execute("SELECT total_words, estimated_duration, segments FROM script WHERE workflow_id=?", (WF,))
tw, est, segs = cur.fetchone()
seg_list = json.loads(segs) if segs else []
actual = sum(len(s.get("content", "")) for s in seg_list)
body_segs = [s for s in seg_list if s.get("title") not in ("开场白", "结尾")]
body_actual = sum(len(s.get("content", "")) for s in body_segs)

print(f"  total_words={tw} est_dur={est}s 段数={len(seg_list)} 正文={len(body_segs)}段")
print(f"  正文总字数={body_actual} 平均{body_actual//len(body_segs)}/段")
for i, s in enumerate(seg_list):
    print(f"    seg{i}: {s.get('title','')[:25]} chars={len(s.get('content',''))}")

# workflow_step stitch 结果
print(f"\n===== stitch step =====")
cur.execute("SELECT result, error FROM workflow_step WHERE workflow_id=? AND step_name='stitch'", (WF,))
row = cur.fetchone()
if row and row[0]:
    r = json.loads(row[0])
    print(f"  result: {json.dumps(r, ensure_ascii=False)[:500]}")

# 计算对比
print(f"\n===== 计算对比 =====")
WORDS_PER_MINUTE = 330
target = 900
rate = 1.5
calc = int(target * WORDS_PER_MINUTE * rate / 60)
actual_wpm_50 = 454  # +50% 实测
ratio = actual / calc if calc else 0
est_dur_actual = actual / actual_wpm_50 * 60
print(f"  WORDS_PER_MINUTE={WORDS_PER_MINUTE} target={target}s rate=+{int((rate-1)*100)}%")
print(f"  计算字数={calc} 实际字数={actual} 达成率={ratio:.0%}")
print(f"  按实测语速{actual_wpm_50}字/分 预计时长={est_dur_actual:.0f}s")
print(f"  目标范围 [{int(target*0.85)}, {int(target*1.15)}]")

conn.close()
