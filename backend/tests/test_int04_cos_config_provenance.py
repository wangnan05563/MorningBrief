"""INT-UX-04：`GET /admin/api/v1/cos/config` 必须能回答「这些值是哪来的、上次改是什么时候」。

FR-UX-104（T02487）已经把「请求失败」这一半做了：接口报错 → 页内报错 + 禁存 + 重试。
剩下的口子是**请求成功但值不代表库里有什么**：`get_config_for_frontend()` 对每个字段
`raw.get(key)` 取不到就回落 `Settings`（也就是 .env）。于是两种完全不同的状态在响应里
长得一模一样：

- 库里有 5 条记录，管理员改过、正在用；
- 表是空的，屏幕上这几个值是 .env 里躺着的旧值，一次都没入库。

第二种状态下管理员点保存，`update_config` 会把这些回落值原样写进库——
「谁改的」查不到（没有 updated_at），「改之前是什么」也没了（env 值被固化成库值）。
接口层面必须把这两态分开，前端才可能把「加载失败禁存」判准。
"""
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models.cos_config import CosConfig
from app.services.cos_config_service import CosConfigService

FRONT_FIELDS = [
    "secret_id", "secret_key", "region", "bucket", "cdn_domain", "backup_keep_count",
]
SECRET_KEY = "sk-secret-value-8f3a2b"


@pytest.fixture(autouse=True)
def _isolate_settings():
    """把 COS_* 全部擦成空：不擦的话 .env 的真实值会混进每个用例。"""
    s = get_settings()
    saved = {
        a: getattr(s, a) for a in ("COS_SECRET_ID", "COS_SECRET_KEY", "COS_REGION",
                                   "COS_BUCKET", "COS_CDN_DOMAIN", "COS_BACKUP_KEEP_COUNT")
    }
    for a in saved:
        if a == "COS_REGION":
            setattr(s, a, "ap-guangzhou")
        elif a == "COS_BACKUP_KEEP_COUNT":
            setattr(s, a, 5)
        else:
            setattr(s, a, "")
    yield
    for a, v in saved.items():
        setattr(s, a, v)


async def _seed(db_session, **values):
    svc = CosConfigService(db_session)
    await svc.update_config(
        secret_id=values.get("secret_id", "AKIDrealid"),
        secret_key=values.get("secret_key", SECRET_KEY),
        region=values.get("region", "ap-shanghai"),
        bucket=values.get("bucket", "mybucket"),
        cdn_domain=values.get("cdn_domain", ""),
        backup_keep_count=values.get("backup_keep_count", 5),
    )
    return svc


async def test_values_from_db_are_marked_loaded_with_timestamp(db_session):
    """入库过的配置：loaded=true，且给出最后一次入库修改时间。"""
    await _seed(db_session)
    data = await CosConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is True
    assert data["load_error"] is None
    assert data["fallback_fields"] == []
    assert data["updated_at"]
    # 与表里的 max(updated_at) 对齐，不是页面自己算的"刚刚"
    assert datetime.fromisoformat(data["updated_at"]) == (
        await db_session.execute(select(func.max(CosConfig.updated_at)))
    ).scalar_one()


async def test_empty_table_exposes_env_fallback(db_session):
    """表为空但 .env 有值：这不是"已配置好"，接口必须说清值来自回落。"""
    s = get_settings()
    s.COS_SECRET_ID, s.COS_SECRET_KEY, s.COS_BUCKET = "AKIDfromenv", "skfromenv", "envbucket"

    data = await CosConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is True          # 读库成功
    assert data["updated_at"] is None      # 但库里没有任何入库记录
    # 屏幕上这五个值没有一个来自表——逐个点名，页面才敢写「以下值来自环境变量」
    assert sorted(data["fallback_fields"]) == sorted(FRONT_FIELDS)
    # 值本身仍是 .env 的那套（口径不变，只是多了来源说明），凭证照旧脱敏
    assert data["secret_id"] == "****menv"
    assert data["bucket"] == "envbucket"


async def test_read_failure_reports_not_loaded(db_session, monkeypatch):
    """读库异常时不能装作一份正常配置：loaded=false + 可读原因。"""
    # 先让表里真的有一条修改记录：读表失败时如果还把 max(updated_at) 端出去，
    # 页面就会把"上一次成功读到的时间"当成"本次加载成功"的证据。
    await _seed(db_session)

    async def _boom(self):
        raise RuntimeError(
            f"no such column: config_value; bound params secret_key='{SECRET_KEY}' "
            "and AKIDrealid0000"
        )

    monkeypatch.setattr(CosConfigService, "get_all_config", _boom)
    data = await CosConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is False
    assert "no such column" in data["load_error"]
    assert data["updated_at"] is None
    # 失败原因要能读，但不得把异常文本里的凭据原样带到前端（NFR-01 口径）
    assert SECRET_KEY not in str(data)
    assert "AKIDrealid0000" not in str(data)


async def test_load_error_is_bounded(db_session, monkeypatch):
    """驱动层异常动辄上千行：页面提示只留得下的一句，别把整坨堆栈推给前端。"""

    async def _boom(self):
        raise RuntimeError("database is locked " + ("retry later " * 400))

    monkeypatch.setattr(CosConfigService, "get_all_config", _boom)
    data = await CosConfigService(db_session).get_config_for_frontend()

    assert data["loaded"] is False
    assert data["load_error"].startswith("RuntimeError: database is locked")
    assert len(data["load_error"]) <= len("RuntimeError: ") + 200


async def test_route_exposes_the_new_fields(client, admin_token, db_session):
    """HTTP 层同样可见：前端靠这两个字段判定禁存，拿不到就等于没交付。"""
    await _seed(db_session)
    body = client.get(
        "/admin/api/v1/cos/config",
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    ).json()
    assert body["code"] == 0
    for f in ("loaded", "updated_at", "fallback_fields", "load_error"):
        assert f in body["data"], f
