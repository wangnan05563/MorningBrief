"""B 端智能助手路由。

端点（全部 require_admin）：
- GET  /admin/api/v1/assistant/actions    动作注册表（字段 schema，供前端动态表单渲染）
- POST /admin/api/v1/assistant/plan       解析用户自然语言指令为动作草稿（仅规划，不落地）
- POST /admin/api/v1/assistant/execute    落地一个经管理员确认的动作草稿

设计说明：
- 智能助手把「对系统菜单做自动调度」的意图解析为结构化动作草稿（字段级），
  再由管理员在会话内确认后落地，落地复用已有业务 Service（如 ChannelService），
  因此不会绕过既有校验/缓存/事件链。
- 路由层负责 Pydantic 校验（复用 ChannelCreateRequest 保证频道字段契约一致），
  服务层（assistant_service）只做 LLM 解析与业务分发，符合四层依赖方向。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, require_admin
from app.core.response import success, error
from app.database import get_db
from app.routers.admin.channels import ChannelCreateRequest
from app.services.assistant_service import (
    ASSISTANT_ACTIONS,
    execute_action,
    plan_action,
)

router = APIRouter(prefix="/admin/api/v1/assistant", tags=["B端-智能助手"])


class PlanBody(BaseModel):
    """智能助手解析请求体。"""
    # 管理员的自然语言调度指令，如「帮我新增一个 AI 咨询频道」
    message: str = Field(..., min_length=1)
    # 可选，指定使用的模型；留空使用已保存的默认模型
    model: str = ""


class ExecuteBody(BaseModel):
    """落地动作请求体。"""
    action_id: str
    # 字段 key:value 字典；频道字段将经过 ChannelCreateRequest 校验
    fields: dict


@router.get("/actions")
async def list_actions(admin: AdminPayload = Depends(require_admin)):
    """返回可调度动作注册表（含字段 schema），供前端动态渲染确认表单。"""
    return success(data=list(ASSISTANT_ACTIONS.values()))


@router.post("/plan")
async def plan(
    body: PlanBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """把用户的自然语言指令解析为动作草稿，返回待确认的可编辑字段。

    若指令不匹配任何调度动作（闲聊/问答），is_action=false 并附 LLM 原文回复。
    """
    payload, err = await plan_action(db, body.message, body.model)
    if err:
        return error(400, err)
    return success(data=payload)


@router.post("/execute")
async def execute(
    body: ExecuteBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """落地一个经管理员确认的动作草稿。

    第一版仅支持 create_channel；频道字段经 ChannelCreateRequest 校验后调用
    ChannelService.create_channel 落地，成功返回 channel_id/name 供跳转频道管理。
    """
    if body.action_id != "create_channel":
        return error(400, f"暂不支持的动作类型: {body.action_id}")

    fields = body.fields or {}
    # 素材回溯天数仅当为正整数时透传；0 视为未设置（留空继承动态回溯），
    # 否则 ChannelCreateRequest 校验会因 0 小于 1 报 422，影响已确认草稿落地
    material_lookback = fields.get("material_lookback_days")
    if not isinstance(material_lookback, int) or material_lookback < 1:
        material_lookback = None

    # 仅保留 create_channel 支持的字段，并复用 Pydantic 校验（枚举/范围/时间归一化）
    try:
        req = ChannelCreateRequest(
            name=fields.get("name") or "",
            description=fields.get("description") or "",
            schedule_time=fields.get("schedule_time"),
            keywords=fields.get("keywords"),
            channel_type=fields.get("channel_type") or "news",
            disclaimer_level=fields.get("disclaimer_level") or "none",
            selection_strategy=fields.get("selection_strategy"),
            enable_ad=fields.get("enable_ad"),
            display_order=fields.get("display_order") or 0,
            material_lookback_days=material_lookback,
            cover_url=fields.get("cover_url"),
        )
    except ValueError as e:
        return error(422, str(e))

    # 组装校验后的字段字典 + 前端 UI 开关，交由服务层落地
    action = {
        "action_id": "create_channel",
        "fields": {
            "name": req.name,
            "description": req.description,
            "schedule_time": req.schedule_time,
            "keywords": req.keywords,
            "channel_type": req.channel_type,
            "disclaimer_level": req.disclaimer_level,
            "selection_strategy": req.selection_strategy,
            "enable_ad": req.enable_ad,
            "display_order": req.display_order,
            "material_lookback_days": req.material_lookback_days,
            "cover_url": req.cover_url,
            "auto_generate_prompts": body.fields.get("auto_generate_prompts", 1),
        },
    }
    data, err = await execute_action(db, action)
    if err:
        return error(400, err)
    return success(data=data, message=f"频道「{data['name']}」已创建")