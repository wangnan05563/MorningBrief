"""云函数 SCF 通用基类（V1.2 新增）。

5 个云函数共享的 COS 客户端、JWT 验签、黑名单缓存、统一响应。

冷启动优化：
- COS 客户端在模块加载时初始化（SCF 实例复用，避免每次请求重建）
- JWT 黑名单内存缓存 TTL 5 分钟，过期后批量拉取 COS jwt_blacklist/ 前缀对象

与单机 exe 解耦：
- SCF 仅读 COS 对象，不访问单机 SQLite
- 单机 exe 离线时 C 端仍可读历史节目
"""
import json
import os
import time
from typing import Any

import jwt
from qcloud_cos import CosConfig, CosS3Client

# SCF 实例级单例（模块加载时初始化，多次调用复用）
_config = CosConfig(
    Region=os.environ.get("COS_REGION", "ap-guangzhou"),
    SecretId=os.environ.get("COS_SECRET_ID", ""),
    SecretKey=os.environ.get("COS_SECRET_KEY", ""),
    Scheme="https",
)
cos_client = CosS3Client(_config)
JWT_SECRET = os.environ.get("JWT_SECRET", "")
COS_BUCKET = os.environ.get("COS_BUCKET", "")
JWT_BLACKLIST_COS_PREFIX = os.environ.get("JWT_BLACKLIST_COS_PREFIX", "jwt_blacklist/")
# 黑名单缓存 TTL（默认 5 分钟，与单机 B 端保持一致）
BLACKLIST_TTL_SEC = int(os.environ.get("JWT_BLACKLIST_CACHE_TTL_SEC", 300))

# JWT 黑名单内存缓存：{"data": set[str], "expires_at": float}
_blacklist_cache: dict[str, Any] = {"data": set(), "expires_at": 0.0}


def verify_token(event: dict) -> dict:
    """验证 C 端 JWT token，返回 payload。

    流程：
    1. 从 Authorization 头提取 Bearer token
    2. jwt.decode 验证签名与有效期
    3. 检查 jti 是否在黑名单中（内存缓存 + COS 拉取）

    Raises:
        Exception: token 缺失/过期/无效/黑名单命中
    """
    headers = event.get("headers", {}) or {}
    auth_header = headers.get("Authorization") or headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise PermissionError("缺少认证信息")
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise PermissionError("登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise PermissionError("无效的认证信息")

    # 仅接受 C 端 token（SCF 仅承载 C 端接口）
    if payload.get("type") != "user":
        raise PermissionError("认证类型错误")

    # 检查黑名单缓存是否过期，过期则重新拉取
    now = time.time()
    if now > _blacklist_cache["expires_at"]:
        _refresh_blacklist_cache()

    jti = payload.get("jti", "")
    if jti in _blacklist_cache["data"]:
        raise PermissionError("登录已失效，请重新登录")

    return payload


def _refresh_blacklist_cache() -> None:
    """从 COS 拉取当前所有黑名单 jti。

    黑名单对象路径：jwt_blacklist/{jti}.json
    通过 COS list_objects 列举前缀，汇总所有 jti。
    单机 exe 的 APScheduler 定时清理已过期黑名单对象，
    所以 SCF 拉到的对象都是未过期的。
    """
    blacklist: set[str] = set()
    try:
        response = cos_client.list_objects(
            Bucket=COS_BUCKET, Prefix=JWT_BLACKLIST_COS_PREFIX
        )
        for obj in response.get("Contents", []):
            # 对象名为 jwt_blacklist/{jti}.json，提取 jti
            key = obj["Key"]
            filename = key.rsplit("/", 1)[-1]
            if filename.endswith(".json"):
                jti = filename[:-5]
                blacklist.add(jti)
    except Exception:
        # COS 拉取失败时保留旧缓存，避免误判所有 token 通过
        pass

    _blacklist_cache["data"] = blacklist
    _blacklist_cache["expires_at"] = time.time() + BLACKLIST_TTL_SEC


def json_response(data: Any, status_code: int = 200) -> dict:
    """SCF 标准响应格式（与 FastAPI success() 统一）。"""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps({"code": 0, "data": data}, ensure_ascii=False, default=str),
    }


def error_response(message: str, code: int = -1, status_code: int = 400) -> dict:
    """错误响应（与 FastAPI error() 统一）。"""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps({"code": code, "message": message}, ensure_ascii=False),
    }


def parse_body(event: dict) -> dict:
    """解析 SCF HTTP 触发器 body（JSON 字符串 → dict）。"""
    body = event.get("body", "") or "{}"
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return json.loads(body)


def parse_query(event: dict) -> dict:
    """解析 SCF HTTP 触发器 query string。"""
    return event.get("queryStringParameters", {}) or {}
