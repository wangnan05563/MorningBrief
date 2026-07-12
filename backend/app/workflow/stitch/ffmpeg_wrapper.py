"""FFmpeg 命令封装:音频拼接所需的底层命令构造与执行。

统一输出格式:libmp3lame 128k 44100Hz 单声道,保证整期节目音频参数一致,
避免拼接后参数不一致导致的播放器重采样卡顿。
"""
import asyncio
import logging
import subprocess
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# FFmpeg 单次执行上限:超过 120s 大概率卡死,及时失败便于排查
FFMPEG_TIMEOUT_SEC = 120


class StitchError(Exception):
    """音频拼接流程异常(FFmpeg 失败、时长越界等)。"""


async def run_ffmpeg(cmd: list[str]) -> None:
    """执行 FFmpeg 命令,失败时抛 StitchError 含 stderr 末尾。

    用 asyncio.create_subprocess_exec 异步执行,不阻塞事件循环;
    超时强制 kill 子进程,避免僵尸进程持续占用 CPU。
    """
    logger.info("执行 FFmpeg: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=FFMPEG_TIMEOUT_SEC
        )
    except asyncio.TimeoutError:
        # 超时后必须 kill 并回收,否则子进程继续占用资源
        proc.kill()
        await proc.wait()
        raise StitchError(
            f"FFmpeg 执行超时({FFMPEG_TIMEOUT_SEC}s): {' '.join(cmd)}"
        )

    if proc.returncode != 0:
        # 仅保留 stderr 末尾 500 字符:FFmpeg 错误信息尾部最有诊断价值
        err_tail = stderr.decode("utf-8", errors="replace")[-500:]
        raise StitchError(
            f"FFmpeg 执行失败(returncode={proc.returncode}): {err_tail}"
        )


async def get_audio_duration(file_path: str) -> int:
    """用 ffprobe 探测音频时长(秒),返回整数。

    ffprobe 是同步阻塞调用,用 asyncio.to_thread 包装避免阻塞事件循环。
    """
    def _probe() -> int:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise StitchError(f"ffprobe 探测失败: {result.stderr[-500:]}")
        return int(float(result.stdout.strip()))

    return await asyncio.to_thread(_probe)


async def download_file(url: str, dest_path: str) -> None:
    """下载文件到本地，支持 HTTP URL 和本地 /audio/ 静态端点。

    COS 未配置时 TTS 上传降级到本地 /audio/ 路径，stitch 拼接阶段下载
    此类 URL 时走本地文件复制，避免 httpx 无法访问相对路径。
    """
    # 本地 /audio/ 端点：直接复制文件（COS 未配置时的回退路径）
    if url.startswith("/audio/"):
        import shutil
        from app.paths import resolve_data_dir
        try:
            audio_root = Path(resolve_data_dir()) / "audio_cache"
        except Exception:
            audio_root = Path("data/audio_cache")
        src = audio_root / url[len("/audio/"):]
        logger.info("复制本地音频: %s -> %s", src, dest_path)
        shutil.copyfile(str(src), dest_path)
        return

    logger.info("下载文件: %s -> %s", url, dest_path)
    async with httpx.AsyncClient(timeout=60) as client:
        with open(dest_path, "wb") as f:  # NOSONAR
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)


def build_concat_cmd(input_paths: list[str], output_path: str) -> list[str]:
    """构造分段拼接命令(concat demuxer)。

    concat demuxer 要求一个 list.txt 清单文件,本函数内部生成辅助文件
    {output_path}.list.txt(与输出同目录,便于临时目录统一清理)。
    demuxer 方式不需要将所有段解码到内存,适合分段数较多的主音频拼接。
    """
    list_path = f"{output_path}.list.txt"
    # 清单格式:每行 "file '路径'";路径含单引号需用 '\'' 转义
    lines = []
    for p in input_paths:
        escaped = p.replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    Path(list_path).write_text("\n".join(lines), encoding="utf-8")

    return [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c:a", "libmp3lame", "-b:a", "128k",
        "-ar", "44100", "-ac", "1",
        output_path,
    ]


def build_mid_ad_cmd(
    main_path: str, ad_path: str, output_path: str, insert_at: int = 300
) -> list[str]:
    """构造中间广告插入命令。

    用 atrim 将主音频切分为前后两段,与广告三段 concat。
    asetpts 重置时间戳,避免 concat 后时间戳错乱导致播放异常。
    """
    return [
        "ffmpeg", "-y",
        "-i", main_path,
        "-i", ad_path,
        "-filter_complex",
        f"[0:a]atrim=0:{insert_at},asetpts=N/SR/TB[a1];"
        f"[0:a]atrim={insert_at},asetpts=N/SR/TB[a2];"
        "[a1][1:a][a2]concat=n=3:v=0:a=1[out]",
        "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "128k",
        "-ar", "44100", "-ac", "1",
        output_path,
    ]


def build_full_concat_cmd(inputs: list[str], output_path: str) -> list[str]:
    """构造多段拼接命令(filter_complex concat)。

    用于开头/结尾广告与主音频的最终拼接,输入顺序由调用方决定。
    用 filter_complex concat 一次性合并,避免多次重编码累积质量损失。
    """
    n = len(inputs)
    input_args: list[str] = []
    for p in inputs:
        input_args.extend(["-i", p])
    # 拼接 [0:a][1:a]...[n-1:a]concat=n=N:v=0:a=1[out]
    labels = "".join(f"[{i}:a]" for i in range(n))
    return [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex",
        f"{labels}concat=n={n}:v=0:a=1[out]",
        "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "128k",
        "-ar", "44100", "-ac", "1",
        output_path,
    ]


async def generate_silence(duration_sec: float, output_path: str) -> None:
    """生成指定时长的静音 mp3 文件。

    用 lavfi anullsrc 生成静音 PCM 再编码为 mp3,
    作为广告与主音频之间的过渡,避免突兀切换影响收听体验。
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration_sec),
        "-c:a", "libmp3lame", "-b:a", "128k",
        "-ar", "44100", "-ac", "1",
        output_path,
    ]
    await run_ffmpeg(cmd)
