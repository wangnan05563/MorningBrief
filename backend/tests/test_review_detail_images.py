"""审核详情「采集图片」测试（T00809）。

覆盖 services/review_service.py::get_review_detail 新增的 images / image_total：
- 按「分段顺序 → 段内 material_ids 顺序」聚合素材的 images_json，去重保序
- 超出上限时 images 截断为 9 张，image_total 仍为去重后总张数
- 老脚本无 material_ids 时按 referenced_materials 的 URL 反查素材兜底
- 素材无图 / images_json 为脏数据 → 返回空数组且不抛异常
"""
import json
from datetime import date

import pytest

from app.models import Material, Review, ReviewStatus, Script
from app.services.material_images import aggregate_material_images, parse_material_images
from app.services.review_service import REVIEW_IMAGE_LIMIT, ReviewService


async def _make_material(db, url: str, images: list[str] | None = None, raw: str | None = None):
    """建一条采集素材；images 走正常 JSON 落库，raw 用于注入脏数据。"""
    mat = Material(
        source="某站",
        source_type="rss",
        title=f"文章 {url}",
        content="正文",
        url=url,
        crawled_at=date.today(),
        images_json=raw if raw is not None else (json.dumps(images) if images else None),
    )
    db.add(mat)
    await db.flush()
    return mat


async def _make_review(db, segments, referenced_materials=None):
    script = Script(
        workflow_id="wf-img",
        episode_date=date.today(),
        full_text="稿件全文",
        segments=segments,
        referenced_materials=referenced_materials,
    )
    db.add(script)
    await db.flush()
    review = Review(
        workflow_id="wf-img",
        episode_date=date.today(),
        script_id=script.id,
        audio_url="http://cdn/test.mp3",
        status=ReviewStatus.pending,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


@pytest.mark.asyncio
async def test_images_follow_segment_material_order(db_session):
    """按分段引用的素材顺序聚合，同一张图只出现一次（去重保序）。"""
    m1 = await _make_material(db_session, "https://a.com/1", ["https://img/1a.jpg", "https://img/1b.jpg"])
    m2 = await _make_material(db_session, "https://a.com/2", ["https://img/1b.jpg", "https://img/2a.jpg"])
    review = await _make_review(db_session, [
        {"seq": 1, "title": "开场", "material_ids": []},
        {"seq": 2, "title": "正文", "material_ids": [m1.id, m2.id]},
        {"seq": 3, "title": "结尾", "material_ids": [m1.id]},
    ])

    detail = await ReviewService(db_session).get_review_detail(review.id)

    # 顺序：m1 的两张在前，m2 的重复图被去掉，只剩新增那张
    assert detail["images"] == ["https://img/1a.jpg", "https://img/1b.jpg", "https://img/2a.jpg"]
    assert detail["image_total"] == 3


@pytest.mark.asyncio
async def test_images_truncated_but_total_kept(db_session):
    """图片超过上限时展示列表截断，image_total 保留真实总数（前端提示"展示前 N 张"）。"""
    many = [f"https://img/{i}.jpg" for i in range(REVIEW_IMAGE_LIMIT + 5)]
    m = await _make_material(db_session, "https://a.com/many", many)
    review = await _make_review(db_session, [{"seq": 1, "material_ids": [m.id]}])

    detail = await ReviewService(db_session).get_review_detail(review.id)

    assert len(detail["images"]) == REVIEW_IMAGE_LIMIT
    assert detail["image_total"] == len(many)


@pytest.mark.asyncio
async def test_images_fallback_by_referenced_url(db_session):
    """老脚本没有 material_ids 时，按 referenced_materials 的 URL 反查素材取图。"""
    m = await _make_material(db_session, "https://a.com/legacy", ["https://img/legacy.jpg"])
    review = await _make_review(
        db_session,
        segments=[{"seq": 1, "title": "无 material_ids", "content": "段"}],
        referenced_materials=["https://a.com/legacy"],
    )

    detail = await ReviewService(db_session).get_review_detail(review.id)

    assert detail["images"] == ["https://img/legacy.jpg"]
    assert detail["image_total"] == 1


@pytest.mark.asyncio
async def test_images_empty_and_dirty_json(db_session):
    """无图 / images_json 脏数据 → 空数组且不影响详情其他字段。"""
    clean = await _make_material(db_session, "https://a.com/noimg")            # 无 images_json
    dirty = await _make_material(db_session, "https://a.com/dirty", raw="{不是 JSON")  # 脏数据
    review = await _make_review(db_session, [
        {"seq": 1, "material_ids": [clean.id, dirty.id]},
    ])

    detail = await ReviewService(db_session).get_review_detail(review.id)

    assert detail["images"] == []
    assert detail["image_total"] == 0
    # 脏数据不应阻断详情：稿件与状态照常返回
    assert detail["script"]["full_text"] == "稿件全文"
    assert detail["status"] == "pending"


@pytest.mark.asyncio
async def test_images_empty_when_no_material_reference(db_session):
    """既无 material_ids 也无 referenced_materials → images 为空数组（不是 None）。"""
    review = await _make_review(db_session, [{"seq": 1, "content": "段"}])

    detail = await ReviewService(db_session).get_review_detail(review.id)

    assert detail["images"] == []
    assert detail["image_total"] == 0


def test_aggregate_material_images_dedup_and_order():
    """助手单测：跨素材去重、保持首次出现顺序、脏数据按无图处理。"""
    class _M:
        def __init__(self, raw):
            self.images_json = raw

    mats = [
        _M('["u1", "u2"]'),
        _M(None),
        _M('["u2", "u3"]'),
        _M("{坏数据"),
        _M('{"not": "list"}'),
        _M('["u3", "u4", ""]'),
    ]
    assert aggregate_material_images(mats) == ["u1", "u2", "u3", "u4"]
    assert parse_material_images(None) == []
    assert parse_material_images("[]") == []
