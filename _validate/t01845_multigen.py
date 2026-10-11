"""T01845 补充实验：代际损失（同一码率反复重编码）与第二样本复验。

背景：本仓库当前链路对每个 TTS 段要做 loudnorm→silenceremove，再经 concat、final
两次统一格式，全链都是 libmp3lame 有损重编——即同一内容被 MP3 编码 3~4 代。
若把中间产物改为无损（wav/pcm），最终只编一次，同码率下的音质会显著更好，
等价于「不降码率也能拿到额外压缩余量」。本脚本量化这个差值。

用法：
    backend/.venv/Scripts/python.exe _validate/t01845_multigen.py \
        --in _validate/t01845_samples/ep100.mp3 --start 30 --dur 300
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ev = importlib.import_module("t01845_compress_eval")


def encode_chain(src: str, bitrate: str, gens: int, tmpdir: str) -> str:
    cur = src
    for i in range(gens):
        nxt = os.path.join(tmpdir, f"gen{i}_{bitrate}.mp3")
        p = subprocess.run(
            [ev.FFMPEG, "-hide_banner", "-v", "error", "-y", "-i", cur,
             "-c:a", "libmp3lame", "-b:a", bitrate, "-ar", "44100", "-ac", "1", nxt],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            raise RuntimeError(p.stderr[:200])
        cur = nxt
    return cur


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--start", type=float, default=30.0)
    ap.add_argument("--dur", type=float, default=300.0)
    ap.add_argument("--bitrates", default="48k,64k")
    ap.add_argument("--outdir", default=os.path.join(HERE, "t01845_gen"))
    ap.add_argument("--out", default=os.path.join(HERE, "t01845_multigen.json"))
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    excerpt = os.path.join(args.outdir, "excerpt.mp3")
    subprocess.run([ev.FFMPEG, "-hide_banner", "-v", "error", "-y", "-ss", str(args.start),
                    "-i", args.src, "-t", str(args.dur), "-c", "copy", excerpt],
                   capture_output=True)
    ref = ev.decode_mono(excerpt, "")

    rows = []
    for br in args.bitrates.split(","):
        for gens in (1, 2, 3, 4):
            f = encode_chain(excerpt, br, gens, args.outdir)
            t0 = time.perf_counter()
            cand = ev.decode_mono(f, "")
            m = ev.metrics(ref, cand)
            info = ev.probe(f)
            m.update({"bitrate_label": br, "generations": gens,
                      "size_bytes": info["size_bytes"], "bitrate": info["bitrate"],
                      "decode_sec": round(time.perf_counter() - t0, 2)})
            rows.append(m)
            print(f"[{br} x{gens}代] {info['bitrate']/1000:.1f}kbps "
                  f"segSNR={m['seg_snr_mean_db']} p10={m['seg_snr_p10_db']} "
                  f"LSD={m['lsd_mean_db']} cut={m['cand_cutoff_hz']} "
                  f"band={m['band_delta_db']}")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    print(f"[写出] {args.out}")


if __name__ == "__main__":
    main()
