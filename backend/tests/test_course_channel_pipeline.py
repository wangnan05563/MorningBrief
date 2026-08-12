"""业务范围扩展 MVP —— 课程(course)频道流水线验收测试。

对齐 docs/业务范围扩展实施计划.md §四 验收标准：
  #1  course 频道能走通 上传文档 → outline 选题 → 课程模板改写 →
      课程开场/结尾文案，且不注入"今天是X月X日"的日期播报（inject_date=False）。
  #3  selection_strategy='outline' 时按文档章节顺序（素材 id 升序）生成，非热度。

测试策略（与 test_rewriter_channel_isolation.py 同构）：
  - rewriter 内部用模块级 AsyncSessionLocal，无法通过 conftest 的 db_session
    注入；自建内存 engine + sessionmaker 并 monkeypatch rewriter.AsyncSessionLocal。
  - LLM/TTS 不可在沙箱使用，故 mock rewriter._rewrite_one（单条改写），
    并关闭 _is_placeholder_api_key 占位符校验，端到端验证 prompt 接线与组装行为。
"""
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, normalize_metadata_for_sqlite
# 显式导入 Channel / Material 让表注册到 Base.metadata（外键依赖）
from app.models.channel import Channel  # noqa: F401
from app.models.material import Material, MaterialSourceType, MaterialStatus
from app.workflow.llm import rewriter
from app.workflow.llm.style_library import get_style_hint


# ==========================================================================
# Fixture：自建内存 DB 并 patch rewriter.AsyncSessionLocal
# ==========================================================================
@pytest.fixture
async def course_sessionlocal(monkeypatch):
    """为 rewriter 内部 AsyncSessionLocal 提供独立内存 DB（StaticPool 共享同一内存库）。"""
    normalize_metadata_for_sqlite()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(rewriter, "AsyncSessionLocal", session_local)
    yield session_local
    await engine.dispose()


def _add_material(session, *, title, url, channel_id, source_type="list", content=None, id=None):
    """插入一条 pending 素材（list 类型模拟文档上传）。"""
    kwargs = dict(
        source="doc-upload",
        source_type=source_type,
        title=title,
        content=content or f"{title} 正文内容",
        url=url,
        status=MaterialStatus.pending.value,
        channel_id=channel_id,
    )
    if id is not None:
        kwargs["id"] = id  # 显式指定 id，解耦插入顺序与 id 顺序
    session.add(Material(**kwargs))


def _make_course_channel(session, **overrides) -> Channel:
    """创建一条 course 频道，默认走 outline 选题 + 关广告 + 强风险提示。"""
    defaults = dict(
        name="测试课程频道",
        channel_type="course",
        selection_strategy="outline",
        enable_ad=0,
        disclaimer_level="strong",
    )
    defaults.update(overrides)
    ch = Channel(**defaults)
    session.add(ch)
    return ch


# ==========================================================================
# 纯函数测试（无 DB）
# ==========================================================================
def test_resolve_rewrite_template_course_auto_default():
    """course 频道未显式设 rewrite_template 时，自动套用课程模板文件内容。"""
    resolved = rewriter._resolve_rewrite_template(None, "course")
    assert resolved is not None
    # 应是 rewrite_course.txt 的文件内容，而非默认 rewrite.txt
    assert resolved == rewriter._load_prompt_file(rewriter._COURSE_REWRITE_TEMPLATE)
    assert resolved != rewriter._load_prompt_file("rewrite.txt")


def test_resolve_rewrite_template_news_falls_back_to_none():
    """news 频道未显式设模板时返回 None（rewriter 回退默认 rewrite.txt）。"""
    assert rewriter._resolve_rewrite_template(None, "news") is None


def test_resolve_rewrite_template_filename_loaded_not_literal():
    """存的是文件名（.txt 且不含占位符）时解析为文件内容，而非当原文用（旧 bug 回归）。"""
    resolved = rewriter._resolve_rewrite_template("rewrite_course.txt", "news")
    assert resolved == rewriter._load_prompt_file("rewrite_course.txt")


def test_resolve_rewrite_template_raw_text_passthrough():
    """存的是含占位符的原始模板文本时原样返回（向后兼容频道直存整段模板）。"""
    raw = "请改写标题 {title} 内容为 {content}"
    assert rewriter._resolve_rewrite_template(raw, "course") == raw


def test_style_hint_course_uses_lecturer_library():
    """course 频道按类型匹配讲师词库（含'讲师'），与默认主播词库区分。"""
    course_hint = get_style_hint(channel_id=None, seq=1, total_segments=3, channel_type="course")
    default_hint = get_style_hint(channel_id=None, seq=1, total_segments=3, channel_type=None)

    assert "讲师" in course_hint
    assert "讲师" not in default_hint
    # seq>=2 时用过渡词（亦来自课程词库），整体仍含讲师定位
    course_transition = get_style_hint(channel_id=None, seq=2, total_segments=3, channel_type="course")
    assert "讲师" in course_transition


def test_select_top_materials_outline_orders_by_id_not_heat():
    """outline 选题按素材 id 升序（文档章节顺序），忽略热度。"""
    # 故意打乱 id 顺序，并给后段更高"热度"字段（heat_score 依赖 category/score）
    materials = [
        {"id": 3, "title": "第三章", "category": "A", "score": 99, "channel_id": 1},
        {"id": 1, "title": "第一章", "category": "A", "score": 10, "channel_id": 1},
        {"id": 2, "title": "第二章", "category": "A", "score": 50, "channel_id": 1},
    ]
    selected = rewriter._select_top_materials(materials, strategy="outline")
    ids = [m["id"] for m in selected]
    assert ids == [1, 2, 3]  # 章节顺序，而非按 score 降序 [3,2,1]


# ==========================================================================
# DB 支撑测试：outline 选题按章节顺序取全部 pending
# ==========================================================================
@pytest.mark.asyncio
async def test_fetch_materials_outline_returns_channel_pending_in_id_order(course_sessionlocal):
    """outline 选题不卡 crawled_at，取本频道全部 pending 并按 id 升序返回。"""
    async with course_sessionlocal() as session:
        ch = _make_course_channel(session)
        await session.flush()  # 拿到 channel.id
        # 故意以乱序指定 id，验证返回按 id 升序（章节顺序），而非插入顺序
        _add_material(session, title="第三章内容", url="https://doc.test/c3", channel_id=ch.id, id=3)
        _add_material(session, title="第一章内容", url="https://doc.test/c1", channel_id=ch.id, id=1)
        _add_material(session, title="第二章内容", url="https://doc.test/c2", channel_id=ch.id, id=2)
        await session.commit()

    results = await rewriter._fetch_materials(
        date.today().isoformat(), channel_id=ch.id, strategy="outline"
    )
    titles = [r["title"] for r in results]
    assert titles == ["第一章内容", "第二章内容", "第三章内容"]


@pytest.mark.asyncio
async def test_fetch_channel_prompts_returns_course_type(course_sessionlocal):
    """_fetch_channel_prompts 对 course 频道返回 channel_type=course。"""
    async with course_sessionlocal() as session:
        ch = _make_course_channel(session)
        await session.commit()

    prompts = await rewriter._fetch_channel_prompts(ch.id)
    assert prompts["channel_type"] == "course"
    assert prompts["selection_strategy"] == "outline"
    # 频道未显式覆盖 intro/outro 时，仍返回 None（由 rewrite() 接管 course 默认）
    assert prompts["intro_prompt"] is None
    assert prompts["outro_prompt"] is None


# ==========================================================================
# 端到端集成：course 频道 rewrite() 自动接线课程模板 + 文案 + 不注入日期
# ==========================================================================
@pytest.mark.asyncio
async def test_rewrite_course_pipeline_applies_template_and_no_date(course_sessionlocal, monkeypatch):
    """course 频道 rewrite()：自动套课程模板、课程开场/结尾文案，且不注入日期。"""
    # 关闭占位符 API key 校验（沙箱无真实 key）
    monkeypatch.setattr(rewriter, "_is_placeholder_api_key", lambda key: False)

    # 捕获 _rewrite_one 收到的 template_text / style_hint，验证课程模板被传递
    captured = {"calls": []}

    async def fake_rewrite_one(m, words_per_segment=None, segment_duration=None,
                               template_text=None, constraint_text=None,
                               enable_thinking_question=True, style_hint=None):
        captured["calls"].append({
            "material_id": m["id"],
            "template_text": template_text,
            "style_hint": style_hint,
        })
        return {
            "title": m["title"],
            "content": f"本节讲解：{m['title']}。",
            "material_id": m["id"],
            "cover_url": None,
        }

    monkeypatch.setattr(rewriter, "_rewrite_one", fake_rewrite_one)

    async with course_sessionlocal() as session:
        ch = _make_course_channel(session)
        await session.flush()
        _add_material(session, title="第一章", url="https://doc.test/i1", channel_id=ch.id)
        _add_material(session, title="第二章", url="https://doc.test/i2", channel_id=ch.id)
        _add_material(session, title="第三章", url="https://doc.test/i3", channel_id=ch.id)
        await session.commit()

    result = await rewriter.rewrite(
        workflow_id="wf-course-test-001",
        date_str=date.today().isoformat(),
        channel_id=ch.id,
    )

    # rewrite() 落库 script 表并返回元数据（script_id/segments/total_words）
    assert result["segments"] == 3
    assert result["script_id"] is not None

    # 从持久化 Script 读取完整稿件（full_text / segments 由 assemble 写出）
    from app.models.script import Script
    from sqlalchemy import select as _select
    async with course_sessionlocal() as session:
        script = (await session.execute(
            _select(Script).where(Script.workflow_id == "wf-course-test-001")
        )).scalar_one()
    full_text = script.full_text
    segments_json = script.segments

    # 1) 课程模板自动传递（非 None，且为 rewrite_course.txt 内容）
    assert captured["calls"], "未调用 _rewrite_one"
    assert captured["calls"][0]["template_text"] == rewriter._load_prompt_file(
        rewriter._COURSE_REWRITE_TEMPLATE
    )
    # 讲师风格提示注入（channel_type=course 经 get_style_hint 生效）
    assert "讲师" in captured["calls"][0]["style_hint"]

    # 2) 不注入日期播报（课程稿连贯性）
    assert "今天是" not in full_text

    # 3) 自动套用课程开场/结尾文案（intro/outro 在 full_text 首/尾）
    intro_text = rewriter._load_prompt_file(rewriter._COURSE_INTRO_FILE).strip()
    outro_text = rewriter._load_prompt_file(rewriter._COURSE_OUTRO_FILE).strip()
    assert full_text.startswith(intro_text)
    # 结尾文案文件含尾随换行，用 rstrip 对齐
    assert full_text.rstrip("\n").endswith(outro_text)

    # 4) outline 选题按章节顺序（段内容顺序对应 第一/二/三 章）
    body_titles = [s["title"] for s in segments_json
                   if s["title"] not in ("开场白", "结尾")]
    assert body_titles == ["第一章", "第二章", "第三章"]
