"""T01870 集成验证：离线真跑 stitch 主入口 `concat()`，覆盖正常/超长/不足三条分支。

为什么单独跑这个：`_validate/t01870_chain_ab.py` 只验证命令构造器与代际指标，
本脚本直接执行生产函数 `concat()` 本体（含时长校验、atempo 加速兜底、BGM 尾段
补足、HLS 从 PCM 编 AAC、中间 PCM 逐步回收），确认 PCM 化后整条链路真的能跑通。

不触碰任何外部服务与生产配置：
- 素材为本地合成文件，`download_file` 替换为本地复制；
- `upload_to_cos` / `upload_hls_directory` 替换为落盘到 _validate/t01870_run/；
- 广告投放查询替换为固定数据（不查库、不写库）；
- 时长目标/BGM 路径等参数只在**进程内**改 settings 对象，不写 .env。

用法：backend/.venv/Scripts/python.exe _validate/t01870_concat_integration.py
"""
import asyncio
import importlib
import json
import os
import shutil
import subprocess
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ev = importlib.import_module("t01845_compress_eval")
FFMPEG = ev.FFMPEG
RUN = os.path.join(HERE, "t01870_run")

from app.workflow.stitch import concat as concat_mod  # noqa: E402
from app.workflow.tts import audio_postprocess as ap  # noqa: E402

N_SEG = 24
SEG_DUR = 14.0
FAKE_PLACEMENTS = {
    "head": {"file_url": "local://head_ad.mp3"},
    "mid": {"file_url": "local://mid_ad.mp3"},
    "tail": {"file_url": "local://tail_ad.mp3"},
}
# 三个用例的目标时长（成品时长范围 = 目标 ±20%）
CASES = [("normal", 400), ("long_atempo", 280), ("short_pad", 460)]

MKDTEMP_ORIG = concat_mod.tempfile.mkdtemp
RMTREE_ORIG = concat_mod.shutil.rmtree
SEGMENTS: list[dict] = []
TMP_SIZES: list[int] = []
TMP_LEFTOVER: list[str] = []


def ff(*args: str) -> None:
    p = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-y", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300])


def set_(obj, **kw) -> None:
    """进程内改 settings（pydantic 模型可能禁变更，退化为 object.__setattr__）。"""
    for k, v in kw.items():
        try:
            setattr(obj, k, v)
        except Exception:
            object.__setattr__(obj, k, v)


def _read(p: str) -> bytes:
    with open(p, "rb") as f:
        return f.read()


async def build_assets() -> list[dict]:
    """合成 provider 素材 → 生产后处理（单次编码）→ 本地「段缓存」文件。"""
    segments = []
    for i in range(N_SEG):
        provider = os.path.join(RUN, f"provider_{i}.mp3")
        amp = 0.3 + 0.04 * (i % 3)
        ff("-f", "lavfi", "-i", f"anoisesrc=color=pink:r=24000:d={SEG_DUR}:a={amp:.2f}",
           "-f", "lavfi", "-i", f"sine=f={240 + 60 * i}:r=24000:d={SEG_DUR}",
           "-filter_complex",
           "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,volume=1.8,"
           "adelay=300|300,apad=pad_dur=0.4",
           "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", provider)
        seg = os.path.join(RUN, f"seg_{i}.mp3")
        with open(seg, "wb") as f:  # NOSONAR
            f.write(await ap.postprocess_segment(_read(provider)))
        segments.append({
            "seg_seq": i + 1,
            "audio_url": f"local://seg_{i}.mp3",
            "duration": await ap.get_audio_duration(_read(seg)),
        })
    for name in ("head_ad", "mid_ad", "tail_ad"):
        ff("-f", "lavfi", "-i", "sine=f=520:r=44100:d=1.5", "-af", "tremolo=f=5:d=0.6",
           "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k",
           os.path.join(RUN, f"{name}.mp3"))
    ff("-f", "lavfi", "-i", "anoisesrc=color=brown:r=44100:d=8:a=0.5",
       "-ac", "1", os.path.join(RUN, "bgm.wav"))
    return segments


async def fake_download(url: str, dest_path: str) -> None:
    shutil.copyfile(os.path.join(RUN, url[len("local://"):]), dest_path)


async def fake_upload(data: bytes, key: str) -> str:
    out = os.path.join(RUN, "uploaded", key.replace("/", "_"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:  # NOSONAR
        f.write(data)
    return f"file://{out}"


async def fake_hls(dir_path: str, key_prefix: str) -> str:
    listing = sorted(os.listdir(dir_path))
    with open(os.path.join(RUN, "uploaded", f"hls_{key_prefix.replace('/', '_')}.txt"),
              "w", encoding="utf-8") as f:
        f.write("\n".join(listing))
    return f"file://{dir_path}/playlist.m3u8"


class FakeAdService:
    def __init__(self, db):
        pass

    async def get_active_placements(self, episode_date):
        return dict(FAKE_PLACEMENTS)


def _dir_bytes(d: str) -> int:
    total = 0
    for root, _, files in os.walk(d):
        for fn in files:
            total += os.path.getsize(os.path.join(root, fn))
    return total


def _spy_tmpdir(prefix: str) -> str:
    path = MKDTEMP_ORIG(prefix=prefix)
    TMP_SIZES.append(0)
    return path


def _spy_rmtree(path, *a, **kw):
    # 记录每个用例临时目录在被清理前的峰值占用（PCM 中间态是否泄漏）
    if TMP_SIZES:
        TMP_SIZES[-1] = max(TMP_SIZES[-1], _dir_bytes(str(path)))
    return RMTREE_ORIG(path, *a, **kw)


def patch_env(settings) -> None:
    concat_mod.download_file = fake_download
    concat_mod.upload_to_cos = fake_upload
    concat_mod.upload_hls_directory = fake_hls
    concat_mod.AdService = FakeAdService
    concat_mod.tempfile.mkdtemp = _spy_tmpdir
    concat_mod.shutil.rmtree = _spy_rmtree
    set_(settings, BGM_GAP_MODE="continuous", HLS_ENABLE=True,
         SEGMENT_GAP_SEC=0.3, BGM_PATH=os.path.join(RUN, "bgm.wav"))


async def run_case(name: str, target: int, settings) -> dict:
    set_(settings, TARGET_DURATION_SEC=target)
    TMP_SIZES.append(0)
    res = await concat_mod.concat(f"t01870_{name}", date(2026, 10, 11),
                                  [dict(s) for s in SEGMENTS], channel_id=None)
    final_path = res["final_audio_url"][len("file://"):]
    hls_list = os.path.join(RUN, "uploaded", "hls_episodes_20261011_default_"
                                  f"t01870_{name}.txt")
    return {
        "case": name,
        "target_sec": target,
        "allowed_range_sec": list(concat_mod._get_duration_range(None)),
        "returned_duration": res["duration"],
        "final_bytes": os.path.getsize(final_path),
        "hls_files": (open(hls_list, encoding="utf-8").read().splitlines()
                      if os.path.isfile(hls_list) else []),
        "tmp_peak_bytes": TMP_SIZES[-1],
        "tmp_leaked": [f for f in os.listdir(__import__("tempfile").gettempdir())
                       if f.startswith(f"stitch_t01870_{name}")],
    }


async def main() -> None:
    if os.path.isdir(RUN):
        shutil.rmtree(RUN)
    os.makedirs(os.path.join(RUN, "uploaded"), exist_ok=True)
    settings = concat_mod.settings
    global SEGMENTS
    SEGMENTS = await build_assets()
    patch_env(settings)
    try:
        results = [await run_case(n, t, settings) for n, t in CASES]
    finally:
        concat_mod.tempfile.mkdtemp = MKDTEMP_ORIG
        concat_mod.shutil.rmtree = RMTREE_ORIG
    with open(os.path.join(HERE, "t01870_concat_integration.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
