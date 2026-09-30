"""B 端智能助手服务。

定位：把管理员的自然语言调度指令解析为系统菜单可执行的动作草稿（仅规划，不落地），
再由管理员在会话内确认后由 execute 落地为真实配置（第一版为「新增频道」闭环）。

设计要点：
- 动作注册表 ASSISTANT_ACTIONS 声明每个可调度动作的字段 schema，同时作为
  LLM 解析约束（system prompt 参照）与前端动态表单渲染的依据，动作可扩展。
- plan 使用 AIConfigService.chat_with_model 复用已保存的 LLM 配置与用量记录。
- execute 复用 ChannelService.create_channel，不重复实现业务逻辑。
"""
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_config_service import AIConfigService
from app.services.channel_service import ChannelService

logger = logging.getLogger(__name__)


# ===== 动作注册表 =====
# 每个动作：action_id / group / title / target_route / description / fields
# fields 的每个元素：key / label / type(text|textarea|select|switch|number)
#   / required / default / options(select 用) / help
ChannelCreateAction: dict = {
    "action_id": "create_channel",
    "group": "频道管理",
    "title": "新增频道",
    "target_route": "/channels",
    "description": "在频道管理中创建一个新的播报频道，自动生成完整的频道配置，可随时在频道管理中查询修改。",
    "fields": [
        {
            "key": "name",
            "label": "频道名称",
            "type": "text",
            "required": True,
            "help": "频道定位清晰的中文名称，不超过 64 字，如「AI 前沿资讯」",
        },
        {
            "key": "description",
            "label": "频道描述",
            "type": "textarea",
            "required": False,
            "help": "一句话说明频道定位与受众，用于生成开场白/结尾/改写模板",
        },
        {
            "key": "channel_type",
            "label": "频道类型",
            "type": "select",
            "required": False,
            "default": "news",
            "options": [
                {"value": "news", "label": "资讯"},
                {"value": "course", "label": "课程"},
                {"value": "audiobook", "label": "有声读物"},
            ],
            "help": "默认资讯；课程/有声读物走章节列表 + 学习进度 UI",
        },
        {
            "key": "keywords",
            "label": "关键词过滤",
            "type": "textarea",
            "required": False,
            "help": "逗号分隔，如「AI,大模型,机器人」；留空表示不过滤",
        },
        {
            "key": "schedule_time",
            "label": "定时触发",
            "type": "text",
            "required": False,
            "help": "HH:MM:SS 或 HH:MM，如 04:00:00；留空使用全局默认(05:00)",
        },
        {
            "key": "disclaimer_level",
            "label": "风险提示",
            "type": "select",
            "required": False,
            "default": "none",
            "options": [
                {"value": "none", "label": "无（资讯）"},
                {"value": "normal", "label": "普通"},
                {"value": "strong", "label": "强提示（课程/资料）"},
            ],
            "help": "课程/资料类须显式「强提示」",
        },
        {
            "key": "selection_strategy",
            "label": "选题策略",
            "type": "select",
            "required": False,
            "options": [
                {"value": "heat", "label": "按热度（默认）"},
                {"value": "outline", "label": "按文档章节顺序"},
                {"value": "manual", "label": "手动指定素材"},
            ],
            "help": "课程频道建议选「按文档章节顺序」",
        },
        {
            "key": "enable_ad",
            "label": "投放广告",
            "type": "switch",
            "required": False,
            "default": 1,
            "help": "开启则频道内容可插播广告",
        },
        {
            "key": "display_order",
            "label": "展示排序",
            "type": "number",
            "required": False,
            "default": 0,
            "help": "数值越小越靠前（小程序/首页 tab 顺序）",
        },
        {
            "key": "material_lookback_days",
            "label": "素材回溯(天)",
            "type": "number",
            "required": False,
            "help": "1-90；留空继承系统动态回溯",
        },
        {
            "key": "cover_url",
            "label": "封面图 URL",
            "type": "text",
            "required": False,
            "help": "留空用类型默认封面",
        },
        {
            "key": "auto_generate_prompts",
            "label": "自动生成提示词",
            "type": "switch",
            "required": False,
            "default": 1,
            "help": "创建后自动调用 AI 生成开场白/结尾/约束/改写模板",
        },
    ],
}

ASSISTANT_ACTIONS: dict[str, dict] = {act["action_id"]: act for act in [ChannelCreateAction]}


def _field_constraint(field: dict) -> str:
    """生成单字段的生成/解析约束文本，供 LLM 参照。"""
    parts = [f"- {field['key']}（{field['label']}）: {field.get('type', 'text')}"]
    options = field.get("options") or []
    if options:
        allowed = [f"{o['value']}（{o['label']}）" for o in options]
        parts.append(f"  可选值仅限: {'、'.join(allowed)}")
    if field.get("required"):
        parts.append("  必填")
    if field.get("help"):
        parts.append(f"  说明: {field['help']}")
    return "\n".join(parts)


def _build_system_prompt() -> str:
    """构造智能助手动作解析的 system prompt。

    把动作注册表的字段 schema 转成 LLM 可参照的约束文本，并约定输出为严格 JSON。
    """
    blocks: list[str] = []
    for act in ASSISTANT_ACTIONS.values():
        fields_block = "\n".join(_field_constraint(f) for f in act["fields"])
        blocks.append(
            f"[action_id={act['action_id']}] {act['title']}（{act['group']}）\n"
            f"{act['description']}\n字段:\n{fields_block}"
        )
    return (
        "你是 MorningBrief 后台管理系统的智能助手，负责把管理员用自然语言下达的"
        "系统调度指令，解析为一个系统菜单可执行的动作草稿（只规划，不落地执行）。\n\n"
        "可用动作如下（字段 key 必须严格照抄）：\n"
        + "\n\n".join(blocks)
        + "\n\n识别规则：\n"
        "- 从用户指令中识别目标动作 action_id；若无法匹配任何动作（闲聊/普通问答），"
        '则输出 action_id 为字符串 "none" 且 fields 为空对象。\n'
        "- 从用户指令中提取各字段值填入 fields；用户明确给出的字段必须使用，"
        "未涉及的字段设为 null（不要自行编造）。\n"
        "- 枚举字段只能用允许值；不能确定的枚举字段留 null 并交给管理员补全。\n"
        "- name 必填：若用户未给出频道名称，请依据其意图拟一个清晰贴合的频道名；"
        "若完全无法确定（如动作非新增频道）则置 null。\n"
        "- 若用户只是闲聊或询问与调度无关的问题，action_id 必须为 \"none\"。\n"
        "输出格式（严格 JSON，仅输出 JSON 本身，不要任何其他内容/注释/代码块）：\n"
        "{\"action_id\": \"<id>\", \"fields\": {\"<key>\": <value>}, "
        "\"reason\": \"<一句话说明解析依据（30 字内）>\"}\n"
    )


async def _call_llm_plan(db: AsyncSession, user_message: str, model: str = "") -> tuple[dict, str, str | None]:
    """调用 LLM 将用户指令解析为动作 JSON，复用已保存配置与用量记录。

    Returns:
        (data_or_empty, raw_reply, error_msg|None)
        - data_or_empty: 解析后的 JSON dict；解析失败时为 {}
        - raw_reply: LLM 原始回复文本（供闲聊/非调度场景直接展示）
    """
    svc = AIConfigService(db)
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": user_message},
    ]
    result = await svc.chat_with_model(base_url="", api_key="", model=model, messages=messages)
    if not result.get("success"):
        return {}, "", result.get("message", "AI 解析失败")
    raw = (result.get("reply") or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("智能助手 LLM 响应 JSON 解析失败: %s, raw=%s", e, raw[:200], exc_info=True)
        return {}, raw, "模型返回无法解析，请重试"
    if not isinstance(data, dict):
        return {}, raw, "模型返回结构异常"
    return data, raw, None


def _normalize_field(field: dict, raw_val: Any) -> Any:
    """按字段类型对 LLM 返回的字段值做归一化。"""
    if raw_val is None:
        return field.get("default")
    ftype = field.get("type")
    if ftype == "switch":
        # LLM 可能返回 true/false/1/0，统一成后端整数 1/0
        return 1 if raw_val in (True, 1, "1", "true", "on") else 0
    if ftype == "number":
        try:
            return int(raw_val)
        except (TypeError, ValueError):
            return field.get("default")
    if ftype == "select":
        options = field.get("options") or []
        if options:
            valid = {o["value"] for o in options}
            if raw_val not in valid:
                return field.get("default")
        return raw_val
    # text / textarea
    if raw_val is None:
        return None
    return str(raw_val).strip() or None


async def plan_action(
    db: AsyncSession, user_message: str, model: str = ""
) -> tuple[dict | None, str | None]:
    """把用户自然语言指令解析为动作草稿，返回前端可渲染的数据。

    Returns:
        (payload, error_msg|None)
        payload: {"action_id", "target_route", "title", "group",
                  "is_action": bool, "reason", "fields": [schema+value 合并的可编辑字段]}
    """
    data, raw_reply, err = await _call_llm_plan(db, user_message, model)
    if err:
        return None, err

    action_id = data.get("action_id") or "none"
    action = ASSISTANT_ACTIONS.get(action_id)

    # 非调度意图 / 无法匹配动作：转普通对话，直接返回模型原文回复
    if action is None:
        return {
            "action_id": "none",
            "target_route": "",
            "title": "",
            "group": "",
            "is_action": False,
            "reason": data.get("reason", ""),
            "raw_reply": raw_reply or "（无法解析为调度动作）",
            "fields": [],
        }, None

    raw_fields = data.get("fields") or {}
    if not isinstance(raw_fields, dict):
        raw_fields = {}

    # 按注册表顺序输出，并做类型/值归一化，避免 LLM 幻觉值污染前端表单
    merged = [
        {**field, "value": _normalize_field(field, raw_fields.get(field["key"]))}
        for field in action["fields"]
    ]

    return {
        "action_id": action["action_id"],
        "target_route": action["target_route"],
        "title": action["title"],
        "group": action["group"],
        "is_action": True,
        "reason": data.get("reason", ""),
        "fields": merged,
    }, None


async def execute_action(db: AsyncSession, action: dict) -> tuple[dict | None, str | None]:
    """校验并落地一个经管理员确认的动作草稿。

    入参 action 的 fields 为已归一化字典 {key: value}，其中频道字段已由路由层
    通过 ChannelCreateRequest 校验（schedule_time 归一化、各枚举/number 范围）。
    服务层只负责组装并调用业务 Service 落地，不重复校验规则。

    Returns:
        (result_data, error_msg|None)
        - create_channel 成功返回 {"channel_id": int, "name": str}
    """
    action_id = action.get("action_id")
    if action_id != "create_channel":
        return None, f"暂不支持的动作类型: {action_id}"

    values = action.get("fields") or {}
    if not isinstance(values, dict):
        return None, "动作草稿字段缺失"

    name = str(values.get("name") or "").strip()
    if not name:
        return None, "频道名称不能为空"

    svc = ChannelService(db)
    auto_gen = bool(int(values.get("auto_generate_prompts", 1) or 1))
    try:
        channel = await svc.create_channel(
            name=name,
            description=str(values.get("description") or ""),
            schedule_time=values.get("schedule_time"),
            keywords=(values.get("keywords") or None),
            channel_type=(values.get("channel_type") or "news"),
            disclaimer_level=(values.get("disclaimer_level") or "none"),
            selection_strategy=values.get("selection_strategy"),
            enable_ad=values.get("enable_ad"),
            display_order=int(values.get("display_order") or 0),
            material_lookback_days=values.get("material_lookback_days"),
            cover_url=values.get("cover_url"),
        )
    except ValueError as e:
        return None, str(e)

    if auto_gen:
        try:
            from app.services.channel_prompt_service import generate_prompts_for_channel

            prompts = await generate_prompts_for_channel(channel.name, channel.description or "")
            await svc.update_channel(
                channel_id=channel.id,
                intro_prompt=prompts["intro_prompt"],
                outro_prompt=prompts["outro_prompt"],
                constraint_prompt=prompts["constraint_prompt"],
                rewrite_template=prompts["rewrite_template"],
            )
        except Exception as e:  # NOSONAR: 明确吞掉并告警，不阻塞频道创建
            logger.warning("智能助手创建频道后自动生成提示词失败: %s", e, exc_info=True)

    logger.info("智能助手创建频道 channel_id=%s name=%s", channel.id, channel.name)
    return {"channel_id": channel.id, "name": channel.name}, None