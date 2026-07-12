"""FFmpeg 依赖检测与一键安装服务。

工作流 TTS 步骤依赖 ffmpeg/ffprobe 做音频后处理（响度归一化、去静音、时长探测），
本服务提供：
- check_ffmpeg(): 检测系统/bundled ffmpeg 可用性
- download_and_install_ffmpeg(): 从 BtbN/FFmpeg-Builds 下载共享构建并提取到 ./ffmpeg/bin/

下载源选用 gpl-shared 共享构建：免编译、体积小、与 V1.2 bundled 部署设计一致。
"""
import asyncio
import logging
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import httpx

from app.paths import get_app_root, resolve_ffmpeg_path, resolve_ffprobe_path

logger = logging.getLogger(__name__)

# BtbN/FFmpeg-Builds 共享构建（gpl-shared）：含 ffmpeg.exe/ffprobe.exe + DLL，免编译
# win64 共享构建体积约 30MB，适合项目 bundled 部署
FFMPEG_DOWNLOAD_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl-shared.zip"
)
# 下载超时（秒）：GitHub release 经 CDN 分发，通常较快但需容错大文件场景
DOWNLOAD_TIMEOUT_SEC = 300
# subprocess 检测超时（秒）：未安装时 Windows 报错很快，已安装时 -version 秒回
CHECK_TIMEOUT_SEC = 10


def _get_bundled_bin_dir() -> Path:
    """bundled ffmpeg 二进制目录：./ffmpeg/bin/（与 paths.resolve_ffmpeg_path 一致）。"""
    return get_app_root() / "ffmpeg" / "bin"


def check_ffmpeg() -> dict:
    """检测 ffmpeg/ffprobe 可用性。

    通过 resolve_ffmpeg_path()/resolve_ffprobe_path() 获取路径（bundled 优先，回退 PATH），
    执行 `ffmpeg -version` / `ffprobe -version` 验证可执行性。

    Returns:
        {
            "available": bool,        # True 要求 ffmpeg 和 ffprobe 均可执行
            "ffmpeg_path": str,
            "ffprobe_path": str,
            "version": str,           # ffmpeg 版本号（如 "7.0"）
            "error": str,             # 不可用时的原因，可用时为空串
        }
    """
    ffmpeg_path = resolve_ffmpeg_path()
    ffprobe_path = resolve_ffprobe_path()

    # 先检测 ffmpeg（未安装时抛 FileNotFoundError，即 WinError 2 场景）
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True, text=True,
            timeout=CHECK_TIMEOUT_SEC, check=False,
        )
        if result.returncode != 0:
            return {
                "available": False,
                "ffmpeg_path": ffmpeg_path,
                "ffprobe_path": ffprobe_path,
                "version": "",
                "error": f"ffmpeg 返回码 {result.returncode}: {result.stderr[:200]}",
            }
        # stdout 第一行形如 "ffmpeg version 7.0-essentials ..."，提取版本号
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        version = first_line.replace("ffmpeg version", "").strip().split(" ")[0]
    except FileNotFoundError:
        return {
            "available": False,
            "ffmpeg_path": ffmpeg_path,
            "ffprobe_path": ffprobe_path,
            "version": "",
            "error": "ffmpeg 未安装（系统 PATH 和 bundled 目录均未找到）",
        }
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "ffmpeg_path": ffmpeg_path,
            "ffprobe_path": ffprobe_path,
            "version": "",
            "error": f"ffmpeg 检测超时（{CHECK_TIMEOUT_SEC}s）",
        }

    # 再检测 ffprobe（available 要求两者都可用）
    try:
        result = subprocess.run(
            [ffprobe_path, "-version"],
            capture_output=True, text=True,
            timeout=CHECK_TIMEOUT_SEC, check=False,
        )
        if result.returncode != 0:
            return {
                "available": False,
                "ffmpeg_path": ffmpeg_path,
                "ffprobe_path": ffprobe_path,
                "version": version,
                "error": f"ffprobe 返回码 {result.returncode}",
            }
    except FileNotFoundError:
        return {
            "available": False,
            "ffmpeg_path": ffmpeg_path,
            "ffprobe_path": ffprobe_path,
            "version": version,
            "error": "ffprobe 未安装",
        }
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "ffmpeg_path": ffmpeg_path,
            "ffprobe_path": ffprobe_path,
            "version": version,
            "error": f"ffprobe 检测超时（{CHECK_TIMEOUT_SEC}s）",
        }

    return {
        "available": True,
        "ffmpeg_path": ffmpeg_path,
        "ffprobe_path": ffprobe_path,
        "version": version,
        "error": "",
    }


def _extract_binaries(zip_path: str) -> None:
    """提取 BtbN shared build 的完整 bin 目录。

    shared build 的两个 exe 依赖同目录 DLL。通过 ffmpeg.exe 定位动态顶层目录，
    然后仅提取 bin 的直接子文件，保留依赖且避免 zip 路径穿越。
    """
    bin_dir = _get_bundled_bin_dir()

    with zipfile.ZipFile(zip_path) as zf:
        ffmpeg_member = None
        for name in zf.namelist():
            lower = name.lower().replace("\\", "/")
            if lower.endswith("bin/ffmpeg.exe"):
                ffmpeg_member = name
                break

        if not ffmpeg_member:
            raise RuntimeError("zip 中未找到 bin/ffmpeg.exe，可能下载源结构变更")

        normalized_ffmpeg = ffmpeg_member.replace("\\", "/")
        bin_prefix = normalized_ffmpeg[: -len("ffmpeg.exe")]
        members: list[tuple[str, str]] = []
        for name in zf.namelist():
            normalized = name.replace("\\", "/")
            if not normalized.lower().startswith(bin_prefix.lower()):
                continue
            relative_name = normalized[len(bin_prefix):]
            if relative_name and "/" not in relative_name and not name.endswith("/"):
                members.append((name, relative_name))

        if not any(relative.lower() == "ffprobe.exe" for _, relative in members):
            raise RuntimeError("zip 中未找到 bin/ffprobe.exe，可能下载源结构变更")

        # 清除残缺或不同版本的旧文件，避免 exe 与 DLL 版本混用。
        if bin_dir.exists():
            shutil.rmtree(bin_dir)
        bin_dir.mkdir(parents=True, exist_ok=True)

        for member, relative_name in members:
            with zf.open(member) as src, open(bin_dir / relative_name, "wb") as dst:
                shutil.copyfileobj(src, dst)


async def download_and_install_ffmpeg() -> dict:
    """下载并安装 ffmpeg/ffprobe 到 ./ffmpeg/bin/。

    流程：httpx.AsyncClient 流式下载 zip → asyncio.to_thread 解压提取 → 重新检测。
    下载/解压为耗时操作，解压用 to_thread 包装避免阻塞事件循环。
    安装完成后返回 check_ffmpeg() 结果（含 install_message 字段）。

    Returns:
        check_ffmpeg() 结果 + {"install_message": str}
    """
    bin_dir = _get_bundled_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)

    logger.info("开始下载 ffmpeg: %s", FFMPEG_DOWNLOAD_URL)

    # 流式下载到临时文件：follow_redirects 处理 GitHub release 的 302 跳转
    # delete=False + 先 close 再写入：Windows 下文件占用约束
    tmp_zip = tempfile.NamedTemporaryFile(  # NOSONAR
        delete=False, suffix=".zip", prefix="ffmpeg_dl_"
    )
    tmp_zip.close()
    try:
        total = 0
        async with httpx.AsyncClient(
            timeout=DOWNLOAD_TIMEOUT_SEC, follow_redirects=True
        ) as client:
            async with client.stream("GET", FFMPEG_DOWNLOAD_URL) as resp:
                resp.raise_for_status()
                with open(tmp_zip.name, "wb") as f:  # NOSONAR
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
                        total += len(chunk)
                        # 每 5MB 记录一次进度，便于排查下载卡死
                        if total % (5 * 1024 * 1024) < len(chunk):
                            logger.info("ffmpeg 下载进度: %.1f MB", total / 1048576)
        logger.info("ffmpeg 下载完成: %.1f MB", total / 1048576)

        # 解压提取为同步阻塞 IO，用 to_thread 包装避免阻塞事件循环
        await asyncio.to_thread(_extract_binaries, tmp_zip.name)
        logger.info("ffmpeg/ffprobe 已提取到 %s", bin_dir)

        # 重新检测（subprocess 阻塞，同样用 to_thread 包装）
        check_result = await asyncio.to_thread(check_ffmpeg)
        check_result["install_message"] = (
            "安装成功" if check_result["available"] else "安装完成但检测失败，请检查日志"
        )
        return check_result
    finally:
        # 无论成功失败都清理临时 zip 文件
        try:
            Path(tmp_zip.name).unlink()
        except OSError:
            pass
