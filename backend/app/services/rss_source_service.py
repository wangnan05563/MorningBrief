"""RSS 源配置加载服务。

统一 rss.yaml 的加载逻辑，供 admin 路由（频道配置/AI 推荐）与 crawler workflow 复用，
避免两处路径拼接与字段解析逻辑重复导致后续维护漂移。

设计要点：
- 同步文件 IO：rss.yaml 仅在 admin 操作或爬虫启动时加载，调用频率极低，无需异步化
- 路径解析走 app.paths 模块，保证 PyInstaller 打包态/开发态一致
- 缓存策略：调用方按需自行缓存（crawler 启动加载一次，admin 接口按需调用），
  本服务保持无状态，避免缓存失效时机复杂化
"""
import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml

from app.core.timeutil import localnow_naive
from app.paths import resolve_rss_sources_path

logger = logging.getLogger(__name__)


def load_rss_sources() -> list[dict[str, Any]]:
    """加载 rss.yaml 中所有可用 RSS 源。

    Returns:
        源配置列表，每个源为 dict，包含 name/category_hint/authority 等字段。
        rss.yaml 不存在或为空时返回空列表，调用方需自行处理空场景。

    Raises:
        yaml.YAMLError: rss.yaml 语法错误时抛出，调用方按需捕获转 500/警告
    """
    rss_path = resolve_rss_sources_path()
    if not rss_path.exists():
        logger.warning("rss.yaml 不存在: %s", rss_path)
        return []

    with open(rss_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    sources = config.get("sources", [])
    if not isinstance(sources, list):
        logger.warning("rss.yaml sources 字段非列表，按空列表处理")
        return []

    return sources


def load_rss_sources_summary() -> list[dict[str, Any]]:
    """加载 RSS 源的精简摘要（仅 name/category_hint/authority）。

    供前端下拉选择与 LLM 推荐使用，避免 url/qps 等内部字段泄漏到前端或干扰 LLM。
    """
    sources = load_rss_sources()
    return [
        {
            "name": s.get("name", ""),
            "category_hint": s.get("category_hint", ""),
            "authority": s.get("authority", 0.5),
        }
        for s in sources
    ]


# ===== RSS 源可达性巡检 =====
# 内存维护源状态字典，避免引入额外表结构与迁移成本
# 格式：{source_name: {url, last_check, status, consecutive_failures, last_error, latency_ms}}
# status: "ok" / "fail" / "unknown"（未巡检过）
_SOURCE_STATUS: dict[str, dict[str, Any]] = {}

# 巡检并发上限：避免瞬间打爆源站点，与 crawler 串行抓取风格一致
_CHECK_CONCURRENCY = 5
# 单次巡检请求超时：远小于 crawler 30s，避免巡检任务占用过长时间
_CHECK_TIMEOUT = 8.0
# 连续失败告警阈值：达到时发 WARNING 日志，提醒运维检查源
_ALERT_FAILURES_THRESHOLD = 3


def _build_suggestion(url: str, status: str, consecutive_failures: int) -> Optional[str]:
    """根据 URL 模式 + 失败状态给出修复建议，便于运维快速决策。

    判断维度：
    - 第三方转换服务（plink/rsshub）：失败时建议改用原生 RSS（已在 memory R54 沉淀）
    - HTTP 协议源：建议升级到 HTTPS 提升安全性
    - 连续失败 ≥3 次：建议暂时移除该源避免无效重试
    """
    if status == "ok":
        return None

    url_lower = url.lower()
    suggestions = []

    # 第三方转换服务：限流/DNS 污染风险高，建议改用原生 RSS
    if "plink.anyfeeder.com" in url_lower:
        suggestions.append("依赖 plink 第三方转换服务，建议查找站点原生 RSS 替代")
    if "rsshub.app" in url_lower:
        suggestions.append("rsshub.app 公共实例在大陆被 DNS 污染，建议改用原生 RSS 或自建 RSSHub")

    # HTTP 协议源：建议升级 HTTPS
    if url_lower.startswith("http://"):
        suggestions.append("源使用 HTTP 明文协议，建议升级到 HTTPS 提升安全性")

    # 连续失败 ≥3 次：建议暂时移除
    if consecutive_failures >= _ALERT_FAILURES_THRESHOLD:
        suggestions.append(f"连续失败 {consecutive_failures} 次，建议暂时移除该源避免无效重试")

    return "；".join(suggestions) if suggestions else None


async def _check_single_source(client: httpx.AsyncClient, source: dict) -> dict:
    """巡检单个 RSS 源：HEAD 失败则回退 GET（部分源不支持 HEAD）。

    返回巡检结果 dict（含 status/latency/error），由 check_all_sources 合并到全局状态。
    错误信息包含 HTTP 状态码、Content-Type、响应片段，便于运维快速诊断根因：
    - 4xx/5xx：状态码 + 响应前 100 字符
    - 网络异常：异常类型 + 消息
    - HTML 响应：标记为"非 RSS 内容"（站点可能未提供 RSS）
    """
    name = source.get("name", "")
    url = source.get("url", "")
    if not url:
        return {"name": name, "status": "fail", "error": "url 为空", "latency_ms": 0}

    start = time.monotonic()
    try:
        # 先 HEAD：轻量探测，不下载正文，节省带宽
        resp = await client.head(url, follow_redirects=True)
        if resp.status_code == 405:
            # 部分源不支持 HEAD（返回 405 Method Not Allowed），回退 GET
            resp = await client.get(url, follow_redirects=True)
        # 非 2xx 视为失败：拼接状态码 + Content-Type + 响应片段，便于诊断
        if resp.status_code >= 400:
            latency_ms = int((time.monotonic() - start) * 1000)
            content_type = resp.headers.get("content-type", "unknown")[:50]
            body_snippet = (resp.text or "")[:100].replace("\n", " ").strip()
            error_msg = (
                f"HTTP {resp.status_code} | Content-Type: {content_type} | "
                f"Body: {body_snippet}"
            )
            return {"name": name, "status": "fail", "latency_ms": latency_ms, "error": error_msg}

        # 2xx 但内容非 RSS：站点返回 HTML 页面，可能是 WAF 拦截或未提供 RSS
        content_type = resp.headers.get("content-type", "").lower()
        if content_type.startswith("text/html"):
            latency_ms = int((time.monotonic() - start) * 1000)
            return {
                "name": name, "status": "fail", "latency_ms": latency_ms,
                "error": f"HTTP 200 但响应为 HTML（非 RSS）：Content-Type={content_type[:50]}，"
                         f"站点可能未提供 RSS 或被 WAF 拦截，建议改用原生 RSS 或第三方转换服务"
            }

        latency_ms = int((time.monotonic() - start) * 1000)
        return {"name": name, "status": "ok", "latency_ms": latency_ms, "error": None}
    except httpx.TimeoutException:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "name": name, "status": "fail", "latency_ms": latency_ms,
            "error": f"请求超时（>{_CHECK_TIMEOUT}s），源站点响应过慢或不可达"
        }
    except httpx.ConnectError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "name": name, "status": "fail", "latency_ms": latency_ms,
            "error": f"连接失败：{str(e)[:150]}，可能是 DNS 解析失败或网络不通"
        }
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        error_type = type(e).__name__
        return {
            "name": name, "status": "fail", "latency_ms": latency_ms,
            "error": f"{error_type}: {str(e)[:200]}"
        }


async def check_all_sources() -> dict:
    """并发巡检所有 RSS 源可达性，更新内存状态并返回汇总。

    巡检策略：
    - 并发上限 5（避免打爆源站）
    - 单源超时 8s（远小于 crawler 30s，巡检要快速完成）
    - HEAD 失败回退 GET（部分源不支持 HEAD）
    - 连续失败 ≥3 次发 WARNING 日志

    Returns:
        {"total": N, "ok": N, "fail": N, "sources": [{name, url, status, ...}]}
    """
    sources = load_rss_sources()
    if not sources:
        return {"total": 0, "ok": 0, "fail": 0, "sources": []}

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MorningBrief-HealthCheck/1.0)",
    }
    async with httpx.AsyncClient(
        timeout=_CHECK_TIMEOUT,
        headers=headers,
    ) as client:
        # Semaphore 限制并发：避免 50+ 源同时请求触发源站 WAF
        sem = asyncio.Semaphore(_CHECK_CONCURRENCY)

        async def _bounded_check(src: dict) -> dict:
            async with sem:
                return await _check_single_source(client, src)

        results = await asyncio.gather(*[_bounded_check(s) for s in sources], return_exceptions=False)

    # 合并到全局状态字典
    # 项目约定：所有时间字段存为本地 naive datetime（香港 UTC+8），
    # isoformat() 输出无时区后缀，前端按本地时区解析与 crawled_at 等字段一致
    now = localnow_naive().isoformat()
    ok_count = 0
    fail_count = 0
    source_list = []
    for src_cfg, result in zip(sources, results):
        name = result["name"]
        status = result["status"]
        prev = _SOURCE_STATUS.get(name, {})
        prev_failures = prev.get("consecutive_failures", 0)

        if status == "ok":
            ok_count += 1
            consecutive_failures = 0
        else:
            fail_count += 1
            consecutive_failures = prev_failures + 1
            # 连续失败达阈值时告警（仅首次达阈值时告警，避免重复刷屏）
            if consecutive_failures == _ALERT_FAILURES_THRESHOLD:
                logger.warning(
                    "RSS 源连续失败 %d 次 name=%s url=%s error=%s",
                    consecutive_failures, name, src_cfg.get("url", ""),
                    result.get("error", ""),
                )

        _SOURCE_STATUS[name] = {
            "url": src_cfg.get("url", ""),
            "category_hint": src_cfg.get("category_hint"),
            "last_check": now,
            "status": status,
            "latency_ms": result.get("latency_ms", 0),
            "consecutive_failures": consecutive_failures,
            "last_error": result.get("error"),
            "suggestion": _build_suggestion(src_cfg.get("url", ""), status, consecutive_failures),
        }
        source_list.append({
            "name": name,
            **_SOURCE_STATUS[name],
        })

    logger.info("RSS 巡检完成 total=%d ok=%d fail=%d", len(sources), ok_count, fail_count)
    return {
        "total": len(sources),
        "ok": ok_count,
        "fail": fail_count,
        "checked_at": now,
        "sources": source_list,
    }


def get_source_status() -> dict:
    """返回当前所有 RSS 源的最近巡检状态（不触发新巡检）。

    供 API 端点查询用，避免每次查询都触发巡检。
    未巡检过的源返回 status="unknown"。
    """
    sources = load_rss_sources()
    source_list = []
    ok_count = 0
    fail_count = 0
    unknown_count = 0
    for src in sources:
        name = src.get("name", "")
        status = _SOURCE_STATUS.get(name)
        if status is None:
            # 未巡检过的源，标记为 unknown
            source_list.append({
                "name": name,
                "url": src.get("url", ""),
                "category_hint": src.get("category_hint"),
                "status": "unknown",
                "last_check": None,
                "consecutive_failures": 0,
                "latency_ms": 0,
                "last_error": None,
                "suggestion": None,
            })
            unknown_count += 1
        else:
            source_list.append({"name": name, **status})
            if status["status"] == "ok":
                ok_count += 1
            else:
                fail_count += 1

    return {
        "total": len(sources),
        "ok": ok_count,
        "fail": fail_count,
        "unknown": unknown_count,
        "sources": source_list,
    }
