"""TTS 文本清洗（超链接/URL/Markdown 残留）回归测试。

背景（用户反馈）：语音合成出现语音中包含 md 格式符号和超链接符号——
LLM 改写残留的 [标题](url)、https://... 被逐字念出（「方括号」「http」）。

共享实现：app/workflow/text_clean.strip_markdown_residue
（rewriter 源头清洗 + synthesizer TTS 入口防线共用）。
"""
from app.workflow.text_clean import strip_markdown_residue
from app.workflow.llm.rewriter import _strip_markdown_residue


class TestLinkCleanup:
    """超链接与 URL 清理（本次新增能力）。"""

    def test_inline_link_keeps_text(self):
        """[text](url) → 保留 text，URL 不得出现在结果中。"""
        assert strip_markdown_residue("详情见[官网](https://example.com/a?b=1)报道") == "详情见官网报道"

    def test_empty_link_removed(self):
        """空 text 的链接 [](url) → 整段移除。"""
        assert strip_markdown_residue("前文[](https://example.com)后文") == "前文后文"

    def test_reference_link_keeps_text(self):
        """引用式链接 [text][ref] → 保留 text。"""
        assert strip_markdown_residue("参考[维基百科][1]条目") == "参考维基百科条目"

    def test_image_removed_entirely(self):
        """图片 ![alt](url) → 整段移除。"""
        assert strip_markdown_residue("看图![截图](https://img.example.com/x.png)说明") == "看图说明"

    def test_bare_https_url_removed(self):
        """裸 https URL → 移除，不留痕。"""
        assert strip_markdown_residue("访问 https://news.example.com/path?q=1 了解更多") == "访问 了解更多"

    def test_bare_www_url_removed(self):
        """裸 www URL → 移除。"""
        assert strip_markdown_residue("官网 www.example.com.cn 欢迎访问") == "官网 欢迎访问"

    def test_url_stops_at_fullwidth_punct(self):
        """URL 后跟中文标点 → 只删 URL 不吞标点。"""
        assert strip_markdown_residue("见 https://example.com/a，更多请关注") == "见 ，更多请关注"

    def test_url_in_parens_no_leftover(self):
        """(https://x) 删 URL 后残留空括号也被清掉。"""
        assert strip_markdown_residue("来源（https://example.com）报道") == "来源报道"

    def test_url_stops_at_chinese_char_boundary(self):
        """URL 紧跟中文（无空格分隔）→ URL 整体删除、中文保留。"""
        assert strip_markdown_residue("详情https://t.cn/abc123请看") == "详情请看"


class TestMarkdownResidueExtended:
    """Markdown 其他残留清理（代码围栏/反引号/引用/表格/HTML）。"""

    def test_code_fence_removed(self):
        """``` 围栏代码块 → 整块移除（留段落空行，对 TTS 无影响）。"""
        text = "讲解开始\n```python\nprint('hi')\n```\n讲解结束"
        assert strip_markdown_residue(text) == "讲解开始\n\n讲解结束"

    def test_unclosed_code_fence_removed(self):
        """未闭合 ``` 围栏 → 到文末全部移除。"""
        text = "正文\n```js\nvar x = 1;"
        assert strip_markdown_residue(text) == "正文"

    def test_inline_code_backticks(self):
        """行内 `code` → 移除反引号保留内容。"""
        assert strip_markdown_residue("运行 `npm test` 即可") == "运行 npm test 即可"

    def test_blockquote_marker(self):
        """行首 > 引用 → 移除标记保留正文。"""
        assert strip_markdown_residue("> 引用的一句话") == "引用的一句话"

    def test_table_pipe_and_separator(self):
        """表格分隔行整行移除，剩余管道符替换为空格且不跨行拼接。"""
        text = "| 列A | 列B |\n| --- | --- |\n| 甲 | 乙 |"
        assert strip_markdown_residue(text) == "列A 列B\n\n甲 乙"

    def test_horizontal_rule_removed(self):
        """整行 --- / *** 水平线 → 移除（留段落空行，对 TTS 无影响）。"""
        assert strip_markdown_residue("上段\n---\n下段") == "上段\n\n下段"

    def test_html_tag_stripped(self):
        """HTML 标签 → 移除标签保留内部文本。"""
        assert strip_markdown_residue("这是<b>加粗</b>文字") == "这是加粗文字"

    def test_hash_markdown_link_with_bold(self):
        """混合残留：# 标题 + ** 加粗 + 链接 同段清理。"""
        text = "# 今日要闻\n**重大突破**：详见[报道](https://x.com/1)。"
        assert strip_markdown_residue(text) == "今日要闻\n重大突破：详见报道。"


class TestCompatibility:
    """与旧行为的兼容性（rewriter 既有测试语义）。"""

    def test_rewriter_delegate_equivalent(self):
        """rewriter._strip_markdown_residue 与共享实现行为一致。"""
        cases = [
            "**重要消息**",
            "**101亿人民币收购SuperPlay",
            "# 标题\n正文",
            "* 要点",
            "计算 1*2*3=6 的结果",
            "*重要*消息来了",
        ]
        for c in cases:
            assert _strip_markdown_residue(c) == strip_markdown_residue(c)

    def test_math_asterisk_preserved(self):
        """数学乘号保护仍然生效（占位符为 U+E000 私有区字符）。"""
        assert strip_markdown_residue("计算 1*2*3=6 的结果") == "计算 1*2*3=6 的结果"
        assert strip_markdown_residue("面积 3 * 4=12") == "面积 3 * 4=12"

    def test_plain_text_unchanged(self):
        """纯文本零改动（幂等前提）。"""
        text = "这是一段正常的播报文本，包含标点、数字123与English。"
        assert strip_markdown_residue(text) == text

    def test_idempotent(self):
        """幂等：清洗结果再清洗一次不变。"""
        text = "# 标题\n**加粗**与[链接](https://a.com)及 https://b.com 混合"
        once = strip_markdown_residue(text)
        assert strip_markdown_residue(once) == once

    def test_empty_and_none_like(self):
        """空字符串安全。"""
        assert strip_markdown_residue("") == ""
