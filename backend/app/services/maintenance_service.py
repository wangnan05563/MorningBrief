"""系统清理服务（参考 17_xianyu 的 maintenance 模块设计，适配 V1.2 架构）。

职责：
1. 查询存储状态（数据库大小、日志大小、缓存条目数）
2. 清理缓存（TTLCache 进程内缓存、__pycache__ 目录、临时文件）
3. 清理数据库（旧播放日志、旧工作流、旧审核、过期黑名单、旧爬虫去重、旧 AI 用量、旧运营收件箱、VACUUM、无主素材治理）
4. 清理日志文件（旧日志、大日志）

设计要点：
- 所有清理支持 dry_run 预览模式（仅统计不执行）
- days 参数做 max(1, days) 保护，防止 0/负值删全表
- VACUUM 需在 AUTOCOMMIT 隔离级别执行（事务外），使用 engine 独立连接
- 每次清理写 audit_log 表审计日志（持久化，便于事后追溯）
- 文件系统操作使用 asyncio.to_thread 避免阻塞事件循环
"""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select, func, text, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.config import get_settings
from app.core.audit_reason import audit_detail
from app.core.exceptions import NotFoundError, ParamError
from app.core.timeutil import localnow_naive
from app.database import engine
from app.models import (
    AIUsageLog,
    AdminInbox,
    AutoReviewStat,
    BookPoolItem,
    Channel,
    Comment,
    CrawlerDedup,
    Episode,
    Favorite,
    JwtBlacklist,
    Material,
    NotificationLog,
    PlayLog,
    PlayProgress,
    Review,
    Script,
    Workflow,
    WorkflowStep,
)
from app.models.audit_log import AuditLog
from app.paths import get_app_root, resolve_data_dir, resolve_db_path, resolve_log_dir
from app.services import mobile_service

logger = logging.getLogger(__name__)
settings = get_settings()

# 大日志文件阈值（10MB），超过此大小可清理
LARGE_LOG_THRESHOLD_BYTES = 10 * 1024 * 1024
# 活动日志分片的命名（与 logging_setup 的文件 sink 模板一致）
ACTIVE_LOG_GLOB = "MorningBrief_*.log"

# 无主素材预览里列出的样例 ID 上限
ORPHAN_MATERIAL_SAMPLE_LIMIT = 20
# 单条 IN (...) 的 ID 数上限：SQLite 的绑定变量默认上限 999，超了整批清理会直接报错
ORPHAN_MATERIAL_CHUNK = 500


def _chunks(items: list[int]) -> list[list[int]]:
    """切成不超过 ORPHAN_MATERIAL_CHUNK 的分片（空输入返回空列表，不发无意义语句）。"""
    return [
        items[i:i + ORPHAN_MATERIAL_CHUNK]
        for i in range(0, len(items), ORPHAN_MATERIAL_CHUNK)
    ]


# 工作流全链清理的逐表口径：display 顺序 = 删除/统计顺序（子表在前，Workflow 最后）
WORKFLOW_CHAIN_TABLES = {
    "workflow_steps": "工作流步骤",
    "scripts": "稿件",
    "episodes": "节目",
    "reviews": "审核记录",
    "auto_review_stats": "自动审核统计",
    "notification_logs": "通知记录",
    "play_logs": "播放日志",
    "play_progress": "播放进度",
    "comments": "评论",
    "favorites": "收藏",
    "workflows": "工作流",
}


class MaintenanceService:
    """系统清理服务。

    构造函数注入 db 会话（用于审计日志写入与大部分清理操作）。
    VACUUM 需独立连接（不能在事务内），使用 engine.connect()。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ===== 存储状态查询 =====

    async def get_status(self) -> dict:
        """获取当前存储状态。

        返回三类资源的统计：数据库、日志、缓存。
        前端据此展示「是否需要清理」的直观判断。
        """
        db_stats = await self._get_db_stats()
        log_stats = await asyncio.to_thread(self._scan_log_dir)
        cache_stats = await self._get_cache_stats()
        return {
            "db": db_stats,
            "logs": log_stats,
            "cache": cache_stats,
            # 保留窗口交给前端展示，避免页面再写死一个天数（T03329）
            "retention": {
                "admin_inbox_days": max(1, settings.ADMIN_INBOX_KEEP_DAYS),
            },
        }

    async def _get_db_stats(self) -> dict:
        """数据库统计：各表行数 + 数据库文件大小。"""
        db_path = resolve_db_path()
        # 数据库文件大小（含 WAL/SHM 侧文件）
        db_size_mb = 0.0
        if db_path.exists():
            for suffix in ["", "-wal", "-shm"]:
                f = db_path.with_suffix(db_path.suffix + suffix) if suffix else db_path
                if f.exists():
                    db_size_mb += f.stat().st_size / (1024 * 1024)

        # 各表行数统计
        try:
            playlog_count = await self._count_table(PlayLog)
            workflow_count = await self._count_table(Workflow)
            review_count = await self._count_table(Review)
            blacklist_count = await self._count_table(JwtBlacklist)
            dedup_count = await self._count_table(CrawlerDedup)
            ai_usage_count = await self._count_table(AIUsageLog)
            inbox_count = await self._count_table(AdminInbox)
        except Exception as e:
            logger.warning("统计数据库表行数失败: %s", e)
            playlog_count = workflow_count = review_count = 0
            blacklist_count = dedup_count = ai_usage_count = inbox_count = 0

        return {
            "db_size_mb": round(db_size_mb, 2),
            "playlog_count": playlog_count,
            "workflow_count": workflow_count,
            "review_count": review_count,
            "blacklist_count": blacklist_count,
            "dedup_count": dedup_count,
            "ai_usage_count": ai_usage_count,
            "inbox_count": inbox_count,
        }

    async def _get_cache_stats(self) -> dict:
        """缓存统计：TTLCache 条目数 + __pycache__ 目录数 + 临时文件数。"""
        # TTLCache 进程内缓存条目数
        cache_count = len(cache._cache) if hasattr(cache, "_cache") else 0

        # __pycache__ 目录统计
        app_root = get_app_root()
        pycache_stats = await asyncio.to_thread(self._scan_pycache, app_root)

        # 临时文件统计（data 目录下的 .tmp 文件）
        data_dir = resolve_data_dir()
        temp_count = await asyncio.to_thread(self._count_temp_files, data_dir)

        return {
            "ttlcache_count": cache_count,
            "pycache_count": pycache_stats["count"],
            "pycache_mb": pycache_stats["size_mb"],
            "temp_files": temp_count,
        }

    # ===== 缓存清理 =====

    async def cleanup_cache(
        self, target: str, dry_run: bool, admin_name: str, reason: str = ""
    ) -> dict:
        """清理缓存。

        Args:
            target: ttlcache | pycache | temp | all
            dry_run: 仅预览不执行
            admin_name: 操作人（审计日志用）
        """
        cleaned: list[str] = []
        errors: list[str] = []

        if target in ("ttlcache", "all"):
            await self._cache_step_ttlcache(dry_run, cleaned, errors)

        if target in ("pycache", "all"):
            await self._cache_step_pycache(dry_run, cleaned, errors)

        if target in ("temp", "all"):
            await self._cache_step_temp(dry_run, cleaned, errors)

        await self._write_audit(
            "cleanup_cache", target, admin_name, dry_run, cleaned, errors, reason=reason
        )
        return {
            "target": target,
            "dry_run": dry_run,
            "cleaned": cleaned,
            "errors": errors,
        }

    async def _cache_step_ttlcache(self, dry_run, cleaned, errors) -> None:
        """清理 TTLCache 进程内缓存。"""
        try:
            count = len(cache._cache) if hasattr(cache, "_cache") else 0
            if not dry_run and count > 0:
                # 清空 TTLCache：逐个 pop 避免并发问题
                await asyncio.to_thread(self._clear_ttlcache)
            cleaned.append(f"TTLCache {'将清空' if dry_run else '已清空'} {count} 条")
        except Exception as e:
            errors.append(f"TTLCache 清理失败: {e}")
            logger.exception("TTLCache 清理失败")

    @staticmethod
    def _clear_ttlcache() -> None:
        """同步清空 TTLCache 缓存与计数器。"""
        keys = list(cache._cache.keys())
        for k in keys:
            cache._cache.pop(k, None)
        cache._counters.clear()
        cache._counters_ttl.clear()

    async def _cache_step_pycache(self, dry_run, cleaned, errors) -> None:
        """清理 __pycache__ 目录。"""
        try:
            app_root = get_app_root()
            result = await asyncio.to_thread(
                self._cleanup_pycache, app_root, dry_run
            )
            cleaned.append(
                f"__pycache__ {'将清理' if dry_run else '已清理'} "
                f"{result['count']} 个目录（{result['size_mb']:.2f} MB）"
            )
        except Exception as e:
            errors.append(f"__pycache__ 清理失败: {e}")
            logger.exception("__pycache__ 清理失败")

    async def _cache_step_temp(self, dry_run, cleaned, errors) -> None:
        """清理临时文件。"""
        try:
            data_dir = resolve_data_dir()
            result = await asyncio.to_thread(
                self._cleanup_temp_files, data_dir, dry_run
            )
            cleaned.append(
                f"临时文件 {'将删除' if dry_run else '已删除'} "
                f"{result['count']} 个（{result['size_mb']:.2f} MB）"
            )
        except Exception as e:
            errors.append(f"临时文件清理失败: {e}")
            logger.exception("临时文件清理失败")

    # ===== 数据库清理 =====

    async def cleanup_database(
        self, target: str, days: int, dry_run: bool, admin_name: str, reason: str = ""
    ) -> dict:
        """清理数据库。

        Args:
            target: old_playlogs | old_workflows | old_reviews | expired_blacklist
                    | old_dedup | old_ai_usage | old_inbox | vacuum | all
                    | orphan_materials_detach | orphan_materials_delete
                    （后两个是一次性数据治理，不参与 all）
            days: 保留天数（按时间清理时使用，最小值 1）
            dry_run: 仅预览不执行
            admin_name: 操作人（审计日志用）
        """
        # days 最小值保护：防止 0/负值导致删全表
        days = max(1, days)
        cutoff = localnow_naive() - timedelta(days=days)
        cleaned: list[str] = []
        errors: list[str] = []
        total_deleted = 0

        # 时间类清理步骤（共享 cutoff/days 语义）
        time_steps = [
            ("old_playlogs", "播放日志", PlayLog, PlayLog.played_at, ""),
            ("old_workflows", "工作流记录", None, None, ""),
            ("old_reviews", "审核记录", None, None, "，仅已完结"),
            ("old_dedup", "爬虫去重", CrawlerDedup, CrawlerDedup.created_at, ""),
            ("old_ai_usage", "AI 用量日志", AIUsageLog, AIUsageLog.created_at, ""),
        ]
        for key, name, model, time_field, suffix in time_steps:
            if target not in (key, "all"):
                continue
            deleted = await self._run_db_time_step(
                key, name, model, time_field, cutoff, dry_run, days, suffix, errors, cleaned
            )
            total_deleted += deleted

        # 运营收件箱（T03329）：按 created_at 清理，读没读都清——保留窗口的意义是
        # 「过了窗口的提醒不再占位」，与读态无关。与 sched 进程每日任务共用
        # mobile_service.purge_inbox_before，窗口与时间字段只有一处实现。
        if target in ("old_inbox", "all"):
            try:
                if dry_run:
                    deleted = (
                        await self.db.execute(
                            select(func.count(AdminInbox.id)).where(
                                AdminInbox.created_at < cutoff
                            )
                        )
                    ).scalar() or 0
                else:
                    deleted = await mobile_service.purge_inbox_before(self.db, cutoff)
                action = "将删除" if dry_run else "已删除"
                cleaned.append(f"运营收件箱 {action} {deleted} 条（{days} 天前）")
                total_deleted += deleted
            except Exception as e:
                errors.append(f"运营收件箱清理失败: {e}")
                logger.exception("运营收件箱清理失败")

        # 黑名单按 expires_at 清理（不按 days）
        if target in ("expired_blacklist", "all"):
            total_deleted += await self._run_db_step(
                target, "expired_blacklist", "黑名单",
                lambda: self._cleanup_expired_blacklist(dry_run),
                dry_run, cleaned, errors,
            )

        # 无主素材治理（T02598）：按 channel_id 悬空这一条件清理，不按 days。
        # 两个目标都刻意不纳入 all——「全部清理」是例行按时间瘦身，
        # 把「删正文 / 改归属」这种一次性数据治理混进去，一次误点就是数据事故。
        for orphan_key, orphan_action in (
            ("orphan_materials_detach", "detach"),
            ("orphan_materials_delete", "delete"),
        ):
            if target == orphan_key:
                total_deleted += await self._db_step_orphan_materials(
                    target, orphan_action, dry_run, cleaned, errors
                )

        # VACUUM 步骤（消息格式不同）
        if target in ("vacuum", "all"):
            await self._db_step_vacuum(dry_run, cleaned, errors)

        await self._write_audit(
            "cleanup_database", target, admin_name, dry_run, cleaned, errors,
            days=days, reason=reason,
        )
        return {
            "target": target,
            "days": days,
            "dry_run": dry_run,
            "cleaned": cleaned,
            "errors": errors,
            "total_deleted": total_deleted,
        }

    async def _run_db_time_step(
        self, key, name, model, time_field, cutoff, dry_run, days, suffix, errors, cleaned
    ) -> int:
        """执行按时间清理的单个步骤（统一异常处理与消息格式）。

        workflows 和 reviews 有专用清理方法（涉及级联/状态过滤），
        其余通过通用 _cleanup_by_time 按时间字段删除。
        """
        try:
            if key == "old_workflows":
                deleted = await self._cleanup_workflows(cutoff, dry_run)
            elif key == "old_reviews":
                deleted = await self._cleanup_old_reviews(cutoff, dry_run)
            else:
                deleted = await self._cleanup_by_time(model, time_field, cutoff, dry_run)
            action = "将删除" if dry_run else "已删除"
            cleaned.append(f"{name} {action} {deleted} 条（{days} 天前{suffix}）")
            return deleted
        except Exception as e:
            errors.append(f"{name}清理失败: {e}")
            logger.exception(f"{name}清理失败")
            return 0

    async def _run_db_step(
        self, target, key, name, cleanup_fn, dry_run, cleaned, errors
    ) -> int:
        """执行非时间类数据库清理步骤的通用包装。"""
        if target not in (key, "all"):
            return 0
        try:
            deleted = await cleanup_fn()
            action = "将删除" if dry_run else "已删除"
            cleaned.append(f"{name} {action} {deleted} 条")
            return deleted
        except Exception as e:
            errors.append(f"{name}清理失败: {e}")
            logger.exception(f"{name}清理失败")
            return 0

    async def _db_step_vacuum(self, dry_run, cleaned, errors) -> None:
        """执行 VACUUM 步骤（消息格式与删除类不同）。"""
        try:
            freed_mb = await self._vacuum_database(dry_run)
            cleaned.append(
                f"VACUUM {'预览完成' if dry_run else f'已压缩，释放 {freed_mb:.2f} MB'}"
            )
        except Exception as e:
            errors.append(f"VACUUM 失败: {e}")
            logger.exception("VACUUM 失败")

    # ===== 无主素材治理（T02598）=====

    async def _orphan_material_ids(self) -> list[int]:
        """channel_id 有值、但在 channel 表里查无此频道的素材 ID（升序）。

        material.channel_id 没有外键约束（同文件的 workflow/episode 都有），
        所以频道被删过就可能留下悬空值；这些行在按频道筛选的列表与聚合视图里
        永远筛不到，既不展示也不删除，占着库还可能被后续任务误用。
        """
        result = await self.db.execute(
            select(Material.id)
            .where(Material.channel_id.is_not(None))
            .where(Material.channel_id.notin_(select(Channel.id)))
            .order_by(Material.id)
        )
        return [row[0] for row in result.all()]

    async def _count_material_book_pool_refs(self, material_ids: list[int]) -> int:
        """讲书稿书单里引用这批素材的池项数（book_pool_item.material_id 无外键）。"""
        total = 0
        for chunk in _chunks(material_ids):
            result = await self.db.execute(
                select(func.count())
                .select_from(BookPoolItem)
                .where(BookPoolItem.material_id.in_(chunk))
            )
            total += result.scalar() or 0
        return total

    async def _apply_orphan_materials(self, material_ids: list[int], action: str) -> int:
        """按 ID 清单执行解绑或删除，返回实际处理的条数。"""
        applied = 0
        for chunk in _chunks(material_ids):
            if action == "detach":
                await self.db.execute(
                    update(Material).where(Material.id.in_(chunk)).values(channel_id=None)
                )
            else:
                await self.db.execute(delete(Material).where(Material.id.in_(chunk)))
            applied += len(chunk)
        await self.db.commit()
        return applied

    async def _db_step_orphan_materials(
        self, target: str, action: str, dry_run: bool, cleaned: list, errors: list
    ) -> int:
        """无主素材治理步骤：detach 只解绑（素材保留），delete 连正文一起删。

        先取 ID 清单、再按同一份清单执行，预览里的条数与样例和真正改动的行严格一致；
        delete 额外报出书单引用数，避免删完才发现「原来书单还在指它」。
        """
        key = f"orphan_materials_{action}"
        verb = "解绑" if action == "detach" else "删除"
        if target != key:
            return 0
        try:
            ids = await self._orphan_material_ids()
            book_refs = (
                await self._count_material_book_pool_refs(ids) if action == "delete" else 0
            )
            processed = 0 if dry_run else await self._apply_orphan_materials(ids, action)
            head = (
                f"无主素材{verb}：{'将影响' if dry_run else '已处理'} {len(ids)} 条"
                f"（{'channel_id 置空，素材回到全局池' if action == 'detach' else '素材行连同正文一起删除'}）"
            )
            if ids:
                shown = ids[:ORPHAN_MATERIAL_SAMPLE_LIMIT]
                tail = (
                    f"（共 {len(ids)} 条，此处列前 {len(shown)} 条）"
                    if len(ids) > len(shown)
                    else ""
                )
                head += f"；样例 ID {', '.join(map(str, shown))}{tail}"
            else:
                head += "；当前没有 channel_id 悬空的素材"
            if book_refs:
                head += (
                    f"；另有 {book_refs} 条讲书稿书单指向这些素材"
                    "（书单有标题快照，删后仍能展示，但取书范围会少这些书）"
                )
            cleaned.append(head)
            return processed
        except Exception as e:
            errors.append(f"无主素材{verb}失败: {e}")
            logger.exception("无主素材治理失败")
            return 0

    # ===== 日志清理 =====

    async def cleanup_logs(
        self, target: str, days: int, dry_run: bool, admin_name: str, reason: str = ""
    ) -> dict:
        """清理日志文件。

        Args:
            target: old_logs | large_logs | all
            days: 保留天数（old_logs 模式使用，最小值 1）
            dry_run: 仅预览不执行
            admin_name: 操作人（审计日志用）
        """
        days = max(1, days)
        log_dir = resolve_log_dir()
        result = await asyncio.to_thread(
            self._cleanup_log_files, log_dir, target, days, dry_run
        )
        cleaned = result["cleaned"]
        errors = result["errors"]
        total_freed_mb = result["total_freed_mb"]

        await self._write_audit(
            "cleanup_logs", target, admin_name, dry_run, cleaned, errors,
            days=days, reason=reason,
        )
        return {
            "target": target,
            "days": days,
            "dry_run": dry_run,
            "cleaned": cleaned,
            "errors": errors,
            "total_freed_mb": total_freed_mb,
        }

    # ===== 辅助方法：数据库清理 =====

    async def _count_table(self, model) -> int:
        """统计表行数。"""
        result = await self.db.execute(select(func.count()).select_from(model))
        return int(result.scalar() or 0)

    async def _cleanup_by_time(
        self, model, time_field, cutoff: datetime, dry_run: bool
    ) -> int:
        """按时间字段清理表记录（通用方法）。

        dry_run=True 时仅 COUNT，不执行 DELETE。
        """
        if dry_run:
            result = await self.db.execute(
                select(func.count()).select_from(model).where(time_field < cutoff)
            )
            return int(result.scalar() or 0)
        result = await self.db.execute(
            delete(model).where(time_field < cutoff)
        )
        await self.db.commit()
        return result.rowcount or 0

    async def _cleanup_workflows(
        self, cutoff: datetime, dry_run: bool
    ) -> int:
        """清理旧工作流记录，并级联清理其全部子表。

        子表（Script/Review/Episode/AutoReviewStat/NotificationLog/WorkflowStep/
        PlayLog/PlayProgress/Comment/Favorite）的 workflow_id 多为普通字符串列
        （非外键），或直接以 episode_id 关联，删 Workflow 不会自动清理，须手动按
        workflow_id / script_id / episode_id 级联删除，否则悬空数据随定时清理累积。
        仅清理已完结状态（success/failed/cancelled），running 状态不清理。
        """
        from app.models.workflow import WorkflowStatus
        finished_statuses = [
            WorkflowStatus.success.value,
            WorkflowStatus.failed.value,
            WorkflowStatus.cancelled.value,
        ]
        if dry_run:
            result = await self.db.execute(
                select(func.count()).select_from(Workflow).where(
                    Workflow.finished_at < cutoff,
                    Workflow.status.in_(finished_statuses),
                )
            )
            return int(result.scalar() or 0)
        # 先查 ID（用于日志），再删除
        result = await self.db.execute(
            select(Workflow.id).where(
                Workflow.finished_at < cutoff,
                Workflow.status.in_(finished_statuses),
            )
        )
        wf_ids = [row[0] for row in result.all()]
        if not wf_ids:
            return 0

        # 级联清理子表：子表的 workflow_id 多为普通字符串列（非外键），
        # 删 Workflow 不会自动清理，须手动按 workflow_id 删除，否则数据悬空累积。
        # Episode/Review 同时按 script_id 清理，覆盖 workflow_id 为 NULL 的历史孤儿
        # （避免删 Script 时触发 FOREIGN KEY constraint failed）。
        script_ids, episode_ids = await self._workflow_chain_ids(wf_ids)
        return await self._delete_workflow_chain(wf_ids, script_ids, episode_ids)

    async def cleanup_workflow_chain(
        self, workflow_id: str, dry_run: bool, admin_name: str, reason: str = ""
    ) -> dict:
        """按工作流 ID 全链清理（稿件/节目/审核/播放数据等子表一并删除）。

        与 `_cleanup_workflows` 共用同一套级联口径，区别只是选择范围从
        「N 天前的已完结工作流」变成「指定 ID」。运行中/排队中的工作流可能仍被
        worker 写入，拒绝清理；未知 ID 按 404 返回，避免把输错 ID 当成「已清理」。
        """
        from app.models.workflow import WorkflowStatus

        result = await self.db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        wf = result.scalar_one_or_none()
        if wf is None:
            raise NotFoundError(f"工作流不存在: {workflow_id}")
        finished_statuses = {
            WorkflowStatus.success.value,
            WorkflowStatus.failed.value,
            WorkflowStatus.cancelled.value,
        }
        if wf.status not in finished_statuses:
            raise ParamError(
                f"仅已完结的工作流允许全链清理（当前状态：{wf.status}）"
            )

        wf_ids = [workflow_id]
        script_ids, episode_ids = await self._workflow_chain_ids(wf_ids)
        counts = await self._count_workflow_chain(wf_ids, script_ids, episode_ids)
        if not dry_run:
            await self._delete_workflow_chain(wf_ids, script_ids, episode_ids)

        action = "将删除" if dry_run else "已删除"
        cleaned = [
            f"{label} {action} {counts[key]} 条"
            for key, label in WORKFLOW_CHAIN_TABLES.items()
            if counts[key] > 0
        ]
        await self._write_audit(
            "cleanup_workflow_chain", workflow_id, admin_name, dry_run, cleaned, [],
            reason=reason,
        )
        return {
            "target": "workflow_chain",
            "workflow_id": workflow_id,
            "dry_run": dry_run,
            "cleaned": cleaned,
            "errors": [],
            "counts": counts,
            "total_deleted": sum(counts.values()),
        }

    async def _workflow_chain_ids(
        self, wf_ids: list[str]
    ) -> tuple[list[str], list[str]]:
        """收集全链的 script_id / episode_id（含 workflow_id 为 NULL 的孤儿）。"""
        script_result = await self.db.execute(
            select(Script.id).where(Script.workflow_id.in_(wf_ids))
        )
        script_ids = [row[0] for row in script_result.all()]

        ep_result = await self.db.execute(
            select(Episode.id).where(
                or_(
                    Episode.workflow_id.in_(wf_ids),
                    Episode.script_id.in_(script_ids),
                )
            )
        )
        episode_ids = [row[0] for row in ep_result.all()]
        return script_ids, episode_ids

    async def _count_workflow_chain(
        self, wf_ids: list[str], script_ids: list[str], episode_ids: list[str]
    ) -> dict[str, int]:
        """逐表统计全链命中行数；dry-run 与真删共用同一组条件。"""

        async def count(model, condition) -> int:
            result = await self.db.execute(
                select(func.count()).select_from(model).where(condition)
            )
            return int(result.scalar() or 0)

        episode_match = or_(
            Episode.workflow_id.in_(wf_ids),
            Episode.script_id.in_(script_ids),
        )
        review_match = or_(
            Review.workflow_id.in_(wf_ids),
            Review.script_id.in_(script_ids),
        )
        return {
            "workflow_steps": await count(
                WorkflowStep, WorkflowStep.workflow_id.in_(wf_ids)
            ),
            "scripts": await count(Script, Script.workflow_id.in_(wf_ids)),
            "episodes": await count(Episode, episode_match),
            "reviews": await count(Review, review_match),
            "auto_review_stats": await count(
                AutoReviewStat, AutoReviewStat.workflow_id.in_(wf_ids)
            ),
            "notification_logs": await count(
                NotificationLog, NotificationLog.workflow_id.in_(wf_ids)
            ),
            "play_logs": await count(PlayLog, PlayLog.episode_id.in_(episode_ids)),
            "play_progress": await count(
                PlayProgress, PlayProgress.episode_id.in_(episode_ids)
            ),
            "comments": await count(Comment, Comment.episode_id.in_(episode_ids)),
            "favorites": await count(Favorite, Favorite.episode_id.in_(episode_ids)),
            "workflows": await count(Workflow, Workflow.id.in_(wf_ids)),
        }

    async def _delete_workflow_chain(
        self, wf_ids: list[str], script_ids: list[str], episode_ids: list[str]
    ) -> int:
        """删除全链数据并提交，返回删除的 Workflow 行数。

        删除顺序：播放数据/评论/收藏 → Episode → AutoReviewStat → Review →
        NotificationLog → Script → WorkflowStep → Workflow。
        """
        if episode_ids:
            # Comment/Favorite/PlayProgress 的 episode_id 是普通列（无 FK），须随 Episode 清理
            await self.db.execute(
                delete(Comment).where(Comment.episode_id.in_(episode_ids))
            )
            await self.db.execute(
                delete(Favorite).where(Favorite.episode_id.in_(episode_ids))
            )
            await self.db.execute(
                delete(PlayLog).where(PlayLog.episode_id.in_(episode_ids))
            )
            await self.db.execute(
                delete(PlayProgress).where(PlayProgress.episode_id.in_(episode_ids))
            )

        await self.db.execute(
            delete(Episode).where(
                or_(
                    Episode.workflow_id.in_(wf_ids),
                    Episode.script_id.in_(script_ids),
                )
            )
        )
        # AutoReviewStat.review_id 是 RESTRICT 外键指向 review.id，须在 Review 之前清理
        await self.db.execute(
            delete(AutoReviewStat).where(AutoReviewStat.workflow_id.in_(wf_ids))
        )
        await self.db.execute(
            delete(Review).where(
                or_(
                    Review.workflow_id.in_(wf_ids),
                    Review.script_id.in_(script_ids),
                )
            )
        )
        await self.db.execute(
            delete(NotificationLog).where(NotificationLog.workflow_id.in_(wf_ids))
        )
        await self.db.execute(
            delete(Script).where(Script.workflow_id.in_(wf_ids))
        )

        # workflow_step 虽定义 cascade=all,delete-orphan，但此处是 Core 级
        # bulk delete(Workflow)，不会触发 ORM 级联，须显式按 workflow_id 清理
        await self.db.execute(
            delete(WorkflowStep).where(WorkflowStep.workflow_id.in_(wf_ids))
        )
        result = await self.db.execute(
            delete(Workflow).where(Workflow.id.in_(wf_ids))
        )
        await self.db.commit()
        return result.rowcount or 0

    async def _cleanup_old_reviews(
        self, cutoff: datetime, dry_run: bool
    ) -> int:
        """清理旧审核记录（仅已完结状态）。

        pending 状态的审核记录即使超期也不清理，避免丢失待处理任务。
        """
        from app.models.review import ReviewStatus
        finished_statuses = [
            ReviewStatus.approved.value,
            ReviewStatus.rejected.value,
            ReviewStatus.replaced.value,
        ]
        if dry_run:
            result = await self.db.execute(
                select(func.count()).select_from(Review).where(
                    Review.created_at < cutoff,
                    Review.status.in_(finished_statuses),
                )
            )
            return int(result.scalar() or 0)
        result = await self.db.execute(
            delete(Review).where(
                Review.created_at < cutoff,
                Review.status.in_(finished_statuses),
            )
        )
        await self.db.commit()
        return result.rowcount or 0

    async def _cleanup_expired_blacklist(self, dry_run: bool) -> int:
        """清理过期 JWT 黑名单（按 expires_at 字段，不按 days）。"""
        now = localnow_naive()
        if dry_run:
            result = await self.db.execute(
                select(func.count()).select_from(JwtBlacklist).where(
                    JwtBlacklist.expires_at < now
                )
            )
            return int(result.scalar() or 0)
        result = await self.db.execute(
            delete(JwtBlacklist).where(JwtBlacklist.expires_at < now)
        )
        await self.db.commit()
        return result.rowcount or 0

    async def _vacuum_database(self, dry_run: bool) -> float:
        """VACUUM 压缩数据库文件。

        VACUUM 必须在 AUTOCOMMIT 隔离级别执行（不能在事务内），
        否则 SQLite 报错 "cannot VACUUM from within a transaction"。
        因此使用 engine 独立连接，不使用注入的 db session。
        """
        db_path = resolve_db_path()
        size_before = await asyncio.to_thread(self._get_file_size_mb, db_path)

        if dry_run:
            # 预览模式：仅返回当前大小，不执行 VACUUM
            return size_before

        # 使用 AUTOCOMMIT 隔离级别执行 VACUUM（独立连接，不依赖注入的 db）
        async with engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text("VACUUM"))

        size_after = await asyncio.to_thread(self._get_file_size_mb, db_path)
        freed = max(0, size_before - size_after)
        logger.info(
            "VACUUM 完成：%.2f MB → %.2f MB（释放 %.2f MB）",
            size_before, size_after, freed,
        )
        return freed

    # ===== 辅助方法：文件系统操作 =====

    def _get_file_size_mb(self, path: Path) -> float:
        """获取文件大小（MB），文件不存在返回 0。"""
        try:
            return path.stat().st_size / (1024 * 1024)
        except OSError:
            return 0.0

    def _scan_log_dir(self) -> dict:
        """扫描日志目录统计。"""
        log_dir = resolve_log_dir()
        file_count = 0
        total_size = 0
        oldest_mtime: Optional[float] = None

        try:
            for entry in log_dir.iterdir():
                if not entry.is_file():
                    continue
                # 仅统计 .log 和 .log.* 文件
                if not (entry.name.endswith(".log") or ".log." in entry.name):
                    continue
                file_count += 1
                try:
                    stat = entry.stat()
                    total_size += stat.st_size
                    if oldest_mtime is None or stat.st_mtime < oldest_mtime:
                        oldest_mtime = stat.st_mtime
                except OSError:
                    continue
        except OSError as e:
            logger.warning("扫描日志目录失败: %s", e)

        oldest_str = None
        if oldest_mtime is not None:
            oldest_str = datetime.fromtimestamp(oldest_mtime).strftime("%Y-%m-%d")

        return {
            "file_count": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "oldest": oldest_str,
        }

    def _scan_pycache(self, root: Path) -> dict:
        """扫描 __pycache__ 目录统计。"""
        count = 0
        total_size = 0
        # 排除第三方依赖目录，避免误删虚拟环境缓存
        exclude_dirs = {".venv", "venv", "node_modules", ".git", "__pycache__"}

        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # 剪枝：不遍历第三方依赖目录
                dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
                if os.path.basename(dirpath) == "__pycache__":
                    count += 1
                    for fname in filenames:
                        try:
                            total_size += os.path.getsize(
                                os.path.join(dirpath, fname)
                            )
                        except OSError:
                            continue
        except OSError as e:
            logger.warning("扫描 __pycache__ 失败: %s", e)

        return {
            "count": count,
            "size_mb": round(total_size / (1024 * 1024), 2),
        }

    def _count_temp_files(self, data_dir: Path) -> int:
        """统计临时文件数量（.tmp 后缀）。"""
        count = 0
        try:
            for entry in data_dir.iterdir():
                if entry.is_file() and entry.name.endswith(".tmp"):
                    count += 1
        except OSError:
            pass
        return count

    def _cleanup_pycache(self, root: Path, dry_run: bool) -> dict:
        """清理 __pycache__ 目录。"""
        count = 0
        total_size = 0
        exclude_dirs = {".venv", "venv", "node_modules", ".git"}

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
            if os.path.basename(dirpath) != "__pycache__":
                continue
            dir_size = self._sum_file_sizes(dirpath, filenames)
            total_size += dir_size
            count += 1
            if not dry_run:
                self._try_rmtree(dirpath)

        return {
            "count": count,
            "size_mb": round(total_size / (1024 * 1024), 2),
        }

    @staticmethod
    def _sum_file_sizes(dirpath: str, filenames: list[str]) -> int:
        """统计目录内所有文件总大小（忽略单个文件读取失败）。"""
        total = 0
        for fname in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError:
                continue
        return total

    @staticmethod
    def _try_rmtree(dirpath: str) -> None:
        """尝试删除目录，失败时仅记录警告（不影响后续清理）。"""
        try:
            shutil.rmtree(dirpath)
        except OSError as e:
            logger.warning("删除 __pycache__ 失败 %s: %s", dirpath, e)

    def _cleanup_temp_files(self, data_dir: Path, dry_run: bool) -> dict:
        """清理临时文件（.tmp 后缀）。"""
        count = 0
        total_size = 0
        try:
            for entry in data_dir.iterdir():
                if entry.is_file() and entry.name.endswith(".tmp"):
                    try:
                        total_size += entry.stat().st_size
                        count += 1
                        if not dry_run:
                            entry.unlink()
                    except OSError as e:
                        logger.warning("删除临时文件失败 %s: %s", entry, e)
        except OSError as e:
            logger.warning("扫描临时文件失败: %s", e)

        return {
            "count": count,
            "size_mb": round(total_size / (1024 * 1024), 2),
        }

    def _cleanup_log_files(
        self, log_dir: Path, target: str, days: int, dry_run: bool
    ) -> dict:
        """清理日志文件。

        target=old_logs: 按 days 清理旧日志（mtime < cutoff）
        target=large_logs: 清理大日志文件（> 10MB）
        target=all: 同时按天数和大小清理
        """
        cleaned: list[str] = []
        errors: list[str] = []
        total_freed_mb = 0.0
        cutoff_mtime = (datetime.now() - timedelta(days=days)).timestamp()
        # M66：活动分片（loguru 正在写的最新 MorningBrief_*.log）永远不删。
        # 删它不只是「删了正在用的文件」：Windows 上 unlink 直接 PermissionError，
        # POSIX 上句柄继续写但目录里已无此文件，日志静默丢失。
        # 预览与执行走同一函数，所以预览也不会再把它列进「将删除」。
        active_log = self._active_log_file(log_dir)
        active_name = active_log.name if active_log is not None else ""

        try:
            for entry in log_dir.iterdir():
                if not self._is_log_file(entry):
                    continue
                if entry.name == active_name:
                    continue
                should_delete, reason = self._check_log_deletion(
                    entry, target, cutoff_mtime, days
                )
                if should_delete:
                    total_freed_mb += self._delete_log_entry(
                        entry, reason, dry_run, cleaned, errors
                    )
        except OSError as e:
            errors.append(f"扫描日志目录失败: {e}")

        return {
            "cleaned": cleaned,
            "errors": errors,
            "total_freed_mb": round(total_freed_mb, 2),
        }

    @staticmethod
    def _is_log_file(entry) -> bool:
        """判断是否为日志文件（.log 后缀或 .log. 轮转文件）。"""
        if not entry.is_file():
            return False
        return entry.name.endswith(".log") or ".log." in entry.name

    @staticmethod
    def _active_log_file(log_dir: Path):
        """当前正在写入的日志分片：目录里 mtime 最新的 MorningBrief_*.log。

        与 `logging_setup._enforce_dir_quota` 的「保留最新那个」是同一判定口径。
        返回 None 表示目录不可读或没有本系统的日志分片。
        """
        try:
            shards = [
                p for p in log_dir.glob(ACTIVE_LOG_GLOB)
                if p.is_file() and not p.is_symlink()
            ]
        except OSError:
            return None
        if not shards:
            return None

        def _key(p):
            try:
                st = p.stat()
            except OSError:
                return (0.0, p.name)
            return (st.st_mtime, p.name)

        return max(shards, key=_key)

    def _check_log_deletion(
        self, entry, target: str, cutoff_mtime: float, days: int
    ) -> tuple[bool, str]:
        """判断日志文件是否应删除，返回 (是否删除, 原因)。"""
        try:
            stat = entry.stat()
        except OSError:
            return False, ""

        if target in ("old_logs", "all") and stat.st_mtime < cutoff_mtime:
            return True, f"超过 {days} 天"

        if target in ("large_logs", "all") and stat.st_size > LARGE_LOG_THRESHOLD_BYTES:
            size_mb = stat.st_size / (1024 * 1024)
            return True, f"大于 10MB（{size_mb:.1f}MB）"

        return False, ""

    @staticmethod
    def _delete_log_entry(
        entry, reason: str, dry_run: bool, cleaned: list, errors: list
    ) -> float:
        """删除单个日志文件，返回释放的 MB 数。"""
        try:
            size_mb = entry.stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = 0.0

        if not dry_run:
            try:
                entry.unlink()
                cleaned.append(f"已删除 {entry.name}（{reason}）")
            except OSError as e:
                errors.append(f"删除 {entry.name} 失败: {e}")
        else:
            cleaned.append(f"将删除 {entry.name}（{reason}）")
        return size_mb

    # ===== 审计日志 =====

    async def _write_audit(
        self, action: str, target: str, operator: str,
        dry_run: bool, cleaned: list, errors: list, days: int | None = None,
        reason: str = "",
    ) -> None:
        """写入审计日志到 audit_log 表（持久化，便于事后追溯）。

        失败不抛异常（审计日志写入失败不应影响清理操作本身）。
        """
        try:
            detail = {
                "dry_run": dry_run,
                # T02926：按天数执行的清理必须把窗口本身落进审计列，
                # 否则事后只看得到「清过了」，看不到「按几天清的」
                **({"days": days} if days is not None else {}),
                "cleaned_count": len(cleaned),
                "error_count": len(errors),
                "cleaned_items": cleaned[:20],
                "errors": errors[:5],
            }
            log = AuditLog(
                category="maintenance",
                action=action,
                target=target,
                operator=operator,
                detail=audit_detail(detail, reason=reason),
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as e:
            logger.error("写入审计日志失败: %s", e, exc_info=True)
            # 审计日志写入失败不抛异常，清理操作本身已成功
