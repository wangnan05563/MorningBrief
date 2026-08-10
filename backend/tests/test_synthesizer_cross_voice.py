"""交叉音色（段落间轮流换声）分配逻辑单元测试。

assign_cross_voices 为纯函数，不依赖网络/DB，便于稳定验证三策略与回退分支。
"""
import random

from app.workflow.tts.synthesizer import assign_cross_voices


def test_disabled_returns_all_none():
    cfg = {"enabled": False, "strategy": "round_robin", "voices": {"edge": ["a", "b"]}}
    assert assign_cross_voices(5, cfg, "edge") == [None] * 5


def test_less_than_two_voices_returns_all_none():
    cfg = {"enabled": True, "voices": {"edge": ["a"]}}
    assert assign_cross_voices(4, cfg, "edge") == [None] * 4


def test_provider_without_voices_returns_all_none():
    cfg = {"enabled": True, "voices": {"edge": ["a", "b"]}}
    assert assign_cross_voices(4, cfg, "aliyun") == [None] * 4


def test_round_robin_alternates():
    cfg = {"enabled": True, "strategy": "round_robin", "voices": {"edge": ["a", "b", "c"]}}
    plan = assign_cross_voices(7, cfg, "edge")
    assert plan == ["a", "b", "c", "a", "b", "c", "a"]


def test_interval_strategy():
    cfg = {"enabled": True, "strategy": "interval", "interval": 2, "voices": {"edge": ["a", "b"]}}
    plan = assign_cross_voices(6, cfg, "edge")
    # 每 2 段切换：a,a,b,b,a,a
    assert plan == ["a", "a", "b", "b", "a", "a"]


def test_interval_strategy_clamps_minimum():
    cfg = {"enabled": True, "strategy": "interval", "interval": 0, "voices": {"edge": ["a", "b"]}}
    plan = assign_cross_voices(4, cfg, "edge")
    # interval 被 clamp 到 1 -> 每段切换
    assert plan == ["a", "b", "a", "b"]


def test_random_strategy_avoids_adjacent_repeat():
    cfg = {"enabled": True, "strategy": "random", "voices": {"edge": ["a", "b"]}}

    # 固定 random.choice 行为以确定性验证「避免相邻重复」逻辑
    class FakeRandom:
        def choice(self, seq):
            # 调用方已排除 prev，seq 至少 1 个元素；返回首个即得到 a,b,a,b...
            return seq[0]

    import app.workflow.tts.synthesizer as syn

    orig = syn.random
    syn.random = FakeRandom()
    try:
        plan = assign_cross_voices(6, cfg, "edge")
    finally:
        syn.random = orig

    assert plan == ["a", "b", "a", "b", "a", "b"]
    assert all(v in ("a", "b") for v in plan)


def test_piper_single_voice_no_cross():
    # Piper 单说话人模型：音色不足 2 个，回退默认单音色（后端也忽略 voice 参数）
    cfg = {"enabled": True, "voices": {"piper": ["zh_CN-huayan-medium"]}}
    assert assign_cross_voices(3, cfg, "piper") == [None] * 3
