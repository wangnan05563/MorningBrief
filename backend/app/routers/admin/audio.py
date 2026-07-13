"""B 端音频文件管理路由。

提供工作流产物中音频文件的列表、流式播放与删除能力：
- TTS 片段：data/audio_cache/tts/{workflow_id}/*.mp3
- 拼接成品：data/audio_cache/episodes/{episode_date_str}/final.mp3

所有路径均通过 resolve_data_dir() 派生，避免硬编码。
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin, require_admin
from app.core.exceptions import BizError, NotFoundError
from app.core.response import success
from app.database import get_db
from app.models import Workflow
from app.paths import resolve_data_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/workflows", tags=["B端-音频管理"])

# 模块级常量：与 main.py 中 StaticFiles 挂载点保持一致，避免重复构造
_AUDIO_ROOT = resolve_data_dir() / "audio_cache"


def _tts_dir(workflow_id: str) -> Path:
    """工作流对应的 TTS 片段目录。"""
    return _AUDIO_ROOT / "tts" / workflow_id


def _episode_file(episode_date_str: str) -> Path:
    """节目日期对应的成品音频路径。"""
    return _AUDIO_ROOT / "episodes" / episode_date_str / "final.mp3"


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
    """
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
                })

    # 成品音频需要 episode_date 派生路径
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    episode_file_info = None
    if wf is not None:
        episode_date_str = wf.episode_date.strftime("%Y%m%d")
        ep_path = _episode_file(episode_date_str)
        episode_file_info = {
            "path": _rel_path(ep_path),
            "exists": ep_path.exists(),
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

    根据 workflow.episode_date 定位 final.mp3 路径。
    """
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundError("工作流不存在")

    episode_date_str = wf.episode_date.strftime("%Y%m%d")
    ep_path = _episode_file(episode_date_str)
    if not ep_path.is_file():
        raise NotFoundError("成品音频尚未生成")

    return FileResponse(path=str(ep_path), media_type="audio/mpeg")


@router.delete("/{workflow_id}/audio/tts/{filename}")
async def delete_tts(
    workflow_id: str,
    filename: str,
    admin: AdminPayload = Depends(require_admin),
):
    """删除单个 TTS 片段音频（仅管理员）。"""
    _check_filename_safe(filename)
    file_path = _tts_dir(workflow_id) / filename
    if not file_path.is_file():
        raise NotFoundError("音频文件不存在")

    file_path.unlink()
    return success(data={"deleted": filename})


@router.delete("/{workflow_id}/audio/episode")
async def delete_episode(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除成品音频文件（仅管理员）。

    需要查 workflow.episode_date 确定文件路径。
    """
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = result.scalar_one_or_none()
    if wf is None:
        raise NotFoundError("工作流不存在")

    episode_date_str = wf.episode_date.strftime("%Y%m%d")
    ep_path = _episode_file(episode_date_str)
    if not ep_path.is_file():
        raise NotFoundError("成品音频尚未生成")

    ep_path.unlink()
    return success(data={"deleted": _rel_path(ep_path)})
