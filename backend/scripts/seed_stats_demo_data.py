"""演示/验收用统计样本生成（T02715）。

背景：真实库 play_log 样本极少（单日 1~2 条、1 个用户），完播率是 `avg(completed)`，
样本退化时只会取 0.0 或 1.0 —— 卡片显示 0.0% / 100.0%，趋势是贴底贴顶的方波，
「换算只发生一次」在真数据上根本无法验收（0 和 1 乘不乘 100 都长得像）。

本脚本向**隔离副本库**写入可核对的样本：3 个用户 × 7 天 × 每天 5~10 条播放，
completed 按天混合（每天的完播率都落在 0~1 之间，且今天最高），duration 覆盖
120~900 秒。写入后可起后端核对 PC 卡片 / PC 趋势 / 移动端首页三处数值。

安全边界：
- `--db` 必填，且解析后若指向生产库（app.paths.resolve_db_path()）直接拒绝；
- 只删/只写 openid 前缀为 `demo_t02715_` 的演示用户及其播放记录，不碰真实行；
- 固定随机种子（`--seed`）下结果可复现，重复执行不会叠加（幂等）。

仅用于演示/验收，勿在生产库执行。
"""
import argparse
import json
import os
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.paths import resolve_db_path  # noqa: E402

DEMO_OPENID_PREFIX = "demo_t02715_"
MIN_PLAYS_PER_USER = 5
MAX_PLAYS_PER_USER = 10
MIN_DURATION_SEC = 120
MAX_DURATION_SEC = 900

# 偏移 0 = 今天。递减的目标完播率保证今天既在 0~1 之间、又是 7 天峰值——
# 这样 PC 卡片的当日值、趋势图峰值文案、移动端今日卡片可以逐字符比对。
DAY_COMPLETION_TARGETS = (0.65, 0.60, 0.55, 0.50, 0.45, 0.40, 0.35)
FALLBACK_TARGET = 0.40


class SeedRefused(RuntimeError):
    """不满足隔离/前置条件，拒绝写入（脚本不猜、不兜底）。"""


def _is_production_db(db_path: Path) -> bool:
    production = resolve_db_path()
    try:
        if db_path.resolve() == production.resolve():
            return True
        return db_path.exists() and production.exists() and os.path.samefile(db_path, production)
    except OSError:
        return False


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _require_schema(conn: sqlite3.Connection) -> None:
    names = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = {"user", "episode", "play_log"} - names
    if missing:
        raise SeedRefused(f"目标库缺少表: {', '.join(sorted(missing))}")


def _published_episode_ids(conn: sqlite3.Connection) -> list[int]:
    ids = [
        int(row[0])
        for row in conn.execute(
            "SELECT id FROM episode WHERE status = 'published' ORDER BY id"
        )
    ]
    if not ids:
        raise SeedRefused("目标库没有已发布节目（play_log.episode_id 为必填外键）")
    return ids


def _remove_previous_demo_rows(conn: sqlite3.Connection) -> int:
    demo_ids = [
        int(row[0])
        for row in conn.execute(
            "SELECT id FROM user WHERE openid LIKE ? || '%'", (DEMO_OPENID_PREFIX,)
        )
    ]
    if not demo_ids:
        return 0
    placeholders = ",".join("?" * len(demo_ids))
    conn.execute(f"DELETE FROM play_log WHERE user_id IN ({placeholders})", demo_ids)
    conn.execute(f"DELETE FROM user WHERE id IN ({placeholders})", demo_ids)
    return len(demo_ids)


def _insert_demo_users(conn: sqlite3.Connection, users: int) -> list[int]:
    ids: list[int] = []
    for index in range(users):
        cursor = conn.execute(
            "INSERT INTO user (openid, nickname, total_listen_count, total_listen_duration, disabled) "
            "VALUES (?, ?, 0, 0, 0)",
            (f"{DEMO_OPENID_PREFIX}{index + 1}", f"演示用户{index + 1}"),
        )
        ids.append(int(cursor.lastrowid))
    return ids


def _daily_summary(conn: sqlite3.Connection, start: date, end: date) -> list[dict]:
    rows = conn.execute(
        "SELECT date(played_at), COUNT(DISTINCT user_id), COUNT(*), SUM(completed), "
        "AVG(completed), AVG(duration) FROM play_log "
        "WHERE date(played_at) BETWEEN ? AND ? GROUP BY date(played_at) ORDER BY date(played_at)",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    summary = []
    for day, dau, play_count, completed, rate, avg_duration in rows:
        summary.append(
            {
                "date": str(day),
                "dau": int(dau),
                "play_count": int(play_count),
                "completed": int(completed),
                # 与 StatsService.get_overview 同口径：AVG(completed) 原始值（0~1 比值）
                "completion_rate": float(rate),
                "avg_listen_duration": float(avg_duration),
            }
        )
    return summary


def seed_demo_data(
    db_path: Path,
    *,
    days: int = 7,
    users: int = 3,
    seed: int = 2715,
    today: Optional[date] = None,
) -> dict:
    """向隔离副本库写入演示样本并返回按日聚合（原始单位，与接口一致）。"""
    db_path = Path(db_path)
    if _is_production_db(db_path):
        raise SeedRefused("目标是生产库，拒绝写入；请先复制出隔离副本再指定 --db")
    if not db_path.is_file():
        raise SeedRefused("目标库不存在（本脚本不建库：需要已迁移的副本）")
    if days < 1 or users < 1:
        raise SeedRefused("days/users 必须 >= 1")

    today = today or date.today()
    dates = [today - timedelta(days=offset) for offset in range(days)]

    conn = _connect(db_path)
    try:
        _require_schema(conn)
        episode_ids = _published_episode_ids(conn)
        with conn:
            _remove_previous_demo_rows(conn)
            user_ids = _insert_demo_users(conn, users)

            for offset, day in enumerate(dates):
                rng = random.Random(f"{seed}:{day.isoformat()}")
                plays: list[tuple[int, int, int, str]] = []
                for user_id in user_ids:
                    count = rng.randint(MIN_PLAYS_PER_USER, MAX_PLAYS_PER_USER)
                    for index in range(count):
                        duration = rng.randint(MIN_DURATION_SEC, MAX_DURATION_SEC)
                        # 播放时刻铺在 07:00~20:00，避免同秒聚堆影响阅读
                        hour = 7 + (index * 13) // max(1, count - 1)
                        minute = rng.randint(0, 59)
                        episode_id = episode_ids[(offset + index) % len(episode_ids)]
                        played_at = (
                            f"{day.isoformat()} {hour:02d}:{minute:02d}:00"
                        )
                        plays.append((user_id, episode_id, duration, played_at))

                total = len(plays)
                target = (
                    DAY_COMPLETION_TARGETS[offset]
                    if offset < len(DAY_COMPLETION_TARGETS)
                    else FALLBACK_TARGET
                )
                completed_count = round(total * target)
                # 每天至少各有一条 completed=0 与 =1：完播率必然严格落在 (0, 1)
                completed_count = max(1, min(total - 1, completed_count))
                flags = [1] * completed_count + [0] * (total - completed_count)
                rng.shuffle(flags)

                conn.executemany(
                    "INSERT INTO play_log (user_id, episode_id, position, duration, completed, played_at) "
                    "VALUES (?, ?, 0, ?, ?, ?)",
                    [
                        (user_id, episode_id, duration, flag, played_at)
                        for (user_id, episode_id, duration, played_at), flag in zip(plays, flags)
                    ],
                )

            # 演示用户的累计值按实际写入行回填，避免与 play_log 自相矛盾
            conn.execute(
                f"UPDATE user SET "
                f"total_listen_count = (SELECT COUNT(*) FROM play_log WHERE user_id = user.id), "
                f"total_listen_duration = (SELECT COALESCE(SUM(duration), 0) FROM play_log WHERE user_id = user.id) "
                f"WHERE id IN ({','.join('?' * len(user_ids))})",
                user_ids,
            )

        return {
            "db": str(db_path),
            "seed": seed,
            "users": users,
            "days": days,
            "demo_openid_prefix": DEMO_OPENID_PREFIX,
            "daily": _daily_summary(conn, dates[-1], dates[0]),
        }
    finally:
        conn.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成统计演示样本（仅用于隔离副本库，勿在生产库执行）"
    )
    parser.add_argument("--db", type=Path, required=True, help="隔离副本库路径（必填）")
    parser.add_argument("--days", type=int, default=7, help="生成天数（含今天）")
    parser.add_argument("--users", type=int, default=3, help="演示用户数")
    parser.add_argument("--seed", type=int, default=2715, help="随机种子（固定后结果可复现）")
    parser.add_argument("--today", type=str, default=None, help="锚定日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--json", type=Path, default=None, help="把按日聚合写入 JSON 文件")
    args = parser.parse_args(argv)

    today = None
    if args.today:
        try:
            today = date.fromisoformat(args.today)
        except ValueError:
            print(f"[refuse] 非法日期: {args.today}", file=sys.stderr)
            return 2

    try:
        result = seed_demo_data(
            args.db,
            days=args.days,
            users=args.users,
            seed=args.seed,
            today=today,
        )
    except SeedRefused as exc:
        print(f"[refuse] {exc}", file=sys.stderr)
        return 2

    print(f"库: {result['db']}")
    print(
        f"演示用户 {result['users']} 个（{result['demo_openid_prefix']}*）· "
        f"{result['days']} 天 · seed={result['seed']}"
    )
    print("日期           DAU  播放  completed  完播率(原始)  平均时长(秒)")
    for day in result["daily"]:
        print(
            f"{day['date']}  {day['dau']:>3}  {day['play_count']:>4}  "
            f"{day['completed']:>9}  {day['completion_rate']:>12.6f}  "
            f"{day['avg_listen_duration']:>12.2f}"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"按日聚合已写入: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
