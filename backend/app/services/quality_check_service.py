"""LLM 语义级质量审核服务（T01712 P1：只告警不回退，tts 照常）。

定位：rewrite 完成后、tts 之前插入的语义级审核环节。既有防线
（段长/敏感词/格式/字数）均为规则枚举式，对新形态问题（事实锚错配、
视角漂移、钩子套路、未兑现预告）无防御能力，本服务用 LLM 结构化
审核补充语义级防线。

P1 阶段约束（T01711 评估结论）：
- 只告警不回退：issues 落库 script.quality_report + 日志，供运营审核时参考
- LLM 返回非法 JSON / 任何内部异常 → 降级为「未审核」，绝不阻塞主流程
- LLM 调用复用 rewriter._call_llm（crawler/runner.py 已有同模式先例），
  AI 预算速率限制（60 次/分钟/服务类型）与用量记录自动生效
"""
import json
import re
from datetime import datetime

from loguru import logger
from sqlalchemy import select, update

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Material, Script, Workflow
settings = get_settings()

# issue_type 枚举（与 prompts/quality_check.txt 的审核维度一一对应）：
# LLM 自造维度或拼写偏差的条目直接丢弃，防止污染前端展示与后续统计
_ISSUE_TYPES = frozenset({
    "fact_anchor", "semantic_drift", "perspective",
    "structure", "hook", "readability",
})
_SEVERITIES = frozenset({"high", "medium", "low"})
# severity 告警等级序：用于比较是否达到配置的告警阈值
_SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

# LLM 常见输出污染：markdown 代码块包裹（```json ... ```）。剥掉后再解析，
# 否则"模型正确返回但带了围栏"会被误判为非法 JSON 而整次降级
_MARKDOWN_FENCE_PAT = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


async def _load_context(workflow_id: str, script_id: int) -> dict | None:
    """加载审核上下文：稿件分段 + 频道类型 + 书名/作者锚 + 素材原文锚点。

    Returns:
        上下文字典；script 不存在或无分段时返回 None（调用方降级为未审核）。
    """
    async with AsyncSessionLocal() as session:
        script = (await session.execute(
            select(Script).where(Script.id == script_id)
        )).scalar_one_or_none()
        if script is None or not script.segments:
            return None
        segments = list(script.segments)
        channel_id = (await session.execute(
            select(Workflow.channel_id).where(Workflow.id == workflow_id)
        )).scalar_one_or_none()

        # 收集全部正文段引用的素材 ID（开场白/结尾 material_ids 为空，天然被排除）
        material_ids = sorted({
            mid for seg in segments for mid in (seg.get("material_ids") or [])
        })
        materials: dict[int, Material] = {}
        if material_ids:
            rows = await session.execute(
                select(Material).where(Material.id.in_(material_ids))
            )
            materials = {m.id: m for m in rows.scalars().all()}

        # audiobook 书名/作者锚：书名以素材 source 锚定（book_pool 模式下
        # source 即书名，与 rewriter._filter_audiobook_sources 同源），
        # 作者从 book_pool_item 按频道+书名查，未填则显式声明不得编造
        book_title = None
        author = None
        channel_type = None
        if channel_id:
            from app.models import BookPoolItem, Channel
            channel = await session.get(Channel, channel_id)
            channel_type = channel.channel_type if channel else None
            source_counts: dict[str, int] = {}
            for m in materials.values():
                if m.source:
                    source_counts[m.source] = source_counts.get(m.source, 0) + 1
            if source_counts:
                book_title = max(source_counts, key=source_counts.get)
                try:
                    author = (await session.execute(
                        select(BookPoolItem.author).where(
                            BookPoolItem.channel_id == channel_id,
                            BookPoolItem.title == book_title,
                        ).limit(1)
                    )).scalar_one_or_none()
                except Exception as e:
                    logger.warning("质量审核读取书籍作者失败，降级为仅书名锚: {}", e)

    # 素材原文锚点：截断到配置长度——锚点只需支撑事实核对（人名/书名/年份），
    # 全文注入会撑爆上下文且稀释审核注意力
    max_chars = settings.QUALITY_CHECK_ANCHOR_MAX_CHARS
    anchor_lines = []
    for mid in sorted(materials):
        m = materials[mid]
        content = (m.content or "").strip()[:max_chars]
        anchor_lines.append(
            f"[素材 {mid}] 来源：{m.source or '未知'} | 标题：{m.title or ''}\n原文：{content}"
        )
    return {
        "segments": segments,
        "channel_type": channel_type or "news",
        "book_title": book_title or "无（非书籍解读类）",
        "author": author or "未提供（不得编造作者姓名）",
        "material_anchors": "\n\n".join(anchor_lines) or "无",
    }


def _build_prompt(ctx: dict) -> str:
    """按模板构建审核 prompt（模板文件维护，禁硬编码）。"""
    from app.workflow.llm.rewriter import _load_prompt_file
    template = _load_prompt_file("quality_check.txt")
    segments_text = "\n\n".join(
        f"【第 {s.get('seq')} 段｜{s.get('title', '')}】\n{s.get('content', '')}"
        for s in ctx["segments"]
    )
    return template.format(
        channel_type=ctx["channel_type"],
        book_title=ctx["book_title"],
        author=ctx["author"],
        material_anchors=ctx["material_anchors"],
        segments_text=segments_text,
    )


def _parse_llm_report(raw: str) -> dict | None:
    """解析 LLM 审核结果，结构非法时返回 None（调用方降级为未审核）。

    与 rewriter._parse_llm_response 同思路：先剥 markdown 围栏再 json.loads，
    逐条校验 issue 字段——issue_type 不在枚举内的条目丢弃而非整次失败，
    因为 LLM 对枚举的遵守是概率性的，一条自造维度不代表整体不可信。
    """
    cleaned = _MARKDOWN_FENCE_PAT.sub("", raw.strip()).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    issues = []
    for item in data.get("issues") or []:
        if not isinstance(item, dict):
            continue
        if item.get("issue_type") not in _ISSUE_TYPES:
            continue
        if item.get("severity") not in _SEVERITIES:
            continue
        try:
            seq = int(item.get("seq"))
        except (TypeError, ValueError):
            continue
        issues.append({
            "seq": seq,
            "issue_type": item["issue_type"],
            "severity": item["severity"],
            "evidence": str(item.get("evidence") or "")[:500],
            "suggestion": str(item.get("suggestion") or "")[:500],
        })
    # severity 按等级降序，前端与日志先看到最严重的问题
    issues.sort(key=lambda x: (-_SEVERITY_ORDER[x["severity"]], x["seq"]))
    return {
        "passed": bool(data.get("pass")) and not issues,
        "issues": issues,
        "issue_count": len(issues),
    }


async def run_quality_check(workflow_id: str, script_id: int) -> dict:
    """执行语义级质量审核并落库报告。

    Returns:
        {"quality_check": {passed, issue_count, alert_count, skipped, skipped_reason}}
        键名 "quality_check" 包裹的原因：_run_step 会把 result 合并进工作流
        context，裸字段会与 script_id 等既有键冲突，断点续跑时被覆盖。

    Raises:
        不主动抛业务异常：审核是旁路告警环节，任何失败都降级为 skipped
        返回，由 _run_step 记录为步骤成功（P1 语义：审核失败 ≠ 工作流失败）。
    """
    result = {
        "quality_check": {
            "passed": True, "issue_count": 0, "alert_count": 0,
            "skipped": False, "skipped_reason": None,
        }
    }
    if not settings.QUALITY_CHECK_ENABLED:
        result["quality_check"].update(skipped=True, skipped_reason="disabled")
        logger.info("质量审核已关闭（QUALITY_CHECK_ENABLED=False），跳过 workflow_id={}", workflow_id)
        return result

    try:
        ctx = await _load_context(workflow_id, script_id)
        if ctx is None:
            result["quality_check"].update(skipped=True, skipped_reason="no_script")
            logger.warning("质量审核跳过：稿件不存在或无分段 script_id={}", script_id)
            return result

        prompt = _build_prompt(ctx)
        # 复用 rewriter 的 LLM 调用封装：预算检查/频率等待/用量记录/重试全部继承
        from app.workflow.llm.rewriter import _call_llm
        raw = await _call_llm(prompt)

        parsed = _parse_llm_report(raw or "")
        if parsed is None:
            # 非法 JSON 降级为「未审核」：宁可漏审不可误杀，也绝不阻塞 tts
            result["quality_check"].update(skipped=True, skipped_reason="invalid_llm_response")
            logger.warning(
                "质量审核 LLM 返回非法 JSON，降级为未审核 workflow_id={} script_id={} raw[:120]={}",
                workflow_id, script_id, (raw or "")[:120],
            )
            return result

        alert_threshold = _SEVERITY_ORDER.get(
            settings.QUALITY_CHECK_ALERT_SEVERITY, _SEVERITY_ORDER["medium"]
        )
        alert_count = sum(
            1 for i in parsed["issues"]
            if _SEVERITY_ORDER[i["severity"]] >= alert_threshold
        )

        # 完整报告落库 script.quality_report（admin-web 从稿件接口读取展示）
        report = {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "passed": parsed["passed"],
            "issue_count": parsed["issue_count"],
            "alert_count": alert_count,
            "issues": parsed["issues"],
        }
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    update(Script).where(Script.id == script_id)
                    .values(quality_report=report)
                )

        result["quality_check"].update(
            passed=parsed["passed"],
            issue_count=parsed["issue_count"],
            alert_count=alert_count,
        )
        if parsed["issues"]:
            # 告警日志按 severity 分级：达到阈值才 warning，low 只 info，
            # 避免 low 级噪音刷满运行日志掩盖真告警
            for issue in parsed["issues"]:
                log = (
                    logger.warning
                    if _SEVERITY_ORDER[issue["severity"]] >= alert_threshold
                    else logger.info
                )
                log(
                    "[质量审核] workflow_id={} 第{}段 {}[{}]: {} → {}",
                    workflow_id, issue["seq"], issue["issue_type"],
                    issue["severity"], issue["evidence"], issue["suggestion"],
                )
        logger.info(
            "质量审核完成 workflow_id={} script_id={} passed={} issues={} alerts={}",
            workflow_id, script_id, parsed["passed"], parsed["issue_count"], alert_count,
        )
        return result
    except Exception as e:
        # 防御性兜底：审核环节任何异常（含 LLM 网络/预算超限）都不阻断工作流
        logger.warning("质量审核异常（降级为未审核，不阻断工作流）workflow_id={}: {}", workflow_id, e)
        result["quality_check"].update(skipped=True, skipped_reason=f"error: {e}")
        return result
