"""INT-UX-02：导入接口的 `dry_run=true`。

PRD §7 要的是「POST /import 新增 dry_run=true」，而现状是另有一个
`POST /import/preview` 端点做只读预览。两个入口做同一件事，本身不是缺陷；
真正的缺陷是**预览说「将更新 2 行」而真实导入只写了 1 行**——没人断过这件事，
于是 dry-run 只是个估计值，运营照它决定要不要提交。

本文件把两件事钉住：
1. `dry_run=true` 走的是导入接口本身（PRD 契约），且真的什么都不写；
2. 预览计数与随后真实导入的计数一致（不一致就是预览在骗人）。
"""
import pytest
from sqlalchemy import func, select

from app.models.ai_config import AIConfig
from app.models.audit_log import AuditLog
from app.routers.admin import db_admin as db_router

BASE = "/admin/api/v1/db-admin/tables"
TABLE = "ai_config"


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture(autouse=True)
def _server_confirm_token(monkeypatch):
    """真实导入需要服务端令牌总开关；不配置它就永远进不到写入分支。"""
    monkeypatch.setattr(db_router, "CONFIRM_TOKEN", "server-side-only-secret")


@pytest.fixture
async def seeded(db_session):
    row = AIConfig(config_key="int02_target", config_value="old-value")
    db_session.add(row)
    await db_session.commit()
    return row.id


def _payload(pk):
    # 一行命中已有主键（应算更新），一行带全新主键（应算新增）
    return [
        {"id": pk, "config_key": "int02_target", "config_value": "new-value"},
        {"id": 900001, "config_key": "int02_brand_new", "config_value": "fresh"},
    ]


async def _post(client, auth, body):
    return client.post(f"{BASE}/{TABLE}/import", json=body, headers=auth)


async def _row_count(db_session) -> int:
    return (await db_session.execute(select(func.count()).select_from(AIConfig))).scalar_one()


async def _import_audit_count(db_session) -> int:
    stmt = select(func.count()).select_from(AuditLog).where(AuditLog.action == "import")
    return (await db_session.execute(stmt)).scalar_one()


async def test_dry_run_returns_counts_without_writing(client, auth, db_session, seeded):
    before = await _row_count(db_session)
    resp = await _post(client, auth, {
        "rows": _payload(seeded), "mode": "replace", "dry_run": True,
    })
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["dry_run"] is True
    assert (data["to_insert"], data["to_update"]) == (1, 1)
    # 一行都没写进去
    assert await _row_count(db_session) == before
    target = (await db_session.execute(
        select(AIConfig).filter_by(config_key="int02_target")
    )).scalar_one()
    await db_session.refresh(target)
    assert target.config_value == "old-value"


async def test_dry_run_leaves_no_audit_trail(client, auth, db_session, seeded):
    """预览不是执行：审计里不该出现一条 import 记录（否则「谁导过数据」被污染）。"""
    before = await _import_audit_count(db_session)
    await _post(client, auth, {"rows": _payload(seeded), "mode": "replace", "dry_run": True})
    assert await _import_audit_count(db_session) == before


async def test_dry_run_needs_no_confirm_token_but_real_import_does(client, auth, db_session, seeded):
    """dry_run 免确认令牌（它不写任何东西）；同一份请求去掉 dry_run 就必须被拦。"""
    ok = await _post(client, auth, {
        "rows": _payload(seeded), "mode": "replace", "dry_run": True, "confirm_text": "",
    })
    assert ok.json()["code"] == 0

    blocked = await _post(client, auth, {
        "rows": _payload(seeded), "mode": "replace", "confirm_text": "",
    })
    assert blocked.json()["code"] == 400
    assert await _row_count(db_session) == 1  # 只有 seeded 那一行


async def test_dry_run_counts_match_the_real_import(client, auth, db_session, seeded):
    """核心一致性：预览报的 新增/更新 数，必须等于随后真实导入实际发生的数。

    预览与执行分算两本账时，dry-run 就只是个装饰——运营看到「将更新 1 行」
    却发生 0 行写入，或反过来，都是拿预览做决定时被误导。
    """
    preview = (await _post(client, auth, {
        "rows": _payload(seeded), "mode": "replace", "dry_run": True,
    })).json()["data"]

    applied = (await _post(client, auth, {
        "rows": _payload(seeded), "mode": "replace", "confirm_text": "IMPORT",
    })).json()["data"]

    assert applied["inserted"] == preview["to_insert"], (preview, applied)
    assert applied["updated"] == preview["to_update"], (preview, applied)
    assert applied["errors"] == [], applied


async def test_preview_endpoint_is_the_same_contract(client, auth, db_session, seeded):
    """老端点 /import/preview 必须与 dry_run 返回同一形状，不能各长一套字段。"""
    rows = _payload(seeded)
    via_dry = (await _post(client, auth, {"rows": rows, "mode": "replace", "dry_run": True})).json()["data"]
    via_ep = client.post(
        f"{BASE}/{TABLE}/import/preview", json={"rows": rows, "mode": "replace"}, headers=auth
    ).json()["data"]
    assert {k: v for k, v in via_dry.items() if k != "dry_run"} == via_ep


async def test_row_with_extra_column_counts_as_writable(client, auth, db_session, seeded):
    """多带一个不存在的列：该行照样会写（只是丢掉那列），所以不能算「错误行」。

    这一条是预览计数的地基。把它算成 error_rows 时，预览报「错误 1、新增 0」
    而导入实际「新增 1、错误 0」——dry-run 就纯粹在骗人。
    """
    rows = [{"id": 900002, "config_key": "int02_extra", "config_value": "v", "not_a_column": "x"}]
    preview = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "dry_run": True,
    })).json()["data"]
    assert preview["to_insert"] == 1
    assert preview["error_rows"] == 0
    assert preview["notice_rows"] == 1
    assert preview["notices"][0]["columns"] == ["not_a_column"]

    applied = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "confirm_text": "IMPORT",
    })).json()["data"]
    assert applied["inserted"] == preview["to_insert"], (preview, applied)
    assert applied["errors"] == [], applied


async def test_missing_required_column_is_blocked_in_preview(client, auth, db_session, seeded):
    """缺 NOT NULL 无默认值的列：导入必然 IntegrityError，预览必须提前拦住。

    取证时踩到的原样：预览说「新增 1 行」，真实导入报
    `NOT NULL constraint failed: ai_config.config_value`、0 行写入。
    这类行不拦，dry_run 的计数就永远比实际多。
    """
    rows = [{"id": 900003, "config_key": "int02_no_value"}]  # 少 config_value
    preview = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "dry_run": True,
    })).json()["data"]
    assert preview["to_insert"] == 0
    assert preview["error_rows"] == 1
    assert "config_value" in preview["errors"][0]["error"]

    applied = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "confirm_text": "IMPORT",
    })).json()["data"]
    assert applied["inserted"] == 0 and applied["skipped"] == preview["error_rows"], applied
    assert await _row_count(db_session) == 1  # 只有 seeded 那一行


async def test_update_row_need_not_carry_required_columns(client, auth, db_session, seeded):
    """走 UPDATE 的行不该被必填列卡住：没带的列保持原值，这正是 replace 模式的卖点。

    把它也当错误拦掉，就等于废掉「只改一列」的局部导入。
    """
    rows = [{"id": seeded, "config_value": "only-one-col"}]
    preview = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "dry_run": True,
    })).json()["data"]
    assert (preview["to_update"], preview["error_rows"]) == (1, 0)

    applied = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "confirm_text": "IMPORT",
    })).json()["data"]
    assert applied["updated"] == preview["to_update"], (preview, applied)


async def test_row_with_only_pk_is_blocked(client, auth, db_session, seeded):
    """只给主键的行：导入侧会报「无可更新字段」，预览必须同样拦下，不能算成一次更新。"""
    rows = [{"id": seeded}]
    preview = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "dry_run": True,
    })).json()["data"]
    assert (preview["to_update"], preview["error_rows"]) == (0, 1)

    applied = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "confirm_text": "IMPORT",
    })).json()["data"]
    assert applied["updated"] == 0 and applied["skipped"] == preview["error_rows"], applied


async def test_rejected_row_is_not_counted_as_writable(client, auth, db_session, seeded):
    """反方向：真正被拒的行既不进 to_insert/to_update，也确实不写库。

    只在「有坏行的载荷」上才测得出预览会不会把错误行也计入可写数——
    干净载荷上 to_insert 与 error_rows 互不相干，怎么改都绿。
    """
    rows = [
        {"id": seeded, "config_value": "keep"},          # 可更新
        {"config_key": "int02_no_pk", "config_value": "y"},  # replace 缺主键 → 拒
    ]
    preview = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "dry_run": True,
    })).json()["data"]
    assert (preview["to_insert"], preview["to_update"]) == (0, 1)
    assert preview["error_rows"] == 1

    applied = (await _post(client, auth, {
        "rows": rows, "mode": "replace", "confirm_text": "IMPORT",
    })).json()["data"]
    assert applied["updated"] == preview["to_update"], (preview, applied)
    assert applied["inserted"] == preview["to_insert"], (preview, applied)
    assert applied["skipped"] == preview["error_rows"], applied
    assert await _row_count(db_session) == 1  # 坏行没变成半截数据


async def test_default_request_still_writes(client, auth, db_session, seeded):
    """不带 dry_run 时行为逐字节不变——新参数不能把默认路径变成预览。"""
    applied = (await _post(client, auth, {
        "rows": _payload(seeded), "mode": "replace", "confirm_text": "IMPORT",
    })).json()["data"]
    assert applied["inserted"] == 1 and applied["updated"] == 1
    assert await _row_count(db_session) == 2
