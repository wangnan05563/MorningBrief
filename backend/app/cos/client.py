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
from typing import Optional

from loguru import logger

from app.config import get_settings

settings = get_settings()

# 延迟初始化 CosS3Client，避免测试时无 COS 配置导致导入失败
_cos_client = None


def is_cos_configured() -> bool:
    """检查 COS 是否已配置（单一真相源）。

    调用方据此区分日志级别：未配置时降级为 DEBUG（避免每次调用刷 WARNING
    污染日志），已配置但失败时升为 WARNING（真实异常需排障）。
    仅校验三项必填项（ID/KEY/BUCKET），REGION 有默认值不强制。
    """
    return bool(
        settings.COS_SECRET_ID
        and settings.COS_SECRET_KEY
        and settings.COS_BUCKET
    )


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
            # loguru {} 占位符延迟格式化：DEBUG 被过滤时不计算字符串，优于 f-string
            logger.debug("[cos] 对象不存在或读取失败 Key={}: {}", Key, e)
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

    async def list_objects_delimited(
        self,
        Prefix: str = "",
        Delimiter: str = "/",
        Marker: str = "",
        MaxKeys: int = 1000,
    ) -> dict:  # NOSONAR
        """列举对象（支持目录模拟）。

        用 Delimiter='/' 把对象按「目录」分组：Contents 为当前前缀下的直接文件，
        CommonPrefixes 为子目录前缀。配合 Marker/MaxKeys 实现分页遍历。
        返回 COS 原始响应字典（含 Contents / CommonPrefixes / IsTruncated / NextMarker）。
        """
        client = _get_cos_client()
        kwargs: dict = {
            "Bucket": settings.COS_BUCKET,
            "Prefix": Prefix,
            "Delimiter": Delimiter,
            "MaxKeys": MaxKeys,
        }
        if Marker:
            kwargs["Marker"] = Marker
        return await asyncio.to_thread(client.list_objects, **kwargs)

    async def head_object(self, Key: str) -> dict:  # NOSONAR
        """获取对象元数据（大小 / 最后修改 / 类型 / ETag）。

        返回归一化字典：{size, last_modified, content_type, etag}，
        与 SDK 原始响应头字段解耦，便于上层与测试使用。
        """
        client = _get_cos_client()
        resp = await asyncio.to_thread(
            client.head_object, Bucket=settings.COS_BUCKET, Key=Key
        )
        return {
            "size": int(resp.get("Content-Length", 0) or 0),
            "last_modified": resp.get("Last-Modified", ""),
            "content_type": resp.get("Content-Type", ""),
            "etag": (resp.get("ETag") or "").strip('"'),
        }

    async def get_presigned_download_url(self, Key: str, Expired: int = 300) -> str:  # NOSONAR
        """生成对象下载预签名 URL（默认 5 分钟有效）。"""
        client = _get_cos_client()
        return await asyncio.to_thread(
            client.get_presigned_download_url,
            Bucket=settings.COS_BUCKET,
            Key=Key,
            Expired=Expired,
        )

    async def get_presigned_upload_url(
        self, Key: str, Expired: int = 300, ContentType: str = None
    ) -> str:  # NOSONAR
        """生成对象上传预签名 URL（PUT 方法，小程序/前端直传 COS 用）。

        不把 ContentType 签入签名：客户端 PUT 时可自由带任意 Content-Type，
        避免签名头与实际请求头不一致导致 403。对象上传完成后的可访问地址
        由模块级 build_object_url(Key) 计算（CDN 直链优先）。
        """
        client = _get_cos_client()
        kwargs: dict = {
            "Method": "PUT",
            "Bucket": settings.COS_BUCKET,
            "Key": Key,
            "Expired": Expired,
        }
        return await asyncio.to_thread(client.get_presigned_url, **kwargs)

    async def copy_object(self, SourceKey: str, Key: str) -> None:  # NOSONAR
        """复制对象（用于重命名 / 移动）。"""
        client = _get_cos_client()
        copy_source = {
            "Bucket": settings.COS_BUCKET,
            "Key": SourceKey,
            "Region": settings.COS_REGION,
        }
        await asyncio.to_thread(
            client.copy_object,
            Bucket=settings.COS_BUCKET,
            Key=Key,
            CopySource=copy_source,
        )

    async def delete_objects(self, keys: list[str]) -> None:  # NOSONAR
        """批量删除对象（用于删除目录）。"""
        if not keys:
            return
        client = _get_cos_client()
        objects = [{"Key": k} for k in keys]
        await asyncio.to_thread(
            client.delete_objects,
            Bucket=settings.COS_BUCKET,
            Delete={"Object": objects, "Quiet": "true"},
        )

    async def object_exists(self, Key: str) -> bool:  # NOSONAR
        """检查对象是否存在。"""
        client = _get_cos_client()
        return await asyncio.to_thread(
            client.object_exists, Bucket=settings.COS_BUCKET, Key=Key
        )


def reset_cos_client() -> None:
    """重置 COS 客户端缓存（全局单例置空）。

    配置（凭证/地域/Bucket）变更后必须调用，使下一次操作用新配置重新初始化
    CosS3Client。否则模块级缓存会沿用旧凭证，导致上传/列举失败。
    """
    global _cos_client
    _cos_client = None


def build_object_url(Key: str) -> str:
    """拼出对象可公开访问的 URL（CDN 直链优先，否则 COS 默认域名）。

    与 cos_storage_service.get_download_url 的 CDN 逻辑保持一致口径。
    用于预签名上传成功后，前端/小程序直接持此 URL 作为头像等资源的访问地址。

    访问策略由 ``COS_OBJECTS_PUBLIC_READ`` 决定（消除无 CDN 时与
    get_download_url 的语义分叉）：
    - True（默认）：Bucket/对象公开读 → 返回公开直链（<image src> 直接可用）；
    - False：Bucket 私有读 → 回退预签名私有 URL（有时效，与 get_download_url
      口径一致），避免私有读时公开直链 403。C 端 UGC 直传本就以公开读为前提，
      私有读下 object_url 有时效，仅作兜底。
    """
    from urllib.parse import urlparse

    cfg = get_settings()
    cdn = (cfg.COS_CDN_DOMAIN or "").strip()
    if cdn:
        parsed = urlparse(cdn)
        netloc = parsed.netloc or cdn
        scheme = parsed.scheme or "https"
        return f"{scheme}://{netloc.rstrip('/')}/{Key.lstrip('/')}"
    if cfg.COS_OBJECTS_PUBLIC_READ:
        return (
            f"https://{cfg.COS_BUCKET}.cos.{cfg.COS_REGION}.myqcloud.com/"
            f"{Key.lstrip('/')}"
        )
    # 私有读兜底：回退预签名私有 URL，避免公开直链 403（注意有时效）
    logger.warning(
        "[cos] COS_OBJECTS_PUBLIC_READ=False 但 C 端直传需要公开可读，"
        "object_url 回退预签名私有 URL（有时效），请确认部署契约"
    )
    client = _get_cos_client()
    return client.get_presigned_download_url(
        Bucket=cfg.COS_BUCKET, Key=Key, Expired=300
    )


# 模块级单例
cos_client = CosClientWrapper()
