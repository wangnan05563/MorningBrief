"""音频拼接主入口:分段音频 → 主音频 → 广告插入 → 最终节目音频。

流程(LLD 第 4 步 stitch):
1. 下载 TTS 分段音频,段间插入 0.5s 静音过渡,拼接为主音频
2. (可选)叠加低音量 BGM 垫底;TTS 段间静音处默认真实静音(可由 bgm_gap_mode 切换为 BGM 桥接)
3. 查询当日广告投放,中间位置插入广告
4. 开头/结尾广告与主音频最终拼接,加静音过渡
5. 时长校验(目标时长 ±20%)后上传 COS,key 含频道名+workflow_id 防覆盖
"""
import asyncio
import logging
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Channel
from app.paths import resolve_ffmpeg_path
from app.services.ad_service import AdService
from app.workflow.stitch.ffmpeg_wrapper import (
    StitchError,
    _audio_bitrate,
    adjust_tempo,
    build_concat_cmd,
    build_full_concat_cmd,
    build_hls_cmd,
    build_mid_ad_cmd,
    download_file,
    generate_bgm_tail,
    generate_silence,
    get_audio_duration,
    build_bgm_overlay,
    build_bgm_bridge,
    run_ffmpeg,
)
from app.workflow.tts.uploader import upload_to_cos, upload_hls_directory

logger = logging.getLogger(__name__)
settings = get_settings()

# 时长校验区间按 settings.TARGET_DURATION_SEC 动态计算:
#   允许范围 = [target × 0.80, target × 1.20]
# 即默认 600s → [480, 720]，用户调整 target_sec 后范围自动跟随
# ±20% 容差覆盖 LLM 字数波动(±10% prompt 约束实际可达 ±15-20%)+ TTS 语速波动 + 段间静音累加
# 绝对下限 180s 兜底防止目标时长配置异常导致范围过宽
ABSOLUTE_MIN_DURATION_SEC = 180
# 频道级最短时长默认值（秒）：当频道未配置 min_duration_sec 时由 _get_duration_range 动态计算
# 中间广告插入位置(秒):默认 5 分钟处,避开开场白与首条新闻
# 若目标时长 < 600s，按目标时长的中点插入
MID_AD_INSERT_AT_DEFAULT = 300
# 广告与主音频之间的静音过渡时长(秒)
SILENCE_DURATION = 0.5
# 素材稀缺场景的段数判定阈值：总段数（含 intro/outro）< 5 即视为稀缺
# 对应正文段 < 3（与 rewriter.MIN_VALID_SEGMENTS 对齐）
# 稀缺场景下放宽 padding 上限，允许用 BGM/静音补足全部缺口
SPARSE_SEGMENT_THRESHOLD = 5


def _slugify_channel_name(name: str | None) -> str:
    """将频道名转换为 URL/COS key 友好的 slug。

    中文频道名保留原样（COS key 支持 UTF-8），仅清理路径分隔符和特殊字符。
    空名或 None 返回 "default"，保证 key 始终有可读的频道标识段。
    """
    if not name or not name.strip():
        return "default"
    # 清理 COS key 不允许的字符：/ : * ? " < > | 及控制字符
    cleaned = re.sub(r'[/:\*\?"<>|\x00-\x1f]', '_', name.strip())
    return cleaned[:32] or "default"


async def _resolve_channel_bgm(channel_id: int | None) -> tuple[str, Path | None, float, float, int | None, str]:  # NOSONAR
    """解析频道级配置（BGM + 段间静音 + 最短时长 + 段间 BGM 模式，频道未配置时回退全局 settings）。

    一次查询同时取 name + bgm_path + bgm_volume + segment_gap_sec + bgm_gap_mode，避免多次 DB 往返。

    Returns:
        slug: 频道名 slug（用于 COS key 命名）
        bgm_path: BGM 文件绝对路径，None 表示无可用 BGM
        bgm_volume: BGM 音量（0.0-1.0），频道未配时取全局值
        gap_sec: 段间静音时长（秒），频道未配时取全局值
        bgm_gap_mode: 段间 BGM 模式（"silence"/"bridge"），频道未配时取全局值
    """
    slug = "default"
    bgm_rel = (settings.BGM_PATH or "").strip()
    bgm_volume = float(getattr(settings, "BGM_VOLUME", 0.15) or 0.15)
    # 段间静音时长：优先用全局配置。
    # 注意：必须区分"未配置(None)"与"显式配置为 0"——`or 0.5` 会把合法的 0.0
    # 兜底成 0.5，导致"段间静音=0 无停顿"在全局配置下失效。
    _gap_cfg = getattr(settings, "SEGMENT_GAP_SEC", None)
    gap_sec = 0.5 if _gap_cfg is None else float(_gap_cfg)
    # 段间 BGM 模式：频道级优先，未配置回退全局 settings.BGM_GAP_MODE（默认 silence）
    _gap_mode_cfg = getattr(settings, "BGM_GAP_MODE", "silence")
    gap_mode = "silence" if _gap_mode_cfg is None else str(_gap_mode_cfg)
    if gap_mode not in ("silence", "bridge"):
        gap_mode = "silence"
    # 频道级最短时长：未配置时回退全局 target×0.80，初始化避免 channel_id=None 时 NameError
    channel_min_duration: int | None = None

    if channel_id:
        try:
            async with AsyncSessionLocal() as db:
                ch = await db.get(Channel, channel_id)
                if ch:
                    slug = _slugify_channel_name(ch.name)
                    # 频道级 BGM 优先于全局配置
                    if ch.bgm_path:
                        bgm_rel = ch.bgm_path
                    if ch.bgm_volume is not None:
                        bgm_volume = float(ch.bgm_volume)
                    # 频道级段间静音优先于全局配置
                    if ch.segment_gap_sec is not None:
                        gap_sec = float(ch.segment_gap_sec)
                    # 频道级最短时长优先于全局配置
                    if ch.min_duration_sec is not None:
                        channel_min_duration = int(ch.min_duration_sec)
                    else:
                        channel_min_duration = None
                    # 频道级段间 BGM 模式优先于全局配置
                    if ch.bgm_gap_mode is not None:
                        _ch_mode = str(ch.bgm_gap_mode)
                        gap_mode = _ch_mode if _ch_mode in ("silence", "bridge") else "silence"
        except Exception as e:
            logger.warning("查询频道配置失败 channel_id=%s: %s", channel_id, e)

    # 解析 BGM 路径：频道级为相对 data/bgm/ 的路径，全局可能为绝对路径或相对 cwd
    bgm_path = None
    if bgm_rel:
        # 先尝试作为 data/bgm/ 下的相对路径解析（频道级 BGM）
        from app.paths import resolve_bgm_dir
        bgm_root = resolve_bgm_dir()
        p1 = bgm_root / bgm_rel
        if p1.is_file():
            bgm_path = p1
        else:
            # 回退到作为绝对路径或 cwd 相对路径解析（全局 BGM_PATH）
            p2 = Path(bgm_rel)
            if not p2.is_absolute():
                p2 = Path.cwd() / p2
            if p2.is_file():
                bgm_path = p2
            else:
                logger.warning("BGM 文件不存在，降级为无 BGM 模式: %s", bgm_rel)

    return slug, bgm_path, bgm_volume, gap_sec, channel_min_duration, gap_mode


def _get_duration_range(min_duration_sec: int | None = None) -> tuple[int, int]:
    """按目标时长动态计算允许的时长范围。

    范围 = [max(180, target×0.80), target×1.20]
    与 settings.TARGET_DURATION_SEC 联动，用户调整目标时长后范围自动更新。
    ±20% 容差覆盖 LLM 字数波动 + TTS 语速波动 + 段间静音累加的综合误差。
    
    支持频道级 min_duration_sec 覆盖：配置后下限直接使用频道值，上限保持 target×1.20。
    冷门/小众频道可设置较短时长（如 300s），避免素材稀缺时 padding 补足后仍不足下限。
    """
    target = getattr(settings, "TARGET_DURATION_SEC", 600) or 600
    try:
        target = int(target)
    except (ValueError, TypeError):
        target = 600
    # 频道级最短时长优先
    if min_duration_sec is not None:
        low = max(ABSOLUTE_MIN_DURATION_SEC, int(min_duration_sec))
        high = int(target * 1.20)
        logger.info(
            "使用自定义最短时长: min=%ds target=%ds",
            low, target,
        )
        return low, high
    low = max(ABSOLUTE_MIN_DURATION_SEC, int(target * 0.80))
    high = int(target * 1.20)
    return low, high

def _read_file(path: str) -> bytes:
    """同步读取文件(由 asyncio.to_thread 调用,避免阻塞事件循环)。"""
    with open(path, "rb") as f:
        return f.read()


async def concat(  # NOSONAR
    workflow_id: str,
    episode_date,
    audio_segments: list,
    channel_id: int | None = None,
) -> dict:
    """音频拼接主入口。

    Args:
        workflow_id: 工作流 ID,用于日志关联与临时目录命名 + COS key 防覆盖
        episode_date: 节目日期(date 对象或 ISO 字符串),用于查询广告投放与生成 COS key
        audio_segments: TTS 分段列表 [{"seg_seq": 1, "audio_url": "...", "duration": 90}]
        channel_id: 频道 ID,用于生成频道级 COS key,避免不同频道产物互相覆盖

    Returns:
        {"final_audio_url": str, "duration": int}

    Raises:
        StitchError: 拼接失败或时长越界
    """
    # 兼容 date 对象与 ISO 字符串两种入参,上层调用方可能传任一形式
    if isinstance(episode_date, str):
        episode_date = date.fromisoformat(episode_date)

    logger.info(
        "拼接启动 workflow_id=%s date=%s segments=%d channel_id=%s",
        workflow_id, episode_date, len(audio_segments), channel_id,
    )

    # 临时目录前缀含 workflow_id,便于排查时定位
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"stitch_{workflow_id}_"))
    try:
        # 1. 按 seg_seq 排序,确保分段顺序与稿件一致
        segments = sorted(audio_segments, key=lambda s: s["seg_seq"])

        # 2. 下载所有分段音频到本地
        seg_paths: list[str] = []
        for seg in segments:
            seg_path = str(tmp_dir / f"seg_{seg['seg_seq']}.mp3")
            await download_file(seg["audio_url"], seg_path)
            seg_paths.append(seg_path)

        # 2.5 预估拼接总时长（含段间静音），便于排查时长偏差根因
        # TTS 段 duration 由 TTS 步骤上报，此处累加 + 段间静音得到预估总时长
        # 段间静音时长取频道级配置，回退全局 settings.SEGMENT_GAP_SEC
        seg_durations = [s.get("duration", 0) for s in segments]
        channel_slug, bgm_path, bgm_volume, gap_sec, _min_dur, bgm_gap_mode = await _resolve_channel_bgm(channel_id)
        estimated_total = sum(seg_durations) + max(0, len(seg_durations) - 1) * gap_sec
        target_sec = getattr(settings, "TARGET_DURATION_SEC", 600) or 600
        logger.info(
            "时长预估 workflow_id=%s 段数=%d 段时长=%s 段间静音=%.1fs 预估总时长=%ds 目标=%ds",
            workflow_id, len(seg_durations), seg_durations, gap_sec,
            estimated_total, target_sec,
        )

        # 3. 主音频拼接：TTS 段之间插入静音过渡
        # 段间静音的作用：① 避免 TTS 段突兀衔接 ② 无 BGM 时仍提供段间停顿,提升收听体验
        # 有 BGM 时,叠加轨在段间复用纯静音(gap_path),使停顿可被听觉感知(见 3.5)
        gap_path = str(tmp_dir / "gap.mp3")
        await generate_silence(gap_sec, gap_path)

        # 交替排列 [seg1, gap, seg2, gap, seg3, ...]，concat demuxer 顺序拼接
        interleaved: list[str] = []
        for i, p in enumerate(seg_paths):
            if i > 0:
                interleaved.append(gap_path)
            interleaved.append(p)
        main_path = str(tmp_dir / "main.mp3")
        await run_ffmpeg(build_concat_cmd(interleaved, main_path))

        # 3.5 (可选)叠加低音量 BGM 垫底
        # 频道级 BGM 优先（channel.bgm_path + channel.bgm_volume），回退到全局配置
        # bgm_gap_mode 控制段间静音处的处理：
        #   "silence"（默认）= 按 TTS 分段切片 BGM，段间复用 gap_path 纯静音 → 真实停顿
        #   "bridge"            = 旧版：循环 BGM 均匀铺满整段（含段间静音）→ BGM 桥接无停顿感
        if bgm_path:
            if bgm_gap_mode == "bridge":
                # 旧版 BGM 桥接：整段循环 BGM 均匀叠加，段间静音处表现为 BGM 桥接
                bgm_mix_path = str(tmp_dir / "main_bgm.mp3")
                await build_bgm_bridge(
                    main_path, str(bgm_path), bgm_volume, bgm_mix_path, str(tmp_dir),
                )
                main_path = bgm_mix_path
                logger.info(
                    "BGM 桥接模式 workflow_id=%s volume=%.2f（段间为 BGM 桥接）",
                    workflow_id, bgm_volume,
                )
            else:
                # 默认 silence：段间真实静音
                bgm_overlay_path = str(tmp_dir / "bgm_overlay.mp3")
                await build_bgm_overlay(
                    str(bgm_path), seg_durations, gap_path,
                    bgm_volume, bgm_overlay_path, str(tmp_dir),
                )
                bgm_mix_path = str(tmp_dir / "main_bgm.mp3")
                await run_ffmpeg([
                    resolve_ffmpeg_path(), "-y",
                    "-i", main_path, "-i", bgm_overlay_path,
                    "-filter_complex", "amix=inputs=2:duration=first",
                    "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
                    "-ar", "44100", "-ac", "1",
                    bgm_mix_path,
                ])
                main_path = bgm_mix_path
                logger.info(
                    "BGM 段间静音模式 workflow_id=%s volume=%.2f（段间静音处为纯静音）",
                    workflow_id, bgm_volume,
                )
        else:
            logger.info("无 BGM 配置,跳过混音 workflow_id=%s", workflow_id)

        # 4. 查询当日广告投放,需独立 db session(本模块不在请求上下文中)
        async with AsyncSessionLocal() as db:
            ad_service = AdService(db)
            placements = await ad_service.get_active_placements(episode_date)

        # 5. 中间广告插入(insert_at=300s),缺位则跳过
        mid_ad = placements.get("mid")
        if mid_ad:
            mid_ad_path = str(tmp_dir / "mid_ad.mp3")
            await download_file(mid_ad["file_url"], mid_ad_path)
            mid_inserted_path = str(tmp_dir / "main_with_mid.mp3")
            await run_ffmpeg(
                build_mid_ad_cmd(main_path, mid_ad_path, mid_inserted_path)
            )
            main_path = mid_inserted_path
            logger.info("中间广告已插入 workflow_id=%s", workflow_id)
        else:
            logger.info("无中间广告,跳过插入 workflow_id=%s", workflow_id)

        # 6. 生成 0.5s 静音过渡文件（广告与主音频之间的过渡,与段间 gap 区分）
        silence_path = str(tmp_dir / "silence.mp3")
        await generate_silence(SILENCE_DURATION, silence_path)

        # 7. 开头/结尾广告与主音频最终拼接,广告缺位则跳过该广告位
        head_ad = placements.get("head")
        tail_ad = placements.get("tail")
        final_inputs: list[str] = []
        if head_ad:
            head_ad_path = str(tmp_dir / "head_ad.mp3")
            await download_file(head_ad["file_url"], head_ad_path)
            final_inputs.append(head_ad_path)
            final_inputs.append(silence_path)
        final_inputs.append(main_path)
        if tail_ad:
            final_inputs.append(silence_path)
            tail_ad_path = str(tmp_dir / "tail_ad.mp3")
            await download_file(tail_ad["file_url"], tail_ad_path)
            final_inputs.append(tail_ad_path)

        final_path = str(tmp_dir / "final.mp3")
        if len(final_inputs) == 1:
            # 无任何广告:主音频直接重编码统一格式输出
            await run_ffmpeg([
                resolve_ffmpeg_path(), "-y", "-i", main_path,
                "-c:a", "libmp3lame", "-b:a", _audio_bitrate(),
                "-ar", "44100", "-ac", "1", final_path,
            ])
        else:
            await run_ffmpeg(build_full_concat_cmd(final_inputs, final_path))

        # 8. 时长校验 + 双向兜底（超长 atempo 加速 / 不足 BGM 补足）
        # 正常范围 [target×0.80, target×1.20]：
        # - 超长但在 1.15x atempo 可修复范围内时，自动轻微加速（不改变音高）
        # - 不足时优先用 BGM 自然延续兜底，无 BGM 时降级静音填充
        # 安全边界：atempo 最多 1.15x；补足最多追加 min_allowed×0.20 秒，避免无限补
        duration = await get_audio_duration(final_path)
        # 传入频道级最短时长（_min_dur）而非 channel_id：
        # _resolve_channel_bgm 已解析频道 min_duration_sec，此处应透传该值，
        # 原实现误把 channel_id（小整数）当作 min_duration_sec 传入，导致
        # 频道级最短时长配置完全失效（且 channel_id 大小被当成秒数下限）。
        min_allowed, max_allowed = _get_duration_range(_min_dur)
        if duration > max_allowed:
            tempo_needed = duration / max_allowed
            if tempo_needed <= 1.15:
                adjusted_path = str(tmp_dir / "final_adjusted.mp3")
                await adjust_tempo(final_path, adjusted_path, tempo_needed)
                final_path = adjusted_path
                original_duration = duration
                duration = await get_audio_duration(final_path)
                logger.info(
                    "atempo 加速兜底 workflow_id=%s tempo=%.3f 原时长=%ds 调整后=%ds",
                    workflow_id, tempo_needed, original_duration, duration,
                )
            else:
                raise StitchError(
                    f"最终音频时长 {duration}s 超出允许范围 "
                    f"[{min_allowed}, {max_allowed}]（目标时长 "
                    f"{getattr(settings, 'TARGET_DURATION_SEC', 600)}s ±20%），"
                    f"超长 {tempo_needed:.2f}x 超过 atempo 安全上限 1.15x"
                )
        elif duration < min_allowed:
            # 时长不足兜底：补到 min_allowed + 2s 缓冲（防 ffprobe 取整再次落入下限以下）
            # 优先用 BGM 尾段延续（与主节目 BGM 音量一致，听众感知为"节目在 BGM 中结束"）
            # 无 BGM 时降级静音填充（最后选择，仅保证不失败，体验略差）
            # 场景：rewriter 5.6 字数补足仍不够（LLM 严重不遵守字数约束 / selected 素材耗尽）
            shortfall = (min_allowed - duration) + 2
            # 上限保护：单次最多补 target×0.30 秒，超出说明 rewriter 严重失效，应直接失败暴露问题
            # 例外：素材稀缺场景（总段数 < SPARSE_SEGMENT_THRESHOLD，即正文段 < 3）时
            # rewriter 已动态下调段数下限，此处同步放宽 padding 上限到全部缺口，
            # 避免短节目因 padding 不足而拼接失败（R23 自动调整 / R110 自动降级）
            max_supplement = int(target_sec * 0.30)
            if len(segments) < SPARSE_SEGMENT_THRESHOLD:
                logger.warning(
                    "素材稀缺场景（总段数 %d < %d），放宽 padding 上限从 %ds 到 %ds",
                    len(segments), SPARSE_SEGMENT_THRESHOLD,
                    max_supplement, shortfall,
                )
                max_supplement = shortfall
            supplement_sec = min(shortfall, max_supplement)

            logger.warning(
                "时长不足兜底 workflow_id=%s 时长=%ds < 下限=%ds，补足 %ds（BGM=%s）",
                workflow_id, duration, min_allowed, supplement_sec,
                "有" if bgm_path else "无（降级静音）",
            )

            tail_path = str(tmp_dir / "tail_filler.mp3")
            if bgm_path:
                await generate_bgm_tail(
                    str(bgm_path), supplement_sec, tail_path, volume=bgm_volume,
                )
            else:
                await generate_silence(supplement_sec, tail_path)

            # 主音频 + 尾段拼接
            padded_path = str(tmp_dir / "final_padded.mp3")
            await run_ffmpeg(build_full_concat_cmd([final_path, tail_path], padded_path))
            final_path = padded_path
            original_duration = duration
            duration = await get_audio_duration(final_path)

            # 补足后仍不足则报错（不应发生，除非 ffprobe 测量异常）
            if duration < min_allowed:
                raise StitchError(
                    f"BGM/静音补足后时长仍不足: 原时长={original_duration}s "
                    f"补足 {supplement_sec}s 后={duration}s < 下限={min_allowed}s"
                )

            logger.info(
                "时长补足完成 workflow_id=%s 原时长=%ds 补足=%ds 最终=%ds",
                workflow_id, original_duration, supplement_sec, duration,
            )

        # 9. 上传 COS:key 含日期+频道名+workflow_id,避免同日多频道/重试覆盖
        # channel_slug 已在步骤 3.5 获取（与 BGM 配置同时查询），避免重复 DB 往返
        data = await asyncio.to_thread(_read_file, final_path)
        cos_key = (
            f"episodes/{episode_date.strftime('%Y%m%d')}/"
            f"{channel_slug}_{workflow_id}.mp3"
        )
        final_url = await upload_to_cos(data, cos_key)

        # 10. 生成 HLS 分片（V1.3 新增）：开启 HLS_ENABLE 时同步生成 m3u8 + ts 分片
        # 为什么放在 upload_to_cos 之后：mp3 是主交付物，HLS 失败不应阻塞主流程
        # 失败时仅记录日志，hls_url 留空，客户端回退到 mp3 播放
        hls_url = None
        if settings.HLS_ENABLE:
            try:
                hls_dir = str(tmp_dir / "hls")
                hls_cmd, _ = build_hls_cmd(final_path, hls_dir)
                await run_ffmpeg(hls_cmd)
                hls_key_prefix = (
                    f"episodes/{episode_date.strftime('%Y%m%d')}/"
                    f"{channel_slug}_{workflow_id}"
                )
                hls_url = await upload_hls_directory(hls_dir, hls_key_prefix)
                logger.info(
                    "HLS 生成完成 workflow_id=%s url=%s",
                    workflow_id, hls_url,
                )
            except Exception as hls_err:
                # HLS 失败不阻塞主流程：mp3 已上传，客户端可降级播放
                logger.warning(
                    "HLS 生成失败，回退到 mp3 播放 workflow_id=%s err=%s",
                    workflow_id, hls_err,
                )

        logger.info(
            "拼接完成 workflow_id=%s duration=%ds channel=%s url=%s hls=%s",
            workflow_id, duration, channel_slug, final_url,
            hls_url or "（未生成）",
        )
        return {
            "final_audio_url": final_url,
            "hls_url": hls_url,
            "duration": duration,
        }
    finally:
        # 10. 清理临时目录:无论成功失败都回收磁盘空间
        # 用 to_thread 包装避免阻塞事件循环（rmtree 在大目录下耗时）
        await asyncio.to_thread(shutil.rmtree, tmp_dir, ignore_errors=True)
