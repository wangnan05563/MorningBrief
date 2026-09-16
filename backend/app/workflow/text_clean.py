"""TTS/稿件文本清洗（共享模块）。

背景：LLM 改写偶发违反「禁止输出 Markdown 标记」约束，在 content 中残留
Markdown 符号与超链接。TTS 朗读时会念出「星号星号」「井号」「方括号」，
或直接把 URL 逐字符读出，严重影响听感。

本模块是**共享真相源**：
- workflow/llm/rewriter.py 在解析 LLM 输出后调用（源头清洗）；
- workflow/tts/synthesizer.py 在 synthesize_segment 入口调用（最后一道防线，
  覆盖历史脏数据与任何绕过 rewriter 的写入路径）。

清理范围（仅清理已知模式，不破坏正文标点与数学表达）：
- Markdown 超链接 [text](url) → 保留 text；空 text 的链接整段移除
- 引用式链接 [text][ref] → 保留 text
- 图片 ![alt](url) → 整段移除（alt 非播报内容）
- 裸 URL（http:// / https:// / www.）→ 移除（TTS 无法朗读且必为噪声）
- 代码围栏 ``` 块 → 整块移除（代码不可播报）
- 行内反引号 `xxx` → 移除反引号保留内容
- HTML 标签 <tag> → 移除标签保留内部文本
- 行首 # / ## / ### 等标题符号 + 空格 → 移除符号保留标题文字
- 行首列表符号（* / - / + 后跟空格）→ 移除标记保留正文
- 行首 blockquote（> 后跟空格）→ 移除标记保留正文
- 表格管道符 | 与分隔行（|---|---|）→ 移除/整行移除
- 水平线（--- / *** / ___ 整行）→ 整行移除
- **xxx** / __xxx__ / *xxx* / _xxx_ 强调 → 移除分隔符保留内部文字
- 星号**变体**（T00627）：全角 ＊ / ﹡ / ∗ / ⁎ 与装饰星 ✱✳✻✽❋、参考标记 ※ → 一律清除
  （TTS 会念「星号」；实测脏数据形态如「根据＊＊数据」「、＊组织奖」）
- 零宽字符（ZWSP/ZWNJ/ZWJ/BOM）→ 移除（不可见但破坏成对标记配对、干扰断句）
- 孤立的 ** / * / ` → 直接移除
- 数学乘号保护：两侧均为数字/字母的 * 视为乘号保留（1*2*3、a*b、3 * 4）
"""
import re


def strip_markdown_residue(text: str) -> str:
    """清洗文本中残留的 Markdown 标记与超链接，返回可直接送 TTS 的纯文本。

    幂等：对已干净的文本重复调用无副作用。
    """
    if not text:
        return text

    # 1. 代码围栏 ```xxx``` 整块移除（含语言标注行）；未闭合围栏也一并处理
    text = re.sub(r"```[^\n]*\n?.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"```[^\n]*\n?.*$", "", text, flags=re.DOTALL)

    # 2. 图片 ![alt](url) 整段移除（alt 非播报内容）
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)

    # 3. 引用式链接 [text][ref] → 保留 text
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)

    # 4. 行内链接 [text](url) → 保留 text；空 text 的链接整段移除
    text = re.sub(r"\[\s*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)

    # 5. 裸 URL（http/https/www 开头）：到空白/右括号/中文标点/中文字符为止，
    #    避免无空格分隔时把后面的中文正文一起吞掉。
    #    注意：ASCII 的 ? & = 等是合法 URL 字符不可排除，只排全角标点。
    text = re.sub(
        r"(?:https?://|www\.)[^\s)\n]"
        r"[^\s)\n\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef）】」』，。；！？]*",
        "", text)

    # 6. HTML 标签 → 移除标签保留内部文本
    text = re.sub(r"</?[A-Za-z][^>\n]*>", "", text)

    # 7. 行内反引号：成对移除分隔符保留内容，孤立的反引号直接删
    text = re.sub(r"`([^`\n]+?)`", r"\1", text)
    text = text.replace("`", "")

    # 8. 行首标题符号（# / ## / ### 后跟空格）
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # 9. 行首 blockquote（> 后跟空格）
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)

    # 10. 表格分隔行（| --- | --- | 或 --- --- 整行）整行移除
    text = re.sub(r"^\s*\|?(?:\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?\s*$",
                  "", text, flags=re.MULTILINE)
    # 表格剩余管道符 → 替换为空格（避免「标题|标题」被连读）；
    # 仅限同行匹配（[ \t] 而非 \s），避免跨行把整段表格拼成一行
    text = re.sub(r"[ \t]*\|[ \t]*", " ", text)

    # 11. 水平线整行移除（--- / *** / ___ 及其空格变体）
    text = re.sub(r"^\s*(?:[-*_]\s*){3,}$", "", text, flags=re.MULTILINE)

    # 12. 先清理闭合的 **xxx**（避免被未闭合规则误伤）
    text = re.sub(r"\*\*([^*]+?)\*\*", r"\1", text)
    # 清理未闭合的 **xxx（行内剩余的开头 **）
    text = re.sub(r"\*\*([^*\n]+)", r"\1", text)
    # 清理孤立的 **（未成对出现）
    text = text.replace("**", "")

    # 13. 行首列表符号（* / - / + 后跟空格）→ 仅移除标记保留正文
    text = re.sub(r"^\s*[\*\-\+]\s+", "", text, flags=re.MULTILINE)

    # 14. 单星号 * 处理（数学安全策略）：
    # 1. 先保护"数学乘号"（两侧均为数字/字母，允许中间空格，如 1*2*3 / 3 * 4 / a*b），
    #    用占位符暂存，避免被后续清理误删。
    #    注：不能用 \w 边界判断——Python \w 在 Unicode 模式下含汉字，会导致中文后的
    #    斜体 * 因"其后为汉字"而被判定为边界外而不匹配，斜体清理整体失效。
    # 2. 成对斜体分隔符 *文字* / _文字_ → 移除分隔符保留内部文字。
    # 3. 清理剩余孤立单个 *（未成对残留 / LLM 噪声），数学乘号已用占位符保护不受影响。
    # 4. 恢复数学乘号占位符。
    def replace_math(match):
        return match.group(1) + match.group(2) + _math_ph + match.group(3)

    _math_asterisk = re.compile(r"([0-9A-Za-z])(\s*)\*(\s*)(?=[0-9A-Za-z])")
    # 用私有区字符作占位符（正常文本绝不会出现），避免与正文冲突
    _math_ph = ""
    text = _math_asterisk.sub(replace_math, text)
    text = re.sub(r"([*_])([^*\n_]+?)\1", r"\2", text)
    text = text.replace("*", "")
    text = text.replace(_math_ph, "*")

    # 16. 星号/标记**变体**（T00627 实测补充）：全角与装饰性星号此前完全未覆盖，
    #     TTS 会念出「星号」。真实脏数据形态（8 月稿实测）：残缺标记粘连中文，
    #     如「根据＊＊数据」「、＊组织奖」「＊可达500万元」——左右各清理一次，
    #     先把成对强调还原为内部文字，再清除全部残留。
    #     覆盖：全角 ＊(U+FF0A) / 小号﹡(U+FE61) / 数学 ∗(U+2217) / ⁎(U+204E)
    #          装饰星 ✱(U+2731) ✳(U+2733) ✻(U+273B) ✽(U+273D) ❋(U+274B)
    #          参考标记 ※(U+203B)
    _VARIANT_MARKS = "＊﹡∗⁎✱✳✻✽❋"
    text = re.sub(rf"[{_VARIANT_MARKS}]([^{_VARIANT_MARKS}\n]+?)[{_VARIANT_MARKS}]", r"\1", text)
    text = re.sub(rf"[{_VARIANT_MARKS}]+", "", text)
    text = text.replace("※", "")

    # 17. 零宽字符（ZWSP/ZWNJ/ZWJ/WORD-JOINER/BOM）：不可见却会破坏成对标记的
    #     正则配对、干扰 TTS 断句（表现为莫名停顿），一律移除
    text = re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", text)

    # 18. 收尾：把清理产生的连续空行/多余空白压平（清洗残骸不应留出空洞）
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 清理每行行尾/行首残留空格（表格管道/围栏移除后的残骸）
    text = re.sub(r"[ \t]+(?=\n)", "", text)
    text = re.sub(r"(?<=\n)[ \t]+", "", text)
    # URL/链接删除后残留的空括号一并清掉（避免被念成「括号括号」）
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"（\s*）", "", text)
    return text.strip()
