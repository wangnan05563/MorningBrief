"""
安全工具：JWT 生成/验证 + bcrypt 密码哈希

JWT 设计：无状态本地验签（性能优），仅登出/强制下线时写 Redis 黑名单。
- payload 含 jti（唯一 ID），便于黑名单定位
- C 端有效期 7 天，B 端有效期 2 小时
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from app.config import get_settings

settings = get_settings()


# ---- JWT ----

def create_access_token(
    subject: str,
    *,
    token_type: str = "user",   # "user" | "admin"
    extra_claims: Optional[dict] = None,
) -> tuple[str, str, int]:
    """
    生成 JWT。

    返回 (token, jti, expires_in_seconds)。
    jti 用于登出时写入 Redis 黑名单。
    """
    now = datetime.now(timezone.utc)

    if token_type == "admin":
        expires_delta = timedelta(hours=settings.JWT_ADMIN_EXPIRE_HOURS)
    else:
        expires_delta = timedelta(days=settings.JWT_EXPIRE_DAYS)

    expire = now + expires_delta
    jti = uuid.uuid4().hex

    payload = {
        "sub": subject,          # 用户标识（user_id 或 admin_user_id）
        "jti": jti,              # 唯一 ID，黑名单定位用
        "type": token_type,      # 区分 C 端 / B 端 token
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    expires_in = int(expires_delta.total_seconds())
    return token, jti, expires_in


def decode_token(token: str) -> dict:
    """
    验证并解码 JWT。

    抛出 jwt.PyJWTError 子类异常（ExpiredSignatureError 等），
    由调用方捕获后转为 AuthError。
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


# ---- bcrypt 密码哈希 ----

def hash_password(plain: str) -> str:
    """bcrypt 加盐哈希。"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
