"""
鉴权依赖：C 端用户 / B 端运营

校验流程（HLD V1.4 10.1）：
1. 从 Authorization 头提取 Bearer token
2. JWT 本地验签
3. 查 Redis 黑名单（仅 jti 命中才拒绝）
4. 返回用户信息

用法：
    @router.get("/me", dependencies=[Depends(require_user)])
    @router.get("/info", dependencies=[Depends(require_admin)])
    async def me(user: UserPayload = Depends(get_current_user)):
"""
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, Header

from app.core.exceptions import AuthError, PermissionError
from app.core.security import decode_token
from app.redis_client import admin_blacklist_key, is_in_blacklist, user_blacklist_key


@dataclass
class UserPayload:
    """C 端用户信息（从 JWT 解析）。"""
    user_id: int
    jti: str
    token_type: str


@dataclass
class AdminPayload:
    """B 端运营信息（从 JWT 解析）。"""
    admin_id: int
    username: str
    role: str
    jti: str
    token_type: str


def _extract_token(authorization: Optional[str]) -> str:
    """从 Authorization 头提取 Bearer token。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("缺少认证信息")
    return authorization.removeprefix("Bearer ").strip()


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserPayload:
    """C 端鉴权依赖。"""
    token = _extract_token(authorization)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise AuthError("无效的认证信息")

    # 仅接受 C 端 token
    if payload.get("type") != "user":
        raise AuthError("认证类型错误")

    jti = payload.get("jti", "")
    if await is_in_blacklist(user_blacklist_key(jti)):
        raise AuthError("登录已失效，请重新登录")

    return UserPayload(
        user_id=int(payload["sub"]),
        jti=jti,
        token_type=payload["type"],
    )


async def get_current_admin(authorization: Optional[str] = Header(None)) -> AdminPayload:
    """B 端鉴权依赖。"""
    token = _extract_token(authorization)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise AuthError("无效的认证信息")

    # 仅接受 B 端 token
    if payload.get("type") != "admin":
        raise AuthError("认证类型错误")

    jti = payload.get("jti", "")
    if await is_in_blacklist(admin_blacklist_key(jti)):
        raise AuthError("登录已失效，请重新登录")

    return AdminPayload(
        admin_id=int(payload["sub"]),
        username=payload.get("username", ""),
        role=payload.get("role", "operator"),
        jti=jti,
        token_type=payload["type"],
    )


async def require_admin(admin: AdminPayload = Depends(get_current_admin)) -> AdminPayload:
    """要求 admin 角色（工作流操作、用户管理等高权限接口）。"""
    if admin.role != "admin":
        raise PermissionError("需要管理员权限")
    return admin


# 便捷别名
require_user = get_current_user
require_operator = get_current_admin  # operator + admin 均可访问
