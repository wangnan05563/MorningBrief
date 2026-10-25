"""通知投递状态枚举化（T02702 / FR-UX-405 收尾）。

`notification_log.status` 的取值此前只写在列注释里，前端
`NotificationConfig.vue` 同一组值写了三份（筛选下拉、tag 颜色、文案 map），
门禁 `checkEnums` 只能对账模型 Enum，因此完全管不到这个域。

本单把它提升为 `NotificationDeliveryStatus(str, Enum)`：

- 值字符串保持不变，存量数据无需迁移；
- 列注释从枚举派生，新增状态只改一处，注释不会漂移；
- 前端字典改走 `NOTIFICATION_DELIVERY_STATUS`，门禁自动双向对账。
"""
from app.models.notification_log import NotificationDeliveryStatus, NotificationLog


def test_enum_values_are_stable():
    """枚举值就是前端字典与存量数据的契约，顺序也决定字典选项顺序。"""
    assert [s.value for s in NotificationDeliveryStatus] == [
        "success",
        "failed",
        "failed_capped",
        "suppressed",
    ]


def test_status_column_comment_is_derived_from_enum():
    comment = NotificationLog.__table__.c.status.comment
    assert comment == " | ".join(s.value for s in NotificationDeliveryStatus)
    for s in NotificationDeliveryStatus:
        assert s.value in comment


def test_enum_values_fit_the_column():
    """列宽是 16：新增状态若超长会在写入时被截断/报错，这里提前拦住。"""
    length = NotificationLog.__table__.c.status.type.length
    for s in NotificationDeliveryStatus:
        assert len(s.value) <= length
