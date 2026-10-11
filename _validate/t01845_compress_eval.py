"""T01845 音频压缩潜力评估（客观指标驱动，不依赖人工试听结论）。

输入：本项目已发布的成品音频（128kbps 单声道 44.1kHz MP3）。
做四件事：
1. 基线盘点：ffprobe 取编码参数、体积、有效频谱上限（判断 44.1k 采样是否被内容用满）；
2. 压缩矩阵：对同一 excerpt 生成多档重编码样本（MP3 CBR/VBR、AAC、Opus，含降采样档）；
3. 客观质量：以基线为参考，逐档计算分段 SNR、对数谱距离、分频带能量差、频谱截止，
   并记录编码耗时（实时性约束）；
4. 效率：体积/压缩比/下载耗时对比。

口径说明（重要）：参考信号本身是有损成品，测量的是「在当前交付质量之上再压一代」
的代际损失，比「从 TTS 源直接编到目标码率」更严苛 → 结论偏保守，可直接作为下限。
PESQ/POLQA 需要干净的原始参考（本仓库无未压缩源），故不采用，改用有参考失真度量。

用法：
    backend/.venv/Scripts/python.exe _validate/t01845_compress_eval.py \
        --in _validate/t01845_samples/ep100.mp3 --start 30 --dur 300 \
        --out _validate/t01845_eval.json
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FFMPEG = os.path.join(ROOT, "backend", "ffmpeg", "bin", "ffmpeg.exe")
FFPROBE = os.path.join(ROOT, "backend", "ffmpeg", "bin", "ffprobe.exe")
SR = 44100

# 压缩矩阵：(标签, 描述, 输出容器, ffmpeg 参数)
MATRIX = [
    ("mp3_cbr_128", "MP3 CBR 128k（基线同码率重编，代际下限对照）", "mp3",
     ["-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-ac", "1"]),
    ("mp3_cbr_96", "MP3 CBR 96k", "mp3",
     ["-c:a", "libmp3lame", "-b:a", "96k", "-ar", "44100", "-ac", "1"]),
    ("mp3_cbr_64", "MP3 CBR 64k（当前代码默认档）", "mp3",
     ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "44100", "-ac", "1"]),
    ("mp3_cbr_48", "MP3 CBR 48k", "mp3",
     ["-c:a", "libmp3lame", "-b:a", "48k", "-ar", "44100", "-ac", "1"]),
    ("mp3_cbr_40", "MP3 CBR 40k", "mp3",
     ["-c:a", "libmp3lame", "-b:a", "40k", "-ar", "44100", "-ac", "1"]),
    ("mp3_cbr_32", "MP3 CBR 32k", "mp3",
     ["-c:a", "libmp3lame", "-b:a", "32k", "-ar", "44100", "-ac", "1"]),
    ("mp3_vbr_q6", "MP3 VBR -q:a 6", "mp3",
     ["-c:a", "libmp3lame", "-q:a", "6", "-ar", "44100", "-ac", "1"]),
    ("mp3_vbr_q8", "MP3 VBR -q:a 8", "mp3",
     ["-c:a", "libmp3lame", "-q:a", "8", "-ar", "44100", "-ac", "1"]),
    ("mp3_vbr_q9", "MP3 VBR -q:a 9（单声道语音推荐档）", "mp3",
     ["-c:a", "libmp3lame", "-q:a", "9", "-ar", "44100", "-ac", "1"]),
    ("mp3_64k_32k_ar", "MP3 64k + 32kHz 采样（验证降采样收益）", "mp3",
     ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "32000", "-ac", "1"]),
    ("aac_64", "AAC-LC 64k（m4a，小程序兼容）", "m4a",
     ["-c:a", "aac", "-b:a", "64k", "-ar", "44100", "-ac", "1"]),
    ("aac_48", "AAC-LC 48k（m4a）", "m4a",
     ["-c:a", "aac", "-b:a", "48k", "-ar", "44100", "-ac", "1"]),
    ("aac_32", "AAC-LC 32k（m4a）", "m4a",
     ["-c:a", "aac", "-b:a", "32k", "-ar", "44100", "-ac", "1"]),
    ("opus_48", "Opus 48k（技术上限参照，小程序不支持）", "ogg",
     ["-c:a", "libopus", "-b:a", "48k", "-ar", "48000", "-ac", "1"]),
    ("opus_32", "Opus 32k（VoIP 语音档）", "ogg",
     ["-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1", "-application", "voip"]),
    ("opus_24", "Opus 24k", "ogg",
     ["-c:a", "libopus", "-b:a", "24k", "-ar", "48000", "-ac", "1", "-application", "voip"]),
]

# 分频带（Hz）：语音主要能量在 0-8k，BGM 与齿音在 8-16k，16k 以上基本只有源采样上限信息
BANDS = [(0, 300), (300, 1000), (1000, 3000), (3000, 6000),
         (6000, 9000), (9000, 12000), (12000, 16000), (16000, 20000)]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path: str) -> dict:
    r = run([FFPROBE, "-hide_banner", "-v", "error", "-show_entries",
             "format=duration,bit_rate,size", "-show_entries",
             "stream=codec_name,sample_rate,channels", "-of", "json", path])
    d = json.loads(r.stdout)
    fmt, st = d.get("format", {}), (d.get("streams") or [{}])[0]
    return {
        "codec": st.get("codec_name"), "sample_rate": st.get("sample_rate"),
        "channels": st.get("channels"), "size_bytes": int(fmt["size"]),
        "bitrate": int(float(fmt["bit_rate"])), "duration": float(fmt["duration"]),
    }


def decode_mono(src: str, out_wav: str, start: float | None = None, dur: float | None = None) -> np.ndarray:
    """解码为 44.1kHz 单声道 float32（统一口径后才能逐样本比较）。

    直接取 ffmpeg 的 raw f32le 字节流，不解析 WAV 头（扩展头会让固定 44 字节偏移失真）。
    out_wav 参数仅保留给调用方传路径占位，不再落盘。
    """
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-nostdin"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", src]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-ac", "1", "-ar", str(SR), "-c:a", "pcm_f32le", "-f", "f32le", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"decode 失败: {p.stderr[:300].decode(errors='replace')}")
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def align(ref: np.ndarray, cand: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """对齐编码器延迟/填充偏移（±0.5s），再按公共长度截断。

    不同编解码器的前导延迟不同（MP3 576 样本、AAC ~1024、Opus 编译器相关），
    不对齐会让逐样本误差里混入时间偏移，SNR 会假性崩到个位数。
    """
    win = min(len(ref), len(cand), SR * 3)
    step = 32
    rc, cc = ref[:win], cand[: win + SR // 2]
    if np.allclose(rc, 0) or np.allclose(cc, 0):
        return ref, cand
    best_off, best_err = 0, np.inf
    for off in range(0, len(cc) - win + 1, step):
        err = float(((rc - cc[off: off + win]) ** 2).mean())
        if err < best_err:
            best_off, best_err = off, err
    # 精搜：粗网格步长 32 样本（0.7ms）会残留高频相位误差，±step 内逐样本再收一次
    lo, hi = max(0, best_off - step), min(len(cc) - win, best_off + step)
    for off in range(lo, hi + 1):
        err = float(((rc - cc[off: off + win]) ** 2).mean())
        if err < best_err:
            best_off, best_err = off, err
    cand = cand[best_off:]
    L = min(len(ref), len(cand))
    return ref[:L], cand[:L]


def frames(x: np.ndarray, size: int, hop: int) -> np.ndarray:
    idx = 1 + (len(x) - size) // hop
    if idx <= 0:
        return np.empty((0, size))
    return np.lib.stride_tricks.as_strided(
        x, shape=(idx, size), strides=(x.strides[0] * hop, x.strides[0])
    ).copy()


def stft_db(x: np.ndarray, size: int = 2048, hop: int = 512) -> np.ndarray:
    w = np.hanning(size)
    fr = frames(x, size, hop)
    spec = np.abs(np.fft.rfft(fr * w, axis=1)) + 1e-9
    return 20 * np.log10(spec)


def metrics(ref: np.ndarray, cand: np.ndarray) -> dict:
    """有参考失真度量：分段 SNR、对数谱距离、分频带能量差、频谱截止。

    先做整体最小二乘增益匹配再算误差：不同编码器/解码器之间存在约 ±0.5dB 的系统
    响度差（实测 128k→128k 重编就有 0.44dB），不剔除的话纯电平差就能把 SNR 压到
    26dB，把「压缩损失」和「电平差」混为一谈。电平差本身单独作为字段输出。
    """
    ref, cand = align(ref, cand)
    gain = float((ref * cand).sum() / ((cand * cand).sum() + 1e-12))
    cand_g = cand * gain
    level_delta_db = round(20 * np.log10(abs(gain) + 1e-12), 2)

    fs, hs = int(0.02 * SR), int(0.01 * SR)
    fr, fc = frames(ref, fs, hs), frames(cand_g, fs, hs)
    rms_r = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
    rms_e = np.sqrt(((fr - fc) ** 2).mean(axis=1) + 1e-12)
    active = rms_r > 10 ** (-60 / 20)  # 只统计非静音帧，避免静音段把 SNR 拉高
    seg_snr = 20 * np.log10(rms_r[active] / (rms_e[active] + 1e-12))
    global_snr = 10 * np.log10((ref ** 2).sum() / ((ref - cand_g) ** 2).sum() + 1e-12)

    sr_db, sc_db = stft_db(ref), stft_db(cand_g)
    L = min(len(sr_db), len(sc_db))
    freqs = np.fft.rfftfreq(2048, 1 / SR)
    # LSD 只在有效语音带宽（≤11kHz）内算：基线本身在 10k 以上就没有内容了，
    # 把空频段计入会让逐 bin 的 dB 差被噪声底放大（实测均值虚高一个数量级）
    valid = freqs <= 11000
    lsd = np.sqrt(((sr_db[:L] - sc_db[:L])[:, valid] ** 2).mean(axis=1))

    band_delta = {}
    for lo, hi in BANDS:
        m = (freqs >= lo) & (freqs < hi)
        er = 10 * np.log10((10 ** (sr_db[:, m] / 10)).mean(axis=1) + 1e-12)
        ec = 10 * np.log10((10 ** (sc_db[:L][:, m] / 10)).mean(axis=1) + 1e-12)
        band_delta[f"{lo//1000}-{hi//1000}k"] = round(float(np.median(er - ec)), 2)

    def cutoff(db_spec: np.ndarray) -> int:
        mean = db_spec.mean(axis=0)
        peak = mean.max()
        ok = np.where(mean > peak - 45)[0]
        return int(freqs[ok[-1]]) if len(ok) else 0

    return {
        "level_delta_db": level_delta_db,
        "seg_snr_mean_db": round(float(seg_snr.mean()), 2),
        "seg_snr_p10_db": round(float(np.percentile(seg_snr, 10)), 2),
        "global_snr_db": round(float(global_snr), 2),
        "lsd_mean_db": round(float(lsd.mean()), 3),
        "lsd_p95_db": round(float(np.percentile(lsd, 95)), 3),
        "band_delta_db": band_delta,
        "ref_cutoff_hz": cutoff(sr_db),
        "cand_cutoff_hz": cutoff(sc_db),
        "compared_sec": round(L / SR, 1),
    }


def download_time_sec(size_bytes: int, kbps: float) -> float:
    return size_bytes * 8 / (kbps * 1000)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--start", type=float, default=30.0)
    ap.add_argument("--dur", type=float, default=300.0)
    ap.add_argument("--outdir", default=os.path.join(HERE, "t01845_out"))
    ap.add_argument("--out", default=os.path.join(HERE, "t01845_eval.json"))
    ap.add_argument("--bands", default="", help="逗号分隔的标签子集（调试用）")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    base = probe(args.src)
    print(f"[基线] {base}")

    excerpt = os.path.join(args.outdir, "excerpt_src.mp3")
    run([FFMPEG, "-hide_banner", "-v", "error", "-y", "-ss", str(args.start),
         "-i", args.src, "-t", str(args.dur), "-c", "copy", excerpt])
    ref = decode_mono(excerpt, os.path.join(args.outdir, "ref.wav"))
    print(f"[参考波形] {len(ref)/SR:.1f}s")

    subset = set(args.bands.split(",")) if args.bands else None
    results = {"baseline_file": base, "excerpt": {"start": args.start, "dur": args.dur,
                                                  "sha_sample": os.path.basename(args.src)},
               "candidates": []}
    for label, desc, ext, enc in MATRIX:
        if subset and label not in subset:
            continue
        out = os.path.join(args.outdir, f"{label}.{ext}")
        t0 = time.perf_counter()
        p = run([FFMPEG, "-hide_banner", "-v", "error", "-y", "-i", excerpt] + enc + [out])
        rt = time.perf_counter() - t0
        if p.returncode != 0:
            print(f"[跳过] {label}: {p.stderr[:200]}")
            continue
        info = probe(out)
        cand = decode_mono(out, os.path.join(args.outdir, f"{label}.wav"))
        m = metrics(ref, cand)
        m.update({"label": label, "desc": desc, "container": ext,
                  "size_bytes": info["size_bytes"], "bitrate": info["bitrate"],
                  "sample_rate": info["sample_rate"],
                  "encode_sec": round(rt, 2), "rtf": round(rt / args.dur, 4),
                  "bytes_per_sec": round(info["size_bytes"] / args.dur, 1)})
        for kbps, tag in ((500, "0.5Mbps"), (1000, "1Mbps"), (2000, "2Mbps"), (5000, "5Mbps")):
            m[f"dl_sec@{tag}"] = round(download_time_sec(info["size_bytes"], kbps), 1)
        results["candidates"].append(m)
        print(f"[{label}] {info['bitrate']/1000:.1f}kbps {info['size_bytes']/1e6:.2f}MB "
              f"segSNR={m['seg_snr_mean_db']} LSD={m['lsd_mean_db']} "
              f"cut={m['cand_cutoff_hz']} enc={rt:.2f}s")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[写出] {args.out}（{len(results['candidates'])} 档）")


if __name__ == "__main__":
    main()
