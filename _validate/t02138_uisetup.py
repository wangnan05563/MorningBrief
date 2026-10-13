"""T02138 UI 实测准备：复制真实库 → 在副本注入带 payload.channels 的日志行。

为什么注入合成行：真实库的历史行 payload 没有 channels/hub（旧格式），
展开行的逐渠道子表与 failed_capped 状态标签都无法在真实数据上验证；
而新链路要跑出这些行必须先有真实渠道凭证（会真发消息，不允许）。
只在副本库写，不碰 backend/data/news.db。
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "backend" / "data" / "news.db"
DST_DIR = HERE / "t02138_smoke"
DST = DST_DIR / "news.db"
DST_DIR.mkdir(exist_ok=True)

assert SRC.exists(), f"真实库不存在：{SRC}"
if DST.exists():
    DST.unlink()

# 用 sqlite backup API：真实库正被桌面端持有 WAL，copy2 可能拿到半写状态
src_conn = sqlite3.connect(str(SRC))
dst_conn = sqlite3.connect(str(DST))
src_conn.backup(dst_conn)
src_conn.close()

now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
rows = [
    {
        "event_type": "system.stall_alert",
        "channel": "multi",
        "title": "【MorningBrief】流水线停摆告警",
        "status": "failed",
        "error": "所有渠道发送失败",
        "payload": {
            "stalled": True,
            "stall_days": 2,
            "last_success_at": "2026-10-11 07:30:00",
            "auth_errors_24h": 0,
            "summary": "流水线已停摆 2 天：最近一次成功生成 2026-10-11 07:30，此后无成功记录。",
            "channels": [
                {"channel": "dingtalk", "success": False,
                 "error": "钉钉 webhook 仍是配置占位符：<请填写钉钉机器人地址>"},
                {"channel": "wecom", "success": False,
                 "error": "请求失败: HTTPSConnectionPool(host='qyapi.weixin.qq.com', port=443): Max retries exceeded"},
            ],
            "hub": {"total": 2, "success": 0, "failed": 2, "suppressed": 0},
        },
    },
    {
        "event_type": "system.stall_alert",
        "channel": "multi",
        "title": "【MorningBrief】停摆告警暂停重试",
        "status": "failed_capped",
        "error": "本地当日已连续 3 次发送失败（上限 3 次/日），今日不再重试——请检查通知渠道配置",
        "payload": {
            "stalled": True,
            "stall_days": 2,
            "last_success_at": "2026-10-11 07:30:00",
            "auth_errors_24h": 0,
            "summary": "流水线已停摆 2 天（聚合记录，无逐渠道明细）。",
            "channels": [],
        },
    },
    {
        "event_type": "test",
        "channel": "multi",
        "title": "🔔 通知测试",
        "status": "success",
        "error": "",
        "payload": {
            "type": "test",
            "channels": [
                {"channel": "email", "success": True, "error": None},
            ],
            "hub": {"total": 1, "success": 1, "failed": 0, "suppressed": 0},
        },
    },
    {
        # 旧格式行（payload 无 channels/hub）：验证展开行走回退文案而不是报错
        "event_type": "workflow.pending_review",
        "channel": "dingtalk",
        "title": "【MorningBrief】待审核提醒",
        "status": "success",
        "error": "",
        "payload": {"workflow_id": "wf-legacy-001", "title": "10 月 12 日早报"},
    },
]

cur = dst_conn.cursor()
created = []
for i, r in enumerate(rows):
    ts = now_utc - timedelta(minutes=5 * i)
    cur.execute(
        "INSERT INTO notification_log (event_type, channel, title, status, error, payload,"
        " workflow_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (r["event_type"], r["channel"], r["title"], r["status"], r["error"],
         json.dumps(r["payload"], ensure_ascii=False),
         "wf-legacy-001" if r["event_type"] == "workflow.pending_review" else "",
         ts.strftime("%Y-%m-%d %H:%M:%S")),
    )
    created.append(cur.lastrowid)
dst_conn.commit()

out = {
    "db": str(DST),
    "inserted_ids": created,
    "total_logs": cur.execute("SELECT COUNT(*) FROM notification_log").fetchone()[0],
    "by_status": cur.execute(
        "SELECT status, COUNT(*) FROM notification_log GROUP BY status ORDER BY status"
    ).fetchall(),
}
print(json.dumps(out, ensure_ascii=False, indent=2))
(HERE / "t02138_uisetup.txt").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
dst_conn.close()
