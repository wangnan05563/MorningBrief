"""C 端用户路由：收听统计 + 头像昵称编辑。

设计原因：
- 收听统计基于 play_progress 表聚合查询（每用户每节目一条 upsert 记录），
  不用 play_log 表是因为 play_log 是落库批写的历史日志，position/duration 语义
  为节目总时长而非实际收听时长，sum(duration) 会严重偏高
- 头像昵称编辑使用微信新版 chooseAvatar + nickname 能力，旧版 getUserProfile 已废弃
- 头像上传由前端调用 wx.uploadFile 上传到后端 /api/v1/users/avatar，
  后端流式写入 data/avatars/ 目录并返回 /avatars/{filename} URL，
  前端拿到 URL 后调 PUT /users/profile 写回 User.avatar 持久化
"""
import asyncio
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.models import User, PlayProgress, Favorite
from app.paths import resolve_avatar_dir

router = APIRouter(prefix="/api/v1/users", tags=["C端-用户"])

# 头像上传安全约束
# 为什么用这组扩展名：微信 chooseAvatar 返回的临时文件均为 jpg/png/webp/gif 中的一种
# content_type 双重校验：防止伪造扩展名上传可执行文件
_AVATAR_ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_AVATAR_ALLOWED_CONTENT_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".gif": {"image/gif"},
}
# 2MB：覆盖微信压缩后的头像（通常 <200KB），余量给高清原图
_AVATAR_MAX_SIZE = 2 * 1024 * 1024


@router.get("/stats")
async def get_user_stats(
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户收听统计：累计收听时长、累计收听期数、完播期数、收藏数。

    累计收听时长/期数从 User 表字段读取（由 play_service 增量累加）：
    - total_listen_duration：前端每次上报 listened_seconds 增量，后端累加
    - total_listen_count：首次达到 PLAY_COUNT_THRESHOLD_SEC 时 +1
    不再用 sum(PlayProgress.position)：position 是 upsert 覆盖的最后位置，
    重新听同一段只会覆盖不会累加，sum 会严重低估实际收听时长。

    完播期数仍从 PlayProgress 查询：完播标志由进度上报维护，与 User 字段解耦。
    """
    # 一次查询拿到 User 表的累计字段 + openid（收藏数查询需要）
    # 合并查询避免多次 DB 往返：原实现分别查 sum(position) 和 openid，现合并为一次
    user_result = await db.execute(
        select(
            User.total_listen_duration,
            User.total_listen_count,
            User.openid,
        ).where(User.id == user.user_id)
    )
    row = user_result.one_or_none()
    total_listen_seconds = int(row.total_listen_duration or 0) if row else 0
    total_listen_episodes = int(row.total_listen_count or 0) if row else 0
    openid = row.openid if row else None

    # 完播期数：completed=1 的记录数（每节目仅一条，无需 distinct）
    # 仍从 PlayProgress 查询：完播标志由进度上报维护，与 User 字段解耦
    completed_result = await db.execute(
        select(func.count(PlayProgress.id)).where(
            PlayProgress.user_id == user.user_id,
            PlayProgress.completed == 1,
        )
    )
    completed_episodes = completed_result.scalar() or 0

    # 收藏数：Favorite.user_id 存的是 openid 字符串
    favorite_count = 0
    if openid is not None:
        fav_result = await db.execute(
            select(func.count(Favorite.id)).where(Favorite.user_id == openid)
        )
        favorite_count = fav_result.scalar() or 0

    return success(data={
        "total_listen_seconds": total_listen_seconds,
        "total_listen_episodes": total_listen_episodes,
        "completed_episodes": int(completed_episodes),
        "favorite_count": int(favorite_count),
    })


class UpdateProfileRequest(BaseModel):
    """更新用户资料请求体。"""
    nickname: str | None = Field(None, max_length=64)
    avatar: str | None = Field(None, max_length=512)


@router.put("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户头像与昵称。

    头像由前端 wx.uploadFile 上传到后端 /api/v1/users/avatar 接口，
    后端保存到 data/avatars/ 并返回 /avatars/{filename} URL，
    前端拿到 URL 后再调本接口写回 User.avatar 字段持久化。
    """
    result = await db.execute(select(User).where(User.id == user.user_id))
    user_obj = result.scalar_one_or_none()
    if user_obj is None:
        raise BizError(code=1002, message="用户不存在")

    if req.nickname is not None:
        user_obj.nickname = req.nickname.strip() or user_obj.nickname
    if req.avatar is not None:
        user_obj.avatar = req.avatar.strip()

    await db.commit()

    return success(data={
        "success": True,
        "user": {
            "nickname": user_obj.nickname,
            "avatar": user_obj.avatar,
        },
    })


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: UserPayload = Depends(get_current_user),
):
    """上传用户头像到 data/avatars/，返回可访问的 URL。

    前端流程：
    1. wx.chooseAvatar 拿到 wxfile:// 临时路径（仅本会话有效）
    2. wx.uploadFile 上传到本接口，后端流式写入持久化目录
    3. 后端返回 /avatars/{filename} URL（由 main.py 静态挂载对外提供访问）
    4. 前端拿 URL 调 PUT /users/profile 写回 User.avatar 持久化

    安全：
    - 扩展名白名单 + content_type 双重校验，防止伪造扩展名上传可执行文件
    - 流式写入 + 大小上限，避免大文件占满内存
    - 文件名用 user_id + timestamp 命名，避免路径穿越与覆盖他人头像
    """
    if not file.filename:
        raise BizError(code=400, message="文件名不能为空")

    # 扩展名校验：file.filename 由客户端提供，basename 后再取后缀防止路径穿越
    raw_name = Path(file.filename).name
    ext = Path(raw_name).suffix.lower()
    if ext not in _AVATAR_ALLOWED_EXTS:
        raise BizError(
            code=400,
            message=f"不支持的图片格式：{ext}，允许：{', '.join(sorted(_AVATAR_ALLOWED_EXTS))}",
        )

    # content_type 双重校验：防止伪造扩展名上传非图片文件
    received_ct = (file.content_type or "").lower()
    allowed_cts = _AVATAR_ALLOWED_CONTENT_TYPES.get(ext, set())
    if received_ct and allowed_cts and received_ct not in allowed_cts:
        raise BizError(
            code=400,
            message=f"文件 content_type 与扩展名不匹配：{received_ct} vs {ext}",
        )

    # 文件名：user_id + timestamp + ext，避免覆盖他人头像与重名冲突
    # 不直接用 file.filename：用户文件名可能含中文/特殊字符，URL 编码后易出错
    filename = f"{user.user_id}_{int(time.time())}{ext}"
    target = resolve_avatar_dir() / filename

    # 流式写入 + 大小校验：避免大文件占满内存
    # 参考 admin/channels.py upload_bgm 的同款实现
    written = 0
    with open(target, "wb") as fp:  # NOSONAR
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > _AVATAR_MAX_SIZE:
                fp.close()
                target.unlink(missing_ok=True)
                raise BizError(
                    code=400,
                    message=f"文件过大，上限 {_AVATAR_MAX_SIZE // 1024 // 1024}MB",
                )
            await asyncio.to_thread(fp.write, chunk)

    # 返回相对路径：前端拼接 baseUrl 后即可访问
    # 不返回绝对 URL：baseUrl 由前端 discovery 决定（开发态/正式态不同），
    # 后端不感知前端实际访问域名，返回相对路径让前端拼接最稳健
    return success(data={"url": f"/avatars/{filename}"})
