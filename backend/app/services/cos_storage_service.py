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
- 快照恢复（.backup 快照 → 原 Key，恢复前先备份当前对象；T02609）
- 快照保留份数清理（COS_BACKUP_KEEP_COUNT，默认每对象 5 份）
- 对象元数据（大小 / 最后修改 / 类型）

所有方法先用 is_cos_configured() 守卫：未配置 COS 时直接抛出可读业务异常，
避免创建空客户端抛晦涩错误。KEY/Prefix 做路径穿越校验，拒绝绝对路径与 ".."。
"""
import logging
import re
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

# 快照 Key 的两处形态：桶根 ".backup/..." 与任意层级 "<dir>/.backup/..."
_SNAPSHOT_ROOT_MARK = f"{_BACKUP_DIR_NAME}/"
_SNAPSHOT_DIR_MARK = f"/{_BACKUP_DIR_NAME}/"

# 同一秒内连续覆盖时快照名追加的序号后缀（"-1" / "-2" …）
_SNAPSHOT_SEQ_SUFFIX = re.compile(r"-\d+$")

# 快照保留份数的兜底默认值（Settings 读失败或配置表存了非数字时用）
_DEFAULT_BACKUP_KEEP_COUNT = 5

# 移动冲突预览最多列几条样例（确认框只用于点名，全量条数另有 conflict_count）
_MOVE_CONFLICT_SAMPLE_LIMIT = 10


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


def is_snapshot_key(key: str) -> bool:
    """Key 是否位于 .backup 快照目录（桶根或任意层级）。"""
    key = key or ""
    return key.startswith(_SNAPSHOT_ROOT_MARK) or _SNAPSHOT_DIR_MARK in key


def snapshot_parts(backup_key: str) -> tuple[str, str, str]:
    """把快照 Key 拆成 (原对象目录前缀, 时间戳目录前缀, 快照文件名)。

    "a/.backup/20260101-120000/a.mp3" → ("a/", "a/.backup/20260101-120000/", "a.mp3")
    ".backup/20260101-120000/a.mp3"   → ("",   ".backup/20260101-120000/",   "a.mp3")

    结构不完整（缺时间戳目录或文件名）视为非法 Key，抛业务错误而不是猜。
    """
    key = (backup_key or "").strip()
    if not is_snapshot_key(key):
        raise BizError(code=400, message=f"不是 .backup 快照对象：{backup_key}")
    if key.startswith(_SNAPSHOT_ROOT_MARK):
        head = ""
        rest = key[len(_SNAPSHOT_ROOT_MARK):]
    else:
        # 取第一处 "/.backup/"：快照只会落在被备份对象所在目录下
        idx = key.index(_SNAPSHOT_DIR_MARK) + 1
        head = key[:idx]
        rest = key[idx + len(_BACKUP_DIR_NAME) + 1:]
    stamp, sep, stored = rest.partition("/")
    if not stamp or not sep or not stored:
        raise BizError(code=400, message=f"快照 Key 结构不完整：{backup_key}")
    return head, f"{head}{_BACKUP_DIR_NAME}/{stamp}/", stored


def _snapshot_is_of(stored: str, name: str, siblings: set[str]) -> bool:
    """时间戳目录里的 stored 是不是对象 name 的快照。

    -N 是同秒防重名后缀：只有当同目录里同时存在无后缀那份时，才把它算作 name 的副本；
    否则「原文件名本身以 -1 结尾」会被误剥成另一个对象。
    """
    if stored == name:
        return True
    plain = _SNAPSHOT_SEQ_SUFFIX.sub("", stored)
    return bool(plain) and plain == name and plain in siblings


def backup_keep_count() -> int:
    """当前快照保留份数（0 表示不备份）。配置表存的是字符串也要能读。"""
    raw = getattr(get_settings(), "COS_BACKUP_KEEP_COUNT", _DEFAULT_BACKUP_KEEP_COUNT)
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return _DEFAULT_BACKUP_KEEP_COUNT


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
                    # T02609：快照对象在列表里要能被认出来，否则「旧版本」与「现役文件」长得一样，误删就是永久丢失。
                    "is_snapshot": is_snapshot_key(key),
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
        return {
            "prefix": prefix,
            "folders": folders,
            "files": files,
            # 当前就在快照目录里：页面据此提示「这些是覆盖前的旧版本」
            "is_snapshot_dir": is_snapshot_key(prefix) if prefix else False,
        }

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

    async def _snapshot_before_overwrite(self, key: str) -> Optional[str]:
        """把将被覆盖的旧对象复制到 .backup/<时间戳>/ 下，返回备份 Key。

        backup_keep_count == 0 表示「不备份」，返回 None（调用方据此提示不可回退）。
        备份对象永不覆盖：同一秒内连续覆盖时依次追加 -1/-2 后缀。
        备份成功后按保留份数清理更老的快照（T02609）。
        """
        if backup_keep_count() == 0:
            return None
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
        await self._prune_snapshots(key)
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
        """删除整个文件夹及其下所有层级的对象（含子目录、含目录占位对象本身）。

        返回实际下发给 COS 删除的对象数量。列举口径见 _list_prefix_objects：
        递归才能把 a/b/c.txt 这类深层对象一并删掉，否则只删顶层却照样报数。
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

    async def move_preview(self, source_key: str, dest_key: str) -> dict:
        """移动/重命名前的冲突预览：目标侧有多少个同名对象会被覆盖（T02608 / H19）。

        条数只来自服务端实测：前端手里只有当前页的列表，据它判断「目标位置是空的」
        是假承诺——分页外、子层级里已存在的对象照样会被 copy_object 静默换掉。
        预览与真正执行共用同一份列举与同一个 Key 映射，确认框看到的条数＝实际覆盖数。
        """
        source, dest, is_prefix, keys, conflicts = await self._move_plan(source_key, dest_key)
        return self._move_preview_payload(source, dest, is_prefix, len(keys), conflicts)

    async def _move_plan(self, source_key: str, dest_key: str) -> tuple:
        """算出 (source, dest, is_prefix, 源 Key 列表, 冲突列表)，预览与执行共用。"""
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        is_prefix = source_key.endswith("/")
        if not is_prefix:
            _validate_key(source_key)
            _validate_key(dest_key)
            conflicts = []
            if await _cos_call(cos_client.object_exists(Key=dest_key)):
                meta = await _cos_call(cos_client.head_object(Key=dest_key))
                conflicts = [{
                    "dest_key": dest_key,
                    "size": meta.get("size", 0),
                    "last_modified": meta.get("last_modified", ""),
                }]
            return (source_key, dest_key, False, [source_key], conflicts)

        source_prefix = _normalize_prefix(source_key)
        dest_prefix = _normalize_prefix(dest_key)
        _validate_key(source_prefix)
        _validate_key(dest_prefix)
        keys = await self._list_all_keys(source_prefix)
        if not keys:
            return (source_prefix, dest_prefix, True, [], [])
        existing = await self._list_prefix_sizes(dest_prefix)
        conflicts = []
        for _src, dst in self._move_pairs(source_prefix, dest_prefix, keys):
            if dst in existing:
                conflicts.append({"dest_key": dst, "size": existing[dst], "last_modified": ""})
        return (source_prefix, dest_prefix, True, keys, conflicts)

    @staticmethod
    def _move_pairs(source_prefix: str, dest_prefix: str, keys: list[str]) -> list[tuple[str, str]]:
        """源 Key → 目标 Key 的唯一映射（把源前缀替换为目标前缀）。"""
        return [
            (src, dest_prefix + (src[len(source_prefix):] if src.startswith(source_prefix) else src))
            for src in keys
        ]

    @staticmethod
    def _move_preview_payload(source, dest, is_prefix, moved, conflicts) -> dict:
        return {
            "source_key": source,
            "dest_key": dest,
            "is_prefix": is_prefix,
            "moved": moved,
            "conflict_count": len(conflicts),
            "conflicts": conflicts[:_MOVE_CONFLICT_SAMPLE_LIMIT],
            "conflicts_truncated": len(conflicts) > _MOVE_CONFLICT_SAMPLE_LIMIT,
        }

    async def move_object(
        self, source_key: str, dest_key: str, overwrite: bool = False
    ) -> dict:
        """重命名 / 移动对象（目标同名默认拒绝，覆盖前先留快照）。

        source_key 以 '/' 结尾视为文件夹：递归复制前缀下所有对象到 dest 前缀，
        再删除源对象；否则为单文件复制 + 删除。返回 {moved, overwritten, backup_keys}。

        H19（T02608）：旧实现直接 copy_object——COS 复制即覆盖，目标已存在时被换掉的
        那个对象连一条提示都没有，与上传路径覆盖前不备份是同一类破坏。现在与
        upload_file 同一口径，且把关放在服务端（确认框可被绕过、列表存在时间窗）：
        - 目标已存在且 overwrite=False → 业务码 409，消息点名目标 Key 与当前大小；
        - overwrite=True → 先把每个将被覆盖的目标对象复制进 .backup/<时间戳>/ 再复制，
          快照失败即中止整个移动，绝不退化成静默覆盖。
        """
        source, dest, is_prefix, keys, conflicts = await self._move_plan(source_key, dest_key)
        if is_prefix:
            return await self._move_prefix(source, dest, overwrite, keys, conflicts)
        if conflicts and not overwrite:
            raise self._move_conflict_error(source, dest, conflicts)

        backup_keys = []
        for conflict in conflicts:
            key = await self._snapshot_before_overwrite(conflict["dest_key"])
            if key:
                backup_keys.append(key)
        await _cos_call(cos_client.copy_object(SourceKey=source, Key=dest))
        await _cos_call(cos_client.delete_object(Key=source))
        return {"moved": 1, "overwritten": len(conflicts), "backup_keys": backup_keys}

    @staticmethod
    def _move_conflict_error(source: str, dest: str, conflicts: list[dict]) -> BizError:
        """409 消息：单个对象报大小与修改时间，文件夹报条数与样例 Key。"""
        if len(conflicts) == 1:
            one = conflicts[0]
            detail = f"{dest}（{_human_size(one.get('size'))}，更新于 {one.get('last_modified') or '时间未知'}）"
            tail = "已拒绝移动，请确认后再以覆盖方式重做"
        else:
            names = "、".join(c["dest_key"] for c in conflicts[:_MOVE_CONFLICT_SAMPLE_LIMIT])
            more = "…" if len(conflicts) > _MOVE_CONFLICT_SAMPLE_LIMIT else ""
            detail = f"{len(conflicts)} 个同名对象（{names}{more}）"
            tail = "已拒绝移动整个文件夹，请确认后再以覆盖方式重做"
        return BizError(
            code=409,
            message=f"目标位置已有{detail}；移动「{source}」会把它们换掉。{tail}",
            data={
                "conflict_count": len(conflicts),
                "conflicts": conflicts[:_MOVE_CONFLICT_SAMPLE_LIMIT],
            },
        )

    async def _move_prefix(
        self,
        source_prefix: str,
        dest_prefix: str,
        overwrite: bool,
        keys: list[str],
        conflicts: list[dict],
    ) -> dict:
        """递归移动文件夹：复制前缀下所有对象到新前缀，再删源。

        keys / conflicts 都来自 _move_plan：预览、409 判断与实际覆盖用同一份数据，
        不会出现「确认框说 3 条、实际覆盖 5 条」。
        """
        if conflicts and not overwrite:
            raise self._move_conflict_error(source_prefix, dest_prefix, conflicts)
        if not keys:
            return {"moved": 0, "overwritten": 0, "backup_keys": []}
        # 覆盖前逐个快照；这里失败会直接上抛中止，此时源尚未删除，不会两头空
        backup_keys = []
        for conflict in conflicts:
            key = await self._snapshot_before_overwrite(conflict["dest_key"])
            if key:
                backup_keys.append(key)
        for src, dst in self._move_pairs(source_prefix, dest_prefix, keys):
            await _cos_call(cos_client.copy_object(SourceKey=src, Key=dst))
        # 复制成功后删除源（分批）
        batch_size = 500
        for i in range(0, len(keys), batch_size):
            await _cos_call(cos_client.delete_objects(keys[i:i + batch_size]))
        return {"moved": len(keys), "overwritten": len(conflicts), "backup_keys": backup_keys}

    # ---- 快照恢复（T02609） ----

    async def restore_preview(self, backup_key: str) -> dict:
        """恢复前的预览：快照元数据、被恢复的原对象 Key、目标当前状态。

        target_key 由服务端从快照 Key 推出——前端手里没有「快照属于谁」的映射，
        让调用方自己传目标 Key 才是把「恢复到哪」交给一个可能拼错的字符串。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(backup_key)
        target_key = await self._resolve_snapshot_target(backup_key)
        if not await _cos_call(cos_client.object_exists(Key=backup_key)):
            raise BizError(code=404, message=f"快照对象不存在：{backup_key}")

        snapshot = await _cos_call(cos_client.head_object(Key=backup_key))
        target_meta = None
        if await _cos_call(cos_client.object_exists(Key=target_key)):
            target_meta = await _cos_call(cos_client.head_object(Key=target_key))
        return {
            "backup_key": backup_key,
            "target_key": target_key,
            "snapshot": {
                "size": snapshot.get("size", 0),
                "last_modified": snapshot.get("last_modified", ""),
            },
            "target_exists": target_meta is not None,
            "target": None if target_meta is None else {
                "size": target_meta.get("size", 0),
                "last_modified": target_meta.get("last_modified", ""),
            },
            "backup_keep_count": backup_keep_count(),
        }

    async def restore_snapshot(
        self, backup_key: str, target_key: str = "", overwrite: bool = False
    ) -> dict:
        """把快照复制回原对象（恢复前先给当前对象留一份快照，恢复也可回退）。

        - target_key 可留空（服务端推出）；显式传入时必须与推出值一致，
          免得「恢复 a.mp3 的快照」变成「往 b.mp3 写 a.mp3 的内容」。
        - 目标已存在且 overwrite=False → 业务码 409，与上传/移动同一口径
          （前端确认框可被绕过，把关必须在服务端）。
        - backup_keep_count == 0 时不留当前对象的快照，此时覆盖不可回退，
          响应里 backup_key=None，由界面在确认框点名风险。
        """
        if not is_cos_configured():
            raise BizError(code=400, message=_ERROR_MESSAGE_COS_NOT_CONFIGURED)
        _validate_key(backup_key)
        derived = await self._resolve_snapshot_target(backup_key)
        if target_key and target_key != derived:
            raise BizError(
                code=400,
                message=f"快照 {backup_key} 对应的原对象是 {derived}，不能恢复到 {target_key}",
            )
        _validate_key(derived)
        if not await _cos_call(cos_client.object_exists(Key=backup_key)):
            raise BizError(code=404, message=f"快照对象不存在：{backup_key}")

        snapshot = await _cos_call(cos_client.head_object(Key=backup_key))
        target_meta = None
        if await _cos_call(cos_client.object_exists(Key=derived)):
            target_meta = await _cos_call(cos_client.head_object(Key=derived))
        if target_meta is not None and not overwrite:
            raise BizError(
                code=409,
                message=(
                    f"目标对象已存在：{derived}（{_human_size(target_meta.get('size', 0))}，"
                    f"更新于 {target_meta.get('last_modified') or '时间未知'}）；"
                    "已拒绝恢复该快照，请确认后再以覆盖方式恢复"
                ),
            )

        current_backup = None
        if target_meta is not None:
            current_backup = await self._snapshot_before_overwrite(derived)
        await _cos_call(cos_client.copy_object(SourceKey=backup_key, Key=derived))
        return {
            "restored_from": backup_key,
            "target_key": derived,
            "overwritten": target_meta is not None,
            "backup_key": current_backup,
            "size": snapshot.get("size", 0),
            "last_modified": snapshot.get("last_modified", ""),
            "backup_keep_count": backup_keep_count(),
        }

    async def _resolve_snapshot_target(self, backup_key: str) -> str:
        """从快照 Key 推出原对象 Key（同秒序号后缀按同目录兄弟快照判定）。"""
        head, stamp_dir, stored = snapshot_parts(backup_key)
        plain = _SNAPSHOT_SEQ_SUFFIX.sub("", stored)
        if plain and plain != stored and \
                await _cos_call(cos_client.object_exists(Key=stamp_dir + plain)):
            return head + plain
        return head + stored

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

    @staticmethod
    def _page_subdirs(resp: dict, prefix: str) -> list[str]:
        """当页 CommonPrefixes 中除自身外的子目录前缀。"""
        return [
            cp.get("Prefix", "")
            for cp in (resp.get("CommonPrefixes") or [])
            if cp.get("Prefix", "") and cp.get("Prefix", "") != prefix
        ]

    @staticmethod
    def _page_contents(resp: dict) -> list[dict]:
        """当页 Contents 条目。"""
        return resp.get("Contents") or []

    @staticmethod
    def _page_next_marker(resp: dict) -> str:
        """下一页游标：优先 NextMarker，缺失时取当页最后一个 Key。"""
        next_marker = resp.get("NextMarker") or (
            (resp.get("Contents") or [{}])[-1].get("Key") or ""
        )
        return next_marker

    async def _list_direct(self, prefix: str) -> tuple[list[str], list[dict]]:
        """单层列举：返回 (子目录前缀列表, 当前层直接文件条目)。

        COS 的前缀列举默认是递归的，必须带 delimiter="/" 才只看当前层——
        快照保留策略按时间戳目录逐层清点，靠的就是这个区别。
        """
        subdirs: list[str] = []
        items: list[dict] = []
        marker = ""
        for _ in range(_LIST_MAX_PAGES):
            resp = await _cos_call(cos_client.list_objects_delimited(
                prefix=prefix, delimiter="/", marker=marker, max_keys=_LIST_PAGE_SIZE
            ))
            subdirs.extend(self._page_subdirs(resp, prefix))
            items.extend(
                item for item in self._page_contents(resp)
                if item.get("Key") and item.get("Key") != prefix
            )
            if not resp.get("IsTruncated"):
                break
            marker = self._page_next_marker(resp)
            if not marker:
                break
        return subdirs, items

    async def _list_snapshots(self, key: str) -> list[dict]:
        """某对象的全部快照，新 → 旧；同秒内的 -1/-2 序号副本也归到该对象。"""
        directory, _, name = key.rpartition("/")
        base = f"{directory + '/' if directory else ''}{_BACKUP_DIR_NAME}/"
        stamp_dirs, _ = await self._list_direct(base)
        snaps: list[dict] = []
        # 时间戳目录名 %Y%m%d-%H%M%S 的字典序即时间序，倒序就是「新 → 旧」
        for stamp in sorted(stamp_dirs, reverse=True):
            _, items = await self._list_direct(stamp)
            stored_names = {
                item["Key"][len(stamp):]
                for item in items
                if item["Key"].startswith(stamp)
            }
            for item in items:
                if not item["Key"].startswith(stamp):
                    continue
                stored = item["Key"][len(stamp):]
                if not _snapshot_is_of(stored, name, stored_names):
                    continue
                snaps.append({
                    "key": item["Key"],
                    "name": stored,
                    "size": int(item.get("Size", 0) or 0),
                    "last_modified": _normalize_last_modified(item.get("LastModified")),
                })
        return snaps

    async def _prune_snapshots(self, key: str) -> list[str]:
        """按 COS_BACKUP_KEEP_COUNT 删掉更老的快照，返回被删的 Key。

        清理失败只记日志：覆盖已经写入成功，因为「旧版本没删干净」让上传接口报错，
        调用方会误以为新文件没传上去。keep=0 表示此后不再产生快照，存量不动。
        """
        keep = backup_keep_count()
        if keep <= 0:
            return []
        try:
            snaps = await self._list_snapshots(key)
        except BizError as exc:
            logger.warning("快照清理：列举失败 key=%s: %s", key, exc.message)
            return []
        stale = [snap["key"] for snap in snaps[keep:]]
        for stale_key in stale:
            try:
                await _cos_call(cos_client.delete_object(Key=stale_key))
            except BizError as exc:
                logger.warning("快照清理：删除失败 key=%s: %s", stale_key, exc.message)
        return stale

    async def _list_prefix_objects(self, prefix: str) -> list[dict]:
        """递归列举前缀下**所有层级**的对象条目（分页，最多 10 页）。

        T03313：这里必须显式传 delimiter=""。`list_objects_delimited` 的默认
        delimiter 是 "/"，按目录分组后 Contents 只剩当前层的直接文件，子目录里的
        对象全部落进 CommonPrefixes 被丢掉——删除文件夹只删顶层却报「已删 N 个」，
        移动文件夹也只搬顶层，子目录原地留下成为无主对象。传空串才是真递归。
        单层视图（list_path / 快照清点）仍走 _list_direct，两者不可互换。
        """
        items: list[dict] = []
        marker = ""
        pages = 0
        while pages < _LIST_MAX_PAGES:
            pages += 1
            resp = await _cos_call(cos_client.list_objects_delimited(
                prefix=prefix, delimiter="", marker=marker, max_keys=_LIST_PAGE_SIZE
            ))
            for item in resp.get("Contents", []) or []:
                if item.get("Key"):
                    items.append(item)
            if not resp.get("IsTruncated"):
                break
            next_marker = resp.get("NextMarker") or (
                (resp.get("Contents", []) or [])[-1].get("Key") if resp.get("Contents") else ""
            )
            if not next_marker:
                break
            marker = next_marker
        return items

    async def _list_all_keys(self, prefix: str) -> list[str]:
        """递归列举前缀下所有对象 Key（含各层子目录里的对象与目录占位对象）。"""
        return [item["Key"] for item in await self._list_prefix_objects(prefix)]

    async def _list_prefix_sizes(self, prefix: str) -> dict[str, int]:
        """递归列举前缀下所有对象 → {key: size}。

        冲突预览要给出「覆盖哪个对象、它现在多大」，光有条数不够；
        与 _list_all_keys 共用同一份列举，预览所见即移动所为。
        """
        return {item["Key"]: item.get("Size") or 0 for item in await self._list_prefix_objects(prefix)}


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



