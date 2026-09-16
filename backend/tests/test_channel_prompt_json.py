"""频道提示词 JSON 解析与自修复重试测试（T00621）。

背景：用户实测「AI 重新生成频道提示词」报 `LLM 响应 JSON 解析失败: Expecting ',' delimiter`——
LLM 输出的 JSON 里出现未转义的英文双引号（提示词文本含引用）即解析失败。

覆盖：
- parse_llm_json 宽容解析（围栏剥离 / 前后杂文截取 / 单引号风格回退 / 非法输入报错含摘录）；
- _chat_json 自修复重试（首响应非法 → 喂回错误重试一次 → 成功；二次仍失败才抛错）；
- 元提示词含输出规则（从源头约束 LLM）。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_channel_prompt_json.py
"""
import json
import types

import pytest

from app.services import channel_prompt_service as cps


class TestParseLlmJson:
    def test_plain_json(self):
        assert cps.parse_llm_json('{"a": "1"}', 't') == {"a": "1"}

    def test_markdown_fences_stripped(self):
        raw = '```json\n{"intro": "开场"}\n```'
        assert cps.parse_llm_json(raw)['intro'] == '开场'

    def test_leading_and_trailing_prose_tolerated(self):
        raw = '好的，以下是结果：\n{"a": "b"}\n希望有帮助'
        assert cps.parse_llm_json(raw) == {"a": "b"}

    def test_single_quote_style_fallback(self):
        """LLM 偶发输出单引号风格（Python 字面量）→ ast 回退可解析。"""
        raw = "{'intro': '开场白'}"
        assert cps.parse_llm_json(raw) == {'intro': '开场白'}

    def test_broken_json_raises_with_excerpt(self):
        """未转义引号等真非法输入 → ValueError 且消息含内容摘录（便于定位）。"""
        broken = '{"intro": "他说"你好"了"}'  # 内部未转义双引号
        with pytest.raises(ValueError, match='不是合法 JSON'):
            cps.parse_llm_json(broken)

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            cps.parse_llm_json('', 't')


class TestChatJsonRepair:
    """自修复重试：首响应非法 → 喂回错误重试一次 → 成功；二次仍失败才抛错。"""

    @staticmethod
    def _fake_client(responses):
        """responses 依次消费；每项为 LLM 返回的 content 文本。"""

        class _Msg:
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, content):
                self.message = _Msg(content)

        class _Resp:
            def __init__(self, content):
                self.choices = [_Choice(content)]
                self.usage = None

        class _Completions:
            def __init__(self, queue):
                self._queue = queue

            async def create(self, **kwargs):
                assert self._queue, 'LLM 调用次数超出预期'
                return _Resp(self._queue.pop(0))

        class _Chat:
            def __init__(self, queue):
                self.completions = _Completions(queue)

        class _Client:
            def __init__(self, queue):
                self.chat = _Chat(queue)

        return _Client(list(responses))

    @pytest.mark.asyncio
    async def test_repair_after_invalid_first_response(self, monkeypatch):
        monkeypatch.setattr(cps, 'record_call', lambda **kw: None)
        good = json.dumps({"intro": "早上好", "outro": "再见", "constraint": "", "template": "T"}, ensure_ascii=False)
        broken = '{"intro": "他说"你好""}'  # 未转义引号
        calls = []

        client = self._fake_client([broken, good])

        class _Proxy:
            def chat(self):
                pass

        monkeypatch.setattr(cps, '_get_client', lambda: client)
        # 记录调用内容，断言重试 prompt 携带了原始错误
        orig_create = client.chat.completions.create

        async def spy_create(**kwargs):
            calls.append(kwargs['messages'][0]['content'])
            return await orig_create(**kwargs)

        client.chat.completions.create = spy_create
        data = await cps._chat_json('生成提示词', 60, '频道提示词')
        assert data['intro'] == '早上好'
        assert len(calls) == 2
        assert '不是合法 JSON' in calls[1], '重试 prompt 应包含解析错误'
        assert '他说' in calls[1], '重试 prompt 应携带原始输出'

    @pytest.mark.asyncio
    async def test_second_failure_raises(self, monkeypatch):
        monkeypatch.setattr(cps, 'record_call', lambda **kw: None)
        broken1 = '{"intro": "他说"你好""}'
        broken2 = '{"intro": "还是"坏的""}'
        client = self._fake_client([broken1, broken2])
        monkeypatch.setattr(cps, '_get_client', lambda: client)
        with pytest.raises(ValueError, match='自修复重试后仍失败'):
            await cps._chat_json('生成提示词', 60, '频道提示词')


class TestMetaPromptRules:
    def test_output_rules_appended_to_all_templates(self):
        """三类生成的 prompt 都必须拼接 JSON 输出规则（源头约束）。"""
        src = open(cps.__file__, encoding='utf-8').read()
        assert src.count('_JSON_OUTPUT_RULES') >= 4  # 定义 1 + 三处拼接
        for name in ('_META_PROMPT_TEMPLATE', '_BGM_RECOMMEND_TEMPLATE', '_RSS_RECOMMEND_TEMPLATE'):
            assert name in src
        rules = cps._JSON_OUTPUT_RULES
        assert '中文引号' in rules and '不要任何解释' in rules

    def test_meta_prompt_asked_for_json_only(self):
        """元提示词本身要求仅输出 JSON（与规则片段双保险）。"""
        assert '仅输出 JSON 本身' in cps._META_PROMPT_TEMPLATE


@pytest.mark.asyncio
async def test_generate_prompts_uses_repair(monkeypatch):
    monkeypatch.setattr(cps, 'record_call', lambda **kw: None)
    """端到端（打桩）：首响应带未转义引号 → 自修复 → 4 字段正常返回。"""
    broken = (
        '{"intro": "大家"早上"好", "outro": "明天见", '
        '"constraint": "不构成投资建议", "template": "模板{{title}}"}'
    )
    good = json.dumps(
        {
            "intro": "今天，欢迎收听。",
            "outro": "感谢收听，明天再会。",
            "constraint": "内容不构成投资建议。",
            "template": "请改写：{{title}} {{content}} {{source}} {{category}} {{source_url}} {{words_per_segment}} {{segment_duration}}",
        },
        ensure_ascii=False,
    )
    client = TestChatJsonRepair._fake_client([broken, good])
    monkeypatch.setattr(cps, '_get_client', lambda: client)
    monkeypatch.setattr(cps, 'check_budget', lambda **kw: (True, ''))

    data = await cps.generate_prompts_for_channel('财经早知道', '每日财经要闻解读')
    assert data['intro_prompt'] == '今天，欢迎收听。'
    assert data['constraint_prompt'] == '内容不构成投资建议。'
    assert '{{title}}' in data['rewrite_template']
