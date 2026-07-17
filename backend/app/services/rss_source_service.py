"""RSS 源配置加载服务。

统一 rss.yaml 的加载逻辑，供 admin 路由（频道配置/AI 推荐）与 crawler workflow 复用，
避免两处路径拼接与字段解析逻辑重复导致后续维护漂移。

设计要点：
- 同步文件 IO：rss.yaml 仅在 admin 操作或爬虫启动时加载，调用频率极低，无需异步化
- 路径解析走 app.paths 模块，保证 PyInstaller 打包态/开发态一致
- 缓存策略：调用方按需自行缓存（crawler 启动加载一次，admin 接口按需调用），
  本服务保持无状态，避免缓存失效时机复杂化
"""
import logging
from pathlib import Path
from typing import Any

import yaml

from app.paths import resolve_rss_sources_path

logger = logging.getLogger(__name__)


def load_rss_sources() -> list[dict[str, Any]]:
    """加载 rss.yaml 中所有可用 RSS 源。

    Returns:
        源配置列表，每个源为 dict，包含 name/category_hint/authority 等字段。
        rss.yaml 不存在或为空时返回空列表，调用方需自行处理空场景。

    Raises:
        yaml.YAMLError: rss.yaml 语法错误时抛出，调用方按需捕获转 500/警告
    """
    rss_path = resolve_rss_sources_path()
    if not rss_path.exists():
        logger.warning("rss.yaml 不存在: %s", rss_path)
        return []

    with open(rss_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    sources = config.get("sources", [])
    if not isinstance(sources, list):
        logger.warning("rss.yaml sources 字段非列表，按空列表处理")
        return []

    return sources


def load_rss_sources_summary() -> list[dict[str, Any]]:
    """加载 RSS 源的精简摘要（仅 name/category_hint/authority）。

    供前端下拉选择与 LLM 推荐使用，避免 url/qps 等内部字段泄漏到前端或干扰 LLM。
    """
    sources = load_rss_sources()
    return [
        {
            "name": s.get("name", ""),
            "category_hint": s.get("category_hint", ""),
            "authority": s.get("authority", 0.5),
        }
        for s in sources
    ]
