"""FFmpeg 命令封装:音频拼接所需的底层命令构造与执行。

编码口径（T01870）：**拼接链路中间态一律 16bit PCM WAV，只有最终交付物做有损编码。**
此前 loudnorm→silenceremove→concat→amix→广告插入→final 每步都重编一次 MP3，
同一段语音最多被有损编码 4~5 代；T01845 实测同码率下 1 代→4 代 segSNR 掉 4.6dB
（9-12kHz 频带丢 2.23dB），而体积一个字节没省。改成中间态无损后，整期只编一次。

- 中间态参数：`pcm_s16le` + 档位采样率 + 单声道（`_pcm_args()`）；
- 成品编码：`libmp3lame` + 档位码率（`_encode_args()`），只在 concat.py 的最终输出调用一次；
- HLS：从中间态 PCM 直接编 AAC，避免「MP3→AAC」二次有损转换。

采样率与码率都取自档位套餐 `app/core/audio_profile.py`（T01871），本文件不再写死数值。
统一采样率的目的是让 concat demuxer 混合多段时参数一致，避免播放器侧重采样卡顿。
"""
import asyncio
import logging
import subprocess
from pathlib import Path

import httpx

from app.config import get_settings
from app.core.audio_profile import resolve_encoding
from app.paths import resolve_ffmpeg_path, resolve_ffprobe_path

logger = logging.getLogger(__name__)

# FFmpeg 单次执行上限:超过 120s 大概率卡死,及时失败便于排查
FFMPEG_TIMEOUT_SEC = 120

# filter_complex 输出标签,3 处 -map 复用,提为常量避免字面量重复触发 S1192
_FFMPEG_OUT_LABEL = "[out]"


def _audio_bitrate() -> str:
    """当前档位生效的成品码率。"""
    return resolve_encoding(get_settings()).bitrate


def _stitch_sample_rate() -> str:
    """拼接链路统一采样率（字符串形态，直接进 ffmpeg 参数）。

    必须走档位套餐而不是写死 44100：中间态 PCM 的落盘体积与「编码器把预算花在哪」
    都由它决定，32k 档比 44.1k 省 26% 临时盘，且同码率下 segSNR 更高（T01845）。
    """
    return str(resolve_encoding(get_settings()).sample_rate)


def _pcm_args() -> list[str]:
    """中间态输出参数：无损 PCM。

    中间步骤（拼接/混音/插广告/变速/补足）不做任何有损编码，避免代际累积损失；
    PCM 也顺带消除了「ffmpeg 对 mp3 输出默认 128k」这类隐式参数问题。
    """
    return ["-c:a", "pcm_s16le", "-ar", _stitch_sample_rate(), "-ac", "1"]


def _encode_args() -> list[str]:
    """成品编码参数：仅在最终交付物上调用一次。"""
    return ["-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
            "-ar", _stitch_sample_rate(), "-ac", "1"]


async def to_pcm(input_path: str, output_path: str) -> None:
    """把任意输入（MP3 分段/广告素材/BGM）解到统一 PCM 参数，供后续无损中间态使用。

    「解码不是又一次有损」：MP3→PCM 只丢编码噪声底，不再引入量化损失，
    因此入口处统一转一次，比每一步各自带着不同采样率/声道重编更稳。
    """
    await run_ffmpeg(
        [resolve_ffmpeg_path(), "-y", "-i", input_path, *_pcm_args(), output_path]
    )


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


async def get_audio_duration_f(file_path: str) -> float:
    """用 ffprobe 探测音频时长,返回浮点秒(精确值)。

    为什么需要浮点版本:BGM 叠加轨按分段时长切片,若用整数秒(取整)会与
    主音频的实际分段时长产生每段最多 1s 的偏差,且逐段累积——叠加轨相对
    主音频漂移,表现为段边界(音色切换点)处 BGM 空白后突然跳回。
    BGM 切片必须用与主音频一致的精确时长。

    ffprobe 是同步阻塞调用,用 asyncio.to_thread 包装避免阻塞事件循环。
    """
    def _probe() -> float:
        cmd = [
            resolve_ffprobe_path(), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise StitchError(f"ffprobe 探测失败: {result.stderr[-500:]}")
        return float(result.stdout.strip())

    return await asyncio.to_thread(_probe)


async def get_audio_duration(file_path: str) -> int:
    """用 ffprobe 探测音频时长(秒),返回整数。

    供时长校验/循环长度等"整秒足够"的场景使用;
    BGM 分段切片对齐必须用 get_audio_duration_f(浮点)。
    """
    return int(await get_audio_duration_f(file_path))


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
        *_pcm_args(),
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
        *_pcm_args(),
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
        *_pcm_args(),
        output_path,
    ]


def build_crossfade_cmd(
    input_paths: list[str],
    crossfade_sec: float,
    output_path: str,
) -> list[str]:
    """构造分段「交叉淡化」拼接命令（消除段间空档，双人播报切换丝滑）。

    与 build_concat_cmd 的本质区别：
    - concat demuxer 是首尾硬接，段间必须插入静音 gap 才能避免爆音，听感上就是
      「播报人切换处有短暂空档」——双人（交叉音色）播报时尤其明显；
    - acrossfade 让相邻两段在 crossfade_sec 内重叠并交叉淡化，段间不存在静音空档，
      且两个不同音色不会硬切产生「啪」的断裂声。

    实现要点：
    - N 段需要 N-1 次 acrossfade，链式串接（[0][1]→[a1]，[a1][2]→[a2] …）；
    - 所有输入一次性 -i 传入，只重编码一次，避免多轮转码累积质量损失；
    - 交叉淡化会让相邻段重叠，总时长比朴素相加短 (N-1)×crossfade_sec，
      调用方做时长校验/预估时需按此扣减；
    - 单段（N==1）无需交叉淡化，直接重编码统一音频参数即可。

    Args:
        input_paths: 按播放顺序排列的分段音频路径（至少 1 个）
        crossfade_sec: 交叉淡化时长（秒），必须小于最短分段时长
        output_path: 输出主音频路径

    Raises:
        StitchError: 输入为空
    """
    n = len(input_paths)
    if n == 0:
        raise StitchError("交叉淡化拼接需要至少 1 段输入")
    if n == 1:
        return [
            resolve_ffmpeg_path(), "-y", "-i", input_paths[0],
            *_pcm_args(),
            output_path,
        ]

    input_args: list[str] = []
    for p in input_paths:
        input_args.extend(["-i", p])

    # 链式 acrossfade：prev 为上一级输出标签，最后一级落到 [out]
    # c1/c2=tri 为三角形曲线，交叉点两侧能量和恒定，是语音衔接最稳的选择
    d = max(0.01, float(crossfade_sec))
    chain: list[str] = []
    for i in range(1, n):
        prev = "[0:a]" if i == 1 else f"[a{i - 1}]"
        out_label = _FFMPEG_OUT_LABEL if i == n - 1 else f"[a{i}]"
        chain.append(
            f"{prev}[{i}:a]acrossfade=d={d:.3f}:c1=tri:c2=tri{out_label}"
        )

    return [
        resolve_ffmpeg_path(), "-y",
        *input_args,
        "-filter_complex", ";".join(chain),
        "-map", _FFMPEG_OUT_LABEL,
        *_pcm_args(),
        output_path,
    ]


async def generate_silence(duration_sec: float, output_path: str) -> None:
    """生成指定时长的静音 PCM(wav) 文件。

    用 lavfi anullsrc 生成静音信号（T01870 后为无损中间态，随主音频一次编码）。
    作为广告与主音频之间的过渡,避免突兀切换影响收听体验。
    """
    cmd = [
        resolve_ffmpeg_path(), "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r={_stitch_sample_rate()}:cl=mono",
        "-t", str(duration_sec),
        *_pcm_args(),
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

    实现关键（两个实测过的 ffmpeg 坑，都会让 BGM「消失／错位」）：
    1. 先把 BGM 循环成**一条足够长的实体源文件**，再对源做输入侧 seek 切片。
       直接在切片命令里用 `-stream_loop -1` 是不可行的：
       - `-ss` 放 `-i` 前（输入侧）时输出侧 `-t` 被忽略，实测请求 2.5s 产出 4.496s，
         切片逐段变长，叠加轨与主音频彻底错位；
       - `-ss` 放 `-i` 后（输出侧）时，seek 偏移超出「剩余循环内容」会产出整段静音，
         实测 start=3.0 / 源长 4.0 / dur=2.5 的切片音量 -91dB（BGM 整段消失）。
    2. 循环源长度取 `BGM 长度 + 最长分段 + 1s`：切片偏移已按 BGM 长度取模（< 源长），
       再加最长分段即可保证任意切片都能取满，不会读越过文件尾。

    Args:
        bgm_path: BGM 文件绝对路径
        seg_durations: 各 TTS 分段时长（秒，浮点），用于切片长度与连续偏移。
            必须传主音频实际分段时长（拼接前 ffprobe 实测），而非 TTS 上报的
            整数秒——整数取整会导致切片与主音频逐段错位，段边界（音色切换点）
            处 BGM 空白后跳回。
        gap_path: 段间静音文件（generate_silence 产物），直接复用为叠加轨的静音段
        volume: BGM 音量（0.0-1.0）
        output_path: 叠加轨输出路径
        tmp_dir: 临时目录（切片文件写入此处，随主流程统一清理）
    """
    bgm_len = await get_audio_duration_f(bgm_path)
    parts: list[str] = []
    offset = 0.0
    n = len(seg_durations)
    durs = [float(d) for d in seg_durations]

    # 预循环：生成一条长度足够的 BGM 源，后续所有切片都在它上面做输入侧 seek
    max_dur = max(durs) if durs else 0.0
    needed = (bgm_len if bgm_len > 0 else max_dur) + max_dur + 1.0
    looped_src = str(Path(tmp_dir) / "bgm_looped_src.wav")
    await run_ffmpeg([
        resolve_ffmpeg_path(), "-y",
        "-stream_loop", "-1", "-i", bgm_path,
        "-t", f"{needed:.3f}",
        *_pcm_args(),
        looped_src,
    ])

    for i, dur in enumerate(durs):
        slice_path = str(Path(tmp_dir) / f"bgm_slice_{i}.wav")
        # 连续偏移取模 BGM 长度，保证 BGM 在整期节目里连续推进、循环处不跳变
        start = offset % bgm_len if bgm_len > 0 else 0.0
        # 每个切片加淡入/淡出，避免段边界处 BGM 被硬切产生"啪"的断裂感：
        # - 淡入 0.08s 消除切片起点的爆音
        # - 淡出 0.3s 让 BGM 在段间停顿前自然收束（而非戛然而止）
        fade_in_d = min(0.08, dur / 4)
        fade_out_d = min(0.3, dur / 4)
        fade_out_st = max(0.0, dur - fade_out_d)
        filter_chain = (
            f"volume={volume},"
            f"afade=t=in:st=0:d={fade_in_d:.3f},"
            f"afade=t=out:st={fade_out_st:.3f}:d={fade_out_d:.3f}"
        )
        cmd = [
            resolve_ffmpeg_path(), "-y",
            "-ss", f"{start:.3f}",
            "-i", looped_src,
            "-t", f"{dur:.3f}",
            "-af", filter_chain,
            *_pcm_args(),
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
    bgm_looped = str(Path(tmp_dir) / "bgm_looped.wav")
    # 循环 BGM 到主音频长度（多循环覆盖，amix duration=first 截断到主音频）
    await run_ffmpeg([
        resolve_ffmpeg_path(), "-y", "-stream_loop", "-1", "-i", bgm_path,
        "-t", f"{main_dur:.3f}", "-af", f"volume={volume}",
        *_pcm_args(), bgm_looped,
    ])
    await run_ffmpeg(build_amix_cmd(main_path, bgm_looped, output_path))


def build_amix_cmd(
    main_path: str, overlay_path: str, output_path: str,
) -> list[str]:
    """构造「主音频 + 叠加轨」混音命令。

    抽为公共函数的原因：无 BGM 段间静音模式、BGM 桥接模式、BGM 连续模式
    三处都需要同一套 amix 参数，重复字面量既易写错也触发 S1192。
    duration=first 以主音频长度为准，叠加轨更长时自动截断。
    """
    return [
        resolve_ffmpeg_path(), "-y",
        "-i", main_path, "-i", overlay_path,
        "-filter_complex", "amix=inputs=2:duration=first",
        *_pcm_args(),
        output_path,
    ]


async def build_bgm_continuous(
    bgm_path: str, total_dur: float, volume: float, output_path: str,
) -> None:
    """生成「铺满整期节目」的连续 BGM 叠加轨（段间不中断）。

    与 build_bgm_overlay（按段切片 + 段间插静音）的本质区别：
    - 按段切片会在每个段边界处各自编码并加淡入/淡出，听感上 BGM 在每次播报人切换点
      「断一下再回来」（用户反馈：双人播报切换时 bgm 会中断）；
    - 本函数只生成一条连续 BGM 流（-stream_loop -1 循环铺满目标时长），
      整期节目 BGM 一次不断，配合主音频的段间交叉淡化即为「切换丝滑」。

    只编码一次 BGM，随后交给 amix 与主音频混合，音量由 volume 控制。

    Args:
        bgm_path: BGM 文件绝对路径
        total_dur: 目标时长（秒），应传主音频实际时长
        volume: BGM 音量（0.0-1.0）
        output_path: 叠加轨输出路径
    """
    await run_ffmpeg([
        resolve_ffmpeg_path(), "-y",
        "-stream_loop", "-1",
        "-i", bgm_path,
        "-t", f"{float(total_dur):.3f}",
        "-af", f"volume={volume}",
        *_pcm_args(),
        output_path,
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
        *_pcm_args(),
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
        *_pcm_args(),
        output_path,
    ])
    await run_ffmpeg(cmd)


def build_hls_cmd(input_path: str, output_dir: str) -> tuple[list[str], str]:
    """构造 HLS 分片生成命令（PCM 中间态 → m3u8 + ts 分片）。

    为什么 HLS 用 AAC 而非 MP3：HLS 规范（RFC 8216）要求 ADTS-AAC，
    ffmpeg -f hls 对 mp3 输出兼容性差，部分播放器无法解码。
    AAC 64kbps 与 MP3 64kbps 听感相当，且 HLS 原生支持。

    为什么从 PCM 中间态编而不是从成品 mp3 编（T01870）：mp3→AAC 是第二次有损编码，
    直接从拼接时间线的 PCM 编 AAC，HLS 与 MP3 各只有一次有损编码、互不叠加。

    输出结构：
        output_dir/
        ├── playlist.m3u8      # 主清单（VOD 类型，支持任意 seek）
        └── seg_00000.ts       # 分片文件（按 HLS_SEGMENT_SEC 切分）

    Args:
        input_path: 输入音频路径（T01870 后传拼接时间线的 PCM 中间态）
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
        "-ar", _stitch_sample_rate(), "-ac", "1",
        # HLS 封装参数
        "-f", "hls",
        "-hls_time", str(settings.HLS_SEGMENT_SEC),
        "-hls_playlist_type", settings.HLS_PLAYLIST_TYPE,
        "-hls_segment_filename", seg_pattern,
        "-hls_list_size", "0",  # 0 = 保留所有分片（VOD 必需）
        playlist_path,
    ]
    return cmd, playlist_path
