"""T02030 只读取证：用当前 backend/.env 的真实配置实例化渠道与 Hub（不发送任何通知）。

- 打印每个渠道 webhook/SMTP 字段的**脱敏形态**与 is_configured/configuration_error
- 用 NotifierHub._init_channels() 验证占位符 wecom 不再被加载（附 loguru 日志原文）
- 真实库只读（mode=ro）统计 system.stall_alert 的 status 分布，作为修复前基线对照
"""
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from loguru import logger  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.notifier.channels.dingtalk import DingTalkNotifier  # noqa: E402
from app.services.notifier.channels.email import EmailNotifier  # noqa: E402
from app.services.notifier.channels.wecom import WeComNotifier  # noqa: E402
from app.services.notifier.hub import NotifierHub  # noqa: E402

OUT = Path(__file__).with_name("t02030_hub_probe.txt")
lines: list[str] = []


def mask(v: str) -> str:
    if not v:
        return "<empty>"
    return v if len(v) <= 6 else v[:3] + "*" * (len(v) - 6) + v[-3:]


def main() -> None:
    settings = get_settings()

    lines.append("== 真实配置下的渠道判定（值已脱敏，只看形态） ==")
    for cls, key in (
        (WeComNotifier, "ALERT_WECOM_WEBHOOK"),
        (DingTalkNotifier, "ALERT_DINGTALK_WEBHOOK"),
    ):
        raw = getattr(settings, key, "")
        inst = cls(settings=settings)
        lines.append(
            f"{cls.__name__}: 原值长度={len(raw)} 首字符={raw[:1]!r} 脱敏={mask(raw)}\n"
            f"  is_configured={inst.is_configured()}\n"
            f"  configuration_error={inst.configuration_error()!r}"
        )
    email = EmailNotifier(settings=settings)
    lines.append(
        f"EmailNotifier: smtp_host={mask(settings.ALERT_EMAIL_SMTP_HOST)} "
        f"user={mask(settings.ALERT_EMAIL_SMTP_USER)} to={mask(settings.ALERT_EMAIL_TO)}\n"
        f"  is_configured={email.is_configured()} "
        f"configuration_error={email.configuration_error()!r}"
    )

    lines.append("")
    lines.append("== NotifierHub._init_channels() 日志与加载结果 ==")
    captured: list[str] = []
    sink_id = logger.add(
        lambda m: captured.append(m.rstrip()), level="DEBUG", enqueue=False
    )
    hub = NotifierHub()
    hub._init_channels()
    logger.remove(sink_id)
    for line in captured:
        lines.append("  " + line)
    lines.append(f"  → 已加载渠道: {[ch.name for ch in hub._channels]}")

    lines.append("")
    lines.append("== 真实库只读基线（mode=ro）：system.stall_alert status 分布 ==")
    db = BACKEND / "data" / "news.db"
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        for st, cnt in conn.execute(
            "SELECT status, COUNT(*) FROM notification_log "
            "WHERE event_type='system.stall_alert' GROUP BY status ORDER BY 2 DESC"
        ):
            lines.append(f"  {st}: {cnt}")
        total = conn.execute(
            "SELECT COUNT(*) FROM notification_log WHERE event_type='system.stall_alert'"
        ).fetchone()[0]
        lines.append(f"  合计: {total}")
    finally:
        conn.close()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
