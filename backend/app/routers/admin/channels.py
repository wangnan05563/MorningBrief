"""B 端频道管理路由。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache as cache_manager
from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success, error
from app.database import get_db
from app.services.channel_service import ChannelService, _TTL_CHANNELS

router = APIRouter(prefix="/admin/api/v1/channels", tags=["B端-频道管理"])


class ChannelCreateRequest(BaseModel):
    """新增频道请求体。"""
    name: str
    description: str = ""
    schedule_time: str | None = None
    intro_prompt: str | None = None
    outro_prompt: str | None = None
    constraint_prompt: str | None = None
    rewrite_template: str | None = None
    # 频道创建时是否自动调用 AI 生成提示词
    auto_generate_prompts: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("频道名称不能为空")
        if len(v) > 64:
            raise ValueError("频道名称不能超过 64 字符")
        return v

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time(cls, v: str | None) -> str | None:
        """校验定时时间格式 HH:MM:SS。"""
        if v is None or v == "":
            return None
        v = v.strip()
        parts = v.split(":")
        if len(parts) != 3:
            raise ValueError("schedule_time 格式应为 HH:MM:SS")
        try:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            raise ValueError("schedule_time 时分秒必须为数字")
        if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
            raise ValueError("schedule_time 时分秒超出范围")
        return f"{h:02d}:{m:02d}:{s:02d}"


class ChannelUpdateRequest(BaseModel):
    """修改频道请求体。"""
    name: str | None = None
    description: str | None = None
    is_active: int | None = None
    schedule_time: str | None = None
    intro_prompt: str | None = None
    outro_prompt: str | None = None
    constraint_prompt: str | None = None
    rewrite_template: str | None = None

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return ""
        v = v.strip()
        parts = v.split(":")
        if len(parts) != 3:
            raise ValueError("schedule_time 格式应为 HH:MM:SS")
        try:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            raise ValueError("schedule_time 时分秒必须为数字")
        if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
            raise ValueError("schedule_time 时分秒超出范围")
        return f"{h:02d}:{m:02d}:{s:02d}"


def _channel_to_dict(ch) -> dict:
    """统一频道序列化，避免列表/详情接口字段不一致。"""
    return {
        "id": ch.id,
        "name": ch.name,
        "description": ch.description,
        "is_active": ch.is_active,
        "schedule_time": ch.schedule_time,
        "intro_prompt": ch.intro_prompt,
        "outro_prompt": ch.outro_prompt,
        "constraint_prompt": ch.constraint_prompt,
        "rewrite_template": ch.rewrite_template,
        "created_at": ch.created_at.isoformat() if ch.created_at else None,
        "updated_at": ch.updated_at.isoformat() if ch.updated_at else None,
    }


@router.get("")
async def list_channels(
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """查询频道列表。admin + operator 均可查看。

    cache-aside：频道数据变更频率极低，缓存 5 分钟减少 DB 查询。
    """
    cache_key = f"channels:list:{'active' if active_only else 'all'}"
    cached = await cache_manager.get(cache_key)
    if cached:
        return success(data=cached)

    svc = ChannelService(db)
    channels = await svc.list_channels(active_only=active_only)
    data = [_channel_to_dict(ch) for ch in channels]
    await cache_manager.set(cache_key, data, ttl=_TTL_CHANNELS)
    return success(data=data)


@router.post("")
async def create_channel(
    req: ChannelCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """新增频道。仅 admin。

    auto_generate_prompts=True 时，频道创建后自动调用 AI 生成提示词并回填。
    """
    svc = ChannelService(db)
    try:
        channel = await svc.create_channel(
            name=req.name, description=req.description,
            schedule_time=req.schedule_time,
        )
    except ValueError as e:
        return error(code=400, message=str(e))

    # 按需自动生成提示词（频道创建时 AI 生成，失败不阻塞创建流程）
    if req.auto_generate_prompts:
        try:
            from app.services.channel_prompt_service import generate_prompts_for_channel
            prompts = await generate_prompts_for_channel(req.name, req.description)
            channel = await svc.update_channel(
                channel_id=channel.id,
                intro_prompt=prompts["intro_prompt"],
                outro_prompt=prompts["outro_prompt"],
                constraint_prompt=prompts["constraint_prompt"],
                rewrite_template=prompts["rewrite_template"],
            )
        except Exception as e:
            # AI 生成失败不影响频道创建，用户可后续手动生成
            import logging
            logging.getLogger(__name__).warning("频道创建时 AI 生成提示词失败: %s", e)

    return success(data=_channel_to_dict(channel))


@router.put("/{channel_id}")
async def update_channel(
    channel_id: int,
    req: ChannelUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """修改频道。仅 admin。"""
    svc = ChannelService(db)
    try:
        channel = await svc.update_channel(
            channel_id=channel_id,
            name=req.name,
            description=req.description,
            is_active=req.is_active,
            schedule_time=req.schedule_time,
            intro_prompt=req.intro_prompt,
            outro_prompt=req.outro_prompt,
            constraint_prompt=req.constraint_prompt,
            rewrite_template=req.rewrite_template,
        )
    except ValueError as e:
        return error(code=400, message=str(e))
    return success(data=_channel_to_dict(channel))


@router.post("/{channel_id}/generate-prompts")
async def generate_prompts(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """AI 自动生成频道提示词。仅 admin。

    根据频道 name + description 调用 LLM 生成 4 类提示词，
    生成后直接持久化到频道记录，前端可再次编辑覆盖。
    """
    svc = ChannelService(db)
    channel = await svc.get_channel(channel_id)
    if channel is None:
        return error(code=404, message="频道不存在")

    try:
        from app.services.channel_prompt_service import generate_prompts_for_channel
        prompts = await generate_prompts_for_channel(channel.name, channel.description)
    except ValueError as e:
        return error(code=400, message=str(e))

    channel = await svc.update_channel(
        channel_id=channel_id,
        intro_prompt=prompts["intro_prompt"],
        outro_prompt=prompts["outro_prompt"],
        constraint_prompt=prompts["constraint_prompt"],
        rewrite_template=prompts["rewrite_template"],
    )
    return success(data=_channel_to_dict(channel))


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除频道。仅 admin。关联工作流的 channel_id 自动置 NULL。"""
    svc = ChannelService(db)
    try:
        await svc.delete_channel(channel_id=channel_id)
    except ValueError as e:
        return error(code=404, message=str(e))
    return success(data={"deleted": True})
