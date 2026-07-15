"""实测 Edge TTS zh-CN-YunyangNeural 不同 rate 的实际语速。

用已知字数的中文文本合成音频，用 ffprobe 测量时长，反算字/分。
测试 +0%（基准）、+50%（当前配置）两个档位。
"""
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

import edge_tts

# 用项目的 ffprobe 路径解析
sys.path.insert(0, str(Path(__file__).parent))
from app.paths import resolve_ffprobe_path

VOICE = "zh-CN-YunyangNeural"
# 500 字中文测试文本（新闻播报风格，含标点）
TEST_TEXT = (
    "欢迎收听每日新闻早报。今日重点关注国内外财经动态与科技前沿资讯。"
    "英国政府近日公布中小企业融资新政策，旨在通过税收优惠和担保贷款双管齐下，"
    "缓解中小企业融资难题。业内人士分析，该政策将有效降低企业融资成本，"
    "提振市场信心。众擎机器人公司近日就借壳上市传闻发布澄清公告，"
    "否认相关市场传言。公司表示目前经营正常，未进行任何资本运作。"
    "软银集团宣布与人工智能公司 Sierra 开展战略合作，共同推出新一代智能客服系统。"
    "该系统将集成大语言模型技术，为企业提供更高效的客户服务解决方案。"
    "逐际动力公司完成 Pre-IPO 融资，金额近两亿美元。本轮融资由多家知名机构领投，"
    "公司估值大幅提升。美国数据中心开发商借助人工智能热潮实现商业变现，"
    "收入和利润均实现大幅增长。人形机器人公司逐际动力完成两亿美元融资，"
    "估值创行业新高。以上就是今天的全部内容，感谢您的收听，我们明天见。"
)
CHAR_COUNT = len(TEST_TEXT)
print(f"测试文本: {CHAR_COUNT} 字")


async def synthesize(text: str, rate: str, out_path: Path):
    """合成音频并返回时长（秒）。"""
    communicate = edge_tts.Communicate(text, VOICE, rate=rate)
    await communicate.save(str(out_path))


async def main():
    results = {}
    for rate_label, rate_val in [("+0%", "+0%"), ("+50%", "+50%")]:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            out_path = Path(f.name)
        try:
            await synthesize(TEST_TEXT, rate_val, out_path)
            # 用 ffprobe 测时长
            ffprobe = resolve_ffprobe_path()
            proc = subprocess.run(
                [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(out_path)],
                capture_output=True, text=True, timeout=10,
            )
            duration = float(proc.stdout.strip())
            wpm = CHAR_COUNT / duration * 60
            results[rate_label] = {"duration": duration, "wpm": wpm}
            print(f"{rate_label}: 时长={duration:.2f}s 语速={wpm:.1f} 字/分")
        finally:
            out_path.unlink(missing_ok=True)

    # 推算 WORDS_PER_MINUTE（+0% 基准语速）
    base_wpm = results["+0%"]["wpm"]
    print(f"\n===== 校准结论 =====")
    print(f"zh-CN-YunyangNeural +0% 基准语速: {base_wpm:.1f} 字/分")
    print(f"+50% 实际语速: {results['+50%']['wpm']:.1f} 字/分")
    print(f"建议 WORDS_PER_MINUTE = {int(base_wpm)}")
    print(f"\n验证 target=900s rate=+50%:")
    total_words = int(900 * int(base_wpm) * 1.5 / 60)
    actual_dur = total_words / results["+50%"]["wpm"] * 60
    print(f"  计算字数={total_words} 实际时长={actual_dur:.0f}s (目标 900s)")


asyncio.run(main())
