"""NFR-UX-03（T02521）分页尺寸上限的门禁与口径纠正。

本单要钉死两件事：

1. **上限确实存在**：所有分页类 query 参数都必须带 `le`，且默认不得超过 100。
   判据取自 OpenAPI（`app.openapi()`）而不是 grep 源码——`Query(ge=, le=)` 写成
   `ge=1, le=100` 还是 `Query(default=20, ge=1, le=100)`、参数换行与否都不影响，
   而源码正则一定会漏掉某种排版。
2. **「越界会被后端静默钳回 100」是错的**：`core/exceptions.py:70` 把
   `RequestValidationError` 统一转成 **HTTP 400**，所以前端把 `?size=999` 原样发出去
   不是「反正会被钳」，而是**必定失败**（WorkflowList 漏 `max` 的真实后果）。
   这条用行为断言证明，不用注释证明。
"""
import pytest

# 超过 100 的分页参数白名单：**必须**逐项写明理由，新增一项就等于承认一处新的例外。
# 它们都不是「管理端列表页的分页档位」，不受 NFR-UX-03 约束。
PAGE_SIZE_EXCEPTIONS = {
    # 移动端公开评论区：一屏滚动加载 200 条，没有管理端表格的渲染成本
    ("GET", "/api/v1/comments", "size"): 200,
    # 数据库维护页是「运维直查」入口，审计日志一次拉 500 条用于排障
    ("GET", "/admin/api/v1/db-admin/audit-log", "limit"): 500,
    # 同上：通用表浏览要能一屏看下一千行才谈得上「排查脏数据」
    ("GET", "/admin/api/v1/db-admin/tables/{table}/rows", "limit"): 1000,
}

PAGE_PARAM_NAMES = {"size", "page_size", "limit", "per_page"}
NFR_MAX_PAGE_SIZE = 100


def _page_params(app):
    """从 OpenAPI 抽出所有分页类 query 参数 → [(method, path, name, maximum, minimum)]。"""
    spec = app.openapi()
    out = []
    for path, methods in (spec.get("paths") or {}).items():
        for method, op in (methods or {}).items():
            if not isinstance(op, dict):
                continue
            for p in op.get("parameters") or []:
                if p.get("in") != "query" or p.get("name") not in PAGE_PARAM_NAMES:
                    continue
                schema = p.get("schema") or {}
                out.append((method.upper(), path, p["name"], schema.get("maximum"), schema.get("minimum")))
    return out


@pytest.fixture
def page_params(app):
    return _page_params(app)


def test_openapi_枚举到分页参数(page_params):
    """枚举没空跑：一条都没有说明取参方式失效，后面的断言就全是自我安慰。"""
    assert len(page_params) >= 15, f"只扫到 {len(page_params)} 个分页参数，取值口径可能已变"


def test_所有分页参数都有上限(page_params):
    """漏 `le` 的参数可以让前端要多少给多少——上限门禁的第一条是「不许没有上限」。"""
    unbounded = [(m, p, n) for m, p, n, mx, _ in page_params if mx is None]
    assert unbounded == [], f"以下分页参数没有 le 上限：{unbounded}"


def test_所有分页参数都有下限(page_params):
    """`ge=1` 同理由：`?size=0` / `?limit=-5` 会走进「每页 0 条」的死循环分页。"""
    no_min = [(m, p, n) for m, p, n, _, mn in page_params if mn is None]
    assert no_min == [], f"以下分页参数没有 ge 下限：{no_min}"


def test_超上限的分页参数只能是白名单那几处(page_params):
    """NFR-UX-03 的「上限 100」管的是管理端列表；其它端点要放宽必须登记理由。"""
    actual = {(m, p, n): mx for m, p, n, mx, _ in page_params if mx and mx > NFR_MAX_PAGE_SIZE}
    assert actual == PAGE_SIZE_EXCEPTIONS, (
        "分页上限例外发生变化：新增/删除/改动上限都要在这里登记，"
        f"实际={actual}，登记={PAGE_SIZE_EXCEPTIONS}"
    )


def test_列表页用到的管理端接口上限就是_100(page_params):
    """管理端列表页档位（PAGE_SIZE_OPTIONS 的 100）必须逐一对上后端 le=100。

    这一条是「前端档位 100」与「后端 le=100」的契约缝：任何一边改动都会在这里红。
    """
    watched = {
        "/admin/api/v1/workflows",
        "/admin/api/v1/reviews",
        "/admin/api/v1/materials",
        "/admin/api/v1/queue/tasks",
        "/admin/api/v1/m/inbox",
    }
    seen = {(m, p, n): mx for m, p, n, mx, _ in page_params if p in watched}
    assert set(p for _, p, _ in seen) == watched, f"这些列表接口没扫到分页参数：{watched - set(p for _, p, _ in seen)}"
    assert all(mx == NFR_MAX_PAGE_SIZE for mx in seen.values()), f"列表接口上限不等于 100：{seen}"


class Test越界是400不是静默钳回:
    """行为证据：把 400 这件事从「我觉得」变成「跑出来的」。"""

    @pytest.fixture
    def stub_blacklist(self, monkeypatch):
        """绕过 is_in_blacklist 的 DB 查询，避免命中生产 SQLite 文件（与各路由测试同法）。"""

        async def _always_false(jti: str) -> bool:
            return False

        monkeypatch.setattr("app.core.auth.is_in_blacklist", _always_false)

    @pytest.fixture
    def admin(self, client, admin_token, stub_blacklist):
        client.headers = {"Authorization": f"Bearer {admin_token['token']}"}
        return client

    @pytest.mark.parametrize("path,over,ok_value", [
        ("/admin/api/v1/workflows", {"size": 101}, {"size": 100}),
        ("/admin/api/v1/reviews", {"size": 999}, {"size": 100}),
        ("/admin/api/v1/m/inbox", {"page_size": 101}, {"page_size": 100}),
    ])
    def test_越界被判400(self, admin, path, over, ok_value):
        r = admin.get(path, params=over)
        assert r.status_code == 400, (
            f"{path} 越界 {over} 期望 400，实得 {r.status_code}：{r.text[:200]}"
        )
        assert "参数错误" in r.text, f"400 应来自 RequestValidationError，实得：{r.text[:200]}"
        # 上限值本身必须可用，否则「钳到 100」这个前端策略会把页面打死
        assert admin.get(path, params=ok_value).status_code == 200

    @pytest.mark.parametrize("path,key", [
        ("/admin/api/v1/workflows", "size"),
        ("/admin/api/v1/reviews", "size"),
    ])
    def test_下界同样判400(self, admin, path, key):
        assert admin.get(path, params={key: 0}).status_code == 400
        assert admin.get(path, params={key: -1}).status_code == 400


def test_异常处理器把校验错误映射成400():
    """口径的出处：core/exceptions.py 里 RequestValidationError → http_status=400。

    行为断言已经证明过一次，这条是防止有人把处理器改成「返回 200 + 空列表」
    来「兼容前端」——那会让「静默钳回」的错误说法重新变成事实，且更难发现。
    """
    import inspect

    from app.core import exceptions

    src = inspect.getsource(exceptions.register_exception_handlers)
    block = src[src.index("RequestValidationError"):]
    assert "http_status=400" in block[:400], "校验错误必须仍是 400，不许改成静默兜底"
