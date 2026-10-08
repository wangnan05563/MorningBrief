"""进程角色门控测试（T01660 路线 A 前置）。

验证 `APP_ROLE`（all|api|sched）下 lifespan 的职责切分：
- 「整个应用只需跑一次」的副作用 —— 建表/迁移/seed、APScheduler、启动补跑清理、
  隧道 auto_start 及其通知 —— 只在 all/sched 角色执行，api 角色一次都不执行；
- play_write_buffer 与 EventBus 是每进程自己的 asyncio 状态（内存缓冲 / asyncio.Queue），
  三种角色都必须各自启动消费者，否则本进程的进度写与事件无人消费；
- 关闭阶段与启动阶段严格对称（api 不能去停从未启动的调度器/隧道）。

实现方式：把 lifespan 里所有真实副作用换成计数替身，只观察调用次数，
不触碰 SQLite、调度器、隧道子进程与通知通道。
"""
import asyncio
import threading

import pytest
from fastapi import FastAPI

import app.core.event_bus as event_bus_module
import app.database as database_module
import app.main as main_module
import app.services.ai_config_service as ai_config_module
import app.services.backup_service as backup_service_module
import app.services.cos_config_service as cos_config_module
import app.services.notification.template_service as template_service_module
import app.services.play_write_buffer as pwb_module
import app.services.tunnel_notifications as tunnel_notify_module
import app.services.tunnel_service as tunnel_service_module
import app.services.workflow_scheduler as scheduler_module
from app.config import get_settings
from app.main import lifespan

_GATED_PREFIXES = ("_migrate", "_seed")

# 隧道 auto_start 开关（测试用替身读取，避免触碰真实隧道配置与通知）
_AUTO_START = {"value": True}


class _Calls:
    """调用计数容器：按名字记录 lifespan 触达过的副作用。"""

    def __init__(self) -> None:
        self.items: list[str] = []

    def hit(self, name: str) -> None:
        self.items.append(name)

    def count(self, name: str) -> int:
        return self.items.count(name)

    def gated_total(self) -> int:
        """一次性职责（建表/迁移/seed）的调用次数。"""
        return sum(
            1
            for name in self.items
            if name == "_init_sqlite_schema" or name.startswith(_GATED_PREFIXES)
        )


class _FakeBus:
    """EventBus 替身：run_forever 轮询标志位，stop 后快速退出（与真实实现同构）。"""

    def __init__(self, calls: _Calls) -> None:
        self._calls = calls
        self._stopped = False

    async def run_forever(self) -> None:
        self._calls.hit("event_bus.run_forever")
        while not self._stopped:
            await asyncio.sleep(0.01)

    def stop(self) -> None:
        self._stopped = True
        self._calls.hit("event_bus.stop")


class _FakeTunnelService:
    def __init__(self, calls: _Calls) -> None:
        self._calls = calls
        self.on_started = None

    def get_config(self) -> dict:
        return {"auto_start": _AUTO_START["value"]}

    def start(self) -> str:
        self._calls.hit("tunnel.start")
        url = "https://tunnel.invalid"
        if self.on_started:
            self.on_started(url)
        return url

    def stop(self) -> None:
        self._calls.hit("tunnel.stop")


class _SyncThread:
    """替身线程：同步执行 target，让断言不依赖调度时机。"""

    def __init__(self, target=None, daemon=None, **kwargs) -> None:
        self._target = target

    def start(self) -> None:
        if self._target:
            self._target()


@pytest.fixture
def calls(monkeypatch):
    """替换 lifespan 的全部真实副作用，返回调用计数器。"""
    c = _Calls()

    def _async_noop(name: str):
        async def _fn(*args, **kwargs):
            c.hit(name)

        return _fn

    # 建表 / 迁移 / seed：app.main 里的模块级私有函数（按前缀枚举，新增迁移自动覆盖）
    monkeypatch.setattr(main_module, "_init_sqlite_schema", _async_noop("_init_sqlite_schema"))
    for attr in dir(main_module):
        if attr.startswith(_GATED_PREFIXES):
            monkeypatch.setattr(main_module, attr, _async_noop(attr))

    # 日志初始化会重排 loguru sink，测试里不需要真实日志文件
    monkeypatch.setattr(main_module, "setup_logging", lambda *a, **k: c.hit("setup_logging"))

    # 任何走 DB session 的初始化都替换成替身（AI/COS 配置、模板 seed 在替身内部计数）
    class _FakeSessionCtx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(database_module, "AsyncSessionLocal", lambda *a, **k: _FakeSessionCtx())

    class _FakeAIConfigService:
        def __init__(self, session):
            pass

        async def apply_config_to_settings(self):
            c.hit("ai_config.apply")

    class _FakeCosConfigService:
        def __init__(self, session):
            pass

        async def apply_config_to_settings(self):
            c.hit("cos_config.apply")

    class _FakeTemplateService:
        def __init__(self, session):
            pass

        async def seed_preset_templates(self):
            c.hit("template.seed")
            return 0

    monkeypatch.setattr(ai_config_module, "AIConfigService", _FakeAIConfigService)
    monkeypatch.setattr(cos_config_module, "CosConfigService", _FakeCosConfigService)
    monkeypatch.setattr(template_service_module, "TemplateService", _FakeTemplateService)

    class _FakeBackupService:
        @staticmethod
        async def cleanup_old_backups():
            c.hit("backup.cleanup")
            return 0

        @staticmethod
        async def cleanup_stale_restore_snapshots():
            c.hit("backup.cleanup_stale")
            return 0

    monkeypatch.setattr(backup_service_module, "BackupService", _FakeBackupService)

    # 调度器 / 写缓冲 / EventBus / 隧道 / 引擎释放
    monkeypatch.setattr(scheduler_module.workflow_scheduler, "start", _async_noop("scheduler.start"))
    monkeypatch.setattr(scheduler_module.workflow_scheduler, "stop", _async_noop("scheduler.stop"))
    monkeypatch.setattr(pwb_module.play_write_buffer, "start", _async_noop("play_buffer.start"))
    monkeypatch.setattr(pwb_module.play_write_buffer, "stop", _async_noop("play_buffer.stop"))

    # get_event_bus 是单例语义：必须返回同一个实例，否则关闭阶段 stop() 停错对象
    fake_bus = _FakeBus(c)
    monkeypatch.setattr(event_bus_module, "get_event_bus", lambda: fake_bus)

    fake_tunnel = _FakeTunnelService(c)

    def _tunnel_factory(*args, **kwargs):
        c.hit("tunnel.construct")
        fake_tunnel.on_started = kwargs.get("on_started")
        return fake_tunnel

    monkeypatch.setattr(tunnel_service_module, "TunnelService", _tunnel_factory)
    # get_tunnel_service 同为单例语义：关闭阶段取回的必须是启动阶段那个实例
    monkeypatch.setattr(tunnel_service_module, "get_tunnel_service", lambda: fake_tunnel)
    monkeypatch.setattr(tunnel_service_module, "set_tunnel_service", lambda svc: c.hit("tunnel.inject"))
    monkeypatch.setattr(tunnel_notify_module, "notify_tunnel_started", lambda *a: c.hit("notify.tunnel_started"))
    monkeypatch.setattr(tunnel_notify_module, "notify_autostart_failed", lambda *a: c.hit("notify.autostart_failed"))
    monkeypatch.setattr(threading, "Thread", _SyncThread)

    class _FakeEngine:
        async def dispose(self):
            c.hit("engine.dispose")

    monkeypatch.setattr(database_module, "engine", _FakeEngine())
    return c


async def _run_lifespan(role: str, monkeypatch) -> None:
    # 直接改 Settings 单例属性而不是 setenv + cache_clear：
    # 全仓有几十个模块在 import 期就 `settings = get_settings()` 持有同一个对象，
    # 清缓存会让后续 get_settings() 返回新实例，别的测试对被打补丁的旧实例断言就会失真
    # （实测会让 COS「未配置」类测试读到真实配置而失败）。
    monkeypatch.setattr(get_settings(), "APP_ROLE", role, raising=False)
    async with lifespan(FastAPI()):
        pass


@pytest.mark.parametrize(
    "role, singleton_expected",
    [("all", True), ("sched", True), ("api", False)],
)
async def test_role_gating(calls, monkeypatch, role, singleton_expected):
    """api 角色零一次性副作用，all/sched 各执行一次；写缓冲与 EventBus 恒为每进程一份。"""
    await _run_lifespan(role, monkeypatch)

    # 一次性职责：建表 + 迁移 + seed + 调度器 + 清理 + 隧道
    if singleton_expected:
        assert calls.count("_init_sqlite_schema") == 1
        assert calls.count("template.seed") == 1
        assert calls.count("scheduler.start") == 1
        assert calls.count("scheduler.stop") == 1
        assert calls.count("backup.cleanup") == 1
        assert calls.count("tunnel.construct") == 1
        assert calls.count("tunnel.inject") == 1
        assert calls.count("tunnel.start") == 1
        assert calls.count("notify.tunnel_started") == 1
        assert calls.count("tunnel.stop") == 1
        assert calls.gated_total() > 1, "迁移/seed 未被执行"
    else:
        assert calls.gated_total() == 0
        assert calls.count("template.seed") == 0
        assert calls.count("scheduler.start") == 0
        assert calls.count("scheduler.stop") == 0
        assert calls.count("backup.cleanup") == 0
        assert calls.count("tunnel.construct") == 0
        assert calls.count("notify.tunnel_started") == 0
        assert calls.count("tunnel.stop") == 0

    # 每进程职责：三种角色都必须启动（否则本进程缓冲/事件无人消费）
    assert calls.count("play_buffer.start") == 1
    assert calls.count("play_buffer.stop") == 1
    assert calls.count("event_bus.run_forever") == 1
    assert calls.count("event_bus.stop") == 1

    # 配置覆盖加载读的是本进程的 Settings 单例，与角色无关
    assert calls.count("ai_config.apply") == 1
    assert calls.count("cos_config.apply") == 1
    assert calls.count("engine.dispose") == 1


async def test_auto_start_off_skips_tunnel_thread(calls, monkeypatch):
    """auto_start=false 时 sched 角色仍注入隧道服务，但不启动隧道、不发通知。"""
    _AUTO_START["value"] = False
    try:
        await _run_lifespan("sched", monkeypatch)
    finally:
        _AUTO_START["value"] = True
    assert calls.count("tunnel.construct") == 1
    assert calls.count("tunnel.start") == 0
    assert calls.count("notify.tunnel_started") == 0


async def test_invalid_role_falls_back_to_all(calls, monkeypatch):
    """角色值写错时回退 all：宁可重复跑一次性职责，也不要所有进程都不跑。"""
    await _run_lifespan("scheduler", monkeypatch)
    assert calls.count("_init_sqlite_schema") == 1
    assert calls.count("scheduler.start") == 1
