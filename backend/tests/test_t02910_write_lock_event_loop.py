"""T02910：全局写锁的事件循环边界与调用方归属门禁。

验收口径：
1. 一条测试证明「跨事件循环复用」的真实行为 —— 未争用不绑定、争用后绑定首个循环、
   换循环再取直接 RuntimeError（与 write_gate 模块头文档一致）。
2. 现有调用方全部有归属判定：代码里的每处 write_lock()/serialized_write() 必须在
   tests/write_lock_callers.json 登记用途与原子性来源，双向核对，新增调用漏登记即红。
"""
import ast
import asyncio
import json
from pathlib import Path

import pytest

from app.core import write_gate

BACKEND = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND / "app"
REGISTRY_PATH = Path(__file__).resolve().parent / "write_lock_callers.json"
API_NAMES = {"write_lock", "serialized_write"}


@pytest.fixture()
def pristine_lock():
    """把全局锁恢复到「未绑定循环、未加锁」状态，并在用例结束后还原。"""
    lock = write_gate._write_lock
    assert not lock.locked(), "全局写锁在本用例开始前已被持有，说明前面的用例泄漏了状态"
    saved_loop = getattr(lock, "_loop", None)
    lock._loop = None
    try:
        yield lock
    finally:
        lock._loop = saved_loop


def test_uncontended_reuse_across_event_loops_does_not_bind(pristine_lock):
    """跑一次没事 ≠ 可跨循环：未发生争用时 Lock 不绑定循环。"""

    async def take_and_release() -> bool:
        async with write_gate.write_lock():
            return True

    assert asyncio.run(take_and_release()) is True
    assert asyncio.run(take_and_release()) is True
    assert getattr(pristine_lock, "_loop", None) is None


def test_contended_lock_binds_to_first_loop_and_rejects_another(pristine_lock):
    """争用会把锁钉在第一个事件循环上，换循环再取抛 RuntimeError（地雷本体）。"""

    async def bind_loop() -> bool:
        lock = write_gate.write_lock()
        await lock.acquire()
        waiter = asyncio.create_task(lock.acquire())
        await asyncio.sleep(0)  # 让 waiter 真正进入等待，触发循环绑定
        lock.release()
        await waiter
        lock.release()
        return True

    assert asyncio.run(bind_loop()) is True
    bound_loop = getattr(pristine_lock, "_loop", None)
    assert bound_loop is not None
    assert not bound_loop.is_running(), "绑定后原循环已结束，正是 pytest 多循环场景"

    async def reuse_with_contention_in_new_loop() -> bool:
        lock = write_gate.write_lock()
        await lock.acquire()  # 未争用走快路径，不校验已绑定循环 —— 所以「没炸」不能证明安全
        waiter = asyncio.create_task(lock.acquire())
        try:
            await waiter  # 新循环里出现争用，_get_loop 才会撞上旧循环绑定
        finally:
            lock.release()
        return True

    with pytest.raises(RuntimeError, match="different event loop"):
        asyncio.run(reuse_with_contention_in_new_loop())


class _CallSiteCollector(ast.NodeVisitor):
    def __init__(self, rel: str):
        self.rel = rel
        self.stack: list[str] = []
        self.sites: set[str] = set()
        self.duplicates: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _visit_function(self, node: ast.AST) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in API_NAMES:
            if not self.stack:
                self.duplicates.append(f"{self.rel}::<module>")
            else:
                self.sites.add(f"{self.rel}::" + ".".join(self.stack))
        self.generic_visit(node)


def _detected_call_sites() -> set[str]:
    sites: set[str] = set()
    for path in sorted(APP_DIR.rglob("*.py")):
        rel = path.relative_to(BACKEND.parent).as_posix()
        collector = _CallSiteCollector(rel)
        collector.visit(ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path)))
        assert not collector.duplicates, f"写锁不允许在模块级使用：{collector.duplicates}"
        sites |= collector.sites
    return sites


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def test_every_call_site_is_registered():
    detected = _detected_call_sites()
    registered = {entry["caller"] for entry in _registry()["entries"]}
    missing = sorted(detected - registered)
    assert not missing, (
        "以下调用未在 tests/write_lock_callers.json 登记用途/原子性来源："
        + "; ".join(missing)
    )


def test_registry_has_no_stale_entries():
    detected = _detected_call_sites()
    registered = {entry["caller"] for entry in _registry()["entries"]}
    stale = sorted(registered - detected)
    assert not stale, "登记了但代码里已不存在的调用方：" + "; ".join(stale)


def test_registry_entries_declare_real_atomicity_source():
    data = _registry()
    allowed = set(data["allowed_atomicity_sources"])
    assert "asyncio-lock" not in allowed, "全局写锁不能作为原子性来源"
    for entry in data["entries"]:
        caller = entry["caller"]
        assert entry["api"] in API_NAMES, f"{caller}: api 必须来自 {sorted(API_NAMES)}"
        assert entry["purpose"].strip(), f"{caller}: purpose 不能为空"
        assert entry["note"].strip(), f"{caller}: note 不能为空"
        assert entry["atomicity_source"] in allowed, (
            f"{caller}: atomicity_source={entry['atomicity_source']!r} 不在允许集合 {sorted(allowed)}"
        )


def test_write_gate_doc_states_the_loop_boundary():
    doc = write_gate.__doc__ or ""
    for phrase in ("单一事件循环", "跨进程", "different event loop", "不得把本锁当作读写原子性的依据"):
        assert phrase in doc, f"write_gate 模块头缺少边界说明：{phrase!r}"
