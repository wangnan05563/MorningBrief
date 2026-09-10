"""腾讯云 API 3.0 通用签名与签名请求（TC3-HMAC-SHA256）。

抽出为共享工具的原因（T00388）：AI 配置服务的「音色同步」需要调用
DescribeVoices 接口，与 workflow/tts/tencent_client 的 TextToVoice 共用
同一套签名算法；签名逻辑独立成模块后可被多个调用方复用，避免二次实现。

说明：tencent_client 当前仍保留自带的私有签名实现（合成主链路，改动需
专门回归），后续收敛项是让它改用本模块。

签名算法参考：https://cloud.tencent.com/document/api/213/30654
关键约束：请求体 JSON 字符串在「签名」与「发送」两个阶段必须字节一致，
因此用 content= 而非 json= 传递，避免 httpx 重新序列化。
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

import httpx


class TencentAPIError(RuntimeError):
    """腾讯云云 API 返回 Error（业务错误）或响应不可解析。"""

    def __init__(self, code: str, message: str, request_id: str = ""):
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(f"腾讯云 API {code}: {message}")


def tc3_authorization(
    secret_id: str,
    secret_key: str,
    payload_bytes: bytes,
    timestamp: int,
    service: str,
    action: str,
    host: str,
    content_type: str = "application/json; charset=utf-8",
) -> str:
    """构造 TC3-HMAC-SHA256 Authorization 头。

    步骤：CanonicalRequest → StringToSign → 派生签名密钥（日期/服务/tc3_request
    三层 HMAC）→ 签名 → 拼接 Authorization。
    """
    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = (
        f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n"
        f"{hashlib.sha256(payload_bytes).hexdigest()}"
    )

    # Date 必须从 timestamp 换算为 UTC+0 日期，不能带本地时区
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = (
        f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    secret_date = hmac.new(
        ("TC3" + secret_key).encode("utf-8"), date.encode("utf-8"), hashlib.sha256
    ).digest()
    secret_service = hmac.new(secret_date, service.encode("utf-8"), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return (
        f"TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


async def signed_tencent_post(
    host: str,
    service: str,
    action: str,
    version: str,
    payload: Optional[dict] = None,
    secret_id: str = "",
    secret_key: str = "",
    region: str = "",
    timeout_sec: float = 20.0,
) -> dict:
    """发送带 TC3 签名的腾讯云云 API 3.0 POST 请求，返回 Response 字典。

    - 响应含 Error 字段时抛 TencentAPIError（含 code/message/request_id）。
    - HTTP 层异常（超时/连接失败/5xx）统一包装为 TencentAPIError，
      让上层调用方只需处理一种异常类型。
    """
    payload = payload or {}
    # ensure_ascii=False + 紧凑分隔符：签名与发送共用同一字节串
    payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = int(datetime.now(tz=timezone.utc).timestamp())
    authorization = tc3_authorization(
        secret_id, secret_key, payload_bytes, timestamp, service, action, host
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Timestamp": str(timestamp),
    }
    if region:
        headers["X-TC-Region"] = region

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            resp = await client.post(f"https://{host}/", content=payload_bytes, headers=headers)
    except httpx.HTTPError as e:
        raise TencentAPIError("NetworkError", f"请求失败：{type(e).__name__}: {e}") from e

    if resp.status_code >= 500:
        raise TencentAPIError("ServiceUnavailable", f"服务异常 status={resp.status_code}")
    if resp.status_code != 200:
        raise TencentAPIError("HTTPError", f"status={resp.status_code} body={resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise TencentAPIError("InvalidResponse", f"响应解析失败: {e}") from e

    response = data.get("Response", {})
    if not isinstance(response, dict):
        raise TencentAPIError("InvalidResponse", "响应缺少 Response 字段")
    if "Error" in response:
        err = response["Error"]
        raise TencentAPIError(
            str(err.get("Code", "")),
            str(err.get("Message", "")),
            str(response.get("RequestId", "")),
        )
    return response


def utc_now_iso() -> str:
    """返回带时区的 UTC ISO8601 时间串（用于缓存元信息 synced_at）。"""
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


__all__ = ["TencentAPIError", "signed_tencent_post", "utc_now_iso"]

