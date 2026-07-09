"""审核服务：审核列表、详情、审批/打回/替换。"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BizError, NotFoundError
from app.core.timeutil import utcnow_naive
from app.models import Review
from app.models.review import ReviewStatus


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_reviews(
        self, status: str, page: int, size: int
    ) -> dict:
        """审核列表分页，status 为空时不过滤。"""
        # 总数独立查询，避免扫描全部数据
        count_stmt = select(func.count(Review.id))
        list_stmt = select(Review)

        # status 可选过滤：传入合法值才加条件，空串视为全部
        if status:
            count_stmt = count_stmt.where(Review.status == status)
            list_stmt = list_stmt.where(Review.status == status)

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 按创建时间倒序，最新审核优先处理
        offset = (page - 1) * size
        result = await self.db.execute(
            list_stmt.order_by(Review.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        reviews = result.scalars().all()

        list_data = [
            {
                "id": r.id,
                "workflow_id": r.workflow_id,
                "episode_date": r.episode_date.isoformat() if r.episode_date else None,
                "script_id": r.script_id,
                "status": r.status if r.status else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ]
        return {"total": total, "list": list_data}

    async def get_review_detail(self, review_id: int) -> dict:
        """审核详情，含关联稿件全文与分段结构。"""
        # selectinload 一次性带出 script，避免详情页二次查询
        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.script))
            .where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        if review is None:
            raise NotFoundError("审核记录不存在")

        script = review.script
        script_data = None
        if script is not None:
            script_data = {
                "full_text": script.full_text,
                "segments": script.segments or [],
                "referenced_materials": script.referenced_materials or [],
                "categories": script.categories or [],
            }

        return {
            "id": review.id,
            "workflow_id": review.workflow_id,
            "episode_date": review.episode_date.isoformat() if review.episode_date else None,
            "script": script_data,
            "audio_url": review.audio_url,
            "status": review.status if review.status else None,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        }

    async def handle_action(
        self,
        review_id: int,
        action: str,
        reviewer_id: int,
        reviewer_name: str,
        reason: str = None,
        segment_id: int = None,
    ) -> dict:
        """处理审核动作：approve / reject / replace。

        返回 need_publish 标识与 workflow_id，由路由层决定是否触发内容发布。
        workflow_id 一并返回避免路由层二次查询 get_review_detail（防止 commit 后
        publish 失败导致的数据不一致与多余查询）。
        """
        result = await self.db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        if review is None:
            raise NotFoundError("审核记录不存在")

        # 已处理的审核记录不允许重复操作，保证审核流单向流转
        if review.status != ReviewStatus.pending:
            raise BizError(code=400, message="该审核记录已处理")

        now = utcnow_naive()

        if action == "approve":
            review.status = ReviewStatus.approved
            need_publish = True
        elif action == "reject":
            # 打回必须填理由，便于编导修改
            if not reason:
                raise BizError(code=400, message="打回必须填写理由")
            review.status = ReviewStatus.rejected
            review.reason = reason
            need_publish = False
        elif action == "replace":
            # 替换需定位到具体分段，segment_id 供路由层调内容服务替换
            if not reason or segment_id is None:
                raise BizError(code=400, message="替换必须填写理由和 segment_id")
            review.status = ReviewStatus.replaced
            review.reason = reason
            need_publish = False
        else:
            raise BizError(code=400, message=f"不支持的审核动作: {action}")

        review.reviewer_id = reviewer_id
        review.reviewer_name = reviewer_name
        review.reviewed_at = now

        await self.db.commit()

        # workflow_id 随返回值带出，路由层无需再查详情
        return {"need_publish": need_publish, "workflow_id": review.workflow_id}
