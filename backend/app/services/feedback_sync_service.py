"""反馈数据 COS → SQLite 同步服务。

设计要点：
- SCF 端将用户反馈写入 COS 对象 feedbacks/{yyyymmdd}/{feedback_id}.json
- 本服务定时（每小时）从 COS 列出 feedbacks/ 前缀下所有对象
- 逐个读取 JSON、解析为 Feedback 记录写入 SQLite（INSERT OR IGNORE 幂等）
- 写入成功后删除 COS 源对象，避免重复同步
- 单条失败不中断整批同步，错误计入 details 返回

幂等保障：
1. id 主键冲突时 INSERT OR IGNORE 跳过
2. 写入成功后删除 COS 源对象，下次同步不再读到
3. 即使删除失败，下次同步也会因主键冲突而跳过
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.timeutil import localnow_naive
from app.cos.client import cos_client
from app.database import AsyncSessionLocal
from app.models.feedback import Feedback

logger = logging.getLogger(__name__)

# COS 反馈对象前缀（与 SCF feedbacks/index.py 写入路径对齐）
FEEDBACK_COS_PREFIX = "feedbacks/"


def _parse_created_at(raw: Optional[str]) -> Optional[datetime]:
    """解析 SCF 写入的 ISO 8601 时间字符串为 naive datetime。

    SCF 端用 datetime.now(timezone.utc).isoformat() 写入，带时区信息；
    SQLite DATETIME 列无时区，需存 naive UTC（与 SCF 写入的 UTC 源保持一致）。
    """
    if not raw:
        return None
    try:
        # fromisoformat 在 Python 3.11+ 支持带时区的 ISO 字符串
        dt = datetime.fromisoformat(raw)
        # 统一转为 naive UTC（先转 UTC 再剥除时区信息）
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        logger.warning("反馈 created_at 解析失败，使用当前时间回退: %s", raw)
        return localnow_naive()


class FeedbackSyncService:
    """反馈数据 COS → SQLite 同步服务。

    定时从 COS 读取 feedbacks/ 前缀下的 JSON 对象，
    写入 SQLite feedback 表后删除 COS 源对象，确保数据不重复。
    """

    @staticmethod
    async def sync_feedbacks() -> dict:
        """执行同步，返回 { synced: N, errors: N, details: [...] }。

        流程：
        1. list_objects 列出 feedbacks/ 前缀下所有对象
        2. 逐个 get_object_bytes 读取 JSON
        3. INSERT OR IGNORE 写入 SQLite（主键冲突跳过）
        4. 写入成功后 delete_object 删除 COS 源对象
        5. 单条失败不中断整批，错误计入 details
        """
        result = {"synced": 0, "errors": 0, "details": []}

        # 1. 列出所有 feedbacks/ 前缀对象
        try:
            objects = await cos_client.list_objects(Prefix=FEEDBACK_COS_PREFIX)
        except Exception as e:
            # COS 不可用时不中断调度器，下次调度继续尝试
            logger.exception("列出 COS feedbacks/ 前缀对象失败: %s", e)
            result["errors"] = 1
            result["details"].append({"phase": "list_objects", "error": str(e)})
            return result

        if not objects:
            logger.info("无待同步反馈对象")
            return result

        logger.info("待同步反馈对象 %d 个", len(objects))

        # 2. 逐个处理
        for obj in objects:
            key = obj.get("Key")
            if not key or not key.endswith(".json"):
                # 跳过非 JSON 对象（如目录占位符）
                continue

            try:
                # 读取 COS 对象内容
                body = await cos_client.get_object_bytes(key)
                if body is None:
                    result["errors"] += 1
                    result["details"].append({"key": key, "error": "对象不存在或读取失败"})
                    continue

                payload = json.loads(body)
                feedback_id = payload.get("feedback_id")
                if not feedback_id:
                    result["errors"] += 1
                    result["details"].append({"key": key, "error": "缺少 feedback_id 字段"})
                    continue

                # 3. INSERT OR IGNORE 写入（主键冲突跳过，保证幂等）
                # 用 sqlite_insert 而非 ORM merge：单条 INSERT 语义更清晰且性能更优
                stmt = sqlite_insert(Feedback).values(
                    id=str(feedback_id),
                    user_id=str(payload.get("user_id", "")),
                    category=payload.get("category", "other"),
                    content=payload.get("content", ""),
                    contact=payload.get("contact"),
                    status="pending",
                    created_at=_parse_created_at(payload.get("created_at")),
                    synced_at=localnow_naive(),
                ).on_conflict_do_nothing(index_elements=["id"])

                async with AsyncSessionLocal() as session:
                    await session.execute(stmt)
                    await session.commit()

                # 4. 写入成功后删除 COS 源对象，避免下次重复同步
                # 即使此处删除失败，下次同步也会因主键冲突而跳过，幂等
                await cos_client.delete_object(key)

                result["synced"] += 1
                logger.info("同步反馈成功 feedback_id=%s key=%s", feedback_id, key)

            except Exception as e:
                # 单条失败不中断整批同步，错误计入 details
                logger.exception("同步反馈失败 key=%s: %s", key, e)
                result["errors"] += 1
                result["details"].append({"key": key, "error": str(e)})

        logger.info(
            "反馈同步完成 synced=%d errors=%d total=%d",
            result["synced"], result["errors"], len(objects),
        )
        return result
