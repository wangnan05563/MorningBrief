"""T02028 真实链路冒烟：concat 级本地拼接 → _create_review → publish_episode。

不花钱、不触发 LLM/TTS：分段音频用已有成品 ep100.mp3 切出的本地片段，
上传环节 monkeypatch 成本地保存（绝不把冒烟产物推到 COS）。
库写全部发生在 news.db 的副本上，生产库不受影响。
"""
import asyncio
import shutil
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

SMOKE_DIR = Path(__file__).with_name("t02028_smoke")
DB_COPY = SMOKE_DIR / "news.db"
SRC_DB = BACKEND / "data" / "news.db"
SRC_AUDIO = ROOT / "_validate" / "t01845_samples" / "ep100.mp3"
# 分段落到 download_file 认得的 /audio/ 端点根目录（拼接走真实下载分支，不绕开代码路径）
AUDIO_CACHE = BACKEND / "data" / "audio_cache" / "t02028_smoke"

SEG_SECONDS = [140, 140, 140]  # 合计 420s < 下限 480s，必然走「补足」分支，正好验证留痕


def _cut_segments():
    from app.paths import resolve_ffmpeg_path

    SMOKE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC_DB, DB_COPY)
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    urls = []
    for i, sec in enumerate(SEG_SECONDS, start=1):
        name = f"seg{i}.mp3"
        out = AUDIO_CACHE / name
        subprocess.run(
            [resolve_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
             "-ss", str((i - 1) * 30), "-t", str(sec), "-i", str(SRC_AUDIO),
             "-c:a", "libmp3lame", "-b:a", "64k", str(out)],
            check=True, capture_output=True,
        )
        urls.append(f"/audio/t02028_smoke/{name}")
    return urls


def _pin_local_db():
    """把 app 的库路径指向副本——必须在 import app.database 之前生效。"""
    from app import paths
    paths.resolve_db_path = lambda *a, **k: DB_COPY


def _no_cloud():
    """冒烟产物只在本地：替换上传函数，绝不碰 COS。"""
    from app.workflow.stitch import concat as concat_mod
    from app.workflow.tts import uploader

    async def _fake_upload(data: bytes, key: str) -> str:
        local = SMOKE_DIR / "out" / key.replace("/", "_")
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(data)
        return f"/local-smoke/{key}"

    async def _fake_hls(_dir, _prefix) -> str:
        return None

    concat_mod.upload_to_cos = _fake_upload
    concat_mod.upload_hls_directory = _fake_hls
    uploader.upload_to_cos = _fake_upload
    return _fake_upload


async def main():
    urls = _cut_segments()
    _pin_local_db()

    from app.workflow.stitch.concat import concat
    _no_cloud()

    wf = "t02028-smoke"
    result = await concat(
        workflow_id=wf,
        episode_date=date.today(),
        audio_segments=[
            {"seg_seq": i + 1, "audio_url": u, "duration": s}
            for i, (u, s) in enumerate(zip(urls, SEG_SECONDS))
        ],
        channel_id=None,
    )
    print("[concat] ->", {k: v for k, v in result.items()})
    assert result["duration"] >= 480, "补足后应落入允许区间"
    assert result["supplement_sec"] > 0, "420s 内容应触发补足留痕"
    assert result["original_duration"] < result["duration"]

    # ---- _create_review：实测时长是否真的进了 review 行 ----
    from app.services.workflow_scheduler import WorkflowScheduler
    from app.database import AsyncSessionLocal
    from app.models import Episode, Review, Script
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        script = Script(
            workflow_id=wf, episode_date=date.today(),
            full_text="冒烟稿件", segments=[{"seq": 1, "content": "段"}],
            estimated_duration=86,  # 与实测差 ~5 倍，发布若还落估算值一眼能看出来
            categories=None, status="approved",
        )
        session.add(script)
        await session.commit()
        await session.refresh(script)
        script_id = script.id

    ctx = {
        "workflow_id": wf,
        "episode_date": date.today(),
        "script_id": script_id,
        "final_audio_url": result["final_audio_url"],
        "hls_url": result.get("hls_url"),
        "duration": result["duration"],
        "original_duration": result["original_duration"],
        "supplement_sec": result["supplement_sec"],
    }
    created = await WorkflowScheduler()._create_review(ctx)
    review_id = created["review_id"]

    async with AsyncSessionLocal() as session:
        review = (await session.execute(
            select(Review).where(Review.id == review_id))).scalar_one()
        row = (review.measured_duration_sec, review.original_duration_sec,
               review.supplement_sec)
        print(f"[review #{review_id}] measured/original/supplement =", row)
        assert row == (result["duration"], result["original_duration"],
                       result["supplement_sec"])

        # ---- publish：时长取 review 实测，episode 带凑时快照 ----
        from app.services.content_service import ContentService
        # 探测函数打桩：有实测值时不该被调用；若被调用即为回归
        import app.workflow.stitch.ffmpeg_wrapper as fw
        calls = []
        orig_get_duration = fw.get_audio_duration_f

        async def _spy(url):
            calls.append(url)
            return await orig_get_duration(url)

        fw.get_audio_duration_f = _spy
        try:
            ep_id = await ContentService(session).publish_episode(wf, review_id)
        finally:
            fw.get_audio_duration_f = orig_get_duration

        ep = (await session.execute(
            select(Episode).where(Episode.id == ep_id))).scalar_one()
        print(f"[episode #{ep.id}] duration={ep.duration} "
              f"supplement={ep.supplement_sec} original={ep.original_duration_sec} "
              f"(估算值 86 应被忽略)")
        assert calls == [], f"有实测时长仍发起探测：{calls}"
        assert ep.duration == result["duration"] != 86
        assert ep.supplement_sec == result["supplement_sec"]
        assert ep.original_duration_sec == result["original_duration"]

    print("[ok] concat → review → episode 全链路时长留痕贯通（副本库，生产库未写）")
    conn = sqlite3.connect(str(DB_COPY))
    print("[copy db] review rows:",
          conn.execute("select count(*) from review").fetchone()[0],
          "| episode rows:",
          conn.execute("select count(*) from episode").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
