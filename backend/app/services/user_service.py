"""用户服务：微信登录、登出、用户信息。"""
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import create_access_token
from app.core.exceptions import BizError, AuthError
from app.models import User
from app.redis_client import redis_client, user_blacklist_key, add_to_blacklist

settings = get_settings()


class UserService:
    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis or redis_client

    async def login_by_code(self, code: str) -> dict:
        """微信 code 换 openid 登录，不存在则新建用户。"""
        if not code:
            raise BizError(code=400, message="code 不能为空")

        # 小程序登录态由微信签发，必须回源校验 code 有效性
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": settings.WX_APPID,
                    "secret": settings.WX_SECRET,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
            data = resp.json()

        # 微信接口错误返回 errcode，0 才是成功
        if data.get("errcode", 0) != 0:
            raise BizError(
                code=400, message=f"微信登录失败: {data.get('errmsg', '')}"
            )

        openid = data["openid"]
        unionid = data.get("unionid")

        # 按 openid 查用户，不存在则新建（首次登录即注册）
        result = await self.db.execute(select(User).where(User.openid == openid))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(openid=openid, unionid=unionid)
            self.db.add(user)
            await self.db.flush()
        elif unionid and not user.unionid:
            # 之前缺失的 unionid 现在补全
            user.unionid = unionid

        # subject 用 user_id 字符串，token_type=user 标识 C 端 token
        token, jti, expires_in = create_access_token(
            str(user.id), token_type="user"
        )

        await self.db.commit()

        return {
            "token": token,
            "expires_in": expires_in,
            "user": {
                "openid": user.openid,
                "nickname": user.nickname,
                "avatar": user.avatar,
            },
        }

    async def logout(self, jti: str, exp: int) -> None:
        """登出：把 jti 写入 Redis 黑名单，TTL 与 JWT 剩余有效期一致。"""
        now = int(datetime.now(timezone.utc).timestamp())
        remaining_ttl = exp - now
        # token 已过期则无需写黑名单，避免 Redis 残留无意义 Key
        if remaining_ttl <= 0:
            return
        await add_to_blacklist(user_blacklist_key(jti), remaining_ttl)

    async def get_user_info(self, user_id: int) -> dict:
        """获取用户信息：累计收听时长、期数。"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise AuthError("用户不存在")
        return {
            "user_id": user.id,
            "openid": user.openid,
            "nickname": user.nickname,
            "avatar": user.avatar,
            "total_listen_duration": user.total_listen_duration or 0,
            "total_listen_count": user.total_listen_count or 0,
        }
