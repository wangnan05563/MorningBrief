"""T02909：审计读口补齐（15 个 category 全部可读）。

红基线（改前）：写侧 37 处 `AuditLog(...)` 分布在 15 个 category，
读侧只有 `/db-admin/audit-log`（SQL 硬过滤 category='db_admin'）和移动端停服那条。
backup 恢复、maintenance 清理、review 强制过审、user 停用这类高危动作
事后查「谁做的」只能手工 sqlite3 捞表——写了等于没写。

权限裁决（写在单里）：**全量管理员可读**。所以这里断言的是
「任何 B 端登录态都能按 category 读到」+「C 端/匿名读不到」，
而不是按模块切权限。
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.services.audit_service import AUDIT_CATEGORIES

URL = "/admin/api/v1/audit-logs"
BACKEND_APP = Path(__file__).resolve().parents[1] / "app"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _add(db, *, category, action="create", target="t", operator="admin",
               detail=None, created_at=None):
    row = AuditLog(
        category=category,
        action=action,
        target=target,
        operator=operator,
        detail=detail,
    )
    if created_at is not None:
        row.created_at = created_at
    db.add(row)
    await db.commit()
    return row


def _written_categories() -> set[str]:
    """AST 取所有 `AuditLog(category=...)` 字面量。

    用 AST 而不是 grep：`category="tech"` 在素材表里是业务字段，
    文本扫描会把无关字面量算进审计类别。
    """
    found: set[str] = set()
    for py in BACKEND_APP.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != "AuditLog":
                continue
            for kw in node.keywords:
                if kw.arg == "category" and isinstance(kw.value, ast.Constant):
                    assert isinstance(kw.value.value, str), f"{py} 里出现了非字面量的审计类别"
                    found.add(kw.value.value)
    return found


async def test_every_written_category_is_registered():
    """写侧新增类别必须先登记，否则任何界面都读不到（本单的根因）。"""
    written = _written_categories()
    assert len(written) >= 13, f"源码扫描异常，只找到 {len(written)} 个类别"
    unregistered = sorted(written - set(AUDIT_CATEGORIES))
    assert not unregistered, f"这些 category 有写入但没登记读口：{unregistered}"


async def test_all_registered_categories_are_readable_via_api(client, admin_token, db_session):
    """登记表里的每个类别都要真能按 category 读回来（验收：13+ 全部有读口）。

    这里刻意不做客户端二次过滤：先让别的类别也有行，再要求**服务端返回的这一页**
    只含本类别。否则「category 过滤被丢掉」这种接错对象的改法，客户端筛一筛就绿了。
    """
    from sqlalchemy import func, select

    for cat in AUDIT_CATEGORIES:
        await _add(db_session, category=cat, action="probe", target=cat, operator="admin")
    # 再放一行不属于任何登记类别的脏数据，保证过滤失效时一定会混进来
    await _add(db_session, category="not_registered", action="noise", target="noise")

    for cat in AUDIT_CATEGORIES:
        body = client.get(f"{URL}?category={cat}&page_size=100", headers=_auth(admin_token["token"])).json()
        assert body["code"] == 0, f"{cat} 读取失败：{body}"
        items = body["data"]["items"]
        assert items, f"{cat} 写进去了却读不到：{body['data']['total']}"
        assert {i["category"] for i in items} == {cat}, f"{cat} 的查询串到了别的类别：{sorted({i['category'] for i in items})}"
        expected_total = await db_session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.category == cat)
        )
        assert body["data"]["total"] == expected_total, \
            f"{cat} 的 total={body['data']['total']}，与库里该类别的 {expected_total} 行不符（过滤没生效）"


async def test_category_summary_covers_every_registered_category(client, admin_token, db_session):
    """汇总口一次调用即可清点：未落过库的类别也要出现（count=0），否则「读不到」和「没数据」分不清。"""
    await _add(db_session, category="backup", action="restore")
    await _add(db_session, category="backup", action="restore")
    await _add(db_session, category="review", action="approve")

    data = client.get(f"{URL}/categories", headers=_auth(admin_token["token"])).json()["data"]
    by_cat = {i["category"]: i for i in data["items"]}
    assert set(by_cat) == set(AUDIT_CATEGORIES)
    assert by_cat["backup"]["count"] == 2 and by_cat["review"]["count"] == 1
    assert by_cat["user"]["count"] == 0 and by_cat["user"]["latest_at"] is None
    assert by_cat["backup"]["latest_at"] is not None


async def test_operator_role_admin_can_read_all_categories(client, db_session):
    """裁决口径：全量管理员可读——非 superadmin 的 B 端登录态同样能读高危类别。"""
    await _add(db_session, category="backup", action="restore", target="database", operator="admin")
    token, _, _ = create_access_token(
        "2", token_type="admin", extra_claims={"username": "ops", "role": "operator"}
    )
    body = client.get(f"{URL}?category=backup", headers=_auth(token)).json()
    assert body["code"] == 0, f"operator 角色被挡住，与「全量管理员可读」裁决不符：{body}"
    assert body["data"]["items"][0]["action"] == "restore"


async def test_anonymous_and_c_end_caller_cannot_read(client, db_session, user_token):
    """越权的调用方读不到：匿名与 C 端 token 都不该拿到任何审计行。"""
    await _add(db_session, category="user", action="toggle_status", operator="admin")

    anon = client.get(URL).json()
    assert anon["code"] == 401, f"匿名读到了审计：{anon}"
    c_end = client.get(URL, headers=_auth(user_token["token"])).json()
    assert c_end["code"] == 401, f"C 端 token 读到了审计：{c_end}"
    anon_summary = client.get(f"{URL}/categories").json()
    assert anon_summary["code"] == 401, f"匿名读到了类别汇总：{anon_summary}"


async def test_unknown_category_is_rejected(client, admin_token, db_session):
    """未知类别不给「静默空列表」——那会让运营以为这个模块没有审计。"""
    await _add(db_session, category="ad", action="update")
    body = client.get(f"{URL}?category=admingmt", headers=_auth(admin_token["token"])).json()
    assert body["code"] == 400, f"未登记的类别被照单全收：{body}"
    assert "admingmt" in body["message"]


async def test_action_and_time_range_filters(client, admin_token, db_session):
    """按动作与时间范围筛：值班查「昨天那次恢复」不该靠翻页。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await _add(db_session, category="backup", action="create", created_at=now - timedelta(days=3))
    await _add(db_session, category="backup", action="restore", created_at=now - timedelta(days=1))
    await _add(db_session, category="backup", action="cleanup", created_at=now)

    h = _auth(admin_token["token"])
    one_action = client.get(f"{URL}?category=backup&action=restore", headers=h).json()["data"]
    assert [i["action"] for i in one_action["items"]] == ["restore"]

    window = (now - timedelta(days=2)).isoformat()
    ranged = client.get(f"{URL}?category=backup&start={window}", headers=h).json()["data"]
    assert {i["action"] for i in ranged["items"]} == {"restore", "cleanup"}
    assert ranged["total"] == 2

    up_to = client.get(f"{URL}?category=backup&end={window}", headers=h).json()["data"]
    assert {i["action"] for i in up_to["items"]} == {"create"}


async def test_newest_first_and_pagination(client, admin_token, db_session):
    """倒序 + 分页：total 是全量条数，items 只是本页。"""
    base = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(5):
        await _add(db_session, category="queue", action=f"a{i}", created_at=base + timedelta(hours=i))

    h = _auth(admin_token["token"])
    page1 = client.get(f"{URL}?category=queue&page=1&page_size=2", headers=h).json()["data"]
    page2 = client.get(f"{URL}?category=queue&page=2&page_size=2", headers=h).json()["data"]
    assert page1["total"] == 5
    assert [i["action"] for i in page1["items"]] == ["a4", "a3"]
    assert [i["action"] for i in page2["items"]] == ["a2", "a1"]


async def test_detail_is_masked_on_read(client, admin_token, db_session):
    """历史明文行也要在展示层过滤：新读口不能变成第二条泄露通道（T02486 / T02591）。"""
    # 直接写「修复前」形态：detail 里带密钥形状的原值
    await _add(
        db_session,
        category="cos",
        action="update_config",
        detail='{"secret_id": "AKIAIOSFODNN7EXAMPLE", "bucket": "news"}',
    )
    item = client.get(f"{URL}?category=cos", headers=_auth(admin_token["token"])).json()["data"]["items"][0]
    assert item["detail"]["secret_id"] == "***", f"审计读口回显明文密钥：{item['detail']}"
    assert item["detail"]["bucket"] == "news", "无关字段被顺手改坏"


async def test_unparsable_detail_does_not_break_the_list(client, admin_token, db_session):
    """detail 不是合法 JSON（历史脏数据）时原样带出，不能整页 500。"""
    await _add(db_session, category="material", action="cleanup", detail="清理了 3 个文件")
    item = client.get(f"{URL}?category=material", headers=_auth(admin_token["token"])).json()["data"]["items"][0]
    assert item["detail"] == "清理了 3 个文件"


async def test_high_risk_action_records_who_what_why(client, admin_token, db_session):
    """第 3 点：高危动作的审计要「谁 / 对什么 / 为什么」都读得出来。

    改前 user 那条写的是 `str({...})`——Python repr 不是 JSON，读口拿到的是
    一整串 `{'disabled': 1}`，既按字段查不到、也永远没有原因可查。
    """
    from app.models.user import User

    u = User(openid="o_t02909", nickname="被停用的张三")
    db_session.add(u)
    await db_session.commit()

    resp = client.post(
        f"/admin/api/v1/users/{u.id}/toggle-status",
        json={"disabled": 1, "reason": "多次违规上传"},
        headers=_auth(admin_token["token"]),
    )
    assert resp.json()["code"] == 0, resp.json()

    item = client.get(f"{URL}?category=user", headers=_auth(admin_token["token"])).json()["data"]["items"][0]
    assert item["operator"] == "admin"
    assert item["target"] == str(u.id)
    assert isinstance(item["detail"], dict), f"detail 不是 JSON，读口只能整串吐出：{item['detail']!r}"
    assert item["detail"]["reason"] == "多次违规上传"
    assert item["detail"]["nickname"] == "被停用的张三"
    assert item["detail"]["disabled"] == 1
