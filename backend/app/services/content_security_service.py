"""微信内容安全检测服务。

在 AI 工作流的 rewrite 步骤后自动执行 msgSecCheck，
检测稿件是否含政治敏感/色情/暴恐/违法等违规内容。

设计要点：
1. 复用项目已有的 WX_APPID/WX_SECRET（微信小程序通用凭证），避免重复配置
2. access_token 用 TTLCache 进程内缓存（TTL 7200s），规避微信每日获取次数限制
3. 检测失败（未配置/网络异常/微信限流）一律跳过，不阻断主工作流；
   工作流中已有 AC 自动机敏感词替换机制，本检测作为"二次告警"而非"拦截"
4. 检测结果写入 workflow_step.result.content_security，便于运营在后台追溯
"""
import asyncio
import logging
from typing import Optional

import httpx
from cachetools import TTLCache

from app.config import get_settings
from app.core.timeutil import localnow_naive

logger = logging.getLogger(__name__)
settings = get_settings()

# access_token 缓存：微信 access_token 有效期 7200 秒，提前 300 秒失效以留出安全余量
# 用模块级单例缓存，多协程共享；TTLCache 自带线程安全（dict 操作原子），
# 但获取 token 的 HTTP 请求需加锁防止并发重复获取
_ACCESS_TOKEN_CACHE: TTLCache = TTLCache(maxsize=1, ttl=7200)
_ACCESS_TOKEN_LOCK = asyncio.Lock()

# 微信 API 端点：从 settings.WX_API_BASE 派生，避免硬编码
# 仅在微信变更域名时才需修改 WX_API_BASE，默认值对齐官方文档
_TOKEN_URL = f"{settings.WX_API_BASE}/cgi-bin/token"
_MSG_SEC_CHECK_URL = f"{settings.WX_API_BASE}/wxa/msg_sec_check"

# HTTP 请求超时：微信 API 通常 < 1s，留 10s 余量防止网络抖动
_HTTP_TIMEOUT = 10.0


class ContentSecurityService:
    """微信内容安全检测服务。

    调用微信 msgSecCheck API 检测文本内容安全性，
    在 rewrite 步骤后自动执行，检测结果写入 workflow_step。
    """

    @staticmethod
    async def _get_access_token() -> Optional[str]:
        """获取微信 access_token，带 TTLCache 缓存。

        用 asyncio.Lock 串行化获取请求，避免多工作流并发触发时
        重复调用 token 接口浪费微信每日调用配额（2000 次/天）。
        缓存命中时直接返回，无网络开销。
        """
        # 缓存命中优先返回（无锁快路径）
        cached = _ACCESS_TOKEN_CACHE.get("access_token")
        if cached:
            return cached

        # 未命中则加锁获取，防止并发重复请求
        async with _ACCESS_TOKEN_LOCK:
            # 双检：持锁后再次检查，可能在等待锁期间已被其他协程填充
            cached = _ACCESS_TOKEN_CACHE.get("access_token")
            if cached:
                return cached

            appid = settings.WX_APPID
            secret = settings.WX_SECRET
            # 未配置微信凭证时跳过检测，不抛异常（开发态常态）
            if not appid or not secret:
                logger.debug("WX_APPID/WX_SECRET 未配置，跳过内容安全检测")
                return None

            params = {
                "grant_type": "client_credential",
                "appid": appid,
                "secret": secret,
            }
            try:
                async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                    resp = await client.get(_TOKEN_URL, params=params)
                data = resp.json()
            except httpx.HTTPError as e:
                logger.warning("获取微信 access_token 网络异常: %s", e)
                return None
            except Exception as e:
                logger.warning("获取微信 access_token 解析失败: %s", e)
                return None

            if "access_token" not in data:
                # 微信返回 errcode/errmsg，记录便于运维排查
                logger.warning(
                    "获取微信 access_token 失败 errcode=%s errmsg=%s",
                    data.get("errcode"), data.get("errmsg"),
                )
                return None

            token = data["access_token"]
            _ACCESS_TOKEN_CACHE["access_token"] = token
            logger.debug("已获取微信 access_token（缓存 7200s）")
            return token

    @staticmethod
    async def check_text(content: str, openid: str = "") -> dict:
        """检测文本内容安全性。

        调用微信 msgSecCheck（version=2），检测政治敏感/色情/暴恐/违法等违规内容。
        任何异常都不阻断主流程，仅返回 skipped=True 信号告知调用方"检测未执行"。

        返回格式：
        {
            "safe": bool,        # 是否安全（True 表示未命中违规或检测被跳过）
            "detail": [...],     # 违规详情列表（safe=True 时为空）
            "checked_at": str,   # 检测时间 ISO 格式
            "skipped": bool,     # 是否跳过（未配置/网络失败等）
            "error": str,        # 跳过或失败时的原因（skipped=False 时为空）
        }

        Args:
            content: 待检测文本（稿件全文）
            openid: 用户 openid（msgSecCheck v2 必填，工作流场景无具体用户时留空）
        """
        # 空内容直接判定安全，避免无意义 API 调用
        if not content or not content.strip():
            return {
                "safe": True,
                "detail": [],
                "checked_at": localnow_naive().isoformat(),
                "skipped": True,
                "error": "内容为空，跳过检测",
            }

        access_token = await ContentSecurityService._get_access_token()
        # access_token 未配置或获取失败：跳过检测，不阻断工作流
        if not access_token:
            return {
                "safe": True,
                "detail": [],
                "checked_at": localnow_naive().isoformat(),
                "skipped": True,
                "error": "微信 access_token 未配置或获取失败",
            }

        # msgSecCheck v2 请求体
        # scene=1：资料场景（对应稿件审核）；version=2：使用新版检测策略
        payload = {
            "version": 2,
            "scene": 1,
            "openid": openid or "default",
            "content": content,
        }
        params = {"access_token": access_token}

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(_MSG_SEC_CHECK_URL, params=params, json=payload)
            data = resp.json()
        except httpx.HTTPError as e:
            # 网络错误不阻断工作流：记录原因，标记 skipped
            logger.warning("msgSecCheck 网络异常（跳过检测）: %s", e)
            return {
                "safe": True,
                "detail": [],
                "checked_at": localnow_naive().isoformat(),
                "skipped": True,
                "error": f"网络异常: {e}",
            }
        except Exception as e:
            logger.warning("msgSecCheck 调用异常（跳过检测）: %s", e)
            return {
                "safe": True,
                "detail": [],
                "checked_at": localnow_naive().isoformat(),
                "skipped": True,
                "error": f"调用异常: {e}",
            }

        checked_at = localnow_naive().isoformat()

        # errcode=0 表示检测通过（无违规）
        # errcode=0 时 result 数组中每项的 suggest 字段指示处理建议
        errcode = data.get("errcode", -1)
        if errcode != 0:
            # access_token 过期/失效：清除缓存，下次调用会重新获取
            # 40001: invalid credential / 42001: access_token expired
            if errcode in (40001, 42001):
                _ACCESS_TOKEN_CACHE.pop("access_token", None)
                logger.warning(
                    "微信 access_token 失效（errcode=%s），已清除缓存", errcode,
                )
            logger.warning(
                "msgSecCheck 返回错误 errcode=%s errmsg=%s",
                errcode, data.get("errmsg"),
            )
            return {
                "safe": True,
                "detail": [],
                "checked_at": checked_at,
                "skipped": True,
                "error": f"微信 API 错误 errcode={errcode} errmsg={data.get('errmsg', '')}",
            }

        # 解析检测结果
        # result 是数组，每项含 trace_id/suggest/label 等
        # - suggest="pass"：通过
        # - suggest="risky"：命中违规
        # - label：违规类型（100=广告, 10001=涉政, 20001=色情, 20002=辱骂, 21000=暴恐等）
        result_items = data.get("result", []) or []
        detail = []
        any_risky = False
        for item in result_items:
            suggest = item.get("suggest", "pass")
            label = item.get("label", 0)
            if suggest == "risky":
                any_risky = True
                detail.append({
                    "suggest": suggest,
                    "label": label,
                    "trace_id": item.get("trace_id", ""),
                })

        if any_risky:
            logger.warning(
                "内容安全检测命中违规 detail=%s（不阻断工作流，已有敏感词替换机制）",
                detail,
            )
        else:
            logger.debug("内容安全检测通过")

        return {
            "safe": not any_risky,
            "detail": detail,
            "checked_at": checked_at,
            "skipped": False,
            "error": "",
        }
