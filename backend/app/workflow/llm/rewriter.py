"""LLM 改写模块：选题 → 并发改写 → 敏感词过滤 → 组装稿件（LLD 5.3 / 7.2 / 7.3 / 7.4）。

流程：
1. 从 SQLite material 表查询当日 pending 素材
2. 按热度（LLD 7.2）排序选 5-6 条
3. 并发改写（asyncio.gather），单条调用通义千问 API
4. 敏感词双层过滤（生成前 prompt 约束 + 生成后扫描，LLD 7.3）
5. 组装稿件（开场白 + 改写正文 + 结尾）
6. 存入 script 表
"""
import asyncio
import json
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from openai import AsyncOpenAI
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from sqlalchemy import func, select, update

from app.config import get_settings
from app.core.ai_budget import check_budget, record_call
from app.database import AsyncSessionLocal
from app.models import Material, Script
from app.models.material import MaterialStatus
from app.models.script import ScriptStatus
from app.workflow.llm import sensitive_filter
from app.workflow.llm.heat_score import heat_score
settings = get_settings()

# Prompt 模板与敏感词表路径（与模块同级目录）
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "rewrite.txt"
SENSITIVE_WORDS_PATH = Path(__file__).parent / "sensitive_words.txt"

# 模块加载时初始化敏感词自动机（避免每次改写重复加载）
sensitive_filter.load_words(str(SENSITIVE_WORDS_PATH))

# 选题数量：10 条新闻，覆盖主要品类又不超出单期时长
# 从 6 调整到 10：部分素材可能因敏感词/JSON 解析失败，增加候选提高成功率
# 最终组装稿件时仅使用成功段，不超过 MAX_SCRIPT_SEGMENTS 限制
SELECT_TOP_N = 10
SELECT_MIN_N = 5
# 有效段数下限：少于 3 段无法构成一期节目
MIN_VALID_SEGMENTS = 3
# 当日无 pending 素材时，向前回溯查询最近 N 天的 pending 素材
# 场景：RSS 源无新内容时爬虫去重导致当日采集 0 条，回溯避免工作流直接失败
# 取 7 而非 3：覆盖周末+小长假场景（周五素材到周一已 3 天，原值会漏掉），
# 同时 7 天内素材时效性仍在新闻可接受范围内
FALLBACK_DAYS = 7
# 稿件最大段数：组装时仅取前 N 条成功段，避免段数过多导致节目超长
# 与 SELECT_TOP_N 对齐：10 条候选全部可用时不浪费，目标 900s 时每段约 655 字（LLM 可达成）
MAX_SCRIPT_SEGMENTS = 10
# 基础播报语速（字/分钟）：Edge-TTS zh-CN-YunyangNeural +0% 实测约 303 字/分
# 取 330 而非 303：LLM 实际生成字数通常为 prompt 要求的 80%-90%（±10% 措辞下），
# 高出 9% 的余量补偿 LLM 生成不足，使最终 TTS 时长落在目标范围内
# 数学关系：330×1.5=495 字/分（+50% rate），LLM 85% 达成 → 实际约 420 字/分 → 接近实测 454
WORDS_PER_MINUTE = 330
# 默认目标节目时长（秒），与 settings.TARGET_DURATION_SEC 对齐
DEFAULT_TARGET_DURATION_SEC = 600

# LLM 并发上限：限制同时发起的 LLM 请求数，避免瞬间打爆 API 频率限制
# AI_BUDGET_RATE_LIMIT_PER_MIN 默认 20 次/分钟，10 条无限制并发 + tenacity 重试
# 会在 3s 内产生 30 次调用尝试，全部被 check_budget 拦截
# 3 并发：10 条分 4 批，每批约 3s，总耗时约 12s，且不会超出频率预算
_LLM_CONCURRENCY_LIMIT = 3

# 字数硬约束重试命中率累计指标（自进程启动以来累计，重启清零）
# 用于运维评估 P2-2 改进效果：触发率反映 LLM 字数缩水严重程度，
# 改善率反映硬约束 prompt 的有效性，未改善率反映需要进一步优化的场景
_WORD_COUNT_RETRY_STATS = {
    "triggered": 0,    # 触发硬约束重试的次数（首次生成字数 <70%）
    "improved": 0,     # 重试后字数有改善的次数
    "not_improved": 0,  # 重试后字数未改善（保留首次结果）的次数
    "total_calls": 0,  # _rewrite_one 总调用次数（基线，用于算触发率）
}


def get_word_count_retry_stats() -> dict:
    """返回字数硬约束重试命中率指标（含派生率）。

    供 /admin/api/v1/stats/llm-metrics 端点调用，运维仪表盘可视化：
    - trigger_rate = triggered / total_calls：触发率，反映 LLM 字数缩水严重程度
    - improve_rate = improved / triggered：改善率，反映硬约束 prompt 有效性
    - not_improve_rate = not_improved / triggered：未改善率，反映需进一步优化场景占比

    Returns:
        原始计数 + 派生率（百分比 0-100，保留 2 位小数），total_calls=0 时率为 0
    """
    total = _WORD_COUNT_RETRY_STATS["total_calls"]
    triggered = _WORD_COUNT_RETRY_STATS["triggered"]
    improved = _WORD_COUNT_RETRY_STATS["improved"]
    not_improved = _WORD_COUNT_RETRY_STATS["not_improved"]

    return {
        "total_calls": total,
        "triggered": triggered,
        "improved": improved,
        "not_improved": not_improved,
        # 派生率：分母为 0 时返回 0.0 避免 ZeroDivisionError
        "trigger_rate": round(triggered / total * 100, 2) if total > 0 else 0.0,
        "improve_rate": round(improved / triggered * 100, 2) if triggered > 0 else 0.0,
        "not_improve_rate": round(not_improved / triggered * 100, 2) if triggered > 0 else 0.0,
    }


# 告警阈值：单次工作流粒度的即时告警，触发即输出 WARNING
# 触发率 > 50%：LLM 字数缩水严重，应优化 prompt 或更换模型
# 改善率 < 30%：硬约束后缀效果不佳，应更换重试策略
_TRIGGER_RATE_ALERT_THRESHOLD = 50.0
_IMPROVE_RATE_ALERT_THRESHOLD = 30.0


def _emit_word_count_retry_stats(workflow_id: str, stats_before: dict) -> None:
    """输出本轮 + 累计 LLM 字数重试指标，触发阈值时告警。

    在 rewrite() 主函数末尾调用，便于运维观察：
    - 本轮指标：单次工作流粒度的即时反馈，高触发率或低改善率立即告警
    - 累计指标：进程启动以来的整体趋势，供 /llm-metrics 端点查询

    Args:
        workflow_id: 工作流 ID，用于日志关联
        stats_before: 本轮 rewrite 开始前的 _WORD_COUNT_RETRY_STATS 快照
    """
    after = _WORD_COUNT_RETRY_STATS
    # 本轮贡献 = 当前快照 - 开始前快照  # NOSONAR S125: 中文说明性注释，非注释掉的代码
    round_calls = after["total_calls"] - stats_before.get("total_calls", 0)
    round_triggered = after["triggered"] - stats_before.get("triggered", 0)
    round_improved = after["improved"] - stats_before.get("improved", 0)
    round_not_improved = after["not_improved"] - stats_before.get("not_improved", 0)

    # 本轮派生率：本轮无调用时分母为 0，跳过派生率计算避免 ZeroDivisionError
    round_trigger_rate = round(round_triggered / round_calls * 100, 2) if round_calls > 0 else 0.0
    round_improve_rate = round(round_improved / round_triggered * 100, 2) if round_triggered > 0 else 0.0

    # INFO 日志：本轮 + 累计快照，便于运维通过日志观察趋势
    logger.info(
        "LLM 字数重试指标 workflow_id=%s 本轮 calls=%d triggered=%d improved=%d not_improved=%d"
        " trigger_rate=%.2f%% improve_rate=%.2f%% | 累计 calls=%d triggered=%d improved=%d",
        workflow_id, round_calls, round_triggered, round_improved, round_not_improved,
        round_trigger_rate, round_improve_rate,
        after["total_calls"], after["triggered"], after["improved"],
    )

    # 告警：仅在本轮有触发时检查改善率，避免无触发场景误告警
    # 触发率告警：> 50% 说明 LLM 字数缩水严重
    if round_calls > 0 and round_trigger_rate > _TRIGGER_RATE_ALERT_THRESHOLD:
        logger.warning(
            "LLM 字数重试触发率 %.2f%% 超过 %.0f%% 阈值 workflow_id=%s"
            "（本轮 %d/%d 调用触发），LLM 字数缩水严重，建议优化 prompt 或更换模型",
            round_trigger_rate, _TRIGGER_RATE_ALERT_THRESHOLD,
            workflow_id, round_triggered, round_calls,
        )

    # 改善率告警：< 30% 说明硬约束后缀效果不佳（仅在本轮有触发时检查）
    if round_triggered > 0 and round_improve_rate < _IMPROVE_RATE_ALERT_THRESHOLD:
        logger.warning(
            "LLM 字数重试改善率 %.2f%% 低于 %.0f%% 阈值 workflow_id=%s"
            "（本轮 %d/%d 触发后改善），硬约束后缀效果不佳，建议更换重试策略",
            round_improve_rate, _IMPROVE_RATE_ALERT_THRESHOLD,
            workflow_id, round_improved, round_triggered,
        )

# 开场白与结尾（固定文案，约 180 字 ≈ 50s 播报）
# {date_placeholder} 由 _assemble_script 动态替换为"今天是7月15日星期三"
# 文案风格：口语化、有温度，像真人主播与听众聊天而非念稿
INTRO_TEXT = (
    "{date_placeholder}，"
    "欢迎收听今天的新闻节目，我是您的新闻主播。"
    "忙碌的清晨，让我用几分钟时间，陪您了解今天最值得关注的事儿。"
    "无论您在通勤路上，还是正在准备一天的工作，"
    "希望这份简明扼要的新闻速递，能帮您快速掌握外界动态。"
    "话不多说，我们一起进入今天的要闻。"
)
OUTRO_TEXT = (
    "以上就是今天节目的全部内容，感谢您的收听。"
    "世界很大，变化很快，但您愿意花几分钟听听这些故事，"
    "本身就是一件很了不起的事。"
    "如果今天的节目对您有帮助，欢迎分享给身边的朋友，"
    "我们明天同一时间再会，祝您今天一切顺利。"
)

# 第一层过滤：生成前 prompt 约束（写入 prompt 末尾，引导 LLM 主动规避）
PROMPT_CONSTRAINT = """
重要约束：
- 严禁出现以下类型词汇：政治敏感、暴力、色情、歧视性表达
- 严禁编造未经证实的信息
- 严禁出现具体人名负面评价
"""

# JSON 输出格式后缀：频道级模板可能省略 JSON 格式要求时自动追加
# 频道模板若缺少此格式，LLM 会返回纯文本导致 json.loads 失败（char 0）
# 用 {{ }} 转义 JSON 花括号，与默认 rewrite.txt 模板一致
_JSON_FORMAT_SUFFIX = """

## 输出格式（严格 JSON，仅输出 JSON 本身，不要输出任何其他内容）
{{
  "title": "改写后的标题（≤20字，不含引号、编号、Markdown）",
  "content": "改写后的正文（{words_per_segment}字±10%，纯文本，段落之间用空行分隔，不含标题/编号/Markdown符号/解释性文字）",
  "estimated_duration": {segment_duration},
  "source_url": "{source_url}"
}}

## 禁止
- 不要输出 JSON 以外的任何内容（无引导语、无注释、无解释）
- 不要输出 Markdown 标记（如 **、#、-、``` 等）
- content 字段内不要包含标题、序号、列表符号、分点编号
- content 字段只能是适合语音播报的连续纯文本，段落用空行分隔
- 不要编造未在原文出现的事实、数字、引语
"""


# 思考问题后缀：频道开启 enable_thinking_question 时追加到 prompt 末尾
# 作为"补充要求"动态注入（独立于 rewrite.txt 的 9 条改写要求），关闭时不追加
_THINKING_QUESTION_SUFFIX = """

## 补充要求（结尾思考）
正文最后用一句话向听众提出引发思考的问题（15-25字），问题需紧扣本段新闻核心，激发听众联想或判断，如"这项政策落地后，你会是受益者吗？""技术进步带来的便利，是否也让我们失去了什么？"。问题以问号结尾，语气亲切自然，像与朋友聊天。思考问题计入总字数。
"""


# 字数硬约束后缀：当首次生成字数严重不足（<70%）时追加到 prompt 末尾触发重试
# 场景：中文 LLM 普遍存在"字数缩水"现象，prompt 中 ±10% 约束常被忽视
# 此后缀用更强烈的措辞 + 明确的字数下限数字，提升 LLM 遵守率
# 仅在字数低于 70% 时触发（避免频繁重试浪费 LLM 调用配额）
# 关键数字 {words_min} 前置到首行，避免 LLM 在长后缀中忽视
_WORD_COUNT_ENFORCE_SUFFIX = """

## 字数硬约束（必须严格遵守，否则任务失败）
本次正文必须达到 {words_min}-{words_max} 字（上次仅 {actual_words} 字，严重不足）。
扩充方法（禁止重复内容或填充无意义连接词）：
- 补充背景与细节：事件时间线、相关历史、具体数字、地点、人物言论
- 补充影响与观点：对相关群体/行业/社会的具体影响、不同立场的人对此事的看法
"""


# ===== 时长/字数/语速三参数联动 =====
# 数学关系：时长(秒) = 总字数 / (基础语速 × 语速倍率) × 60
# 反算：总字数 = 时长 × 基础语速 × 语速倍率 / 60
# 用户在 AI 配置页调整 target_duration_sec 或 edge_rate 时，
# rewriter 按此公式反算所需字数，动态调整每段 prompt 的字数要求
def _parse_edge_rate(rate_str: str) -> float:
    """解析 Edge-TTS rate 字符串为倍率。

    支持格式："+50%" / "-10%" / "+50" / "-10" / "50%" / ""
    返回 1.0 + percent/100，如 "+50%" → 1.5，"-10%" → 0.9
    倍率限制在 [0.5, 2.5] 避免极端值导致字数反算失真。
    """
    if not rate_str:
        return 1.0
    s = str(rate_str).strip().replace('%', '').replace('+', '')
    try:
        percent = float(s)
        return max(0.5, min(2.5, 1.0 + percent / 100.0))
    except ValueError:
        return 1.0


def _get_rate_multiplier() -> float:
    """获取当前 TTS Provider 的实际语速倍率。

    按 settings.TTS_PROVIDER 分支解析对应 provider 的语速字段：
    - edge: 解析 EDGE_TTS_RATE（如 "+50%" → 1.5）
    - tencent: TENCENT_TTS_SPEED（0=1.0, 2=1.2, -2=0.8 近似线性映射）
    - aliyun: 默认 1.0（阿里云 NLS 无语速调节字段）

    rewriter 用此倍率校正估算时长，stitch 用此倍率动态计算允许范围。
    """
    provider = (settings.TTS_PROVIDER or "aliyun").lower()
    if provider == "edge":
        return _parse_edge_rate(settings.EDGE_TTS_RATE)
    if provider == "tencent":
        # 腾讯云 speed: 0=默认, 正数加快, 负数减慢，近似每 +1 = +10%
        return max(0.5, min(2.5, 1.0 + settings.TENCENT_TTS_SPEED * 0.1))
    return 1.0


def _get_target_duration_sec() -> int:
    """读取目标节目时长（秒），fallback 到默认值 600。"""
    val = getattr(settings, "TARGET_DURATION_SEC", None)
    if val is None:
        return DEFAULT_TARGET_DURATION_SEC
    try:
        return max(180, min(1800, int(val)))
    except (ValueError, TypeError):
        return DEFAULT_TARGET_DURATION_SEC


def _calc_target_words(target_sec: int, rate_multiplier: float) -> int:
    """按目标时长 + 实际语速反算所需总字数。

    公式：总字数 = 时长(秒) × 基础语速(字/分) × 倍率 / 60
    例：600s × 210 × 1.5 / 60 = 3150 字（1.5 倍速下需更多字数填满时长）
    """
    return int(target_sec * WORDS_PER_MINUTE * rate_multiplier / 60)


def _calc_segment_words(target_sec: int, rate_multiplier: float) -> tuple[int, int]:
    """计算每段目标字数与段数。

    策略：
    1. 总字数 = 目标时长 × 基础语速 × 倍率 / 60
    2. 扣除开场白+结尾固定字数（约 145 字）= 正文总字数
    3. 段数 = clamp(round(正文总字数 / 350), 3, 6)
       - 350 字/段是经验值：基础语速下约 100s/段，节奏适中
    4. 每段字数 = 正文总字数 / 段数

    Returns:
        (segment_count, words_per_segment)
    """
    total_words = _calc_target_words(target_sec, rate_multiplier)
    intro_outro_words = len(INTRO_TEXT) + len(OUTRO_TEXT)
    body_words = max(300, total_words - intro_outro_words)

    # 段数动态调整：正文越长段数越多，但限制在 [3, 6]
    target_segments = max(MIN_VALID_SEGMENTS, min(MAX_SCRIPT_SEGMENTS, round(body_words / 350)))
    words_per_seg = max(200, int(body_words / target_segments))
    return target_segments, words_per_seg


def _count_content_words(text: str) -> int:
    """统计正文字数（去除空白与标点）。

    中文按字符计数：每个汉字算 1 字，标点与空白不计入。
    英文按空格分词：连续字母数字算 1 词。
    此计数与 LLM prompt 中的"字"语义一致（中文 LLM 通常按字符计）。
    """
    if not text:
        return 0
    # 去除所有空白字符（空格/换行/制表符）
    cleaned = re.sub(r"\s+", "", text)
    # 去除中英文标点（常见标点全角半角均覆盖）
    # ] 放在字符类开头表示字面 ]（否则会被解析为字符类结束符），[ 在字符类内无需转义
    cleaned = re.sub(r"[]，。！？；：、""''（）【】《》—…,.!?;:\"'()<>-]", "", cleaned)
    return len(cleaned)


def _strip_markdown_residue(text: str) -> str:
    """防御性清洗 content 字段中残留的 Markdown 标记。

    场景：LLM 偶发违反"禁止输出 Markdown 标记"约束，在 content 中留下
    加粗/斜体/标题/列表等符号。TTS 朗读时会念出"星号星号""星号""井号"，
    严重影响听感。此处做兜底清理，仅清理已知模式，不破坏正文标点与数学表达。

    清理范围：
    - **xxx** 闭合加粗 → 保留内部文字 xxx
    - **xxx 未闭合加粗 → 保留内部文字 xxx（移除开头的 **）
    - 孤立的 **（未成对）→ 直接移除
    - 行首 # / ## / ### 等 Markdown 标题符号 + 空格 → 移除符号保留标题文字
    - 行首列表符号（* / - / + 后跟空格）→ 移除标记保留正文（LLM 偶发输出列表）
    - 成对斜体 *文字* / _文字_ → 移除分隔符保留内部文字
      （仅当分隔符两侧均非数字/字母时清理，保护数学乘号 1*2*3、a*b、3 * 4）

    注意单星号 * 的处理：早期版本完全放过单个 *（担心误伤数学乘号），
    导致斜体/列表残留的单个 * 被 TTS 念成"星号"。现改为"数学安全"策略：
    两侧都被数字/字母紧邻的 * 视为乘号保留，其余 Markdown 用法的 * 一律清理。
    """
    if not text:
        return text
    # 先清理闭合的 **xxx**（避免被未闭合规则误伤）
    text = re.sub(r"\*\*([^*]+?)\*\*", r"\1", text)
    # 清理未闭合的 **xxx（行内剩余的开头 **）
    text = re.sub(r"\*\*([^*\n]+)", r"\1", text)
    # 清理孤立的 **（未成对出现）
    text = text.replace("**", "")
    # 清理行首 Markdown 标题符号（# / ## / ### 后跟空格）
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 清理行首列表符号（* / - / + 后跟空格）→ 仅移除标记保留正文
    text = re.sub(r"^\s*[\*\-\+]\s+", "", text, flags=re.MULTILINE)
    # 单星号 * 处理（数学安全策略）：
    # 1. 先保护"数学乘号"（两侧均为数字/字母，允许中间空格，如 1*2*3 / 3 * 4 / a*b），
    #    用占位符暂存，避免被后续清理误删。
    #    注：不能用 \w 边界判断——Python \w 在 Unicode 模式下含汉字，会导致中文后的
    #    斜体 * 因"其后为汉字"而被判定为边界外而不匹配，斜体清理整体失效。
    # 2. 成对斜体分隔符 *文字* / _文字_ → 移除分隔符保留内部文字。
    # 3. 清理剩余孤立单个 *（未成对残留 / LLM 噪声），数学乘号已用占位符保护不受影响。
    # 4. 恢复数学乘号占位符。
    _math_asterisk = re.compile(r"([0-9A-Za-z])(\s*)\*(\s*)(?=[0-9A-Za-z])")
    # 用私有区字符作占位符（正常文本绝不会出现），避免与正文冲突
    _math_ph = ""
    text = _math_asterisk.sub(
        lambda m: m.group(1) + m.group(2) + _math_ph + m.group(3), text
    )
    text = re.sub(r"(\*|_)([^*\n_]+?)\1", r"\2", text)
    text = text.replace("*", "")
    text = text.replace(_math_ph, "*")
    return text


# ===== 异常定义（LLD 7.4） =====
# 可重试错误：网络抖动 / 服务端临时问题，指数退避后大概率成功
class LLMRateLimitError(Exception):
    """API 限流（HTTP 429），退避后重试。"""


class LLMTimeoutError(Exception):
    """请求超时，重试。"""


class LLMServiceError(Exception):
    """服务端 5xx 或连接异常，重试。"""


# 不可重试错误：参数/鉴权/内容问题，重试无意义
class LLMAuthError(Exception):
    """鉴权失败（HTTP 401），立即失败并告警运维。"""


class LLMContentError(Exception):
    """内容审核拒绝，改用约束 prompt 重生成一次。"""


class SensitiveHitError(Exception):
    """首次生成命中敏感词，触发二次重生成。"""


class LLMError(Exception):
    """改写流程整体失败的兜底异常。

    携带 failure_details 属性时，包含每条素材的失败原因（供 workflow_step
    记录详细错误，便于前端详情页展示与运维定位）。
    """

    def __init__(self, message: str, failure_details: list[dict] | None = None):
        super().__init__(message)
        # failure_details 结构：[{material_id, title, stage, error_type, error_message}]
        # 仅在 rewrite() 中聚合并发失败时填充，单点失败场景为 None
        self.failure_details = failure_details


# tenacity 重试装饰器（LLD 7.4）
# - stop_after_attempt(3)：最多 3 次（含首次），总耗时上限可控
# - wait_exponential(1, 10)：1s, 2s, 4s... 退避上限 10s，避免雪崩压垮下游
# - retry_if_exception_type：仅可重试错误重试，不可重试错误立即抛出
# - reraise=True：重试耗尽后抛出原异常，保留错误上下文
def _log_retry(retry_state):
    """tenacity before_sleep 回调：重试前记录 warning 日志。

    替代 tenacity.before_sleep_log，因为后者依赖标准库 logging 接口，
    与项目 loguru logger 不兼容。
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "LLM 调用重试 attempt={} wait={:.1f}s exc={}: {}",
        retry_state.attempt_number,
        float(retry_state.next_sleep) if hasattr(retry_state, 'next_sleep') else 0,
        type(exc).__name__ if exc else 'None',
        str(exc)[:200] if exc else '',
    )


llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10, multiplier=1),
    retry=retry_if_exception_type(
        (LLMRateLimitError, LLMTimeoutError, LLMServiceError)
    ),
    before_sleep=_log_retry,
    reraise=True,
)

# 通义千问兼容 OpenAI SDK，复用同一客户端连接池
# 延迟初始化：模块加载时 settings.LLM_API_KEY 可能仍是 .env 占位符，
# 前端通过 AIConfigService 热更新后才会注入真实 key。
# 若在此处固化 _client，前端配置的 Key 无法生效。
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """按需构建 OpenAI 客户端，每次读取最新 settings，兼容配置热更新。

    模块加载时 _client=None，首次调用 _call_llm 时才创建实例。
    若 settings.LLM_API_KEY 变更（前端配置或 .env 修改），
    下次调用会重建客户端，避免占位符固化导致 401。
    """
    global _client
    # 用 (api_key, base_url) 元组作为缓存键，配置变更时自动重建
    cache_key = (settings.LLM_API_KEY, settings.LLM_BASE_URL)
    if _client is None or getattr(_client, "_cache_key", None) != cache_key:
        _client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
        # 附加缓存键到实例，避免重建时丢失
        _client._cache_key = cache_key  # type: ignore[attr-defined]
    return _client


def _is_placeholder_api_key(key: str) -> bool:
    """检测 API key 是否为占位符或无效值。

    覆盖以下场景：
    - 空字符串或纯空白
    - .env.example 中的 <...> 占位符（含 < 或 >）
    - 含中文说明文本（真实 key 只含 ASCII 字符）

    提前拦截避免无效 key 浪费网络往返和重试配额（401 拒绝耗时虽短
    但会消耗 3 次重试 + 退避时间，且日志被笼统的"段数不足"掩盖）。
    """
    if not key or not key.strip():
        return True
    key = key.strip()
    # .env.example 占位符以 < 开头或 > 结尾
    if key.startswith("<") or key.endswith(">"):
        return True
    # 真实 API key 只含 ASCII 字符，含中文说明是未替换的占位符
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        return True
    return False


async def _wait_for_rate_limit_slot(timeout: float = 65) -> bool:  # NOSONAR
    """等待本地频率预算有空位（频率超限时的恢复策略）。

    60s 滑动窗口内的旧记录会随时间过期，轮询 check_budget 直到通过或超时。
    避免 10 条并发 + tenacity 短退避（1-2s）导致的"全部失败"连锁反应：
    tenacity 重试间隔远小于 60s 频率窗口，短退避后重试仍会被 check_budget 拦截。

    Returns:
        True 如果等到空位；False 如果超时或遇到不可恢复的预算超限（token/费用）
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        allowed, reason = check_budget(service_type="llm")
        if allowed:
            return True
        if "频率超限" not in reason:
            # token/费用超限不可恢复，无需等待
            return False
        await asyncio.sleep(3)
    return False


@llm_retry
async def _call_llm(prompt: str) -> str:
    """调用通义千问 API（LLD 7.4 重试策略）。

    异常映射：
    - HTTP 429 RateLimitError → LLMRateLimitError（重试）
    - HTTP 401 AuthenticationError → LLMAuthError（不重试）
    - 超时 APITimeoutError → LLMTimeoutError（重试）
    - 连接异常 APIConnectionError → LLMServiceError（重试）
    - HTTP 5xx InternalServerError → LLMServiceError（重试）

    预算控制：调用前检查三重预算（token/费用/频率），超限直接抛 LLMAuthError
    避免无效请求打到外部 API；调用成功后记录用量更新预算计数。

    频率超限特殊处理：主动等待 60s 滑动窗口滑过后重试，而非立即抛错。
    因为 tenacity 的 wait_exponential(1-10s) 远小于 60s 频率窗口，
    立即抛错后 tenacity 短退避重试仍然会被 check_budget 拦截，导致全部失败。

    其他异常（含内容审核）不在此处映射，由调用方按不可重试处理。
    """
    # 预算检查：超限时不发起请求（避免外部 API 计费）
    allowed, reason = check_budget(service_type="llm")
    if not allowed:
        if "频率超限" in reason:
            # 频率超限：等待 60s 滑动窗口滑过后重试，而非立即抛错
            # tenacity 短退避（1-2s）无法突破 60s 频率窗口，立即抛错会导致
            # 10 条并发全部失败（tenacity 3 次重试均在窗口内，全部被拦截）
            logger.warning("频率超限，等待滑动窗口滑过后重试: %s", reason)
            if not await _wait_for_rate_limit_slot(timeout=65):
                raise LLMAuthError(f"AI 预算超限(不可重试): {reason}")
        else:
            # token/费用超限：不可恢复，立即失败
            logger.warning("AI 预算超限(不可重试)，跳过 LLM 调用: %s", reason)
            raise LLMAuthError(f"AI 预算超限(不可重试): {reason}")

    try:
        resp = await _get_client().chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            timeout=settings.LLM_TIMEOUT_SEC,
        )
    except Exception as e:
        # 按异常类型映射，便于 tenacity 精准判断是否重试
        # 用类名字符串匹配，避免直接 import openai 异常类造成耦合
        type_name = type(e).__name__
        if type_name == "RateLimitError":
            raise LLMRateLimitError(str(e)) from e
        elif type_name == "AuthenticationError":
            raise LLMAuthError(str(e)) from e
        elif type_name == "APITimeoutError":
            raise LLMTimeoutError(str(e)) from e
        elif type_name in ("APIConnectionError", "InternalServerError"):
            raise LLMServiceError(str(e)) from e
        # 其他异常原样抛出，tenacity 不会重试（不在 retry_if_exception_type 列表）
        raise

    # 调用成功后记录用量（更新预算计数 + 持久化）
    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    record_call(
        service_type="llm",
        model=settings.LLM_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return resp.choices[0].message.content


def _build_prompt(
    material: dict,
    words_per_segment: int = 450,
    segment_duration: int = 60,
    extra_constraint: str = None,
    template_text: str = None,
    enable_thinking_question: bool = True,
    style_hint: str = None,
) -> str:
    """构建改写 prompt（读 rewrite.txt 模板，填入素材信息 + 动态字数要求）。

    Args:
        material: 素材 dict，含 title/content/source/category/source_url
        words_per_segment: 每段目标字数（由目标时长 + 语速倍率反算得出）
        segment_duration: 每段预估时长（秒），供 LLM 输出 estimated_duration
        extra_constraint: 额外约束（如敏感词命中后追加的规避要求）
        template_text: 频道级自定义模板，为 None 则读默认 rewrite.txt
        enable_thinking_question: 是否在 prompt 中注入结尾思考问题要求
        style_hint: 风格多样性提示（开场白/过渡词/同义词/段落结构变体），
            None 时不追加。由 _rewrite_one_with_limit 按 seq 号从 style_library 轮换选取
    """
    template = template_text if template_text else PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    # 预计算字数范围，供模板中 {words_min}/{words_max} 使用
    # .format() 不支持表达式，必须预计算后传入
    words_min = int(words_per_segment * 0.9)
    words_max = int(words_per_segment * 1.1)
    prompt = template.format(
        title=material["title"],
        content=material["content"],
        source=material["source"],
        category=material.get("category") or "未分类",
        source_url=material["url"],
        words_per_segment=words_per_segment,
        words_min=words_min,
        words_max=words_max,
        segment_duration=segment_duration,
    )
    # 频道级模板可能省略 JSON 输出格式要求，导致 LLM 返回纯文本
    # 检测模板是否已含 JSON 格式声明（双引号包裹的 title/content 字段），
    # 缺失时追加 JSON 格式后缀，保证 LLM 输出可解析的 JSON
    if template_text and '"title"' not in template_text:
        prompt = prompt + _JSON_FORMAT_SUFFIX.format(
            words_per_segment=words_per_segment,
            segment_duration=segment_duration,
            source_url=material["url"],
        )
    # 风格多样性约束先于思考问题注入：
    # 风格约束含"提问前置"变体（段首提问），与"段尾思考问题"二选一不叠加
    # style_hint 为 None 时（如字数硬约束重试场景）跳过，避免重复追加
    if style_hint:
        prompt = prompt + style_hint
        # style_hint 已含段首提问要求，强制跳过段尾思考问题，避免 LLM 收到矛盾指令
        enable_thinking_question = False
    # 思考问题要求动态注入：开关开启时追加，无论使用默认模板还是频道自定义模板
    # 频道自定义模板通常不含思考问题要求（seed 模板已移除），追加不会重复
    if enable_thinking_question:
        prompt = prompt + _THINKING_QUESTION_SUFFIX
    # 第一层过滤：在 prompt 末尾追加敏感词规避约束，引导 LLM 主动避开
    if extra_constraint:
        prompt = prompt + "\n" + extra_constraint
    return prompt


async def _rewrite_one(  # NOSONAR S3776: 双层过滤改写主逻辑，职责单一不可再拆分
    material: dict,
    words_per_segment: int = 450,
    segment_duration: int = 60,
    retry_with_constraint: bool = False,
    template_text: str = None,
    constraint_text: str = None,
    enable_thinking_question: bool = True,
    style_hint: str = None,
) -> dict:
    """改写单条素材（LLD 7.3 双层过滤）。

    流程：
    1. 构建 prompt（首次无约束，二次追加 constraint）
    2. 调用 LLM（tenacity 自动重试可重试错误）
    3. 解析 JSON 响应
    4. 敏感词检查：
       - 首次命中 → 抛 SensitiveHitError，由上层触发二次重生成
       - 二次仍命中 → 替换兜底（保证稿件可用，记录 warning）

    Args:
        material: 素材 dict
        words_per_segment: 每段目标字数（动态注入 prompt）
        segment_duration: 每段预估时长（秒）
        retry_with_constraint: 是否为二次重生成（追加敏感词约束 prompt）
        template_text: 频道级自定义改写模板，None 则用默认 rewrite.txt
        constraint_text: 频道级敏感词约束，None 则用默认 PROMPT_CONSTRAINT
        enable_thinking_question: 是否在 prompt 中注入结尾思考问题要求
        style_hint: 风格多样性提示（开场白/过渡词/同义词/段落结构变体），
            None 时不追加。由 _rewrite_one_with_limit 按 seq 号轮换注入

    Returns:
        {title, content, estimated_duration, source_url, material_id, cover_url}
    """
    # 字数重试命中率统计基线：每次进入 _rewrite_one 计 1
    # 用于计算触发率 = triggered / total_calls
    _WORD_COUNT_RETRY_STATS["total_calls"] += 1

    # 频道级约束优先，回退到默认 PROMPT_CONSTRAINT
    effective_constraint = constraint_text if constraint_text is not None else PROMPT_CONSTRAINT
    prompt = _build_prompt(
        material,
        words_per_segment=words_per_segment,
        segment_duration=segment_duration,
        extra_constraint=effective_constraint if retry_with_constraint else None,
        template_text=template_text,
        enable_thinking_question=enable_thinking_question,
        style_hint=style_hint,
    )
    raw = await _call_llm(prompt)

    # 空 content 防御：某些 API 在限流/审核拒绝时返回 200 + 空 content
    # 不做检查会导致 json.loads("") 报 char 0，丢失真实原因
    if not raw or not raw.strip():
        logger.error(
            "LLM 返回空 content material_id={} prompt_len={}",
            material["id"], len(prompt),
        )
        raise LLMContentError(
            f"LLM 返回空 content（可能被限流或审核拒绝），prompt 长度={len(prompt)}"
        )

    # LLM 偶尔会输出 Markdown 代码块包裹，剥离后再解析
    text = raw.strip()
    if text.startswith("```"):
        # 去掉首尾 ``` 行，兼容 ```json 与 ``` 两种写法
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # JSON 解析失败视为不可重试错误，记录原始响应便于排查
        # 把 raw 前 300 字存入错误消息，使 failure_details 能直接展示
        logger.error(
            "LLM 响应 JSON 解析失败 material_id={} raw_len={} raw_preview={}",
            material["id"], len(raw), raw[:300],
        )
        raise LLMContentError(
            f"JSON 解析失败: {e}，raw 前300字: {raw[:300]}"
        ) from e

    # 防御性清洗 content 字段中残留的 Markdown 标记
    # 关键修复：主解析路径（正常生成 ~95%+ 走这里）此前从未调用 _strip_markdown_residue，
    # 导致 ** / 单个 * 等符号直达 TTS 被念成"星号星号"/"星号"（见 wf-0011 同类问题）。
    # 仅"字数不足重试"分支走 _parse_llm_response 才清洗，覆盖面严重不足。
    # 此处与主/次路径统一清洗，保证任何路径返回的 content 都已去 Markdown。
    if isinstance(data, dict) and isinstance(data.get("content"), str):
        original = data["content"]
        cleaned = _strip_markdown_residue(original)
        if cleaned != original:
            logger.warning(
                "LLM 输出 content 含 Markdown 残留，已清洗 material_id=%s",
                material["id"],
            )
            data["content"] = cleaned

    # 第二层过滤：生成后词表扫描
    content = data.get("content", "")
    if sensitive_filter.contains(content):
        if retry_with_constraint:
            # 二次仍命中，替换兜底（不完美但保证可用）
            data["content"] = sensitive_filter.replace(content)
            logger.warning(
                "素材 %s 二次生成仍含敏感词，已替换",
                material["id"],
            )
        else:
            # 首次命中，抛异常触发上层二次重生成
            raise SensitiveHitError(
                f"素材 {material['id']} 首次生成命中敏感词"
            )

    # 字数硬约束校验：content 字数低于目标 70% 时触发一次重试
    # 场景：中文 LLM 普遍字数缩水，首次生成 65-80% 字数是常见现象
    # 重试策略：追加 _WORD_COUNT_ENFORCE_SUFFIX 强化约束，仅重试一次
    # 不在二次重生成（retry_with_constraint=True）时触发，避免与敏感词重试叠加
    actual_words = _count_content_words(data.get("content", ""))
    words_min = int(words_per_segment * 0.9)
    words_max = int(words_per_segment * 1.1)
    if (
        not retry_with_constraint
        and actual_words < words_per_segment * 0.70
        and actual_words > 0
    ):
        # 触发硬约束重试计数：用于运维评估 LLM 字数缩水严重程度
        _WORD_COUNT_RETRY_STATS["triggered"] += 1
        logger.warning(
            "字数严重不足 material_id=%s actual=%d target=%d（%.0f%%），追加硬约束重试",
            material["id"], actual_words, words_per_segment,
            actual_words / words_per_segment * 100,
        )
        enforce_suffix = _WORD_COUNT_ENFORCE_SUFFIX.format(
            actual_words=actual_words,
            words_per_segment=words_per_segment,
            words_min=words_min,
            words_max=words_max,
        )
        # 在原 prompt 基础上追加字数硬约束后重新调用
        retry_prompt = prompt + enforce_suffix
        try:
            retry_raw = await _call_llm(retry_prompt)
            retry_data = _parse_llm_response(retry_raw, material["id"])
            retry_words = _count_content_words(retry_data.get("content", ""))
            # 重试后字数有改善则采用重试结果，否则保留首次结果（避免重试更差）
            if retry_words > actual_words:
                _WORD_COUNT_RETRY_STATS["improved"] += 1
                logger.info(
                    "字数硬约束重试改善 material_id=%s %d → %d 字",
                    material["id"], actual_words, retry_words,
                )
                data = retry_data
            else:
                # 未改善包含两种场景：重试字数 ≤ 首次、重试异常失败
                # 两者都意味着硬约束 prompt 未生效，统一计入 not_improved
                _WORD_COUNT_RETRY_STATS["not_improved"] += 1
                logger.warning(
                    "字数硬约束重试未改善 material_id=%s 重试=%d 首次=%d，保留首次结果",
                    material["id"], retry_words, actual_words,
                )
        except Exception as e:
            # 重试失败不阻断主流程，使用首次结果（由 5.6 节字数补足兜底）
            # 计入 not_improved：硬约束重试未带来改善（与未改善语义一致）
            _WORD_COUNT_RETRY_STATS["not_improved"] += 1
            logger.warning(
                "字数硬约束重试异常 material_id=%s: %s，使用首次结果",
                material["id"], e,
            )

    return {
        "title": data.get("title", material["title"]),
        "content": data.get("content", ""),
        "estimated_duration": data.get("estimated_duration", 90),
        "source_url": data.get("source_url", material["url"]),
        "material_id": material["id"],
        # 封面图透传到 segment，小程序文稿页按段展示
        "cover_url": material.get("cover_url"),
    }


def _parse_llm_response(raw: str, material_id: int) -> dict:  # NOSONAR S3776: LLM 响应解析含两级降级容错，结构清晰
    """解析 LLM 响应为 dict（剥离 Markdown 代码块 + JSON 解析 + content 字段清洗）。

    抽出此函数避免 _rewrite_one 在字数重试分支重复解析逻辑。
    失败时抛 LLMContentError，由调用方决定是否降级。

    容错策略（两级降级）：
    1. 严格模式 json.loads：标准 JSON 解析
    2. 宽松模式 json.loads(strict=False)：允许控制字符（实际换行符/制表符）
       出现在字符串值中。LLM 生成长文本时常在 content 字段中返回未转义
       的换行符，导致 "Expecting ',' delimiter" 错误（如 wf-20260722-0002
       material_id=176 案例）。strict=False 是 Python json 模块内置的
       容错机制，无需引入额外依赖。

    解析后对 content 字段做 Markdown 残留清洗：
    - LLM 偶发违反"禁止输出 Markdown 标记"约束，在 content 中残留 ** 或 #
    - TTS 朗读这些符号会念出"星号星号"或"井号"，严重影响听感
    - 此处做兜底清理，确保任何路径返回的 content 都已清洗
    """
    if not raw or not raw.strip():
        raise LLMContentError("LLM 返回空 content（可能被限流或审核拒绝）")

    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # 第一级：严格模式解析（标准 JSON）
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # 第一级失败，进入第二级宽松模式
        parsed = None

    if parsed is None:
        # 第二级：宽松模式解析（允许控制字符出现在字符串值中）
        # 场景：LLM 在 content 字段中返回未转义换行符/制表符
        try:
            parsed = json.loads(text, strict=False)
            logger.warning(
                "LLM 响应 JSON 严格模式解析失败，宽松模式成功 material_id={}",
                material_id,
            )
        except json.JSONDecodeError as e:
            logger.error(
                "LLM 响应 JSON 解析失败 material_id={} raw_preview={}",
                material_id, raw[:300],
            )
            raise LLMContentError(
                f"JSON 解析失败: {e}，raw 前300字: {raw[:300]}"
            ) from e

    # 防御性清洗 content 字段中残留的 Markdown 标记
    # 统一在解析成功后处理，覆盖严格/宽松两条路径
    if isinstance(parsed, dict) and isinstance(parsed.get("content"), str):
        original = parsed["content"]
        cleaned = _strip_markdown_residue(original)
        if cleaned != original:
            logger.warning(
                "LLM 输出 content 含 Markdown 残留，已清洗 material_id=%s",
                material_id,
            )
            parsed["content"] = cleaned
    return parsed


def _select_top_materials(materials: list[dict], top_n: int = SELECT_TOP_N) -> list[dict]:
    """按品类分组选题，保证多样性与数量充足（LLD 5.3.2）。

    策略：
    1. 按品类分组，每品类按热度降序
    2. 轮询各品类取热度最高的 1 篇（第一轮保证品类覆盖）
    3. 若总量不足 top_n，第二轮从各品类补取次高热度的素材
    4. 单品类素材池很大时仍受 top_n 上限约束

    避免单一品类（如爬虫未分类导致全归"综合"）只能取 2 篇 < MIN_VALID_SEGMENTS 的缺陷。
    """
    by_category = defaultdict(list)
    for m in materials:
        cat = m.get("category") or "未分类"
        by_category[cat].append(m)

    # 每品类按热度降序
    for cat in by_category:
        by_category[cat].sort(key=lambda m: heat_score(m), reverse=True)

    selected = []
    # 第一轮：每个品类取 1 篇，保证品类覆盖
    cats = list(by_category.keys())
    for cat in cats:
        if by_category[cat]:
            selected.append(by_category[cat].pop(0))
        if len(selected) >= top_n:
            return selected[:top_n]

    # 第二轮：从剩余素材中按品类轮询补取，直到达到 top_n 或素材耗尽
    # 收集所有剩余素材，按热度全局排序后补足
    remaining = []
    for cat in cats:
        remaining.extend(by_category[cat])
    remaining.sort(key=lambda m: heat_score(m), reverse=True)
    for m in remaining:
        if len(selected) >= top_n:
            break
        selected.append(m)

    return selected[:top_n]


def _build_aggregated_error(
    segments: list[dict],
    failure_details: list[dict],
    min_segments: int = MIN_VALID_SEGMENTS,
) -> LLMError:
    """根据并发失败的 failure_details 聚合错误信息，构建 LLMError。

    策略：
    - 若同一 error_type 出现次数 >= 总失败数的 2/3，认为这是根因，
      错误消息中明确指出根因类型和示例，便于运维直接定位
      （例：6 条全部 LLMAuthError → 明确报鉴权失败而非"段数不足"）
    - 否则回退到笼统的"段数不足"消息，但附带 failure_details 供 workflow_step 展示

    始终把完整 failure_details 附加到 LLMError.failure_details 属性，
    供 workflow_scheduler._run_step 在 failed 状态下写入 workflow_step.result。

    Args:
        min_segments: 动态有效段数下限（素材稀缺时降级，默认 MIN_VALID_SEGMENTS）
    """
    base_msg = (
        f"有效改写段数 {len(segments)} < {min_segments}，无法生成节目"
    )

    if not failure_details:
        # 无单条素材失败（如素材总量不足选不够 top_n），构造诊断摘要写入 workflow_step.result
        # 否则 result 为 NULL，前端详情页无法展示失败原因
        return LLMError(base_msg, failure_details=[{
            "stage": "insufficient_segments",
            "error_type": "InsufficientSegments",
            "error_message": base_msg,
        }])

    # 统计 error_type 分布，识别主导错误
    from collections import Counter
    type_counter = Counter(d["error_type"] for d in failure_details)
    most_common_type, most_common_count = type_counter.most_common(1)[0]
    threshold = max(2, len(failure_details) * 2 // 3)

    if most_common_count >= threshold:
        # 同类型错误占主导：透传根因类型 + 代表性错误消息
        representative = next(
            d for d in failure_details if d["error_type"] == most_common_type
        )
        msg = (
            f"有效改写段数 {len(segments)} < {MIN_VALID_SEGMENTS}，"
            f"根因：{most_common_count}/{len(failure_details)} 条素材"
            f"因 {most_common_type} 失败"
            f"（示例: {representative['error_message'][:200]}）"
        )
    else:
        # 错误类型分散：保留笼统消息，详情见 failure_details
        type_summary = ", ".join(
            f"{t}={c}" for t, c in type_counter.most_common()
        )
        msg = f"{base_msg}（失败分布: {type_summary}）"

    return LLMError(msg, failure_details=failure_details)


def _assemble_script(
    segments: list[dict],
    rate_multiplier: float = 1.0,
    intro_text: str = None,
    outro_text: str = None,
) -> dict:
    """组装整稿（开场白 + 改写正文 + 结尾）。

    Args:
        segments: 改写后的分段列表 [{seq, title, content, ...}]
        rate_multiplier: TTS 实际语速倍率（如 1.5 = 1.5 倍速），
            用于校正估算时长，避免与实际 TTS 输出时长偏差过大
        intro_text: 频道级开场白，None 则用默认 INTRO_TEXT
        outro_text: 频道级结尾，None 则用默认 OUTRO_TEXT

    Returns:
        {full_text, segments_json, total_words, estimated_duration}
    """
    # 频道级文案优先，回退到默认 INTRO_TEXT/OUTRO_TEXT
    effective_intro = intro_text if intro_text else INTRO_TEXT
    effective_outro = outro_text if outro_text else OUTRO_TEXT

    # 开场白动态注入今日日期：替换 {date_placeholder} 为"今天是7月15日星期三"
    # 频道自定义文案也可使用 {date_placeholder} 占位符享受日期注入
    # 兜底：频道文案不含占位符时前置日期，确保所有频道都有日期播报
    today = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    date_str = f"今天是{today.month}月{today.day}日{weekdays[today.weekday()]}"
    if "{date_placeholder}" in effective_intro:
        effective_intro = effective_intro.replace("{date_placeholder}", date_str)
    else:
        # 频道自定义 intro_prompt 未声明占位符，前置日期作为兜底
        effective_intro = f"{date_str}，{effective_intro}"

    # 实际播报速率 = 基础语速 × 倍率（如 210 × 1.5 = 315 字/分）
    actual_words_per_min = WORDS_PER_MINUTE * rate_multiplier

    # 开场白与结尾作为独立分段，便于 TTS 单独合成与时长控制
    # 时长按实际字数 + 实际语速估算
    intro_duration = int(len(effective_intro) / actual_words_per_min * 60)
    intro_segment = {
        "seq": 1,
        "title": "开场白",
        "content": effective_intro,
        "start_sec": 0,
        "end_sec": intro_duration,
        "material_ids": [],
    }

    body_segments = []
    # 正文段 seq 从 2 开始，衔接开场白
    current_sec = intro_duration
    for idx, seg in enumerate(segments, start=2):
        # 每段时长按实际字数 + 实际语速估算，避免 LLM 返回的 estimated_duration 不准
        seg_words = len(seg.get("content", ""))
        duration = int(seg_words / actual_words_per_min * 60) if seg_words else seg.get("estimated_duration", 90)
        body_segments.append(
            {
                "seq": idx,
                "title": seg["title"],
                "content": seg["content"],
                "start_sec": current_sec,
                "end_sec": current_sec + duration,
                "material_ids": [seg["material_id"]],
                # 封面图：小程序文稿页每段顶部展示，无图时小程序自然降级
                "cover_url": seg.get("cover_url"),
            }
        )
        current_sec += duration

    outro_duration = int(len(effective_outro) / actual_words_per_min * 60)
    outro_segment = {
        "seq": len(segments) + 2,
        "title": "结尾",
        "content": effective_outro,
        "start_sec": current_sec,
        "end_sec": current_sec + outro_duration,
        "material_ids": [],
    }

    all_segments = [intro_segment] + body_segments + [outro_segment]

    # 拼接完整稿件文本，用于全文检索与人工审阅
    full_text = "\n\n".join(s["content"] for s in all_segments)
    total_words = sum(len(s["content"]) for s in all_segments)
    # 总时长按实际语速估算，与 TTS 实际输出对齐
    estimated_duration = int(total_words / actual_words_per_min * 60)

    return {
        "full_text": full_text,
        "segments_json": all_segments,
        "total_words": total_words,
        "estimated_duration": estimated_duration,
    }


async def _fetch_materials(
    date_str: str, channel_id: int = None, material_lookback_days: int = None
) -> list[dict]:
    """查询当日 pending 素材，当日不足 SELECT_MIN_N 条时回溯最近 N 天。

    N 的优先级：频道显式配置的 material_lookback_days > 按入库频率动态计算
    （_calc_dynamic_fallback_days）：
    - 频道已配置 material_lookback_days（>0）：直接使用该天数放宽选材时间范围，
      从上游扩展时间跨度获取更多素材，避免依赖 stitch 的 BGM/静音补足凑短节目
    - 未配置时（None）：按频道入库频率动态计算
      - 高频道道（≥5 天/周有入库）：3 天回溯，避免拉入过旧素材
      - 中频道道（2-4 天/周）：7 天回溯，覆盖周末场景
      - 低频道道（0-1 天/周）：14 天回溯，避免无素材可用

    按 crawled_at 当日筛选，避免历史积压素材混入当日节目。
    status=pending 确保不重复消费已被选题的素材。
    回溯阈值取 SELECT_MIN_N 而非 0：RSS 源稀疏日即使爬到 1-2 条，
    也常不足 MIN_VALID_SEGMENTS=3，提前回溯避免工作流必然失败。
    channel_id 非空时严格按本频道过滤，确保各频道素材互不交叉；
    为空时（全局工作流）查询全部 pending 素材。

    重要：已配置 rss_sources/keywords 的专门频道不再回退到 channel_id IS NULL 的
    历史遗留素材。历史遗留素材未经过频道 RSS 白名单和关键词过滤，混入会绕过
    频道级数据隔离（曾导致"主机游戏"频道消费 36氪/人民网等非游戏素材的 bug）。
    专门频道 RSS 不可达时让工作流显式失败，由运维介入修复源配置，
    而非用不相关内容掩盖问题。
    """
    async with AsyncSessionLocal() as session:
        day = date.fromisoformat(date_str)
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())

        stmt = select(Material).where(
            Material.status == MaterialStatus.pending,
            Material.crawled_at >= start,
            Material.crawled_at <= end,
        )
        # 频道级严格隔离：channel_id 非空时仅查本频道素材，不再 OR channel_id IS NULL
        # 历史遗留 NULL 素材只允许被全局工作流（channel_id=None）消费，
        # 避免绕过专门频道的 rss_sources 白名单与 keywords 过滤造成跨频道污染
        if channel_id is not None:
            stmt = stmt.where(Material.channel_id == channel_id)
        result = await session.execute(stmt)
        rows = list(result.scalars().all())

        # 当日 pending 素材不足时，按"配置优先、动态兜底"的回溯天数放宽选材时间范围
        # 场景：RSS 源周末/夜间/稀疏日，单日仅 1-2 条素材，
        # 改写后段数 < MIN_VALID_SEGMENTS 必然失败，提前回溯兜底
        # 优先使用频道显式配置的 material_lookback_days（运营可在频道编辑页设定），
        # 未配置时回退到按频道入库频率动态计算的 _calc_dynamic_fallback_days（3/7/14 天）
        if material_lookback_days is not None and material_lookback_days > 0:
            fallback_days = material_lookback_days
        else:
            fallback_days = await _calc_dynamic_fallback_days(channel_id)
        if len(rows) < SELECT_MIN_N and fallback_days > 0:
            fb_start = datetime.combine(
                day - timedelta(days=fallback_days), datetime.min.time()
            )
            existing_ids = {r.id for r in rows}
            fb_stmt = select(Material).where(
                Material.status == MaterialStatus.pending,
                Material.crawled_at >= fb_start,
                Material.crawled_at < start,
            )
            # 回溯也按本频道严格过滤，不回退 NULL 历史遗留素材，保持与当日查询一致
            # 历史遗留 NULL 素材绕过频道 rss_sources/keywords 过滤，混入会造成跨频道污染
            if channel_id is not None:
                fb_stmt = fb_stmt.where(Material.channel_id == channel_id)
            fb_stmt = fb_stmt.order_by(Material.crawled_at.desc())
            fb_result = await session.execute(fb_stmt)
            fb_rows = [r for r in fb_result.scalars().all() if r.id not in existing_ids]
            if fb_rows:
                rows.extend(fb_rows)
                logger.warning(
                    "当日 %s pending 素材不足（%d < %d），回溯最近 %d 天补 %d 条，合计 %d 条"
                    "（channel_id=%s）",
                    date_str, len(existing_ids), SELECT_MIN_N,
                    fallback_days, len(fb_rows), len(rows),
                    channel_id,
                )

        # ORM 对象转 dict，便于热度计算与并发传递
        # 注：schema 未含 source_authority 字段，heat_score 内部默认 0.5
        return [
            {
                "id": r.id,
                "source": r.source,
                "title": r.title,
                "content": r.content,
                "url": r.url,
                "published_at": r.published_at,
                "category": r.category,
                "workflow_id": r.workflow_id,
                # 封面图透传到 segment，小程序文稿页按段展示
                "cover_url": r.cover_url,
            }
            for r in rows
        ]


async def _calc_dynamic_fallback_days(channel_id: int | None) -> int:
    """按频道近 7 天入库频率动态计算回溯天数。

    策略：
    - 高频道道（≥5 天有入库）：3 天（素材充足，小回溯即可）
    - 中频道道（2-4 天有入库）：7 天（默认值，覆盖周末场景）
    - 低频道道（0-1 天有入库）：14 天（扩大回溯，避免无素材可用）

    channel_id 为 None 时（全局工作流）使用默认值 7。

    实现细节：用 func.date(crawled_at) 去重日期，统计近 7 天有入库的天数。
    不查 pending 状态：入库频率反映 RSS 源活跃度，与素材是否已被消费无关。
    """
    if channel_id is None:
        return FALLBACK_DAYS

    try:
        today = date.today()
        week_ago = datetime.combine(today - timedelta(days=7), datetime.min.time())
        async with AsyncSessionLocal() as session:
            stmt = (
                select(func.date(Material.crawled_at))
                .where(
                    Material.channel_id == channel_id,
                    Material.crawled_at >= week_ago,
                )
                .group_by(func.date(Material.crawled_at))
            )
            result = await session.execute(stmt)
            distinct_days = len(result.all())

        if distinct_days >= 5:
            return 3
        if distinct_days >= 2:
            return FALLBACK_DAYS
        return 14
    except Exception as e:
        # 查询失败时回退到默认值，避免影响主流程
        logger.warning(
            "动态 FALLBACK_DAYS 查询失败 channel_id=%s: %s，使用默认值 %d",
            channel_id, e, FALLBACK_DAYS,
        )
        return FALLBACK_DAYS


async def _fetch_channel_prompts(channel_id: int) -> dict:
    """查询频道级提示词与配置。空值字段返回 None，由调用方回退默认值。

    Args:
        channel_id: 频道 ID

    Returns:
        {name, description, intro_prompt, outro_prompt, constraint_prompt,
         rewrite_template, enable_thinking_question, material_lookback_days}
        频道不存在或字段为空时对应值为 None
    """
    from app.models import Channel
    async with AsyncSessionLocal() as session:
        ch = await session.get(Channel, channel_id)
        if ch is None:
            return {
                "name": None,
                "description": None,
                "intro_prompt": None,
                "outro_prompt": None,
                "constraint_prompt": None,
                "rewrite_template": None,
                "enable_thinking_question": None,
                "material_lookback_days": None,
            }
        return {
            "name": ch.name,
            "description": ch.description,
            "intro_prompt": ch.intro_prompt,
            "outro_prompt": ch.outro_prompt,
            "constraint_prompt": ch.constraint_prompt,
            "rewrite_template": ch.rewrite_template,
            # None=默认开启，0=关闭，1=开启；统一转为 bool
            "enable_thinking_question": ch.enable_thinking_question != 0,
            # None=未配置，rewriter 回退到 _calc_dynamic_fallback_days 的动态值
            "material_lookback_days": ch.material_lookback_days,
        }


async def _filter_materials_by_relevance(
    materials: list[dict], channel_name: str, channel_description: str
) -> list[dict]:
    """AI 相关性筛选：批量判断素材是否与频道主题相关。

    作为关键词过滤的第二道防线，处理关键词无法覆盖的语义相关性。
    批量调用 LLM（一次传全部素材的 title+summary），返回相关素材 ID 列表。
    筛选失败时降级为全部保留（不阻断工作流），仅记录 warning。

    Args:
        materials: 待筛选的素材列表（dict 含 id/title/summary）
        channel_name: 频道名称（如"娱乐焦点"）
        channel_description: 频道描述（如"影视、音乐、明星动态与文娱产业资讯"）

    Returns:
        相关素材列表（原 dict 列表的子集）
    """
    if not materials or not channel_name:
        return materials

    # 构造批量筛选 prompt：一次调用判断所有素材，节省 AI 预算
    # 使用 content 前 100 字作为摘要（_fetch_materials 返回的 dict 无 summary 字段）
    items_text = "\n".join(
        f"[{i}] 标题：{m['title']}\n    摘要：{(m.get('content') or '')[:100]}"
        for i, m in enumerate(materials)
    )

    prompt = f"""你是新闻频道内容审核员。请判断以下素材是否与频道主题相关。

频道名称：{channel_name}
频道描述：{channel_description or ''}

待审核素材：
{items_text}

请仅返回相关素材的序号（方括号中的数字），以 JSON 数组格式输出。
判断标准：素材核心内容应与频道主题直接相关，边缘关联不算。
仅输出 JSON 数组本身，不要任何解释。

示例输出：[0, 2, 5]"""

    try:
        resp = await _call_llm(prompt)
        # 解析 LLM 返回的相关序号
        # 提取 JSON 数组（LLM 可能包裹在 markdown 中）
        match = re.search(r'\[[\d\s,]*\]', resp)
        if not match:
            logger.warning("AI 相关性筛选返回格式异常，降级全部保留: %s", resp[:200])
            return materials

        raw_indices = json.loads(match.group())
        # 保序去重 + 类型检查 + 越界过滤：LLM 可能返回重复序号或非整数值
        seen = set()
        relevant = []
        for i in raw_indices:
            if isinstance(i, int) and 0 <= i < len(materials) and i not in seen:
                seen.add(i)
                relevant.append(materials[i])

        if len(relevant) < len(materials):
            skipped_titles = [
                m["title"][:40] for i, m in enumerate(materials) if i not in seen
            ]
            logger.info(
                "AI 相关性筛选：%d → %d 条（筛除 %d 条不相关：%s）",
                len(materials), len(relevant), len(materials) - len(relevant),
                skipped_titles,
            )

        # 筛选后不足 SELECT_MIN_N 时保留全部（降级策略，不阻断工作流）
        if len(relevant) < SELECT_MIN_N:
            logger.warning(
                "AI 筛选后仅 %d 条 <%d，降级保留全部素材",
                len(relevant), SELECT_MIN_N,
            )
            return materials

        return relevant
    except Exception as e:
        # AI 筛选失败时降级为全部保留，不阻断工作流
        logger.warning("AI 相关性筛选异常，降级全部保留: %s", e)
        return materials


async def rewrite(workflow_id: str, date_str: str, channel_id: int = None) -> dict:  # NOSONAR
    """改写主入口（LLD 5.3）。

    整合目标时长 + TTS 实际语速，动态反算每段字数要求，注入 prompt。
    channel_id 非空时使用频道级提示词，空值字段回退默认值。

    Args:
        workflow_id: 工作流 ID，用于关联稿件与回溯
        date_str: 日期字符串（如 "2026-07-08"），筛选当日素材
        channel_id: 频道 ID，用于读取频道级提示词

    Returns:
        {"script_id": N, "segments": 6, "total_words": 2100}

    Raises:
        LLMError: 有效改写段数 < 3，无法生成节目
    """
    logger.info("改写启动 workflow_id=%s date=%s channel_id=%s", workflow_id, date_str, channel_id)

    # 记录本轮改写开始前的字数重试计数器快照
    # 用于在 rewrite 结束时计算本轮触发率/改善率，单次工作流粒度的即时反馈
    # _WORD_COUNT_RETRY_STATS 是模块级累计计数器，差值即本轮贡献
    _stats_before = dict(_WORD_COUNT_RETRY_STATS)

    # 0. 占位符前置检测：避免无效 API key 浪费重试配额
    # 若 .env 未替换占位符或前端未配置真实 key，立即抛出明确错误
    if _is_placeholder_api_key(settings.LLM_API_KEY):
        masked = settings.LLM_API_KEY[:8] + "***" if settings.LLM_API_KEY else "(空)"
        raise LLMError(
            f"LLM_API_KEY 未配置或仍为占位符（当前值: {masked}），"
            f"请在 .env 文件或前端 AI 配置页填入真实 API Key"
        )

    # 0.3 读取频道级提示词（channel_id 为空或字段为空时，回退默认值）
    channel_prompts = None
    if channel_id:
        channel_prompts = await _fetch_channel_prompts(channel_id)
        logger.info(
            "频道提示词 channel_id=%s intro=%s outro=%s template=%s",
            channel_id,
            bool(channel_prompts["intro_prompt"]),
            bool(channel_prompts["outro_prompt"]),
            bool(channel_prompts["rewrite_template"]),
        )

    # 0.5 读取目标时长 + TTS 语速倍率，反算每段目标字数
    # 数学关系：总字数 = 目标时长 × 基础语速 × 倍率 / 60
    # 用户调整目标时长或 TTS 语速时，自动协同调整稿件字数
    target_sec = _get_target_duration_sec()
    rate_multiplier = _get_rate_multiplier()
    target_segments, words_per_segment = _calc_segment_words(target_sec, rate_multiplier)
    segment_duration = int(words_per_segment / (WORDS_PER_MINUTE * rate_multiplier) * 60)
    logger.info(
        "时长/字数联动 target_sec=%d rate=%.2f 目标段数=%d 每段字数=%d 每段时长=%ds",
        target_sec, rate_multiplier, target_segments, words_per_segment, segment_duration,
    )

    # 1. 拉取当日 pending 素材（频道级隔离：channel_id 非空时仅查本频道素材）
    # 频道显式配置 material_lookback_days 时优先使用，否则 rewriter 动态计算回溯天数
    material_lookback_days = (
        channel_prompts.get("material_lookback_days") if channel_prompts else None
    )
    materials = await _fetch_materials(
        date_str, channel_id, material_lookback_days=material_lookback_days
    )
    logger.info(
        "当日 pending 素材 %d 条（channel_id=%s lookback=%s）",
        len(materials), channel_id, material_lookback_days,
    )

    if not materials:
        # 查询 material 表诊断信息，帮助定位根因
        # 按 channel_id 过滤统计，避免全局数字误导（不同频道素材互不交叉，
        # 全局 pending 数与当前频道无关，会误导用户以为有素材可用）
        # 场景：爬虫从未成功、RSS 源全部不可达、数据库被重置、素材状态被批量修改
        async with AsyncSessionLocal() as session:
            total_stmt = select(func.count(Material.id))
            status_stmt = (
                select(Material.status, func.count(Material.id))
                .group_by(Material.status)
            )
            if channel_id is not None:
                total_stmt = total_stmt.where(Material.channel_id == channel_id)
                status_stmt = status_stmt.where(Material.channel_id == channel_id)
            total_count = await session.scalar(total_stmt)
            status_rows = (await session.execute(status_stmt)).all()
            status_dist = dict(status_rows) if status_rows else {}
        channel_hint = f"频道 channel_id={channel_id} " if channel_id is not None else "全局"
        # 实际回溯天数优先取频道显式配置，否则复用动态计算（3/7/14 天三档）
        # 错误消息需与实际选材行为一致，避免误导运维
        actual_fallback_days = (
            material_lookback_days
            if (material_lookback_days is not None and material_lookback_days > 0)
            else await _calc_dynamic_fallback_days(channel_id)
        )
        raise LLMError(
            f"当日 {date_str} 无 pending 素材（回溯 {actual_fallback_days} 天亦无），"
            f"无法改写。{channel_hint}material 表共 {total_count} 条，"
            f"状态分布: {status_dist or '空表'}。"
            f"请检查爬虫是否正常运行、RSS 源配置是否可达"
        )

    # 2. 选题：按品类分组，每品类选 1-2 篇热度最高
    selected = _select_top_materials(materials, top_n=SELECT_TOP_N)
    logger.info("选题 %d 条（按热度排序）", len(selected))

    # 2.3 AI 相关性筛选：批量判断选题素材是否与频道主题相关
    # 作为关键词过滤的第二道防线，处理关键词无法覆盖的语义相关性
    # 筛选失败时降级为全部保留（不阻断工作流）
    if channel_prompts and channel_prompts.get("name"):
        selected = await _filter_materials_by_relevance(
            selected,
            channel_prompts["name"],
            channel_prompts.get("description") or "",
        )
        logger.info("AI 相关性筛选后剩余 %d 条", len(selected))

    # 2.4 动态段数下限：素材稀缺时降级允许生成短节目，而非直接失败（R23 自动调整 / R110 自动降级）
    # 场景：低频频道（如主机游戏/教育资讯）周末或 RSS 源稀疏日，回溯期内 pending 素材
    # 仍不足 MIN_VALID_SEGMENTS=3，原逻辑直接 raise 导致工作流必然失败
    # 策略：有效下限 = min(配置下限, 实际选题数)，至少 1 段保证节目可生成
    # 后续 duration 下限校验（5.6）会记录字数不足警告，但不阻断短节目生成
    if selected:
        effective_min_segments = min(MIN_VALID_SEGMENTS, len(selected))
    else:
        effective_min_segments = MIN_VALID_SEGMENTS
    if effective_min_segments < MIN_VALID_SEGMENTS:
        logger.warning(
            "选题数 %d < MIN_VALID_SEGMENTS=%d，动态下调有效段数下限为 %d "
            "(channel_id=%s, workflow_id=%s)，将生成较短节目",
            len(selected), MIN_VALID_SEGMENTS, effective_min_segments,
            channel_id, workflow_id,
        )

    # 2.5 关联素材到当前工作流并标记为 selected
    # 回溯选取的历史素材 workflow_id 可能为 NULL，需更新为当前工作流
    # 否则工作流详情页按 workflow_id 过滤素材列表会查不到数据
    selected_ids = [m["id"] for m in selected]
    if selected_ids:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Material)
                .where(Material.id.in_(selected_ids))
                .values(workflow_id=workflow_id, status=MaterialStatus.selected.value)
            )
            await session.commit()
        logger.info("已关联 %d 条素材到 %s", len(selected_ids), workflow_id)

    # 3. 并发改写（Semaphore 限流 + return_exceptions 隔离单条失败）
    # 限制并发数避免瞬间打爆 LLM API 频率限制（AI_BUDGET_RATE_LIMIT_PER_MIN=20）
    # 无 Semaphore 时 10 条并发 + tenacity 重试会在 3s 内产生 30 次调用尝试，
    # 远超 20 次/分钟的频率预算，导致全部被 check_budget 拦截
    semaphore = asyncio.Semaphore(_LLM_CONCURRENCY_LIMIT)

    # 风格多样性提示：按 selected 索引 i 作为 seq 号从 style_library 轮换选取
    # 用 selected 索引而非最终 segments seq：并发调用时 segments seq 不可预知，
    # 而 selected 索引稳定，保证单期内开场白/过渡词轮换不重复
    # total_segments 用 selected 长度，让 LLM 知道整期节目段数以控制循环周期
    from app.workflow.llm.style_library import get_style_hint
    channel_id_for_style = channel_id
    total_for_style = len(selected)

    async def _rewrite_one_with_limit(m: dict, style_seq: int) -> dict:
        async with semaphore:
            # 按 seq 号从 style_library 轮换选取开场白/过渡词/同义词提示
            style_hint = get_style_hint(channel_id_for_style, style_seq, total_for_style)
            return await _rewrite_one(
                m,
                words_per_segment=words_per_segment,
                segment_duration=segment_duration,
                template_text=channel_prompts["rewrite_template"] if channel_prompts else None,
                constraint_text=channel_prompts["constraint_prompt"] if channel_prompts else None,
                enable_thinking_question=channel_prompts["enable_thinking_question"] if channel_prompts else True,
                style_hint=style_hint,
            )

    # enumerate 从 1 开始：seq=1 用开场白（intro），seq>=2 用过渡词（transition）
    tasks = [_rewrite_one_with_limit(m, i + 1) for i, m in enumerate(selected)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. 过滤失败项 + 敏感词扫描
    segments = []
    failure_details: list[dict] = []  # 记录每条素材失败原因，供 workflow_step 展示
    for i, (m, r) in enumerate(zip(selected, results)):
        if isinstance(r, SensitiveHitError):
            # 首次命中敏感词，带约束 prompt 二次重生成
            # style_hint 在敏感词重试时仍注入：保持风格一致性，避免重试产出与首版风格迥异
            try:
                style_hint = get_style_hint(channel_id_for_style, i + 1, total_for_style)
                r = await _rewrite_one(
                    m,
                    words_per_segment=words_per_segment,
                    segment_duration=segment_duration,
                    retry_with_constraint=True,
                    template_text=channel_prompts["rewrite_template"] if channel_prompts else None,
                    constraint_text=channel_prompts["constraint_prompt"] if channel_prompts else None,
                    enable_thinking_question=channel_prompts["enable_thinking_question"] if channel_prompts else True,
                    style_hint=style_hint,
                )
                segments.append({**r, "seq": len(segments) + 1})
            except Exception as e:
                logger.warning("素材 %s 二次改写失败: %s", m["id"], e)
                failure_details.append({
                    "material_id": m["id"],
                    "title": m["title"][:50],
                    "stage": "retry_with_constraint",
                    "error_type": type(e).__name__,
                    "error_message": str(e)[:300],
                })
        elif isinstance(r, Exception):
            # 其他异常（LLM 调用失败、JSON 解析失败等）跳过该条
            logger.warning("素材 %s 改写失败: %s", m["id"], r)
            failure_details.append({
                "material_id": m["id"],
                "title": m["title"][:50],
                "stage": "initial_rewrite",
                "error_type": type(r).__name__,
                "error_message": str(r)[:300],
            })
        else:
            segments.append({**r, "seq": len(segments) + 1})

    if len(segments) < effective_min_segments:
        # 错误聚合：若多数失败属同一类型，透传根因异常而非笼统报"段数不足"
        # 避免掩盖真实问题（如全部 LLMAuthError 应明确报鉴权失败）
        # 回滚素材状态：改写前已把素材标记为 selected，段数不足抛错后 _run_step
        # 会重试（最多3次），但 _fetch_materials 只查 pending，不回滚会导致重试时
        # 查不到素材，错误从"段数不足"变为"无 pending 素材"，掩盖真实根因
        if selected_ids:
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(Material)
                        .where(Material.id.in_(selected_ids))
                        .values(status=MaterialStatus.pending.value)
                    )
                    await session.commit()
                logger.warning(
                    "段数不足，已回滚 %d 条素材状态为 pending workflow_id=%s",
                    len(selected_ids), workflow_id,
                )
            except Exception as rollback_err:
                # 回滚失败不影响原错误抛出，仅记录日志便于运维定位
                logger.error(
                    "回滚素材状态失败 workflow_id=%s: %s",
                    workflow_id, rollback_err,
                )
        raise _build_aggregated_error(
            segments, failure_details, effective_min_segments
        )

    # 4.5 限制最终段数，避免选题数增加后节目时长过长
    # 按 target_segments 截取，避免段数超出目标时长对应的需求
    if len(segments) > target_segments:
        logger.info(
            "成功段数 %d 超过目标段数 %d，截取前 %d 段",
            len(segments), target_segments, target_segments,
        )
        segments = segments[:target_segments]

    # 5. 组装整稿（频道级开场白/结尾 + 改写段），用实际语速估算时长
    assembled = _assemble_script(
        segments,
        rate_multiplier=rate_multiplier,
        intro_text=channel_prompts["intro_prompt"] if channel_prompts else None,
        outro_text=channel_prompts["outro_prompt"] if channel_prompts else None,
    )

    # 5.5 字数上限校验：LLM 常不遵守 prompt 字数约束（中文 LLM 尤甚），
    # 超长时从末尾丢弃正文段，避免 TTS 合成后时长超出 stitch 校验上限
    # 安全边界：保留至少 effective_min_segments 段正文 + intro + outro
    # （素材稀缺场景 effective_min_segments 已下调，截断下限同步调整避免过度截断）
    max_allowed_duration = int(target_sec * 1.2)
    if assembled["estimated_duration"] > max_allowed_duration:
        segs = assembled["segments_json"]
        while len(segs) > effective_min_segments + 2 and assembled["estimated_duration"] > max_allowed_duration:
            segs.pop(-2)
            assembled["total_words"] = sum(len(s["content"]) for s in segs)
            assembled["estimated_duration"] = int(
                assembled["total_words"] / (WORDS_PER_MINUTE * rate_multiplier) * 60
            )
        assembled["full_text"] = "\n\n".join(s["content"] for s in segs)
        assembled["segments_json"] = segs
        logger.warning(
            "字数超限截断 target=%ds max=%ds 保留段数=%d estimated=%ds",
            target_sec, max_allowed_duration, len(segs), assembled["estimated_duration"],
        )

    # 5.6 字数下限补足：LLM 实际生成字数常低于 prompt 约束（中文 LLM 尤甚），
    # 不足时从 selected 中未使用的素材追加 LLM 改写，补到目标下限
    # 场景：LLM 生成 2400 字（目标 3300 字），stitch 拼接后 459s < 480s 下限
    # 安全边界：最多追加 2 段避免无限循环；selected 无未使用素材时跳过
    min_allowed_duration = int(target_sec * 0.80)
    if assembled["estimated_duration"] < min_allowed_duration:
        # 已使用的素材 ID（segments 中已改写的 material_id）
        used_material_ids = {seg["material_id"] for seg in segments if seg.get("material_id")}
        # 从 selected 中找未使用的素材（按热度降序已排好）
        unused_materials = [m for m in selected if m["id"] not in used_material_ids]

        if unused_materials:
            logger.warning(
                "字数不足补足 target=%ds min=%ds estimated=%ds 待补素材 %d 条",
                target_sec, min_allowed_duration, assembled["estimated_duration"],
                len(unused_materials),
            )
            # 追加补充段：最多 2 段，避免 LLM 调用过多
            # 每段补足后立即检查是否达到下限，达到则停止
            max_supplement = min(2, len(unused_materials))
            for i in range(max_supplement):
                if assembled["estimated_duration"] >= min_allowed_duration:
                    break
                try:
                    sup_seg = await _rewrite_one_with_limit(unused_materials[i], i + 1)
                    segments.append({**sup_seg, "seq": len(segments) + 1})
                    # 重新组装以更新时长估算
                    assembled = _assemble_script(
                        segments,
                        rate_multiplier=rate_multiplier,
                        intro_text=channel_prompts["intro_prompt"] if channel_prompts else None,
                        outro_text=channel_prompts["outro_prompt"] if channel_prompts else None,
                    )
                    logger.info(
                        "补充段 %d 完成 material_id=%s 重新估算 %ds",
                        i + 1, unused_materials[i]["id"], assembled["estimated_duration"],
                    )
                except Exception as e:
                    logger.warning(
                        "补充段 %d 改写失败 material_id=%s: %s",
                        i + 1, unused_materials[i]["id"], e,
                    )
                    break

            logger.info(
                "字数补足结束 最终 estimated=%ds segments=%d",
                assembled["estimated_duration"], len(segments),
            )
        else:
            logger.warning(
                "字数不足 %ds < %ds 但 selected 无未使用素材，跳过补足",
                assembled["estimated_duration"], min_allowed_duration,
            )

    # 5.7 LLM 字数达成率监控：对比目标字数与实际字数
    # 场景：LLM 常不遵守 prompt ±10% 字数约束（中文 LLM 尤甚），
    # 实际生成 65-80% 字数是常见现象，达成率低于 80% 时 WARNING
    # 便于运维发现 LLM 模型质量问题或 prompt 约束力不足
    # 不阻断工作流：补足机制（5.6）已尽力兜底，监控仅告警
    target_total_words = _calc_target_words(target_sec, rate_multiplier)
    actual_total_words = assembled["total_words"]
    if target_total_words > 0:
        achievement_rate = actual_total_words / target_total_words
        if achievement_rate < 0.80:
            logger.warning(
                "LLM 字数达成率 %.0f%% 低于 80%% 阈值"
                "（实际 %d 字 / 目标 %d 字，segments=%d estimated=%ds）"
                "prompt ±10%% 约束未被遵守，建议检查 LLM 模型或 prompt",
                achievement_rate * 100, actual_total_words, target_total_words,
                len(segments), assembled["estimated_duration"],
            )
        else:
            logger.info(
                "LLM 字数达成率 %.0f%%（%d / %d 字）",
                achievement_rate * 100, actual_total_words, target_total_words,
            )

    # 6. 落库 script 表
    referenced_materials = [
        {"title": m["title"], "url": m["url"]} for m in selected
    ]
    categories = list({m.get("category") or "未分类" for m in selected})

    script = Script(
        workflow_id=workflow_id,
        episode_date=date.fromisoformat(date_str),
        full_text=assembled["full_text"],
        segments=assembled["segments_json"],
        total_words=assembled["total_words"],
        estimated_duration=assembled["estimated_duration"],
        referenced_materials=referenced_materials,
        categories=categories,
        status=ScriptStatus.draft,
    )
    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(script)
            await session.flush()
            script_id = script.id

    logger.info(
        "改写完成 workflow_id=%s script_id=%s segments=%d total_words=%d",
        workflow_id,
        script_id,
        len(segments),
        assembled["total_words"],
    )

    # 7. LLM 字数重试指标采集与告警
    # 输出本轮 + 累计两个粒度的快照，便于运维观察单次工作流与长期趋势
    # 告警阈值：本轮触发率 > 50%（LLM 字数缩水严重）或改善率 < 30%（硬约束无效）
    _emit_word_count_retry_stats(workflow_id, _stats_before)

    return {
        "script_id": script_id,
        "segments": len(segments),
        "total_words": assembled["total_words"],
    }
