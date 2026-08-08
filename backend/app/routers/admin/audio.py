"""B 端音频文件管理路由。

提供工作流产物中音频文件的列表、流式播放与删除能力：
- TTS 片段：data/audio_cache/tts/{workflow_id}/*.mp3
- 拼接成品：data/audio_cache/episodes/{episode_date_str}/{channel_slug}_{workflow_id}.mp3

成品命名规则（V1.2+）：含频道名 + workflow_id，避免同日多频道/重试覆盖。
旧版 final.mp3 已废弃，查找时按 workflow_id 后缀匹配。

所有路径均通过 resolve_data_dir() 派生，避免硬编码。

打包模式兼容：COS 已配置时（生产/打包态），TTS 片段与成品仅上传云端，本地
audio_cache 为空。此时 list_audio 回退到 DB 持久化的 audio_url（Script 分段 /
Episode / Review），保证工作流详情页的「语音合成·TTS 片段」「音频拼接·成品」
面板在打包态也能展示内容；播放通过 /audio/proxy 代理远端 COS 对象。
"""
import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.database import get_db
from app.models import AuditLog, Episode, Review, Script, Workflow
from app.paths import resolve_data_dir

logger = logging.getLogger(__name__)

# 模块级配置单例（与运行时其他模块共享同一实例）
settings = get_settings()

router = APIRouter(prefix="/admin/api/v1/workflows", tags=["B端-音频管理"])

# 模块级常量：与 main.py 中 StaticFiles 挂载点保持一致，避免重复构造
_AUDIO_ROOT = resolve_data_dir() / "audio_cache"


def _tts_dir(workflow_id: str) -> Path:
    """工作流对应的 TTS 片段目录。"""
    return _AUDIO_ROOT / "tts" / workflow_id


def _find_episode_file(episode_date_str: str, workflow_id: str) -> Path | None:
    """按 workflow_id 后缀匹配成品音频文件。

    新命名规则：{channel_slug}_{workflow_id}.mp3，channel_slug 长度可变，
    用 glob "*_{workflow_id}.mp3" 匹配，避免依赖频道名反查。
    返回第一个匹配项（理论上唯一），无匹配返回 None。
    """
    ep_dir = _AUDIO_ROOT / "episodes" / episode_date_str
    if not ep_dir.is_dir():
        return None
    matches = list(ep_dir.glob(f"*_{workflow_id}.mp3"))
    return matches[0] if matches else None


def _check_filename_safe(filename: str) -> None:
    """校验文件名防路径穿越。

    拒绝包含 .. 或路径分隔符的输入，避免攻击者通过构造 filename
    访问 tts 目录之外的任意文件。
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise BizError(code=400, message="非法文件名")


def _rel_path(path: Path) -> str:
    """转成相对 audio_cache 的正斜杠路径，便于跨平台展示与日志。"""
    return str(path.relative_to(_AUDIO_ROOT)).replace("\\", "/")


@router.get("/{workflow_id}/audio")
async def list_audio(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """列出该工作流的音频文件。

    返回 TTS 片段目录与成品音频的存在状态。
    成品路径需要通过 workflow.episode_date 派生，工作流不存在时 episode_file 为 null。

    打包态兼容：COS 已配置时本地 audio_cache 为空，回退到 DB 持久化的 audio_url
    （Script 分段 / Episode / Review），使详情页在打包态也能展示 TTS 片段与成品。
    """
    # 1) 本地 TTS 目录（开发态 / COS 未配置时的主路径）
    tts_dir = _tts_dir(workflow_id)
    tts_files = []
    if tts_dir.exists():
        # 排序保证前端展示稳定；只收 .mp3 避免误把临时文件暴露
        for f in sorted(tts_dir.iterdir(), key=lambda p: p.name):
            if f.is_file() and f.suffix == ".mp3":
                tts_files.append({
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                    "url": f"/admin/api/v1/workflows/{workflow_id}/audio/tts/{f.name}",
                    "remote": False,
                })

    # 2) 本地 TTS 为空（COS 已配置/打包态）：回退到稿件分段持久化的 audio_url
    if not tts_files:
        scr_result = await db.execute(select(Script).where(Script.workflow_id == workflow_id))
        script = scr_result.scalar_one_or_none()
        if script and script.segments:
            for seg in script.segments:
                if not isinstance(seg, dict):
                    continue
                u = seg.get("audio_url")
                if not u:
                    continue
                seq = seg.get("seq", "?")
                tts_files.append({
                    "name": f"seg_{seq}.mp3",
                    # 远端对象不知道真实字节数，置 0（前端展示"大小未知"），
                    # 避免把 duration 秒误当作字节数回填到 size_bytes 字段
                    "size_bytes": 0,
                    "url": u,
                    "remote": bool(urlparse(u).scheme in ("http", "https")),
                })

    # 3) 成品音频：优先本地 glob（命名含频道名+workflow_id）
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    episode_file_info = None
    # episode_date 可能为 None（异常工作流 / Workflow 记录缺失），统一兜底避免 500
    episode_date_str = None
    if wf is not None:
        try:
            episode_date_str = wf.episode_date.strftime("%Y%m%d") if wf.episode_date else None
        except Exception:
            episode_date_str = None
    ep_path = _find_episode_file(episode_date_str, workflow_id) if episode_date_str else None
    if ep_path:
        episode_file_info = {
            "path": _rel_path(ep_path),
            "exists": ep_path.is_file(),
            "remote": False,
            "url": None,
        }
    else:
        # 本地无成品（COS 模式 / Workflow 记录缺失）：回退到 episode / review 持久化的
        # audio_url。回退不依赖 Workflow 是否存在，避免「工作流记录缺失但成品已生成」
        # 时面板空白。
        ep_result = await db.execute(select(Episode).where(Episode.workflow_id == workflow_id))
        ep = ep_result.scalars().first()
        if ep is None:
            rev_result = await db.execute(select(Review).where(Review.workflow_id == workflow_id))
            ep = rev_result.scalars().first()
        if ep and ep.audio_url:
            episode_file_info = {
                # 远端模式下无本地路径，置为可读文案，避免前端渲染出字面 null
                "path": "云端(COS)",
                "exists": True,
                "remote": bool(urlparse(ep.audio_url).scheme in ("http", "https")),
                "url": ep.audio_url,
            }

    return success(data={
        "tts_dir": tts_files,
        "episode_file": episode_file_info,
    })


@router.get("/{workflow_id}/audio/tts/{filename}")
async def stream_tts(
    workflow_id: str,
    filename: str,
    admin: AdminPayload = Depends(get_current_admin),
):
    """流式播放 TTS 片段音频。"""
    _check_filename_safe(filename)
    file_path = _tts_dir(workflow_id) / filename
    if not file_path.is_file():
        raise NotFoundError("音频文件不存在")
    # 不传 filename 参数：默认 Content-Disposition=inline，浏览器直接播放而非下载
    return FileResponse(path=str(file_path), media_type="audio/mpeg")


@router.get("/{workflow_id}/audio/episode")
async def stream_episode(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """流式播放成品音频。

    按 workflow_id 后缀匹配成品文件（命名含频道名+workflow_id）。
    """
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundError("工作流不存在")

    episode_date_str = wf.episode_date.strftime("%Y%m%d")
    ep_path = _find_episode_file(episode_date_str, workflow_id)
    if not ep_path or not ep_path.is_file():
        raise NotFoundError("成品音频尚未生成")

    return FileResponse(path=str(ep_path), media_type="audio/mpeg")


@router.get("/{workflow_id}/audio/proxy")
async def proxy_audio(
    workflow_id: str,
    url: str = Query(..., description="远端音频地址（COS / CDN），仅允许项目配置的 COS 域名"),
    admin: AdminPayload = Depends(get_current_admin),
):
    """代理播放远端（COS / CDN）音频，避免浏览器直连 COS 的 CORS / 鉴权问题。

    打包态（COS 已配置）下 TTS 片段与成品仅存于云端，本地 audio_cache 为空，
    前端无法用 /audio/tts/{filename} 直读，故通过此后端代理拉取 COS 对象并以
    blob 形式回传。SSRF 防护：仅放行项目配置的 COS 存储桶域名与 CDN 域名。
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BizError(code=400, message="非法音频地址")

    # 仅允许项目配置的 COS 域名，防止被当作通用代理发起 SSRF
    allowed_hosts = set()
    if settings.COS_BUCKET and settings.COS_REGION:
        allowed_hosts.add(f"{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com")
    if settings.COS_CDN_DOMAIN:
        cdn_netloc = urlparse(settings.COS_CDN_DOMAIN).netloc
        if cdn_netloc:
            allowed_hosts.add(cdn_netloc)
    if parsed.netloc not in allowed_hosts:
        raise BizError(code=400, message="非法音频地址")

    key = parsed.path.lstrip("/")
    if not key:
        raise BizError(code=400, message="非法音频地址")

    # 复用 TTS uploader 的 COS 客户端（携带项目凭证，支持私有桶）
    from app.workflow.tts.uploader import _get_client

    async def _stream_cos(stream):
        # COS SDK 为同步库，分块读取必须在 asyncio.to_thread 内进行，避免阻塞事件循环
        while True:
            chunk = await asyncio.to_thread(stream.read, 1024 * 1024)
            if not chunk:
                break
            yield chunk

    try:
        client = _get_client()
        # get_object 仅建立流式请求；若对象不存在 / 无权访问，此处即抛错并映射为 404，
        # 避免在已发送 200 响应头后再断流导致客户端收到截断的损坏音频
        resp = await asyncio.to_thread(
            client.get_object, Bucket=settings.COS_BUCKET, Key=key
        )
        stream = resp["Body"].get_raw_stream()
    except Exception as e:  # NOSONAR 统一兜底为 404，避免泄露内部错误
        logger.warning("音频代理失败 workflow_id=%s key=%s", workflow_id, key, exc_info=True)
        raise NotFoundError("音频获取失败")

    # 分块流式返回，避免 10MB+ 成品一次性读入内存拉高并发内存峰值
    return StreamingResponse(_stream_cos(stream), media_type="audio/mpeg")


@router.delete("/{workflow_id}/audio/tts/{filename}")
async def delete_tts(
    workflow_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除单个 TTS 片段音频（仅管理员）。"""
    _check_filename_safe(filename)
    file_path = _tts_dir(workflow_id) / filename
    if not file_path.is_file():
        raise NotFoundError("音频文件不存在")

    file_path.unlink()
    # 审计日志：TTS 片段删除影响工作流音频拼接，记录操作人与文件路径便于追溯
    db.add(AuditLog(
        category="audio",
        action="delete_tts",
        target=f"{workflow_id}/{filename}",
        operator=admin.username,
        detail=json.dumps({"workflow_id": workflow_id, "filename": filename}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"deleted": filename})


@router.delete("/{workflow_id}/audio/episode")
async def delete_episode(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除成品音频文件（仅管理员）。

    按 workflow_id 后缀匹配成品文件路径。
    """
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundError("工作流不存在")

    episode_date_str = wf.episode_date.strftime("%Y%m%d")
    ep_path = _find_episode_file(episode_date_str, workflow_id)
    if not ep_path or not ep_path.is_file():
        raise NotFoundError("成品音频尚未生成")

    ep_path.unlink()
    # 审计日志：成品音频删除影响节目播放，记录操作人与文件路径便于追溯
    db.add(AuditLog(
        category="audio",
        action="delete_episode",
        target=str(ep_path),
        operator=admin.username,
        detail=json.dumps({"workflow_id": workflow_id, "path": str(ep_path)}, ensure_ascii=False),
    ))
    await db.commit()
    return success(data={"deleted": _rel_path(ep_path)})
