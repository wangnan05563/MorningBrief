"""个人数据自助删除（T02788 / J98，裁决见 MTask T02788）。

身份在库里不是一个键：`favorite` / `comment` / `comment_like` / `subscription`
存 openid，`play_log` / `play_progress` / `channel_subscription` 存 `User.id`。
只按 openid 删会把播放记录、播放进度、频道订阅整片留下——现场库取证
（`_validate/news2/T02788_run/`）显示这三张表 8/13/21 行全部挂在数字 id 上。
所以这里一律**双键并删**，且删除后按 openid 与 `User.id` 各自 count(*)=0 验收。

收藏与播放进度还是 DB + COS 双写（`favorites/{openid}/index.json`、
`play_progress/{user_id}/{episode_id}.json`）：只删库等于把用户数据完整留在
对象存储里。COS 清理放在**数据库提交之后**，失败只告警不回滚——否则会出现
「库已删、接口 500、用户以为没删」的二义状态，重试还会把一个不可逆操作
做成半途而废。

留痕只保留计数与 openid 的不可逆摘要：审计要能自证「删过、删了几条」，
但没有理由把 openid 明文再复制一份（与 T02591 的明文清洗方向一致）。
"""
import hashlib
import json
import logging

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cos.client import is_cos_configured
from app.models import (
    AuditLog,
    ChannelSubscription,
    Comment,
    CommentLike,
    Favorite,
    PlayLog,
    PlayProgress,
    Subscription,
    User,
)
from app.services.cos_storage_service import CosStorageService

logger = logging.getLogger(__name__)

# 审计里的 openid 摘要长度：12 位十六进制，足够在同一份审计里区分不同用户，
# 又不构成可反查的明文标识。
OPENID_DIGEST_LEN = 12

AUDIT_CATEGORY = "user"
AUDIT_ACTION = "user_data_purge"
AUDIT_OPERATOR = "小程序用户自助"

# COS 镜像前缀，与 play_service / favorite 模型注释里的写入路径保持一致
FAVORITES_COS_PREFIX = "favorites"
PLAY_PROGRESS_COS_PREFIX = "play_progress"


def openid_digest(openid: str) -> str:
    """openid 的不可逆摘要（审计 target 用）。"""
    return hashlib.sha256((openid or "").encode("utf-8")).hexdigest()[:OPENID_DIGEST_LEN]


def retention_policy() -> dict:
    """备份保留口径，供隐私文案直接引用真实配置而非写死数字。

    删除只作用于当前库：每日备份与 COS 备份仍会保留该用户数据直到过期，
    所以第七条不能承诺「立即彻底删除」。数字取自配置与备份服务的常量，
    保留策略一旦调整，文案跟着变，不会变成第二处谎言。
    """
    from app.config import get_settings
    from app.services import backup_service

    return {
        "db_backup_keep_days": backup_service._DEFAULT_KEEP_DAYS,
        "db_backup_keep_files": backup_service._MAX_KEEP_FILES,
        "cos_backup_keep_count": get_settings().COS_BACKUP_KEEP_COUNT,
    }


async def _count(db: AsyncSession, model, *conds) -> int:
    result = await db.execute(select(func.count(model.id)).where(*conds))
    return int(result.scalar() or 0)


class AccountPurgeService:
    """C 端「删除我的数据」：预览计数 + 双键清除 + 云端镜像清理。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 预览 ----

    async def summarize(self, user_id: int, openid: str) -> dict:
        """确认框要显示的「影响条数」：与 purge 实际删除口径逐表对齐。

        点赞数把两类都算上——我点出去的赞，以及我的评论收到的赞：
        后者随评论一起消失，漏算会让确认框少报条数。
        """
        my_comment_ids = (
            await self.db.execute(select(Comment.id).where(Comment.user_id == openid))
        ).scalars().all()
        liked = await _count(self.db, CommentLike, CommentLike.user_id == openid)
        received = 0
        if my_comment_ids:
            received = await _count(
                self.db, CommentLike, CommentLike.comment_id.in_(my_comment_ids)
            )

        counts = {
            "favorite": await _count(self.db, Favorite, Favorite.user_id == openid),
            "comment": len(my_comment_ids),
            "comment_like": liked + received,
            "play_log": await _count(self.db, PlayLog, PlayLog.user_id == user_id),
            "play_progress": await _count(
                self.db, PlayProgress, PlayProgress.user_id == user_id
            ),
            "channel_subscription": await _count(
                self.db, ChannelSubscription, ChannelSubscription.user_id == user_id
            ),
            "subscription": await _count(
                self.db,
                Subscription,
                or_(Subscription.user_id == user_id, Subscription.openid == openid),
            ),
            # 账号本身也是一行：不写进预览，确认框报的总数就会比实际少 1
            "user": await _count(self.db, User, User.id == user_id),
        }
        counts["total"] = sum(counts.values())
        return counts

    # ---- 清除 ----

    async def purge(self, user_id: int, openid: str) -> dict:
        """按双键删除个人数据，返回各表删除行数。调用方负责事务边界。

        顺序有讲究：先删别人的评论所依赖的点赞行、再删我的评论，
        最后才删 user 行——`play_log.user_id` 是指向 `user.id` 的外键，
        先删记录再删主表，FK 打开时也不会中途失败。
        """
        my_comment_ids = (
            await self.db.execute(select(Comment.id).where(Comment.user_id == openid))
        ).scalars().all()
        # 我点过赞的评论：删完后这些评论的 like_count 会与真实点赞数不符，必须重算
        liked_comment_ids = (
            await self.db.execute(
                select(CommentLike.comment_id).where(CommentLike.user_id == openid)
            )
        ).scalars().all()

        counts = {}
        counts["favorite"] = await self._delete(Favorite, Favorite.user_id == openid)
        counts["comment_like"] = await self._delete(
            CommentLike, CommentLike.user_id == openid
        )
        if my_comment_ids:
            # 我的评论收到的赞：评论本体要删，这些指向它的点赞行不能留成悬空引用
            counts["comment_like"] += await self._delete(
                CommentLike, CommentLike.comment_id.in_(my_comment_ids)
            )
        counts["comment"] = await self._delete(Comment, Comment.user_id == openid)
        counts["play_log"] = await self._delete(PlayLog, PlayLog.user_id == user_id)
        counts["play_progress"] = await self._delete(
            PlayProgress, PlayProgress.user_id == user_id
        )
        counts["channel_subscription"] = await self._delete(
            ChannelSubscription, ChannelSubscription.user_id == user_id
        )
        counts["subscription"] = await self._delete(
            Subscription,
            or_(Subscription.user_id == user_id, Subscription.openid == openid),
        )
        await self._recount_like_counts(liked_comment_ids)
        counts["user"] = await self._delete(User, User.id == user_id)
        return counts

    async def purge_cos(self, user_id: int, openid: str) -> dict:
        """删除云端镜像前缀（DB 已提交后调用，best-effort）。

        返回每类前缀的实际删除对象数；未配置 COS 时返回 skipped，
        让调用方能在响应里如实告诉前端「云端没动」而不是假装删了。
        """
        if not is_cos_configured():
            return {"skipped": "COS 未配置"}

        svc = CosStorageService()
        targets = (
            ("favorites", f"{FAVORITES_COS_PREFIX}/{openid}/"),
            ("play_progress", f"{PLAY_PROGRESS_COS_PREFIX}/{user_id}/"),
        )
        result = {}
        for label, prefix in targets:
            try:
                result[label] = await svc.delete_folder(prefix)
            except Exception as exc:  # COS 抖动不该让已提交的删除看起来失败
                logger.warning(
                    "[account.purge] COS 前缀删除失败 prefix=%s: %s", prefix, exc
                )
                result[label] = f"failed: {type(exc).__name__}"
        return result

    def add_audit(self, openid: str, counts: dict) -> None:
        """写计数型审计：只留各表删除行数 + openid 摘要，不记任何内容正文。"""
        detail = {k: v for k, v in counts.items() if v}
        self.db.add(
            AuditLog(
                category=AUDIT_CATEGORY,
                action=AUDIT_ACTION,
                target=openid_digest(openid),
                operator=AUDIT_OPERATOR,
                detail=json.dumps(detail, ensure_ascii=False),
            )
        )

    # ---- 内部 ----

    async def _delete(self, model, *conds) -> int:
        result = await self.db.execute(delete(model).where(*conds))
        return int(result.rowcount or 0)

    async def _recount_like_counts(self, comment_ids) -> None:
        """按剩余点赞关系重算 `comment.like_count`。

        like_count 是冗余列，删点赞行不会自动减——不重算的话，被删用户点过的
        评论会永远显示一个虚高的赞数，而且没有任何后续动作会纠正它。
        只处理仍在库里的评论：我的评论已经在本方法之前删掉了。
        """
        ids = sorted({int(cid) for cid in comment_ids})
        if not ids:
            return
        survivors = (
            await self.db.execute(select(Comment.id).where(Comment.id.in_(ids)))
        ).scalars().all()
        if not survivors:
            return
        remaining = (
            select(func.count(CommentLike.id))
            .where(CommentLike.comment_id == Comment.id)
            .scalar_subquery()
        )
        await self.db.execute(
            update(Comment)
            .where(Comment.id.in_(survivors))
            .values(like_count=remaining)
        )
