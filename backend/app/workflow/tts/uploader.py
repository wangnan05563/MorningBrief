"""腾讯云 COS 上传（LLD 7.5）。

将音频二进制上传至 COS，返回 CDN URL 供拼接模块使用。
COS SDK 为同步库，用 asyncio.to_thread 包装避免阻塞事件循环。
"""
import asyncio
import logging

from qcloud_cos import CosConfig, CosS3Client

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 模块级懒加载单例：避免每次上传重建连接，复用 HTTP 连接池
_cos_client: CosS3Client | None = None


def _get_client() -> CosS3Client:
    """懒加载 COS 客户端单例。

    首次调用时初始化，后续复用。延迟到首次上传而非模块 import 时创建，
    避免配置未就绪或测试环境因缺少凭证而 import 报错。
    """
    global _cos_client
    if _cos_client is None:
        config = CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
        _cos_client = CosS3Client(config)
    return _cos_client


def _upload_sync(data: bytes, key: str) -> str:
    """同步上传实现，由 asyncio.to_thread 调用。

    返回 CDN URL（优先 CDN 域名，无则回退 COS 默认 URL）。
    """
    client = _get_client()
    client.put_object(
        Bucket=settings.COS_BUCKET,
        Body=data,
        Key=key,
        EnableMD5=True,
    )
    # CDN 域名优先，否则拼 COS 默认 URL
    if settings.COS_CDN_DOMAIN:
        base = settings.COS_CDN_DOMAIN.rstrip("/")
    else:
        # 回退格式: https://<bucket>.cos.<region>.myqcloud.com
        base = (
            f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com"
        )
    return f"{base}/{key}"


async def upload_to_cos(data: bytes, key: str) -> str:
    """上传二进制到 COS，返回可访问 URL。

    Args:
        data: 二进制内容
        key: COS 对象 key（如 "tts/seg_1.mp3"）

    Returns:
        CDN URL 或 COS 默认 URL
    """
    # 同步 SDK 调用放入线程池，避免阻塞事件循环
    return await asyncio.to_thread(_upload_sync, data, key)
