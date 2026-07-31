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

1. intro（开场白）：必须以 "{{date_placeholder}}，" 开头（占位符 {{date_placeholder}} 会在运行时替换为"今天是X月X日星期X"），然后约 60-80 字，欢迎语 + 频道定位介绍 + 今日要闻引导。要体现频道特色，如科技频道可强调"前沿"，财经频道可强调"洞察"。
2. outro（结尾）：约 60-80 字，总结语 + 分享引导 + 期待再会。与开场白风格呼应。
3. constraint（敏感词约束）：针对频道内容特点的额外约束，如财经频道需强调"不构成投资建议"，健康频道需强调"不替代医疗诊断"。
4. template（改写模板）：完整的改写 prompt 模板，参考通用模板结构，但语气、风格、术语解释要贴合频道特色。模板中保留占位符 {{title}} {{content}} {{source}} {{category}} {{source_url}} {{words_per_segment}} {{segment_duration}}。模板中须包含"每段新闻正文最后用一句话向听众提出引发思考的问题"的要求，问题需紧扣本段新闻核心。

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
    allowed, reason = check_budget(service_type="llm")
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
        # exc_info=True 保留 traceback，便于排查 LLM 网关/超时/认证类问题
        logger.error("频道提示词生成 LLM 调用失败: %s", e, exc_info=True)
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
        # exc_info=True 保留解析栈，raw[:200] 限制日志体积避免爆盘
        logger.error("频道提示词 LLM 响应 JSON 解析失败: %s, raw=%s", e, raw[:200], exc_info=True)
        raise ValueError(f"LLM 响应 JSON 解析失败: {e}") from e

    # 字段校验：缺失字段填空字符串，避免 None 污染前端
    return {
        "intro_prompt": data.get("intro", "").strip(),
        "outro_prompt": data.get("outro", "").strip(),
        "constraint_prompt": data.get("constraint", "").strip(),
        "rewrite_template": data.get("template", "").strip(),
    }


# BGM 推荐元提示词：引导 LLM 从可用列表中选择最匹配频道的 BGM
_BGM_RECOMMEND_TEMPLATE = """你是一位专业的电台音乐编辑。请根据频道定位，从可用 BGM 列表中选择最匹配频道的背景音乐。

频道名称：{name}
频道描述：{description}

可用 BGM 列表（path 是文件路径，name 是 BGM 名称）：
{bgm_list_json}

选择原则：
1. BGM 风格要与频道内容定位匹配（如科技频道适合电子/轻音乐，财经频道适合稳重的钢琴曲）
2. BGM 应为衬底音乐，不喧宾夺主，节奏舒缓
3. 优先选择预制 BGM（category=预制），其次自定义

输出格式（严格 JSON，仅输出 JSON 本身）：
{{
  "path": "选中的 BGM path",
  "reason": "选择理由（30字以内）"
}}

禁止：
- 不要输出 JSON 以外的任何内容
- 不要编造不在列表中的 BGM
"""


async def recommend_bgm_for_channel(
    name: str, description: str, bgm_list: list[dict],
) -> dict:
    """调用 LLM 为频道推荐最匹配的 BGM。

    Args:
        name: 频道名称
        description: 频道描述
        bgm_list: 可用 BGM 列表（来自 _scan_bgm_files）

    Returns:
        {path, reason} 推荐结果

    Raises:
        ValueError: LLM 响应解析失败、预算超限或推荐了不存在的 BGM
    """
    allowed, reason = check_budget(service_type="llm")
    if not allowed:
        logger.warning("AI 预算超限，跳过 BGM 推荐: %s", reason)
        raise ValueError(f"AI 预算超限: {reason}")

    # 构造 BGM 列表摘要供 LLM 选择，避免传完整 path 前缀干扰
    bgm_summary = [
        {"path": b["path"], "name": b["name"], "category": b["category"]}
        for b in bgm_list
    ]
    prompt = _BGM_RECOMMEND_TEMPLATE.format(
        name=name,
        description=description or "无描述",
        bgm_list_json=json.dumps(bgm_summary, ensure_ascii=False, indent=2),
    )

    try:
        resp = await _get_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            timeout=settings.LLM_TIMEOUT_SEC,
        )
    except Exception as e:
        logger.error("BGM 推荐 LLM 调用失败: %s", e, exc_info=True)
        raise ValueError(f"LLM 调用失败: {e}") from e

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
        logger.error("BGM 推荐 LLM 响应 JSON 解析失败: %s, raw=%s", e, raw[:200], exc_info=True)
        raise ValueError(f"LLM 响应 JSON 解析失败: {e}") from e

    recommended_path = data.get("path", "").strip()
    # 校验推荐的 path 确实在可用列表中，防止 LLM 幻觉返回不存在的 BGM
    valid_paths = {b["path"] for b in bgm_list}
    if recommended_path not in valid_paths:
        logger.warning("LLM 推荐了不存在的 BGM: %s, 退化为列表第一个", recommended_path)
        recommended_path = bgm_list[0]["path"] if bgm_list else None

    return {
        "path": recommended_path,
        "reason": data.get("reason", "").strip(),
    }


# RSS 源 + 关键词推荐元提示词：引导 LLM 根据频道定位选择最匹配的源子集与过滤关键词
# 与 BGM 推荐模板风格保持一致，便于后续扩展为多字段联合推荐
_RSS_RECOMMEND_TEMPLATE = """你是一位专业的新闻编辑。请根据频道定位，从可用 RSS 源列表中选择最匹配该频道的源，并生成对应的关键词过滤。

频道名称：{name}
频道描述：{description}

可用 RSS 源列表（name 是源名称，category_hint 是品类提示）：
{rss_list_json}

选择原则：
1. 选择的 RSS 源应与频道内容定位强相关（如科技频道选择科技类源，财经频道选择财经类源）
2. 源数量控制在 3-8 个之间，避免过多导致素材冗余或过少导致素材不足
3. 关键词应能精准过滤频道相关主题，避免与频道无关的素材入库
4. 关键词数量控制在 5-15 个，使用逗号分隔
5. 关键词应涵盖频道核心主题、相关品牌/产品、行业术语等

输出格式（严格 JSON，仅输出 JSON 本身）：
{{
  "rss_sources": ["源名称1", "源名称2"],
  "keywords": "关键词1,关键词2,关键词3",
  "reason": "选择理由（50字以内）"
}}

禁止：
- 不要输出 JSON 以外的任何内容
- 不要编造不在列表中的 RSS 源名称
- rss_sources 必须使用列表中存在的 name 字段
"""


async def recommend_rss_keywords_for_channel( # NOSONAR
    name: str, description: str, rss_list: list[dict],
) -> dict:
    """调用 LLM 为频道推荐 RSS 源子集与关键词过滤。

    Args:
        name: 频道名称
        description: 频道描述
        rss_list: 可用 RSS 源列表（来自 list_rss_sources 路由）

    Returns:
        {rss_sources, keywords, reason} 推荐结果
        - rss_sources: 推荐的源名称列表（已过滤掉 LLM 幻觉返回的不存在源）
        - keywords: 逗号分隔的关键词字符串
        - reason: 推荐理由

    Raises:
        ValueError: LLM 响应解析失败、预算超限或无可用 RSS 源
    """
    if not rss_list:
        raise ValueError("无可用 RSS 源，请先在 rss.yaml 中配置")

    allowed, reason = check_budget(service_type="llm")
    if not allowed:
        logger.warning("AI 预算超限，跳过 RSS 源推荐: %s", reason)
        raise ValueError(f"AI 预算超限: {reason}")

    # 仅传递 LLM 决策需要的字段，避免 url/qps 等无关信息干扰选择
    rss_summary = [
        {"name": s.get("name", ""), "category_hint": s.get("category_hint", "")}
        for s in rss_list
    ]
    prompt = _RSS_RECOMMEND_TEMPLATE.format(
        name=name,
        description=description or "无描述",
        rss_list_json=json.dumps(rss_summary, ensure_ascii=False, indent=2),
    )

    try:
        resp = await _get_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            timeout=settings.LLM_TIMEOUT_SEC,
        )
    except Exception as e:
        logger.error("RSS 源推荐 LLM 调用失败: %s", e, exc_info=True)
        raise ValueError(f"LLM 调用失败: {e}") from e

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
        logger.error("RSS 源推荐 LLM 响应 JSON 解析失败: %s, raw=%s", e, raw[:200], exc_info=True)
        raise ValueError(f"LLM 响应 JSON 解析失败: {e}") from e

    # 校验推荐的源名称确实在可用列表中，过滤 LLM 幻觉返回的不存在源
    valid_names = {s.get("name", "") for s in rss_list}
    recommended_sources = [
        s for s in data.get("rss_sources", []) if s in valid_names
    ]
    # 过滤后为空时退化为不推荐（让前端走全局模式），避免锁死频道
    if not recommended_sources:
        logger.warning(
            "LLM 推荐的 RSS 源全部不在可用列表中: %s",
            data.get("rss_sources", []),
        )

    # 关键词清洗：去除空白项与重复项，保持逗号分隔格式与前端一致
    raw_keywords = data.get("keywords", "")
    keywords_list = [k.strip() for k in raw_keywords.split(",") if k.strip()]
    # 去重保序，避免 LLM 返回重复关键词
    seen = set()
    deduped_keywords = []
    for k in keywords_list:
        if k not in seen:
            seen.add(k)
            deduped_keywords.append(k)
    keywords = ",".join(deduped_keywords)

    return {
        "rss_sources": recommended_sources,
        "keywords": keywords,
        "reason": data.get("reason", "").strip(),
    }
