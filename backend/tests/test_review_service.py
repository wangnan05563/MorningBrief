"""审核服务测试。

覆盖 services/review_service.py：
- list_reviews：按状态过滤 + 分页
- handle_action：approve/reject/replace 状态流转 + 无效 action 抛异常
"""
from datetime import date

import pytest

from app.core.exceptions import BizError, NotFoundError
from app.models import Script, Review, ReviewStatus
from app.services.review_service import ReviewService


async def _create_review(
    db, status=ReviewStatus.pending, workflow_id="wf-001", episode_date=None
):
    """辅助：创建一条 review 记录（含关联 script）。"""
    script = Script(
        workflow_id=workflow_id,
        episode_date=episode_date or date.today(),
        full_text="稿件全文",
        segments=[{"seq": 1, "content": "段"}],
    )
    db.add(script)
    await db.flush()

    review = Review(
        workflow_id=workflow_id,
        episode_date=episode_date or date.today(),
        script_id=script.id,
        audio_url="http://cdn/test.mp3",
        status=status,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


@pytest.mark.asyncio
async def test_list_reviews_filter_by_status(db_session):
    """list_reviews 按 status 过滤：只返回匹配状态的记录。"""
    await _create_review(db_session, status=ReviewStatus.pending)
    await _create_review(db_session, status=ReviewStatus.pending, workflow_id="wf-002")
    await _create_review(db_session, status=ReviewStatus.approved, workflow_id="wf-003")

    svc = ReviewService(db_session)
    # 只查 pending
    pending = await svc.list_reviews(status="pending", page=1, size=10)
    assert pending["total"] == 2
    assert len(pending["list"]) == 2
    for item in pending["list"]:
        assert item["status"] == "pending"

    # 只查 approved
    approved = await svc.list_reviews(status="approved", page=1, size=10)
    assert approved["total"] == 1
    assert approved["list"][0]["status"] == "approved"


@pytest.mark.asyncio
async def test_list_reviews_no_status_returns_all(db_session):
    """status 为空时返回全部记录。"""
    await _create_review(db_session, status=ReviewStatus.pending)
    await _create_review(db_session, status=ReviewStatus.approved, workflow_id="wf-002")

    svc = ReviewService(db_session)
    result = await svc.list_reviews(status="", page=1, size=10)
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_list_reviews_pagination(db_session):
    """分页：total 与每页条数正确。"""
    for i in range(5):
        await _create_review(db_session, workflow_id=f"wf-{i:03d}")

    svc = ReviewService(db_session)
    page1 = await svc.list_reviews(status="", page=1, size=2)
    assert page1["total"] == 5
    assert len(page1["list"]) == 2

    page3 = await svc.list_reviews(status="", page=3, size=2)
    assert len(page3["list"]) == 1


@pytest.mark.asyncio
async def test_handle_action_approve(db_session):
    """approve 后状态变 approved，返回 need_publish=True + workflow_id。"""
    review = await _create_review(db_session)

    svc = ReviewService(db_session)
    result = await svc.handle_action(
        review_id=review.id,
        action="approve",
        reviewer_id=1,
        reviewer_name="admin",
    )

    assert result["need_publish"] is True
    assert result["workflow_id"] == "wf-001"

    # DB 中状态已更新
    await db_session.refresh(review)
    assert review.status == ReviewStatus.approved
    assert review.reviewer_id == 1
    assert review.reviewer_name == "admin"
    assert review.reviewed_at is not None


@pytest.mark.asyncio
async def test_handle_action_reject(db_session):
    """reject 后状态变 rejected，need_publish=False，reason 被记录。"""
    review = await _create_review(db_session)

    svc = ReviewService(db_session)
    result = await svc.handle_action(
        review_id=review.id,
        action="reject",
        reviewer_id=1,
        reviewer_name="admin",
        reason="内容不合规",
    )

    assert result["need_publish"] is False
    await db_session.refresh(review)
    assert review.status == ReviewStatus.rejected
    assert review.reason == "内容不合规"


@pytest.mark.asyncio
async def test_handle_action_reject_without_reason_raises(db_session):
    """reject 必须填写理由，否则抛 BizError。"""
    review = await _create_review(db_session)

    svc = ReviewService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.handle_action(
            review_id=review.id,
            action="reject",
            reviewer_id=1,
            reviewer_name="admin",
            reason=None,
        )
    assert "理由" in exc_info.value.message


@pytest.mark.asyncio
async def test_handle_action_invalid_raises(db_session):
    """无效 action 抛 BizError，状态不变。"""
    review = await _create_review(db_session)

    svc = ReviewService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.handle_action(
            review_id=review.id,
            action="invalid-action",
            reviewer_id=1,
            reviewer_name="admin",
        )
    assert "不支持" in exc_info.value.message

    # 状态仍为 pending
    await db_session.refresh(review)
    assert review.status == ReviewStatus.pending


@pytest.mark.asyncio
async def test_handle_action_review_not_found_raises(db_session):
    """review_id 不存在时抛 NotFoundError。"""
    svc = ReviewService(db_session)
    with pytest.raises(NotFoundError):
        await svc.handle_action(
            review_id=99999,
            action="approve",
            reviewer_id=1,
            reviewer_name="admin",
        )


@pytest.mark.asyncio
async def test_handle_action_on_processed_review_raises(db_session):
    """已处理的 review 不允许重复操作。"""
    review = await _create_review(db_session, status=ReviewStatus.approved)

    svc = ReviewService(db_session)
    with pytest.raises(BizError) as exc_info:
        await svc.handle_action(
            review_id=review.id,
            action="approve",
            reviewer_id=1,
            reviewer_name="admin",
        )
    assert "已处理" in exc_info.value.message


@pytest.mark.asyncio
async def test_handle_action_replace(db_session):
    """replace 后状态变 replaced，需提供 reason + segment_id。"""
    review = await _create_review(db_session)

    svc = ReviewService(db_session)
    result = await svc.handle_action(
        review_id=review.id,
        action="replace",
        reviewer_id=1,
        reviewer_name="admin",
        reason="段落需替换",
        segment_id=2,
    )

    assert result["need_publish"] is False
    await db_session.refresh(review)
    assert review.status == ReviewStatus.replaced
    assert review.reason == "段落需替换"
