"""B 端频道管理路由。"""
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query, UploadFile, File
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache as cache_manager
from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.response import success, error
from app.database import get_db
from app.paths import resolve_bgm_dir
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
    # 频道级 BGM：相对 data/bgm/ 的路径，为空使用全局配置
    bgm_path: str | None = None
    bgm_volume: float | None = None
    # 频道级段间静音时长（秒），为空使用全局配置
    segment_gap_sec: float | None = None
    # 每段新闻末尾是否追加思考问题，None=默认开启
    enable_thinking_question: int | None = None
    # 频道专属 RSS 源列表（JSON 数组字符串，如 '["游民星空-资讯"]'），为空使用全部源
    rss_sources: str | None = None
    # 频道关键词过滤（逗号分隔，如 "游戏,主机,PS5"），为空表示不过滤
    keywords: str | None = None
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

    @field_validator("bgm_volume")
    @classmethod
    def validate_bgm_volume(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not (0.0 <= v <= 1.0):
            raise ValueError("bgm_volume 必须在 0.0-1.0 之间")
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
    enable_thinking_question: int | None = None
    rss_sources: str | None = None
    keywords: str | None = None

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

    @field_validator("bgm_volume")
    @classmethod
    def validate_bgm_volume(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not (0.0 <= v <= 1.0):
            raise ValueError("bgm_volume 必须在 0.0-1.0 之间")
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
        "enable_thinking_question": ch.enable_thinking_question,
        "rss_sources": ch.rss_sources,
        "keywords": ch.keywords,
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
            enable_thinking_question=req.enable_thinking_question,
            rss_sources=req.rss_sources,
            keywords=req.keywords,
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
            enable_thinking_question=req.enable_thinking_question,
            rss_sources=req.rss_sources,
            keywords=req.keywords,
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


# ===================== BGM 管理 =====================

# 允许的 BGM 音频扩展名（白名单，避免上传可执行文件）
_BGM_ALLOWED_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
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

    custom_dir = resolve_bgm_dir() / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    target = custom_dir / safe_name
    # 重名时追加时间戳后缀，避免覆盖
    if target.exists():
        stem = Path(safe_name).stem
        target = custom_dir / f"{stem}_{int(__import__('time').time())}{ext}"

    # 流式写入 + 大小校验，避免大文件占满内存
    written = 0
    with open(target, "wb") as fp:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > _BGM_MAX_SIZE:
                fp.close()
                target.unlink(missing_ok=True)
                return error(code=400, message=f"文件过大，上限 {_BGM_MAX_SIZE // 1024 // 1024}MB")
            fp.write(chunk)

    rel_path = f"custom/{target.name}"
    return success(data={
        "path": rel_path,
        "name": target.stem,
        "size_kb": round(written / 1024, 1),
    })


@router.delete("/bgm/{path:path}")
async def delete_bgm(
    path: str,
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
    return success(data={"deleted": path})


# ===================== RSS 源管理 =====================

@router.get("/rss/sources")
async def list_rss_sources(
    admin: AdminPayload = Depends(get_current_admin),
):
    """列出 rss.yaml 中所有可用的 RSS 源，供频道配置选择。

    admin + operator 均可查看。返回源名称、品类、权威度，前端用于多选下拉。
    """
    import yaml
    from pathlib import Path as PathLib

    rss_path = PathLib(__file__).parent.parent.parent / "workflow" / "crawler" / "sources" / "rss.yaml"
    if not rss_path.exists():
        return success(data={"sources": []})

    with open(rss_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sources = [
        {
            "name": s.get("name", ""),
            "category_hint": s.get("category_hint", ""),
            "authority": s.get("authority", 0.5),
        }
        for s in config.get("sources", [])
    ]
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
        return error(code=404, message="频道不存在")

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
