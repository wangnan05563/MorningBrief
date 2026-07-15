"""通知管理 API 路由测试。

覆盖：
- GET/PUT /config：配置读取与保存
- POST /test：测试发送（mock sender）
- GET /templates：模板列表
- PUT /templates/{id}：模板更新
- POST /templates/{id}/preview：模板预览
- GET /logs：日志列表分页
- POST /logs/{id}/resend：日志重发（mock sender）

测试目标：路由鉴权、参数校验、响应格式正确。
sender 内部发送逻辑在 test_notification_sender.py 中测试，这里 mock 掉。
"""
from unittest.mock import AsyncMock, patch

import pytest


def _admin_headers(admin_token):
    """构造 admin 请求头。"""
    return {"Authorization": f"Bearer {admin_token['token']}"}


# ====================== 配置 API 测试 ======================

def test_get_config_returns_defaults(client, admin_token):
    """空库 GET /config 返回默认值。"""
    resp = client.get(
        "/admin/api/v1/notification/config",
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["global_enabled"] is False
    assert data["failed_enabled"] is True
    assert data["review_enabled"] is True
    assert data["published_enabled"] is False
    assert data["dingtalk_webhook"] == ""
    assert data["dingtalk_secret"] == ""
    assert "auto_detected_base_url" in data


def test_save_config_persists_and_reloads(client, admin_token):
    """PUT /config 保存后 GET 返回新值。"""
    resp = client.put(
        "/admin/api/v1/notification/config",
        headers=_admin_headers(admin_token),
        json={
            "global_enabled": True,
            "failed_enabled": True,
            "review_enabled": False,
            "published_enabled": True,
            "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=test123",
            "dingtalk_secret": "SECtest",
            "admin_base_url": "https://news.example.com",
        },
    )
    assert resp.status_code == 200

    resp = client.get(
        "/admin/api/v1/notification/config",
        headers=_admin_headers(admin_token),
    )
    data = resp.json()["data"]
    assert data["global_enabled"] is True
    assert data["review_enabled"] is False
    assert data["published_enabled"] is True
    assert data["dingtalk_webhook"] == "https://oapi.dingtalk.com/robot/send?access_token=test123"
    assert data["dingtalk_secret"].startswith("****")
    assert data["admin_base_url"] == "https://news.example.com"


def test_save_config_secret_masked_value_ignored(client, admin_token):
    """PUT /config 传入脱敏值（****开头）时 secret 不被覆盖。"""
    client.put(
        "/admin/api/v1/notification/config",
        headers=_admin_headers(admin_token),
        json={
            "global_enabled": True,
            "failed_enabled": True,
            "review_enabled": True,
            "published_enabled": False,
            "dingtalk_webhook": "",
            "dingtalk_secret": "SECreal_secret_value",
            "admin_base_url": "",
        },
    )
    client.put(
        "/admin/api/v1/notification/config",
        headers=_admin_headers(admin_token),
        json={
            "global_enabled": True,
            "failed_enabled": True,
            "review_enabled": True,
            "published_enabled": False,
            "dingtalk_webhook": "",
            "dingtalk_secret": "****_value",
            "admin_base_url": "",
        },
    )
    resp = client.get(
        "/admin/api/v1/notification/config",
        headers=_admin_headers(admin_token),
    )
    data = resp.json()["data"]
    assert data["dingtalk_secret"] == "****alue"


def test_config_requires_admin(client, user_token):
    """非 admin token 访问配置接口被拒（401 或 403 均可）。"""
    resp = client.get(
        "/admin/api/v1/notification/config",
        headers={"Authorization": f"Bearer {user_token['token']}"},
    )
    # require_admin 可能返回 401（token type 不匹配）或 403（role 不足）
    assert resp.status_code in (401, 403)


# ====================== 模板 API 测试 ======================

def test_list_templates_empty(client, admin_token):
    """空库 GET /templates 返回空列表。"""
    resp = client.get(
        "/admin/api/v1/notification/templates",
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_list_templates_after_seed(client, admin_token, db_session):
    """seed 预设模板后 GET /templates 返回 3 条。"""
    from app.services.notification.template_service import TemplateService
    svc = TemplateService(db_session)
    inserted = await svc.seed_preset_templates()
    assert inserted == 3

    resp = client.get(
        "/admin/api/v1/notification/templates",
        headers=_admin_headers(admin_token),
    )
    data = resp.json()["data"]
    assert len(data) == 3
    for tpl in data:
        assert "variables" in tpl
        assert isinstance(tpl["variables"], list)


@pytest.mark.asyncio
async def test_update_template(client, admin_token, db_session):
    """PUT /templates/{id} 更新模板字段。"""
    from app.services.notification.template_service import TemplateService
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    templates = await svc.list_templates()
    first_id = templates[0].id

    resp = client.put(
        f"/admin/api/v1/notification/templates/{first_id}",
        headers=_admin_headers(admin_token),
        json={
            "name": "自定义模板",
            "title_template": "新标题 {{workflow_id}}",
            "body_template": "新正文",
            "enabled": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "自定义模板"
    # SQLite 用 0/1 存储布尔值，API 返回 0 而非 false
    assert data["enabled"] == 0


def test_update_template_not_found(client, admin_token):
    """更新不存在的模板返回错误。"""
    resp = client.put(
        "/admin/api/v1/notification/templates/99999",
        headers=_admin_headers(admin_token),
        json={"name": "x"},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_preview_template(client, admin_token, db_session):
    """POST /templates/{id}/preview 返回渲染结果。"""
    from app.services.notification.template_service import TemplateService
    svc = TemplateService(db_session)
    await svc.seed_preset_templates()
    templates = await svc.list_templates()
    first_id = templates[0].id

    resp = client.post(
        f"/admin/api/v1/notification/templates/{first_id}/preview",
        headers=_admin_headers(admin_token),
        json={"variables": {"workflow_id": "wf-test", "channel_name": "新闻频道"}},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "title" in data
    assert "body" in data
    assert "wf-test" in data["title"] or "wf-test" in data["body"]


# ====================== 日志 API 测试 ======================

def test_list_logs_empty(client, admin_token):
    """空库 GET /logs 返回空列表。"""
    resp = client.get(
        "/admin/api/v1/notification/logs",
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_logs_with_data(client, admin_token, db_session):
    """有日志数据时 GET /logs 返回列表。"""
    from app.services.notification.log_service import LogService
    log_svc = LogService(db_session)
    await log_svc.create_log(
        event_type="workflow.failed",
        channel="dingtalk",
        title="测试日志",
        status="success",
        error="",
        payload={"workflow_id": "wf-1"},
        workflow_id="wf-1",
    )

    resp = client.get(
        "/admin/api/v1/notification/logs",
        headers=_admin_headers(admin_token),
    )
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "测试日志"


@pytest.mark.asyncio
async def test_list_logs_filter_by_status(client, admin_token, db_session):
    """按 status 过滤日志。"""
    from app.services.notification.log_service import LogService
    log_svc = LogService(db_session)
    await log_svc.create_log(
        event_type="workflow.failed", channel="dingtalk",
        title="成功日志", status="success", error="", payload={}, workflow_id="wf-1",
    )
    await log_svc.create_log(
        event_type="workflow.failed", channel="dingtalk",
        title="失败日志", status="failed", error="webhook 错误", payload={}, workflow_id="wf-2",
    )

    resp = client.get(
        "/admin/api/v1/notification/logs?status=failed",
        headers=_admin_headers(admin_token),
    )
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["status"] == "failed"


# ====================== 测试发送与重发 API 测试 ======================

def test_test_send_endpoint(client, admin_token):
    """POST /test 调用 sender.send_test（mock 返回成功）。"""
    mock_sender = AsyncMock()
    mock_sender.send_test = AsyncMock(return_value={
        "success": True,
        "message": "测试通知已发送",
        "results": [{"channel": "dingtalk", "success": True, "error": ""}],
    })
    with patch(
        "app.routers.admin.notification.get_notification_sender",
        return_value=mock_sender,
    ):
        resp = client.post(
            "/admin/api/v1/notification/test",
            headers=_admin_headers(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["success"] is True


@pytest.mark.asyncio
async def test_resend_log_endpoint(client, admin_token, db_session):
    """POST /logs/{id}/resend 调用 sender.resend_log（mock 返回成功）。"""
    from app.services.notification.log_service import LogService
    log_svc = LogService(db_session)
    # create_log 返回 NotificationLog 对象，需取 .id 构造 URL
    log = await log_svc.create_log(
        event_type="workflow.failed", channel="dingtalk",
        title="测试", status="failed", error="err", payload={"workflow_id": "wf-1"},
        workflow_id="wf-1",
    )
    log_id = log.id

    mock_sender = AsyncMock()
    mock_sender.resend_log = AsyncMock(return_value={
        "status": "success",
        "message": "重发成功",
        "success": 1,
        "failed": 0,
    })
    with patch(
        "app.routers.admin.notification.get_notification_sender",
        return_value=mock_sender,
    ):
        resp = client.post(
            f"/admin/api/v1/notification/logs/{log_id}/resend",
            headers=_admin_headers(admin_token),
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
