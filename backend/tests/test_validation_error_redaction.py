"""T02846：参数校验失败不得回显用户提交的原值（NFR-UX-05）。

pydantic 的 errors() 默认带 input（提交原值）与 ctx，直接拼进 message 等于把
密码、API key、webhook URL 明文回给客户端。验收口径：
1. 响应体全文（含 message 与 data）不出现任何提交原值；
2. 明细只含 loc / type / msg，loc + msg 仍足以定位字段。
"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exceptions import register_exception_handlers

LEAK_PASSWORD = "P@ssw0rd-LEAK-9f3c21"
LEAK_WEBHOOK_SECRET = "hooks-secret-LEAK-4d8a"


class _CredentialPayload(BaseModel):
    password: int
    webhook_url: str


def _make_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/credentials")
    def submit(payload: _CredentialPayload):  # pragma: no cover - 校验失败不会进入
        return {"code": 0, "data": payload.model_dump()}

    return TestClient(app)


def test_validation_error_does_not_echo_submitted_values():
    client = _make_client()
    resp = client.post(
        "/credentials",
        json={
            "password": LEAK_PASSWORD,
            "webhook_url": {"url": f"https://hooks.example.com/{LEAK_WEBHOOK_SECRET}"},
        },
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 400

    text = json.dumps(body, ensure_ascii=False)
    assert LEAK_PASSWORD not in text
    assert LEAK_WEBHOOK_SECRET not in text
    assert "input" not in text
    assert "ctx" not in text

    errors = body["data"]["errors"]
    assert [e["loc"] for e in errors] == [["body", "password"], ["body", "webhook_url"]]
    for err in errors:
        assert set(err) == {"loc", "type", "msg"}
        assert err["msg"]

    # 人读 message 仍需带字段路径，前端 toast 可直接指出哪个字段错了
    assert body["message"].startswith("参数错误:")
    assert "body.password" in body["message"]
    assert "body.webhook_url" in body["message"]
