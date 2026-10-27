"""关键词白名单的长度护栏（T02604，裁决方案1）。

匹配口径是大小写不敏感的**子串包含**，所以过短的关键词等于大面积放行。
本模块的两个下限不是拍的，是在同一批真实历史稿件（`script.full_text` 83 篇，
只读取证 `_validate/news2/measure_T02604_v2.py`）上量出来的：

| 关键词 | 长度 | 子串命中篇数 | 其中「整篇没有一次独立出现」 |
| --- | --- | --- | --- |
| 中 / 国 / 了 | 1 汉字 | 82 / 81 / 82（≈98%） | —— 汉字没有词边界可言，见下 |
| EA / OK / OS | 2 字母 | 15 / 12 / 14 | 15 / 12 / 12（全部内嵌） |
| AI / PS / PC | 2 字母 | 37 / 15 / 13 | 1 / 9 / 4（AI 靠 2 字母放行 44.6% 的稿件） |
| 游戏 / 科技 | 2 汉字 | 20 / 40 | 有效粒度，运营正常用法 |
| iOS / NBA / PS5 / CEO | 3 字母 | 2 / 1 / 8 / 3 | 0 / 0 / 0 / 0 |
| APP / RPG / GPT | 3 字母 | 8 / 4 / 3 | 2 / 1 / 1 |

两条结论决定阈值取 2 / 3：

1. **汉字侧只看长度**：中文没有词边界概念，「前后不许接汉字」那种伪边界会把
   中文白名单整体作废（游戏 20→0、科技 40→1），所以不能靠改匹配方式救单字词，
   只能在录入侧拦；两字词（游戏/科技/时政）是运营的正常使用粒度，不动它 → 下限 2。
2. **英文侧的灾难集中在 2 字母**：EA/OK 的子串命中 100% 是内嵌（air、Coupella 一类），
   而 3 字母词的内嵌极少（PS5/CEO/iOS 为 0）—— 3 字母已经能当白名单用，
   取 4 会连 PS5、CEO 这类干净词一起拦掉，没有数据支持 → 下限 3。

裁决只批了「拦住过短关键词」，判定口径一个字都没动：存量短词仍按子串命中，
下一次保存时被点名删掉即可（不静默改判定，免得现有白名单突然全部不命中）。

判定只在这里写一份：下限常量由 `GET /admin/api/v1/auto-review/config` 的
`keyword_limits` 下发给管理端，界面据此即时提示，不各写一套数字。
"""

# 含非 ASCII 字符（中日韩等）的关键词下限：单字词在真实语料里命中 98% 的稿件
MIN_LENGTH_NON_ASCII = 2
# 纯 ASCII 关键词下限：2 字母缩写几乎必然内嵌在更长的词里，3 字母起才干净
MIN_LENGTH_ASCII = 3


def min_length(keyword: str) -> int:
    return MIN_LENGTH_ASCII if keyword.isascii() else MIN_LENGTH_NON_ASCII


def too_short(keyword: str) -> bool:
    return len(keyword) < min_length(keyword)


def find_too_short(keywords) -> list[str]:
    return [kw for kw in keywords if too_short(kw)]


def limits_payload() -> dict:
    """下发给前端的阈值，字段名与本模块常量同名语义，避免界面自己猜。"""
    return {
        "min_length": MIN_LENGTH_NON_ASCII,
        "ascii_min_length": MIN_LENGTH_ASCII,
        "rule": "substring",
    }


def reject_message(keywords) -> str:
    """拦住过短关键词时给管理员的那句话——口径、阈值依据和出路都在一句里。"""
    words = "、".join(f"「{k}」" for k in keywords)
    ascii_only = all(k.isascii() for k in keywords)
    limit_text = (
        f"纯英文词至少 {MIN_LENGTH_ASCII} 个字母" if ascii_only
        else f"至少 {MIN_LENGTH_NON_ASCII} 个字（纯英文词至少 {MIN_LENGTH_ASCII} 个字母）"
    )
    return (
        f"关键词{words} 太短：白名单按子串包含匹配，{limit_text}。"
        "实测单字汉字在 83 篇历史稿件里命中 82 篇、两字母英文词（EA/OK）的子串命中全部是内嵌误命中，"
        "过短等于大面积放行。请删除该词或改成更具体的表述。"
    )
