"""Empirical validation of the new '段间静音 truly silent' pipeline.

Mirrors backend/app/workflow/stitch/ffmpeg_wrapper.build_bgm_overlay + the
amix step in concat.py:
  - BGM is sliced per TTS segment (continuous offset, looping),
  - gap_path (pure silence) is inserted between segments,
  - the overlay track is then amix'd with the main audio.

We synthesize: seg durations [2.0, 2.0], gap 1.5s  => main total 5.5s.
Gap region in final audio = [2.0s, 3.5s).

Assertions:
  - RMS in gap region ~ 0 (true silence)
  - RMS in a TTS segment > 0 (audio still present)
"""
import subprocess
import wave
import struct
import math
import os

FF = r"D:\code\otherProjects\20_News\backend\ffmpeg/bin/ffmpeg.exe"
TMP = r"D:\code\otherProjects\20_News\_gaptest"
os.makedirs(TMP, exist_ok=True)


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.decode('utf-8', 'ignore')[-500]}")
    return r


def gen_tone(path, freq, dur, rate=44100):
    run([FF, "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}",
         "-ar", str(rate), "-ac", "1", path])


def gen_silence(path, dur, rate=44100):
    run([FF, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(dur),
         "-ar", str(rate), "-ac", "1", path])


def to_wav(mp3_path, wav_path, rate=44100):
    run([FF, "-y", "-i", mp3_path, "-ar", str(rate), "-ac", "1", wav_path])


def rms_in_region(wav_path, start_s, end_s, rate=44100):
    with wave.open(wav_path, "rb") as w:
        fr = w.getframerate()
        n = w.getnframes()
        width = w.getsampwidth()
        start_f = int(start_s * fr)
        end_f = min(int(end_s * fr), n)
        w.setpos(start_f)
        data = w.readframes(end_f - start_f)
    fmt = "<" + ("h" if width == 2 else "b") * (len(data) // width)
    samples = struct.unpack(fmt, data)
    if not samples:
        return 0.0
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    # normalize by max int for width
    maxv = (1 << (width * 8 - 1)) - 1
    return rms / maxv


def concat_demuxer(paths, out_path):
    list_path = out_path + ".list.txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    run([FF, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
         "-c:a", "libmp3lame", "-b:a", "64k", "-ar", "44100", "-ac", "1", out_path])


# ---- inputs ----
bgm = os.path.join(TMP, "v_bgm.mp3")          # 6s BGM loop (440Hz)
seg1 = os.path.join(TMP, "v_seg1.mp3")         # 2s speech-ish (200Hz)
seg2 = os.path.join(TMP, "v_seg2.mp3")         # 2s speech-ish (200Hz)
gap = os.path.join(TMP, "v_gap.mp3")           # 1.5s silence
gen_tone(bgm, 440, 6.0)
gen_tone(seg1, 200, 2.0)
gen_tone(seg2, 200, 2.0)
gen_silence(gap, 1.5)

# ---- main audio: seg1 + gap + seg2 ----
main = os.path.join(TMP, "v_main.mp3")
concat_demuxer([seg1, gap, seg2], main)

# ---- build_bgm_overlay equivalent ----
bgm_len = 6.0
seg_durations = [2.0, 2.0]
offset = 0.0
volume = 0.15
parts = []
for i, dur in enumerate(seg_durations):
    start = offset % bgm_len
    sp = os.path.join(TMP, f"v_bgm_slice_{i}.mp3")
    run([FF, "-y", "-stream_loop", "-1", "-ss", f"{start:.3f}", "-i", bgm,
         "-t", f"{dur:.3f}", "-af", f"volume={volume}",
         "-c:a", "libmp3lame", "-b:a", "64k", "-ar", "44100", "-ac", "1", sp])
    parts.append(sp)
    if i < len(seg_durations) - 1:
        parts.append(gap)
    offset += dur
overlay = os.path.join(TMP, "v_overlay.mp3")
concat_demuxer(parts, overlay)

# ---- amix main + overlay (concat.py 3.5) ----
final = os.path.join(TMP, "v_final.mp3")
run([FF, "-y", "-i", main, "-i", overlay,
     "-filter_complex", "amix=inputs=2:duration=first",
     "-c:a", "libmp3lame", "-b:a", "64k", "-ar", "44100", "-ac", "1", final])

# ---- measure ----
to_wav(final, os.path.join(TMP, "v_final.wav"))
to_wav(overlay, os.path.join(TMP, "v_overlay.wav"))

gap_rms = rms_in_region(os.path.join(TMP, "v_final.wav"), 2.0, 3.5)
seg_rms = rms_in_region(os.path.join(TMP, "v_final.wav"), 0.0, 2.0)
overlay_gap_rms = rms_in_region(os.path.join(TMP, "v_overlay.wav"), 2.0, 3.5)

print(f"final gap-region RMS (expect ~0)   : {gap_rms:.6f}")
print(f"final TTS-seg RMS   (expect > 0)   : {seg_rms:.6f}")
print(f"overlay gap-region RMS (expect ~0) : {overlay_gap_rms:.6f}")

ok = gap_rms < 1e-4 and seg_rms > 1e-3 and overlay_gap_rms < 1e-4
print("RESULT:", "PASS" if ok else "FAIL")
