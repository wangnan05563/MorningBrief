"""C 端客户端告警上报端点冒烟测试（FR-MC-12 后续增强）。

验证 POST /api/v1/client/report：
- 合法上报 → 200，body.data.accepted == True
- 缺字段 / 超长 / payload 非对象 / payload 过大 → 422（pydantic 校验）
匿名端点，无需登录；仅结构校验 + 服务端 logging，不落库。
"""
import pytest


def test_report_valid(client):
    """合法上报体应 200 且 accepted。"""
    resp = client.post(
        "/api/v1/client/report",
        json={
            "category": "unknown_channel_type",
            "message": "未知 channel_type: foo",
            "payload": {"unknown_type": "foo"},
            "client_ts": 1700000000000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["accepted"] is True


def test_report_minimal(client):
    """仅 category + message 也可（payload / client_ts 可选）。"""
    resp = client.post(
        "/api/v1/client/report",
        json={"category": "x", "message": "y"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["accepted"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {},  # 缺 category
        {"category": "x"},  # 缺 message
        {"category": "x" * 65, "message": "y"},  # category 超长
        {"category": "x", "message": "y" * 1025},  # message 超长
        {"category": "x", "message": "y", "payload": "not-a-dict"},  # payload 非对象
    ],
)
def test_report_invalid_shape(client, payload):
    """结构非法（缺字段 / 超长 / payload 非对象）→ 400（项目自定义校验处理器）。"""
    resp = client.post("/api/v1/client/report", json=payload)
    assert resp.status_code == 400


def test_report_payload_too_large(client):
    """payload 序列化超过 4KB → 400。"""
    big = {"data": "z" * 5000}
    resp = client.post(
        "/api/v1/client/report",
        json={"category": "x", "message": "y", "payload": big},
    )
    assert resp.status_code == 400
