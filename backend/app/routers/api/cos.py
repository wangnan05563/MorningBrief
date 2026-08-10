"""C 端 COS 直传（预签名上传）路由（V1.5 新增）。

用途：小程序头像等 UGC 直接上传到 COS，避免流量经后端磁盘代理（data/avatars）。

安全约束（与 B 端 COS 上传一致，且更严格）：
- 必须登录（require_user）：从 JWT 拿到 user_id
- 对象 Key 强制限定在 user:{user_id}/ 前缀下，杜绝越权覆盖他人对象
- 文件名做 basename + 扩展名白名单校验，防路径穿越与可执行文件上传
- 不把 ContentType 签入预签名，客户端 PUT 可自由带 content-type

COS 未配置时返回 cos_enabled=false，前端据此回退到后端代理上传
（/api/v1/users/avatar），保证开发态/未配置环境头像功能不中断。
"""
import os
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import UserPayload, require_user
from app.core.exceptions import BizError, ParamError
from app.core.response import success
from app.cos.client import (
    build_object_url,
    cos_client,
    is_cos_configured,
)

router = APIRouter(prefix="/api/v1/cos", tags=["C端-云端存储"])

# 与 users.py 头像约束保持一致：微信 chooseAvatar 仅返回 jpg/png/webp/gif
_AVATAR_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
# 预签名有效期上下限：防止前端传过长/过短导致安全或易用性问题
_PRESIGN_MIN_EXPIRED = 60
_PRESIGN_MAX_EXPIRED = 1800


class CosPresignUploadRequest(BaseModel):
    """申请上传预签名 URL 请求体。"""
    filename: str
    content_type: str | None = None
    expired: int = 300


@router.post("/presign-upload")
async def presign_upload(
    req: CosPresignUploadRequest,
    user: UserPayload = Depends(require_user),
):
    """申请对象上传预签名 URL（小程序直传 COS 用）。

    仅当 COS 已配置时返回 cos_enabled=true + upload_url（PUT 预签名）+ object_url
    （上传完成后的公开可访问地址，CDN 直链优先）。未配置时 cos_enabled=false，
    前端回退到后端代理上传（/api/v1/users/avatar）。

    安全：Key 强制 user:{user_id}/{文件名}，content_type 仅作客户端请求头提示，
    不签入签名（避免客户端 header 与签名不一致 403）。
    """
    if not is_cos_configured():
        return success(data={"cos_enabled": False})

    # 文件名安全化处理：basename 防路径穿越（../ 或绝对路径）+ 扩展名白名单
    raw = os.path.basename(req.filename or "")
    if not raw:
        raise ParamError("文件名不能为空")
    ext = os.path.splitext(raw)[1].lower()
    if ext not in _AVATAR_ALLOWED_EXTS:
        raise ParamError(
            f"不支持的图片格式：{ext}，允许：{', '.join(sorted(_AVATAR_ALLOWED_EXTS))}"
        )

    # Key 强制落在本人前缀下：user:{user_id}/{timestamp}{ext}
    # timestamp 避免同一用户覆盖历史头像，也避免并发上传互相覆盖
    key = f"user:{user.user_id}/{int(time.time() * 1000)}{ext}"

    # 防越权兜底：即便上层逻辑变化，Key 也必须以本人前缀开头
    prefix = f"user:{user.user_id}/"
    if not key.startswith(prefix):
        raise ParamError("非法上传路径")

    expired = max(_PRESIGN_MIN_EXPIRED, min(req.expired or 300, _PRESIGN_MAX_EXPIRED))
    content_type = req.content_type or "image/jpeg"

    upload_url = await cos_client.get_presigned_upload_url(
        Key=key, Expired=expired
    )
    object_url = build_object_url(key)

    return success(data={
        "cos_enabled": True,
        "upload_url": upload_url,
        "object_url": object_url,
        "key": key,
        "content_type": content_type,
    })
