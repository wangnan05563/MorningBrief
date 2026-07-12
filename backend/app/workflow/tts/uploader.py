"""腾讯云 COS 上传与本地存储回退（LLD 7.5）。

COS 已配置时上传至云端返回 CDN URL；COS 未配置时降级到本地 data/audio_cache/
目录，返回 /audio/ 静态端点 URL，保证 TTS 流程在开发态/无 COS 环境下也能跑通。

COS SDK 为同步库，用 asyncio.to_thread 包装避免阻塞事件循环。
"""
import asyncio
import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 模块级懒加载单例：避免每次上传重建连接，复用 HTTP 连接池
_cos_client = None


def _local_root() -> Path:
    """本地音频缓存根目录。

    用 paths.resolve_data_dir() 解析打包态/开发态路径，与 main.py 挂载的
    /audio 静态目录保持一致，避免硬编码路径导致打包后定位失败。
    """
    try:
        from app.paths import resolve_data_dir
        return Path(resolve_data_dir()) / "audio_cache"
    except Exception:
        return Path("data/audio_cache")


def is_cos_configured() -> bool:
    """检测 COS 是否已配置真实可用值（非空且非占位符）。

    与 workflow_scheduler._is_cos_configured 同样的判断逻辑，但放在 uploader
    作为 TTS 上传回退的单一入口。COS 未配置时 TTS 上传降级到本地存储，
    保证开发态无 COS 也能完成工作流。
    """
    bucket = (settings.COS_BUCKET or "").strip()
    secret_id = (settings.COS_SECRET_ID or "").strip()
    secret_key = (settings.COS_SECRET_KEY or "").strip()
    if not bucket or not secret_id or not secret_key:
        return False
    # 占位符检测：.env.example 的 <...> 占位符
    if "<" in bucket or ">" in bucket:
        return False
    return True


def _get_client():
    """懒加载 COS 客户端单例。

    延迟到首次上传而非模块 import 时创建，避免配置未就绪或测试环境
    因缺少凭证而 import 报错。本地存储回退模式下永不触发此函数。
    """
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


def _upload_sync(data: bytes, key: str) -> str:
    """同步上传到 COS，返回 CDN URL（优先 CDN 域名，无则回退 COS 默认 URL）。"""
    client = _get_client()
    client.put_object(
        Bucket=settings.COS_BUCKET,
        Body=data,
        Key=key,
        EnableMD5=True,
    )
    if settings.COS_CDN_DOMAIN:
        base = settings.COS_CDN_DOMAIN.rstrip("/")
    else:
        # 回退格式: https://<bucket>.cos.<region>.myqcloud.com
        base = (
            f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com"
        )
    return f"{base}/{key}"


def _save_local_sync(data: bytes, key: str) -> str:
    """本地存储回退：保存到 data/audio_cache/<key>，返回 /audio/<key> 静态 URL。

    key 形如 "tts/wf-xxx/1_abc.mp3"，最终路径为 data/audio_cache/tts/wf-xxx/1_abc.mp3，
    通过 main.py 挂载的 /audio 静态目录暴露为 /audio/tts/wf-xxx/1_abc.mp3。
    """
    local_path = _local_root() / key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(data)
    return f"/audio/{key}"


async def upload_to_cos(data: bytes, key: str) -> str:
    """上传二进制音频，返回可访问 URL。

    COS 已配置时上传云端；未配置时降级本地存储。返回的 URL 在两种模式下
    都可被后续 stitch 模块通过 download_file() 下载（本地模式走文件复制）。

    Args:
        data: 二进制内容
        key: 对象 key（如 "tts/wf-xxx/1_abc.mp3"）

    Returns:
        COS 已配置：CDN URL 或 COS 默认 URL
        COS 未配置：/audio/<key> 本地静态端点 URL
    """
    if not is_cos_configured():
        # 本地存储回退：避免开发态无 COS 时 TTS 整体失败
        return await asyncio.to_thread(_save_local_sync, data, key)
    return await asyncio.to_thread(_upload_sync, data, key)
