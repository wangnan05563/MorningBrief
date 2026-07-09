"""腾讯云 COS 客户端封装（V1.2 新增）。

提供异步友好的 COS 操作接口，用于：
- 上传音频文件、JSON 元数据
- 读取 JSON 对象（供发布服务、聚合任务使用）
- JWT 黑名单对象写入

设计要点：
- 全局单例，避免重复初始化 CosS3Client
- put_object 支持同步转异步（run_in_executor）
- 失败不抛异常给上层（由调用方决定是否重试）
"""
import asyncio
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 延迟初始化 CosS3Client，避免测试时无 COS 配置导致导入失败
_cos_client = None


def _get_cos_client():
    """延迟初始化 COS 客户端（首次调用时创建）。"""
    global _cos_client
    if _cos_client is None:
        from qcloud_cos import CosConfig, CosS3Client
        config = CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
        _cos_client = CosS3Client(config)
    return _cos_client


class CosClientWrapper:
    """COS 客户端异步封装。

    CosS3Client 的方法都是同步阻塞的，用 run_in_executor 包装为异步。
    """

    async def put_object(self, Key: str, Body: bytes, ContentType: str = None) -> None:  # NOSONAR
        """上传对象到 COS。"""
        client = _get_cos_client()
        kwargs = {"Bucket": settings.COS_BUCKET, "Key": Key, "Body": Body}
        if ContentType:
            kwargs["ContentType"] = ContentType
        await asyncio.to_thread(client.put_object, **kwargs)

    async def get_object(self, Key: str) -> dict:  # NOSONAR
        """读取 COS 对象，返回原始响应（含 Body 流）。"""
        client = _get_cos_client()
        return await asyncio.to_thread(
            client.get_object, Bucket=settings.COS_BUCKET, Key=Key
        )

    async def get_object_bytes(self, Key: str) -> Optional[bytes]:  # NOSONAR
        """读取 COS 对象并返回 bytes，不存在返回 None。"""
        try:
            response = await self.get_object(Key)
            # Body 是流式对象，需同步读取
            body = response["Body"]
            return await asyncio.to_thread(body.read)
        except Exception as e:
            logger.debug(f"[cos] 对象不存在或读取失败 Key={Key}: {e}")
            return None

    async def delete_object(self, Key: str) -> None:  # NOSONAR
        """删除 COS 对象。"""
        client = _get_cos_client()
        await asyncio.to_thread(
            client.delete_object, Bucket=settings.COS_BUCKET, Key=Key
        )

    async def list_objects(self, Prefix: str) -> list[dict]:  # NOSONAR
        """列举指定前缀的对象。"""
        client = _get_cos_client()
        response = await asyncio.to_thread(
            client.list_objects, Bucket=settings.COS_BUCKET, Prefix=Prefix
        )
        return response.get("Contents", [])

    async def object_exists(self, Key: str) -> bool:  # NOSONAR
        """检查对象是否存在。"""
        client = _get_cos_client()
        return await asyncio.to_thread(
            client.object_exists, Bucket=settings.COS_BUCKET, Key=Key
        )


# 模块级单例
cos_client = CosClientWrapper()
