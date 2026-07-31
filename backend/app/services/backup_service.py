"""SQLite 数据库备份服务。

每日凌晨执行，使用 VACUUM INTO 创建紧凑的备份副本，
保留最近 N 天，过期备份自动清理。

设计要点：
1. VACUUM INTO（SQLite 3.27+）比文件复制更可靠：
   - 生成紧凑文件（清理碎片与 WAL），体积通常 < 原文件
   - 一致性快照：备份过程中若有写入，备份反映的是备份开始时刻的状态
   - 不会阻塞主库写入（读锁级别）
2. 必须在 AUTOCOMMIT 隔离级别执行：VACUUM 系列语句不能在事务内运行
3. 文件系统操作用 asyncio.to_thread 包装，避免阻塞事件循环
4. 备份目录通过 paths.py 解析，打包态/开发态路径一致
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import text

from app.database import engine
from app.paths import resolve_data_dir

logger = logging.getLogger(__name__)

# 备份文件命名模式：news_backup_YYYYMMDD_HHMMSS.db
_BACKUP_NAME_PATTERN = re.compile(r"^news_backup_(\d{8})_(\d{6})\.db$")

# 备份文件保留天数（与 MAINTENANCE_DEDUP_RETAIN_DAYS 等保持一致的 7 天窗口）
_DEFAULT_KEEP_DAYS = 7


def _resolve_backup_dir() -> Path:
    """解析备份目录路径：data/backup/。

    复用 resolve_data_dir() 保证打包态/开发态路径解析一致，
    避免备份数据落到 PyInstaller 临时解压目录被升级时清除。
    """
    backup_dir = resolve_data_dir() / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


class BackupService:
    """SQLite 数据库备份服务。

    每日凌晨执行，使用 VACUUM INTO 创建紧凑的备份副本，
    保留最近 7 天，过期备份自动清理。
    """

    @staticmethod
    async def backup_database() -> str:
        """执行数据库备份，返回备份文件路径。

        使用 VACUUM INTO 'path' 创建紧凑副本：
        - 一致性快照，备份期间不阻塞写入
        - 自动清理碎片，备份文件通常比原文件小
        - 失败时抛异常，由调用方决定重试/告警策略
        """
        # 时间戳用本地时区（Asia/Shanghai），便于运维识别备份归属的工作日
        # 数据库内时间用 UTC（见 utcnow_naive），但文件名用本地时间更直观
        from app.config import get_settings
        settings = get_settings()
        tz_name = settings.APP_TIMEZONE
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name)
            now_local = datetime.now(tz)
        except Exception:
            # 退化到无时区时间（与历史备份命名兼容）
            now_local = datetime.now()

        timestamp = now_local.strftime("%Y%m%d_%H%M%S")
        backup_dir = _resolve_backup_dir()
        backup_path = backup_dir / f"news_backup_{timestamp}.db"

        # VACUUM INTO 必须在 AUTOCOMMIT 隔离级别执行
        # SQLite 的 VACUUM 语句不能在事务内运行，否则报 "cannot VACUUM from within a transaction"
        # 用 engine.connect() 独立连接，不依赖请求级 session
        # 路径需用单引号包裹（SQLite SQL 语法要求字符串字面量）
        # 注意：Windows 路径含反斜杠，SQLite 会将 \ 视为转义字符，需用正斜杠 / 或双反斜杠
        sqlite_path = str(backup_path).replace("\\", "/")
        sql = f"VACUUM INTO '{sqlite_path}'"

        try:
            async with engine.connect() as conn:
                await conn.execution_options(isolation_level="AUTOCOMMIT")
                await conn.execute(text(sql))
        except Exception:
            logger.exception("数据库备份失败 path=%s", backup_path)
            # 清理可能产生的不完整备份文件
            try:
                await asyncio.to_thread(_safe_unlink, backup_path)
            except Exception:
                pass
            raise

        size_mb = await asyncio.to_thread(_get_file_size_mb, backup_path)
        logger.info("数据库备份完成 path=%s size=%.2fMB", backup_path, size_mb)
        return str(backup_path)

    @staticmethod
    async def cleanup_old_backups(keep_days: int = _DEFAULT_KEEP_DAYS) -> int:
        """清理过期备份，返回清理的文件数。

        按 backup 文件名中的时间戳判断保留窗口，而非文件 mtime：
        原因是文件复制/移动会改变 mtime，而文件名时间戳是备份生成时刻的稳定记录。
        """
        backup_dir = _resolve_backup_dir()
        # 列目录操作可能阻塞，放到线程池
        entries = await asyncio.to_thread(_list_dir_safe, backup_dir)
        if not entries:
            return 0

        # 计算保留截止时间（文件名时间戳 < cutoff 的删除）
        # 用本地日期计算，与备份文件命名时区一致
        cutoff = datetime.now() - timedelta(days=keep_days)
        cutoff_str = cutoff.strftime("%Y%m%d")

        deleted = 0
        for entry in entries:
            match = _BACKUP_NAME_PATTERN.match(entry.name)
            if not match:
                continue
            # 文件名中的 YYYYMMDD 部分与 cutoff 比较（字符串比较等价于日期比较）
            backup_date_str = match.group(1)
            if backup_date_str < cutoff_str:
                try:
                    await asyncio.to_thread(_safe_unlink, entry.path)
                    deleted += 1
                    logger.info("已清理过期备份 %s", entry.name)
                except Exception as e:
                    logger.warning("清理过期备份失败 %s: %s", entry.name, e)

        if deleted > 0:
            logger.info("过期备份清理完成，共删除 %d 个文件", deleted)
        return deleted

    @staticmethod
    async def list_backups() -> list[dict]:
        """列出可用备份。

        返回按文件名降序排列的备份列表（最新在前），
        包含文件名、路径、大小、修改时间，供管理后台展示。
        """
        backup_dir = _resolve_backup_dir()
        entries = await asyncio.to_thread(_list_dir_safe, backup_dir)
        if not entries:
            return []

        backups: list[dict] = []
        for entry in entries:
            match = _BACKUP_NAME_PATTERN.match(entry.name)
            if not match:
                continue
            stat = await asyncio.to_thread(_get_stat_dict, entry.path)
            backups.append({
                "filename": entry.name,
                "path": str(entry.path),
                "size_mb": round(stat["size_mb"], 2),
                "created_at": stat["mtime_iso"],
            })

        # 按文件名降序（最新备份在前）
        backups.sort(key=lambda b: b["filename"], reverse=True)
        return backups

    @staticmethod
    async def restore_backup(backup_path: str) -> bool:  # NOSONAR
        """从备份恢复数据库。

        恢复策略：
        1. 校验备份文件存在且为合法备份文件名
        2. 关闭当前 engine 释放对原数据库文件的句柄（SQLite 文件锁）
        3. 用备份文件覆盖当前数据库文件（先备份当前库以防恢复失败）
        4. 删除 WAL/SHM 侧文件（旧 WAL 与新 db 不一致会导致数据错乱）

        警告：恢复操作会丢失自备份以来所有数据，仅管理员可执行。
        """
        backup_file = Path(backup_path)
        if not backup_file.is_file():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        if not _BACKUP_NAME_PATTERN.match(backup_file.name):
            raise ValueError(f"非法备份文件名: {backup_file.name}")

        # 当前数据库路径
        from app.paths import resolve_db_path
        db_path = resolve_db_path()

        # 恢复前先关闭 engine，释放文件句柄（Windows 下文件被占用会失败）
        try:
            await engine.dispose()
        except Exception as e:
            logger.warning("恢复前关闭 engine 失败（继续尝试恢复）: %s", e)

        # 备份当前数据库（恢复失败时可回滚）
        pre_restore_backup: Optional[Path] = None
        if db_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = db_path.parent / f"news_pre_restore_{timestamp}.db"
            try:
                await asyncio.to_thread(_copy_file, db_path, pre_restore_backup)
            except Exception as e:
                logger.warning("恢复前备份当前库失败（继续恢复）: %s", e)
                pre_restore_backup = None

        # 执行恢复：覆盖数据库文件 + 清理 WAL/SHM
        try:
            await asyncio.to_thread(_copy_file, backup_file, db_path)
            # 清理 WAL/SHM 侧文件：新 db 文件不带 WAL，旧的 WAL 会导致数据不一致
            for suffix in ("-wal", "-shm"):
                side_file = db_path.with_suffix(db_path.suffix + suffix)
                if side_file.exists():
                    await asyncio.to_thread(_safe_unlink, side_file)
        except Exception as e:
            # 恢复失败：尝试回滚到恢复前状态
            logger.exception("恢复数据库失败")
            if pre_restore_backup and pre_restore_backup.exists():
                try:
                    await asyncio.to_thread(_copy_file, pre_restore_backup, db_path)
                    logger.info("已回滚到恢复前状态")
                except Exception as rollback_err:
                    logger.error("回滚失败: %s", rollback_err)
            raise

        # 清理恢复前的临时备份
        if pre_restore_backup and pre_restore_backup.exists():
            try:
                await asyncio.to_thread(_safe_unlink, pre_restore_backup)
            except Exception:
                pass

        logger.info("数据库已从备份恢复 source=%s target=%s", backup_path, db_path)
        return True


# ===== 文件系统辅助函数（在线程池中执行） =====
# 这些函数是同步的 blocking IO，必须通过 asyncio.to_thread 调用，避免阻塞事件循环

def _get_file_size_mb(path: Path) -> float:
    """获取文件大小（MB），文件不存在返回 0。"""
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def _safe_unlink(path: Path) -> None:
    """安全删除文件，不存在不报错。"""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _list_dir_safe(directory: Path) -> list[Path]:
    """列出目录下所有文件，目录不存在返回空列表。"""
    if not directory.exists():
        return []
    return [p for p in directory.iterdir() if p.is_file()]


def _get_stat_dict(path: Path) -> dict:
    """获取文件统计信息（大小 + 修改时间）。"""
    try:
        stat = path.stat()
        return {
            "size_mb": stat.st_size / (1024 * 1024),
            "mtime_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }
    except OSError:
        return {"size_mb": 0.0, "mtime_iso": ""}


def _copy_file(src: Path, dst: Path) -> None:
    """复制文件（含元数据）。

    用 shutil.copy2 而非 copyfile：保留 mtime 等元数据，
    便于备份文件追溯原始备份时刻。
    """
    import shutil
    # 确保目标目录存在
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
