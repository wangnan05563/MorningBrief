"""
SimHash 标题去重算法

用途：爬虫模块对素材标题做近似去重，避免不同源转发同一新闻重复爬取。

算法选择理由：相比严格 hash（一字之差判为不同），SimHash 对局部修改不敏感，
相似输入产生相似指纹；通过汉明距离阈值即可判定近似重复，适合 MVP 的 50-100 条标题规模。
"""
import hashlib
from collections import Counter

import jieba

# 64 位 SimHash，对应 16 位十六进制字符串
BITS = 64


def compute(text: str) -> str:
    """计算文本的 SimHash 指纹。

    流程：
    1. jieba 分词，得到词列表
    2. 每个词 MD5 哈希得 64 位整数
    3. 对每一位：该位为 1 则 +词频权重，为 0 则 -词频权重
    4. 累加后每一位 > 0 取 1，否则取 0，得 64 位指纹
    5. 转十六进制字符串返回
    """
    words = jieba.lcut(text)
    if not words:
        return "0" * 16

    # 词频统计：重复词权重更高
    word_weights = Counter(words)

    # 64 个位置的累加器
    accum = [0] * BITS

    for word, weight in word_weights.items():
        # MD5 取前 8 字节 = 64 位
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(BITS):
            if h & (1 << i):
                accum[i] += weight
            else:
                accum[i] -= weight

    # 累加结果符号化 → 64 位指纹
    fingerprint = 0
    for i in range(BITS):
        if accum[i] > 0:
            fingerprint |= (1 << i)

    # 转十六进制字符串（16 字符）
    return f"{fingerprint:016x}"


def hamming_distance(hash1: str, hash2: str) -> int:
    """计算两个 SimHash 指纹的汉明距离。

    异或后统计 1 的个数即为汉明距离。
    """
    n1 = int(hash1, 16)
    n2 = int(hash2, 16)
    return bin(n1 ^ n2).count("1")


def is_similar(hash1: str, hash2: str, threshold: int = 3) -> bool:
    """判断两个指纹是否近似重复。

    64 位 SimHash 经验阈值：汉明距离 ≤ 3 视为相似。
    阈值越小越严格（误判少但漏判多），越大越宽松（漏判少但误判多）。
    MVP 取 3 是业界常用值，对中文新闻标题效果良好。
    """
    return hamming_distance(hash1, hash2) <= threshold
