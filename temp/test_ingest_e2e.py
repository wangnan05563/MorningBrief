"""M1 T1/T2/T3 端到端验证（不依赖 create_all，使用真实 db 拷贝）。

验证点：
1. T1 document_ingest.parse_document：多章节解析 + 超长章节切块（>1200 字）。
2. T2 _persist_material 去重：
   - list 类型按 (source_type, dedup_key) 去重 → 重复 409；
   - rss 类型按 url 唯一 → 重复 409；两条路径互不干扰。
3. T3 上传端点逻辑：逐章入库 + 重复上传整体去重。
4. POST /upload 端点已注册到 materials router。
5. 不支持格式（.pdf）被正确拒绝（UnsupportedFormatError）。

注意：list 去重为「全局按内容哈希」，与频道无关（MVP 计划既定口径），因此
Phase A 与 Phase B 之间先清理，避免 Phase A 已入库内容被 Phase B 判重。
验证后清理测试数据并删除临时 db。
"""
import asyncio
import os
import shutil
import sqlite3
import sys
import tempfile

BACKEND_DIR = r"D:\code\otherProjects\20_News\backend"
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Material, MaterialSourceType
from app.core.exceptions import BizError
from app.services.document_ingest import parse_document, compute_content_hash
from app.routers.admin import materials as materials_router_mod

TEST_CHANNEL = 999999
TEST_RSS_URL = "http://e2e-test.local/feed/unique-12345"


def _ensure_dedup_column(copy_path: str) -> None:
    conn = sqlite3.connect(copy_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(material)")
        cols = {r[1] for r in cur.fetchall()}
        if "dedup_key" not in cols:
            cur.execute("ALTER TABLE material ADD COLUMN dedup_key VARCHAR(64)")
            conn.commit()
            print("[migrate] 为拷贝库追加 dedup_key 列")
        else:
            print("[migrate] 拷贝库已含 dedup_key 列（沿用真实库迁移结果）")
    finally:
        conn.close()


async def _cleanup(db: AsyncSession) -> None:
    res = await db.execute(select(Material).where(Material.channel_id == TEST_CHANNEL))
    for m in res.scalars().all():
        await db.delete(m)
    res = await db.execute(select(Material).where(Material.url == TEST_RSS_URL))
    for m in res.scalars().all():
        await db.delete(m)
    await db.commit()
    print("[cleanup] 已删除测试频道/测试 RSS 的素材")


async def _insert_list(db, channel_id, title, content):
    return await materials_router_mod._persist_material(
        db, channel_id=channel_id, source="文档上传", title=title, content=content,
        source_type=MaterialSourceType.list.value, dedup_key=compute_content_hash(content),
    )


async def main() -> None:
    real_db = r"D:\code\otherProjects\20_News\backend\data\news.db"
    tmp = tempfile.mkdtemp(prefix="mb_e2e_")
    copy_path = os.path.join(tmp, "news_test.db")
    shutil.copyfile(real_db, copy_path)
    print(f"[setup] 拷贝真实库到 {copy_path}")
    _ensure_dedup_column(copy_path)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{copy_path}", connect_args={"check_same_thread": False},
    )
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results = []
    def record(name, ok, detail=""):
        results.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" :: {detail}" if detail else ""))

    # 超长章节内容：300 次重复 > 1200 字，强制切块；
    # 第三章正文拉长到 >30 字，避免被 _MIN_MERGE_CHARS 合并进第二章，
    # 否则切块后章节数会被合并抵消，无法从计数上验证切块。
    md_content = (
        "# 第一章 绪论\n这是第一章的绪论内容，介绍专业领域的背景与意义。\n\n"
        "# 第二章 核心方法\n" + "方法论段落。" * 300 + "\n\n"
        "# 第三章 结论\n这是结论章节，总结全文要点并给出后续研究方向、"
        "实验验证方式与参考文献列表，供学习者进一步深入。\n"
    )

    async with SessionLocal() as db:
        try:
            # ---------- T1: 解析 ----------
            chapters = parse_document("test_course.md", md_content.encode("utf-8"))
            record("T1 解析多章节", len(chapters) >= 3, f"得到 {len(chapters)} 个章节")
            chunked = len(chapters) > 3 or any("（" in c.title for c in chapters)
            record("T1 超长章节切块", chunked,
                   f"切块后 {len(chapters)} 章，含子章标记={any('（' in c.title for c in chapters)}")

            unsupported_ok = False
            try:
                parse_document("doc.pdf", b"%PDF-1.4 fake")
            except Exception as e:
                unsupported_ok = type(e).__name__ == "UnsupportedFormatError"
            record("T1 不支持格式被拒绝", unsupported_ok)

            # ---------- Phase A: T2 去重逻辑 ----------
            m1 = await _insert_list(db, TEST_CHANNEL, chapters[0].title, chapters[0].content)
            record("T2 list 首次入库", m1.id is not None, f"id={m1.id}, url={m1.url}")

            list_dup = False
            try:
                await _insert_list(db, TEST_CHANNEL, chapters[0].title, chapters[0].content)
            except BizError as e:
                list_dup = (e.code == 409)
            record("T2 list 重复→409", list_dup)

            mr = await materials_router_mod._persist_material(
                db, channel_id=TEST_CHANNEL, source="rss", title="RSS条目",
                content="RSS正文", source_type=MaterialSourceType.rss.value, url=TEST_RSS_URL)
            record("T2 rss 入库(url唯一)", mr.id is not None, f"id={mr.id}")

            rss_dup = False
            try:
                await materials_router_mod._persist_material(
                    db, channel_id=TEST_CHANNEL, source="rss", title="RSS条目2",
                    content="另一正文", source_type=MaterialSourceType.rss.value, url=TEST_RSS_URL)
            except BizError as e:
                rss_dup = (e.code == 409)
            record("T2 rss 重复URL→409", rss_dup)

            # 清理 Phase A，避免与 Phase B 全局内容去重冲突
            await _cleanup(db)

            # ---------- Phase B: T3 上传端点逻辑 ----------
            first_ids = []
            for ch in chapters:
                m = await _insert_list(db, TEST_CHANNEL, ch.title, ch.content)
                first_ids.append(m.id)
            record("T3 逐章入库", len(first_ids) == len(chapters),
                   f"入库 {len(first_ids)}/{len(chapters)} 章")

            re_dups = 0
            for ch in chapters:
                try:
                    await _insert_list(db, TEST_CHANNEL, ch.title, ch.content)
                except BizError as e:
                    if e.code == 409:
                        re_dups += 1
            record("T3 重复上传全部去重", re_dups == len(chapters),
                   f"重复被拒 {re_dups}/{len(chapters)} 章")

            routes = {r.path for r in materials_router_mod.router.routes}
            record("T3 POST /upload 已注册", any(r.endswith("/upload") for r in routes),
                   f"routes={sorted(routes)}")

        finally:
            await _cleanup(db)

    await engine.dispose()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n==== 结果: {passed}/{total} 通过 ====")
    try:
        os.remove(copy_path)
        os.rmdir(tmp)
    except OSError:
        pass
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
