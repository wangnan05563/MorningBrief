"""T03319（C91）：整本上传遇重复章节不再「半本入库」。

红基线（改前）：`upload_document` / `import_from_cos` 循环调用 `_persist_material`，
而后者每章自提交；第 N 章命中重复时前 N-1 章已落库，响应只有一句与「整本上传」
无关的 409，库里留下半本书。

修法：整本先按 `(source_type, channel_id, dedup_key)` 一次性预检，再把缺的章节
写进**同一个事务**；已存在的章节按章跳过并回报 `skipped`（断点续传）。
这里断言的是**库里的章节集合**，不是只看返回码——半本入库的现场就是「返回码看着
有理、库里却缺章」，只看 code 会放过它。
"""
import pytest
from sqlalchemy import select

from app.core.exceptions import BizError
from app.models import Material
from app.models.material import MaterialSourceType, MaterialStatus
from app.services.document_ingest import compute_content_hash

UPLOAD_URL = "/admin/api/v1/materials/upload"
COS_URL = "/admin/api/v1/materials/import-cos"

CH1 = "第一章正文：小镇的清晨很安静，主角在这里长大，也为后面的冒险埋下伏笔。"
CH2 = "第二章正文：主线冲突逐步升级，人物关系变得复杂，读者开始理解故事的主题。"
CH3 = "第三章正文：结局收束伏笔，主角回到小镇，把所有线索重新串成一条完整的线。"


@pytest.fixture
def stub_blacklist(monkeypatch):
    """绕过 is_in_blacklist 的 DB 查询，避免命中生产 SQLite 文件。"""
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def _book(*chapters: tuple[str, str]) -> bytes:
    """按 Markdown 标题拼一本多章书（解析器按 # 标题分章）。"""
    return "\n".join(f"# {title}\n{body}" for title, body in chapters).encode("utf-8")


def _headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def _upload(client, admin_token, *, channel_id: int, raw: bytes, filename="测试书.txt"):
    return client.post(
        UPLOAD_URL,
        files={"file": (filename, raw, "text/plain")},
        data={"channel_id": str(channel_id), "source": "文档上传"},
        headers=_headers(admin_token),
    )


async def _seed_chapter(db_session, *, channel_id: int, content: str, source="旧素材", source_type="list"):
    """预埋一条已入库章节（用于模拟「旧版半本入库」现场）。"""
    key = compute_content_hash(content)
    db_session.add(
        Material(
            source=source,
            source_type=source_type,
            title="预埋章节",
            content=content,
            url=f"{source_type}://{channel_id}/{key[:16]}",
            dedup_key=key,
            status=MaterialStatus.pending.value,
            channel_id=channel_id,
        )
    )
    await db_session.commit()


async def _contents(db_session, *, channel_id: int, source_type="list") -> list[str]:
    """频道内某来源类型的全部章节正文（排序后便于判断「缺章/重复」）。"""
    res = await db_session.execute(
        select(Material.content).where(
            Material.channel_id == channel_id,
            Material.source_type == source_type,
        )
    )
    return sorted(res.scalars().all())


async def test_existing_middle_chapter_no_longer_leaves_half_book(
    client, admin_token, db_session, stub_blacklist
):
    """频道里已有第 2 章时整本上传：三章齐全、无重复，而不是停在第 2 章留下半本。"""
    await _seed_chapter(db_session, channel_id=77, content=CH2)

    body = _upload(
        client, admin_token, channel_id=77,
        raw=_book(("第一章", CH1), ("第二章", CH2), ("第三章", CH3)),
    ).json()

    assert body["code"] == 0, f"整本上传被重复章节打断：{body}"
    data = body["data"]
    assert data["count"] == 2 and data["skipped"] == 1, data
    assert data["skipped_titles"] == ["测试书 · 第二章"], data["skipped_titles"]
    assert await _contents(db_session, channel_id=77) == sorted([CH1, CH2, CH3])


async def test_reupload_after_half_book_fills_the_missing_chapters(
    client, admin_token, db_session, stub_blacklist
):
    """断点续传：旧版留下的「只有第 1 章」半本，重新上传即可补齐后两章。"""
    await _seed_chapter(db_session, channel_id=88, content=CH1, source="测试书")

    body = _upload(
        client, admin_token, channel_id=88,
        raw=_book(("第一章", CH1), ("第二章", CH2), ("第三章", CH3)),
    ).json()

    assert body["code"] == 0, body
    assert body["data"]["count"] == 2 and body["data"]["skipped"] == 1, body["data"]
    assert body["data"]["skipped_titles"] == ["测试书 · 第一章"], body["data"]["skipped_titles"]
    assert await _contents(db_session, channel_id=88) == sorted([CH1, CH2, CH3])


async def test_reuploading_whole_book_is_idempotent(
    client, admin_token, db_session, stub_blacklist
):
    """整本重复上传：0 新增、全章跳过，库里不出现第二份。"""
    raw = _book(("第一章", CH1), ("第二章", CH2), ("第三章", CH3))
    first = _upload(client, admin_token, channel_id=66, raw=raw).json()
    assert first["data"]["count"] == 3 and first["data"]["skipped"] == 0, first

    second = _upload(client, admin_token, channel_id=66, raw=raw).json()
    assert second["code"] == 0, second
    assert second["data"]["count"] == 0 and second["data"]["skipped"] == 3, second["data"]
    assert await _contents(db_session, channel_id=66) == sorted([CH1, CH2, CH3])


async def test_duplicate_chapters_inside_one_book_insert_once(
    client, admin_token, db_session, stub_blacklist
):
    """同一本书里正文完全相同的两章只入一次（批内重复也不许 409 打断整本）。"""
    body = _upload(
        client, admin_token, channel_id=55,
        raw=_book(("第一章", CH1), ("第二章", CH1), ("第三章", CH2)),
    ).json()

    assert body["code"] == 0, body
    assert body["data"]["count"] == 2 and body["data"]["skipped"] == 1, body["data"]
    assert body["data"]["skipped_titles"] == ["测试书 · 第二章"], body["data"]["skipped_titles"]
    assert await _contents(db_session, channel_id=55) == sorted([CH1, CH2])


async def test_same_content_in_another_channel_is_not_skipped(
    client, admin_token, db_session, stub_blacklist
):
    """接错对象护栏：去重是**频道级**的，另一频道的同内容不能被当成「已存在」。"""
    await _seed_chapter(db_session, channel_id=11, content=CH1)

    body = _upload(
        client, admin_token, channel_id=22,
        raw=_book(("第一章", CH1), ("第二章", CH2)),
    ).json()

    assert body["code"] == 0, body
    assert body["data"]["count"] == 2 and body["data"]["skipped"] == 0, body["data"]
    assert await _contents(db_session, channel_id=22) == sorted([CH1, CH2])
    assert await _contents(db_session, channel_id=11) == [CH1]


async def test_failure_midway_commits_nothing(
    client, admin_token, db_session, stub_blacklist, monkeypatch
):
    """第 3 章构造阶段异常：整本 0 条落库，而不是「前两章已入库」。"""
    import app.routers.admin.materials as materials_routes

    real_make = materials_routes._make_material
    calls = {"n": 0}

    async def _boom_on_third(db, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("模拟第 3 章构造失败")
        return await real_make(db, **kwargs)

    monkeypatch.setattr(materials_routes, "_make_material", _boom_on_third)

    with pytest.raises(RuntimeError):
        _upload(
            client, admin_token, channel_id=5,
            raw=_book(("第一章", CH1), ("第二章", CH2), ("第三章", CH3)),
        )

    assert calls["n"] == 3
    assert await _contents(db_session, channel_id=5) == []


async def test_concurrent_duplicate_falls_back_to_409_without_partial(
    client, admin_token, db_session, stub_blacklist, monkeypatch
):
    """预检漏掉、提交时才撞唯一约束：409 且整本回滚，不留半本。"""
    import app.routers.admin.materials as materials_routes

    async def _precheck_misses(db, **kwargs):
        return set()

    monkeypatch.setattr(materials_routes, "_existing_dedup_keys", _precheck_misses)
    await _seed_chapter(db_session, channel_id=9, content=CH2)

    body = _upload(
        client, admin_token, channel_id=9,
        raw=_book(("第一章", CH1), ("第二章", CH2), ("第三章", CH3)),
    ).json()

    assert body["code"] == 409, body
    assert "未写入任何章节" in body["message"], body["message"]
    # 只剩场景预埋的那条：第 1 章不能因为「早于冲突章」而被写进去
    assert await _contents(db_session, channel_id=9) == [CH2]


async def test_cos_import_uses_same_atomic_skip_semantics(
    client, admin_token, db_session, stub_blacklist, monkeypatch
):
    """COS 导入与文档上传同一口径：整本单事务 + 跳过已存在章节。"""
    from app.services.cos_storage_service import CosStorageService

    async def _fake_bytes(self, key):
        return _book(("第一章", CH1), ("第二章", CH2))

    monkeypatch.setattr(CosStorageService, "get_object_bytes", _fake_bytes)
    await _seed_chapter(db_session, channel_id=21, content=CH1, source_type="cos")

    body = client.post(
        COS_URL,
        json={"key": "books/测试书.txt", "channel_id": 21, "source": "COS导入"},
        headers=_headers(admin_token),
    ).json()

    assert body["code"] == 0, body
    assert body["data"]["count"] == 1 and body["data"]["skipped"] == 1, body["data"]
    assert body["data"]["skipped_titles"] == ["第一章"], body["data"]["skipped_titles"]
    assert await _contents(db_session, channel_id=21, source_type="cos") == sorted([CH1, CH2])


async def test_single_persist_still_409_on_duplicate(db_session):
    """单条入库语义不变：重复仍 409，且不覆盖已入库的那条。"""
    from app.routers.admin.materials import _persist_material

    key = compute_content_hash(CH1)
    await _persist_material(
        db_session, channel_id=30, source="手动录入", title="第一章",
        content=CH1, source_type=MaterialSourceType.list.value, dedup_key=key,
    )
    with pytest.raises(BizError) as ei:
        await _persist_material(
            db_session, channel_id=30, source="手动录入", title="重复章节",
            content=CH1, source_type=MaterialSourceType.list.value, dedup_key=key,
        )
    assert ei.value.code == 409
    assert await _contents(db_session, channel_id=30) == [CH1]
