"""自动审批服务。

设计要点：
- 配置管理：单行配置表（id=1），首次访问自动 seed 默认配置
- 规则匹配：所有启用的规则必须全部命中才触发自动审批（AND 语义）
- 自动审批执行：复用 ReviewService.handle_action 逻辑，但标记 auto_approved=True
- 异常处理：失败时记录 AutoReviewStat + 通过通知系统告警，不阻塞工作流主流程
- 统计：每次自动审批尝试记录一条 AutoReviewStat，含节省时间指标

调用入口：WorkflowScheduler._create_review 创建 Review 后调用 try_auto_approve
"""
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizError
from app.core.timeutil import localnow_naive
from app.database import AsyncSessionLocal
from app.models import (
    AutoReviewConfig, AutoReviewStat, Review, WorkflowStep,
    WorkflowStepName, WorkflowStepStatus, AuditLog, Script,
    Material, Workflow, Channel,
)
from app.models.review import ReviewStatus

logger = logging.getLogger(__name__)

# 系统操作人标识，用于 Review.reviewer_name 和 AuditLog.operator
# 让审批历史明确标记为"系统自动审批"
_SYSTEM_OPERATOR = "system_auto_review"


def evaluate_audiobook_consistency(
    channel_type: str | None,
    sources: list[str] | None,
    segment_material_ids: list[int] | None,
    full_text: str | None,
) -> tuple[bool, str]:
    """听书频道专用一致性校验（T00626 P2，纯函数便于单测）。

    规则（对应《每日听书频道专有流程规范》的验收标准）：
    1. **单书聚焦**：素材来源（书名）去重后应为 1 本，多本即跨书混讲；
    2. **章节衔接**：稿件分段引用的素材顺序应递增（与讲述顺序一致，防乱序拼接）；
    3. **结尾合规**：稿件需含"正版"提醒（引用原著金句的合规要求）。

    非 audiobook 频道直接通过——不改变既有自动审批行为。

    Returns:
        (是否通过, 失败原因)
    """
    if channel_type != "audiobook":
        return True, ""

    books = {str(s).strip() for s in (sources or []) if s and str(s).strip()}
    if len(books) > 1:
        shown = "、".join(sorted(books))[:60]
        return False, f"听书频道要求单书聚焦：本次引用了 {len(books)} 个来源（{shown}）"

    ids = [i for i in (segment_material_ids or []) if isinstance(i, int)]
    if ids != sorted(ids):
        return False, "章节衔接异常：稿件分段顺序与素材顺序不一致（可能存在乱序拼接）"

    if "正版" not in (full_text or ""):
        return False, "结尾缺少正版提醒（讲书合规要求：每集结尾提示支持正版原著）"

    return True, ""


class AutoReviewService:
    """自动审批配置管理与执行服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ===== 配置管理 =====

    async def get_config(self) -> AutoReviewConfig:
        """获取自动审批配置（不存在则 seed 默认值）。

        单行配置表模式：应用层保证仅 id=1 一行，避免重复创建。
        """
        result = await self.db.execute(
            select(AutoReviewConfig).where(AutoReviewConfig.id == 1)
        )
        config = result.scalar_one_or_none()
        if config is None:
            # 首次访问 seed 默认配置，避免启动时强制迁移
            config = AutoReviewConfig(
                id=1,
                enabled=AutoReviewConfig.DEFAULT_ENABLED,
                require_content_safe=AutoReviewConfig.DEFAULT_REQUIRE_CONTENT_SAFE,
                require_steps_first_success=AutoReviewConfig.DEFAULT_REQUIRE_STEPS_FIRST_SUCCESS,
                keyword_whitelist=AutoReviewConfig.DEFAULT_KEYWORD_WHITELIST,
                updated_by=_SYSTEM_OPERATOR,
            )
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)
            logger.info("自动审批配置已 seed 默认值（enabled=False）")
        return config

    @staticmethod
    def parse_keywords(raw: Optional[str]) -> list[str]:
        """白名单 JSON 解析：解析失败按空列表处理（即该规则视为跳过）。"""
        try:
            data = json.loads(raw or "[]")
        except (json.JSONDecodeError, TypeError):
            logger.warning("keyword_whitelist 解析失败，按空列表处理")
            return []
        return data if isinstance(data, list) else []

    @staticmethod
    def split_rules(
        require_content_safe: bool,
        require_steps_first_success: bool,
        keywords: list[str],
    ) -> tuple[list[str], list[str]]:
        """拆出「生效校验」与「显式跳过的校验」（T02492 / FR-UX-204）。

        配置层与运行期护栏共用这一份口径，避免两边各写一遍判断后漂移。
        """
        pairs = (
            ("content_safe", bool(require_content_safe)),
            ("steps_first_success", bool(require_steps_first_success)),
            ("keyword_whitelist", bool(keywords)),
        )
        enforced = [name for name, on in pairs if on]
        skipped = [name for name, on in pairs if not on]
        return enforced, skipped

    async def update_config(
        self,
        enabled: bool,
        require_content_safe: bool,
        require_steps_first_success: bool,
        keyword_whitelist: list[str],
        operator: str,
        risk_acknowledged: bool = False,
    ) -> AutoReviewConfig:
        """更新自动审批配置，记录操作人与时间。

        所有字段必须显式传入，避免部分更新导致配置不一致。

        护栏（T02492 / FR-UX-204）：开启总开关时，既不能三条校验全关
        （那等于「无条件全部命中」，任意内容零检查自动上线），
        也不能缺少管理员的风险确认勾选。

        风险确认可沿用（不必每次保存都重新打勾）的前提是：总开关本来就开着、
        此前已确认过、且跳过的校验没有变多——多关一条就意味着风险面扩大，
        必须重新确认。关闭总开关会清掉确认状态，下次开启需重新确认。
        """
        config = await self.get_config()
        keywords = [str(k).strip() for k in (keyword_whitelist or []) if str(k).strip()]
        enforced, skipped = self.split_rules(
            require_content_safe, require_steps_first_success, keywords,
        )
        _, prev_skipped = self.split_rules(
            config.require_content_safe,
            config.require_steps_first_success,
            self.parse_keywords(config.keyword_whitelist),
        )
        ack_carried = bool(
            enabled and config.enabled and config.risk_acknowledged
            and set(skipped) <= set(prev_skipped)
        )
        # 护栏拒绝走 BizError(code=400)（HTTP 200 + 业务码），与管理端其他业务错误同口径：
        # 响应拦截器只在 code!=0 分支把 message 交给页面，用 ParamError(HTTP400) 会让
        # 前端只剩下「Request failed with status code 400」这句没用的话。
        if enabled:
            if not enforced:
                raise BizError(
                    code=400,
                    message=(
                        "三条校验全部关闭时不能开启自动审批："
                        "至少保留一条校验（内容安全检测 / 步骤一次成功 / 关键词白名单）"
                    ),
                )
            if not risk_acknowledged and not ack_carried:
                if skipped:
                    msg = "开启自动审批前需勾选风险确认：跳过的校验（{}）将不再检查".format(
                        "、".join(skipped),
                    )
                else:
                    msg = "开启自动审批前需勾选风险确认：命中的稿件将绕过人工审核直接发布"
                raise BizError(code=400, message=msg)

        config.enabled = enabled
        config.require_content_safe = require_content_safe
        config.require_steps_first_success = require_steps_first_success
        # 关键词白名单统一序列化为 JSON 字符串存储
        config.keyword_whitelist = json.dumps(keywords, ensure_ascii=False)
        config.updated_by = operator
        config.updated_at = localnow_naive()
        # 风险确认状态：本次勾选=刷新确认人/时间；沿用旧确认=保持不变；其余清空
        acknowledged = bool(risk_acknowledged) or ack_carried
        config.risk_acknowledged = acknowledged
        if risk_acknowledged:
            config.risk_acknowledged_by = operator
            config.risk_acknowledged_at = localnow_naive()
        elif not acknowledged:
            config.risk_acknowledged_by = None
            config.risk_acknowledged_at = None

        # 配置变更记录审计日志，便于追溯谁在何时切换了开关
        self.db.add(AuditLog(
            category="review",
            action="update_auto_review_config",
            target="auto_review_config",
            operator=operator,
            detail=json.dumps({
                "enabled": enabled,
                "require_content_safe": require_content_safe,
                "require_steps_first_success": require_steps_first_success,
                "keyword_whitelist": keywords,
                "risk_acknowledged": acknowledged,
                "risk_ack_carried": ack_carried,
                # 跳过的校验项进审计：出问题时能直接看出这次放行少了哪道检查
                "enforced_rules": enforced,
                "skipped_rules": skipped,
            }, ensure_ascii=False),
        ))
        await self.db.commit()
        await self.db.refresh(config)
        logger.info(
            "自动审批配置已更新 operator=%s enabled=%s",
            operator, enabled,
        )
        return config

    # ===== 规则匹配 =====

    async def _check_content_safe(self, workflow_id: str) -> tuple[bool, str]:
        """规则 1：检查 rewrite 步骤的微信内容安全检测结果。

        检测结果存储在 workflow_step.result.content_security 字段。
        返回 (是否通过, 原因说明)。
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(WorkflowStep.result).where(
                    WorkflowStep.workflow_id == workflow_id,
                    WorkflowStep.step_name == WorkflowStepName.rewrite.value,
                ).order_by(WorkflowStep.id.desc()).limit(1)
            )
            row = result.first()

        if row is None or not row[0]:
            # rewrite 步骤无结果：视为不安全（保守策略，不自动通过）
            return False, "rewrite 步骤无结果，无法验证内容安全"

        step_result = row[0]
        content_security = step_result.get("content_security")
        if not content_security:
            # 未执行内容安全检测：视为不安全
            return False, "未执行内容安全检测"

        # T00914 D11：skipped 表示检测未真实执行（微信 API 失败/凭证缺失），
        # 即使 safe=True 也不能当作"检测通过"放行——否则 40003 类错误会让
        # 违规内容绕过门禁。保守视为不安全，转人工审核兜底。
        if content_security.get("skipped"):
            return False, f"内容安全检测未真实执行（skipped: {content_security.get('error') or '未知原因'}）"

        if not content_security.get("safe"):
            # 检测命中违规：明确不安全
            return False, "内容安全检测命中违规"

        return True, "内容安全检测通过"

    async def _check_steps_first_success(
        self, workflow_id: str,
    ) -> tuple[bool, str]:
        """规则 2：检查前 4 步是否全部一次成功（retry_count=0）。

        重试过的步骤可能掩盖上游不稳定，自动审批前要求一次成功更安全。
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(WorkflowStep).where(
                    WorkflowStep.workflow_id == workflow_id,
                    WorkflowStep.step_name.in_([
                        WorkflowStepName.crawl.value,
                        WorkflowStepName.rewrite.value,
                        WorkflowStepName.tts.value,
                        WorkflowStepName.stitch.value,
                    ]),
                )
            )
            steps = result.scalars().all()

        if len(steps) < 4:
            # 步骤数量不足，说明工作流未完整执行
            return False, f"步骤数量不足（{len(steps)}/4）"

        for step in steps:
            if step.status != WorkflowStepStatus.success.value:
                return False, f"步骤 {step.step_name} 状态非 success"
            if step.retry_count and step.retry_count > 0:
                return False, f"步骤 {step.step_name} 有重试（retry_count={step.retry_count}）"

        return True, "前 4 步全部一次成功"

    async def _check_keyword_whitelist(
        self, workflow_id: str, keywords: list[str],
    ) -> tuple[bool, str]:
        """规则 3：检查稿件是否命中关键词白名单。

        关键词白名单为空时视为不启用此规则（直接通过）。
        命中任一关键词即视为通过。
        """
        if not keywords:
            # 空白名单视为不启用此规则
            return True, "未启用关键词白名单规则"

        # 查询稿件全文用于匹配
        async with AsyncSessionLocal() as session:
            # 先查 review 拿 script_id，再查 script 拿 full_text
            review_result = await session.execute(
                select(Review.script_id).where(Review.workflow_id == workflow_id)
            )
            script_id = review_result.scalar_one_or_none()
            if script_id is None:
                return False, "未找到关联审核记录"

            text_result = await session.execute(
                select(Script.full_text).where(Script.id == script_id)
            )
            full_text = text_result.scalar_one_or_none()

        if not full_text:
            return False, "稿件全文为空，无法匹配关键词"

        # 大小写不敏感匹配
        text_lower = full_text.lower()
        for kw in keywords:
            if kw and kw.lower() in text_lower:
                return True, f"命中关键词: {kw}"

        return False, f"未命中任何白名单关键词（共 {len(keywords)} 个）"

    # ===== 自动审批执行 =====

    async def _check_audiobook_consistency(self, workflow_id: str) -> tuple[bool, str, bool]:
        """T00626 P2：听书频道一致性校验（取库数据后交由纯函数判定）。

        Returns:
            (是否通过, 失败原因, 是否本次校验适用)——applicable=False 表示非听书频道，
            调用方不应把本项计入 matched_rules（避免污染自动审批规则命中记录）。
        """
        async with AsyncSessionLocal() as session:
            channel_type = (await session.execute(
                select(Channel.channel_type)
                .join(Workflow, Workflow.channel_id == Channel.id)
                .where(Workflow.id == workflow_id)
            )).scalar()
            if channel_type != "audiobook":
                return True, "", False

            sources = (await session.execute(
                select(Material.source).where(Material.workflow_id == workflow_id)
            )).scalars().all()

            latest = (await session.execute(
                select(Script.segments, Script.full_text)
                .where(Script.workflow_id == workflow_id)
                .order_by(Script.id.desc()).limit(1)
            )).first()
            seg_json, full_text = (latest if latest else (None, None))
            ids: list[int] = []
            if seg_json:
                try:
                    for seg in json.loads(seg_json):
                        if isinstance(seg, dict):
                            ids.extend(m for m in (seg.get("material_ids") or []) if isinstance(m, int))
                except (json.JSONDecodeError, TypeError):
                    logger.warning("script.segments 解析失败，跳过章节衔接校验 workflow_id=%s", workflow_id)

        ok, msg = evaluate_audiobook_consistency(channel_type, list(sources), ids, full_text)
        return ok, msg, True

    async def try_auto_approve(  # NOSONAR
        self, workflow_id: str, review_id: int, review_created_at: datetime,
    ) -> dict:
        """尝试自动审批（工作流创建 Review 后调用）。

        流程：
        1. 检查开关是否启用
        2. 逐项检查启用的规则（AND 语义：全部命中才通过）
        3. 命中则执行 approve + publish_episode
        4. 失败时记录统计 + 通知管理员，不抛异常（不阻塞工作流）

        返回：{"auto_approved": bool, "reason": str}
        """
        # 1. 检查开关
        config = await self.get_config()
        if not config.enabled:
            return {"auto_approved": False, "reason": "自动审批开关未启用"}

        keywords = self.parse_keywords(config.keyword_whitelist)
        enforced, skipped = self.split_rules(
            config.require_content_safe, config.require_steps_first_success, keywords,
        )

        # 1.5 运行期护栏（T02492）：库内可能仍存着改造前遗留的「开启 + 三条全关」配置，
        # 那种组合下 matched_rules 与 fail_reasons 皆空 → 旧逻辑会零检查放行。
        # 校验项为零时一律不自动通过，转人工，并把原因写进统计供追溯。
        if not enforced:
            guard_msg = "无生效校验规则（三条校验均关闭），已拒绝自动通过并转人工审核"
            await self._record_stat(
                review_id=review_id,
                workflow_id=workflow_id,
                success=False,
                trigger_reason=json.dumps(
                    {"skipped_rules": skipped, "guard": "no_enforced_rule"},
                    ensure_ascii=False,
                ),
                error_message=guard_msg,
                time_saved_sec=None,
            )
            logger.warning(
                "自动审批被护栏拦截 workflow_id=%s review_id=%s 原因=%s",
                workflow_id, review_id, guard_msg,
            )
            return {"auto_approved": False, "reason": guard_msg}

        # 2. 规则匹配（收集命中的规则与失败原因）
        matched_rules: list[str] = []
        fail_reasons: list[str] = []

        if config.require_content_safe:
            ok, msg = await self._check_content_safe(workflow_id)
            if ok:
                matched_rules.append("content_safe")
            else:
                fail_reasons.append(msg)

        if config.require_steps_first_success:
            ok, msg = await self._check_steps_first_success(workflow_id)
            if ok:
                matched_rules.append("steps_first_success")
            else:
                fail_reasons.append(msg)

        if keywords:
            ok, msg = await self._check_keyword_whitelist(workflow_id, keywords)
            if ok:
                matched_rules.append("keyword_whitelist")
            else:
                fail_reasons.append(msg)

        # 3. T00626 P2：听书频道专用校验（非 audiobook 频道 applicable=False，不影响既有行为）
        ok, msg, applicable = await self._check_audiobook_consistency(workflow_id)
        if not ok:
            fail_reasons.append(msg)
        elif applicable:
            matched_rules.append("audiobook_consistency")

        # 4. 任一规则失败则不自动审批
        if fail_reasons:
            fail_msg = "; ".join(fail_reasons)
            await self._record_stat(
                review_id=review_id,
                workflow_id=workflow_id,
                success=False,
                trigger_reason=json.dumps({"failed_rules": fail_reasons}, ensure_ascii=False),
                error_message=fail_msg,
                time_saved_sec=None,
            )
            logger.info(
                "自动审批未触发 workflow_id=%s review_id=%s 原因=%s",
                workflow_id, review_id, fail_msg,
            )
            return {"auto_approved": False, "reason": fail_msg}

        # 4. 全部规则命中，执行自动审批
        try:
            episode_id = await self._execute_auto_approve(
                review_id, workflow_id, matched_rules, review_created_at, skipped,
            )
            logger.info(
                "自动审批成功 workflow_id=%s review_id=%s episode_id=%s",
                workflow_id, review_id, episode_id,
            )
            return {"auto_approved": True, "episode_id": episode_id}
        except Exception as exc:
            # 自动审批失败：记录统计 + 通知管理员，不抛异常避免影响工作流
            logger.exception(
                "自动审批执行失败 workflow_id=%s review_id=%s",
                workflow_id, review_id,
            )
            await self._record_stat(
                review_id=review_id,
                workflow_id=workflow_id,
                success=False,
                trigger_reason=json.dumps(
                    {"matched_rules": matched_rules, "skipped_rules": skipped},
                    ensure_ascii=False,
                ),
                error_message=str(exc),
                time_saved_sec=None,
            )
            # 异步通知管理员，不等待结果
            try:
                await self._notify_admin_failure(workflow_id, review_id, str(exc))
            except Exception:
                logger.warning("通知管理员失败，已忽略")
            return {"auto_approved": False, "reason": f"执行失败: {exc}"}

    async def _execute_auto_approve(
        self,
        review_id: int,
        workflow_id: str,
        matched_rules: list[str],
        review_created_at: datetime,
        skipped_rules: Optional[list[str]] = None,
    ) -> int:
        """执行自动审批通过操作并发布节目。

        复用 ContentService.publish_episode 完成节目发布。
        标记 Review.auto_approved=True 与 auto_trigger_reason，
        使审批历史明确区分系统自动审批与人工审批。
        trigger_reason 同时记录「命中」与「显式跳过」的校验项（T02492），
        事后看一条自动通过就能知道这次放行少查了什么。
        """
        from app.services.content_service import ContentService

        now = localnow_naive()
        skipped_rules = skipped_rules or []
        trigger_reason_json = json.dumps(
            {"matched_rules": matched_rules, "skipped_rules": skipped_rules},
            ensure_ascii=False,
        )

        async with AsyncSessionLocal() as session:
            # 锁定审核记录，确保状态变更原子性
            result = await session.execute(
                select(Review).where(Review.id == review_id).with_for_update()
            )
            review = result.scalar_one_or_none()
            if review is None:
                raise RuntimeError(f"审核记录不存在 review_id={review_id}")

            if review.status != ReviewStatus.pending.value:
                # 已被处理（可能被手动审核抢先）：跳过自动审批
                raise RuntimeError(
                    f"审核记录已被处理 status={review.status}，跳过自动审批"
                )

            # 标记为系统自动审批
            review.status = ReviewStatus.approved.value
            review.reviewer_id = None
            review.reviewer_name = _SYSTEM_OPERATOR
            review.reviewed_at = now
            review.auto_approved = True
            review.auto_trigger_reason = trigger_reason_json
            await session.commit()

            # 发布节目（复用 ContentService，确保缓存失效等逻辑一致）
            content_svc = ContentService(session)
            episode_id = await content_svc.publish_episode(
                workflow_id=workflow_id, review_id=review_id,
            )

            # 记录审计日志，与人工审批保持一致的追溯链路
            session.add(AuditLog(
                category="review",
                action="auto_approve",
                target=str(review_id),
                operator=_SYSTEM_OPERATOR,
                detail=json.dumps({
                    "review_id": review_id,
                    "action": "approve",
                    "matched_rules": matched_rules,
                    "skipped_rules": skipped_rules,
                    "episode_id": episode_id,
                    "workflow_id": workflow_id,
                }, ensure_ascii=False),
            ))
            await session.commit()

        # 计算节省时间：从 review 创建到自动审批完成
        time_saved = int((now - review_created_at).total_seconds()) if review_created_at else 0
        await self._record_stat(
            review_id=review_id,
            workflow_id=workflow_id,
            success=True,
            trigger_reason=trigger_reason_json,
            error_message=None,
            time_saved_sec=time_saved,
        )

        # 发送发布通知（与人工审批一致）
        try:
            from app.services.notification import get_notification_sender
            sender = get_notification_sender()
            await sender.send_workflow_event("workflow.published", workflow_id)
        except Exception:
            logger.warning("发布通知发送失败 workflow_id=%s", workflow_id)

        return episode_id

    async def _record_stat(
        self,
        review_id: Optional[int],
        workflow_id: str,
        success: bool,
        trigger_reason: Optional[str],
        error_message: Optional[str],
        time_saved_sec: Optional[int],
    ) -> None:
        """记录自动审批执行统计。

        独立 session 提交，避免与主流程事务耦合。
        """
        try:
            async with AsyncSessionLocal() as session:
                stat = AutoReviewStat(
                    review_id=review_id,
                    workflow_id=workflow_id,
                    success=success,
                    trigger_reason=trigger_reason,
                    error_message=error_message,
                    time_saved_sec=time_saved_sec,
                )
                session.add(stat)
                await session.commit()
        except Exception as exc:
            # 统计记录失败不应影响主流程
            logger.exception("记录自动审批统计失败: %s", exc)

    async def _notify_admin_failure(
        self, workflow_id: str, review_id: int, error: str,
    ) -> None:
        """自动审批失败时通知管理员手动干预。

        复用现有通知系统（NotifierHub），不引入新的通知通道。
        """
        try:
            from app.services.notification import get_notification_sender
            sender = get_notification_sender()
            # 自定义事件类型，模板可在通知配置页配置
            await sender.send_workflow_event(
                "workflow.auto_review_failed", workflow_id,
                {"review_id": review_id, "error_message": error},
            )
        except Exception:
            logger.warning("通知管理员失败 workflow_id=%s", workflow_id)

    # ===== 统计查询 =====

    async def get_stats(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None,
    ) -> dict:
        """获取自动审批统计指标。

        默认统计最近 7 天，可按日期范围过滤。
        返回：总数、成功数、失败数、成功率、平均节省时间、总节省时间。
        """
        if start_date is None:
            start_date = localnow_naive().date() - timedelta(days=7)
        if end_date is None:
            end_date = localnow_naive().date() + timedelta(days=1)

        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.min.time())

        async with AsyncSessionLocal() as session:
            # 总数与成功率
            base_filter = AutoReviewStat.created_at.between(start_dt, end_dt)
            total_result = await session.execute(
                select(func.count(AutoReviewStat.id)).where(base_filter)
            )
            total = total_result.scalar() or 0

            success_result = await session.execute(
                select(func.count(AutoReviewStat.id)).where(
                    base_filter, AutoReviewStat.success.is_(True),
                )
            )
            success_count = success_result.scalar() or 0

            # 节省时间统计（仅成功的记录）
            time_result = await session.execute(
                select(
                    func.avg(AutoReviewStat.time_saved_sec),
                    func.sum(AutoReviewStat.time_saved_sec),
                ).where(
                    base_filter,
                    AutoReviewStat.success.is_(True),
                    AutoReviewStat.time_saved_sec.isnot(None),
                )
            )
            avg_time, total_time = time_result.first()
            avg_time = int(avg_time) if avg_time else 0
            total_time = int(total_time) if total_time else 0

            # 失败原因分布（按 error_message 分组，取前 5）
            fail_result = await session.execute(
                select(
                    AutoReviewStat.error_message,
                    func.count(AutoReviewStat.id),
                ).where(
                    base_filter, AutoReviewStat.success.is_(False),
                ).group_by(AutoReviewStat.error_message).order_by(
                    func.count(AutoReviewStat.id).desc(),
                ).limit(5)
            )
            fail_distribution = [
                {"reason": r[0] or "", "count": r[1]}
                for r in fail_result
            ]

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total": total,
            "success_count": success_count,
            "failed_count": total - success_count,
            "success_rate": round(success_count / total, 4) if total > 0 else 0.0,
            "avg_time_saved_sec": avg_time,
            "total_time_saved_sec": total_time,
            "fail_distribution": fail_distribution,
        }

    async def list_history(
        self,
        page: int = 1,
        size: int = 20,
        success: Optional[bool] = None,
    ) -> dict:
        """获取自动审批执行历史（分页）。

        按创建时间倒序，可按成功/失败过滤。
        """
        count_stmt = select(func.count(AutoReviewStat.id))
        list_stmt = select(AutoReviewStat)

        if success is not None:
            count_stmt = count_stmt.where(AutoReviewStat.success.is_(success))
            list_stmt = list_stmt.where(AutoReviewStat.success.is_(success))

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        list_result = await self.db.execute(
            list_stmt.order_by(AutoReviewStat.created_at.desc())
            .offset(offset).limit(size)
        )
        stats = list_result.scalars().all()

        return {
            "total": total,
            "list": [
                {
                    "id": s.id,
                    "review_id": s.review_id,
                    "workflow_id": s.workflow_id,
                    "success": s.success,
                    "trigger_reason": s.trigger_reason,
                    "error_message": s.error_message,
                    "time_saved_sec": s.time_saved_sec,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in stats
            ],
        }
