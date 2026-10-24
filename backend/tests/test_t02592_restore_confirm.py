"""T02592：备份/恢复的危险操作确认口径统一到「手输确认文本 + 服务端总开关」。

T02486 把数据库后台三个危险接口改成了 `_validate_danger_op(confirm_text, expected)`，
但同族的 `POST /backups/restore` 仍要求前端传一个固定令牌
（`_validate_confirm_token(body.confirm_token)`）。当时它没构成泄露——令牌没被打进前端产物——
留下来的是**同一类操作的两套口径**：只要接口还要求「前端知道服务端密钥」，
就迟早有人为了图省事把密钥写进 bundle，把一个后台按钮的权限变成全体登录用户浏览器里的明文。

本文件钉住四件事：
1. 总开关（服务端配置）为空 → 一律禁止，且提示信息只说配置名，不吐配置值；
2. 确认文本与目标备份文件名不一致 → 拒绝，且响应体任何位置都不出现服务端配置值；
3. 旧的 `confirm_token` 字段彻底失效——**把真实令牌抄进来也过不去**（这才叫口径换掉了，
   而不是两种都能过）；
4. 认的是文件名（basename），不是整条路径，且首尾空白不参与比较。
"""
import pytest
from pathlib import Path

from app.routers.admin import backup as backup_router
from app.routers.admin import db_admin as db_router
from app.services.backup_service import BackupService

BASE = "/admin/api/v1/backups"
SERVER_TOKEN = "server-side-only-secret"
BACKUP_NAME = "news_backup_20261020_030000.db"


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


@pytest.fixture(autouse=True)
def _switch_on(monkeypatch):
    """默认把总开关配上：不配就永远进不到比对分支，用例测的就只是开关。"""
    monkeypatch.setattr(backup_router, "CONFIRM_TOKEN", SERVER_TOKEN)


@pytest.fixture
def restores(monkeypatch):
    """替身掉真实恢复动作——恢复会覆盖 SQLite 文件，测试里绝不能真跑。"""
    calls: list[str] = []

    async def fake_restore(backup_path: str) -> bool:
        calls.append(backup_path)
        return True

    monkeypatch.setattr(BackupService, "restore_backup", staticmethod(fake_restore))
    return calls


def _post(client, auth, body):
    return client.post(f"{BASE}/restore", json=body, headers=auth)


# ---- ① 总开关 ----

def test_empty_switch_forbids_even_with_correct_text(client, auth, restores, monkeypatch):
    """DB_ADMIN_CONFIRM_TOKEN 没配 → 连确认文本都对了也不许恢复。"""
    monkeypatch.setattr(backup_router, "CONFIRM_TOKEN", "")
    r = _post(client, auth, {"backup_path": f"backup/{BACKUP_NAME}", "confirm_text": BACKUP_NAME})
    assert r.status_code == 400
    assert "DB_ADMIN_CONFIRM_TOKEN" in r.text
    assert restores == []


# ---- ② 确认文本比对 ----

def test_mismatched_text_rejected_and_leaks_no_server_value(client, auth, restores):
    r = _post(client, auth, {"backup_path": f"backup/{BACKUP_NAME}", "confirm_text": "RESTORE"})
    assert r.status_code == 400
    assert "确认文本不匹配" in r.text
    assert BACKUP_NAME in r.text, "报错要指出该输什么，否则运维只能猜"
    assert SERVER_TOKEN not in r.text, "响应体任何位置（含回显字段）都不该出现服务端配置值"
    assert restores == []


def test_missing_confirm_text_is_rejected(client, auth, restores):
    """不传确认文本（默认空串）必须被拒——否则「不带确认」就成了默认放行。"""
    r = _post(client, auth, {"backup_path": f"backup/{BACKUP_NAME}"})
    assert r.status_code == 400
    assert "确认文本不匹配" in r.text
    assert restores == []


def test_correct_backup_name_passes(client, auth, restores):
    path = f"backup/{BACKUP_NAME}"
    r = _post(client, auth, {"backup_path": path, "confirm_text": BACKUP_NAME})
    assert r.status_code == 200, r.text
    assert restores == [path]


def test_confirm_compares_basename_not_whole_path(client, auth, restores):
    """运维从列表里拿到的是路径，手输的是文件名：比对必须落在 basename 上。"""
    r = _post(
        client,
        auth,
        {"backup_path": f"D:/data/news/backup/{BACKUP_NAME}", "confirm_text": BACKUP_NAME},
    )
    assert r.status_code == 200, r.text
    assert restores == [f"D:/data/news/backup/{BACKUP_NAME}"]


def test_surrounding_whitespace_ignored(client, auth, restores):
    """与 db_admin 同口径：首尾空白不参与比较（复制粘贴带个空格不该变成一次失败）。"""
    r = _post(client, auth, {"backup_path": f"backup/{BACKUP_NAME}", "confirm_text": f"  {BACKUP_NAME}  "})
    assert r.status_code == 200, r.text
    assert restores == [f"backup/{BACKUP_NAME}"]


# ---- ③ 旧口径已死 ----

def test_server_token_as_confirm_text_does_not_work(client, auth, restores):
    """把真实令牌抄进 confirm_text 也过不去：认的是备份文件名。

    这条是本单的核心牙齿。若实现写成「confirm_text 等于令牌或文件名都放行」，
    上一切「前端内置密钥」的用法就还能跑通，两个口径只是叠在一起而没有收敛。
    """
    r = _post(client, auth, {"backup_path": f"backup/{BACKUP_NAME}", "confirm_text": SERVER_TOKEN})
    assert r.status_code == 400
    assert "确认文本不匹配" in r.text
    assert SERVER_TOKEN not in r.text
    assert restores == []


def test_legacy_confirm_token_field_is_ignored(client, auth, restores):
    """老请求体（只带 confirm_token）不再被接受——字段本身已从模型里去掉。"""
    r = client.post(
        f"{BASE}/restore",
        json={"backup_path": f"backup/{BACKUP_NAME}", "confirm_token": SERVER_TOKEN},
        headers=auth,
    )
    assert r.status_code == 400
    assert restores == []


# ---- ④ 同一套口径（而不是两份实现）----

def test_backup_and_db_admin_use_the_same_wording(client, auth, monkeypatch):
    """两个路由的拒绝话术必须逐字一致。

    这条防的是「以后又加第四个危险接口，复制一份比较逻辑、话术各写各的」。
    两处都指向 `app/core/danger_op.validate_danger_op`，话术只有一个来源；
    任何一方被改回本地实现，这句断言就会红。
    """
    monkeypatch.setattr(db_router, "CONFIRM_TOKEN", SERVER_TOKEN)
    db = client.delete(
        "/admin/api/v1/db-admin/tables/admin_user/rows/1",
        params={"confirm_text": "wrong_table"},
        headers=auth,
    )
    bk = _post(client, auth, {"backup_path": f"backup/{BACKUP_NAME}", "confirm_text": "wrong_name"})
    prefix = "确认文本不匹配，请输入 "
    assert db.text.count(prefix) == 1 and bk.text.count(prefix) == 1, (db.text, bk.text)


def test_router_module_no_longer_references_confirm_token():
    """源码层面确认旧口径没被留在某个角落（比如「两种都兼容」的分支）。"""
    import inspect

    src = inspect.getsource(backup_router)
    assert "confirm_token" not in src, "backup.py 里不该再出现 confirm_token 形态的口径"
    assert "validate_danger_op" in src, "恢复接口要复用单一口径的实现"


def test_no_frontend_source_embeds_a_confirm_token():
    """两端口径的「另一头」：前端源码里不许出现 confirm_token 形态的内置密钥。

    这条是 2026-10-13 那次真实形态的回归检查——当时的构建产物把服务端的
    `DB_ADMIN_CONFIRM_TOKEN` 值原样硬编码进了 `DatabaseAdmin-*.js`
    （`{params:{confirm_token:"CONFIRM_DELETE"}}`），等价于把危险操作权限打包进浏览器。
    扫描范围只覆盖 src/（不含 dist/ 与 temp/ 的历史产物），命中即说明有人又开始
    「让前端知道服务端配置值」。
    """
    roots = [
        Path(__file__).resolve().parents[2] / "apps" / "admin-web" / "src",
        Path(__file__).resolve().parents[2] / "apps" / "miniprogram",
    ]
    hits = []
    for root in roots:
        for f in root.rglob("*"):
            if not f.is_file() or f.suffix not in {".js", ".vue", ".wxs", ".json"}:
                continue
            if "confirm_token" in f.read_text(encoding="utf-8", errors="replace"):
                hits.append(str(f.relative_to(root.parent)))
    assert hits == [], f"前端里出现了 confirm_token 形态的内置密钥：{hits}"
