"""T02845：ADMIN_INITIAL_PASSWORD 真的接线（修前是死配置）。

两条 seed 路径各测一遍，因为它们是不共享的代码：
- 启动 seed：app.main._seed_default_admin（首次启动 / 删库后重启）
- 构建期 seed：seed_admin.seed（scripts/build-exe.ps1 5.3.1 预置 dist 数据库）
只测其中一条时，另一条退回 admin123 也照样全绿。

另外两条边界：
- 库里已有 admin 时改 .env 不得改口令（两条路径都靠 COUNT 早退）；
- 构建日志与终端输出不得回显自定义口令。

get_settings 带 lru_cache，改完环境变量必须 cache_clear，否则读到的是
进程里第一次加载的 .env；teardown 也要恢复环境后再清一次，避免污染后续测试。
"""
import sqlite3

import pytest
from sqlalchemy import create_engine

import app.config as config_module
import app.paths as paths_module
import seed_admin
from app.core.security import verify_password
from app.main import _seed_default_admin
from app.models.admin_user import AdminUser

ENV_PASSWORD = "Env-Only-Initial-Pw-4711"
NEXT_ENV_PASSWORD = "Second-Env-Pw-9982"


def _prepare_db(db_path) -> None:
    """按生产模型建表，避免测试自己抄一份 DDL 与 models 漂移。"""
    engine = create_engine(f"sqlite:///{db_path}")
    AdminUser.__table__.create(engine)
    engine.dispose()


def _password_hash(db_path) -> str:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT password_hash FROM admin_user WHERE username = 'admin'"
        ).fetchone()[0]
    finally:
        conn.close()


def _admin_count(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM admin_user WHERE username = 'admin'"
        ).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def env_password(monkeypatch):
    """设置（或清空）ADMIN_INITIAL_PASSWORD 并刷新 lru_cache。"""

    def _apply(value):
        if value is None:
            monkeypatch.delenv("ADMIN_INITIAL_PASSWORD", raising=False)
        else:
            monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", value)
        config_module.get_settings.cache_clear()

    yield _apply
    monkeypatch.undo()
    config_module.get_settings.cache_clear()


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "news.db"
    _prepare_db(db_path)
    monkeypatch.setattr(paths_module, "resolve_db_path", lambda: db_path)
    return db_path


async def test_startup_seed_uses_env_password(db, env_password):
    env_password(ENV_PASSWORD)

    await _seed_default_admin()

    stored = _password_hash(db)
    assert verify_password(ENV_PASSWORD, stored)
    assert not verify_password("admin123", stored)


async def test_startup_seed_blank_env_falls_back_to_admin123(db, env_password):
    env_password(None)

    await _seed_default_admin()

    stored = _password_hash(db)
    assert verify_password("admin123", stored)


async def test_startup_seed_keeps_existing_admin_password(db, env_password):
    env_password(ENV_PASSWORD)
    await _seed_default_admin()
    first = _password_hash(db)

    # 改 .env 后重启：已有账号不能被这条路径改口令
    env_password(NEXT_ENV_PASSWORD)
    await _seed_default_admin()

    assert _password_hash(db) == first
    assert _admin_count(db) == 1
    assert verify_password(ENV_PASSWORD, first)
    assert not verify_password(NEXT_ENV_PASSWORD, first)


def test_build_seed_uses_env_password_without_echoing_it(tmp_path, env_password, capsys):
    db_path = tmp_path / "dist.db"
    env_password(ENV_PASSWORD)

    assert seed_admin.seed(str(db_path)) is True

    captured = capsys.readouterr()
    assert ENV_PASSWORD not in captured.out
    assert ENV_PASSWORD not in captured.err
    assert verify_password(ENV_PASSWORD, _password_hash(db_path))


def test_build_seed_explicit_password_wins(tmp_path, env_password):
    db_path = tmp_path / "dist.db"
    env_password(ENV_PASSWORD)

    seed_admin.seed(str(db_path), password="Explicit-One-33")

    stored = _password_hash(db_path)
    assert verify_password("Explicit-One-33", stored)
    assert not verify_password(ENV_PASSWORD, stored)
