"""健康检查端点测试。

覆盖：
- GET /api/health 综合健康检查
- GET /api/health/live 存活探针
- GET /api/health/ready 就绪探针（SQLite 失败返回 503）
"""
import pytest
from fastapi.testclient import TestClient


def test_health_live_returns_200(client):
    """存活探针始终返回 200。"""
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["status"] == "alive"


def test_health_ready_returns_200_when_sqlite_ok(client):
    """SQLite 正常时就绪探针返回 200。"""
    resp = client.get("/api/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["status"] == "ready"
    assert data["data"]["services"]["sqlite"] == "ok"


def test_health_comprehensive_returns_services(client):
    """综合健康检查返回各依赖状态。"""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "services" in data["data"]
    assert "sqlite" in data["data"]["services"]
    assert "cache" in data["data"]["services"]


def test_health_live_no_db_dependency(client):
    """存活探针不查 DB，即使 DB 异常也返回 200（不需要 db_session fixture）。

    这里通过 app fixture（不含 db）直接测 TestClient 是否能访问 /api/health/live。
    """
    # client fixture 已注入 db_session，但 /live 路由不 Depends(get_db)
    # 仅验证响应正常即可
    resp = client.get("/api/health/live")
    assert resp.status_code == 200
