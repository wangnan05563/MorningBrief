"""
鉴权依赖：C 端用户 / B 端运营

校验流程（HLD V1.6 10.1）：
1. 从 Authorization 头提取 Bearer token
2. JWT 本地验签
3. 查 SQLite 黑名单（仅 jti 命中才拒绝；B 端本地查询，带内存缓存）
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

from app.core.exceptions import AuthError, BizPermissionError
from app.core.security import decode_token
from app.services.blacklist_service import is_in_blacklist


@dataclass
class UserPayload:
    """C 端用户信息（从 JWT 解析）。"""
    user_id: int
    jti: str
    token_type: str
    exp: int = 0


@dataclass
class AdminPayload:
    """B 端运营信息（从 JWT 解析）。"""
    admin_id: int
    username: str
    role: str
    jti: str
    token_type: str
    exp: int = 0


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization 头提取 Bearer token，无 token 时返回 None。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip()


def _extract_token_strict(authorization: Optional[str]) -> str:
    """从 Authorization 头提取 Bearer token，无 token 时抛出 AuthError。"""
    token = _extract_token(authorization)
    if token is None:
        raise AuthError("缺少认证信息")
    return token


async def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[UserPayload]:
    """可选鉴权依赖：有 token 则校验返回，无 token 返回 None。"""
    token = _extract_token(authorization)
    if token is None:
        return None
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "user":
        return None

    jti = payload.get("jti", "")
    if await is_in_blacklist(jti):
        return None

    return UserPayload(
        user_id=int(payload["sub"]),
        jti=jti,
        token_type=payload["type"],
        exp=int(payload.get("exp", 0)),
    )


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserPayload:
    """C 端鉴权依赖。"""
    token = _extract_token_strict(authorization)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise AuthError("无效的认证信息")

    if payload.get("type") != "user":
        raise AuthError("认证类型错误")

    jti = payload.get("jti", "")
    if await is_in_blacklist(jti):
        raise AuthError("登录已失效，请重新登录")

    return UserPayload(
        user_id=int(payload["sub"]),
        jti=jti,
        token_type=payload["type"],
        exp=int(payload.get("exp", 0)),
    )


async def get_current_admin(authorization: Optional[str] = Header(None)) -> AdminPayload:
    """B 端鉴权依赖。"""
    token = _extract_token_strict(authorization)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise AuthError("无效的认证信息")

    if payload.get("type") != "admin":
        raise AuthError("认证类型错误")

    jti = payload.get("jti", "")
    if await is_in_blacklist(jti):
        raise AuthError("登录已失效，请重新登录")

    return AdminPayload(
        admin_id=int(payload["sub"]),
        username=payload.get("username", ""),
        role=payload.get("role", "operator"),
        jti=jti,
        token_type=payload["type"],
        exp=int(payload.get("exp", 0)),
    )


async def require_admin(admin: AdminPayload = Depends(get_current_admin)) -> AdminPayload:  # NOSONAR
    """要求 admin 角色（工作流操作、用户管理等高权限接口）。"""
    if admin.role != "admin":
        raise BizPermissionError("需要管理员权限")
    return admin


# 便捷别名
require_user = get_current_user
require_operator = get_current_admin
