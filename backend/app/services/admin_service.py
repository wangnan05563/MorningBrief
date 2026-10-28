"""B 端运营服务：登录、改密、后台账号管理。"""
import re
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError
from app.core.security import (
    MIN_ADMIN_PASSWORD_LEN,
    create_access_token,
    hash_password,
    verify_password,
)
from app.core.timeutil import localnow_naive
from app.models import AdminUser
from app.models.admin_user import AdminRole
from app.services.blacklist_service import add_to_blacklist

# 账号名口径与参考实现一致：3-32 位字母/数字/下划线
ADMIN_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")
# bcrypt 只取前 72 字节，超长口令会静默截断；上限按参考实现定在 64
MAX_ADMIN_PASSWORD_LEN = 64
_ADMIN_ROLES = {r.value for r in AdminRole}


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

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
                "role": admin.role,
            },
        )

        admin.last_login_at = localnow_naive()
        await self.db.commit()

        return {
            "token": token,
            "role": admin.role,
            "username": admin.username,
        }

    async def logout(self, jti: str, exp: int, admin_id: int) -> None:
        """登出：把 jti 写入黑名单（SQLite + COS 双写），TTL 与 JWT 剩余有效期一致。

        V1.2 起黑名单改为 SQLite + COS 双写：
        - SQLite：B 端验签本地查询（带内存缓存 TTL 5 分钟）
        - COS：C 端 SCF 共享读取（jwt_blacklist/{jti}.json）
        """
        now = int(datetime.now(timezone.utc).timestamp())
        remaining_ttl = exp - now
        # token 已过期则无需写黑名单，避免 SQLite/COS 残留无意义记录
        if remaining_ttl <= 0:
            return
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
        await add_to_blacklist(jti, "admin", admin_id, expires_at, remaining_ttl)

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

        # 长度口径与路由层 schema 同源：直接调服务方法的调用方也不会绕过
        if len(new_pwd or "") < MIN_ADMIN_PASSWORD_LEN:
            raise BizError(
                code=400,
                message=f"新密码至少 {MIN_ADMIN_PASSWORD_LEN} 位",
            )

        admin.password_hash = hash_password(new_pwd)
        await self.db.commit()

    # ===== 后台账号管理（T03439）=====

    async def list_admins(
        self,
        *,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> dict:
        """分页检索后台账号；只返回安全字段，不出密码哈希。"""
        page = max(1, int(page or 1))
        size = max(1, min(int(size or 20), 100))

        conds = []
        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            conds.append(or_(
                AdminUser.username.ilike(kw),
                AdminUser.nickname.ilike(kw),
            ))

        count_stmt = select(func.count(AdminUser.id))
        list_stmt = select(AdminUser)
        if conds:
            count_stmt = count_stmt.where(*conds)
            list_stmt = list_stmt.where(*conds)

        total = (await self.db.execute(count_stmt)).scalar_one()
        rows = (
            (
                await self.db.execute(
                    list_stmt.order_by(AdminUser.id.asc())
                    .offset((page - 1) * size)
                    .limit(size)
                )
            )
            .scalars()
            .all()
        )
        return {
            "list": [self.serialize(row) for row in rows],
            "total": int(total or 0),
            "page": page,
            "size": size,
        }

    async def create_admin(
        self,
        *,
        username: str,
        password: str,
        role: str = AdminRole.operator.value,
        nickname: str | None = None,
    ) -> AdminUser:
        name = (username or "").strip()
        if not ADMIN_USERNAME_PATTERN.match(name):
            raise BizError(
                code=400,
                message="用户名需为 3-32 位字母、数字或下划线",
            )
        self._validate_password(password)
        if role not in _ADMIN_ROLES:
            raise BizError(code=400, message="角色仅支持管理员或运营")

        existing = (
            await self.db.execute(
                select(AdminUser.id).where(AdminUser.username == name)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise BizError(code=400, message="用户名已存在")

        row = AdminUser(
            username=name,
            password_hash=hash_password(password),
            role=role,
            nickname=(nickname or "").strip() or None,
            status=1,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_admin(
        self,
        *,
        actor_id: int,
        admin_id: int,
        role: str | None = None,
        nickname: str | None = None,
        status: int | None = None,
        password: str | None = None,
    ) -> AdminUser:
        """编辑账号；自我降级/禁用/改密一律拒绝，避免把自己锁在门外。"""
        admin = await self._get_admin(admin_id)

        if role is not None:
            if role not in _ADMIN_ROLES:
                raise BizError(code=400, message="角色仅支持管理员或运营")
            if admin.id == actor_id and role != admin.role:
                raise BizError(code=400, message="不能修改自己的角色")
            if (
                admin.role == AdminRole.admin.value
                and role != AdminRole.admin.value
                and admin.status == 1
                and await self._other_active_admins(admin.id) == 0
            ):
                raise BizError(code=400, message="至少保留一个启用状态的管理员")
            admin.role = role

        if nickname is not None:
            admin.nickname = nickname.strip() or None

        if status is not None:
            if status not in (0, 1):
                raise BizError(code=400, message="状态仅支持 0 / 1")
            if status == 0 and admin.id == actor_id:
                raise BizError(code=400, message="不能禁用当前登录的账号")
            if (
                status == 0
                and admin.role == AdminRole.admin.value
                and admin.status == 1
                and await self._other_active_admins(admin.id) == 0
            ):
                raise BizError(code=400, message="至少保留一个启用状态的管理员")
            admin.status = status

        if password is not None:
            if admin.id == actor_id:
                raise BizError(
                    code=400,
                    message="请在右上角「修改密码」中修改自己的登录口令",
                )
            self._validate_password(password)
            admin.password_hash = hash_password(password)

        await self.db.commit()
        await self.db.refresh(admin)
        return admin

    async def delete_admin(self, *, actor_id: int, admin_id: int) -> AdminUser:
        admin = await self._get_admin(admin_id)
        if admin.id == actor_id:
            raise BizError(code=400, message="不能删除当前登录的账号")
        if (
            admin.role == AdminRole.admin.value
            and admin.status == 1
            and await self._other_active_admins(admin.id) == 0
        ):
            raise BizError(code=400, message="至少保留一个启用状态的管理员")

        await self.db.delete(admin)
        await self.db.commit()
        return admin

    async def _get_admin(self, admin_id: int) -> AdminUser:
        admin = (
            await self.db.execute(
                select(AdminUser).where(AdminUser.id == admin_id)
            )
        ).scalar_one_or_none()
        if admin is None:
            raise BizError(code=404, message="账号不存在")
        return admin

    async def _other_active_admins(self, exclude_id: int) -> int:
        """除指定账号外，仍处于启用状态的管理员数量。"""
        return (
            await self.db.execute(
                select(func.count(AdminUser.id)).where(
                    AdminUser.id != exclude_id,
                    AdminUser.role == AdminRole.admin.value,
                    AdminUser.status == 1,
                )
            )
        ).scalar_one()

    @staticmethod
    def _validate_password(password: str | None) -> None:
        length = len(password or "")
        if length < MIN_ADMIN_PASSWORD_LEN or length > MAX_ADMIN_PASSWORD_LEN:
            raise BizError(
                code=400,
                message=(
                    f"密码长度需为 {MIN_ADMIN_PASSWORD_LEN}-"
                    f"{MAX_ADMIN_PASSWORD_LEN} 位"
                ),
            )

    @staticmethod
    def serialize(admin: AdminUser) -> dict:
        """安全视图：不含 password_hash。"""
        return {
            "id": admin.id,
            "username": admin.username,
            "nickname": admin.nickname,
            "role": admin.role,
            "status": admin.status,
            "last_login_at": (
                admin.last_login_at.isoformat() if admin.last_login_at else None
            ),
            "created_at": (
                admin.created_at.isoformat() if admin.created_at else None
            ),
            "updated_at": (
                admin.updated_at.isoformat() if admin.updated_at else None
            ),
        }
