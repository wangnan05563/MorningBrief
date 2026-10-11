"""T01845 补充实验：候选参数扫描 + 参考信号绝对频带能量（判定哪些频段是噪声底）。

用于回答两个问题：
1. 「32kHz 采样」是否优于「44.1kHz 同码率」——内容上限实测只有约 10kHz，
   44.1k 采样带来的 10k 以上部分只有编码器噪声底，降采样可把比特花在有效带内；
2. 参考信号在 12k 以上的能量有多低——避免把噪声底的消失误判成音质损失。

用法：
    backend/.venv/Scripts/python.exe _validate/t01845_variants.py \
        --in _validate/t01845_samples/ep99.mp3 --start 20 --dur 300
"""
import argparse
import importlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ev = importlib.import_module("t01845_compress_eval")
import numpy as np

VARIANTS = [
    ("mp3_64k_44100", "MP3 64k @44.1kHz（现配置）",
     ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "44100", "-ac", "1"], "mp3"),
    ("mp3_64k_32000", "MP3 64k @32kHz",
     ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "32000", "-ac", "1"], "mp3"),
    ("mp3_48k_32000", "MP3 48k @32kHz",
     ["-c:a", "libmp3lame", "-b:a", "48k", "-ar", "32000", "-ac", "1"], "mp3"),
    ("mp3_40k_32000", "MP3 40k @32kHz",
     ["-c:a", "libmp3lame", "-b:a", "40k", "-ar", "32000", "-ac", "1"], "mp3"),
    ("mp3_vbr_q7_32000", "MP3 VBR q7 @32kHz",
     ["-c:a", "libmp3lame", "-q:a", "7", "-ar", "32000", "-ac", "1"], "mp3"),
    ("mp3_64k_24000", "MP3 64k @24kHz",
     ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "24000", "-ac", "1"], "mp3"),
    ("aac_48k_32000", "AAC 48k @32kHz（m4a）",
     ["-c:a", "aac", "-b:a", "48k", "-ar", "32000", "-ac", "1"], "m4a"),
    ("aac_56k_32000", "AAC 56k @32kHz（m4a）",
     ["-c:a", "aac", "-b:a", "56k", "-ar", "32000", "-ac", "1"], "m4a"),
]


def ref_band_energy(x: np.ndarray) -> dict:
    """参考信号各频带的绝对能量（dBFS）：低于 -70dBFS 的带属于噪声底，不计入质量判据。"""
    db = ev.stft_db(x)
    freqs = np.fft.rfftfreq(2048, 1 / ev.SR)
    out = {}
    for lo, hi in [(0, 3000), (3000, 6000), (6000, 9000), (9000, 12000),
                   (12000, 16000), (16000, 20000), (20000, 22050)]:
        m = (freqs >= lo) & (freqs < hi)
        if not m.any():
            continue
        e = 10 * np.log10((10 ** (db[:, m] / 10)).mean(axis=1) + 1e-12)
        out[f"{lo//1000}-{hi//1000}k"] = round(float(np.percentile(e, 90)), 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--start", type=float, default=20.0)
    ap.add_argument("--dur", type=float, default=300.0)
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "t01845_var"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    excerpt = os.path.join(args.outdir, "excerpt.mp3")
    subprocess.run([ev.FFMPEG, "-hide_banner", "-v", "error", "-y", "-ss", str(args.start),
                    "-i", args.src, "-t", str(args.dur), "-c", "copy", excerpt], capture_output=True)
    ref = ev.decode_mono(excerpt, "")
    ref_energy = ref_band_energy(ref)
    print(f"[参考频带能量 dBFS(p90)] {ref_energy}")

    rows = [{"label": "__reference__", "desc": "已发布基线（128k MP3）",
             "bitrate": ev.probe(excerpt)["bitrate"], "ref_band_energy_dbfs": ref_energy}]
    for label, desc, enc, ext in VARIANTS:
        out = os.path.join(args.outdir, f"{label}.{ext}")
        p = subprocess.run([ev.FFMPEG, "-hide_banner", "-v", "error", "-y", "-i", excerpt]
                           + enc + [out], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode != 0:
            print(f"[跳过] {label}: {p.stderr[:160]}")
            continue
        info = ev.probe(out)
        cand = ev.decode_mono(out, "")
        m = ev.metrics(ref, cand)
        m.update({"label": label, "desc": desc, "container": ext,
                  "size_bytes": info["size_bytes"], "bitrate": info["bitrate"],
                  "sample_rate": int(info["sample_rate"])})
        rows.append(m)
        print(f"[{label}] {info['bitrate']/1000:.1f}kbps ar={info['sample_rate']} "
              f"segSNR={m['seg_snr_mean_db']} p10={m['seg_snr_p10_db']} LSD={m['lsd_mean_db']} "
              f"cut={m['cand_cutoff_hz']} 6-9k={m['band_delta_db'].get('6-9k')} "
              f"9-12k={m['band_delta_db'].get('9-12k')}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"[写出] {args.out}")


if __name__ == "__main__":
    main()
