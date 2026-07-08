"""音频拼接主入口:分段音频 → 主音频 → 广告插入 → 最终节目音频。

流程(LLD 第 4 步 stitch):
1. 下载 TTS 分段音频并按序拼接为主音频
2. 查询当日广告投放,中间位置插入广告
3. 开头/结尾广告与主音频最终拼接,加静音过渡
4. 时长校验(9:30-10:30)后上传 COS
"""
import asyncio
import logging
import shutil
import tempfile
from datetime import date
from pathlib import Path

from app.database import AsyncSessionLocal
from app.services.ad_service import AdService
from app.workflow.stitch.ffmpeg_wrapper import (
    StitchError,
    build_concat_cmd,
    build_full_concat_cmd,
    build_mid_ad_cmd,
    download_file,
    generate_silence,
    get_audio_duration,
    run_ffmpeg,
)
from app.workflow.tts.uploader import upload_to_cos

logger = logging.getLogger(__name__)

# 时长校验区间(秒):9:30-10:30,超出则视为内容异常
MIN_DURATION_SEC = 570
MAX_DURATION_SEC = 630
# 中间广告插入位置(秒):5 分钟处,避开开场白与首条新闻
MID_AD_INSERT_AT = 300
# 广告与主音频之间的静音过渡时长(秒)
SILENCE_DURATION = 0.5


def _read_file(path: str) -> bytes:
    """同步读取文件(由 asyncio.to_thread 调用,避免阻塞事件循环)。"""
    with open(path, "rb") as f:
        return f.read()


async def concat(workflow_id: str, episode_date, audio_segments: list) -> dict:
    """音频拼接主入口。

    Args:
        workflow_id: 工作流 ID,用于日志关联与临时目录命名
        episode_date: 节目日期(date 对象或 ISO 字符串),用于查询广告投放与生成 COS key
        audio_segments: TTS 分段列表 [{"seg_seq": 1, "audio_url": "...", "duration": 90}]

    Returns:
        {"final_audio_url": str, "duration": int}

    Raises:
        StitchError: 拼接失败或时长越界
    """
    # 兼容 date 对象与 ISO 字符串两种入参,上层调用方可能传任一形式
    if isinstance(episode_date, str):
        episode_date = date.fromisoformat(episode_date)

    logger.info(
        "拼接启动 workflow_id=%s date=%s segments=%d",
        workflow_id, episode_date, len(audio_segments),
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

        # 3. 主音频拼接(concat demuxer)
        main_path = str(tmp_dir / "main.mp3")
        await run_ffmpeg(build_concat_cmd(seg_paths, main_path))

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

        # 6. 生成 0.5s 静音过渡文件
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
                "ffmpeg", "-y", "-i", main_path,
                "-c:a", "libmp3lame", "-b:a", "128k",
                "-ar", "44100", "-ac", "1", final_path,
            ])
        else:
            await run_ffmpeg(build_full_concat_cmd(final_inputs, final_path))

        # 8. 时长校验:570 <= duration <= 630(9:30-10:30),否则视为内容异常
        duration = await get_audio_duration(final_path)
        if not (MIN_DURATION_SEC <= duration <= MAX_DURATION_SEC):
            raise StitchError(
                f"最终音频时长 {duration}s 超出允许范围 "
                f"[{MIN_DURATION_SEC}, {MAX_DURATION_SEC}]"
            )

        # 9. 上传 COS:key 按日期分目录,便于按期检索与清理
        data = await asyncio.to_thread(_read_file, final_path)
        cos_key = f"episodes/{episode_date.strftime('%Y%m%d')}/final.mp3"
        final_url = await upload_to_cos(data, cos_key)

        logger.info(
            "拼接完成 workflow_id=%s duration=%ds url=%s",
            workflow_id, duration, final_url,
        )
        return {"final_audio_url": final_url, "duration": duration}
    finally:
        # 10. 清理临时目录:无论成功失败都回收磁盘空间
        shutil.rmtree(tmp_dir, ignore_errors=True)
