"""T02029 补充取证：ep58 尾段是「语音」还是「凑时的 BGM」——用声学特征判定。

背景：ep58 稿件仅 481 字（估算 86s），成品却 482s，说明约 396s 不是语音；
但逐 30s 能量剖面显示尾段能量（-30dBFS）与语音段同量级，
所以「尾段是安静的 BGM 尾奏」这一前提需要核实。

判据（不需要耳朵）：
- 过零率 ZCR：语音（含大量清音/摩擦音）显著高于器乐循环
- 包络波动：语音每秒 RMS 的离散度大（语句间停顿），铺底 BGM 平稳
- 短静音占比：语音必有 < -45dBFS 的瞬时停顿，连续 BGM 几乎没有
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.paths import resolve_ffmpeg_path  # noqa: E402

SR = 8000


def load(path: Path) -> np.ndarray:
    raw = subprocess.run(
        [resolve_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-i",
         str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def stats(x: np.ndarray, a: int, b: int) -> dict:
    seg = x[a * SR:b * SR]
    per_sec = np.array([
        20 * np.log10(float(np.sqrt(np.mean(seg[i * SR:(i + 1) * SR] ** 2))) + 1e-9)
        for i in range(len(seg) // SR)
    ])
    zcr = np.mean([
        float(np.count_nonzero(np.diff(np.sign(seg[i * SR:(i + 1) * SR]))))
        for i in range(len(seg) // SR)
    ])
    # 包络自相关：BGM 循环铺底会在循环周期处出现高相关峰，语音包络不会
    env = per_sec - float(np.mean(per_sec))
    norm = float(np.dot(env, env)) or 1.0
    best_lag, best_corr = 0, 0.0
    for lag in range(5, len(env) // 2 + 1):
        c = float(np.dot(env[:-lag], env[lag:])) / norm
        if c > best_corr:
            best_corr, best_lag = c, lag
    return {
        "秒数": len(seg) // SR,
        "平均dBFS": round(float(np.mean(per_sec)), 1),
        "每秒能量标准差": round(float(np.std(per_sec)), 1),
        "过零率均值(次/秒)": int(round(zcr)),
        "低于-45dBFS的秒占比": f"{float(np.mean(per_sec < -45)) * 100:.0f}%",
        "包络自相关峰": f"{best_corr:.2f}@{best_lag}s",
    }


CASES = [
    ("ep58 语音段 0-86s", "t02029_ep58.mp3", 0, 86),
    ("ep58 尾段 400-482s", "t02029_ep58.mp3", 400, 482),
    ("ep100 语音段 0-86s", "t02029_ep100.mp3", 0, 86),
    ("ep100 尾段 515-597s", "t02029_ep100.mp3", 515, 597),
]

cache = {}
print(f"{'样本':<22}{'秒数':>5}{'平均dBFS':>10}{'能量std':>9}{'过零率':>9}"
      f"{'<-45dB占比':>12}{'包络自相关峰':>16}")
for label, fn, a, b in CASES:
    p = ROOT / "_validate" / fn
    if not p.exists():
        continue
    x = cache.setdefault(fn, load(p))
    s = stats(x, a, min(b, len(x) // SR))
    print(f"{label:<22}{s['秒数']:>5}{s['平均dBFS']:>10}{s['每秒能量标准差']:>9}"
          f"{s['过零率均值(次/秒)']:>9}{s['低于-45dBFS的秒占比']:>12}"
          f"{s['包络自相关峰']:>16}")
