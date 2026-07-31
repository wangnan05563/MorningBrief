"""回填清洗历史 script 表中的 Markdown 残留。

背景：
- 51 份历史文稿中 25 份含 `**` Markdown 残留（共 47 处）
- 这些文稿在 _strip_markdown_residue 部署前生成，TTS 朗读会念出"星号星号"
- script.segments 字段 JSON 中的 content 同样受影响
- 需一次性回填清洗，避免影响历史音频重生成或用户收听

策略：
- 直接复用 rewriter._strip_markdown_residue 函数（确保规则一致）
- 同时清洗 full_text 和 segments[*].content
- 先 dry-run 统计影响范围，再实际执行
- 不清洗已生成音频的文稿（避免与已合成音频不一致）：
  实际上重生成音频也会读清洗后文本，无负作用，因此全部清洗

使用：
  python backfill_strip_markdown.py --dry-run    # 仅预览
  python backfill_strip_markdown.py              # 实际执行
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

# 添加 backend 目录到 sys.path 以便导入 rewriter
sys.path.insert(0, str(Path(__file__).parent))

# 延迟导入：rewriter 模块加载时会初始化敏感词自动机，需要 data 目录存在
from app.workflow.llm.rewriter import _strip_markdown_residue


def clean_segments(segments_json: str) -> tuple[str, int]:
    """清洗 segments JSON 中每个 seg 的 content 字段。

    Returns:
        (清洗后的 JSON 字符串, 清洗掉的 ** 总数)
    """
    segs = json.loads(segments_json)
    removed_count = 0
    for seg in segs:
        if isinstance(seg, dict) and isinstance(seg.get("content"), str):
            original = seg["content"]
            cleaned = _strip_markdown_residue(original)
            if cleaned != original:
                removed_count += original.count("**") - cleaned.count("**")
                seg["content"] = cleaned
    return json.dumps(segs, ensure_ascii=False), removed_count


def main():
    parser = argparse.ArgumentParser(description="回填清洗历史 script 表 Markdown 残留")
    parser.add_argument("--dry-run", action="store_true", help="仅预览影响范围，不执行更新")
    parser.add_argument("--db", default="data/news.db", help="SQLite 数据库路径")
    args = parser.parse_args()

    db_path = Path(__file__).parent / args.db
    if not db_path.exists():
        print(f"[ERROR] 数据库不存在: {db_path}")
        sys.exit(1)

    print(f"数据库: {db_path}")
    print(f"模式: {'dry-run（仅预览）' if args.dry_run else '实际执行'}")
    print("=" * 60)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 查询所有受影响的 script
    rows = cur.execute(
        "SELECT id, workflow_id, full_text, segments FROM script ORDER BY id"
    ).fetchall()

    affected = []
    total_full_text_md = 0
    total_segments_md = 0

    for r in rows:
        full_text = r["full_text"] or ""
        segments = r["segments"] or "[]"

        ft_md_before = full_text.count("**")
        cleaned_ft = _strip_markdown_residue(full_text)
        ft_md_after = cleaned_ft.count("**")
        ft_removed = ft_md_before - ft_md_after

        cleaned_seg_json, seg_removed = clean_segments(segments)

        if ft_removed > 0 or seg_removed > 0:
            affected.append({
                "id": r["id"],
                "workflow_id": r["workflow_id"],
                "full_text_before": full_text,
                "full_text_after": cleaned_ft,
                "ft_removed": ft_removed,
                "segments_after": cleaned_seg_json,
                "seg_removed": seg_removed,
            })
            total_full_text_md += ft_removed
            total_segments_md += seg_removed

    print(f"受影响 script 数: {len(affected)} / 总计 {len(rows)}")
    print(f"full_text 清洗 ** 总数: {total_full_text_md}")
    print(f"segments  清洗 ** 总数: {total_segments_md}")
    print(f"合计清洗 ** 总数: {total_full_text_md + total_segments_md}")
    print()

    if not affected:
        print("[OK] 无需清洗，所有文稿均已干净")
        conn.close()
        return

    # 展示前 5 个受影响样本
    print("===== 受影响样本（前 5 个）=====")
    for a in affected[:5]:
        print(f"  script_id={a['id']:<4} wf={a['workflow_id']:<20} "
              f"full_text 清洗 {a['ft_removed']} 处 / segments 清洗 {a['seg_removed']} 处")

    if args.dry_run:
        print("\n[dry-run] 未实际更新数据库。去掉 --dry-run 参数以执行清洗。")
        conn.close()
        return

    # 实际执行更新
    print("\n===== 开始执行回填清洗 =====")
    updated = 0
    for a in affected:
        cur.execute(
            "UPDATE script SET full_text=?, segments=? WHERE id=?",
            (a["full_text_after"], a["segments_after"], a["id"]),
        )
        updated += 1
        print(f"  [OK] script_id={a['id']:<4} 已更新")

    conn.commit()
    conn.close()
    print(f"\n[完成] 共清洗 {updated} 份文稿，"
          f"移除 {total_full_text_md + total_segments_md} 处 ** 残留")


if __name__ == "__main__":
    main()
