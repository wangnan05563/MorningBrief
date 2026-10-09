"""找书工具的书源索引服务（T00612：修复全量搜索超时）。

问题（T00612 实测）：书源仓库有 **1000 个分类 md**（单文件 150–250KB，全量 ≳200MB），
「不选分类直接搜索」需逐文件下载解析，必然超过前端 15s 超时（`timeout of 15000ms exceeded`）。

解法：**一次构建本地索引，之后毫秒级检索**。
- `build_index()`：并发（线程池）拉取全部分类 md → 复用 `ebook_source_service.parse_category`
  解析 → 原子写入 `data/ebook_index.json`（含 built_at / 分类数 / 书目数 / 书目数组）；
- `search_index()`：纯本地过滤（书名 / 作者，大小写不敏感），毫秒级返回；
- 构建由路由层后台触发（BackgroundTasks），前端轮询 `/ebooks/index/status` 看进度；
- **快路径保留**：选中具体分类时无需索引——直接抓那一个分类文件（秒级），索引未就绪也能用。

索引文件与素材无关，可随时删除重建（json 便于排查，无需 DB 迁移）。
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.paths import resolve_data_dir
from app.services import ebook_source_service as src_svc

INDEX_FILENAME = "ebook_index.json"
_BUILD_WORKERS = 10  # 并发拉取分类 md：兼顾速度与 raw.githubusercontent 限流

# 构建进度状态（进程内；单实例部署，无需共享）
_STATE_LOCK = threading.Lock()
_BUILD_STATE: dict = {
    "running": False,
    "done": 0,
    "total": 0,
    "failed": 0,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def index_path() -> Path:
    return resolve_data_dir() / INDEX_FILENAME


def _set_state(**kwargs) -> None:
    with _STATE_LOCK:
        _BUILD_STATE.update(kwargs)


def build_state() -> dict:
    with _STATE_LOCK:
        return dict(_BUILD_STATE)


def _load_one(category: str) -> list[dict]:
    """抓取并解析单个分类。

    **必须吞掉异常并返回空列表**：`ThreadPoolExecutor.map` 会把异常在迭代结果时抛出，
    单个分类抓取失败就会中断整个索引构建（实测踩坑）。失败由调用方按空结果计入 failed。
    """
    try:
        text = src_svc._fetch(f"md/{category}.md")
        books = src_svc.parse_category(text)
    except Exception as e:
        logger.warning("[ebook_index] 分类 {} 抓取失败，跳过: {}", category, e)
        return []
    for b in books:
        b["category"] = category
    return books


def build_index(max_workers: int = _BUILD_WORKERS, fetch_categories: list[str] | None = None) -> dict:
    """构建书源索引并落盘。返回索引摘要（含 books）。

    Args:
        max_workers: 并发抓取数
        fetch_categories: 仅构建指定分类（单测/增量场景）；None = 全部分类
    """
    started = time.time()
    _set_state(running=True, done=0, total=0, failed=0,
               started_at=datetime.now(timezone.utc).isoformat(),
               finished_at=None, error=None)

    categories = fetch_categories or src_svc.list_categories()
    total = len(categories)
    _set_state(total=total)
    logger.info("[ebook_index] 开始构建索引：{} 个分类（并发 {}）", total, max_workers)

    books: list[dict] = []
    failed = 0
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for result in pool.map(_load_one, categories):
            done += 1
            if result:
                books.extend(result)
            else:
                failed += 1
            # 每 20 个分类更新一次进度，避免频繁加锁
            if done % 20 == 0 or done == total:
                _set_state(done=done, failed=failed)

    index = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": round(time.time() - started, 1),
        "category_count": total - failed,
        "failed_category_count": failed,
        "book_count": len(books),
        "books": books,
    }

    path = index_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)  # 原子写：避免构建中断留下半截索引

    _set_state(running=False, done=done,
               finished_at=index["built_at"], error=None)
    logger.info(
        "[ebook_index] 索引构建完成：{} 本书 / {} 分类（失败 {}），耗时 {}s → {}",
        len(books), index["category_count"], failed, index["elapsed_sec"], path,
    )
    return index


def load_index() -> dict | None:
    """读取索引（不存在或损坏返回 None，调用方据此提示重建）。"""
    path = index_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("[ebook_index] 索引文件损坏，需重建: {}", e)
        return None


def _age_days(built_at: str | None) -> float | None:
    """索引构建时间距今天数（解析失败返回 None）。"""
    if not built_at:
        return None
    try:
        dt = datetime.fromisoformat(str(built_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        return None


def index_status() -> dict:
    """索引就绪状态（供前端展示与轮询）。

    T00619：新增年龄与过期标记——索引是一次性快照，书源后续新增的书不会自动进入，
    过期后搜索结果会"查不到新书"且此前无任何提示。
    """
    idx = load_index()
    age = _age_days((idx or {}).get("built_at"))
    return {
        "ready": bool(idx),
        "built_at": (idx or {}).get("built_at"),
        "book_count": (idx or {}).get("book_count", 0),
        "category_count": (idx or {}).get("category_count", 0),
        "elapsed_sec": (idx or {}).get("elapsed_sec"),
        "file": str(index_path()),
        # T00619：年龄 / 过期（阈值可用环境变量覆盖，便于不同环境调参）
        "age_days": round(age, 1) if age is not None else None,
        "stale": bool(idx) and age is not None and age > index_stale_days(),
        "stale_days": index_stale_days(),
        "build": build_state(),
    }


def index_stale_days() -> float:
    """过期阈值（天）：默认 14，环境变量 EBOOK_INDEX_STALE_DAYS 覆盖。"""
    try:
        return float(os.getenv("EBOOK_INDEX_STALE_DAYS") or 14)
    except ValueError:
        return 14.0


def maybe_auto_rebuild() -> dict:
    """T00619：索引缺失或过期时自动触发一次后台重建（自愈；构建中不重复触发）。

    为什么自动而非只提醒：过期索引会让用户"静默查不到新书"——提醒容易被忽略，
    重建成本（约 165s / 200MB）可接受且已有并发与原子写保护；仍保留前端手动重建入口。

    Returns:
        {"triggered": bool, "reason": "missing" | "stale" | "fresh" | "building"}
    """
    st = index_status()
    if (st.get("build") or {}).get("running"):
        return {"triggered": False, "reason": "building"}
    if not st.get("ready"):
        reason = "missing"
    elif st.get("stale"):
        reason = "stale"
    else:
        return {"triggered": False, "reason": "fresh"}
    logger.info("[ebook_index] 索引{}（age={} 天），自动触发后台重建", reason, st.get("age_days"))
    start_build_async()
    return {"triggered": True, "reason": reason}


def search_index(keyword: str, category: str | None = None, limit: int = 20) -> dict:
    """本地索引检索（毫秒级）。返回结构与 ebook_source_service.search 对齐。"""
    kw = (keyword or "").strip().lower()
    idx = load_index()
    if not idx:
        return {"keyword": keyword, "scanned_categories": [], "failed_categories": [],
                "hits": [], "index_ready": False}
    hits = []
    for b in idx.get("books", []):
        if category and b.get("category") != category:
            continue
        if kw in (b.get("title") or "").lower() or kw in (b.get("author") or "").lower():
            hits.append(b)
            if len(hits) >= max(1, limit):
                break
    return {
        "keyword": keyword,
        "scanned_categories": [f"index({idx.get('category_count', 0)} 分类)"],
        "failed_categories": [],
        "hits": hits,
        "index_ready": True,
        "index_built_at": idx.get("built_at"),
    }


def random_books(limit: int = 10) -> dict:
    """从本地索引无重复随机抽取 limit 本书（T00810：找书工具「随机」按钮）。

    为什么放后端：索引文件是全量书目（≳200MB 抓取产物），不可能拉到前端再抽样；
    后端随机只读本地 json，毫秒级。与 search_index 返回结构对齐，前端结果表可直接复用。

    无重复：`random.sample` 保证单次抽取内不重复；书名总数不足 limit 时返回全部
    （约束要求：不足 10 本返回全部可用书名）。
    """
    idx = load_index()
    if not idx:
        return {"scanned_categories": [], "failed_categories": [],
                "hits": [], "index_ready": False}
    books = idx.get("books", [])
    picked = random.sample(books, min(max(1, limit), len(books))) if books else []
    return {
        "scanned_categories": [f"index({idx.get('category_count', 0)} 分类)"],
        "failed_categories": [],
        "hits": picked,
        "index_ready": True,
        "index_built_at": idx.get("built_at"),
    }


def start_build_async() -> dict:
    """后台线程触发构建（已在运行则不重复启动）。返回当前构建状态。"""
    st = build_state()
    if st.get("running"):
        return st
    _set_state(running=True, done=0, total=0, failed=0, error=None,
               started_at=datetime.now(timezone.utc).isoformat(), finished_at=None)

    def _run():
        try:
            build_index()
        except Exception as e:  # 构建失败要把状态复位，否则永远显示"构建中"
            logger.error("[ebook_index] 索引构建失败: {}", e)
            _set_state(running=False, error=str(e)[:300],
                       finished_at=datetime.now(timezone.utc).isoformat())

    threading.Thread(target=_run, name="ebook-index-build", daemon=True).start()
    return build_state()
