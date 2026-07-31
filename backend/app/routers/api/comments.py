"""C 端评论路由（任务8）。

设计原因：
- Comment 表 user_id 用 openid 字符串，与 Favorite 对齐，便于 SCF/COS 异地容灾
- 点赞通过 CommentLike 关系表保证幂等：重复点赞不会增加计数
- 评论列表默认按 created_at 倒序（最新在前）
- 评论查询不强制鉴权，未登录用户也能查看；发布/点赞需登录
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user, get_optional_user
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.database import get_db
from app.models import Comment, CommentLike, Episode, EpisodeStatus, User
from app.services.user_service import get_user_openid

router = APIRouter(prefix="/api/v1/comments", tags=["C端-评论"])


class CommentRequest(BaseModel):
    """发布评论请求体。

    user_name/user_avatar 为可选：前端可在发布时附带当前登录用户的微信头像昵称，
    后端优先用前端值、否则从 User 表读取。这样 User 表尚未更新时评论也不会显示"匿名听众"。
    """
    episode_id: int
    content: str = Field(..., min_length=1, max_length=200)
    user_name: str | None = Field(None, max_length=64, description="前端附带的昵称（可选）")
    user_avatar: str | None = Field(None, max_length=512, description="前端附带的头像 URL（可选）")


async def _get_user_profile(db: AsyncSession, user_id: int) -> tuple[str, str, str]:
    """根据 User.id 查询 openid + nickname + avatar，避免多次往返。

    返回三元组（openid, nickname, avatar），nickname 缺省回退为"匿名听众"。
    """
    result = await db.execute(
        select(User.openid, User.nickname, User.avatar).where(User.id == user_id)
    )
    row = result.first()
    if row is None:
        raise NotFoundError("用户不存在")
    return row[0], row[1] or "匿名听众", row[2] or ""


@router.get("")
async def list_comments(
    episode_id: int = Query(..., description="节目 ID"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user: UserPayload | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """评论列表：按节目过滤，默认按时间倒序。

    未登录也能查看，已登录时返回 liked 字段标识当前用户是否点赞。
    """
    # 总数
    count_stmt = select(func.count(Comment.id)).where(Comment.episode_id == episode_id)
    total = (await db.execute(count_stmt)).scalar() or 0

    # 当前用户的 openid（用于查 liked 状态）
    user_openid = None
    if user is not None:
        user_openid = await get_user_openid(db, user.user_id)

    offset = (page - 1) * size
    list_stmt = (
        select(Comment)
        .where(Comment.episode_id == episode_id)
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(list_stmt)
    comments = result.scalars().all()

    # 批量查当前用户对这些评论的点赞关系，避免 N+1
    liked_set: set[int] = set()
    if user_openid is not None and comments:
        ids = [c.id for c in comments]
        like_result = await db.execute(
            select(CommentLike.comment_id).where(
                CommentLike.user_id == user_openid,
                CommentLike.comment_id.in_(ids),
            )
        )
        liked_set = {row[0] for row in like_result.all()}

    # 任务5+6：批量从 User 表覆盖评论作者的头像昵称
    # Comment.user_name/user_avatar 在发布时已固化，User 表更新后旧评论不会自动刷新
    # 这里用 User 表的当前值覆盖，让"用户登录后写回 User 表"对历史评论也立即生效
    profile_map: dict[str, tuple[str | None, str | None]] = {}
    if comments:
        openids = {c.user_id for c in comments}
        user_result = await db.execute(
            select(User.openid, User.nickname, User.avatar).where(User.openid.in_(openids))
        )
        profile_map = {row[0]: (row[1], row[2]) for row in user_result.all()}

    list_data = [
        {
            "id": c.id,
            "episode_id": c.episode_id,
            "user_id": c.user_id,
            # User 表有头像昵称时优先用 User 表的（覆盖 Comment 旧值），否则 fallback 到 Comment 自身的字段
            "user_name": (profile_map.get(c.user_id, (None, None))[0]) or c.user_name or "匿名听众",
            "user_avatar": (profile_map.get(c.user_id, (None, None))[1]) or c.user_avatar or "",
            "content": c.content,
            "like_count": c.like_count,
            "liked": c.id in liked_set,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else None,
        }
        for c in comments
    ]
    return success(data={"total": total, "list": list_data})


@router.post("")
async def create_comment(
    req: CommentRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发布评论：需登录。

    头像昵称优先级：前端附带 > User 表 > 默认"匿名听众"。
    前端附带是双保险：解决"用户从 onLaunch 静默登录后直接进 detail 页发评论"，
    此时 User 表还没被 silentEnrichProfile 写回，user_name/user_avatar 是空。
    """
    openid, db_nickname, db_avatar = await _get_user_profile(db, user.user_id)

    # 校验节目存在
    ep_result = await db.execute(
        select(Episode.id).where(
            Episode.id == req.episode_id,
            Episode.status == EpisodeStatus.published,
        )
    )
    if ep_result.scalar_one_or_none() is None:
        raise NotFoundError("节目不存在或未发布")

    # 头像昵称优先级：前端附带 > User 表 > 默认
    final_name = (req.user_name or "").strip() or db_nickname or "匿名听众"
    final_avatar = (req.user_avatar or "").strip() or db_avatar or ""

    new_comment = Comment(
        user_id=openid,
        user_name=final_name,
        user_avatar=final_avatar,
        episode_id=req.episode_id,
        content=req.content,
        like_count=0,
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    return success(data={
        "id": new_comment.id,
        "episode_id": new_comment.episode_id,
        "user_name": new_comment.user_name,
        "user_avatar": new_comment.user_avatar,
        "content": new_comment.content,
        "like_count": new_comment.like_count,
        "created_at": new_comment.created_at.strftime("%Y-%m-%d %H:%M") if new_comment.created_at else None,
    })


@router.post("/{comment_id}/like")
async def like_comment(
    comment_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """点赞评论：幂等，已点赞则直接返回成功。"""
    openid = await get_user_openid(db, user.user_id)

    # 校验评论存在
    comment = (
        await db.execute(select(Comment).where(Comment.id == comment_id))
    ).scalar_one_or_none()
    if comment is None:
        raise NotFoundError("评论不存在")

    # 幂等检查：已点赞则直接返回
    existing = (
        await db.execute(
            select(CommentLike.id).where(
                CommentLike.user_id == openid,
                CommentLike.comment_id == comment_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return success(data={"liked": True, "like_count": comment.like_count})

    # 新增点赞记录 + 计数 +1
    db.add(CommentLike(user_id=openid, comment_id=comment_id))
    comment.like_count = (comment.like_count or 0) + 1
    await db.commit()
    return success(data={"liked": True, "like_count": comment.like_count})


@router.delete("/{comment_id}/like")
async def unlike_comment(
    comment_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消点赞：幂等，未点赞也返回成功。"""
    openid = await get_user_openid(db, user.user_id)

    comment = (
        await db.execute(select(Comment).where(Comment.id == comment_id))
    ).scalar_one_or_none()
    if comment is None:
        raise NotFoundError("评论不存在")

    # 删除点赞记录（无论是否存在都执行，DELETE 幂等）
    result = await db.execute(
        delete(CommentLike).where(
            CommentLike.user_id == openid,
            CommentLike.comment_id == comment_id,
        )
    )
    # rowcount > 0 表示实际删除了记录，才需要减计数
    if result.rowcount and (comment.like_count or 0) > 0:
        comment.like_count = comment.like_count - 1
        await db.commit()
    return success(data={"liked": False, "like_count": comment.like_count})
