"""T02715：统计演示样本生成器的隔离边界与退化红线。

本文件的断言顺序刻意「先钉越权/退化，再核对计数」：
若脚本把演示行写到真实用户上，或把完播率写成 0/1，只断言总数会表现为
`assert 24 == 27` 这类看不出原因的失败，运维/CI 无法判断是哪条红线被突破。
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert, select

from app import models
from app.database import Base, normalize_metadata_for_sqlite
from scripts import seed_stats_demo_data as seeder

ANCHOR = date(2026, 10, 27)
REAL_PLAYED_AT = datetime(2026, 9, 1, 9, 0)  # 窗口外：证明真实行不被改写，也不干扰演示日聚合


def _create_db(path: Path, *, with_episode: bool = True) -> Path:
    normalize_metadata_for_sqlite()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(models.User).values(openid="real_user", nickname="真实用户"))
        if with_episode:
            conn.execute(
                insert(models.Episode).values(
                    date=date(2026, 9, 1),
                    title="真实节目",
                    duration=300,
                    audio_url="http://example.com/a.mp3",
                    status="published",
                )
            )
            user_id = conn.execute(
                select(models.User.id).where(models.User.openid == "real_user")
            ).scalar_one()
            episode_id = conn.execute(select(models.Episode.id)).scalar_one()
            conn.execute(
                insert(models.PlayLog).values(
                    user_id=user_id,
                    episode_id=episode_id,
                    position=10,
                    duration=500,
                    completed=1,
                    played_at=REAL_PLAYED_AT,
                )
            )
    engine.dispose()
    return path


@pytest.fixture
def demo_db(tmp_path):
    return _create_db(tmp_path / "demo.db")


def _seed(db: Path, **overrides):
    options = {"days": 7, "users": 3, "seed": 2715, "today": ANCHOR}
    options.update(overrides)
    return seeder.seed_demo_data(db, **options)


def _query(db: Path, sql: str, params: tuple = ()):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _demo_user_ids(db: Path) -> list[int]:
    return [
        row[0]
        for row in _query(
            db,
            "SELECT id FROM user WHERE openid LIKE ? || '%'",
            (seeder.DEMO_OPENID_PREFIX,),
        )
    ]


def test_refuses_production_db_before_opening(monkeypatch):
    monkeypatch.setattr(
        seeder.sqlite3,
        "connect",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("拒绝分支不应打开任何数据库")),
    )
    assert seeder.main(["--db", str(seeder.resolve_db_path()), "--days", "1"]) == 2


def test_refuses_missing_db(tmp_path):
    missing = tmp_path / "missing.db"
    assert seeder.main(["--db", str(missing)]) == 2
    assert not missing.exists(), "脚本不应自行建库"


def test_refuses_db_without_published_episode(tmp_path):
    empty = _create_db(tmp_path / "no_episode.db", with_episode=False)
    assert seeder.main(["--db", str(empty), "--days", "1"]) == 2
    assert _demo_user_ids(empty) == []


def test_completion_rate_is_not_degenerate(demo_db):
    summary = _seed(demo_db)
    daily = summary["daily"]
    assert len(daily) == 7

    # 红线一：每天的完播率必须是真比例。0/1 会让「换算一次」在真数据上无法验收。
    for day in daily:
        assert 0.0 < day["completion_rate"] < 1.0, (
            f"{day['date']} 完播率退化: {day['completion_rate']}"
        )
        completed = _query(
            demo_db,
            "SELECT MIN(completed), MAX(completed) FROM play_log WHERE date(played_at) = ?",
            (day["date"],),
        )[0]
        assert completed == (0, 1), f"{day['date']} 缺少 completed 混合: {completed}"

    # 红线二：今天必须是峰值，否则「卡片 = 趋势峰值」的三处比对会错位。
    today = daily[-1]
    assert today["date"] == ANCHOR.isoformat()
    assert today["completion_rate"] == max(d["completion_rate"] for d in daily), (
        "今天不是峰值，三处比对会错位"
    )

    # DAU 去重：3 个用户每天 5~10 条，播放数必须严格大于用户数。
    assert today["dau"] == 3
    assert today["play_count"] > today["dau"], "DAU 去重失效：播放数应远大于用户数"
    assert 15 <= today["play_count"] <= 30
    assert 120 <= today["avg_listen_duration"] <= 900


def test_idempotent_rerun(demo_db):
    first = _seed(demo_db)
    counts = _query(demo_db, "SELECT COUNT(*) FROM play_log")[0][0]
    demo_users = _demo_user_ids(demo_db)
    assert len(demo_users) == 3

    second = _seed(demo_db)

    assert _query(demo_db, "SELECT COUNT(*) FROM play_log")[0][0] == counts, "重复执行叠加了播放行"
    assert _demo_user_ids(demo_db) == demo_users, "重复执行重建了演示用户"
    assert second["daily"] == first["daily"], "固定 seed 下结果不可复现"


def test_preserves_non_demo_rows(demo_db):
    real_id = _query(demo_db, "SELECT id FROM user WHERE openid = 'real_user'")[0][0]

    _seed(demo_db)

    # 先钉越权红线：真实行的字段必须逐列原样。
    real_row = _query(
        demo_db,
        "SELECT user_id, position, duration, completed, played_at FROM play_log WHERE user_id = ?",
        (real_id,),
    )
    assert len(real_row) == 1, "真实用户的播放行被删除或复制"
    user_id, position, duration, completed, played_at = real_row[0]
    assert (user_id, position, duration, completed) == (real_id, 10, 500, 1), "真实播放行被改写"
    assert str(played_at).startswith(REAL_PLAYED_AT.strftime("%Y-%m-%d %H:%M:%S")), (
        "真实播放时间被改写"
    )
    assert _query(demo_db, "SELECT nickname FROM user WHERE id = ?", (real_id,))[0][0] == "真实用户"


def test_all_play_rows_in_window_belong_to_demo_users(demo_db):
    summary = _seed(demo_db)
    window = (summary["daily"][0]["date"], summary["daily"][-1]["date"])
    demo_ids = _demo_user_ids(demo_db)
    placeholders = ",".join("?" * len(demo_ids))

    outside = _query(
        demo_db,
        f"SELECT COUNT(*) FROM play_log WHERE date(played_at) BETWEEN ? AND ? "
        f"AND user_id NOT IN ({placeholders})",
        (*window, *demo_ids),
    )[0][0]
    assert outside == 0, "演示窗口内混入了非演示用户的行"

    other_days = _query(
        demo_db,
        f"SELECT COUNT(*) FROM play_log WHERE date(played_at) NOT BETWEEN ? AND ? "
        f"AND user_id IN ({placeholders})",
        (*window, *demo_ids),
    )[0][0]
    assert other_days == 0, "演示行写到了窗口外"
