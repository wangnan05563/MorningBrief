"""LRUDict 容量上限字典测试。

覆盖：
- 基本读写与 dict 接口兼容性
- 容量超限驱逐最旧条目（队首）
- 命中后顺序更新（LRU 语义）
- .get() 走 __getitem__ 维护顺序
- 边界：maxsize=1 / maxsize<=0 兜底为 1
"""
import pytest

from app.core.lru import LRUDict


def test_basic_set_get():
    """基本写入读取，与 dict 接口兼容。"""
    d = LRUDict(maxsize=10)
    d["a"] = 1
    d["b"] = 2
    assert d["a"] == 1
    assert d["b"] == 2
    assert "a" in d
    assert len(d) == 2


def test_evict_oldest_when_exceed_maxsize():
    """超容量驱逐最旧条目（队首）。"""
    d = LRUDict(maxsize=3)
    d["a"] = 1
    d["b"] = 2
    d["c"] = 3
    # 插入第 4 个应驱逐 a（最久未访问）
    d["d"] = 4
    assert "a" not in d
    assert d["b"] == 2
    assert d["c"] == 3
    assert d["d"] == 4
    assert len(d) == 3


def test_get_updates_order():
    """.get() 命中后提到队尾，避免驱逐刚访问的条目。"""
    d = LRUDict(maxsize=3)
    d["a"] = 1
    d["b"] = 2
    d["c"] = 3
    # 访问 a，应提到队尾
    _ = d.get("a")
    # 插入 d，应驱逐 b（现在最旧）而非 a
    d["d"] = 4
    assert "a" in d
    assert "b" not in d


def test_getitem_updates_order():
    """__getitem__ 命中后提到队尾。"""
    d = LRUDict(maxsize=2)
    d["a"] = 1
    d["b"] = 2
    # 访问 a
    _ = d["a"]
    # 插入 c，应驱逐 b
    d["c"] = 3
    assert "a" in d
    assert "b" not in d


def test_set_existing_key_moves_to_end():
    """已存在 key 重新赋值应提到队尾。"""
    d = LRUDict(maxsize=2)
    d["a"] = 1
    d["b"] = 2
    d["a"] = 10  # 更新 a
    # 插入 c，应驱逐 b（最旧）
    d["c"] = 3
    assert d["a"] == 10
    assert "b" not in d


def test_get_returns_default_on_miss():
    """未命中返回 default。"""
    d = LRUDict(maxsize=10)
    d["a"] = 1
    assert d.get("missing") is None
    assert d.get("missing", "fallback") == "fallback"


def test_maxsize_minimum_one():
    """maxsize <= 0 兜底为 1，避免 popitem 抛 KeyError。"""
    d = LRUDict(maxsize=0)
    assert d.maxsize == 1
    d["a"] = 1
    d["b"] = 2  # 应驱逐 a
    assert "a" not in d
    assert d["b"] == 2


def test_clear_resets():
    """clear() 清空字典。"""
    d = LRUDict(maxsize=10)
    d["a"] = 1
    d.clear()
    assert len(d) == 0
    assert "a" not in d


def test_dict_compatibility():
    """作为 dict 子类，items/values/keys 等方法可用。"""
    d = LRUDict(maxsize=10)
    d["a"] = 1
    d["b"] = 2
    assert set(d.keys()) == {"a", "b"}
    assert set(d.values()) == {1, 2}
    assert dict(d.items()) == {"a": 1, "b": 2}
