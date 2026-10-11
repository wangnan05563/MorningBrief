"""T02029 ep58「凑时尾段」客观取证：逐 30s 能量剖面定位语音结束点。

任务正文要求真机听「ep58 结尾那段 BGM 尾奏听感是否可接受」。听感交回人工，
但「尾段到底是不是几乎没有语音」可以量化：成品 482s、稿件估算 86s，
若语音在 ~86s 后就停止、剩余全是低能量 BGM/静音，则 396s 是凑出来的。
对照组 ep100（597s，正常一期）证明同一口径下语音应持续到接近结尾。

只读：从 COS GET 成品文件，不改任何数据。
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.paths import resolve_ffmpeg_path  # noqa: E402

SR = 8000
BUCKET = 30  # 秒


def load_pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(
        [resolve_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-i",
         str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def profile(path: Path) -> tuple[list[float], int]:
    x = load_pcm(path)
    total = len(x) / SR
    per_sec = np.array([
        20 * np.log10(float(np.sqrt(np.mean(x[i * SR:(i + 1) * SR] ** 2))) + 1e-9)
        for i in range(int(total))
    ])
    buckets = [float(np.mean(per_sec[i:i + BUCKET]))
               for i in range(0, len(per_sec), BUCKET)]
    # 语音段基准：前 3 个桶的最大均值；语音结束点 = 最后一个 >= 基准-10dB 的桶
    base = max(buckets[:3])
    speech_last = max(
        (i for i, v in enumerate(buckets) if v >= base - 10), default=0)
    return buckets, (speech_last + 1) * BUCKET, total


for label, fn in (("ep58", "t02029_ep58.mp3"), ("ep100", "t02029_ep100.mp3")):
    p = ROOT / "_validate" / fn
    if not p.exists():
        print(f"{label}: 文件缺失，跳过")
        continue
    buckets, speech_end, total = profile(p)
    print(f"\n### {label} 总时长 {total:.0f}s  逐 30s 平均能量(dBFS)")
    print("  " + "  ".join(f"{i * BUCKET:>3}:{v:>6.1f}"
                           for i, v in enumerate(buckets)))
    print(f"  能量基准(前3桶最大)={max(buckets[:3]):.1f}dB  "
          f"→ 语音持续到约 {speech_end}s，其后 {total - speech_end:.0f}s 为低能量尾段")
