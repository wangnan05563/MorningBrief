"""频道提示词 AI 自动生成服务。

根据频道名称与描述，调用 LLM 生成频道级的开场白、结尾、敏感词约束、改写模板。
生成的提示词可由用户在前端手动编辑后保存，实现"AI 自动生成 + 人工编辑"工作流。

复用 rewriter.py 的 LLM 客户端与预算控制逻辑，保持调用风格一致。
"""
import json
import logging

from openai import AsyncOpenAI

from app.config import get_settings
from app.core.ai_budget import check_budget, record_call

logger = logging.getLogger(__name__)
settings = get_settings()

# 客户端缓存（与 rewriter._get_client 同策略：配置变更时自动重建）
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """获取 LLM 客户端（缓存实例，配置变更时重建）。"""
    global _client
    cache_key = (settings.LLM_API_KEY, settings.LLM_BASE_URL)
    if _client is None or getattr(_client, "_cache_key", None) != cache_key:
        _client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        _client._cache_key = cache_key  # type: ignore[attr-defined]
    return _client


# 生成提示词的元提示词：引导 LLM 按频道定位产出 4 类提示词
_META_PROMPT_TEMPLATE = """你是一位专业的语音新闻节目制作人。请根据频道信息，为该频道生成个性化的语音新闻播报提示词。

频道名称：{name}
频道描述：{description}

请生成以下 4 个字段，每个字段都要贴合频道定位与受众特点：

1. intro（开场白）：约 60-80 字，欢迎语 + 频道定位介绍 + 今日要闻引导。要体现频道特色，如科技频道可强调"前沿"，财经频道可强调"洞察"。
2. outro（结尾）：约 60-80 字，总结语 + 分享引导 + 期待再会。与开场白风格呼应。
3. constraint（敏感词约束）：针对频道内容特点的额外约束，如财经频道需强调"不构成投资建议"，健康频道需强调"不替代医疗诊断"。
4. template（改写模板）：完整的改写 prompt 模板，参考通用模板结构，但语气、风格、术语解释要贴合频道特色。模板中保留占位符 {{title}} {{content}} {{source}} {{category}} {{source_url}} {{words_per_segment}} {{segment_duration}}。

输出格式（严格 JSON，仅输出 JSON 本身）：
{{
  "intro": "开场白文本",
  "outro": "结尾文本",
  "constraint": "敏感词约束文本",
  "template": "完整的改写模板文本"
}}

禁止：
- 不要输出 JSON 以外的任何内容
- 不要输出 Markdown 标记
- 不要编造频道不存在的定位
"""


async def generate_prompts_for_channel(name: str, description: str) -> dict:
    """调用 LLM 为频道生成 4 类提示词。

    Args:
        name: 频道名称
        description: 频道描述

    Returns:
        {intro, outro, constraint, template} 四字段 dict

    Raises:
        ValueError: LLM 响应解析失败或预算超限
    """
    # 预算检查：超限时不发起请求
    allowed, reason = check_budget()
    if not allowed:
        logger.warning("AI 预算超限，跳过频道提示词生成: %s", reason)
        raise ValueError(f"AI 预算超限: {reason}")

    prompt = _META_PROMPT_TEMPLATE.format(name=name, description=description or "无描述")

    try:
        # 频道提示词生成需产出 4 段长文本，比单条改写更耗时
        # 取 LLM_TIMEOUT_SEC × 2 作为超时，避免长响应被截断
        # 用户可在 AI 配置页调整 llm_timeout_sec，此处自动联动
        prompt_timeout = max(settings.LLM_TIMEOUT_SEC * 2, 60)
        resp = await _get_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            timeout=prompt_timeout,
        )
    except Exception as e:
        logger.error("频道提示词生成 LLM 调用失败: %s", e)
        raise ValueError(f"LLM 调用失败: {e}") from e

    # 记录用量
    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    record_call(
        service_type="llm",
        model=settings.LLM_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    raw = resp.choices[0].message.content.strip()
    # 剥离 Markdown 代码块包裹
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("频道提示词 LLM 响应 JSON 解析失败: %s, raw=%s", e, raw[:200])
        raise ValueError(f"LLM 响应 JSON 解析失败: {e}") from e

    # 字段校验：缺失字段填空字符串，避免 None 污染前端
    return {
        "intro_prompt": data.get("intro", "").strip(),
        "outro_prompt": data.get("outro", "").strip(),
        "constraint_prompt": data.get("constraint", "").strip(),
        "rewrite_template": data.get("template", "").strip(),
    }
