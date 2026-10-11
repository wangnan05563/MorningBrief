"""T01870 复验：拼接链路中间态改无损 PCM 后的代际损失与时长口径前后对比。

设计（尽量单变量）：
1. 先合成 10 段「类语音」provider 产物（mp3, 24k/128k），经**生产实现**
   `postprocess_segment` 单次后处理得到分段缓存 mp3 —— 这批文件是两条链的**共同输入**，
   于是新旧两链的差别只剩「中间步骤是否重编 MP3」。
2. 两条链都调用生产代码（`app.workflow.stitch.ffmpeg_wrapper` 命令构造器），
   按 stitch 真实步骤序列跑完：段间交叉淡化 → BGM 连续铺底 amix → 中间广告插入
   → 头/尾广告 + 静音过渡 final concat。旧链把 `_pcm_args()` 临时替换为
   libmp3lame 参数、中间文件用 .mp3 扩展名，即复刻 T01870 之前「每步重编」的行为。
3. 度量：以新链成品为参考算旧链成品的 segSNR/LSD（两者内容时间线一致，
   差异纯属编码代际）；同时对比各阶段 ffprobe 实测时长与成品体积，
   确认「改无损编码后时长口径不变、体积不变」。
4. 附带量化 TTS 后处理合并（loudnorm+silenceremove 由 2 次编码并成 1 次）的收益：
   对同一份后处理产物做 1 次同参数重编，测出「多 1 代」的代价。

用法：
    backend/.venv/Scripts/python.exe _validate/t01870_chain_ab.py
"""
import asyncio
import importlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ev = importlib.import_module("t01845_compress_eval")
FFMPEG = ev.FFMPEG

from app.workflow.stitch import ffmpeg_wrapper as fw  # noqa: E402
from app.workflow.stitch.concat import _resolve_crossfade_sec  # noqa: E402
from app.workflow.tts import audio_postprocess as ap  # noqa: E402

BITRATE = "64k"
SR_TTS = 24000
OLD_MP3_ARGS = ["-c:a", "libmp3lame", "-b:a", BITRATE, "-ar", "44100", "-ac", "1"]
_ORIG_PCM_ARGS = fw._pcm_args
N_SEG = 10


def ff(*args: str) -> None:
    p = subprocess.run(
        [FFMPEG, "-hide_banner", "-v", "error", "-y", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300])


def probe_dur(path: str) -> float:
    p = subprocess.run(
        [os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe"), "-v", "error",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(p.stdout.strip())


def make_provider_segment(out: str, idx: int, dur: float = 3.0) -> None:
    """合成一段「类语音」素材并编成 mp3，模拟 TTS provider 的产物（第 1 代）。

    粉噪 + 变调正弦覆盖宽带频谱（LSD/频带能量才有判别力），
    首尾留静音（让 silenceremove 真实生效），各段响度不同（让 loudnorm 真实生效）。
    """
    freq = 240 + 70 * idx
    amp = 0.25 + 0.05 * (idx % 4)
    ff("-f", "lavfi", "-i", f"anoisesrc=color=pink:r=24000:d={dur}:a={amp:.2f}",
       "-f", "lavfi", "-i", f"sine=f={freq}:r=24000:d={dur}",
       "-filter_complex",
       "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,volume=1.8,"
       "adelay=350|350,apad=pad_dur=0.4",
       "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", out)


def make_bgm(out: str, dur: float = 6.0) -> None:
    ff("-f", "lavfi", "-i", f"anoisesrc=color=brown:r=44100:d={dur}:a=0.5",
       "-f", "lavfi", "-i", f"sine=f=180:r=44100:d={dur}",
       "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0",
       "-ac", "1", "-b:a", "192k", out)


def make_ad(out: str, dur: float = 2.0) -> None:
    ff("-f", "lavfi", "-i", f"sine=f=520:r=44100:d={dur}",
       "-af", "tremolo=f=5:d=0.7", "-ac", "1",
       "-c:a", "libmp3lame", "-b:a", "128k", out)


def mode(lossy: bool) -> str:
    """切换中间态：lossy=True 复刻旧链路（每步重编 mp3），False 为 PCM 新链路。"""
    fw._pcm_args = (lambda: list(OLD_MP3_ARGS)) if lossy else _ORIG_PCM_ARGS
    return ".mp3" if lossy else ".wav"


def _read(p: str) -> bytes:
    with open(p, "rb") as f:
        return f.read()


async def postprocess_old(src: str, dst: str) -> None:
    """T01870 之前的后处理：loudnorm 编一次 mp3，再 silenceremove 编一次 mp3。"""
    norm = dst.replace(".mp3", "_norm.mp3")
    ff("-i", src, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
       "-ar", str(SR_TTS), "-ac", "1", "-b:a", BITRATE, norm)
    ff("-i", norm, "-af",
       "silenceremove=start_periods=1:start_threshold=-50dB:"
       "stop_periods=-1:stop_threshold=-50dB:stop_duration=0.3",
       "-b:a", BITRATE, dst)
    os.unlink(norm)


async def encode(timeline: str, out: str) -> None:
    """成品编码（生产口径：整期唯一一次有损编码）。"""
    await fw.run_ffmpeg([FFMPEG, "-y", "-i", timeline, *fw._encode_args(), out])


def build_shared_inputs_real(tmp: str, src: str, seg_dur: float = 12.0) -> list[str]:
    """用真实已发布成品切出的分段作为两条链的共同输入（不做任何重编码）。

    评估口径要求以真实产物为准（合成信号的高频内容偏多，代际噪声在 12kHz 以上
    会被放大），故与 `--synth` 并行提供本模式。`-c copy` 保证切分零代际。
    """
    segs = os.path.join(tmp, "real_segs")
    os.makedirs(segs, exist_ok=True)
    ff("-i", src, "-f", "segment", "-segment_time", str(seg_dur),
       "-c", "copy", os.path.join(segs, "seg_%03d.mp3"))
    return [os.path.join(segs, f) for f in sorted(os.listdir(segs))][:N_SEG]


async def build_shared_inputs(tmp: str) -> list[str]:
    """provider 合成素材 → 生产后处理（单次编码）→ 两条链共同的段缓存 mp3。"""
    seg_paths = []
    for i in range(N_SEG):
        provider = os.path.join(tmp, f"provider_{i}.mp3")
        make_provider_segment(provider, i)
        seg = os.path.join(tmp, f"seg_{i}.mp3")
        with open(seg, "wb") as f:  # NOSONAR
            f.write(await ap.postprocess_segment(_read(provider)))
        seg_paths.append(seg)
    return seg_paths


async def run_stitch(tmp: str, seg_srcs: list[str], lossy: bool) -> dict:
    """按 stitch 真实步骤序列跑一条链，返回成品路径与各阶段实测时长。"""
    e = mode(lossy)
    work = os.path.join(tmp, "old" if lossy else "new")
    os.makedirs(work, exist_ok=True)

    # 段入口：新链统一解码到 PCM（解码不再引入有损代际）；旧链直接用段缓存 mp3
    seg_paths = []
    for i, s in enumerate(seg_srcs):
        if lossy:
            seg_paths.append(s)
        else:
            pcm = os.path.join(work, f"seg_{i}.wav")
            await fw.to_pcm(s, pcm)
            seg_paths.append(pcm)

    stages: dict[str, float] = {}
    seg_durs = [await fw.get_audio_duration_f(p) for p in seg_paths]
    crossfade = _resolve_crossfade_sec(seg_durs)

    main = os.path.join(work, f"main{e}")
    await fw.run_ffmpeg(fw.build_crossfade_cmd(seg_paths, crossfade, main))
    stages["1_join"] = probe_dur(main)

    bgm = os.path.join(tmp, "bgm.wav")
    if not os.path.exists(bgm):
        make_bgm(bgm)
    overlay = os.path.join(work, f"bgm_overlay{e}")
    await fw.build_bgm_continuous(bgm, stages["1_join"], 0.15, overlay)
    mixed = os.path.join(work, f"main_bgm{e}")
    await fw.run_ffmpeg(fw.build_amix_cmd(main, overlay, mixed))
    main = mixed
    stages["2_after_bgm"] = probe_dur(main)

    mid_src = os.path.join(tmp, "mid_ad.mp3")
    if not os.path.exists(mid_src):
        make_ad(mid_src)
    mid_ad = mid_src if lossy else os.path.join(work, "mid_ad.wav")
    if not lossy:
        await fw.to_pcm(mid_src, mid_ad)
    with_mid = os.path.join(work, f"main_with_mid{e}")
    await fw.run_ffmpeg(fw.build_mid_ad_cmd(main, mid_ad, with_mid))
    main = with_mid
    stages["3_after_mid_ad"] = probe_dur(main)

    sil = os.path.join(work, f"silence{e}")
    await fw.generate_silence(0.5, sil)
    ad_paths = []
    for tag, dur in (("head", 1.5), ("tail", 1.5)):
        src = os.path.join(tmp, f"{tag}_ad.mp3")
        if not os.path.exists(src):
            make_ad(src, dur)
        path = src if lossy else os.path.join(work, f"{tag}.wav")
        if not lossy:
            await fw.to_pcm(src, path)
        ad_paths.append(path)

    final = os.path.join(work, "final.mp3" if not lossy else f"final{e}")
    if lossy:
        # 旧链：final concat 直接产出成品（每步都已重编，成品是第 N 代）
        await fw.run_ffmpeg(
            fw.build_full_concat_cmd([ad_paths[0], sil, main, sil, ad_paths[1]], final)
        )
    else:
        # 新链：广告与主音频在 PCM 时间线汇合，随后唯一一次有损编码
        timeline = os.path.join(work, "timeline.wav")
        await fw.run_ffmpeg(
            fw.build_full_concat_cmd([ad_paths[0], sil, main, sil, ad_paths[1]], timeline)
        )
        await encode(timeline, final)
    stages["4_final"] = probe_dur(final)

    return {
        "mode": "old" if lossy else "new",
        "final": final,
        "crossfade_sec": round(crossfade, 3),
        "stages": {k: round(v, 3) for k, v in stages.items()},
        "final_int_sec": int(stages["4_final"]),
        "size_bytes": os.path.getsize(final),
    }


def compare(ref_path: str, cand_path: str) -> dict:
    ref = ev.decode_mono(ref_path, "")
    cand = ev.decode_mono(cand_path, "")
    r, c = ev.align(ref, cand)
    m = ev.metrics(r, c)
    # 引擎的 compared_sec 字段是「帧数/采样率」，换算真实秒数需乘回帧移（hop=512）
    covered_sec = round(m["compared_sec"] * 512, 1)
    return {
        **{k: m[k] for k in ("seg_snr_mean_db", "seg_snr_p10_db", "global_snr_db",
                              "lsd_mean_db", "level_delta_db",
                              "ref_cutoff_hz", "cand_cutoff_hz")},
        "covered_sec": covered_sec,
        "band_delta_db": m["band_delta_db"],
    }


async def measure_extra_generation(tmp: str, seg_srcs: list[str]) -> dict:
    """量化「多一代同参数 MP3 重编」的代价（对应旧链各中间步骤的每次重编）。

    基准取段缓存 mp3 本身（内容一致，纯 codec 差），候选取它在同码率/同参数下
    再编 1 次与 3 次的产物——旧链 stitch 恰好是 3~4 次这样的重编。
    """
    base = seg_srcs[0]
    rows = []
    for gens in (1, 2, 3):
        cur = base
        for g in range(gens):
            nxt = os.path.join(tmp, f"gen{gens}_{g}.mp3")
            ff("-i", cur, "-c:a", "libmp3lame", "-b:a", BITRATE,
               "-ar", "44100", "-ac", "1", nxt)
            cur = nxt
        rows.append({"extra_generations": gens, **compare(base, cur)})
    return rows


async def main() -> None:
    import argparse

    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--real", default=None,
                     help="真实成品 mp3 路径（用其切段作为两条链的共同输入）；不给则用合成素材")
    args = ap_.parse_args()

    tmp = os.path.join(HERE, "t01870_ab")
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    os.makedirs(tmp, exist_ok=True)
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "bitrate": BITRATE, "n_seg": N_SEG,
           "input_mode": "real" if args.real else "synthetic",
           "input_src": args.real}

    if args.real:
        seg_srcs = build_shared_inputs_real(tmp, args.real)
    else:
        seg_srcs = await build_shared_inputs(tmp)

    old = await run_stitch(tmp, seg_srcs, lossy=True)
    new = await run_stitch(tmp, seg_srcs, lossy=False)
    out["old_chain"] = old
    out["new_chain"] = new

    # 以新链成品为参考：旧链成品相对新链损失多少（= 被消除的代际损失）
    out["old_vs_new"] = compare(new["final"], old["final"])
    out["duration_delta_sec_new_minus_old"] = {
        k: round(new["stages"][k] - old["stages"][k], 3) for k in old["stages"]
    }
    out["final_int_sec_equal"] = old["final_int_sec"] == new["final_int_sec"]
    out["size_delta_bytes_new_minus_old"] = new["size_bytes"] - old["size_bytes"]

    out["per_extra_generation_cost"] = await measure_extra_generation(tmp, seg_srcs)

    # 编码代数记账（便于复核）：provider → 段缓存 → stitch 各步 → 成品
    out["lossy_generations"] = {
        "old_chain_stitch": 4,   # 段间拼接、BGM amix、中间广告、最终 concat 各编一次
        "new_chain_stitch": 1,   # 仅最终成品编码
        "old_chain_tts_postprocess": 2,  # loudnorm 一次 + silenceremove 一次
        "new_chain_tts_postprocess": 1,  # 合并为单次编码
    }

    fw._pcm_args = _ORIG_PCM_ARGS
    suffix = "_real" if args.real else ""
    out_path = os.path.join(HERE, f"t01870_chain_ab{suffix}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    keys = ("seg_snr_mean_db", "seg_snr_p10_db", "lsd_mean_db", "covered_sec")
    print("old_vs_new:", {k: out["old_vs_new"][k] for k in keys})
    print("band:", out["old_vs_new"]["band_delta_db"])
    print("per_gen:", [(r["extra_generations"], r["seg_snr_mean_db"], r["lsd_mean_db"])
                       for r in out["per_extra_generation_cost"]])
    print("durations:", out["duration_delta_sec_new_minus_old"],
          "int_equal:", out["final_int_sec_equal"],
          "size_delta:", out["size_delta_bytes_new_minus_old"])


if __name__ == "__main__":
    asyncio.run(main())
