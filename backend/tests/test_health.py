"""健康检查接口测试。

验证 GET /api/health 在依赖服务（SQLite/cache）正常时返回成功响应。
测试中 SQLite 用内存库替代、cache 用进程内 TTLCache 单例，
两者均能正常工作，因此健康检查应返回 status=ok。
"""


def test_health_endpoint(client):
    """GET /api/health 返回 200 + { code: 0, message: "success" }。

    依赖服务全部可用时，data.status 应为 "ok"，services 各项均为 "ok"。
    """
    # 健康检查内部对 db 执行 SELECT 1、对 cache 做一次 set/get/delete 探测
    # client fixture 已用 SQLite 内存库 + 进程内 TTLCache 替代真实依赖
    resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "success"
    # 依赖均可用，整体状态 ok
    assert body["data"]["status"] == "ok"
    services = body["data"]["services"]
    assert services["app"] == "ok"
    assert services["sqlite"] == "ok"
    assert services["cache"] == "ok"
