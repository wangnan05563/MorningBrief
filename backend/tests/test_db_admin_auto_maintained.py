"""M20（T02536 / M4）：数据管理把系统维护的时间戳列当普通可编辑文本。

修复前的事实：
- `editableColumns` 就是全部列，`created_at` / `updated_at` 在编辑弹窗里可直接改；
- 保存把后端 `isoformat()` 下来的 `2026-10-17T22:01:00` 原样回写，与库内空格分隔格式不同，
  而「保留天数」清理与排序直接对该列做字符串/时间比较——格式漂移即失效；
- 界面没有任何「这列不建议改」的提示。

修法把判定放在后端（列类型 + 列名是权威来源），下发 `auto_maintained` 供界面只读并跳过提交。
业务日期列（如 `ad_placement.start_date`）必须保持可编辑，所以判定不能只看列名后缀。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_db_admin_auto_maintained.py
"""
import pytest

from app.services.db_admin_service import (
    DbAdminService,
    _is_auto_maintained_time_column,
)


class TestAutoMaintainedPredicate:
    def test_created_at_datetime_is_auto_maintained(self):
        assert _is_auto_maintained_time_column("created_at", "DATETIME") is True
        assert _is_auto_maintained_time_column("updated_at", "TIMESTAMP") is True

    def test_business_date_column_stays_editable(self):
        # 运营手工维护的日期列不能被顺手锁掉
        assert _is_auto_maintained_time_column("start_date", "DATE") is False
        assert _is_auto_maintained_time_column("published_at", "DATETIME") is False

    def test_varchar_named_at_is_not_flagged(self):
        # 列名像时间戳但类型是文本时不自动判死，交由界面正常编辑
        assert _is_auto_maintained_time_column("created_at", "VARCHAR(32)") is False


@pytest.mark.asyncio
async def test_schema_marks_timestamp_columns(db_session):
    from app.models import AdPlacement
    from app.models.ad_material import AdMaterial
    from datetime import date

    db_session.add(AdMaterial(name="音频", description="", file_url="http://x/a.mp3", duration=10))
    db_session.add(AdPlacement(
        material_id=1, position="head", start_date=date(2026, 7, 1), end_date=date(2026, 7, 2),
    ))
    await db_session.commit()

    svc = DbAdminService(db_session)
    mat_cols = {c["name"]: c for c in (await svc.get_table_schema("ad_material"))["columns"]}
    assert mat_cols["created_at"]["auto_maintained"] is True
    # 名称/正文一类的业务列不受影响
    assert mat_cols["name"]["auto_maintained"] is False

    placement_cols = {c["name"]: c for c in (await svc.get_table_schema("ad_placement"))["columns"]}
    assert placement_cols["start_date"]["auto_maintained"] is False
