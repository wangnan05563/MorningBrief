"""T02490（FR-UX-202）破坏性操作确认口径的后端断言。

覆盖两处「确认框要说真话」的服务端前提：
1. 频道删除预览的条数必须与真实数据一致，且三类连带后果各有依据；
2. 数据库后台的级联预览要显式标出「未声明的下游不会被删」。
"""
import inspect
from datetime import date

import pytest
from sqlalchemy import delete, select

from app.database import _set_sqlite_pragma
from app.models.book_pool import BookPoolItem
from app.models.channel import Channel
from app.models.material import Material
from app.models.workflow import Workflow
from app.services.channel_service import ChannelService
from app.services.db_admin_service import UNDECLARED_DOWNSTREAM, DbAdminService

_MISSING_ID = 999999


@pytest.fixture
async def seeded_channel(db_session):
    """一条频道 + 1 本书（池项）+ 1 条素材 + 1 条工作流，覆盖预览里三行计数。"""
    channel = Channel(name="预览测试频道", description="t02490", is_active=1)
    db_session.add(channel)
    await db_session.flush()
    material = Material(
        source="书 A",
        source_type="rss",
        title="素材 A",
        content="正文",
        url="https://example.com/t02490/m1",
        channel_id=channel.id,
    )
    db_session.add(material)
    await db_session.flush()
    db_session.add(
        BookPoolItem(channel_id=channel.id, material_id=material.id, book_key="书 A", title="书 A")
    )
    db_session.add(
        Workflow(
            id="t02490-wf",
            episode_date=date(2026, 10, 18),
            source="manual",
            channel_id=channel.id,
        )
    )
    await db_session.commit()
    yield channel
    await db_session.execute(delete(Workflow).where(Workflow.id == "t02490-wf"))
    await db_session.execute(delete(Material).where(Material.channel_id == channel.id))
    await db_session.execute(delete(BookPoolItem).where(BookPoolItem.channel_id == channel.id))
    await db_session.execute(delete(Channel).where(Channel.id == channel.id))
    await db_session.commit()


@pytest.mark.anyio
async def test_channel_delete_preview_counts_match_real_rows(db_session, seeded_channel):
    svc = ChannelService(db_session)
    preview = await svc.delete_preview(channel_id=seeded_channel.id)
    assert preview["channel_name"] == "预览测试频道"
    # 确认框写的是「书单 N 本 / 素材 N 条 / 工作流 N 条」，这里必须与真实行数一致
    assert preview["book_pool_items"] == 1
    assert preview["materials"] == 1
    assert preview["workflows"] == 1


@pytest.mark.anyio
async def test_channel_delete_preview_missing_channel(db_session):
    svc = ChannelService(db_session)
    with pytest.raises(ValueError):
        await svc.delete_preview(channel_id=_MISSING_ID)


@pytest.mark.anyio
async def test_delete_channel_nulls_workflow_but_pool_relies_on_cascade(db_session, seeded_channel):
    """预览第三行「工作流置空」由应用层显式 UPDATE 保证；「书单随频道删除」由 schema 声明。"""
    svc = ChannelService(db_session)
    await svc.delete_channel(channel_id=seeded_channel.id)

    wf = (
        await db_session.execute(select(Workflow).where(Workflow.id == "t02490-wf"))
    ).scalar_one()
    assert wf.channel_id is None, "工作流应保留、仅置空 channel_id"

    fk = next(iter(BookPoolItem.__table__.columns["channel_id"].foreign_keys))
    assert fk.ondelete == "CASCADE", "书单条数说的是级联删除，schema 必须真的声明 CASCADE"
    # 级联能否生效取决于连接级 PRAGMA foreign_keys=ON（SQLite 默认关闭）；
    # 测试库另建引擎未带该 PRAGMA，故这里断言生产引擎的开关仍然存在
    assert "foreign_keys=ON" in inspect.getsource(_set_sqlite_pragma)


@pytest.mark.anyio
async def test_cascade_preview_exposes_undeclared_downstream(db_session):
    admin = DbAdminService(db_session)
    wf_preview = await admin.cascade_preview("workflow", ["no-such-workflow-id"])
    assert wf_preview["undeclared_downstream"] == UNDECLARED_DOWNSTREAM["workflow"]

    ep_preview = await admin.cascade_preview("episode", [_MISSING_ID])
    assert ep_preview["undeclared_downstream"] is None


@pytest.mark.anyio
async def test_channel_delete_preview_endpoint(client, admin_token):
    resp = client.get(
        f"/admin/api/v1/channels/{_MISSING_ID}/delete-preview",
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 404
