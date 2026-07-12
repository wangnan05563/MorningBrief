"""B 端系统状态路由：ffmpeg 依赖检测与一键安装。

端点：
- GET  /admin/api/v1/system/ffmpeg-status   检测 ffmpeg/ffprobe 可用性
- POST /admin/api/v1/system/ffmpeg-install  下载安装 ffmpeg/ffprobe 到 ./ffmpeg/bin/

所有端点需 admin 权限，防止未授权用户触发大文件下载占用带宽。
"""
import asyncio
import logging

from fastapi import APIRouter, Depends

from app.core.auth import AdminPayload, require_admin
from app.core.response import success
from app.services.ffmpeg_service import check_ffmpeg, download_and_install_ffmpeg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/v1/system", tags=["系统管理"])


@router.get("/ffmpeg-status")
async def get_ffmpeg_status(
    admin: AdminPayload = Depends(require_admin),
):
    """检测 ffmpeg/ffprobe 可用性。

    subprocess 调用为阻塞操作，用 asyncio.to_thread 包装避免阻塞事件循环。
    """
    data = await asyncio.to_thread(check_ffmpeg)
    return success(data=data)


@router.post("/ffmpeg-install")
async def install_ffmpeg(
    admin: AdminPayload = Depends(require_admin),
):
    """下载并安装 ffmpeg/ffprobe。

    下载为耗时操作（约 30MB + CDN 跳转），前端需设较长超时并显示 loading。
    安装失败时返回 available=False + error，不抛异常以便前端展示可读错误。
    """
    try:
        data = await download_and_install_ffmpeg()
        return success(data=data)
    except Exception as e:
        # 下载/解压失败时返回检测结构，前端据 available=False + error 提示
        logger.error("ffmpeg 安装失败: %s", e, exc_info=True)
        check_result = await asyncio.to_thread(check_ffmpeg)
        check_result["install_message"] = f"安装失败: {e}"
        return success(data=check_result)
