"""系统清理服务（参考 17_xianyu 的 maintenance 模块设计，适配 V1.2 架构）。

职责：
1. 查询存储状态（数据库大小、日志大小、缓存条目数）
2. 清理缓存（TTLCache 进程内缓存、__pycache__ 目录、临时文件）
3. 清理数据库（旧播放日志、旧工作流、旧审核、过期黑名单、旧爬虫去重、旧 AI 用量、VACUUM）
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

from sqlalchemy import delete, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.config import get_settings
from app.core.timeutil import utcnow_naive
from app.database import engine
from app.models import (
    AIUsageLog,
    CrawlerDedup,
    JwtBlacklist,
    PlayLog,
    Review,
    Workflow,
)
from app.models.audit_log import AuditLog
from app.paths import get_app_root, resolve_data_dir, resolve_db_path, resolve_log_dir

logger = logging.getLogger(__name__)
settings = get_settings()

# 大日志文件阈值（10MB），超过此大小可清理
LARGE_LOG_THRESHOLD_BYTES = 10 * 1024 * 1024


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
        except Exception as e:
            logger.warning("统计数据库表行数失败: %s", e)
            playlog_count = workflow_count = review_count = 0
            blacklist_count = dedup_count = ai_usage_count = 0

        return {
            "db_size_mb": round(db_size_mb, 2),
            "playlog_count": playlog_count,
            "workflow_count": workflow_count,
            "review_count": review_count,
            "blacklist_count": blacklist_count,
            "dedup_count": dedup_count,
            "ai_usage_count": ai_usage_count,
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
        self, target: str, dry_run: bool, admin_name: str
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
            try:
                count = len(cache._cache) if hasattr(cache, "_cache") else 0
                if not dry_run and count > 0:
                    # 清空 TTLCache：逐个 pop 避免并发问题
                    keys = list(cache._cache.keys())
                    for k in keys:
                        cache._cache.pop(k, None)
                    # 同时清空计数器
                    cache._counters.clear()
                    cache._counters_ttl.clear()
                cleaned.append(f"TTLCache {'将清空' if dry_run else '已清空'} {count} 条")
            except Exception as e:
                errors.append(f"TTLCache 清理失败: {e}")
                logger.exception("TTLCache 清理失败")

        if target in ("pycache", "all"):
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

        if target in ("temp", "all"):
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

        await self._write_audit("cleanup_cache", target, admin_name, dry_run, cleaned, errors)
        return {
            "target": target,
            "dry_run": dry_run,
            "cleaned": cleaned,
            "errors": errors,
        }

    # ===== 数据库清理 =====

    async def cleanup_database(
        self, target: str, days: int, dry_run: bool, admin_name: str
    ) -> dict:
        """清理数据库。

        Args:
            target: old_playlogs | old_workflows | old_reviews | expired_blacklist
                    | old_dedup | old_ai_usage | vacuum | all
            days: 保留天数（按时间清理时使用，最小值 1）
            dry_run: 仅预览不执行
            admin_name: 操作人（审计日志用）
        """
        # days 最小值保护：防止 0/负值导致删全表
        days = max(1, days)
        cutoff = utcnow_naive() - timedelta(days=days)
        cleaned: list[str] = []
        errors: list[str] = []
        total_deleted = 0

        if target in ("old_playlogs", "all"):
            try:
                deleted = await self._cleanup_by_time(
                    PlayLog, PlayLog.played_at, cutoff, dry_run
                )
                total_deleted += deleted
                cleaned.append(
                    f"播放日志 {'将删除' if dry_run else '已删除'} {deleted} 条"
                    f"（{days} 天前）"
                )
            except Exception as e:
                errors.append(f"播放日志清理失败: {e}")
                logger.exception("播放日志清理失败")

        if target in ("old_workflows", "all"):
            try:
                deleted = await self._cleanup_workflows(cutoff, dry_run)
                total_deleted += deleted
                cleaned.append(
                    f"工作流记录 {'将删除' if dry_run else '已删除'} {deleted} 条"
                    f"（{days} 天前）"
                )
            except Exception as e:
                errors.append(f"工作流清理失败: {e}")
                logger.exception("工作流清理失败")

        if target in ("old_reviews", "all"):
            try:
                # 仅清理已完结状态（approved/rejected/replaced）的旧审核记录
                # pending 状态的审核记录即使超期也不清理，避免丢失待处理任务
                deleted = await self._cleanup_old_reviews(cutoff, dry_run)
                total_deleted += deleted
                cleaned.append(
                    f"审核记录 {'将删除' if dry_run else '已删除'} {deleted} 条"
                    f"（{days} 天前，仅已完结）"
                )
            except Exception as e:
                errors.append(f"审核记录清理失败: {e}")
                logger.exception("审核记录清理失败")

        if target in ("expired_blacklist", "all"):
            try:
                # 黑名单按 expires_at 清理（JWT 原始过期时间），不按 days
                deleted = await self._cleanup_expired_blacklist(dry_run)
                total_deleted += deleted
                cleaned.append(
                    f"过期黑名单 {'将删除' if dry_run else '已删除'} {deleted} 条"
                )
            except Exception as e:
                errors.append(f"黑名单清理失败: {e}")
                logger.exception("黑名单清理失败")

        if target in ("old_dedup", "all"):
            try:
                deleted = await self._cleanup_by_time(
                    CrawlerDedup, CrawlerDedup.created_at, cutoff, dry_run
                )
                total_deleted += deleted
                cleaned.append(
                    f"爬虫去重 {'将删除' if dry_run else '已删除'} {deleted} 条"
                    f"（{days} 天前）"
                )
            except Exception as e:
                errors.append(f"爬虫去重清理失败: {e}")
                logger.exception("爬虫去重清理失败")

        if target in ("old_ai_usage", "all"):
            try:
                deleted = await self._cleanup_by_time(
                    AIUsageLog, AIUsageLog.created_at, cutoff, dry_run
                )
                total_deleted += deleted
                cleaned.append(
                    f"AI 用量日志 {'将删除' if dry_run else '已删除'} {deleted} 条"
                    f"（{days} 天前）"
                )
            except Exception as e:
                errors.append(f"AI 用量日志清理失败: {e}")
                logger.exception("AI 用量日志清理失败")

        if target in ("vacuum", "all"):
            try:
                freed_mb = await self._vacuum_database(dry_run)
                cleaned.append(
                    f"VACUUM {'预览完成' if dry_run else f'已压缩，释放 {freed_mb:.2f} MB'}"
                )
            except Exception as e:
                errors.append(f"VACUUM 失败: {e}")
                logger.exception("VACUUM 失败")

        await self._write_audit("cleanup_database", target, admin_name, dry_run, cleaned, errors)
        return {
            "target": target,
            "days": days,
            "dry_run": dry_run,
            "cleaned": cleaned,
            "errors": errors,
            "total_deleted": total_deleted,
        }

    # ===== 日志清理 =====

    async def cleanup_logs(
        self, target: str, days: int, dry_run: bool, admin_name: str
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

        await self._write_audit("cleanup_logs", target, admin_name, dry_run, cleaned, errors)
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
        """清理旧工作流记录（级联删除 workflow_step）。

        workflow_step 通过外键 cascade=all,delete-orphan 自动级联删除。
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
        # workflow_step 通过 cascade 自动删除，无需手动清理
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
        now = utcnow_naive()
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
        except (OSError, FileNotFoundError):
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
            if os.path.basename(dirpath) == "__pycache__":
                dir_size = 0
                for fname in filenames:
                    try:
                        dir_size += os.path.getsize(os.path.join(dirpath, fname))
                    except OSError:
                        continue
                total_size += dir_size
                count += 1
                if not dry_run:
                    try:
                        shutil.rmtree(dirpath)
                    except OSError as e:
                        logger.warning("删除 __pycache__ 失败 %s: %s", dirpath, e)

        return {
            "count": count,
            "size_mb": round(total_size / (1024 * 1024), 2),
        }

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

        try:
            for entry in log_dir.iterdir():
                if not entry.is_file():
                    continue
                if not (entry.name.endswith(".log") or ".log." in entry.name):
                    continue

                try:
                    stat = entry.stat()
                except OSError:
                    continue

                should_delete = False
                reason = ""

                if target in ("old_logs", "all"):
                    if stat.st_mtime < cutoff_mtime:
                        should_delete = True
                        reason = f"超过 {days} 天"

                if target in ("large_logs", "all"):
                    if stat.st_size > LARGE_LOG_THRESHOLD_BYTES:
                        should_delete = True
                        size_mb = stat.st_size / (1024 * 1024)
                        reason = f"大于 10MB（{size_mb:.1f}MB）"

                if should_delete:
                    size_mb = stat.st_size / (1024 * 1024)
                    total_freed_mb += size_mb
                    if not dry_run:
                        try:
                            entry.unlink()
                            cleaned.append(f"已删除 {entry.name}（{reason}）")
                        except OSError as e:
                            errors.append(f"删除 {entry.name} 失败: {e}")
                    else:
                        cleaned.append(f"将删除 {entry.name}（{reason}）")
        except OSError as e:
            errors.append(f"扫描日志目录失败: {e}")

        return {
            "cleaned": cleaned,
            "errors": errors,
            "total_freed_mb": round(total_freed_mb, 2),
        }

    # ===== 审计日志 =====

    async def _write_audit(
        self, action: str, target: str, operator: str,
        dry_run: bool, cleaned: list, errors: list,
    ) -> None:
        """写入审计日志到 audit_log 表（持久化，便于事后追溯）。

        失败不抛异常（审计日志写入失败不应影响清理操作本身）。
        """
        try:
            detail = {
                "dry_run": dry_run,
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
                detail=json.dumps(detail, ensure_ascii=False, default=str),
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as e:
            logger.error("写入审计日志失败: %s", e, exc_info=True)
            # 审计日志写入失败不抛异常，清理操作本身已成功
