"""云端 COS 存储管理服务（V1.5 新增）。

在 app.cos.client.cos_client 异步封装之上，提供面向管理界面的对象存储操作：
- 目录/文件列举（用 Delimiter 模拟目录树）
- 文件上传（bytes；同名默认拒绝，覆盖前自动留 .backup 快照）
- 对象存在性检查（上传/移动前的同名检测）
- 下载 URL（CDN 直链优先，否则预签名）
- 单文件删除
- 新建文件夹（占位对象）
- 删除文件夹（列举前缀后批量删除）
- 重命名 / 移动（复制 + 删除，支持文件夹递归）
- 对象元数据（大小 / 最后修改 / 类型）

所有方法先用 is_cos_configured() 守卫：未配置 COS 时直接抛出可读业务异常，
避免创建空客户端抛晦涩错误。KEY/Prefix 做路径穿越校验，拒绝绝对路径与 ".."。
"""
import logging
from datetime import datetime
from functools import wraps
from typing import Optional
from urllib.parse import urlparse

from app.config import get_settings
from app.core.exceptions import BizError
from app.cos.client import cos_client, is_cos_configured

logger = logging.getLogger(__name__)

# COS SDK 异常软依赖导入：qcloud_cos 缺失（如纯前端/仅语法检查场景）时降级为 Exception
try:
    from qcloud_cos import CosClientError, CosServiceError
except Exception:  # noqa: BLE001 — 依赖缺失不应阻断服务启动
    CosClientError = CosServiceError = Exception

# 模块级常量
_ERROR_MESSAGE_COS_NOT_CONFIGURED = "COS 未配置：请先在「云端配置」页填写凭证"

# 单页列举上限；多页自动翻页（最多 10 页，覆盖 1 万对象，超出视为异常大桶需分批）
_LIST_PAGE_SIZE = 1000
_LIST_MAX_PAGES = 10

# 覆盖上传前的快照目录名（落在被覆盖对象同目录下，便于按目录找回旧版本）
_BACKUP_DIR_NAME = ".backup"

# 快照重名探测上限：同一秒内连续覆盖到第 N 份即中止，避免探测无限循环
_MAX_BACKUP_PROBES = 20


def _validate_key(key: str) -> None:
    """校验对象 Key / 前缀，防路径穿越。

    拒绝：空、以 '/' 开头（绝对路径）、含 ".."、含反斜杠。
    允许内部 "/"（目录分隔符），由调用方决定是否为前缀。
    """
    if not key:
        raise BizError(code=400, message="对象 Key 不能为空")
    if key.startswith("/"):
        raise BizError(code=400, message="非法路径：不允许以 / 开头")
    if ".." in key or "\\" in key:
        raise BizError(code=400, message="非法路径：包含 .. 或反斜杠")


def _normalize_prefix(prefix: str) -> str:
    """规范化列举前缀：去首尾空白，非空时确保以 '/' 结尾。"""
    prefix = (prefix or "").strip()
    if prefix and not prefix.endswith("/"):
        prefix = prefix + "/"
    return prefix


def _cos_sdk_message(exc: Exception) -> str:
    """从 COS SDK 异常提取可读的原因消息（尽量语义化，避免原样 500）。

    与 CosConfigService.test_connection 的语义化口径保持一致：把凭证无效、
    Bucket 不存在、权限不足等常见 COS 服务错误转成运营可直接理解的中文提示，
    而不是让异常一路冒泡到全局兜底返回「服务内部错误」。
    """
    raw = str(exc) or ""
    if isinstance(exc, CosServiceError):
        # 优先取 SDK 解析出的错误码/消息；get_error_code 可能返回 Unknown
        code = getattr(exc, "get_error_code", lambda: "")()
        detail = (code and code != "Unknown" and code) or raw
    else:
        detail = raw
    if "AccessDenied" in raw or "403" in raw:
        return "COS 凭证无效或无 Bucket 访问权限（AccessDenied）"
    if "NoSuchBucket" in raw or "NoSuchKey" in raw:
        return f"COS 存储桶/对象不存在: {_cos_bucket()}"
    if "SecretId" in raw or "SecretKey" in raw:
        return "COS SecretId / SecretKey 无效"
    if "RequestTimeTooSkewed" in raw or "时间" in raw:
        return "COS 请求时间偏差过大，请检查服务器时钟"
    return detail or "COS 服务调用失败"


def _cos_bucket() -> str:
    """返回当前生效的 Bucket 名（语义化消息里展示用）。"""
    return getattr(get_settings(), "COS_BUCKET", "") or ""


def _human_size(size) -> str:
    """把字节数转成运营可读的大小（错误提示里用，避免裸数字）。"""
    if size is None:
        return "大小未知"
    try:
        n = float(size)
    except (TypeError, ValueError):
        return "大小未知"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


async def _cos_call(coro):
    """执行一次 COS SDK 异步调用，把 SDK 异常统一转成语义化 BizError。

    过滤掉 CosServiceError / CosClientError —— 这两类是 SDK 定义的所有失败路径，
    qcloud_cos 只抛这两种异常，其余异常（编程错误等）仍应正常上抛暴露。
    转成的 BizError 带具体原因，配合全局异常处理给前端友好提示而非 500。
    """
    try:
        return await coro
    except (CosServiceError, CosClientError) as e:
        raise BizError(code=502, message=_cos_sdk_message(e), http_status=502) from e


class CosStorageService:
    """云端 COS 存储管理服务。

    直接复用模块级 cos_client 单例（与上传/代理链路同一客户端）。
    """

    # ---- 列举 ----

    async def list_path(self, prefix: str = "") -> dict:  # NOSONAR
        """列举某前缀下的目录与文件（模拟目录树）。

        返回结构：
        {
            "prefix": "folder/",          # 当前所在前缀
            "folders": ["sub1/", ...],    # 子目录名（含结尾 /）
            "files": [                    # 当前层直接文件
                {"key": "folder/a.txt", "name": "a.txt",
                 "size": 123, "last_modified": "2026-...", "content_type": "text/plain"},
                ...
            ],
        }
        空桶 / 空前缀返回空列表，不抛异常。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)

        prefix = _normalize_prefix(prefix)
        _validate_key(prefix) if prefix else None

        folders: list[str] = []
        files: list[dict] = []
        marker = ""
        pages = 0

        while pages < _LIST_MAX_PAGES:
            pages += 1
            resp = await _cos_call(cos_client.list_objects_delimited(
                prefix=prefix, delimiter="/", marker=marker, max_keys=_LIST_PAGE_SIZE
            ))
            # 子目录：CommonPrefixes 中的 Prefix 形如 "folder/sub/"
            for cp in resp.get("CommonPrefixes", []) or []:
                sub = cp.get("Prefix", "")
                if not sub or sub == prefix:
                    continue
                folders.append(sub[len(prefix):] if sub.startswith(prefix) else sub)

            # 文件：Contents 中的 Key 形如 "folder/a.txt"
            for item in resp.get("Contents", []) or []:
                key = item.get("Key", "")
                # 跳过文件夹占位对象本身（Key 等于当前前缀）
                if key == prefix:
                    continue
                files.append({
                    "key": key,
                    "name": key[len(prefix):] if key.startswith(prefix) else key,
                    "size": int(item.get("Size", 0) or 0),
                    "last_modified": _normalize_last_modified(item.get("LastModified")),
                    "content_type": item.get("ContentType") or "",
                })

            if not resp.get("IsTruncated"):
                break
            next_marker = resp.get("NextMarker") or (
                (resp.get("Contents", []) or [])[-1].get("Key") if resp.get("Contents") else ""
            )
            if not next_marker:
                break
            marker = next_marker

        # 稳定排序：目录在前、文件在后，各自按名称
        folders.sort()
        files.sort(key=lambda f: f["name"])
        return {"prefix": prefix, "folders": folders, "files": files}

    # ---- 存在性检查 ----

    async def object_exists(self, key: str) -> dict:
        """检查对象是否存在并回带元数据（上传/移动前的同名检测，FR-UX-205）。

        不存在时 exists=False 且元数据为空，不抛异常 —— 调用方需要的是
        「有没有」这个事实，而不是把 NoSuchKey 翻译成错误提示。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(key)

        exists = await _cos_call(cos_client.object_exists(Key=key))
        meta = await _cos_call(cos_client.head_object(Key=key)) if exists else {}
        return {
            "key": key,
            "exists": exists,
            "size": meta.get("size", 0),
            "last_modified": meta.get("last_modified", ""),
            "content_type": meta.get("content_type", ""),
        }

    # ---- 上传 ----

    async def upload_file(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        overwrite: bool = False,
    ) -> dict:
        """上传对象到 COS（同名默认拒绝，覆盖前自动留快照）。

        key 为该对象的完整路径（含前缀）。返回 {key, size, content_type,
        overwritten, previous, backup_key}。

        FR-UX-205：旧实现直接 put_object，重传同名文件即静默覆盖旧对象。
        现在由服务端把关（前端确认框可被绕过、列表拉取也存在时间窗）：
        - 同名已存在且 overwrite=False → 业务码 409，让调用方先确认；
        - overwrite=True → 先把旧对象复制到同目录 .backup/<时间戳>/ 再写入，
          覆盖动作因此可回退；备份失败即中止覆盖，绝不退化成静默覆盖。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(key)

        previous = await _cos_call(cos_client.head_object(Key=key)) \
            if await _cos_call(cos_client.object_exists(Key=key)) else None
        if previous is not None and not overwrite:
            raise BizError(
                code=409,
                message=(
                    f"同名文件已存在：{key}（{_human_size(previous.get('size', 0))}，"
                    f"更新于 {previous.get('last_modified') or '时间未知'}）；"
                    "已拒绝覆盖上传，请确认后再以覆盖方式重传"
                ),
            )

        backup_key = None
        if previous is not None:
            backup_key = await self._snapshot_before_overwrite(key)

        await _cos_call(cos_client.put_object(Key=key, Body=data, ContentType=content_type))
        return {
            "key": key,
            "size": len(data),
            "content_type": content_type or "",
            "overwritten": previous is not None,
            "previous": previous,
            "backup_key": backup_key,
        }

    async def _snapshot_before_overwrite(self, key: str) -> str:
        """把将被覆盖的旧对象复制到 .backup/<时间戳>/ 下，返回备份 Key。

        备份对象永不覆盖：同一秒内连续覆盖时依次追加 -1/-2 后缀。
        """
        directory, _, name = key.rpartition("/")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{directory + '/' if directory else ''}{_BACKUP_DIR_NAME}/{stamp}"
        backup_key = f"{base}/{name}"
        for seq in range(_MAX_BACKUP_PROBES):
            if not await _cos_call(cos_client.object_exists(Key=backup_key)):
                break
            backup_key = f"{base}/{name}-{seq + 1}"
        else:
            raise BizError(
                code=409,
                message=f"同一秒内已有 {_MAX_BACKUP_PROBES} 份快照，请稍后重传（已中止覆盖）",
            )
        try:
            await _cos_call(cos_client.copy_object(SourceKey=key, Key=backup_key))
        except BizError as exc:
            raise BizError(
                code=exc.code,
                message=f"覆盖前快照备份失败，已中止覆盖：{exc.message}",
            ) from exc
        return backup_key

    # ---- 下载 ----

    async def get_download_url(self, key: str, expired: int = 300) -> str:
        """获取对象下载地址。

        CDN 域名已配置时返回 CDN 直链（公开访问更快）；否则返回 COS 预签名 URL。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(key)

        settings = get_settings()
        cdn = (settings.COS_CDN_DOMAIN or "").strip()
        if cdn:
            # CDN 域名可能带 scheme 也可能不带；统一拼成直链
            netloc = urlparse(cdn).netloc or cdn
            scheme = urlparse(cdn).scheme or "https"
            return f"{scheme}://{netloc.rstrip('/')}/{key.lstrip('/')}"
        return await _cos_call(cos_client.get_presigned_download_url(Key=key, Expired=expired))

    # ---- 下载对象字节（素材导入场景） ----

    async def get_object_bytes(self, key: str) -> bytes:
        """下载对象原始字节，用于 COS 素材导入（云端存储导入渠道）。

        先用 is_cos_configured 守卫（未配置抛可读异常），KEY 做路径穿越校验，
        下载失败（对象不存在/无权限）抛 404 业务异常。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(key)
        data = await cos_client.get_object_bytes(key)
        if data is None:
            raise BizError(code=404, message=f"对象下载失败或不存在: {key}")
        return data

    # ---- 删除 ----

    async def delete_file(self, key: str) -> None:
        """删除单个对象。"""
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(key)
        await _cos_call(cos_client.delete_object(Key=key))

    async def delete_folder(self, prefix: str) -> int:
        """删除整个文件夹（列举前缀下所有对象后批量删除）。

        返回删除的对象数量（含占位对象本身）。空文件夹（仅占位对象）也能删。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        prefix = _normalize_prefix(prefix)
        _validate_key(prefix)

        keys = await self._list_all_keys(prefix)
        if not keys:
            return 0
        # 分批删除，避免单次请求对象过多
        batch_size = 500
        for i in range(0, len(keys), batch_size):
            await _cos_call(cos_client.delete_objects(keys[i:i + batch_size]))
        return len(keys)

    # ---- 文件夹 ----

    async def create_folder(self, prefix: str) -> dict:
        """新建文件夹（上传一个占位对象，使空目录在列举中可见）。

        prefix 为该目录的完整路径（含结尾 /）。返回 {key}。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        prefix = _normalize_prefix(prefix)
        _validate_key(prefix)

        await _cos_call(cos_client.put_object(
            Key=prefix, Body=b"", ContentType="application/x-directory"
        ))
        return {"key": prefix}

    # ---- 重命名 / 移动 ----

    async def move_object(self, source_key: str, dest_key: str) -> dict:
        """重命名 / 移动对象。

        source_key 以 '/' 结尾视为文件夹：递归复制前缀下所有对象到 dest 前缀，
        再删除源对象；否则为单文件复制 + 删除。覆盖目标（COS 复制即覆盖）。
        返回 {moved: N}（移动的对象数）。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        # 文件夹移动
        if source_key.endswith("/"):
            return await self._move_prefix(source_key, dest_key)
        _validate_key(source_key)
        _validate_key(dest_key)

        await _cos_call(cos_client.copy_object(SourceKey=source_key, Key=dest_key))
        await _cos_call(cos_client.delete_object(Key=source_key))
        return {"moved": 1}

    async def _move_prefix(self, source_prefix: str, dest_prefix: str) -> dict:
        """递归移动文件夹：复制前缀下所有对象到新前缀，再删源。"""
        source_prefix = _normalize_prefix(source_prefix)
        dest_prefix = _normalize_prefix(dest_prefix)
        _validate_key(source_prefix)
        _validate_key(dest_prefix)

        keys = await self._list_all_keys(source_prefix)
        if not keys:
            return {"moved": 0}
        for src in keys:
            # 计算目标 key：把源前缀替换为目标前缀
            rel = src[len(source_prefix):] if src.startswith(source_prefix) else src
            dst = dest_prefix + rel
            await _cos_call(cos_client.copy_object(SourceKey=src, Key=dst))
        # 复制成功后删除源（分批）
        batch_size = 500
        for i in range(0, len(keys), batch_size):
            await _cos_call(cos_client.delete_objects(keys[i:i + batch_size]))
        return {"moved": len(keys)}

    # ---- 元数据 ----

    async def get_metadata(self, key: str) -> dict:
        """获取对象元数据。"""
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(key)
        meta = await _cos_call(cos_client.head_object(Key=key))
        meta["key"] = key
        return meta

    # ---- 内部工具 ----

    async def _list_all_keys(self, prefix: str) -> list[str]:
        """列举某前缀下所有对象 Key（不分页上限，最多 10 页）。"""
        keys: list[str] = []
        marker = ""
        pages = 0
        while pages < _LIST_MAX_PAGES:
            pages += 1
            resp = await _cos_call(cos_client.list_objects_delimited(
                prefix=prefix, marker=marker, max_keys=_LIST_PAGE_SIZE
            ))
            for item in resp.get("Contents", []) or []:
                k = item.get("Key")
                if k:
                    keys.append(k)
            if not resp.get("IsTruncated"):
                break
            next_marker = resp.get("NextMarker") or (
                (resp.get("Contents", []) or [])[-1].get("Key") if resp.get("Contents") else ""
            )
            if not next_marker:
                break
            marker = next_marker
        return keys


def _normalize_last_modified(value) -> str:
    """归一化 COS 返回的 LastModified（datetime 或字符串）为 ISO 字符串。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return value.isoformat()
    except Exception:
        return str(value)



