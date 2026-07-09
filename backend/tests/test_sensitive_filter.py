"""敏感词过滤测试。

覆盖 workflow/llm/sensitive_filter.py：
- load_words：从文件加载敏感词，重建 AC 自动机
- contains：包含敏感词返回 True
- find_all：找出全部命中词
- replace：敏感词替换为掩码字符
- 大小写敏感（当前实现不做大小写归一化）
"""
import pytest

from app.workflow.llm import sensitive_filter


@pytest.fixture
def loaded_filter(tmp_path):
    """每个测试加载独立的敏感词表，避免模块级单例状态污染。

    tmp_path 是 pytest 内置 fixture，每个测试函数独立临时目录。
    """
    words = ["暴力", "色情", "违禁品"]
    # 文件格式：每行一个敏感词，# 开头为注释
    words_file = tmp_path / "words.txt"
    words_file.write_text(
        "# 敏感词测试文件\n" + "\n".join(words) + "\n",
        encoding="utf-8",
    )
    sensitive_filter.load_words(str(words_file))
    return words


def test_load_words_builds_automaton(loaded_filter):
    """load_words 后自动机应构建成功，contains 可正常调用不报错。"""
    # 加载后对包含敏感词的文本应能命中
    assert sensitive_filter.contains("包含暴力的内容") is True


def test_contains_returns_true(loaded_filter):
    """包含任一敏感词返回 True。"""
    assert sensitive_filter.contains("这里有暴力镜头") is True
    assert sensitive_filter.contains("涉及色情的描述") is True
    assert sensitive_filter.contains("违禁品禁止流通") is True


def test_contains_returns_false(loaded_filter):
    """不含敏感词返回 False。"""
    assert sensitive_filter.contains("正常的新闻内容") is False
    assert sensitive_filter.contains("") is False


def test_find_all_returns_all_hits(loaded_filter):
    """find_all 返回文本中所有命中的敏感词。"""
    text = "暴力与色情同时出现，还有违禁品"
    hits = sensitive_filter.find_all(text)
    # 三个敏感词都应被找出（顺序由位置决定）
    assert "暴力" in hits
    assert "色情" in hits
    assert "违禁品" in hits
    assert len(hits) == 3


def test_replace_masks_sensitive_words(loaded_filter):
    """replace 将敏感词字符替换为掩码字符，保持原文长度。"""
    text = "暴力内容"
    result = sensitive_filter.replace(text, mask="*")
    # "暴力" 两字被替换为 **
    assert result == "**内容"
    assert len(result) == len(text)


def test_replace_all_occurrences(loaded_filter):
    """replace 替换所有出现的敏感词。"""
    text = "暴力与色情"
    result = sensitive_filter.replace(text, mask="*")
    assert result == "**与**"


def test_replace_no_hit_unchanged(loaded_filter):
    """无敏感词时 replace 返回原文。"""
    text = "正常文本"
    assert sensitive_filter.replace(text) == text


def test_case_sensitive_default(loaded_filter):
    """当前实现不做大小写归一化：大小写不同的词不会被命中。

    验证现状：sensitive_filter 未实现大小写不敏感，此处断言该行为以锁定期望。
    """
    # 加载一个英文敏感词
    import tempfile, os
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("BadWord\n")
        f.flush()
        tmp_file = f.name
    try:
        sensitive_filter.load_words(tmp_file)
        # 大小写敏感：小写形式不应命中
        assert sensitive_filter.contains("this is a badword here") is False
        # 完全匹配才命中
        assert sensitive_filter.contains("this is BadWord here") is True
    finally:
        os.unlink(tmp_file)
