"""图像生成服务（T00730/T00731）：agnes-image-2.5-flash 客户端。

OpenAI 兼容接口（POST {base_url}/images/generations）：
- 文生图：model + prompt + size（+ratio）
- 返回 b64_json（extra_body.response_format），解码为 bytes 供落盘

配置来源（Settings）：IMAGE_API_KEY / IMAGE_API_BASE_URL / IMAGE_API_MODEL。
未配置 KEY 或网络不可达时抛 ImageGenError（调用方转成明确的用户提示）。
"""
from __future__ import annotations

import base64
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class ImageGenError(Exception):
    """图像生成失败（配置缺失 / 网络 / 服务端错误）。"""


def generate_image(prompt: str, *, size: str = "1K", ratio: str = "1:1",
                   timeout: float = 120.0) -> bytes:
    """调用图像生成服务，返回图片二进制（PNG/JPG 由服务端决定）。

    Raises:
        ImageGenError: 未配置 KEY / 请求失败 / 响应缺图。
    """
    settings = get_settings()
    api_key = getattr(settings, "IMAGE_API_KEY", "") or ""
    if not api_key:
        raise ImageGenError("图像生成服务未配置（缺少 IMAGE_API_KEY）")

    base_url = (getattr(settings, "IMAGE_API_BASE_URL", "") or
                "https://apihub.agnes-ai.com/v1").rstrip("/")
    model = getattr(settings, "IMAGE_API_MODEL", "") or "agnes-image-2.5-flash"

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "ratio": ratio,
        "extra_body": {"response_format": "b64_json"},
    }
    try:
        resp = httpx.post(
            f"{base_url}/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        logger.warning("图像生成请求失败: %s", e)
        raise ImageGenError(f"图像生成服务连接失败：{e.__class__.__name__}") from e

    if resp.status_code != 200:
        logger.warning("图像生成服务返回 %s: %s", resp.status_code, resp.text[:200])
        raise ImageGenError(f"图像生成服务返回 {resp.status_code}，请稍后重试")

    try:
        data = resp.json().get("data", [{}])[0]
    except ValueError as e:
        raise ImageGenError("图像生成服务响应格式异常") from e

    b64 = data.get("b64_json")
    if not b64:
        raise ImageGenError("图像生成服务未返回图片数据")
    return base64.b64decode(b64)


def test_connection(*, base_url: str = "", api_key: str = "", model: str = "",
                    timeout: float = 10.0) -> dict:
    """图片服务连接测试（T00730 配置页）：GET {base}/models 验证可达性与鉴权。

    轻量探测（不真实出图，避免测试一次消耗一次生成配额）。
    参数为空时回退 Settings 当前配置。返回 {ok, message}。
    """
    settings = get_settings()
    key = api_key or (getattr(settings, "IMAGE_API_KEY", "") or "")
    base = (base_url or getattr(settings, "IMAGE_API_BASE_URL", "") or
            "https://apihub.agnes-ai.com/v1").rstrip("/")
    mdl = model or (getattr(settings, "IMAGE_API_MODEL", "") or "agnes-image-2.5-flash")

    if not key:
        return {"ok": False, "message": "未配置 API Key"}

    try:
        resp = httpx.get(
            f"{base}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        logger.warning("图片服务连接测试失败: %s", e)
        return {"ok": False, "message": f"连接失败：{e.__class__.__name__}"}

    if resp.status_code == 401:
        return {"ok": False, "message": "鉴权失败（API Key 无效）"}
    if resp.status_code != 200:
        return {"ok": False, "message": f"服务返回 {resp.status_code}"}

    # 尝试确认目标模型在列表中（部分兼容网关不返回模型列表，仅提示不判失败）
    configured = mdl
    found = None
    try:
        items = resp.json().get("data", []) or []
        found = next((it.get("id") for it in items if it.get("id") == configured), None)
    except ValueError:
        pass
    if configured and found is None:
        return {"ok": True,
                "message": f"连接成功（模型 {configured} 未在 /models 列表中，网关可能按需路由，不影响使用）"}
    return {"ok": True, "message": f"连接成功，模型 {configured} 可用"}
