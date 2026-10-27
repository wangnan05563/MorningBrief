"""审计 detail 的「为什么」（T03321，派生自 T02909）。

读口已经把「谁 / 对什么 / 为什么」三列摆出来了，但写侧只有 5 个点在收原因：
出事以后仍然只能靠人回忆动机。口径（哪些动作必须写原因、哪些是纯配置热更新可豁免）
登记在 `docs/T02909_审计读口权限裁决与类别登记.md` 第 6 节，门禁
`backend/scripts/check_audit_reason.py` 按同一份登记做 AST 断言。

约定：
- `detail` 一律经 `audit_detail(...)` 落库，保证 `reason` 键恒在（无原因时为空串）；
- 机器触发（cron / 自动审批 / 用户自助删除）没有操作者输入，用 `machine=` 写死来源，
  不把「没有为什么」伪装成「空原因」；
- 纯配置类热更新列入 `NO_REASON_REQUIRED`，豁免项与写入点必须一一对应，
  门禁会点名「登记了却没有对应写入点」的死豁免。
"""
import json

# (相对 app/ 的文件后缀, action) → 豁免理由。只收「可逆且能一键改回」的配置类动作。
NO_REASON_REQUIRED = {
    ("routers/admin/ads.py", "update_placement_enabled"): "投放启停，可逆且界面可一键切回",
    ("routers/admin/backup.py", "create"): "只读快照，不改变现有数据",
    ("routers/admin/queue.py", "update_priority"): "排队顺序调整，可再次调整",
    ("services/auto_review_service.py", "update_auto_review_config"): "配置热更新，旧值可由表单改回",
}


def audit_detail(payload=None, *, reason="", machine=""):
    """拼出审计 detail JSON：payload 原样保留，`reason` 键恒在。

    reason 为空且给了 machine 时写固定来源说明；两者都为空时写入空串——
    读口据此可以区分「这一版还没补原因」和「历史行根本没有这个键」。
    """
    detail = dict(payload or {})
    text = str(reason or "").strip()
    if not text and machine:
        text = f"系统自动触发：{machine}"
    detail["reason"] = text
    return json.dumps(detail, ensure_ascii=False, default=str)
