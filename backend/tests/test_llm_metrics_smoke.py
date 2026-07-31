"""临时冒烟测试：验证 /llm-metrics 端点能正确返回指标数据。

复用 conftest.py 的 TestClient + 内存 SQLite 基础设施。
"""
import sys
from pathlib import Path

# pytest 默认会把 tests 目录加入 sys.path，无需手动处理
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.security import create_access_token
from app.database import get_db, Base, normalize_metadata_for_sqlite
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


async def _override_get_db():
    """空 session 替代：本测试不需要数据库读，路由逻辑直接返回计数器快照。"""
    # /llm-metrics 路由内部不读 db，仅 Depends(get_db) 占位
    # 用 None 替代也能工作，但保持类型一致用 AsyncSession 模拟
    class _StubSession:
        pass
    yield _StubSession()


def test_llm_metrics_endpoint_smoke():
    """GET /admin/api/v1/stats/llm-metrics 返回 200 + 7 字段。"""
    normalize_metadata_for_sqlite()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db

    # 生成 admin token
    token, _, _ = create_access_token("1", token_type="admin",
                                       extra_claims={"username": "admin", "role": "admin"})

    with TestClient(app) as c:
        # 不进入 with 块触发 lifespan；TestClient 在无 with 时也能发请求
        resp = c.get(
            "/admin/api/v1/stats/llm-metrics",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200, f"端点应返回 200，实际 {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"业务码应为 0，实际 {body.get('code')}"
    data = body["data"]

    # 校验 7 个字段全部存在
    expected_fields = {
        "total_calls", "triggered", "improved", "not_improved",
        "trigger_rate", "improve_rate", "not_improve_rate",
    }
    assert set(data.keys()) == expected_fields, f"字段不匹配: {set(data.keys())}"

    # 初始状态：全 0，派生率应为 0.0（不崩 ZeroDivisionError）
    assert data["total_calls"] == 0
    assert data["triggered"] == 0
    assert data["improved"] == 0
    assert data["not_improved"] == 0
    assert data["trigger_rate"] == 0.0
    assert data["improve_rate"] == 0.0
    assert data["not_improve_rate"] == 0.0

    print("OK: /llm-metrics 端点返回字段完整，初始值为 0")
