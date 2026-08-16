"""JMeter 性能测试准备脚本。

职责：
1. 在 SQLite 插入测试用户（避免污染真实用户数据）
2. 生成 JWT token（用与后端相同的 JWT_SECRET 签名）
3. 输出 token 到文件供 JMeter 读取
4. 记录测试用户 user_id 用于后续清理

设计取舍：
- 直接操作 SQLite 而非调 API，避免 wx.login 一次性 code 限制
- 测试用户 openid 用 'jmeter_test_' 前缀，便于识别和清理
- token 有效期 1 天（足够测试），jti 不写入黑名单
- JWT 用标准库实现 HS256，避免引入 PyJWT 依赖
"""
import base64
import hashlib
import hmac
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 与后端 config.py 默认值保持一致（项目无 .env 文件，使用默认值）
JWT_SECRET = "change-me-in-production"

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
DB_PATH = BACKEND_DIR / "data" / "news.db"
ENV_PATH = BACKEND_DIR / ".env"
TOKEN_OUTPUT = Path(__file__).resolve().parent / "test_token.txt"
USER_INFO_OUTPUT = Path(__file__).resolve().parent / "test_user_info.json"

TEST_OPENID_PREFIX = "jmeter_test_"


def load_jwt_secret_from_env() -> str:
    """从 backend/.env 读取 JWT_SECRET 实际值。

    pydantic-settings 解析 .env 时会去掉行内 # 注释和首尾空白，
    这里手动复现该行为，避免引入 pydantic-settings 依赖。
    若 .env 不存在或未配置 JWT_SECRET，回退到默认值。
    """
    if not ENV_PATH.exists():
        return JWT_SECRET
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("JWT_SECRET"):
            # 格式：JWT_SECRET=value  # comment
            # 去掉行内注释（# 前后有空格才视为注释，避免值中含 # 被误删）
            if "  #" in line or "\t#" in line:
                line = line.split("  #")[0].split("\t#")[0]
            value = line.split("=", 1)[1].strip()
            # 去掉两端的引号（.env 文件常见写法）
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            return value
    return JWT_SECRET


def _b64url_encode(data: bytes) -> str:
    """JWT 规范要求 base64url 编码（无 padding）。"""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def encode_hs256(payload: dict, secret: str) -> str:
    """用 HS256 算法签发 JWT。

    标准库实现，避免引入 PyJWT 依赖：
    1. header 固定 {"alg": "HS256", "typ": "JWT"}
    2. payload 为业务字段
    3. signature = HMAC-SHA256(header.payload, secret)
    """
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def insert_test_user(conn: sqlite3.Connection) -> int:
    """插入测试用户，返回 user_id。

    使用 INSERT OR IGNORE 保证幂等：重复执行不会创建多个测试用户。
    """
    openid = TEST_OPENID_PREFIX + "user_001"
    conn.execute(
        "INSERT OR IGNORE INTO user (openid, nickname, total_listen_duration, total_listen_count) "
        "VALUES (?, ?, 0, 0)",
        (openid, "JMeter测试用户"),
    )
    conn.commit()
    cur = conn.execute("SELECT id FROM user WHERE openid = ?", (openid,))
    return cur.fetchone()[0]


def generate_token(user_id: int, secret: str) -> tuple[str, str]:
    """生成 C 端用户 JWT token。

    payload 字段对齐后端 core/security.py:create_access_token：
    - sub: 用户 ID（字符串）
    - jti: 唯一 ID（不写入黑名单，保持有效）
    - type: "user"（C 端 token 类型标识）
    - iat/exp: 签发/过期时间
    """
    now = datetime.now(timezone.utc)
    # JWT 标准要求 iat/exp 为 NumericDate（Unix 时间戳整数）
    # PyJWT 库会自动转换 datetime，这里手动转以保持一致
    payload = {
        "sub": str(user_id),
        "jti": uuid.uuid4().hex,
        "type": "user",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=1)).timestamp()),
    }
    token = encode_hs256(payload, secret)
    return token, payload["jti"]


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] 数据库不存在: {DB_PATH}", file=sys.stderr)
        return 1

    # 优先从 backend/.env 读取实际 JWT_SECRET（pydantic-settings 同款解析）
    secret = load_jwt_secret_from_env()
    print(f"[INFO] 使用 JWT_SECRET: {secret[:30]}... (长度 {len(secret)})")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        user_id = insert_test_user(conn)
        token, jti = generate_token(user_id, secret)

        # 输出 token 供 JMeter 读取（纯文本，无 BOM）
        TOKEN_OUTPUT.write_text(token, encoding="utf-8")

        # 输出用户信息供清理脚本使用
        USER_INFO_OUTPUT.write_text(
            json.dumps(
                {
                    "user_id": user_id,
                    "openid": TEST_OPENID_PREFIX + "user_001",
                    "jti": jti,
                    "db_path": str(DB_PATH),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(f"[OK] 测试用户已创建: user_id={user_id}")
        print(f"[OK] JWT token 已生成并写入: {TOKEN_OUTPUT}")
        print(f"[OK] 用户信息已写入: {USER_INFO_OUTPUT}")
        print(f"[OK] Token 前 50 字符: {token[:50]}...")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
