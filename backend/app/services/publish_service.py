"""节目发布服务：将 episode 发布到 COS 对象供 C 端读取（参考详细设计说明书 5.7 节）。

设计要点：
1. C 端（小程序/云函数）直接读 COS 对象，避免每次回源 B 端数据库
2. 三类 COS 对象：
   - episodes/detail/{episode_id}.json：单期详情（C 端播放页用）
   - episodes/today/{yyyymmdd}.json：今日节目单例（C 端首页用）
   - episodes/history/{yyyymm}.json：当月历史列表（C 端历史页用，追加写）
3. 发布后失效 B 端缓存，保证运营后台与 C 端数据一致
"""
import json
import logging

from app.cache.manager import cache
from app.cos.client import cos_client
from app.models import Episode

logger = logging.getLogger(__name__)


def _episode_detail(episode: Episode) -> dict:
    """构造 episode 详情字典（详情对象与今日单例共用同一结构）。"""
    return {
        "id": episode.id,
        "date": episode.date.isoformat(),
        "title": episode.title,
        "duration": episode.duration,
        "audio_url": episode.audio_url,
        "cover_url": episode.cover_url,
        "script_id": episode.script_id,
        "categories": episode.categories,
        "is_backup": episode.is_backup,
        "published_at": episode.published_at.isoformat() if episode.published_at else None,
    }


def _episode_summary(episode: Episode) -> dict:
    """构造 episode 摘要字典（历史列表项，字段精简）。"""
    return {
        "id": episode.id,
        "date": episode.date.isoformat(),
        "title": episode.title,
        "duration": episode.duration,
        "audio_url": episode.audio_url,
        "cover_url": episode.cover_url,
        "is_backup": episode.is_backup,
        "published_at": episode.published_at.isoformat() if episode.published_at else None,
    }


async def _put_json(key: str, payload: dict) -> None:
    """统一封装 COS JSON 对象写入。"""
    await cos_client.put_object(
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


async def publish_episode_to_cos(episode: Episode) -> None:
    """将节目发布到 COS（详情 + 今日单例 + 当月历史列表）并失效 B 端缓存。

    Args:
        episode: 已 published 的节目 ORM 对象
    """
    detail = _episode_detail(episode)
    date_str = episode.date.strftime("%Y%m%d")
    yyyymm = episode.date.strftime("%Y%m")

    # 1. 详情对象：C 端播放页读取单期完整信息
    await _put_json(f"episodes/detail/{episode.id}.json", detail)

    # 2. 今日节目单例：C 端首页按日期定位最新一期
    await _put_json(f"episodes/today/{date_str}.json", detail)

    # 3. 追加当月历史列表：先读后写，同日 episode 替换避免重复
    history_key = f"episodes/history/{yyyymm}.json"
    existing = await cos_client.get_object_bytes(history_key)
    history_list: list = []
    if existing is not None:
        try:
            parsed = json.loads(existing)
            if isinstance(parsed, list):
                history_list = parsed
        except json.JSONDecodeError:
            # 历史对象损坏则重建，避免脏数据阻断发布
            history_list = []

    # 同日 episode 替换（备播覆盖原节目场景），再追加新条目
    history_list = [
        item for item in history_list
        if item.get("date") != episode.date.isoformat()
    ]
    history_list.append(_episode_summary(episode))
    # 按日期升序排列，C 端展示顺序稳定
    history_list.sort(key=lambda x: x.get("date", ""))
    await _put_json(history_key, history_list)

    # 4. 失效 B 端缓存：今日节目与历史列表缓存需刷新
    # delete_pattern 仅支持前缀匹配（见 CacheManager），覆盖当月及历史所有缓存
    await cache.delete(f"episodes:today:{episode.date.isoformat()}")
    await cache.delete_pattern("episodes:history:*")

    logger.info(
        "节目已发布到 COS episode_id=%s date=%s",
        episode.id, episode.date,
    )
