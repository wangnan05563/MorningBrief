"""FFmpeg 命令封装:音频拼接所需的底层命令构造与执行。

统一输出格式:libmp3lame 44100Hz 单声道,码率由配置决定(默认 64k 语音已足够),
保证整期节目音频参数一致,避免拼接后参数不一致导致的播放器重采样卡顿。
"""
import asyncio
import logging
import subprocess
from pathlib import Path

import httpx

from app.config import get_settings
from app.paths import resolve_ffmpeg_path, resolve_ffprobe_path

logger = logging.getLogger(__name__)

# FFmpeg 单次执行上限:超过 120s 大概率卡死,及时失败便于排查
FFMPEG_TIMEOUT_SEC = 120

# filter_complex 输出标签,3 处 -map 复用,提为常量避免字面量重复触发 S1192
_FFMPEG_OUT_LABEL = "[out]"


def _audio_bitrate() -> str:
    """从配置读取音频码率，便于运营在 .env 调整而无需改代码。"""
    return get_settings().AUDIO_BITRATE


class StitchError(Exception):
    """音频拼接流程异常(FFmpeg 失败、时长越界等)。"""


async def run_ffmpeg(cmd: list[str]) -> None:
    """执行 FFmpeg 命令,失败时抛 StitchError 含 stderr 末尾。

    用 asyncio.create_subprocess_exec 异步执行,不阻塞事件循环;
    超时强制 kill 子进程,避免僵尸进程持续占用 CPU。
    """
    logger.info("执行 FFmpeg: %s", " ".join(cmd))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as exc:
        # 子进程启动阶段可能因环境问题（句柄耗尽/路径异常/事件循环未挂载
        # child watcher 等）直接抛异常，且其 str() 可能为空，导致上层只记录
        # 到空错误、无法定位 stitch 失败根因。这里统一转成带类型与信息的
        # StitchError，保证错误描述永远非空且含真实异常类型。
        raise StitchError(
            f"FFmpeg 启动失败({type(exc).__name__}): {exc} | cmd={' '.join(cmd)}"
        ) from exc
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
            resolve_ffprobe_path(), "-v", "error",
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
        resolve_ffmpeg_path(), "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
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
        resolve_ffmpeg_path(), "-y",
        "-i", main_path,
        "-i", ad_path,
        "-filter_complex",
        f"[0:a]atrim=0:{insert_at},asetpts=N/SR/TB[a1];"
        f"[0:a]atrim={insert_at},asetpts=N/SR/TB[a2];"
        "[a1][1:a][a2]concat=n=3:v=0:a=1[out]",
        "-map", _FFMPEG_OUT_LABEL,
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
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
        resolve_ffmpeg_path(), "-y",
        *input_args,
        "-filter_complex",
        f"{labels}concat=n={n}:v=0:a=1[out]",
        "-map", _FFMPEG_OUT_LABEL,
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
        "-ar", "44100", "-ac", "1",
        output_path,
    ]


async def generate_silence(duration_sec: float, output_path: str) -> None:
    """生成指定时长的静音 mp3 文件。

    用 lavfi anullsrc 生成静音 PCM 再编码为 mp3,
    作为广告与主音频之间的过渡,避免突兀切换影响收听体验。
    """
    cmd = [
        resolve_ffmpeg_path(), "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration_sec),
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
        "-ar", "44100", "-ac", "1",
        output_path,
    ]
    await run_ffmpeg(cmd)


async def build_bgm_overlay(
    bgm_path: str,
    seg_durations: list[float],
    gap_path: str,
    volume: float,
    output_path: str,
    tmp_dir: str,
) -> None:
    """构建与 TTS 分段对齐的 BGM 叠加轨：播报段叠加 BGM，段间静音处为纯静音。

    修复背景：原 mix_bgm 将 BGM 以固定音量均匀铺满整段主音频（含段间静音），
    导致频道"段间静音"设置被 BGM 掩盖——用户听到的是 BGM 桥接而非停顿，
    误以为设置"未生效"。本函数改为按分段切片：
    - 每段播报叠加连续切片后的 BGM（保持 BGM 连续、自然浮现）
    - 段间静音处直接复用 gap_path（纯静音）
    最终叠加轨与主音频 amix，段间即真实停顿，使"段间静音"可被听觉感知。

    Args:
        bgm_path: BGM 文件绝对路径
        seg_durations: 各 TTS 分段时长（秒），用于切片长度与连续偏移
        gap_path: 段间静音文件（generate_silence 产物），直接复用为叠加轨的静音段
        volume: BGM 音量（0.0-1.0）
        output_path: 叠加轨输出路径
        tmp_dir: 临时目录（切片文件写入此处，随主流程统一清理）
    """
    bgm_len = await get_audio_duration(bgm_path)
    parts: list[str] = []
    offset = 0.0
    n = len(seg_durations)
    for i, dur in enumerate(seg_durations):
        dur = float(dur)
        slice_path = str(Path(tmp_dir) / f"bgm_slice_{i}.mp3")
        # 连续偏移取模 BGM 长度，配合 -stream_loop -1 跨循环 seek，保证 BGM 连续不跳变
        start = offset % bgm_len if bgm_len > 0 else 0.0
        cmd = [
            resolve_ffmpeg_path(), "-y",
            "-stream_loop", "-1",
            "-ss", f"{start:.3f}",
            "-i", bgm_path,
            "-t", f"{dur:.3f}",
            "-af", f"volume={volume}",
            "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
            "-ar", "44100", "-ac", "1",
            slice_path,
        ]
        await run_ffmpeg(cmd)
        parts.append(slice_path)
        # 段间插入纯静音（最后一段后无需）
        if i < n - 1:
            parts.append(gap_path)
        offset += dur
    # 拼接 [bgm_slice0][silence][bgm_slice1]... 为叠加轨
    await run_ffmpeg(build_concat_cmd(parts, output_path))


async def build_bgm_bridge(
    main_path: str, bgm_path: str, volume: float, output_path: str, tmp_dir: str,
) -> None:
    """旧版 BGM 桥接：将循环 BGM 以固定音量均匀铺满整段主音频（含段间静音）。

    作为 bgm_gap_mode='bridge' 的可选模式保留：
    段间静音处表现为 BGM 桥接而非停顿，复现"段间静音"被 BGM 掩盖的旧听感。
    """
    main_dur = await get_audio_duration(main_path)
    bgm_looped = str(Path(tmp_dir) / "bgm_looped.mp3")
    # 循环 BGM 到主音频长度（多循环覆盖，amix duration=first 截断到主音频）
    await run_ffmpeg([
        resolve_ffmpeg_path(), "-y", "-stream_loop", "-1", "-i", bgm_path,
        "-t", f"{main_dur:.3f}", "-af", f"volume={volume}",
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
        "-ar", "44100", "-ac", "1", bgm_looped,
    ])
    await run_ffmpeg([
        resolve_ffmpeg_path(), "-y",
        "-i", main_path, "-i", bgm_looped,
        "-filter_complex", "amix=inputs=2:duration=first",
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
        "-ar", "44100", "-ac", "1", output_path,
    ])


async def adjust_tempo(input_path: str, output_path: str, tempo: float) -> None:
    """用 atempo 滤镜调整音频速度（不改变音高）。

    用于 stitch 阶段音频轻微超长时的兜底加速，避免 LLM 字数波动导致直接失败。
    atempo 1.12x 几乎不可察觉，1.2x 开始有轻微失真，安全上限 1.25x。

    Args:
        input_path: 输入音频路径
        output_path: 输出音频路径
        tempo: 速度倍率（0.5-2.0），>1 加速，<1 减速
    """
    cmd = [
        resolve_ffmpeg_path(), "-y", "-i", input_path,
        "-filter:a", f"atempo={tempo}",
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
        "-ar", "44100", "-ac", "1",
        output_path,
    ]
    await run_ffmpeg(cmd)


async def generate_bgm_tail(
    bgm_path: str, duration_sec: float, output_path: str, volume: float = 0.15
) -> None:
    """从 BGM 截取一段尾部补足音频，末尾应用 2s 淡出。

    用于 stitch 时长不足时的 BGM 自然延续兜底：节目末尾衔接 BGM 片段，
    比单纯静音填充更自然，听众感受到的是节目在 BGM 中渐弱结束。

    策略：
    1. 从 BGM 中段截取 duration_sec 秒（避免开头引入识别度高的主旋律）
    2. 应用 volume 滤镜调整音量（与主节目 BGM 一致）
    3. 末尾 afade 2s 淡出，避免突兀结束

    Args:
        bgm_path: BGM 源文件路径
        duration_sec: 截取时长（秒）
        output_path: 输出路径
        volume: 音量（0.0-1.0），与主节目 BGM 音量一致避免跳变
    """
    # 从 BGM 30s 处开始截取（跳过开头主旋律），若 BGM < 30s 则从 0 开始
    bgm_duration = await get_audio_duration(bgm_path)
    start_at = min(30.0, max(0.0, bgm_duration - duration_sec - 2))
    fade_start = max(0.0, duration_sec - 2.0)

    # BGM 时长不足时循环播放以填满所需补足时长（素材稀缺场景 padding 可能很大）
    # -stream_loop -1 无限循环输入，配合 -t 限制输出时长，确保输出恰好为 duration_sec
    needs_loop = duration_sec > bgm_duration
    cmd = [
        resolve_ffmpeg_path(), "-y",
    ]
    if needs_loop:
        cmd.extend(["-stream_loop", "-1"])
    cmd.extend([
        "-ss", str(start_at),
        "-t", str(duration_sec),
        "-i", bgm_path,
        "-filter_complex",
        f"[0:a]volume={volume},afade=t=out:st={fade_start}:d=2.0[out]",
        "-map", _FFMPEG_OUT_LABEL,
        "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
        "-ar", "44100", "-ac", "1",
        output_path,
    ])
    await run_ffmpeg(cmd)


def build_hls_cmd(input_path: str, output_dir: str) -> tuple[list[str], str]:
    """构造 HLS 分片生成命令（mp3 → m3u8 + ts 分片）。

    为什么 HLS 用 AAC 而非 MP3：HLS 规范（RFC 8216）要求 ADTS-AAC，
    ffmpeg -f hls 对 mp3 输出兼容性差，部分播放器无法解码。
    AAC 64kbps 与 MP3 64kbps 听感相当，且 HLS 原生支持。

    输出结构：
        output_dir/
        ├── playlist.m3u8      # 主清单（VOD 类型，支持任意 seek）
        └── seg_00000.ts       # 分片文件（按 HLS_SEGMENT_SEC 切分）

    Args:
        input_path: 输入 mp3 文件路径
        output_dir: 输出目录（函数内自动创建）

    Returns:
        (cmd, playlist_path): FFmpeg 命令列表 + m3u8 文件绝对路径
    """
    settings = get_settings()
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    playlist_path = str(Path(output_dir) / "playlist.m3u8")
    seg_pattern = str(Path(output_dir) / "seg_%05d.ts")

    cmd = [
        resolve_ffmpeg_path(), "-y",
        "-i", input_path,
        # AAC 编码，码率与 mp3 保持一致避免体积膨胀
        "-c:a", "aac", "-b:a", _audio_bitrate(),
        "-ar", "44100", "-ac", "1",
        # HLS 封装参数
        "-f", "hls",
        "-hls_time", str(settings.HLS_SEGMENT_SEC),
        "-hls_playlist_type", settings.HLS_PLAYLIST_TYPE,
        "-hls_segment_filename", seg_pattern,
        "-hls_list_size", "0",  # 0 = 保留所有分片（VOD 必需）
        playlist_path,
    ]
    return cmd, playlist_path
