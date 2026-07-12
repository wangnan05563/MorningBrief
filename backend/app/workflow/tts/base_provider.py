"""TTS Provider 抽象基类与统一异常定义。

将原 aliyun_client.py 中的异常类提取到此处，作为所有 TTS provider 共享的
异常层级；新增 TTSProvider 抽象基类定义统一的 synthesize 接口，使上层
synthesizer.py 可通过工厂模式按配置切换具体厂商实现，无需感知底层协议差异。

设计要点：
- 异常分层便于 tenacity 精准判断是否重试：可重试错误继承 TTSError，
  不可重试错误直接抛 TTSError，调用方按需处理
- 抽象接口只规定 synthesize 方法签名，各 provider 自行处理鉴权、协议、
  分片等细节，返回统一的音频二进制
"""
import abc
from typing import Optional


# ===== 异常定义（所有 TTS provider 共享） =====
class TTSError(Exception):
    """TTS 流程兜底异常基类。"""


class TTSRateLimitError(TTSError):
    """API 限流（HTTP 429）或预算超限，退避后重试。"""


class TTSTimeoutError(TTSError):
    """请求超时，重试。"""


class TTSServiceError(TTSError):
    """服务端 5xx 或连接异常，重试。"""


class TTSProviderError(TTSError):
    """Provider 配置错误或不可用（如依赖未安装），不可重试。"""


class TTSProvider(abc.ABC):
    """TTS Provider 抽象基类。

    所有具体厂商实现（阿里云/Edge-TTS/腾讯云等）需继承此类，
    实现 synthesize 方法。上层代码通过 get_tts_provider() 工厂获取实例，
    不直接引用具体类名，实现解耦。
    """

    @abc.abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        format: str = "mp3",
        sample_rate: int = 44100,
    ) -> bytes:
        """合成单段文本为音频二进制。

        Args:
            text: 待合成文本（各 provider 自行处理长度限制，上层已分段）
            voice: 音色 ID，缺省用 provider 默认音色
            format: 输出格式（mp3/wav/pcm），provider 不支持的格式自行降级
            sample_rate: 采样率，provider 不支持的值自行降级

        Returns:
            音频二进制数据

        Raises:
            TTSRateLimitError: 限流/预算超限
            TTSTimeoutError: 超时
            TTSServiceError: 服务异常
            TTSError: 其他失败
        """
        ...

    async def test_connection(self) -> bool:
        """测试连接是否可用（可选实现）。

        默认实现：合成一句测试文本验证 provider 可用性。
        子类可覆写为更轻量的鉴权检查（如阿里云仅创建任务不等待合成）。

        Returns:
            True 表示可用
        """
        try:
            await self.synthesize("测试", format="mp3", sample_rate=16000)
            return True
        except Exception:
            return False
