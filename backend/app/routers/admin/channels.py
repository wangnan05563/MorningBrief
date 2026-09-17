"""B 端频道管理路由。"""
import logging
import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query, UploadFile, File
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache as cache_manager
from app.core.audio_modes import VALID_GAP_MODES
from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success, error
from app.database import get_db
from app.models import AuditLog, Channel
from app.paths import resolve_bgm_dir, resolve_channel_asset_dir
from app.services.channel_service import ChannelService, _TTL_CHANNELS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/channels", tags=["B端-频道管理"])

# 频道不存在错误消息常量（统一字面量，避免 S1192 字符串重复告警）
_CHANNEL_NOT_FOUND_MSG = "频道不存在"


def _normalize_schedule_time(v: str) -> str:
    """将宽松的定时时间输入归一化为 HH:MM:SS。

    兼容用户常见的简写形式（前端为自由文本输入框，未强制零填充）：
    - 2 段：H:MM / HH:MM（秒默认补 0），如 "4:00" -> "04:00:00"
    - 3 段：H:MM:SS / HH:MM:SS，如 "4:0:5" -> "04:00:05"
    前后空格会被忽略；各段按 2 位零填充。非法格式抛出 ValueError 由 Pydantic 转 422。
    """
    v = v.strip()
    parts = v.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("schedule_time 格式应为 HH:MM:SS（或 HH:MM）")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        raise ValueError("schedule_time 时分秒必须为数字")
    if len(nums) == 2:
        h, m = nums
        s = 0
    else:
        h, m, s = nums
    if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError("schedule_time 时分秒超出范围")
    return f"{h:02d}:{m:02d}:{s:02d}"


class ChannelCreateRequest(BaseModel):
    """新增频道请求体。"""
    name: str
    description: str = ""
    schedule_time: str | None = None
    intro_prompt: str | None = None
    outro_prompt: str | None = None
    constraint_prompt: str | None = None
    rewrite_template: str | None = None
    # 频道级 BGM：相对 data/bgm/ 的路径，为空使用全局配置
    bgm_path: str | None = None
    bgm_volume: float | None = None
    # 频道级段间静音时长（秒），为空使用全局配置
    segment_gap_sec: float | None = None
    # 频道级段间 BGM 模式："silence"=真实静音；"bridge"=BGM 桥接；None=继承全局
    bgm_gap_mode: str | None = None
    # 每段新闻末尾是否追加思考问题，None=默认开启 # NOSONAR
    enable_thinking_question: int | None = None
    # 频道专属 RSS 源列表（JSON 数组字符串，如 '["游民星空-资讯"]'），为空使用全部源
    rss_sources: str | None = None
    # 频道专属书籍 RSS 源列表（JSON 数组字符串，如 '["豆瓣读书-书评"]'），仅 audiobook 频道使用
    book_rss_sources: str | None = None
    # 频道关键词过滤（逗号分隔，如 "游戏,主机,PS5"），为空表示不过滤
    keywords: str | None = None
    min_duration_sec: int | None = None
    # 展示排序权重：值越小越靠前；相等时按 id 兜底。运营可调整以控制小程序 tab 顺序
    display_order: int = 0
    # 频道级素材周期回溯天数：当日素材不足时自动放宽到最近 N 天选材；为空回退动态值
    material_lookback_days: int | None = None
    # 业务范围扩展：选题策略 heat(默认)/outline/manual；课程/资料频道用 outline
    selection_strategy: str | None = None
    # 是否投放广告：1=投放(默认，兼容存量)，0=关闭；课程/资料频道设 0 实现零广告
    enable_ad: int | None = None
    # manual 选题策略的素材 ID 列表（JSON 数组文本），仅 selection_strategy=manual 时生效
    manual_material_ids: str | None = None
    # 多频道适配 M2：频道类型 news(默认)/course/audiobook，驱动小程序皮肤与课程链路
    channel_type: str = "news"
    # 类型中文标签（冗余存储，避免前端硬编码）：如 "资讯"/"课程"/"有声读物"
    type_label: str | None = None
    # 频道封面图 URL（小程序频道卡片/课程头图），为空用类型默认封面兜底
    cover_url: str | None = None
    # 风险提示等级 none(默认)/normal/strong：课程/资料类须显式 strong 提示
    disclaimer_level: str = "none"
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
        """校验并归一化定时时间：兼容 HH:MM:SS 与 HH:MM，统一输出 HH:MM:SS。"""
        if v is None or v == "":
            return None
        return _normalize_schedule_time(v)

    @field_validator("bgm_volume")
    @classmethod
    def validate_bgm_volume(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not (0.0 <= v <= 1.0):
            raise ValueError("bgm_volume 必须在 0.0-1.0 之间")
        return v

    @field_validator("bgm_gap_mode")
    @classmethod
    def validate_bgm_gap_mode(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            # 空字符串视为"继承全局"：兜底前端 inherit_bgm_gap 发送 null 之外的脏输入
            return None
        if v not in VALID_GAP_MODES:
            raise ValueError("bgm_gap_mode 仅支持 " + " / ".join(VALID_GAP_MODES))
        return v

    @field_validator("material_lookback_days")
    @classmethod
    def validate_material_lookback_days(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v < 1:
            raise ValueError("material_lookback_days 必须为正整数（≥1）")
        if v > 90:
            raise ValueError("material_lookback_days 超出上限 90 天")
        return v

    @field_validator("selection_strategy")
    @classmethod
    def validate_selection_strategy(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if v not in ("heat", "outline", "manual"):
            raise ValueError("selection_strategy 仅支持 heat / outline / manual")
        return v

    @field_validator("enable_ad")
    @classmethod
    def validate_enable_ad(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v not in (0, 1):
            raise ValueError("enable_ad 仅支持 0 / 1")
        return v

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        v = (v or "news").strip()
        if v not in ("news", "course", "audiobook"):
            raise ValueError("channel_type 仅支持 news / course / audiobook")
        return v

    @field_validator("disclaimer_level")
    @classmethod
    def validate_disclaimer_level(cls, v: str) -> str:
        v = (v or "none").strip()
        if v not in ("none", "normal", "strong"):
            raise ValueError("disclaimer_level 仅支持 none / normal / strong")
        return v

    @field_validator("cover_url")
    @classmethod
    def validate_cover_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if len(v) > 256:
            raise ValueError("cover_url 不能超过 256 字符")
        return v


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
    bgm_path: str | None = None
    bgm_volume: float | None = None
    segment_gap_sec: float | None = None
    # 频道级段间 BGM 模式："silence"=真实静音；"bridge"=BGM 桥接；None=继承全局
    bgm_gap_mode: str | None = None
    enable_thinking_question: int | None = None
    rss_sources: str | None = None
    book_rss_sources: str | None = None
    keywords: str | None = None
    # 展示排序权重：值越小越靠前；相等时按 id 兜底。运营可调整以控制小程序 tab 顺序
    display_order: int | None = None
    # 频道级素材周期回溯天数：当日素材不足时自动放宽到最近 N 天选材；为空回退动态值
    material_lookback_days: int | None = None
    # 业务范围扩展：选题策略 heat(默认)/outline/manual；课程/资料频道用 outline
    selection_strategy: str | None = None
    # 是否投放广告：1=投放(默认，兼容存量)，0=关闭；课程/资料频道设 0 实现零广告
    enable_ad: int | None = None
    # manual 选题策略的素材 ID 列表（JSON 数组文本），仅 selection_strategy=manual 时生效
    manual_material_ids: str | None = None
    # 多频道适配 M2：频道类型 news/course/audiobook；课程频道须配合 selection_strategy=outline
    channel_type: str | None = None
    # 类型中文标签（冗余存储）
    type_label: str | None = None
    # 频道封面图 URL
    cover_url: str | None = None
    # 风险提示等级 none/normal/strong
    disclaimer_level: str | None = None

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return ""
        return _normalize_schedule_time(v)

    @field_validator("bgm_volume")
    @classmethod
    def validate_bgm_volume(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not (0.0 <= v <= 1.0):
            raise ValueError("bgm_volume 必须在 0.0-1.0 之间")
        return v

    @field_validator("bgm_gap_mode")
    @classmethod
    def validate_bgm_gap_mode(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            # 空字符串视为"继承全局"：兜底前端 inherit_bgm_gap 发送 null 之外的脏输入
            return None
        if v not in VALID_GAP_MODES:
            raise ValueError("bgm_gap_mode 仅支持 " + " / ".join(VALID_GAP_MODES))
        return v

    @field_validator("material_lookback_days")
    @classmethod
    def validate_material_lookback_days(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v < 1:
            raise ValueError("material_lookback_days 必须为正整数（≥1）")
        if v > 90:
            raise ValueError("material_lookback_days 超出上限 90 天")
        return v

    @field_validator("selection_strategy")
    @classmethod
    def validate_selection_strategy(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if v not in ("heat", "outline", "manual"):
            raise ValueError("selection_strategy 仅支持 heat / outline / manual")
        return v

    @field_validator("enable_ad")
    @classmethod
    def validate_enable_ad(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v not in (0, 1):
            raise ValueError("enable_ad 仅支持 0 / 1")
        return v

    @field_validator("channel_type")
    @classmethod
    def validate_channel_type(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if v not in ("news", "course", "audiobook"):
            raise ValueError("channel_type 仅支持 news / course / audiobook")
        return v

    @field_validator("disclaimer_level")
    @classmethod
    def validate_disclaimer_level(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if v not in ("none", "normal", "strong"):
            raise ValueError("disclaimer_level 仅支持 none / normal / strong")
        return v

    @field_validator("cover_url")
    @classmethod
    def validate_cover_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        if len(v) > 256:
            raise ValueError("cover_url 不能超过 256 字符")
        return v


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
        "bgm_path": ch.bgm_path,
        "bgm_volume": ch.bgm_volume,
        "segment_gap_sec": ch.segment_gap_sec,
        "bgm_gap_mode": ch.bgm_gap_mode,
        "enable_thinking_question": ch.enable_thinking_question,
        "rss_sources": ch.rss_sources,
        "book_rss_sources": ch.book_rss_sources,
        "keywords": ch.keywords,
        "min_duration_sec": ch.min_duration_sec,
        "display_order": ch.display_order,
        "material_lookback_days": ch.material_lookback_days,
        "selection_strategy": ch.selection_strategy,
        "enable_ad": ch.enable_ad,
        "manual_material_ids": ch.manual_material_ids,
        "channel_type": ch.channel_type,
        "type_label": ch.type_label,
        "cover_url": ch.cover_url,
        "disclaimer_level": ch.disclaimer_level,
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
            bgm_path=req.bgm_path,
            bgm_volume=req.bgm_volume,
            segment_gap_sec=req.segment_gap_sec,
            bgm_gap_mode=req.bgm_gap_mode,
            enable_thinking_question=req.enable_thinking_question,
            rss_sources=req.rss_sources,
            book_rss_sources=req.book_rss_sources,
            keywords=req.keywords,
            min_duration_sec=req.min_duration_sec,
            display_order=req.display_order,
            material_lookback_days=req.material_lookback_days,
            selection_strategy=req.selection_strategy,
            enable_ad=req.enable_ad,
            manual_material_ids=req.manual_material_ids,
            channel_type=req.channel_type,
            type_label=req.type_label,
            cover_url=req.cover_url,
            disclaimer_level=req.disclaimer_level,
            intro_prompt=req.intro_prompt,
            outro_prompt=req.outro_prompt,
            constraint_prompt=req.constraint_prompt,
            rewrite_template=req.rewrite_template,
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
            bgm_path=req.bgm_path,
            bgm_volume=req.bgm_volume,
            segment_gap_sec=req.segment_gap_sec,
            bgm_gap_mode=req.bgm_gap_mode,
            enable_thinking_question=req.enable_thinking_question,
            rss_sources=req.rss_sources,
            book_rss_sources=req.book_rss_sources,
            keywords=req.keywords,
            display_order=req.display_order,
            material_lookback_days=req.material_lookback_days,
            selection_strategy=req.selection_strategy,
            enable_ad=req.enable_ad,
            manual_material_ids=req.manual_material_ids,
            channel_type=req.channel_type,
            type_label=req.type_label,
            cover_url=req.cover_url,
            disclaimer_level=req.disclaimer_level,
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
        return error(code=404, message=_CHANNEL_NOT_FOUND_MSG)

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
    # 审计日志：频道删除会级联影响历史工作流的归属，记录操作人便于追溯
    db.add(AuditLog(
        category="channel",
        action="delete",
        target=str(channel_id),
        operator=admin.username,
        detail=json.dumps({"channel_id": channel_id}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"deleted": True})


# ===================== BGM 管理 =====================

# 允许的 BGM 音频扩展名（白名单，避免上传可执行文件）
_BGM_ALLOWED_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
# content_type 白名单：与扩展名白名单对齐，双重校验防止伪造扩展名上传非音频文件
_BGM_ALLOWED_CONTENT_TYPES = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a"},
    ".aac": {"audio/aac", "audio/x-aac"},
    ".ogg": {"audio/ogg", "application/ogg"},
}
# BGM 文件大小上限：20MB（BGM 通常 3-5MB，20MB 足够覆盖长曲）
_BGM_MAX_SIZE = 20 * 1024 * 1024


def _scan_bgm_files() -> list[dict]:
    """扫描 BGM 目录，返回预制 + 自定义 BGM 列表。

    返回结构：[{path, name, category, size_kb}]
    path 为相对 data/bgm/ 的路径（存入 channel.bgm_path），前端通过 /bgm/{path} 试听
    """
    bgm_root = resolve_bgm_dir()
    result = []
    for category in ("preset", "custom"):
        cat_dir = bgm_root / category
        if not cat_dir.is_dir():
            continue
        for f in sorted(cat_dir.iterdir()):
            if not f.is_file() or f.suffix.lower() not in _BGM_ALLOWED_EXTS:
                continue
            # 相对路径用 forward slash，与 URL 路径分隔符一致
            rel_path = f"{category}/{f.name}"
            result.append({
                "path": rel_path,
                "name": f.stem,
                "category": "预制" if category == "preset" else "自定义",
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return result


@router.get("/bgm/list")
async def list_bgm(
    admin: AdminPayload = Depends(get_current_admin),
):
    """列出所有可用 BGM 文件（预制 + 用户上传）。

    admin + operator 均可查看，用于频道表单的下拉选择。
    """
    files = _scan_bgm_files()
    return success(data={"list": files})


@router.post("/bgm/upload")
async def upload_bgm(
    file: UploadFile = File(...),
    admin: AdminPayload = Depends(require_admin),
):
    """上传 BGM 文件到 data/bgm/custom/。仅 admin。

    文件名清理：去除路径分隔符和特殊字符，避免目录穿越。
    重名时追加时间戳，避免覆盖已有文件。
    """
    if not file.filename:
        return error(code=400, message="文件名不能为空")

    # 清理文件名：仅保留字母数字中文._-，防止目录穿越和特殊字符
    raw_name = os.path.basename(file.filename)
    safe_name = re.sub(r'[^\w\u4e00-\u9fa5.\-]', '_', raw_name)
    ext = Path(safe_name).suffix.lower()
    if ext not in _BGM_ALLOWED_EXTS:
        return error(
            code=400,
            message=f"不支持的音频格式：{ext}，允许：{', '.join(_BGM_ALLOWED_EXTS)}",
        )

    # content_type 双重校验：防止伪造扩展名上传非音频文件
    received_ct = (file.content_type or "").lower()
    allowed_cts = _BGM_ALLOWED_CONTENT_TYPES.get(ext, set())
    if received_ct and allowed_cts and received_ct not in allowed_cts:
        return error(
            code=400,
            message=f"文件 content_type 与扩展名不匹配：{received_ct} vs {ext}",
        )

    custom_dir = resolve_bgm_dir() / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    target = custom_dir / safe_name
    # 重名时追加时间戳后缀，避免覆盖
    if target.exists():
        stem = Path(safe_name).stem
        target = custom_dir / f"{stem}_{int(__import__('time').time())}{ext}"

    # 流式写入 + 大小校验，避免大文件占满内存
    written = 0
    # open() 仅创建文件句柄不阻塞事件循环，写操作通过 to_thread 异步化
    with open(target, "wb") as fp:  # NOSONAR
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > _BGM_MAX_SIZE:
                fp.close()
                target.unlink(missing_ok=True)
                return error(code=400, message=f"文件过大，上限 {_BGM_MAX_SIZE // 1024 // 1024}MB")
            await asyncio.to_thread(fp.write, chunk)

    rel_path = f"custom/{target.name}"
    return success(data={
        "path": rel_path,
        "name": target.stem,
        "size_kb": round(written / 1024, 1),
    })


@router.delete("/bgm/{path:path}")
async def delete_bgm(
    path: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除自定义 BGM 文件。仅 admin。

    仅允许删除 custom/ 下的文件，preset/ 受保护不可删。
    path 参数为相对 data/bgm/ 的路径（与上传返回的 path 一致）。
    """
    # 安全校验：仅允许 custom/ 前缀，防止通过 ../ 访问其他目录
    if not path.startswith("custom/"):
        return error(code=400, message="仅允许删除自定义 BGM")
    target = resolve_bgm_dir() / path
    # resolve 后再次确认仍在 bgm 目录内，防止符号链接穿越
    try:
        target.resolve().relative_to(resolve_bgm_dir().resolve())
    except ValueError:
        return error(code=400, message="非法路径")

    if not target.is_file():
        return error(code=404, message="BGM 文件不存在")

    target.unlink()
    # 审计日志：BGM 删除影响依赖该文件的频道配置，记录操作人与文件路径
    db.add(AuditLog(
        category="channel",
        action="delete_bgm",
        target=path,
        operator=admin.username,
        detail=json.dumps({"path": path}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"deleted": path})


# ===================== RSS 源管理 =====================

@router.get("/rss/sources")
async def list_rss_sources(
    admin: AdminPayload = Depends(get_current_admin),
):
    """列出 rss.yaml 中所有可用的 RSS 源，供频道配置选择。

    admin + operator 均可查看。返回源名称、品类、权威度，前端用于多选下拉。
    """
    from app.services.rss_source_service import load_rss_sources_summary
    sources = load_rss_sources_summary()
    return success(data={"sources": sources})


@router.get("/book-rss/sources")
async def list_book_rss_sources(
    admin: AdminPayload = Depends(get_current_admin),
):
    """列出 book_rss.yaml 中所有可用的书籍 RSS 预制源，供 audiobook 频道配置选择。

    admin + operator 均可查看。返回源名称、品类、权威度，前端用于多选下拉。
    该预制源面向有声读物场景（条目即书/章），由 crawler 仅对 audiobook 频道加载。
    """
    from app.services.rss_source_service import (
        load_book_fulltext_sources_summary,
        load_book_rss_sources_summary,
    )
    # T00603：全文源与 RSS 书源合并返回，kind 字段区分（book_rss / fulltext），
    # 前端多选下拉直接展示全部可选书籍源；旧前端忽略 kind 也不受影响。
    sources = load_book_rss_sources_summary() + load_book_fulltext_sources_summary()
    return success(data={"sources": sources})


@router.post("/{channel_id}/recommend-bgm")
async def recommend_bgm(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """AI 推荐频道 BGM。仅 admin。

    根据频道 name + description + 可用 BGM 列表，调用 LLM 推荐最匹配的 BGM。
    LLM 仅返回 BGM path，不修改频道记录，前端确认后再保存。
    """
    svc = ChannelService(db)
    channel = await svc.get_channel(channel_id)
    if channel is None:
        return error(code=404, message=_CHANNEL_NOT_FOUND_MSG)

    bgm_list = _scan_bgm_files()
    if not bgm_list:
        return error(code=400, message="无可用 BGM，请先上传或添加预制 BGM")

    try:
        from app.services.channel_prompt_service import recommend_bgm_for_channel
        recommendation = await recommend_bgm_for_channel(
            channel.name, channel.description or "", bgm_list,
        )
    except ValueError as e:
        return error(code=400, message=str(e))

    return success(data=recommendation)


@router.post("/{channel_id}/recommend-sources")
async def recommend_sources(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """AI 推荐频道 RSS 源与关键词。仅 admin。

    根据频道 name + description + 可用 RSS 源列表，调用 LLM 推荐最匹配的源子集与关键词。
    LLM 仅返回推荐结果，不修改频道记录，前端确认后再保存。
    与 recommend-bgm 路由结构保持一致，便于后续扩展为多字段联合推荐。
    """
    svc = ChannelService(db)
    channel = await svc.get_channel(channel_id)
    if channel is None:
        return error(code=404, message=_CHANNEL_NOT_FOUND_MSG)

    # 复用 rss_source_service 统一加载逻辑，避免路径拼接散落多处
    from app.services.rss_source_service import load_rss_sources_summary
    rss_list = load_rss_sources_summary()
    if not rss_list:
        return error(code=400, message="无可用 RSS 源，请先在 rss.yaml 中配置")

    try:
        from app.services.channel_prompt_service import recommend_rss_keywords_for_channel
        recommendation = await recommend_rss_keywords_for_channel(
            channel.name, channel.description or "", rss_list,
        )
    except ValueError as e:
        return error(code=400, message=str(e))

    return success(data=recommendation)


# ===== T00730 频道图标：上传 / AI 生成 =====

_ICON_ALLOWED = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
_ICON_MAX_BYTES = 2 * 1024 * 1024  # 2MB


def _media_base_url() -> str:
    """静态资源对外基础 URL（与音频/封面同源；复用 settings 的 audio_base_url 逻辑太重，此处取请求基址）。"""
    return ""


def _asset_url(filename: str) -> str:
    """拼接 /channel-assets 静态 URL（相对路径，前端按当前 API 域名补全）。"""
    return f"/channel-assets/{filename}"


@router.get("/cover-presets")
async def list_cover_presets(
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """列出预制频道封面（T00731），供「编辑频道」页直接选图，免手输 URL。

    扫描 channel_assets 目录下 channel_{id}.{jpg|png|webp}，文件名中的 id 与频道对齐，
    频道名作为展示标签返回；按频道 id 升序，便于与频道列表同序浏览。
    """
    asset_dir = resolve_channel_asset_dir()
    result = await db.execute(select(Channel.id, Channel.name))
    name_by_id = {cid: cname for cid, cname in result.all()}

    presets: list[dict] = []
    for path in sorted(asset_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        # 只认预制封面命名（channel_{id}.ext），排除 channel_{id}_icon.ext 图标文件
        m = re.fullmatch(r"channel_(\d+)", path.stem)
        if not m:
            continue
        cid = int(m.group(1))
        presets.append({
            "channel_id": cid,
            "name": name_by_id.get(cid, path.stem),
            "url": _asset_url(path.name),
            "size_kb": round(path.stat().st_size / 1024, 1),
        })
    presets.sort(key=lambda p: p["channel_id"])
    return success(data=presets)


@router.post("/{channel_id}/icon")
async def upload_channel_icon(
    channel_id: int,
    file: UploadFile = File(..., description="图标文件（PNG/JPG/WebP，≤2MB）"),
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """上传频道图标（T00730）：命名 channel_{id}_icon.{ext}，存 /channel-assets 并写 icon_url。"""
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in _ICON_ALLOWED:
        raise BizError(code=400, message=f"不支持的图标格式：.{ext}（仅支持 PNG/JPG/WebP）")
    raw = await file.read()
    if len(raw) > _ICON_MAX_BYTES:
        raise BizError(code=400, message="图标文件超过 2MB 限制")

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    ch = result.scalar_one_or_none()
    if ch is None:
        raise NotFoundError(f"频道 {channel_id} 不存在")

    filename = f"channel_{channel_id}_icon.{ext}"
    from app.paths import resolve_channel_asset_dir
    dest = resolve_channel_asset_dir() / filename
    dest.write_bytes(raw)

    ch.icon_url = _asset_url(filename)
    await db.commit()
    logger.info("[channel] 频道 %s 图标已上传：%s（%d bytes）", channel_id, filename, len(raw))
    return success(data={"icon_url": ch.icon_url, "filename": filename})


class ChannelIconAIRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=500, description="图标主题描述（如：番茄计时器、财经数据）")


@router.post("/{channel_id}/icon/ai-generate")
async def ai_generate_channel_icon(
    channel_id: int,
    req: ChannelIconAIRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminPayload = Depends(require_admin),
):
    """AI 生成频道图标（T00730）：按主题描述生成图标并直接设为频道图标（预览即返回 URL）。

    生成失败（服务未配置/网络不可达）抛明确错误，不落库、不影响原图标。
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    ch = result.scalar_one_or_none()
    if ch is None:
        raise NotFoundError(f"频道 {channel_id} 不存在")

    from app.services import image_gen_service

    prompt = (
        f"Flat minimal app icon for a channel about {req.prompt.strip()}. "
        "Rounded square composition, mint blue and deep navy palette, clean vector style, "
        "centered single subject, no text, no watermark."
    )
    try:
        raw = await asyncio.to_thread(
            image_gen_service.generate_image, prompt, size="1K", ratio="1:1"
        )
    except image_gen_service.ImageGenError as e:
        raise BizError(code=502, message=f"AI 生成失败：{e}")

    filename = f"channel_{channel_id}_icon.png"
    from app.paths import resolve_channel_asset_dir
    (resolve_channel_asset_dir() / filename).write_bytes(raw)

    ch.icon_url = _asset_url(filename)
    await db.commit()
    logger.info("[channel] 频道 %s 图标 AI 生成成功：%s（%d bytes）", channel_id, filename, len(raw))
    return success(data={"icon_url": ch.icon_url, "filename": filename, "prompt": req.prompt})
