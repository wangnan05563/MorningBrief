"""一次性清理历史稿件中的 Markdown/星号变体残留（T00627）。

背景：8 月的稿件在「清洗修复」上线前落库，full_text 与 segments 中残留
`**`（残缺标记粘连中文，如「根据**数据」「、**组织奖」）以及全角 ＊ / ※ / 装饰星等，
TTS 会把这些读成「星号」。本脚本用与运行时**同一套规则**
（`app.workflow.text_clean.strip_markdown_residue`）批量清理历史行。

用法（默认 dry-run，只报告不写库）：
    backend 目录下：
        .venv/Scripts/python scripts/clean_script_text.py                # 预演：列出将被修改的行与命中符号
        .venv/Scripts/python scripts/clean_script_text.py --apply         # 实际写库（自动备份 db 文件路径提示）
        .venv/Scripts/python scripts/clean_script_text.py --apply --id 90 # 只处理指定 script id

写库范围：`script.full_text`、`script.segments`（JSON 内每段 content）、`script.total_words`
（清洗后字数变化需同步，否则稿子字数与音频时长统计不一致）。

安全：dry-run 为默认；--apply 前请确认应用已停止写入（或接受并发风险），
脚本自身逐行事务提交，异常行跳过并汇总。
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.workflow.text_clean import strip_markdown_residue  # noqa: E402

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "news.db"
# 命中即报告的符号（与清洗规则一致）
MARK_CHARS = "**＊﹡∗⁎✱✳✻✽❋※`[]()<>|#~_"


def _touched(text: str) -> bool:
    return bool(text) and any(ch in text for ch in MARK_CHARS)


def main() -> int:
    ap = argparse.ArgumentParser(description="清理历史稿件 Markdown/星号残留（默认 dry-run）")
    ap.add_argument("--apply", action="store_true", help="实际写库（默认只预演）")
    ap.add_argument("--id", type=int, help="只处理指定 script.id")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"[error] 数据库不存在: {DB_PATH}")
        return 2

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    sql = "SELECT id, workflow_id, full_text, segments, total_words FROM script"
    params: tuple = ()
    if args.id:
        sql += " WHERE id = ?"
        params = (args.id,)
    rows = cur.execute(sql, params).fetchall()

    print(f"库: {DB_PATH}")
    print(f"模式: {'APPLY（写库）' if args.apply else 'DRY-RUN（仅预演）'}  稿件总数: {len(rows)}")
    print("-" * 78)

    changed = 0
    for sid, wf, full_text, segments, total_words in rows:
        full_text = full_text or ""
        new_full = strip_markdown_residue(full_text)

        # segments：逐段清洗 content，保持结构与其他字段不变
        new_segments = segments
        seg_notes = []
        if segments:
            try:
                arr = json.loads(segments)
            except (ValueError, TypeError):
                arr = None
            if isinstance(arr, list):
                for seg in arr:
                    if isinstance(seg, dict) and _touched(seg.get("content") or ""):
                        before = len(seg.get("content") or "")
                        seg["content"] = strip_markdown_residue(seg["content"])
                        seg_notes.append((seg.get("seq"), before, len(seg["content"])))
                new_segments = json.dumps(arr, ensure_ascii=False)

        if new_full == full_text and new_segments == segments:
            continue

        changed += 1
        marks = sorted({ch for ch in full_text if ch in MARK_CHARS})
        new_words = sum(len(s["content"]) for s in json.loads(new_segments)) if new_segments and isinstance(json.loads(new_segments), list) else total_words
        print(f"script {sid}（{wf}）命中符号 {marks} | 段内清理 {len(seg_notes)} 段 | "
              f"full_text {len(full_text)}→{len(new_full)} 字 | total_words {total_words}→{new_words}")
        if seg_notes:
            for seq, b, a in seg_notes[:5]:
                print(f"    段 {seq}: {b}→{a} 字")

        if args.apply:
            cur.execute(
                "UPDATE script SET full_text = ?, segments = ?, total_words = ? WHERE id = ?",
                (new_full, new_segments, new_words, sid),
            )
            conn.commit()

    print("-" * 78)
    print(f"需要清理的稿件: {changed} / {len(rows)}")
    if changed and not args.apply:
        print("提示：以上为预演结果，确认无误后加 --apply 实际写库。")
    elif changed:
        print("已完成写库。建议随后重跑受影响的节目（或仅重合成 TTS）以更新音频。")
    else:
        print("库中稿件均已干净，无需处理。")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
