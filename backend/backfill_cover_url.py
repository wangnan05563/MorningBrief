"""批量回填脚本：为已有 material 记录补 cover_url。

复用 article_parser.extract 提取封面图，并发控制避免被站点限流。
幂等：仅更新 cover_url IS NULL 的记录，已存在的跳过。
后处理：同一 cover_url 出现超过 3 次视为默认封面，置为 NULL。

用法：
    python -u backfill_cover_url.py [--limit N] [--concurrency 3] [--dedup-threshold 3]
"""
import argparse
import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

# 独立运行：把 backend 目录加入 sys.path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.workflow.crawler.article_parser import extract

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill")


async def backfill_one(url: str, sem: asyncio.Semaphore) -> str | None:
    """单条回填：信号量限流，提取失败返回 None。"""
    async with sem:
        try:
            result = await extract(url)
            return result.get("cover_url")
        except Exception as e:
            logger.warning("提取失败 url=%s err=%s", url, e)
            return None


def dedup_default_covers(conn, threshold: int) -> int:
    """重复图后处理：同一 cover_url 出现超过 threshold 次视为默认封面，置 NULL。

    依据：真实文章封面图通常唯一，同 URL 在多篇文章出现说明是站点默认封面
    （如 17173cdn 的 nKoygkbtzwsopvl.jpg 在 8 篇文章中重复）。
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT cover_url, COUNT(*) FROM material "
        "WHERE cover_url IS NOT NULL "
        "GROUP BY cover_url HAVING COUNT(*) > ?",
        (threshold,),
    )
    dup_urls = [r[0] for r in cur.fetchall()]
    if not dup_urls:
        return 0
    # 逐个置 NULL 并记录日志
    cleaned = 0
    for url in dup_urls:
        cur.execute(
            "UPDATE material SET cover_url = NULL WHERE cover_url = ?",
            (url,),
        )
        cleaned += cur.rowcount
        logger.info("清理默认封面图（重复>%d次）: %s 影响%d条", threshold, url[:70], cur.rowcount)
    conn.commit()
    return cleaned


async def main(limit: int | None, concurrency: int, dedup_threshold: int) -> None:
    db_path = Path(__file__).parent / "data" / "news.db"
    if not db_path.exists():
        logger.error("数据库不存在: %s", db_path)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # 仅回填 cover_url IS NULL 的记录
    query = "SELECT id, url FROM material WHERE cover_url IS NULL ORDER BY id"
    if limit:
        query += f" LIMIT {limit}"
    cur.execute(query)
    rows = cur.fetchall()
    logger.info("待回填素材: %d 条（并发 %d）", len(rows), concurrency)

    if not rows:
        logger.info("无待回填素材，跳过提取")
    else:
        sem = asyncio.Semaphore(concurrency)
        success = 0
        failed = 0

        # 并发提取所有 URL 的封面图
        tasks = [backfill_one(url, sem) for _, url in rows]
        results = await asyncio.gather(*tasks)

        # 批量更新数据库
        for (mid, url), cover_url in zip(rows, results):
            if cover_url:
                cur.execute(
                    "UPDATE material SET cover_url = ? WHERE id = ?",
                    (cover_url, mid),
                )
                success += 1
                logger.info("✓ id=%d %s", mid, cover_url[:80])
            else:
                failed += 1
                logger.info("✗ id=%d 无封面图 url=%s", mid, url[:60])

        conn.commit()
        logger.info("提取完成：成功 %d，失败 %d", success, failed)

    # 重复图后处理
    if dedup_threshold > 0:
        cleaned = dedup_default_covers(conn, dedup_threshold)
        if cleaned:
            logger.info("清理默认封面图 %d 条", cleaned)

    # 最终统计
    cur.execute("SELECT COUNT(*) FROM material WHERE cover_url IS NOT NULL")
    final = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM material")
    total = cur.fetchone()[0]
    conn.close()
    logger.info("最终：%d/%d 条有封面图", final, total)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量回填 material.cover_url")
    parser.add_argument("--limit", type=int, default=None, help="限制回填条数")
    parser.add_argument(
        "--concurrency", type=int, default=3,
        help="并发数（避免站点限流，默认 3）",
    )
    parser.add_argument(
        "--dedup-threshold", type=int, default=3,
        help="重复图清理阈值（同 URL 出现超过 N 次视为默认封面，0=不清理）",
    )
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.concurrency, args.dedup_threshold))
