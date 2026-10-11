"""T01923 人工 A/B 试听包生成（离线、盲听、可复核）。

本环境没有耳朵，所以这脚本只负责把「该听什么、听哪三段、三版怎么对应」做成可直接执行的包：
1. 在真实已发布成品上**自动定位三类锚点**（衔接点 / 片头 BGM 垫乐段 / 齿音段），不靠猜时间码；
2. 每个锚点产出 3 个版本：线上原码流（-c copy 零重编）、64k@44100（旧口径同码率）、64k@32000（standard），
   随机打乱成 clipN_A/B/C.mp3，映射键单独存 _blind_key.json（听完再对答案）；
3. 给出每个锚点每个版本的**客观差值先验**（segSNR / LSD / 6-12kHz 频带差 / 截止频率），
   用于提示「哪一段最可能被听出来」，不是结论。

诚实边界：候选是从已发布成品（本身 128k MP3）解码后再编 → 带一世代际；
干净的同代对比要等新链路真跑产出真实成品（前置 T01696，涉及付费 TTS，需授权）。

用法：backend/.venv/Scripts/python.exe _validate/t01923_ab_package.py
"""
import importlib.util
import json
import os
import random
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

spec = importlib.util.spec_from_file_location(
    "ev", os.path.join(HERE, "t01845_compress_eval.py")
)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

FFMPEG = ev.FFMPEG
SR = ev.SR
SRC = os.path.join(HERE, "t01845_samples", "ep100.mp3")
OUT = os.path.join(HERE, "t01923_ab")
CLIP_SEC = 8.0
SEED = 20261011


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    assert p.returncode == 0, p.stderr[-500:]
    return p


def band_energy_chunks(x, lo, hi, size=2048, hop=512, chunk=2000):
    """分块算 [lo,hi) Hz 的能量占比（整段 STFT 在 597s 上会吃掉几百 MB）。"""
    freqs = np.fft.rfftfreq(size, 1.0 / SR)
    mask = (freqs >= lo) & (freqs < hi)
    tot_mask = freqs > 0
    w = np.hanning(size)
    n = 1 + (len(x) - size) // hop
    ratios = np.full(n, 0.0, dtype=np.float32)
    for s in range(0, n, chunk):
        e = min(n, s + chunk)
        fr = ev.frames(x[s * hop: (e - 1) * hop + size], size, hop)
        sp = np.abs(np.fft.rfft(fr * w, axis=1)) ** 2 + 1e-12
        ratios[s:e] = (sp[:, mask].sum(1) / sp[:, tot_mask].sum(1)).astype(np.float32)
    return ratios, hop


def rms_db(x, size=882, hop=441):
    fr = ev.frames(x, size, hop)
    r = np.sqrt((fr**2).mean(1) + 1e-12)
    return 20 * np.log10(r + 1e-12), hop


def find_transitions(x):
    """衔接点：短促的深谷（段间静音/淡入淡出），谷底两侧都要有实声。"""
    db, hop = rms_db(x)
    floor = np.percentile(db[db > -90], 70)
    cand = []
    i = 20
    while i < len(db) - 20:
        if db[i] < floor - 18:
            j = i
            while j < len(db) - 1 and db[j] < floor - 18:
                j += 1
            before = db[max(0, i - 40): i]
            after = db[j: j + 40]
            if len(before) >= 20 and len(after) >= 20 and before.max() > floor and after.max() > floor:
                cand.append({
                    "t": round((i + j) / 2 * hop / SR, 2),
                    "dip_db": round(float(db[i:j].min()), 1),
                    "span_sec": round((j - i) * hop / SR, 2),
                })
            i = j + 5
        else:
            i += 1
    cand.sort(key=lambda c: c["dip_db"])
    picked = []
    for c in cand:
        if all(abs(c["t"] - p["t"]) > 40 for p in picked):
            picked.append(c)
        if len(picked) == 3:
            break
    return picked


def find_bgm_intro(x):
    """片头 BGM 垫乐段：前 120s 里高频能量占比最高、且持续 ≥2s 的窗口。"""
    lim = int(120 * SR)
    ratios, hop = band_energy_chunks(x[:lim], 3000, 12000)
    win = max(1, int(2.0 * SR / hop))
    if len(ratios) < win:
        return {"t": 0.0, "note": "前 120s 不足 2s 分析窗"}
    roll = np.convolve(ratios, np.ones(win) / win, mode="valid")
    k = int(np.argmax(roll))
    return {"t": round((k + win / 2) * hop / SR, 2), "high_band_ratio": round(float(roll[k]), 4)}


def find_sibilance(x):
    """齿音段：6.5–11kHz 占比高、且整体够响（排除静音与 BGM）的持续窗。"""
    ratios, hop = band_energy_chunks(x, 6500, 11000)
    db, _ = rms_db(x)
    db_f = np.interp(np.arange(len(ratios)) * hop + hop // 2,
                     np.arange(len(db)) * 441 + 441 // 2, db)
    loud = db_f > np.percentile(db_f[db_f > -90], 60)
    win = max(1, int(1.5 * SR / hop))
    scores = np.convolve(ratios * loud, np.ones(win) / win, mode="valid")
    k = int(np.argmax(scores))
    return {"t": round((k + win / 2) * hop / SR, 2), "sibilance_ratio": round(float(scores[k]), 4)}


def write_clip(pcm, start, path, codec="libmp3lame", bitrate="64k", rate=32000, ext="mp3"):
    wav = path + ".src.wav"
    raw = pcm.astype("<f4").tobytes()
    p = subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1",
         "-i", "-", "-af", f"aresample={rate}", "-c:a", "pcm_s16le", wav],
        input=raw, capture_output=True)
    assert p.returncode == 0, p.stderr.decode(errors="replace")[-400:]
    cmd = [FFMPEG, "-y", "-v", "error", "-i", wav, "-c:a", codec, "-ac", "1"]
    if codec == "libmp3lame":
        cmd += ["-b:a", bitrate, "-ar", str(rate)]
    else:
        cmd += ["-b:a", bitrate, "-ar", str(rate)]
    cmd.append(path)
    run(cmd)
    os.remove(wav)


def encode_copy_slice(src, start, dur, path):
    """线上原码流的逐帧拷贝（-c copy）：保持「用户现在听到什么」的原样，不额外加世代。"""
    run([FFMPEG, "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
         "-i", src, "-c", "copy", path])


def objective(published_clip, variant_path):
    cand = ev.decode_mono(variant_path, "")
    mtr = ev.metrics(published_clip, cand)
    # metrics.compared_sec 是「STFT 帧数/SR」且被 round 到 0.1s，8s 短片会显示成 0.0——
    # 直接记分析窗，避免留一个假 0
    del mtr["compared_sec"]
    mtr["analysis_window_sec"] = CLIP_SEC
    return mtr


def main():
    if os.path.isdir(OUT):
        import shutil

        shutil.rmtree(OUT)
    os.makedirs(OUT)
    full = ev.decode_mono(SRC, "")
    print(f"[解码] {len(full)/SR:.1f}s")

    anchors = [
        {"kind": "衔接点", "picks": find_transitions(full)},
        {"kind": "片头BGM垫乐", "info": find_bgm_intro(full)},
        {"kind": "齿音段", "info": find_sibilance(full)},
    ]

    plan = []
    n = 0
    for a in anchors:
        if a["kind"] == "衔接点":
            for p in a["picks"]:
                n += 1
                plan.append({"idx": n, "kind": "衔接点", "start": max(0.0, p["t"] - CLIP_SEC / 2),
                             "anchor": p})
        else:
            n += 1
            t = a["info"]["t"]
            plan.append({"idx": n, "kind": a["kind"], "start": max(0.0, t - CLIP_SEC / 2),
                         "anchor": a["info"]})

    rng = random.Random(SEED)
    results = []
    for item in plan:
        s = item["start"]
        pub_clip = ev.decode_mono(SRC, "", start=s, dur=CLIP_SEC)
        # 电平对齐：把同一源 PCM 先归到线上原码流的 RMS，再编三版，避免「响的听着好」
        ref_rms = float(np.sqrt((pub_clip.astype(np.float64) ** 2).mean() + 1e-12))
        src_pcm = ev.decode_mono(SRC, "", start=s, dur=CLIP_SEC)  # 同一份，用于再编
        src_rms = float(np.sqrt((src_pcm.astype(np.float64) ** 2).mean() + 1e-12))
        src_pcm = src_pcm * (ref_rms / (src_rms + 1e-12))

        base = os.path.join(OUT, f"clip{item['idx']:02d}")
        real = {"published": f"{base}_pub.mp3", "64k44100": f"{base}_r44.mp3",
                "64k32000": f"{base}_r32.mp3"}
        encode_copy_slice(SRC, s, CLIP_SEC, real["published"])
        write_clip(src_pcm, s, real["64k44100"], bitrate="64k", rate=44100)
        write_clip(src_pcm, s, real["64k32000"], bitrate="64k", rate=32000)

        variants = {
            "published": {**ev.probe(real["published"])},
            "64k44100": objective(pub_clip, real["64k44100"]),
            "64k32000": objective(pub_clip, real["64k32000"]),
        }
        for k in ("64k44100", "64k32000"):
            variants[k] = {**ev.probe(real[k]), **variants[k]}

        labels = ["A", "B", "C"]
        rng.shuffle(labels)
        mapping = dict(zip(labels, ["published", "64k44100", "64k32000"]))
        for lab, which in mapping.items():
            src_f, dst_f = real[which], f"{base}_{lab}.mp3"
            with open(src_f, "rb") as f:
                blob = f.read()
            with open(dst_f, "wb") as f:
                f.write(blob)
        os.remove(real["published"])
        os.remove(real["64k44100"])
        os.remove(real["64k32000"])

        results.append({
            "clip": f"clip{item['idx']:02d}",
            "kind": item["kind"],
            "window_sec": [round(s, 2), round(s + CLIP_SEC, 2)],
            "anchor": item["anchor"],
            "blind_mapping": mapping,
            "objective": variants,
        })
        print(f"[盲听包] clip{item['idx']:02d} {item['kind']} @ {s:.1f}s -> A/B/C={mapping}")

    meta = {
        "source_episode": "ep100（已发布，128kbps@44100，597s）",
        "clip_sec": CLIP_SEC,
        "blind_seed": SEED,
        "note": "A/B/C 与版本的对应见 blind_mapping；试听时先看这张表之外的内容，听完再对答案。",
        "caveat": "64k 两版是从已发布成品解码后再编（第二代）；电平已按线上原码流 RMS 对齐。",
        "clips": results,
    }
    with open(os.path.join(OUT, "_blind_key.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[落盘] {OUT}")


if __name__ == "__main__":
    main()
