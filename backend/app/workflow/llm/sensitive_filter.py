"""敏感词过滤模块（LLD 7.3）。

采用 AC 自动机（Aho-Corasick）多模式匹配，O(N) 一次扫描全文命中所有敏感词，
比朴素遍历快几个数量级，适合长文本与高频调用场景。

加载策略：启动时一次性构建自动机并常驻内存，运行时只读查询；词表更新需调 load_words 重建。
"""
import ahocorasick

# 全局自动机：load_words 后填充，contains/find_all/replace 共享只读访问
_automaton = ahocorasick.Automaton()


def load_words(file_path: str) -> None:
    """从敏感词文件加载，构建 AC 自动机。

    文件格式：每行一个敏感词，# 开头为注释行。
    启动时调用一次；词表更新后需重启应用或再次调用本函数 reload。
    重复调用会重建自动机，避免旧词残留。
    """
    global _automaton
    _automaton = ahocorasick.Automaton()
    with open(file_path, encoding="utf-8") as f:
        for idx, line in enumerate(f):
            word = line.strip()
            # 跳过空行与注释行
            if word and not word.startswith("#"):
                _automaton.add_word(word, (idx, word))
    _automaton.make_automaton()


def contains(text: str) -> bool:
    """快速判断文本是否包含任一敏感词。

    命中即返回，无需遍历全部匹配，用于 LLM 改写结果的快速扫描。
    """
    for _ in _automaton.iter(text):
        return True
    return False


def find_all(text: str) -> list[str]:
    """找出文本中所有命中的敏感词。

    用于运营后台展示具体命中内容，便于人工复核与词表维护。
    """
    return [word for _, (_, word) in _automaton.iter(text)]


def replace(text: str, mask: str = "*") -> str:
    """将敏感词替换为掩码字符。

    用于 LLM 二次生成仍命中时的兜底处理：不完美但保证稿件可用，避免流程中断。
    按字符位置替换，保持原文长度便于排版对齐。
    """
    result = list(text)
    for end_idx, (_, word) in _automaton.iter(text):
        start_idx = end_idx - len(word) + 1
        for i in range(start_idx, end_idx + 1):
            # 边界保护：ahocorasick 返回的 end_idx 基于 0 索引，正常情况下不会越界
            if 0 <= i < len(result):
                result[i] = mask
    return "".join(result)
