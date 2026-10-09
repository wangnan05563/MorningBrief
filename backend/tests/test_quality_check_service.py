"""LLM 语义级质量审核服务测试（T01712 P1）。

覆盖：
1. _parse_llm_report 纯函数：合法/围栏包裹/非法 JSON/枚举外条目丢弃/超长截断
2. run_quality_check 集成：正常审核落库、非法 JSON 降级、异常降级、
   功能开关、稿件缺失——核心断言是「任何失败都不阻塞、不抛异常」

测试策略（与 test_course_channel_pipeline.py 同构）：
  服务内部用模块级 AsyncSessionLocal，自建内存 engine + sessionmaker 并
  monkeypatch quality_check_service.AsyncSessionLocal；LLM 用 monkeypatch
  rewriter._call_llm 模拟（服务函数内 import，patch 模块属性即可生效）。
"""
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, normalize_metadata_for_sqlite
from app.models import Material, Script, Workflow
from app.models.material import MaterialStatus
from app.models.workflow import WorkflowSource, WorkflowStatus
from app.services import quality_check_service as qc


# ==========================================================================
# Fixture：自建内存 DB 并 patch qc.AsyncSessionLocal
# ==========================================================================
@pytest.fixture
async def qc_sessionlocal(monkeypatch):
    """为服务内部 AsyncSessionLocal 提供独立内存 DB（StaticPool 共享同一内存库）。"""
    normalize_metadata_for_sqlite()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(qc, "AsyncSessionLocal", session_local)
    yield session_local
    await engine.dispose()


@pytest.fixture
def enable_qc(monkeypatch):
    """显式开启审核开关（默认即 True，测试中可能被单测改 False 后需还原）。"""
    monkeypatch.setattr(qc.settings, "QUALITY_CHECK_ENABLED", True)


def _make_workflow(session, *, channel_id=None, workflow_id="wf-test-0001") -> Workflow:
    wf = Workflow(
        id=workflow_id,
        episode_date=__import__("datetime").date.today(),
        source=WorkflowSource.manual.value,
        status=WorkflowStatus.running.value,
        channel_id=channel_id,
    )
    session.add(wf)
    return wf


def _make_script(session, workflow_id: str) -> Script:
    segments = [
        {"seq": 1, "title": "开场白", "content": "大家好，欢迎收听。", "material_ids": []},
        {"seq": 2, "title": "第一章", "content": "作者回忆道，那年秋天他回到故乡。",
         "material_ids": [101]},
        {"seq": 3, "title": "结尾", "content": "今天的分享就到这里。", "material_ids": []},
    ]
    script = Script(
        workflow_id=workflow_id,
        episode_date=__import__("datetime").date.today(),
        full_text="\n".join(s["content"] for s in segments),
        segments=segments,
        total_words=30,
        status="draft",
    )
    session.add(script)
    return script


def _make_material(session, *, material_id: int, source: str = "测试书籍"):
    session.add(Material(
        id=material_id,
        source=source,
        source_type="list",
        title=f"素材{material_id}",
        content="作者在原文中写道：一九四三年冬，他随部队转移。",
        url=f"https://example.com/{material_id}",
        status=MaterialStatus.selected.value,
    ))


async def _seed(session, *, workflow_id="wf-test-0001", with_material=True):
    """按外键依赖顺序播种 workflow/script/material，返回 script_id。"""
    _make_workflow(session, workflow_id=workflow_id)
    script = _make_script(session, workflow_id)
    if with_material:
        _make_material(session, material_id=101)
    await session.commit()
    return script.id


# ==========================================================================
# 纯函数测试：_parse_llm_report
# ==========================================================================
def test_parse_report_valid_empty_issues():
    """pass=true + 空 issues → 通过，无问题。"""
    raw = '{"pass": true, "issues": []}'
    parsed = qc._parse_llm_report(raw)
    assert parsed is not None
    assert parsed["passed"] is True
    assert parsed["issues"] == []
    assert parsed["issue_count"] == 0


def test_parse_report_issues_sorted_by_severity():
    """issues 按 severity 等级降序（先高后低），同级按 seq 升序。"""
    raw = (
        '{"pass": false, "issues": ['
        '{"seq": 3, "issue_type": "readability", "severity": "low", "evidence": "e3", "suggestion": "s3"},'
        '{"seq": 2, "issue_type": "fact_anchor", "severity": "high", "evidence": "e2", "suggestion": "s2"},'
        '{"seq": 1, "issue_type": "hook", "severity": "medium", "evidence": "e1", "suggestion": "s1"}'
        ']}'
    )
    parsed = qc._parse_llm_report(raw)
    severities = [i["severity"] for i in parsed["issues"]]
    assert severities == ["high", "medium", "low"]
    assert parsed["issue_count"] == 3
    assert parsed["passed"] is False


def test_parse_report_strips_markdown_fence():
    """LLM 用 ```json 围栏包裹输出时照常解析，不误判非法。"""
    raw = '```json\n{"pass": true, "issues": []}\n```'
    assert qc._parse_llm_report(raw) is not None


def test_parse_report_invalid_json_returns_none():
    """非 JSON 输出 → None（调用方降级为未审核）。"""
    assert qc._parse_llm_report("抱歉，我无法审核") is None
    assert qc._parse_llm_report("") is None


def test_parse_report_non_dict_returns_none():
    """顶层是数组/字符串等非对象 → None。"""
    assert qc._parse_llm_report('[1, 2, 3]') is None


def test_parse_report_drops_invalid_enum_entries():
    """issue_type/severity 枚举外的条目丢弃，合法条目保留（不因单条坏数据整次失败）。"""
    raw = (
        '{"pass": false, "issues": ['
        '{"seq": 1, "issue_type": "made_up_type", "severity": "high", "evidence": "a", "suggestion": "b"},'
        '{"seq": 2, "issue_type": "hook", "severity": "extreme", "evidence": "c", "suggestion": "d"},'
        '{"seq": 3, "issue_type": "hook", "severity": "high", "evidence": "ok", "suggestion": "fine"}'
        ']}'
    )
    parsed = qc._parse_llm_report(raw)
    assert parsed["issue_count"] == 1
    assert parsed["issues"][0]["seq"] == 3


def test_parse_report_drops_bad_seq():
    """seq 非法（缺省/非数字）的条目丢弃。"""
    raw = (
        '{"pass": false, "issues": ['
        '{"issue_type": "hook", "severity": "high", "evidence": "a", "suggestion": "b"},'
        '{"seq": "abc", "issue_type": "hook", "severity": "high", "evidence": "c", "suggestion": "d"}'
        ']}'
    )
    assert qc._parse_llm_report(raw)["issue_count"] == 0


def test_parse_report_truncates_long_text():
    """evidence/suggestion 截断到 500 字，防 LLM 长篇大论撑爆报告与前端。"""
    long_text = "长" * 1000
    raw = (
        '{"pass": false, "issues": ['
        f'{{"seq": 1, "issue_type": "hook", "severity": "high", "evidence": "{long_text}", "suggestion": "{long_text}"}}'
        ']}'
    )
    parsed = qc._parse_llm_report(raw)
    assert len(parsed["issues"][0]["evidence"]) == 500
    assert len(parsed["issues"][0]["suggestion"]) == 500


def test_parse_report_missing_fields_tolerated():
    """缺 evidence/suggestion 时按空串容错，不炸。"""
    raw = '{"pass": false, "issues": [{"seq": 1, "issue_type": "hook", "severity": "low"}]}'
    parsed = qc._parse_llm_report(raw)
    assert parsed["issues"][0]["evidence"] == ""
    assert parsed["issues"][0]["suggestion"] == ""


# ==========================================================================
# 集成测试：run_quality_check
# ==========================================================================
@pytest.mark.asyncio
async def test_run_quality_check_success_persists_report(qc_sessionlocal, monkeypatch, enable_qc):
    """LLM 返回合法报告 → 落库 script.quality_report + 返回摘要。"""
    async with qc_sessionlocal() as session:
        script_id = await _seed(session)

    llm_raw = (
        '{"pass": false, "issues": ['
        '{"seq": 2, "issue_type": "fact_anchor", "severity": "high", '
        '"evidence": "二〇一七年", "suggestion": "应为二〇一四"}]}'
    )
    async def fake_llm(prompt):
        assert "作者回忆道" in prompt      # 分段内容已注入
        assert "测试书籍" in prompt        # 素材锚点已注入
        return llm_raw
    monkeypatch.setattr("app.workflow.llm.rewriter._call_llm", fake_llm)

    result = await qc.run_quality_check("wf-test-0001", script_id)
    summary = result["quality_check"]
    assert summary["skipped"] is False
    assert summary["passed"] is False
    assert summary["issue_count"] == 1
    # 阈值默认 medium，high 达标 → alert_count=1
    assert summary["alert_count"] == 1

    async with qc_sessionlocal() as session:
        script = await session.get(Script, script_id)
        report = script.quality_report
        assert report is not None
        assert report["passed"] is False
        assert report["issues"][0]["issue_type"] == "fact_anchor"
        assert report["checked_at"]


@pytest.mark.asyncio
async def test_run_quality_check_invalid_json_degrades(qc_sessionlocal, monkeypatch, enable_qc):
    """非法 JSON → skipped，不落库报告，不抛异常（宁可漏审不可阻塞）。"""
    async with qc_sessionlocal() as session:
        script_id = await _seed(session)

    async def fake_llm(prompt):
        return "这不是 JSON"
    monkeypatch.setattr("app.workflow.llm.rewriter._call_llm", fake_llm)

    result = await qc.run_quality_check("wf-test-0001", script_id)
    assert result["quality_check"]["skipped"] is True
    assert result["quality_check"]["skipped_reason"] == "invalid_llm_response"

    async with qc_sessionlocal() as session:
        script = await session.get(Script, script_id)
        assert script.quality_report is None


@pytest.mark.asyncio
async def test_run_quality_check_llm_exception_degrades(qc_sessionlocal, monkeypatch, enable_qc):
    """LLM 抛异常（网络/预算超限）→ skipped，异常不外溢。"""
    async with qc_sessionlocal() as session:
        script_id = await _seed(session)

    async def boom(prompt):
        raise RuntimeError("AI 预算超限")
    monkeypatch.setattr("app.workflow.llm.rewriter._call_llm", boom)

    result = await qc.run_quality_check("wf-test-0001", script_id)
    assert result["quality_check"]["skipped"] is True
    assert "error" in result["quality_check"]["skipped_reason"]


@pytest.mark.asyncio
async def test_run_quality_check_disabled(qc_sessionlocal, monkeypatch):
    """QUALITY_CHECK_ENABLED=False → 直接跳过，不调用 LLM。"""
    monkeypatch.setattr(qc.settings, "QUALITY_CHECK_ENABLED", False)

    async def fail(prompt):
        raise AssertionError("关闭时不应调用 LLM")
    monkeypatch.setattr("app.workflow.llm.rewriter._call_llm", fail)

    result = await qc.run_quality_check("wf-test-0001", 1)
    assert result["quality_check"]["skipped"] is True
    assert result["quality_check"]["skipped_reason"] == "disabled"


@pytest.mark.asyncio
async def test_run_quality_check_no_script(qc_sessionlocal, enable_qc):
    """稿件不存在 → skipped_reason=no_script。"""
    result = await qc.run_quality_check("wf-test-0001", 9999)
    assert result["quality_check"]["skipped"] is True
    assert result["quality_check"]["skipped_reason"] == "no_script"


@pytest.mark.asyncio
async def test_run_quality_check_alert_threshold_low_severity(
    qc_sessionlocal, monkeypatch, enable_qc,
):
    """低于告警阈值的 issue 不计入 alert_count 但仍落库（P1 全量留痕）。"""
    async with qc_sessionlocal() as session:
        script_id = await _seed(session)

    llm_raw = (
        '{"pass": false, "issues": ['
        '{"seq": 2, "issue_type": "readability", "severity": "low", "evidence": "x", "suggestion": "y"}]}'
    )

    async def fake_llm(prompt):
        return llm_raw
    monkeypatch.setattr("app.workflow.llm.rewriter._call_llm", fake_llm)

    result = await qc.run_quality_check("wf-test-0001", script_id)
    assert result["quality_check"]["issue_count"] == 1
    assert result["quality_check"]["alert_count"] == 0
