"""T02598：素材表 channel_id 没有外键约束，频道删除会留下无主数据。

根因（工单原文）：material.channel_id 是普通整型列，既没有 ForeignKey 也没有
应用层解绑——workflow / episode 的 channel_id 都声明了 ON DELETE SET NULL，唯独素材没有。
于是删频道后素材行的 channel_id 指向已不存在的频道：按频道筛选的列表与聚合视图永远筛不到，
行却留在库里（本单执行前实测生产库 8 条，分布在 4 个悬空 channel_id）。

本测试锁两件事：
1. 源头堵住——ChannelService.delete_channel 显式把该频道素材的 channel_id 置 NULL，
   素材行保留并回到全局素材池，别的新频道素材不受影响；
2. 存量治理——清理服务的 orphan_materials_detach / orphan_materials_delete 两个目标：
   dry_run 只报数不改动、执行后条数与预览一致、审计落库，
   且二者都不参与 target=all（「全部清理」不该顺手删正文）。
"""
import json

import pytest
from sqlalchemy import func, select

from app.models import BookPoolItem, Channel, Material
from app.models.audit_log import AuditLog
from app.models.material import MaterialSourceType, MaterialStatus
from app.services.channel_service import ChannelService
from app.services.maintenance_service import MaintenanceService

_GHOST_CHANNEL_ID = 9001  # 故意指向一个不存在的频道


async def _add_channel(db, name):
    channel = Channel(name=name)
    db.add(channel)
    await db.flush()
    return channel


async def _add_material(db, url, title, channel_id):
    material = Material(
        source="测试源",
        source_type=MaterialSourceType.rss.value,
        title=title,
        content="正文内容",
        url=url,
        status=MaterialStatus.pending.value,
        channel_id=channel_id,
    )
    db.add(material)
    await db.flush()
    return material


@pytest.mark.anyio
async def test_delete_channel_detaches_materials_instead_of_orphaning(db_session):
    """删频道后素材行仍在，且 channel_id 为 NULL（不再指向已删除频道）。"""
    channel = await _add_channel(db_session, "T02598 待删频道")
    other = await _add_channel(db_session, "T02598 保留频道")
    mine = await _add_material(db_session, "https://t02598/a", "本频道素材", channel.id)
    theirs = await _add_material(db_session, "https://t02598/b", "别频道素材", other.id)

    await ChannelService(db_session).delete_channel(channel_id=channel.id)

    kept = (
        await db_session.execute(select(Material).where(Material.id == mine.id))
    ).scalar_one_or_none()
    assert kept is not None, "解绑不是删素材：正文必须还在库里"
    assert kept.channel_id is None, "channel_id 必须置空，否则就成了无主数据"
    assert (
        await db_session.execute(
            select(Material).where(Material.id == theirs.id)
        )
    ).scalar_one().channel_id == other.id, "别的频道素材不该被牵连"


@pytest.mark.anyio
async def test_orphan_ids_only_pick_dangling_channel_ids(db_session):
    """无主判定＝channel_id 有值且查无此频道；NULL（全局池）与有效频道都不算。"""
    live = await _add_channel(db_session, "T02598 在线频道")
    await _add_material(db_session, "https://t02598/ok", "有效归属", live.id)
    await _add_material(db_session, "https://t02598/null", "全局池", None)
    ghost = await _add_material(
        db_session, "https://t02598/ghost", "无主素材", _GHOST_CHANNEL_ID
    )

    ids = await MaintenanceService(db_session)._orphan_material_ids()

    assert ids == [ghost.id]


@pytest.mark.anyio
async def test_detach_preview_changes_nothing_then_apply(db_session):
    """detach：dry_run 报出条数与样例 ID 且不改数据；执行后解绑，条数与预览一致。"""
    await _add_material(db_session, "https://t02598/g1", "无主1", _GHOST_CHANNEL_ID)
    g2 = await _add_material(db_session, "https://t02598/g2", "无主2", _GHOST_CHANNEL_ID + 1)
    svc = MaintenanceService(db_session)

    preview = await svc.cleanup_database(
        target="orphan_materials_detach", days=30, dry_run=True, admin_name="tester"
    )
    assert preview["total_deleted"] == 0, "预览不能改动任何行"
    assert len(preview["cleaned"]) == 1 and "2 条" in preview["cleaned"][0]
    assert str(g2.id) in preview["cleaned"][0], "预览要给出样例 ID，便于事后核对"
    dangling = await svc._orphan_material_ids()
    assert len(dangling) == 2, "dry_run 之后仍然是 2 条无主"

    applied = await svc.cleanup_database(
        target="orphan_materials_detach", days=30, dry_run=False, admin_name="tester"
    )
    assert applied["total_deleted"] == 2
    assert await svc._orphan_material_ids() == []
    rows = (
        await db_session.execute(
            select(func.count()).select_from(Material).where(Material.channel_id.is_(None))
        )
    ).scalar()
    assert rows == 2, "解绑后的素材回到全局池，正文一条没少"


@pytest.mark.anyio
async def test_delete_target_removes_rows_and_reports_book_refs(db_session):
    """delete：连正文删除，并把书单引用数一起报出来（删完才发现引用悬空＝不诚实）。"""
    ghost = await _add_material(
        db_session, "https://t02598/book", "书的一章", _GHOST_CHANNEL_ID
    )
    live = await _add_channel(db_session, "T02598 书单频道")
    db_session.add(
        BookPoolItem(
            channel_id=live.id, material_id=ghost.id, book_key="测试书", title="测试书"
        )
    )
    await db_session.flush()
    svc = MaintenanceService(db_session)

    result = await svc.cleanup_database(
        target="orphan_materials_delete", days=30, dry_run=False, admin_name="tester"
    )

    assert result["total_deleted"] == 1
    assert "1 条讲书稿书单" in result["cleaned"][0]
    assert (
        await db_session.execute(select(Material).where(Material.id == ghost.id))
    ).scalar_one_or_none() is None, "删除口径要真的删掉素材行"
    pool = (
        await db_session.execute(select(BookPoolItem).where(BookPoolItem.id.isnot(None)))
    ).scalars().all()
    assert len(pool) == 1, "书单快照行保留（标题快照设计如此），但引用已悬空"


@pytest.mark.anyio
async def test_all_target_never_touches_orphan_materials(db_session):
    """「全部清理」是例行按时间瘦身，不得顺手解绑/删除无主素材。"""
    await _add_material(db_session, "https://t02598/keep", "无主但保留", _GHOST_CHANNEL_ID)
    svc = MaintenanceService(db_session)

    await svc.cleanup_database(
        target="all", days=3650, dry_run=False, admin_name="tester"
    )

    assert len(await svc._orphan_material_ids()) == 1


@pytest.mark.anyio
async def test_orphan_cleanup_written_to_audit_log(db_session):
    """审计：目标、动作、按不按预览都要落表，事后能查到「谁治理的」。"""
    await _add_material(db_session, "https://t02598/audit", "待解绑", _GHOST_CHANNEL_ID)

    await MaintenanceService(db_session).cleanup_database(
        target="orphan_materials_detach", days=30, dry_run=False, admin_name="audit-admin"
    )

    log = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.category == "maintenance",
                AuditLog.action == "cleanup_database",
                AuditLog.target == "orphan_materials_detach",
            )
        )
    ).scalar_one()
    assert log.operator == "audit-admin"
    detail = json.loads(log.detail)
    assert detail["dry_run"] is False
    assert any("无主素材解绑" in item for item in detail["cleaned_items"])


def test_every_channel_id_column_is_declared_or_explicitly_detached():
    """一条命令复核「删频道不会再产生无主行」：每个带 channel_id 的模型都得有说法。

    有说法＝两种之一：
    - schema 里声明了外键（ON DELETE CASCADE / SET NULL）；
    - 或者由 ChannelService.delete_channel 显式 UPDATE 解绑（material 就是这种）。
    新增列时两样都没有，这条先红——避免「material 漏了一处、生产库攒下 8 条无人发现」重演。
    """
    import inspect

    from app.database import Base
    from app.models import Channel  # noqa: F401  确保全部模型已注册到 metadata

    without_fk = {
        table.name
        for table in Base.metadata.tables.values()
        if "channel_id" in table.columns
        and table.name != "channel"
        and not table.columns["channel_id"].foreign_keys
    }
    assert without_fk == {"material"}, (
        f"无外键的 channel_id 列集合变了：{sorted(without_fk)}。"
        "新列要么声明外键，要么在 delete_channel 里显式解绑并同步本测试。"
    )
    source = inspect.getsource(ChannelService.delete_channel)
    assert "update(Material)" in source, "delete_channel 必须显式解绑素材，否则又回到无主状态"
