"""rewriter Markdown 残留清洗回归测试。

回归场景：wf-20260727-0011（channel_id=9 游戏咨询）生成的 script 中
出现 2 处 Markdown 残留：
- `**同时在线突破1.6万`（未闭合 **）
- `**101亿人民币`（未闭合 **）

TTS 朗读这些符号会念出"星号星号"，严重影响听感。
修复后：_strip_markdown_residue 清理闭合/未闭合 ** 与行首 # 标题符号。
"""
from app.workflow.llm.rewriter import _strip_markdown_residue


class TestMarkdownStrip:
    """Markdown 残留清洗规则覆盖。"""

    def test_closed_bold_pair(self):
        """闭合 **xxx** 加粗 → 保留内部文字。"""
        assert _strip_markdown_residue("**重要消息**") == "重要消息"

    def test_unclosed_bold_prefix(self):
        """未闭合 **xxx（开头 **，无闭合）→ 移除开头 **。"""
        assert _strip_markdown_residue("**101亿人民币收购SuperPlay") == "101亿人民币收购SuperPlay"

    def test_real_world_case_from_wf_0011(self):
        """wf-20260727-0011 实际案例：未闭合 ** 同时在线 1.6 万。"""
        text = "**同时在线突破1.6万，累计超43万玩家试玩"
        expected = "同时在线突破1.6万，累计超43万玩家试玩"
        assert _strip_markdown_residue(text) == expected

    def test_isolated_double_asterisks(self):
        """孤立的 **（未成对）→ 直接移除。"""
        assert _strip_markdown_residue("普通文本**继续文本") == "普通文本继续文本"

    def test_heading_h1_at_line_start(self):
        """行首 # 标题 + 空格 → 移除符号保留标题文字。"""
        assert _strip_markdown_residue("# 这是标题\n正文内容") == "这是标题\n正文内容"

    def test_heading_multi_level(self):
        """多级标题 ## / ### 同时存在 → 全部清理。"""
        text = "## 二级标题\n### 三级标题\n正文"
        expected = "二级标题\n三级标题\n正文"
        assert _strip_markdown_residue(text) == expected

    def test_plain_text_unchanged(self):
        """无 Markdown 的纯文本不应被改变。"""
        text = "这是一段纯文本，没有Markdown标记。"
        assert _strip_markdown_residue(text) == text

    def test_empty_string(self):
        """空字符串输入应返回空字符串。"""
        assert _strip_markdown_residue("") == ""

    def test_math_asterisk_preserved(self):
        """数学乘号 * 必须保留：两侧均紧邻数字/字母时视为运算而非 Markdown。

        早期版本为"不误伤数学表达"而完全放过单个 *，导致 Markdown 斜体/列表残留的
        单个 * 被 TTS 念成"星号"（用户反馈的 * * 音）。现改为数学安全策略：
        仅当 * 两侧均非数字/字母时才清理，乘号 1*2*3、a*b、3 * 4 均保留。
        """
        assert _strip_markdown_residue("计算 1*2*3=6 的结果") == "计算 1*2*3=6 的结果"
        assert _strip_markdown_residue("面积 3 * 4=12") == "面积 3 * 4=12"
        assert _strip_markdown_residue("变量 a*b 的乘积") == "变量 a*b 的乘积"

    def test_single_asterisk_bullet_stripped(self):
        """行首列表符号 * / - / + 必须清理：避免被 TTS 念成"星号"。"""
        assert _strip_markdown_residue("* 要点一\n* 要点二") == "要点一\n要点二"
        assert _strip_markdown_residue("- 列表项") == "列表项"
        assert _strip_markdown_residue("+ 加号列表") == "加号列表"

    def test_italic_single_asterisk_stripped(self):
        """成对斜体 *文字* / _文字_ 必须清理分隔符：保留内部文字，避免念"星号"。"""
        assert _strip_markdown_residue("*重要*消息来了") == "重要消息来了"
        assert _strip_markdown_residue("这是_强调_内容") == "这是强调内容"

    def test_mixed_closed_and_unclosed_bold(self):
        """混合场景：闭合 **xxx** + 未闭合 **yyy → 分别处理。"""
        text = "**重要**消息：**未闭合部分"
        expected = "重要消息：未闭合部分"
        assert _strip_markdown_residue(text) == expected

    def test_inline_hash_not_stripped(self):
        """行内 # 不被清理：避免误伤"3#楼"等合法用法。

        注：LLM 输出 # 标题时通常在行首，行内 # 场景罕见且语义多义，
        此处刻意不覆盖，避免误伤正常文本。
        """
        text = "住在3#楼的住户"
        assert _strip_markdown_residue(text) == "住在3#楼的住户"

    def test_mixed_bold_and_heading(self):
        """** + # 混合 Markdown 残留 → 全部清理。"""
        text = "**重要**消息：\n# 标题\n普通文字"
        expected = "重要消息：\n标题\n普通文字"
        assert _strip_markdown_residue(text) == expected
