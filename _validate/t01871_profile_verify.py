"""T01871 档位套餐实测：真实成品上比音质，链路真跑上比体积。

A 段（音质）：用已发布真实成品 ep100 的 300s 片段作参考，在**同一代编码**前提下比较
四组「码率 × 采样率」组合。这一步是为了复现 T01845 的结论并把口径搬到 T01870 之后的
新链路（一代编码）上：如果 64k@32k 仍不劣于 64k@44.1k，降采样率就不是妥协而是提质。

B 段（体积/参数）：离线真跑生产函数 `concat()`，在 standard 与 quality 两个档位各跑一遍，
比对成品实际采样率/码率、临时目录 PCM 峰值，确认档位真的贯通到链路两端。

不触碰外部服务与生产配置：素材只读本地产物，settings 只在进程内改，不写 .env。

用法：backend/.venv/Scripts/python.exe _validate/t01871_profile_verify.py
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
ci = importlib.import_module("t01870_concat_integration")
FFMPEG = ev.FFMPEG
RUN = os.path.join(HERE, "t01871_run")
SRC = os.path.join(HERE, "t01845_samples", "ep100.mp3")
START, CLIP_SEC = 30.0, 300.0

# (名称, 码率, 采样率)——覆盖旧口径、默认档、省流档、高音质档
VARIANTS = [
    ("mp3 64k@44100（旧口径）", "64k", 44100),
    ("mp3 64k@32000（standard）", "64k", 32000),
    ("mp3 48k@32000（lean）", "48k", 32000),
    ("mp3 96k@44100（quality）", "96k", 44100),
]


def ff(*args: str) -> None:
    p = subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-y", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300])


def quality_ab() -> list[dict]:
    """参考 = 真实成品解码出的 44.1k PCM；每个候选都是从同一参考出发的**一代**编码。"""
    ref_wav = os.path.join(RUN, "ref.wav")
    ff("-ss", str(START), "-t", str(CLIP_SEC), "-i", SRC,
       "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", ref_wav)
    ref = ev.decode_mono(SRC, "", start=START, dur=CLIP_SEC)
    rows = []
    for name, bitrate, rate in VARIANTS:
        out = os.path.join(RUN, f"cand_{bitrate}_{rate}.mp3")
        ff("-i", ref_wav, "-ar", str(rate), "-ac", "1",
           "-c:a", "libmp3lame", "-b:a", bitrate, out)
        cand = ev.decode_mono(out, "")
        r, c = ev.align(ref, cand)
        m = ev.metrics(r, c)
        rows.append({
            "variant": name,
            "bytes": os.path.getsize(out),
            "seg_snr_mean_db": m["seg_snr_mean_db"],
            "seg_snr_p10_db": m["seg_snr_p10_db"],
            "lsd_mean_db": m["lsd_mean_db"],
            "cand_cutoff_hz": m["cand_cutoff_hz"],
            "band_delta_db": m["band_delta_db"],
            "covered_sec": round(m["compared_sec"] * 512, 1),
        })
    return rows


def profile_run(profile: str) -> dict:
    """进程内切档 → 重新生成段素材（走生产后处理）→ 真跑 concat() 正常分支。"""
    settings = ci.concat_mod.settings
    ci.set_(settings, AUDIO_PROFILE=profile, AUDIO_BITRATE="", AUDIO_SAMPLE_RATE=0,
            TARGET_DURATION_SEC=400)
    os.makedirs(os.path.join(ci.RUN, "uploaded"), exist_ok=True)
    segments = asyncio.run(ci.build_assets())
    ci.SEGMENTS = segments
    ci.patch_env(settings)
    ci.TMP_SIZES.append(0)
    res = asyncio.run(ci.concat_mod.concat(
        f"t01871_{profile}", date(2026, 10, 11),
        [dict(s) for s in segments], channel_id=None,
    ))
    final = res["final_audio_url"][len("file://"):]
    seg_path = os.path.join(ci.RUN, os.path.basename(segments[0]["audio_url"]))
    probe, seg_probe = ev.probe(final), ev.probe(seg_path)
    return {
        "profile": profile,
        "seg_cache_codec": seg_probe["codec"],
        "seg_cache_sample_rate": seg_probe["sample_rate"],
        "seg_cache_bytes": seg_probe["size_bytes"],
        "final_codec": probe["codec"],
        "final_sample_rate": probe["sample_rate"],
        "final_bitrate_bps": probe["bitrate"],
        "final_duration": res["duration"],
        "allowed_range_sec": list(ci.concat_mod._get_duration_range(None)),
        "final_bytes": probe["size_bytes"],
        "tmp_peak_bytes": ci.TMP_SIZES[-1],
        "tmp_leaked": [
            f for f in os.listdir(__import__("tempfile").gettempdir())
            if f.startswith(f"stitch_t01871_{profile}")
        ],
    }


def dump(out: dict) -> None:
    """边跑边落盘：整轮 10 分钟量级，中途失败不该丢掉已实测的部分。"""
    with open(os.path.join(HERE, "t01871_profile_verify.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def main() -> None:
    if os.path.isdir(RUN):
        shutil.rmtree(RUN)
    os.makedirs(RUN, exist_ok=True)
    out: dict = {"quality_ab": quality_ab(), "chain_runs": []}
    dump(out)
    for profile in ("standard", "quality"):
        out["chain_runs"].append(profile_run(profile))
        dump(out)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
