"""应用自升级服务（T00879：桌面端一键下载更新包并安装）。

职责：
- 解析 release 的更新包资产（Setup 安装器 .exe）
- 流式下载到 .updates/<tag>/<name>，实时写进度
- 下载完成后启动安装器，由安装器完成应用替换与重启

为什么用安装器而非自行替换文件：本项目桌面端交付物是 Inno Setup 打包的
MorningBrief-Setup-<version>.exe（用户实际发布形态），安装器自带 UAC 提权、
自升级与版本管理。后端只需下载并拉起它，避免在运行中替换 exe/_internal 的高风险操作。

为什么下载与应用分离为状态机：安装器（尤其海外/CDN 托管）体积可达数百 MB，
POST 同步等待会让浏览器请求超时。进度放进程级状态机，前端轮询展示百分比。
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.config import get_settings as _get_settings
from app.paths import get_app_root, is_frozen

# 更新包资产识别：文件名须含该关键字且以 .exe 结尾，才被认定为安装器更新包
# 排除源码包（源码分发为 tar.gz/tar.zst，天然不满足 .exe 后缀）
_ASSET_INSTALLER_HINT = "morningbrief"
_SETTINGS = _get_settings()
# 下载超时：安装器体积可达数百 MB，读超时是关键窗口，复用 ffmpeg 的下载超时配置
_DOWNLOAD_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=_SETTINGS.FFMPEG_DOWNLOAD_TIMEOUT_SEC,
    write=30.0,
    pool=30.0,
)

# 升级状态机：idle → downloading → staging → (restarting | dev_staged) / error
# percent 语义：0-100 表示确定进度；-1 表示总大小未知（显示为"下载中"）
# 模块级单例：多个请求共享同一份升级进度（与 about.py 的缓存同风格）
_UPGRADE: dict[str, Any] = {
    "state": "idle",
    "tag": None,
    "percent": 0,
    "downloaded_mb": 0.0,
    "message": "",
    "error": "",
}
# 下载/升级异步任务引用：不保留引用会被事件循环垃圾回收，导致下载被中断（R5）
_UPGRADE_TASK: asyncio.Task | None = None


def pick_release_asset(release: dict) -> dict | None:
    """从 release 的 assets 中挑选更新包安装器（.exe）。

    assets 来源可能是 GitHub 原生字段（name/size/browser_download_url），
    也可能是本服务缓存后的字段（name/size_bytes/download_url），故做兜底取值。
    无匹配返回 None，前端据此提示"当前版本未提供一键更新包"。
    """
    for raw in release.get("assets") or []:
        name = str(raw.get("name") or "")
        lower = name.lower()
        if not lower.endswith(".exe") or _ASSET_INSTALLER_HINT not in lower:
            continue
        size = raw.get("size") or raw.get("size_bytes") or 0
        url = raw.get("browser_download_url") or raw.get("download_url") or ""
        return {
            "name": name,
            "size_bytes": int(size or 0),
            "download_url": str(url),
            "type": "installer",
        }
    return None


def get_upgrade_state() -> dict:
    """返回升级进度快照（供 /about/upgrade/status 轮询）。拷贝避免外部篡改。"""
    return dict(_UPGRADE)


def start_upgrade(tag: str, asset: dict) -> dict:
    """触发一次升级。已有升级进行中时直接返回现有进度，避免重复下载。"""
    global _UPGRADE_TASK
    if not asset or not asset.get("download_url"):
        raise ValueError("当前 release 未提供更新包下载地址")
    if _UPGRADE["state"] in ("downloading", "staging", "restarting"):
        return get_upgrade_state()
    _UPGRADE.update(state="idle", error="")
    _UPGRADE_TASK = asyncio.create_task(_run_upgrade(str(tag), asset))
    return get_upgrade_state()


async def _run_upgrade(tag: str, asset: dict) -> None:
    """编排整个升级流程：下载 → 启动安装器（或开发环境下停留在已就绪态）。

    任一环节失败都收敛为 error 状态（不抛到调用方），前端依此展示可重试。
    开发模式（未打包）无真实安装器可执行，只保留下载产物到 dev_staged 供验证。
    """
    app_dir = get_app_root()
    target = app_dir / ".updates" / tag / asset["name"]
    try:
        await _download_release(asset["download_url"], target, tag)
        _UPGRADE.update(
            state="staging", percent=100, message="安装包下载完成，正在启动安装器…",
        )
        if not is_frozen():
            # 开发模式：不真实拉起安装器，保留产物供单测与人工核验
            _UPGRADE.update(
                state="dev_staged",
                message=f"开发模式：已下载到 {target}，未启动安装器",
            )
            return
        _launch_installer(target)
        _UPGRADE.update(
            state="restarting",
            message="安装器已启动，请按向导完成更新（如需管理员权限请确认）",
        )
    except Exception as e:
        logger.error("[upgrade] 升级流程失败, tag=%s: %s", tag, e, exc_info=True)
        _UPGRADE.update(state="error", message="升级失败，请重试", error=str(e))


async def _download_release(url: str, target: Path, tag: str) -> None:
    """流式下载 release 安装器，实时写进度。

    内容总长已知时进度以百分比推进；未知（如分块传输）时 percent=-1，
    前端据此退化为"下载中"提示而不显示错误的百分比。
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    _UPGRADE.update(
        state="downloading", tag=tag, percent=0, downloaded_mb=0.0,
        message="开始下载更新包", error="",
    )
    done = 0
    total: int | None = None
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            if "content-length" in resp.headers:
                try:
                    total = int(resp.headers["content-length"])
                except ValueError:
                    total = None
            with open(target, "wb") as out:  # NOSONAR 需显式落盘，非临时文件
                async for chunk in resp.aiter_bytes():
                    out.write(chunk)
                    done += len(chunk)
                    meg = done / 1048576.0
                    percent = int(done * 100 / total) if total else -1
                    _UPGRADE.update(
                        percent=percent,
                        downloaded_mb=round(meg, 1),
                        message=f"正在下载更新包（{meg:.1f} MB）",
                    )
    _UPGRADE.update(message="下载完成")


def _launch_installer(exe_path: Path) -> None:
    """以脱离控制台方式启动安装器。

    必须脱离进程组/创建独立进程组：若继承父（uvicorn）进程组，
    后端中途退出可能连带终止安装器进程，导致升级中断。
    注意：不带 CREATE_NO_WINDOW，安装器需正常弹出 GUI（含 UAC 提权确认）。
    """
    creationflags = (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
    )
    subprocess.Popen(
        [str(exe_path)], cwd=str(exe_path.parent), creationflags=creationflags
    )


def _reset_upgrade_for_test() -> None:
    """测试专用：重置升级状态与任务引用。生产代码不要调用。

    与 about.py 的 _reset_cache_for_test 同理，避免测试用例间共享模块级
    单例状态（规则 89：模块级单例缓存测试隔离）。
    """
    global _UPGRADE_TASK
    _UPGRADE_TASK = None
    _UPGRADE.update(
        state="idle", tag=None, percent=0, downloaded_mb=0.0, message="", error=""
    )