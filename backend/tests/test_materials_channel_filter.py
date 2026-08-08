"""素材列表 channel_id 过滤 + 创建带 channel_id 测试。

背景（修复「工作流详情页 · 爬虫采集素材」面板空白）：
- 素材本质是「频道级素材池」：channel_id 始终有值，workflow_id 仅为运行期临时关联，
  工作流进入终态后由调度器重置为 NULL。
- 详情页此前按 workflow_id 查询，已完成工作流的素材因 workflow_id 被释放而全部落空。
- 修复：list_materials 增加 channel_id 过滤；详情页改为按 channel_id 查询频道素材池。
"""
import pytest

from app.models import Material
from app.models.material import MaterialSourceType, MaterialStatus


def _make_material(channel_id, url, title="素材标题", workflow_id=None):
    return Material(
        source="测试源",
        source_type=MaterialSourceType.rss.value,
        title=title,
        content="正文内容",
        url=url,
        category="tech",
        status=MaterialStatus.pending.value,
        channel_id=channel_id,
        workflow_id=workflow_id,
    )


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


async def test_list_materials_by_channel_id_filters_pool(
    client, db_session, admin_token
):
    """按 channel_id 查询返回该频道素材池，且不混入其他频道；workflow_id 为 NULL 也能命中。"""
    db_session.add(_make_material(channel_id=1, url="https://a.com/1", workflow_id=None))
    db_session.add(_make_material(channel_id=2, url="https://a.com/2", workflow_id=None))
    await db_session.commit()

    # 按 channel_id=1 查询：只返回频道 1 的素材（url 唯一可区分）
    resp = client.get(
        "/admin/api/v1/materials",
        params={"channel_id": 1},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert len(data["list"]) == 1
    assert data["list"][0]["url"] == "https://a.com/1"

    # 无过滤：返回全部 2 条
    resp_all = client.get(
        "/admin/api/v1/materials",
        headers=_admin_headers(admin_token),
    )
    assert resp_all.json()["data"]["total"] == 2


async def test_list_materials_by_released_workflow_id_is_empty(
    client, db_session, admin_token
):
    """复现旧行为：按被释放为 NULL 的 workflow_id 查询返回空（说明必须改用 channel_id）。"""
    db_session.add(_make_material(channel_id=1, url="https://a.com/1", workflow_id=None))
    await db_session.commit()

    resp = client.get(
        "/admin/api/v1/materials",
        params={"workflow_id": "wf-released"},
        headers=_admin_headers(admin_token),
    )
    assert resp.json()["data"]["total"] == 0


async def test_create_material_persists_channel_id(client, db_session, admin_token):
    """手动新增素材带 channel_id，创建后按该 channel_id 能查到（面板新增后立即可见）。"""
    resp = client.post(
        "/admin/api/v1/materials",
        json={
            "workflow_id": "wf-new",
            "channel_id": 5,
            "source": "手动",
            "title": "新增素材",
            "content": "正文",
            "url": "https://a.com/new-unique-123",
        },
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["channel_id"] == 5

    # 按 channel_id=5 查询应包含刚创建的素材
    resp2 = client.get(
        "/admin/api/v1/materials",
        params={"channel_id": 5},
        headers=_admin_headers(admin_token),
    )
    assert resp2.json()["data"]["total"] == 1
