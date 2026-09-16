"""听书频道一致性校验 + 找书一键送审测试（T00626 P2）。

- `evaluate_audiobook_consistency`：纯函数五场景（非听书频道放行 / 单书+顺序+正版通过 /
  跨书拒绝 / 乱序拒绝 / 缺正版提醒拒绝）；
- `POST /ebooks/draft-material`：加入待讲书单（写素材占位）→ 幂等重复点击返回 created=false
  → 缺 url / 缺书名 400。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_ebook_audiobook_guard.py
"""
import pytest

from app.services.auto_review_service import evaluate_audiobook_consistency as ev


class TestAudiobookConsistency:
    def test_non_audiobook_channel_passes(self):
        ok, msg = ev("news", ["来源A", "来源B"], [2, 1], "任意文本")
        assert ok is True and msg == ""

    def test_single_book_ordered_with_copyright_passes(self):
        ok, _ = ev("audiobook", ["我只知道人是什么"], [3, 4, 5], "结尾：请支持正版原著。")
        assert ok is True

    def test_multi_book_rejected(self):
        ok, msg = ev("audiobook", ["书A", "书B"], [1, 2], "请支持正版")
        assert ok is False and "单书聚焦" in msg

    def test_out_of_order_rejected(self):
        ok, msg = ev("audiobook", ["书A"], [3, 1, 2], "请支持正版")
        assert ok is False and "衔接异常" in msg

    def test_missing_copyright_notice_rejected(self):
        ok, msg = ev("audiobook", ["书A"], [1, 2], "感谢收听，明天见。")
        assert ok is False and "正版提醒" in msg

    def test_empty_inputs_pass_when_single_book(self):
        """缺数据（如素材来源为空）不应误判为跨书。"""
        ok, _ = ev("audiobook", [], [], "请支持正版")
        assert ok is True


# ---------------------------------------------------------------------------
# 找书工具「加入待讲书单」
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_blacklist(monkeypatch):
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_draft_material_created_then_idempotent(client, admin_token, stub_blacklist):
    payload = {
        "title": "我只知道人是什么",
        "author": "余华",
        "category": "文学",
        "url": "https://example.com/ebook/yu-hua-1",
    }
    first = client.post("/admin/api/v1/ebooks/draft-material", json=payload,
                        headers=_headers(admin_token)).json()
    assert first["code"] == 0, first
    assert first["data"]["created"] is True
    assert "加入待讲书单" in first["data"]["message"]

    # 幂等：同 url 再点一次 → created=false 且返回既有素材 id
    second = client.post("/admin/api/v1/ebooks/draft-material", json=payload,
                         headers=_headers(admin_token)).json()
    assert second["code"] == 0
    assert second["data"]["created"] is False
    assert second["data"]["material_id"] == first["data"]["material_id"]


def test_draft_material_requires_title_and_url(client, admin_token, stub_blacklist):
    bad_url = client.post("/admin/api/v1/ebooks/draft-material",
                          json={"title": "书", "url": ""}, headers=_headers(admin_token)).json()
    assert bad_url["code"] != 0 and "链接" in bad_url["message"]

    bad_title = client.post("/admin/api/v1/ebooks/draft-material",
                            json={"title": "  ", "url": "https://example.com/x"}, headers=_headers(admin_token)).json()
    assert bad_title["code"] != 0 and "书名" in bad_title["message"]


def test_draft_material_row_is_pending_placeholder(client, admin_token, stub_blacklist):
    """占位素材内容应说明「待上传书稿」并带书源链接（便于运营补齐）。"""
    payload = {"title": "論語", "author": "孔子", "category": "古籍", "url": "https://example.com/ebook/lunyu"}
    resp = client.post("/admin/api/v1/ebooks/draft-material", json=payload,
                       headers=_headers(admin_token)).json()
    assert resp["code"] == 0
    mid = resp["data"]["material_id"]
    # 详情接口取全文（列表接口按设计只回摘要，content 需走详情）
    detail = client.get(f"/admin/api/v1/materials/{mid}", headers=_headers(admin_token)).json()
    assert detail["code"] == 0, detail
    content = detail["data"].get("content") or ""
    assert "待上传书稿" in content, content[:80]
    assert "https://example.com/ebook/lunyu" in content
