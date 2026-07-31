"""审核服务：审核列表、详情、审批/打回/替换。"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BizError, NotFoundError
from app.core.timeutil import utcnow_naive
from app.models import Review
from app.models.review import ReviewStatus

# 审核记录不存在的统一提示，集中管理避免多处硬编码字符串不一致
_REVIEW_NOT_FOUND_MSG = "审核记录不存在"


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_reviews(
        self, status: str, page: int, size: int,
        workflow_id: str = None,
    ) -> dict:
        """审核列表分页，status/workflow_id 为空时不过滤。"""
        # 总数独立查询，避免扫描全部数据
        count_stmt = select(func.count(Review.id))
        list_stmt = select(Review)

        # status 可选过滤：传入合法值才加条件，空串视为全部
        if status:
            count_stmt = count_stmt.where(Review.status == status)
            list_stmt = list_stmt.where(Review.status == status)

        # workflow_id 可选过滤：工作流详情页按工作流查审核记录
        if workflow_id:
            count_stmt = count_stmt.where(Review.workflow_id == workflow_id)
            list_stmt = list_stmt.where(Review.workflow_id == workflow_id)

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
                # 自动审批标记：前端据此显示"系统自动"标签
                "auto_approved": bool(r.auto_approved),
                "reviewer_name": r.reviewer_name,
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
            raise NotFoundError(_REVIEW_NOT_FOUND_MSG)

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
            # 自动审批标记与触发原因，详情页展示追溯信息
            "auto_approved": bool(review.auto_approved),
            "auto_trigger_reason": review.auto_trigger_reason,
            "reviewer_name": review.reviewer_name,
            "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
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
            raise NotFoundError(_REVIEW_NOT_FOUND_MSG)

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

    # 批量审批单次上限：防止一次性操作过多导致事务过长或 LLM/TTS 等下游过载
    BATCH_MAX_SIZE = 50

    async def batch_handle_action(
        self,
        review_ids: list[int],
        action: str,
        reviewer_id: int,
        reviewer_name: str,
        reason: str = None,
    ) -> dict:
        """批量处理审核动作。

        设计要点：
        - 仅允许 approve / reject 批量操作；replace 需 segment_id 不适合批量
        - 每条独立 commit，保证部分成功可生效；单条失败不影响其他
        - 已处理的记录归入 skipped 而非 failed，便于前端区分展示
        - 上限由 BATCH_MAX_SIZE 控制，超出拒绝整批
        """
        if action not in ("approve", "reject"):
            raise BizError(code=400, message="批量操作仅支持 approve/reject")
        if action == "reject" and not reason:
            raise BizError(code=400, message="批量打回必须填写理由")
        if not review_ids:
            raise BizError(code=400, message="review_ids 不能为空")
        if len(review_ids) > self.BATCH_MAX_SIZE:
            raise BizError(
                code=400,
                message=f"批量操作上限 {self.BATCH_MAX_SIZE} 条，当前 {len(review_ids)} 条",
            )

        succeeded: list[dict] = []
        failed: list[dict] = []
        skipped: list[dict] = []

        for rid in review_ids:
            try:
                result = await self.handle_action(
                    review_id=rid,
                    action=action,
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer_name,
                    reason=reason,
                )
                succeeded.append({
                    "id": rid,
                    "workflow_id": result["workflow_id"],
                    "need_publish": result["need_publish"],
                })
            except NotFoundError:
                failed.append({"id": rid, "reason": _REVIEW_NOT_FOUND_MSG})
            except BizError as exc:
                # 已处理记录归类为 skipped，便于前端提示用户
                if "已处理" in exc.message:
                    skipped.append({"id": rid, "reason": exc.message})
                else:
                    failed.append({"id": rid, "reason": exc.message})

        return {
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "total": len(review_ids),
        }
