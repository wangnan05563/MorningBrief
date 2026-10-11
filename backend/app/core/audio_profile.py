"""音频档位（码率 + 采样率套餐）的共享真相源。

为什么收敛成「档位套餐」而不是两个独立参数：
MP3 的音质由「码率 × 采样率」共同决定，两者错配会同时踩坑——
- 码率给 64k 却把采样率留 44.1k：编码器把预算拿去描述 10kHz 以上根本不存在的内容
  （TTS 源只有 24kHz，上采样到 44.1k 后 12kHz 以上实测 -33dBFS 以下），有效频带反而变差；
- 码率给 48k 又拉到 44.1k：高频截止直接掉到 6kHz 出头，出现任务侧禁止的「高频截断感」。
T01845 实测（ep100 同素材）：64k@44.1k segSNR 23.86dB，同码率降到 32k 反而 24.77dB；
24k 档在 ep99 上 27.48dB 优于 44.1k 的 25.27dB。故降采样率不是妥协，是提质。

档位取值：
- quality  = 96k @ 44100：接近透明，留给「音质优先、体积不敏感」的频道；
- standard = 64k @ 32000：默认档，同码率下比 44.1k 更干净，PCM 中间态体积同步降 26%；
- lean     = 48k @ 32000：弱网/流量敏感场景，实测仍高于旧 128k@44.1k 的听感基线。

采样率一律取 MPEG-1 Layer III 合法值（32000 / 44100），不取 24000：24kHz 属
MPEG-2 Layer III（LSF）范畴，微信内置播放器/部分 Android 解包器对其支持参差，
真机兼容未实测前不进入默认链路（T01871 任务项 3）。
"""
from dataclasses import dataclass

# 档位定义（顺序即管理端展示顺序）
AUDIO_PROFILES: dict[str, dict] = {
    "quality": {"label": "高音质", "bitrate": "96k", "sample_rate": 44100},
    "standard": {"label": "标准", "bitrate": "64k", "sample_rate": 32000},
    "lean": {"label": "省流", "bitrate": "48k", "sample_rate": 32000},
}

DEFAULT_AUDIO_PROFILE = "standard"


def normalize_profile(raw: object) -> str:
    """非法/空值回退默认档：与 gap mode 同口径，展示层枚举不该让整期节目失败。"""
    if raw is None:
        return DEFAULT_AUDIO_PROFILE
    profile = str(raw).strip().lower()
    return profile if profile in AUDIO_PROFILES else DEFAULT_AUDIO_PROFILE


@dataclass(frozen=True)
class AudioEncoding:
    """当前生效的编码参数。

    `overridden` 表示运营用 AUDIO_BITRATE / AUDIO_SAMPLE_RATE 显式覆盖了档位里的值，
    管理端要如实显示「自定义」，否则看到的档位名会与实际参数不符。
    """

    profile: str
    label: str
    bitrate: str
    sample_rate: int
    overridden: bool

    @property
    def pcm_kb_per_sec(self) -> int:
        """PCM 中间态落盘速率（KB/s，十进制），用于估算拼接临时目录峰值占用。"""
        return self.sample_rate * 2 // 1000


def resolve_encoding(settings) -> AudioEncoding:
    """把「档位 + 两个可选覆盖项」解析成实际生效的一组参数。"""
    profile = normalize_profile(getattr(settings, "AUDIO_PROFILE", None))
    base = AUDIO_PROFILES[profile]
    bitrate_cfg = str(getattr(settings, "AUDIO_BITRATE", "") or "").strip()
    rate_cfg = int(getattr(settings, "AUDIO_SAMPLE_RATE", 0) or 0)
    bitrate = bitrate_cfg or base["bitrate"]
    sample_rate = rate_cfg or base["sample_rate"]
    return AudioEncoding(
        profile=profile,
        label=base["label"],
        bitrate=bitrate,
        sample_rate=sample_rate,
        overridden=bool(bitrate_cfg or rate_cfg),
    )
