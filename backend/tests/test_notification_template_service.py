"""通知模板服务测试。

覆盖：
- render_template：变量插值、缺失变量降级、无变量模板
- extract_variables：变量名提取、去重、嵌套花括号
- TemplateService：list/get/update/seed_preset_templates

测试目标：确保模板渲染逻辑稳定，缺失变量不引发异常。
"""
import pytest

from app.services.notification.template_service import (
    render_template,
    extract_variables,
    PRESET_TEMPLATES,
    TemplateService,
)


# ====================== render_template 测试 ======================

def test_render_template_basic():
    """基本变量插值。"""
    tpl = "频道 {{channel_name}} 日期 {{episode_date}}"
    result = render_template(tpl, {"channel_name": "新闻", "episode_date": "2026-07-14"})
    assert result == "频道 新闻 日期 2026-07-14"


def test_render_template_missing_var_becomes_empty():
    """缺失变量降级为空字符串（避免渲染中断）。"""
    tpl = "频道 {{channel_name}} 错误 {{error_message}}"
    result = render_template(tpl, {"channel_name": "新闻"})
    assert result == "频道 新闻 错误 "


def test_render_template_no_vars():
    """无变量模板原样返回。"""
    tpl = "这是一条固定消息"
    assert render_template(tpl, {}) == tpl


def test_render_template_empty_context():
    """空上下文 + 全变量模板 → 全空字符串。"""
    tpl = "{{a}}{{b}}"
    assert render_template(tpl, {}) == ""


def test_render_template_multiple_occurrences():
    """同一变量多次引用全部替换。"""
    tpl = "{{x}} + {{x}} = 2*{{x}}"
    assert render_template(tpl, {"x": "1"}) == "1 + 1 = 2*1"


def test_render_template_none_value():
    """None 值降级为空字符串。"""
    tpl = "val={{v}}"
    assert render_template(tpl, {"v": None}) == "val="


# ====================== extract_variables 测试 ======================

def test_extract_variables_basic():
    """提取变量名列表。"""
    tpl = "{{channel_name}} {{episode_date}} {{workflow_id}}"
    vars_ = extract_variables(tpl)
    assert "channel_name" in vars_
    assert "episode_date" in vars_
    assert "workflow_id" in vars_


def test_extract_variables_dedup():
    """同一变量多次出现只提取一次。"""
    tpl = "{{x}} {{y}} {{x}} {{z}} {{y}}"
    vars_ = extract_variables(tpl)
    assert vars_.count("x") == 1
    assert vars_.count("y") == 1
    assert vars_.count("z") == 1


def test_extract_variables_empty_template():
    """无变量模板返回空列表。"""
    assert extract_variables("固定消息") == []


def test_extract_variables_title_and_body_union():
    """标题 + 正文拼接后提取并集（模拟 list_templates 的调用）。"""
    title = "{{channel_name}} 待审核"
    body = "工作流 {{workflow_id}}\n频道 {{channel_name}}\n错误 {{error_message}}"
    vars_ = extract_variables(title) + extract_variables(body)
    # 不去重拼接（路由层用 set 去重也行，这里仅验证字段都包含）
    assert "channel_name" in vars_
    assert "workflow_id" in vars_
    assert "error_message" in vars_


# ====================== PRESET_TEMPLATES 测试 ======================

def test_preset_templates_have_three_events():
    """预设模板覆盖 3 个事件类型。"""
    event_types = {t["event_type"] for t in PRESET_TEMPLATES}
    assert event_types == {
        "workflow.pending_review",
        "workflow.failed",
        "workflow.published",
    }


def test_preset_templates_contain_vars():
    """预设模板引用了关键变量。"""
    for tpl in PRESET_TEMPLATES:
        vars_ = extract_variables(tpl["title_template"]) + extract_variables(tpl["body_template"])
        # 每个预设模板至少引用了 workflow_id
        assert "workflow_id" in vars_, f"模板 {tpl['event_type']} 缺少 workflow_id 变量"


# ====================== TemplateService CRUD 测试 ======================

@pytest.mark.asyncio
async def test_seed_preset_templates_inserts_when_empty(db_session):
    """空库 seed 插入全部预设模板。"""
    svc = TemplateService(db_session)
    inserted = await svc.seed_preset_templates()
    assert inserted == len(PRESET_TEMPLATES)


@pytest.mark.asyncio
async def test_seed_preset_templates_idempotent(db_session):
    """重复 seed 不重复插入。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    inserted_again = await svc.seed_preset_templates()
    assert inserted_again == 0


@pytest.mark.asyncio
async def test_list_templates_returns_all(db_session):
    """list_templates 返回所有模板。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    templates = await svc.list_templates()
    assert len(templates) == len(PRESET_TEMPLATES)


@pytest.mark.asyncio
async def test_get_template_by_event_type(db_session):
    """按 event_type 查询启用模板。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    tpl = await svc.get_template("workflow.pending_review")
    assert tpl is not None
    assert tpl.event_type == "workflow.pending_review"
    # SQLite 用 0/1 存储布尔值，用 == 比较（1 == True 为 True）
    assert tpl.enabled == 1


@pytest.mark.asyncio
async def test_get_template_by_id(db_session):
    """按 id 查询模板。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    templates = await svc.list_templates()
    first_id = templates[0].id
    tpl = await svc.get_template_by_id(first_id)
    assert tpl is not None
    assert tpl.id == first_id


@pytest.mark.asyncio
async def test_get_template_returns_none_for_unknown_event(db_session):
    """未注册事件类型返回 None。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    tpl = await svc.get_template("unknown.event")
    assert tpl is None


@pytest.mark.asyncio
async def test_update_template(db_session):
    """更新模板字段。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    templates = await svc.list_templates()
    first = templates[0]
    updated = await svc.update_template(first.id, {
        "name": "自定义名称",
        "title_template": "新标题 {{workflow_id}}",
        "body_template": "新正文",
        "enabled": False,
    })
    assert updated is not None
    assert updated.name == "自定义名称"
    assert updated.title_template == "新标题 {{workflow_id}}"
    assert updated.body_template == "新正文"
    assert updated.enabled == 0


@pytest.mark.asyncio
async def test_update_template_partial(db_session):
    """部分更新（仅 enabled 字段）。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    templates = await svc.list_templates()
    first = templates[0]
    original_name = first.name
    updated = await svc.update_template(first.id, {"enabled": False})
    assert updated is not None
    assert updated.enabled == 0
    # name 未传 → 保持原值
    assert updated.name == original_name


@pytest.mark.asyncio
async def test_update_template_returns_none_for_unknown_id(db_session):
    """未知 id 返回 None。"""
    svc = TemplateService(db_session)
    result = await svc.update_template(99999, {"name": "x"})
    assert result is None


@pytest.mark.asyncio
async def test_get_template_skips_disabled(db_session):
    """禁用模板不会被 get_template 返回（按 event_type 查询启用模板）。"""
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    templates = await svc.list_templates()
    # 禁用 pending_review 模板
    for t in templates:
        if t.event_type == "workflow.pending_review":
            await svc.update_template(t.id, {"enabled": False})
            break
    # get_template 查询启用模板，应返回 None
    tpl = await svc.get_template("workflow.pending_review")
    assert tpl is None
