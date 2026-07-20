"""B 端关于路由：暴露系统元信息 + 检查更新。

端点：
- GET /admin/api/v1/about            返回 _build_info.py 写入的版本/日期/SHA
- GET /admin/api/v1/about/check-update 比对本地版本与远端最新版本

设计要点：
- 仅查询公开仓库的 release 元信息，不携带任何认证 token
- 失败安全降级：网络/限速/解析错误时返回 has_update=False, source='local'，
  避免 /check-update 端点 500 污染前端更新检查逻辑
- 缓存 5 分钟内复用上次结果，避免触发 GitHub 限速（60/小时/IP）
"""
from __future__ import annotations

import platform as _platform
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from loguru import logger

from app.core.auth import AdminPayload, require_admin
from app.core.response import success

router = APIRouter(prefix="/admin/api/v1/about", tags=["关于"])

# 项目仓库（用于检查更新与 release_url 跳转）
# 当前项目无对外开源仓库，release_url 指向占位地址；后续接入时仅改这里
_REPO_URL = "https://github.com/your-org/MorningBrief"
_RELEASES_API = f"{_REPO_URL}/releases/latest"
_RELEASE_URL = f"{_REPO_URL}/releases"
_PRODUCT_NAME = "MorningBrief"

# UTC+8 时区（构建日期/检查时间统一使用，与项目其他模块一致）
_CST = timezone(timedelta(hours=8))

# 缓存窗口：5 分钟内复用上次成功结果，避免每次轮询都打 GitHub API 触发限速
# GitHub 公共 API 未认证限速为 60 次/小时/IP，5 分钟缓存可将上限压到 12 次/小时
_CACHE_TTL_SECONDS = 300
# HTTP 请求超时：连接 3s + 读取 5s，避免 GitHub API 偶发慢响应阻塞 check-update
_HTTP_TIMEOUT = httpx.Timeout(connect=3.0, read=5.0, write=1.0, pool=1.0)
# 请求头：GitHub API 要求 User-Agent 标识客户端；不携带任何 token
_HTTP_HEADERS = {
    "User-Agent": "MorningBrief-UpdateChecker/1.0",
    "Accept": "application/vnd.github+json",
}

# 内存缓存：进程级单例，所有请求共享
# 为什么不用 functools.lru_cache：lru_cache 无法缓存异常分支，
# 且这里需要存储 _cached_at 时间戳
_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}


def _safe_build_info() -> dict[str, str]:
    """读取 _build_info.py，缺字段兜底为 'unknown'。

    try/except 防止 _build_info.py 缺失或字段被删导致 About 页崩溃。
    """
    try:
        from app import _build_info  # type: ignore[attr-defined]
    except Exception:
        return {"version": "unknown", "build_date": "unknown", "git_sha": "unknown"}
    return {
        "version": getattr(_build_info, "__version__", "unknown"),
        "build_date": getattr(_build_info, "build_date", "unknown"),
        "git_sha": getattr(_build_info, "git_sha", "unknown"),
    }


def _now_iso() -> str:
    """当前 UTC+8 时间 ISO 字符串（秒精度）。"""
    return datetime.now(_CST).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 版本号比较：语义化版本 (semver) 简化实现
# ---------------------------------------------------------------------------
# 为什么不引入 semver 库：仅需要主.次.微三元组比较，标准库 re 即可完成，
# 避免为单点功能增加依赖。
_SEMVER_RE = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)")


def _parse_version(raw: str) -> tuple[int, int, int] | None:
    """解析 'v1.2.3' / '1.2.3' / 'v1.2.3-beta' 为 (1, 2, 3)。

    非语义化版本（如 'unknown'、'main'、空串）返回 None，
    比较时按保守策略处理，保证 has_update 永远不会误判为 True。
    """
    if not raw or raw == "unknown":
        return None
    m = _SEMVER_RE.match(raw.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _is_newer(current: str, latest: str) -> bool:
    """latest 是否严格大于 current。

    任一端无法解析时返回 False（保守策略，避免误报让用户徒劳升级）。
    为什么不 fallback 到 (0,0,0)：current='unknown' 时若按 (0,0,0) 比较，
    任何远端 release 都会被判为「有更新」，让用户徒劳升级。
    """
    c = _parse_version(current)
    l = _parse_version(latest)
    if c is None or l is None:
        return False
    return l > c


# ---------------------------------------------------------------------------
# GitHub Releases API 调用
# ---------------------------------------------------------------------------

def _build_local_response(current: str, *, error: str | None = None) -> dict[str, Any]:
    """构造降级响应：网络失败或缓存未命中时使用，UI 显示「已是最新」或异常提示。

    为什么失败时仍返回 has_update=False 而非 5xx：
    /admin/api/v1/about/check-update 是元信息端点，500 会污染前端更新检查逻辑，
    返回 200 + source='local' + error 字段让前端按需提示。
    """
    resp: dict[str, Any] = {
        "current": current,
        "latest": current,
        "has_update": False,
        "release_url": _RELEASE_URL,
        "checked_at": _now_iso(),
        "source": "local",
    }
    if error:
        # error 字段仅供前端在「长时间无更新」时给出诊断提示，不强制展示
        resp["error"] = error
    return resp


async def _fetch_latest_release() -> dict[str, Any] | None:
    """调用 GitHub Releases API 获取最新 release。

    返回 dict（含 tag_name/html_url/published_at/name）或 None（任何失败）。
    任何异常都吞掉并记录日志，调用方降级处理。
    """
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, headers=_HTTP_HEADERS) as client:
            resp = await client.get(_RELEASES_API)
        # 404：仓库无任何 release（仅 tag 或预发布），不是错误，正常降级
        if resp.status_code == 404:
            logger.info("[about] GitHub 返回 404：仓库暂无正式 release")
            return None
        # 403 通常为限速触发（GitHub 未认证 60/小时/IP）
        if resp.status_code == 403:
            remaining = resp.headers.get("X-RateLimit-Remaining", "?")
            logger.warning(
                "[about] GitHub API 限速或拒绝访问 (403)，剩余配额=%s", remaining
            )
            return None
        if resp.status_code != 200:
            logger.warning("[about] GitHub API 非预期状态码: %s", resp.status_code)
            return None
        data = resp.json()
        # 必要字段缺失视为无效响应
        if not isinstance(data, dict) or "tag_name" not in data:
            logger.warning("[about] GitHub API 响应缺少 tag_name 字段")
            return None
        return {
            "tag_name": str(data.get("tag_name", "")).strip(),
            "html_url": str(data.get("html_url", _RELEASE_URL)),
            "published_at": str(data.get("published_at", "")),
            "name": str(data.get("name", "")),
        }
    except httpx.TimeoutException:
        logger.warning("[about] GitHub API 请求超时，降级返回本地版本")
        return None
    except httpx.HTTPError as e:
        logger.warning("[about] GitHub API 网络错误: %s", e)
        return None
    except Exception as e:
        # JSON 解析、未知异常等：吞掉防止 check-update 端点 500
        logger.warning("[about] GitHub API 未知异常: %s", e)
        return None


@router.get("")
async def get_about(
    admin: AdminPayload = Depends(require_admin),
) -> dict[str, Any]:
    """系统元信息：版本、构建日期、Git SHA、Python 版本、平台。

    需 admin 权限：与 B 端其他 /admin/api/v1/* 接口保持一致的鉴权策略。
    """
    info = _safe_build_info()
    return success(data={
        "product": _PRODUCT_NAME,
        "version": info["version"],
        "build_date": info["build_date"],
        "git_sha": info["git_sha"],
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": _platform.system().lower(),
    })


@router.get("/check-update")
async def check_update(
    admin: AdminPayload = Depends(require_admin),
) -> dict[str, Any]:
    """检查更新：调用 GitHub Releases API 比对版本。

    流程：
    1. 缓存命中（< 5 分钟）直接返回缓存结果
    2. 缓存过期则发起 GitHub API 请求
    3. 请求成功：与 current 比较版本，缓存结果
    4. 请求失败：降级返回 has_update=False, source='local'（不缓存失败，便于下次重试）
    """
    info = _safe_build_info()
    current = info["version"]

    # 缓存命中：5 分钟内直接复用上次结果
    now = time.monotonic()
    cached = _cache["data"]
    if cached is not None and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        # 缓存内容基于同一 current 版本构造，可直接返回
        # 若 current 变化（构建后版本升级），缓存自动失效由下次轮询刷新
        if cached.get("current") == current:
            return success(data=cached)

    # 缓存过期或 current 变化，发起 GitHub API 请求
    release = await _fetch_latest_release()
    if release is None:
        # 降级：不写缓存，便于下次请求立即重试
        return success(data=_build_local_response(current))

    latest = release["tag_name"]
    has_update = _is_newer(current, latest)
    # has_update=True 时 release_url 指向具体 release 页面，否则指向 releases 列表
    release_url = release["html_url"] if has_update else _RELEASE_URL

    result: dict[str, Any] = {
        "current": current,
        "latest": latest,
        "has_update": has_update,
        "release_url": release_url,
        "checked_at": _now_iso(),
        "source": "remote",
        # 额外元信息（可选，前端用于展示发布时间）
        "published_at": release["published_at"],
    }

    # 写入缓存：仅缓存成功响应
    _cache["data"] = result
    _cache["fetched_at"] = now
    return success(data=result)


def _reset_cache_for_test() -> None:
    """测试专用：清空缓存。生产代码不要调用。"""
    _cache["data"] = None
    _cache["fetched_at"] = 0.0
