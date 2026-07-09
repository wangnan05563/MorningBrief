"""JWT 与密码哈希测试。

覆盖 core/security.py：
- create_access_token：生成的 token 含 jti + exp，且不同 token_type 过期时间不同
- hash_password / verify_password：正确密码通过、错误密码失败
- decode_token：有效 token 能解码；过期 token 抛 ExpiredSignatureError
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_create_access_token_contains_jti_and_exp():
    """生成的 token 解码后必须包含 jti 与 exp 两个关键 claim。

    jti 用于登出黑名单定位，exp 用于过期校验，缺一不可。
    """
    token, jti, expires_in = create_access_token("user-1", token_type="user")

    # 返回的 jti 与 expires_in 应与 token 内一致
    assert isinstance(jti, str) and len(jti) > 0
    assert expires_in > 0

    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["jti"] == jti
    assert payload["type"] == "user"
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_admin_shorter_than_user():
    """admin token 过期时间应短于 user token（B 端安全要求更严）。"""
    _, _, user_expires = create_access_token("u1", token_type="user")
    _, _, admin_expires = create_access_token("a1", token_type="admin")
    # admin 2 小时 vs user 7 天，admin 必然更短
    assert admin_expires < user_expires


def test_hash_and_verify_password():
    """正确密码验证通过，错误密码验证失败。

    bcrypt 加盐哈希：相同明文每次哈希结果不同（盐随机），但验证都能通过。
    """
    plain = "MySecretPass123"
    hashed = hash_password(plain)

    # 哈希结果不应等于明文
    assert hashed != plain
    # 正确密码验证通过
    assert verify_password(plain, hashed) is True
    # 错误密码验证失败
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_generates_different_salts():
    """相同明文两次哈希结果不同（盐随机），但都能验证通过。"""
    plain = "same-password"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2
    assert verify_password(plain, h1) and verify_password(plain, h2)


def test_decode_valid_token():
    """有效 token 解码出 payload，且 sub/jti/type 与生成时一致。"""
    token, jti, _ = create_access_token("42", token_type="user")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["jti"] == jti
    assert payload["type"] == "user"


def test_decode_expired_token():
    """过期 token 解码应抛 jwt.ExpiredSignatureError。

    直接构造 exp=now 的 token，PyJWT 解码时判定为已过期。
    """
    from app.config import get_settings
    settings = get_settings()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "1",
        "jti": "expired-jti",
        "type": "user",
        "iat": now,
        "exp": now,  # 立即过期
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)


def test_decode_invalid_token_raises():
    """非 JWT 格式的字符串解码应抛 PyJWTError 子类。"""
    with pytest.raises(jwt.PyJWTError):
        decode_token("not-a-valid-token")


def test_decode_token_wrong_signature():
    """用其他密钥签发的 token 解码应失败（防伪造）。"""
    from app.config import get_settings
    settings = get_settings()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "1",
        "jti": "x",
        "type": "user",
        "iat": now,
        "exp": now + timedelta(seconds=3600),
    }
    # 用错误密钥签发
    fake_token = jwt.encode(payload, "wrong-secret", algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(jwt.PyJWTError):
        decode_token(fake_token)
