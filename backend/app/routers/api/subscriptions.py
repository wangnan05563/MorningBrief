"""C 端订阅路由：含订阅消息授权记录 + 频道订阅/取消订阅。

设计原因：
- 订阅消息（wx.requestSubscribeMessage）与频道订阅是两个独立概念：
  · 订阅消息：一次性授权，每授权一次仅能推送一条模板消息
  · 频道订阅：长期关注关系，用于首页优先展示已订阅频道
- 两者复用 /subscriptions 前缀，但子路径不同：/subscriptions/message 与 /subscriptions/channels/{id}
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserPayload, get_current_user
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.core.write_gate import write_lock
from app.core.timeutil import localnow_naive
from app.database import get_db
from app.models import Subscription, ChannelSubscription, Channel, User

router = APIRouter(prefix="/api/v1/subscriptions", tags=["C端-订阅"])


class MessageSubscriptionRequest(BaseModel):
    """订阅消息授权记录请求体。"""
    # 微信模板 ID 长度约 40 字符，加 128 上限防止异常长字符串入库
    template_id: str = Field(..., min_length=1, max_length=128, description="微信订阅消息模板 ID")


@router.post("/message")
async def record_message_subscription(
    req: MessageSubscriptionRequest,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录用户订阅消息授权：每次 wx.requestSubscribeMessage 成功后调用一次。

    工作流发布成功后，订阅消息推送服务查询 used=0 的记录进行推送。
    """
    # 查询用户 openid，推送时需要
    user_result = await db.execute(select(User.openid).where(User.id == user.user_id))
    openid = user_result.scalar_one_or_none()
    if openid is None:
        raise BizError(code=1002, message="用户不存在")

    sub = Subscription(
        user_id=user.user_id,
        template_id=req.template_id,
        openid=openid,
        subscribed_at=localnow_naive(),
        used=0,
    )
    async with write_lock():
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

    return success(data={"success": True, "subscription_id": sub.id})


@router.post("/channels/{channel_id}")
async def subscribe_channel(
    channel_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """订阅频道：幂等，已订阅则直接返回成功。"""
    # 校验频道存在且启用
    ch_result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.is_active == 1)
    )
    if ch_result.scalar_one_or_none() is None:
        raise NotFoundError("频道不存在或已停用")

    # 幂等检查 + 插入必须在同一把全局写锁内：否则并发订阅会同时通过检查、
    # 先后插入触发 channel_subscription UNIQUE 冲突 → 500（压测实测 4-5% 写错误）。
    # 锁内先查后插，保证任一时刻只有一个事务能插入该 (user,channel) 组合。
    new_sub = ChannelSubscription(
        user_id=user.user_id,
        channel_id=channel_id,
        created_at=localnow_naive(),
    )
    async with write_lock():
        existing = await db.execute(
            select(ChannelSubscription).where(
                ChannelSubscription.user_id == user.user_id,
                ChannelSubscription.channel_id == channel_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return success(data={"success": True, "already_subscribed": True})
        db.add(new_sub)
        await db.commit()

    return success(data={"success": True, "already_subscribed": False})


@router.delete("/channels/{channel_id}")
async def unsubscribe_channel(
    channel_id: int,
    user: UserPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消订阅频道：幂等，不存在也返回成功。"""
    async with write_lock():
        await db.execute(
            delete(ChannelSubscription).where(
                ChannelSubscription.user_id == user.user_id,
                ChannelSubscription.channel_id == channel_id,
            )
        )
        await db.commit()
    return success(data={"success": True})
