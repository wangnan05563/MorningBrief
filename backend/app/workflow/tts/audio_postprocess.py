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
from app.core.audio_profile import resolve_encoding
from app.paths import resolve_ffmpeg_path, resolve_ffprobe_path

logger = logging.getLogger(__name__)


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


async def postprocess_segment(
    audio_bytes: bytes, target_lufs: int = -16, threshold_db: int = -50
) -> bytes:
    """分段后处理：响度归一化 + 去首尾静音，**整段只做一次有损编码**。

    原来 normalize_loudness / trim_silence 分两次 FFmpeg 调用，每次都解码再
    重编 mp3——同一个分段在 TTS 阶段就落下 2 代有损编码（叠加 provider 自身的
    1 代与 stitch 的若干代）。T01845 实测每多一代 64k 重编 segSNR 掉约 1.5dB，
    而体积毫无收益。两个滤镜本身可以串在同一条 -af 链上，因此合并为一次调用。

    滤镜顺序保持「先 loudnorm 后 silenceremove」，与拆分实现一致：
    先去静音会让 loudnorm 的响度统计漏掉被切掉的段落，导致整体音量偏高。

    threshold_db 为负数 dB，去除低于该阈值的静音段，避免拼接处出现明显停顿。
    start_periods=1 去除首部静音；stop_periods=-1 去除尾部所有静音。

    采样率取档位而不是 provider 的 ALIYUN_TTS_SAMPLE_RATE：T01845 实测成品内容上限
    约 10kHz，把 24kHz 的 TTS 源上采样到 44.1k 只是把体积花在空频带上，还会让
    stitch 侧的 PCM 中间态按 88KB/s 涨；这里一次降到档位采样率即可。
    """
    enc = resolve_encoding(get_settings())
    in_path = _write_temp(audio_bytes, ".mp3")
    out_path = in_path.replace(".mp3", "_pp.mp3")
    cmd = [
        resolve_ffmpeg_path(), "-y", "-i", in_path,
        "-af",
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11,"
        f"silenceremove=start_periods=1:start_threshold={threshold_db}dB:"
        f"stop_periods=-1:stop_threshold={threshold_db}dB:stop_duration=0.3",
        "-ar", str(enc.sample_rate),
        "-ac", "1",
        "-b:a", enc.bitrate,
        out_path,
    ]
    try:
        code, _, err = await asyncio.to_thread(_run_cmd, cmd)
        if code != 0:
            raise RuntimeError(f"分段后处理失败: {err[:300]}")
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
