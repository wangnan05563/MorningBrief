"""回填 script.segments 中的 cover_url 字段。

已有 script.segments 是之前生成的，material_ids 对应的 material 现在已有 cover_url，
但 segments JSON 中没有 cover_url 字段。本脚本从 material 表反查 cover_url 补到 segments。

幂等：segment 已有 cover_url 字段则跳过该 segment（除非 --force）。
"""
import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_seg")


def backfill_script_segments(conn, force: bool) -> None:
    """遍历所有 script，给 segments 补 cover_url。"""
    cur = conn.cursor()

    # 预加载所有 material 的 cover_url，避免逐 segment 查询
    cur.execute("SELECT id, cover_url FROM material WHERE cover_url IS NOT NULL")
    cover_map = {r[0]: r[1] for r in cur.fetchall()}
    logger.info("有 cover_url 的 material: %d 条", len(cover_map))

    cur.execute("SELECT id, segments FROM script")
    scripts = cur.fetchall()
    logger.info("待处理 script: %d 个", len(scripts))

    updated_scripts = 0
    updated_segments = 0

    for sid, segments_json in scripts:
        if not segments_json:
            continue
        try:
            segments = json.loads(segments_json) if isinstance(segments_json, str) else segments_json
        except json.JSONDecodeError:
            logger.warning("script %d segments JSON 解析失败，跳过", sid)
            continue

        modified = False
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            # 已有 cover_url 且非 force 模式则跳过
            if seg.get("cover_url") and not force:
                continue
            material_ids = seg.get("material_ids") or []
            # 取第一个有 cover_url 的 material 作为该段封面
            for mid in material_ids:
                cover = cover_map.get(mid)
                if cover:
                    seg["cover_url"] = cover
                    modified = True
                    updated_segments += 1
                    break
            else:
                # 该段所有 material 都没 cover_url，置空保证字段一致
                if force:
                    seg["cover_url"] = seg.get("cover_url") or None

        if modified:
            cur.execute(
                "UPDATE script SET segments = ? WHERE id = ?",
                (json.dumps(segments, ensure_ascii=False), sid),
            )
            updated_scripts += 1
            logger.info("✓ script %d 更新了 %d 个 segment", sid, sum(1 for s in segments if isinstance(s, dict) and s.get("cover_url")))

    conn.commit()
    logger.info("完成：更新 %d 个 script，%d 个 segment", updated_scripts, updated_segments)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="回填 script.segments.cover_url")
    parser.add_argument(
        "--force", action="store_true",
        help="强制重写所有 segment 的 cover_url（即使已存在）",
    )
    args = parser.parse_args()

    db_path = Path(__file__).parent / "data" / "news.db"
    if not db_path.exists():
        logger.error("数据库不存在: %s", db_path)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    try:
        backfill_script_segments(conn, args.force)
    finally:
        conn.close()
