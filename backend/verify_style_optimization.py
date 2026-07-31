"""次日 cron 验证脚本：检查各频道新工作流的风格优化效果。

使用方式：
  python verify_style_optimization.py                 # 默认查今天
  python verify_style_optimization.py --date 2026-07-28  # 指定日期

检查项：
1. 各频道最新成功文稿的段首提问占比（部署后应 ≥ 30%）
2. 高频口语化词出现次数（"老铁""大佬""神作""真香"应为 0）
3. Markdown 残留（应为 0）
4. 过渡词轮换情况（同一篇文稿内无重复）
"""
import argparse
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "news.db"
HIGH_FREQ_WORDS = ["老铁", "大佬", "神作", "真香"]


def analyze_channel(cur, ch_id: int, ch_name: str, target_date: str) -> dict:
    """分析指定频道在目标日期的最新文稿。"""
    row = cur.execute(
        "SELECT s.id, s.full_text, s.workflow_id, w.finished_at "
        "FROM script s JOIN workflow w ON s.workflow_id=w.id "
        "WHERE w.channel_id=? AND w.status='success' "
        "AND date(w.finished_at)=? "
        "ORDER BY s.id DESC LIMIT 1",
        (ch_id, target_date),
    ).fetchone()

    if not row:
        return {"ch_id": ch_id, "ch_name": ch_name, "found": False}

    full = row["full_text"] or ""
    paragraphs = [p.strip() for p in full.split("\n\n") if p.strip()]
    body = paragraphs[1:11]  # 跳过 intro 段

    # 段首提问占比（前 50 字内有问号）
    intro_q = sum(1 for p in body if 0 < p.find("？") <= 50)
    intro_rate = intro_q / len(body) * 100 if body else 0

    # 高频词
    high_freq = {kw: full.count(kw) for kw in HIGH_FREQ_WORDS if full.count(kw) > 0}

    # Markdown 残留
    md_count = full.count("**")

    # 过渡词重复检测（段首 4 字）
    intro_4chars = [p[:4] for p in body if len(p) >= 4]
    duplicates = [c for c in set(intro_4chars) if intro_4chars.count(c) > 1]

    return {
        "ch_id": ch_id,
        "ch_name": ch_name,
        "found": True,
        "workflow_id": row["workflow_id"],
        "intro_q_count": intro_q,
        "intro_q_total": len(body),
        "intro_rate": intro_rate,
        "high_freq": high_freq,
        "md_count": md_count,
        "duplicate_intros": duplicates,
    }


def main():
    parser = argparse.ArgumentParser(description="检查各频道风格优化部署效果")
    parser.add_argument("--date", default=str(date.today()), help="目标日期 YYYY-MM-DD")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[ERROR] 数据库不存在: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    channels = [
        (1, "科技前沿"), (2, "财经观察"), (3, "体育速递"), (4, "娱乐焦点"),
        (5, "国际视野"), (6, "社会民生"), (7, "健康养生"),
        (8, "教育资讯"), (9, "游戏咨询"),
    ]

    print(f"===== 风格优化验证 日期={args.date} =====\n")
    print(f"{'ch':<4}{'频道':<12}{'wf_id':<22}{'段首提问':<12}{'高频词':<20}{'MD残留':<8}{'重复':<10}")
    print("-" * 90)

    pass_count = 0
    fail_count = 0
    for ch_id, ch_name in channels:
        r = analyze_channel(cur, ch_id, ch_name, args.date)
        if not r["found"]:
            print(f"{ch_id:<4}{ch_name:<12}{'-':<22}{'-':<12}{'-':<20}{'-':<8}{'-':<10}")
            continue

        # 判定是否通过：段首提问 ≥ 30% + 高频词为空 + MD=0 + 无重复
        high_freq_str = ",".join(f"{k}={v}" for k, v in r["high_freq"].items()) or "无"
        dup_str = ",".join(r["duplicate_intros"]) or "无"
        passed = (
            r["intro_rate"] >= 30
            and not r["high_freq"]
            and r["md_count"] == 0
            and not r["duplicate_intros"]
        )
        marker = "[OK]" if passed else "[!]"
        if passed:
            pass_count += 1
        else:
            fail_count += 1

        print(
            f"{ch_id:<4}{ch_name:<12}{r['workflow_id']:<22}"
            f"{r['intro_q_count']}/{r['intro_q_total']} ({r['intro_rate']:.0f}%){'':<4}"
            f"{high_freq_str:<20}{r['md_count']:<8}{dup_str:<10} {marker}"
        )

    print(f"\n通过 {pass_count} / 失败 {fail_count} / 未生成 {9 - pass_count - fail_count}")
    print("\n判定标准：段首提问 ≥ 30% + 高频词为空 + MD 残留 = 0 + 段首 4 字无重复")

    conn.close()


if __name__ == "__main__":
    main()
