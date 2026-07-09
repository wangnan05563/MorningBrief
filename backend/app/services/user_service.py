"""用户服务：微信登录、登出、用户信息。"""
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import create_access_token
from app.core.exceptions import BizError, AuthError
from app.models import User
from app.services.blacklist_service import add_to_blacklist

settings = get_settings()


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # V1.2 起 Redis 移除，黑名单改用 blacklist_service 全局服务（SQLite + COS 双写）

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
        token, _jti, expires_in = create_access_token(
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

    async def logout(self, jti: str, exp: int, user_id: int) -> None:
        """登出：把 jti 写入黑名单（SQLite + COS 双写），TTL 与 JWT 剩余有效期一致。

        V1.2 改造：新增 user_id 参数，供新 add_to_blacklist 写入关联用户与过期时间。
        """
        now = int(datetime.now(timezone.utc).timestamp())
        remaining_ttl = exp - now
        # token 已过期则无需写黑名单，避免无意义记录残留
        if remaining_ttl <= 0:
            return
        # expires_at 从 JWT exp 还原，供 SQLite/COS 按过期时间清理
        # SQLite DateTime 不存时区，统一用 naive UTC 与 blacklist_service 一致
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
        await add_to_blacklist(jti, "user", user_id, expires_at, remaining_ttl)

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
