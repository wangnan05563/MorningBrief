"""FFmpeg 音频后处理（LLD 7.5）。

响度归一化 + 去首尾静音，保证分段拼接后听感一致、无爆音。
所有 subprocess 调用通过 asyncio.to_thread 包装，避免阻塞事件循环。
"""
import asyncio
import logging
import math
import os
import subprocess
import tempfile

from app.config import get_settings
from app.paths import resolve_ffmpeg_path, resolve_ffprobe_path

logger = logging.getLogger(__name__)
settings = get_settings()


def _run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """同步执行命令，返回 (returncode, stdout, stderr)。

    独立函数便于 asyncio.to_thread 包装；不抛异常，由调用方判断返回码。
    """
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return (
        proc.returncode,
        proc.stdout.decode(errors="replace"),
        proc.stderr.decode(errors="replace"),
    )


def _write_temp(data: bytes, suffix: str) -> str:
    """写入临时文件，返回路径。

    Windows 上 NamedTemporaryFile(delete=True) 无法被其他进程打开，
    因此用 delete=False 显式管理生命周期，由调用方 finally 清理。
    """
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, prefix="tts_"
    )
    tmp.write(data)
    tmp.flush()
    tmp.close()
    return tmp.name


def _cleanup(*paths: str) -> None:
    """清理临时文件，容忍文件不存在（避免重复清理报错）。"""
    for p in paths:
        try:
            os.unlink(p)
        except OSError:
            pass


def _read_file(path: str) -> bytes:
    """同步读取文件（由 asyncio.to_thread 调用，避免阻塞事件循环）。"""
    with open(path, "rb") as f:
        return f.read()


async def normalize_loudness(audio_bytes: bytes, target_lufs: int = -16) -> bytes:
    """响度归一化（FFmpeg loudnorm 滤镜）。

    统一各段响度到 target_lufs，避免拼接后段间音量跳变。
    同时统一采样率/声道/码率，为后续拼接做准备。
    """
    in_path = _write_temp(audio_bytes, ".mp3")
    out_path = in_path.replace(".mp3", "_norm.mp3")
    cmd = [
        resolve_ffmpeg_path(), "-y", "-i", in_path,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-ar", str(settings.ALIYUN_TTS_SAMPLE_RATE),
        "-ac", "1",
        "-b:a", "128k",
        out_path,
    ]
    try:
        code, _, err = await asyncio.to_thread(_run_cmd, cmd)
        if code != 0:
            raise RuntimeError(f"loudnorm 失败: {err[:300]}")
        return await asyncio.to_thread(_read_file, out_path)
    finally:
        _cleanup(in_path, out_path)


async def trim_silence(audio_bytes: bytes, threshold_db: int = -50) -> bytes:
    """去首尾静音（FFmpeg silenceremove 滤镜）。

    threshold_db 为负数 dB，去除低于该阈值的静音段，
    避免拼接处出现明显停顿。
    """
    in_path = _write_temp(audio_bytes, ".mp3")
    out_path = in_path.replace(".mp3", "_trim.mp3")
    # start_periods=1 去除首部静音；stop_periods=-1 去除尾部所有静音
    cmd = [
        resolve_ffmpeg_path(), "-y", "-i", in_path,
        "-af",
        f"silenceremove=start_periods=1:start_threshold={threshold_db}dB:"
        f"stop_periods=-1:stop_threshold={threshold_db}dB:stop_duration=0.3",
        out_path,
    ]
    try:
        code, _, err = await asyncio.to_thread(_run_cmd, cmd)
        if code != 0:
            raise RuntimeError(f"silenceremove 失败: {err[:300]}")
        return await asyncio.to_thread(_read_file, out_path)
    finally:
        _cleanup(in_path, out_path)


async def get_audio_duration(audio_bytes: bytes) -> int:
    """返回音频时长（秒），用 ffprobe 探测。

    返回整数秒，向上取整避免拼接时长低估。
    """
    in_path = _write_temp(audio_bytes, ".mp3")
    cmd = [
        resolve_ffprobe_path(), "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        in_path,
    ]
    try:
        code, out, err = await asyncio.to_thread(_run_cmd, cmd)
        if code != 0:
            raise RuntimeError(f"ffprobe 失败: {err[:300]}")
        # ffprobe 返回 "12.345000"，向上取整为 13 秒
        return math.ceil(float(out.strip()))
    finally:
        _cleanup(in_path)
