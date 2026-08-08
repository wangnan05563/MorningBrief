"""回填脚本：从 play_progress 表回填 play_log 表历史数据。

为什么需要：
- 旧版 play_service.report_progress 不写 PlayLog（仅写 play_progress），
  导致用量统计页面所有指标显示为 0（play_log 表 0 行）。
- 新版 report_progress 已修复（直接 self.db.add(PlayLog)），
  但历史数据需本脚本回填，否则历史趋势图与 DAU 永远为 0。

回填策略：
1. 从 play_progress 表读取所有 position >= PLAY_COUNT_THRESHOLD_SEC 的记录
2. 按 (user_id, episode_id) 幂等检查 play_log 是否已有记录
3. 缺失则插入 PlayLog，played_at 取 play_progress.updated_at（最后上报时间）
4. 同步累加 user.total_listen_count（与新版 report_progress 逻辑一致）
5. user.total_listen_duration 用 play_progress.position 作为下限近似值
   （旧版未记录 listened_seconds 增量，无法精确恢复，按 position 累加是保守估计）

符合规范：
- R100 批量数据回填脚本：dry_run + 分批 + 幂等 + 进度输出
- R166 sqlite3 表结构预检查：PRAGMA table_info 确认列名
- R170 SQLite 时间字段写入显式赋值：played_at 显式赋值，不依赖默认值
- R64 dry_run 预览模式：默认 dry_run=True，需 --apply 才实际写入

用法：
    # 预览模式（默认，不写入）
    python -m app.scripts.backfill_play_log

    # 实际执行回填
    python -m app.scripts.backfill_play_log --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# 复用项目时区工具：所有时间字段存为本地 naive datetime（香港 UTC+8）
# 避免与 stats_service 查询窗口（datetime.combine 本地时间）冲突
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.timeutil import localnow_naive  # noqa: E402
from app.paths import resolve_db_path  # noqa: E402


def _table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    """R166 sqlite3 表结构预检查：返回表的列名列表，避免臆测列名。"""
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def _fetch_progress_rows(
    cur: sqlite3.Cursor, threshold: int
) -> list[dict]:
    """读取 play_progress 表中 position >= threshold 的记录。

    只回填达到播放阈值的记录，与新版 report_progress 的写入条件一致：
    position >= PLAY_COUNT_THRESHOLD_SEC 才插入 PlayLog。
    """
    cols = _table_columns(cur, "play_progress")
    # R166 预检查列名，避免臆测
    required = ["id", "user_id", "episode_id", "position", "duration", "completed", "updated_at"]
    missing = [c for c in required if c not in cols]
    if missing:
        raise RuntimeError(f"play_progress 表缺少列: {missing}")

    cur.execute(
        "SELECT id, user_id, episode_id, position, duration, completed, updated_at "
        "FROM play_progress WHERE position >= ? ORDER BY id",
        (threshold,),
    )
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "episode_id": r[2],
            "position": r[3],
            "duration": r[4],
            "completed": r[5],
            "updated_at": r[6],
        }
        for r in cur.fetchall()
    ]


def _existing_playlog_keys(cur: sqlite3.Cursor) -> set[tuple[Optional[int], int]]:
    """读取 play_log 已有的 (user_id, episode_id) 集合，用于幂等检查。

    幂等设计：每用户每节目仅一条 PlayLog（与新版 report_progress upsert 语义一致），
    重复运行本脚本不会重复插入。
    """
    cols = _table_columns(cur, "play_log")
    if "user_id" not in cols or "episode_id" not in cols:
        # play_log 表不存在或结构异常：视为空集合，全部回填
        return set()
    cur.execute("SELECT user_id, episode_id FROM play_log")
    return {(r[0], r[1]) for r in cur.fetchall()}


def _parse_updated_at(raw: object) -> str:
    """将 play_progress.updated_at 标准化为 play_log.played_at 字符串。

    play_progress.updated_at 由旧版 report_progress 写入，可能为：
    - datetime.now(timezone.utc) 旧版（UTC，带时区后缀或 naive UTC）
    - localnow_naive() 新版（本地 naive）
    - SQLite CURRENT_TIMESTAMP（UTC 字符串）

    回填策略：优先尝试解析为 ISO 格式，失败则用当前本地时间兜底。
    历史时间的精度损失可接受（统计按日聚合，不依赖小时级精度）。
    """
    if raw is None:
        return localnow_naive().isoformat()
    s = str(raw)
    try:
        # 兼容 '2026-07-15 14:25:41.671089' 与 ISO 8601 两种格式
        # datetime.fromisoformat 在 Python 3.11+ 支持 'YYYY-MM-DD HH:MM:SS.ffffff'
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # 去除时区信息后存为 naive（与项目本地 naive datetime 约定一致）
        if dt.tzinfo is not None:
            # UTC 时间转本地时间（+8 小时）：旧版写入的 UTC 时间需校正
            from datetime import timedelta
            dt = dt + timedelta(hours=8)
            dt = dt.replace(tzinfo=None)
        return dt.isoformat()
    except (ValueError, TypeError):
        # 解析失败：用当前时间兜底，避免回填中断
        return localnow_naive().isoformat()


def backfill(dry_run: bool = True, batch_size: int = 100) -> dict:
    """执行回填。

    Args:
        dry_run: True 仅预览不写入；False 实际写入
        batch_size: 单批处理上限（数据量大时分批提交事务）

    Returns:
        统计字典：{scanned, existing, inserted, users_updated, total_listen_count_added}
    """
    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # 阈值从配置读取，避免硬编码（R1 配置驱动）
    try:
        from app.config import get_settings
        threshold = get_settings().PLAY_COUNT_THRESHOLD_SEC
    except Exception:
        # 配置加载失败时用默认值 30，不阻断回填
        threshold = 30

    print(f"[backfill] 数据库: {db_path}")
    print(f"[backfill] 播放阈值: {threshold}s (PLAY_COUNT_THRESHOLD_SEC)")
    print(f"[backfill] 模式: {'预览（dry_run）' if dry_run else '实际写入'}")
    print()

    progress_rows = _fetch_progress_rows(cur, threshold)
    existing_keys = _existing_playlog_keys(cur)

    stats = {
        "scanned": len(progress_rows),
        "existing": 0,
        "inserted": 0,
        "users_updated": 0,
        "total_listen_count_added": 0,
    }

    # 用户维度累加：{user_id: episode_count} 用于更新 user.total_listen_count
    user_count_incr: dict[int, int] = {}
    # 用户维度收听时长近似累加（position 之和）：保守估计
    user_duration_incr: dict[int, int] = {}

    to_insert: list[tuple] = []
    for row in progress_rows:
        key = (row["user_id"], row["episode_id"])
        if key in existing_keys:
            stats["existing"] += 1
            continue
        played_at_str = _parse_updated_at(row["updated_at"])
        to_insert.append(
            (
                row["user_id"],
                row["episode_id"],
                row["position"],
                row["duration"],
                row["completed"],
                played_at_str,
            )
        )
        # 累加该用户的统计
        if row["user_id"] is not None:
            user_count_incr[row["user_id"]] = user_count_incr.get(row["user_id"], 0) + 1
            # 用 position 作为收听时长近似值（旧版未记录增量，这是保守下限估计）
            user_duration_incr[row["user_id"]] = (
                user_duration_incr.get(row["user_id"], 0) + (row["position"] or 0)
            )

    stats["inserted"] = len(to_insert)
    stats["users_updated"] = len(user_count_incr)
    stats["total_listen_count_added"] = sum(user_count_incr.values())

    # 打印回填预览
    print(f"[backfill] 待回填 play_log 记录数: {stats['inserted']}")
    print(f"[backfill] 已存在跳过数: {stats['existing']}")
    print(f"[backfill] 待更新 user 数: {stats['users_updated']}")
    print(f"[backfill] 待累加 total_listen_count 总数: {stats['total_listen_count_added']}")
    print()

    if dry_run:
        # 预览模式：打印前 10 条样例
        print("[backfill] 预览前 10 条待插入记录（played_at | user_id | episode_id | position | duration | completed）：")
        for r in to_insert[:10]:
            print(f"  {r[5]} | user={r[0]} | ep={r[1]} | pos={r[2]} | dur={r[3]} | done={r[4]}")
        if len(to_insert) > 10:
            print(f"  ... 其余 {len(to_insert) - 10} 条省略")
        print()
        print("[backfill] 预览模式未写入任何数据。如需实际执行，添加 --apply 参数。")
        conn.close()
        return stats

    # 实际写入：分批提交，避免单次事务过大（R100 批量数据回填脚本规范）
    inserted_total = 0
    for i in range(0, len(to_insert), batch_size):
        batch = to_insert[i : i + batch_size]
        cur.executemany(
            "INSERT INTO play_log (user_id, episode_id, position, duration, completed, played_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            batch,
        )
        inserted_total += len(batch)
        conn.commit()
        print(f"[backfill] 已插入批次 {i // batch_size + 1}: +{len(batch)} 条（累计 {inserted_total}）")

    # 更新 user 表统计字段
    for user_id, count_incr in user_count_incr.items():
        duration_incr = user_duration_incr.get(user_id, 0)
        cur.execute(
            "UPDATE user SET total_listen_count = total_listen_count + ?, "
            "total_listen_duration = total_listen_duration + ? WHERE id = ?",
            (count_incr, duration_incr, user_id),
        )
    conn.commit()
    print()
    print(f"[backfill] user 表更新完成：{len(user_count_incr)} 个用户")
    print(f"[backfill] 回填完成：play_log 插入 {inserted_total} 条")

    conn.close()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="从 play_progress 回填 play_log 历史数据")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际执行回填（默认 dry_run 预览模式，不写入）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="单批处理上限（默认 100）",
    )
    args = parser.parse_args()

    stats = backfill(dry_run=not args.apply, batch_size=args.batch_size)
    # 非 0 退出码仅在异常时使用；正常完成（含 dry_run 无数据）返回 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
