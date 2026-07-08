"""B 端运营服务：登录、改密。"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError
from app.core.security import create_access_token, verify_password, hash_password
from app.models import AdminUser
from app.redis_client import redis_client


class AdminService:
    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis or redis_client

    async def login(self, username: str, password: str) -> dict:
        """账号密码登录，校验通过后签发 B 端 JWT。"""
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        admin = result.scalar_one_or_none()

        # 用户名与密码错误统一返回同一文案，避免账号枚举
        if admin is None or not verify_password(password, admin.password_hash):
            raise BizError(code=401, message="用户名或密码错误")

        # status=0 表示禁用，阻止已离职账号继续使用
        if admin.status == 0:
            raise BizError(code=403, message="账号已禁用")

        # subject 用 admin_id 字符串，type=admin 区分 B 端 token；
        # role/username 写入 claims 供鉴权层直接读取，免去二次查库
        token, _jti, _expires_in = create_access_token(
            str(admin.id),
            token_type="admin",
            extra_claims={
                "username": admin.username,
                "role": admin.role.value,
            },
        )

        admin.last_login_at = datetime.now()
        await self.db.commit()

        return {
            "token": token,
            "role": admin.role.value,
            "username": admin.username,
        }

    async def change_password(
        self, admin_id: int, old_pwd: str, new_pwd: str
    ) -> None:
        """修改密码：先校验旧密码，再写入新哈希。"""
        result = await self.db.execute(
            select(AdminUser).where(AdminUser.id == admin_id)
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            raise BizError(code=404, message="账号不存在")

        if not verify_password(old_pwd, admin.password_hash):
            raise BizError(code=400, message="原密码错误")

        admin.password_hash = hash_password(new_pwd)
        await self.db.commit()
