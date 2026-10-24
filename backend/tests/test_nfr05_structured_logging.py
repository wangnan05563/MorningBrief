"""NFR-UX-05（T02523）关键失败结构化日志 + 敏感值不落盘。

PRD 给的验收方式是「日志抽样」。历史日志是一次性的（backend/logs 里那 195MB
翻完就没了，也无法重放），所以这里把抽样做成**可执行、可回归**的：
在临时目录按生产方式起一套日志，触发四类关键失败与两条实测到的泄露路径，
再读回落盘文本做断言 —— 断言对象是文件里的字节，不是「logger 被调用了几次」。

修前的实测依据（抽样脚本 t02523_sample.py / t02523_site.py，2026-10-08~09 日志）：
- 2538 行 COS v5 签名字符串原样落盘（含 SecretId 与签名）；
- 18 行 SQLAlchemy 异常回显，`[parameters: ...]` 里就是本次写入的真实值；
- 每条标准库桥接日志的调用点都被误标成 `logging:callHandlers:1762`，
  导致上面两条「有凭据、但查不出谁打的」；
- `[shutdown]` 失败 0 行、导入失败 0 行（不是没发生，是压根没落日志）。
"""
import logging
from datetime import datetime

import pytest
from loguru import logger

import app.core.logging_setup as ls
from app.core.logging_setup import log_key_failure

# 形状与真实凭据一致，值是假的 —— 断言靠的是「它没出现在落盘文本里」
FAKE_SECRET_ID = "AKIDz8krbsJ5yKbTfaKeNEXAMPLE01"
FAKE_SIGNATURE = "deadbeef1234567890abcdef9876543210fedcba"
FAKE_LLM_KEY = "sk-FAKEONLYKEYDEADBEEF0123456789"
# 失败行自己的值：断言「绑定参数没回显」必须拿它做靶子
FAKE_ROW_VALUE = "sk-CONFLICTROWVALUEDEADBEEF4242"
COS_SIGNED = (
    f"q-sign-algorithm=sha1&q-ak={FAKE_SECRET_ID}&q-sign-time=1791435506;1791445566"
    f"&q-header-list=host&q-signature={FAKE_SIGNATURE}"
)


@pytest.fixture
def sampled(tmp_path, monkeypatch):
    """按生产方式初始化日志到 tmp_path，返回「读回落盘全文」的函数。

    setup_logging 用 _configured 做幂等，测试必须把它掰回 False 才能重新装配 sink；
    teardown 里再掰回去，避免污染后续测试。
    """
    monkeypatch.setattr(ls, "_configured", False)
    ls.setup_logging(
        log_level="INFO",
        log_dir=tmp_path,
        log_file_max_mb=10,
        retention_days=1,
        dir_max_mb=100,
    )

    def read() -> str:
        return "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(tmp_path.glob("MorningBrief_*.log"))
        )

    try:
        yield read
    finally:
        logger.remove()
        monkeypatch.setattr(ls, "_configured", True)


# ---- 1. 第三方内部日志不再落盘（实测 2538 行凭据的来源就是这里）----

def test_第三方内部日志不落盘而业务日志照写(sampled):
    logging.getLogger("sqlalchemy.engine.Engine").debug("operation %s", COS_SIGNED)
    logging.getLogger("sqlalchemy.pool").debug("pool checkin %s", FAKE_SECRET_ID)
    logging.getLogger("cos.qcloud").debug(COS_SIGNED)
    logging.getLogger("app.services.rss_source_service").warning("RSS 源连续失败 3 次 name=测试源")

    text = sampled()
    assert "q-sign-algorithm" not in text, "第三方 SDK 的内部日志仍然落盘了"
    assert FAKE_SECRET_ID not in text
    # 封顶不是把日志一律哑掉：业务模块自己的 WARNING 必须在
    assert "RSS 源连续失败 3 次 name=测试源" in text


# ---- 2. 凭据形状在落盘前被遮（兜底层，业务代码写漏也挡）----

def test_业务日志里的凭据形状落盘前被遮(sampled):
    # 这两条都是业务模块合法可见的日志级别，靠命名空间封顶挡不住，只能靠形状脱敏
    logger.warning("COS 连接测试失败: {}", COS_SIGNED)
    logger.info("AI 配置已更新 llm_api_key={}", FAKE_LLM_KEY)

    text = sampled()
    assert "COS 连接测试失败" in text, "事件本身还是要能查"
    assert FAKE_SECRET_ID not in text and FAKE_SIGNATURE not in text
    assert "AI 配置已更新" in text and FAKE_LLM_KEY not in text


def test_脱敏只遮值不遮结构():
    """脱敏后还得留得线索，否则日志等于被自己废掉。"""
    out = ls.redact_credentials(COS_SIGNED)
    assert "q-sign-algorithm=sha1" in out  # 协议头没被顺手删
    assert "q-ak=" in out and FAKE_SECRET_ID not in out
    assert ls.redact_credentials("普通一行：workflow_id=wf-1 耗时 3.2s") == \
        "普通一行：workflow_id=wf-1 耗时 3.2s"


# ---- 3. 堆栈路径的参数回显（形状脱敏管不到 traceback，只能从异常对象下手）----

def test_SQLAlchemy包装异常换成底层异常再记():
    class _EchoError(Exception):
        """模仿 SQLAlchemy 的 DBAPIError：字符串自带 SQL + 绑定参数。"""

        def __str__(self):
            return (
                "[SQL: INSERT INTO ai_config (config_key, config_value) VALUES (?, ?)]\n"
                "[parameters: ('llm_api_key', '%s')]" % FAKE_LLM_KEY
            )

    _EchoError.__module__ = "sqlalchemy.engine.base"
    orig = RuntimeError("UNIQUE constraint failed: ai_config.config_key")
    err = _EchoError()
    err.orig = orig

    assert ls.unwrap_echo_exception(err) is orig, "回显型包装异常必须换成底层 DBAPI 异常"
    assert type(ls.unwrap_echo_exception(ValueError("普通异常"))) is ValueError
    assert ls.unwrap_echo_exception(None) is None


# ---- 4. 四类关键失败：配置加载 ----

def test_配置加载失败的关键失败行可定位():
    """结构化行必须带异常类型 —— 修前那行「加载 AI 配置失败: not all arguments
    converted during string formatting」只有 str(e)，事后查不出抛点。"""
    try:
        raise TypeError("not all arguments converted during string formatting")
    except TypeError as exc:
        log_key_failure(domain="config_load", event="加载 AI 配置（已回退 .env 默认值）",
                        exc=exc, level="warning", source="sqlite")

    # main.py 的三个配置加载兜底点都得走同一个出口，不许退回 `logger.warning("...: {}", e)`
    from pathlib import Path

    src = (Path(ls.__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert src.count('domain="config_load"') >= 3
    assert "使用 .env 默认值: {}" not in src


# ---- 5. 四类关键失败：停服 ----

async def test_停服单步抛错不带走后续并留下结构化行(sampled):
    from app.main import _shutdown_step

    async def _boom():
        raise RuntimeError("APScheduler shutdown 卡住")

    assert await _shutdown_step("停止工作流调度器", _boom()) is False
    assert await _shutdown_step("无事发生的步骤", _noop()) is True

    text = sampled()
    assert "domain=shutdown event=停止工作流调度器" in text
    assert "exc_type=RuntimeError" in text
    assert "APScheduler shutdown 卡住" in text


async def _noop():
    return None


# ---- 6. 四类关键失败：导入（真实写库路径，不是打一条日志了事）----

async def test_导入逐行失败落结构化行且不带绑定参数(sampled, db_session):
    from app.services.db_admin_service import DbAdminService

    svc = DbAdminService(db_session)
    # 先占住唯一键，再插一条重复的：真实触发 UNIQUE 冲突。
    # 冲突行的值必须自己可控 —— 断言要盯的就是「这一行的值有没有被回显」，
    # 拿上一行的值做断言会假绿（第一版就是这么漏过去的）。
    await svc.import_rows("ai_config", [{"config_key": "llm_api_key",
                                        "config_value": FAKE_LLM_KEY}])
    result = await svc.import_rows(
        "ai_config", [{"config_key": "llm_api_key", "config_value": FAKE_ROW_VALUE}]
    )

    assert result["errors"], "重复主键本该报错"
    text = sampled()
    assert "domain=import event=逐行写入失败" in text, "导入失败在日志里仍然是隐形的"
    assert "table=ai_config" in text and "row=1" in text
    assert "domain=import event=导入结束（存在失败行）" in text
    # 落盘与回传两条路都不许带出 SQL 绑定参数
    payload = str(result["errors"])
    assert "[parameters:" not in text and FAKE_ROW_VALUE not in text
    assert "[parameters:" not in payload and FAKE_ROW_VALUE not in payload, \
        f"回传给前端的错误串里出现了绑定参数：{payload}"


# ---- 7. 四类关键失败：自动审批（这一域原先就合格，钉住别退步）----

async def test_自动审批护栏拦截落结构化行(sampled, db_session, monkeypatch):
    from app.services.auto_review_service import AutoReviewService

    svc = AutoReviewService(db_session)

    class _Cfg:
        enabled = True
        require_content_safe = False
        require_steps_first_success = False
        keyword_whitelist = ""

    async def _cfg():
        return _Cfg()

    async def _record(**kwargs):  # 统计表不参与本断言
        return None

    monkeypatch.setattr(svc, "get_config", _cfg)
    monkeypatch.setattr(svc, "_record_stat", _record)

    out = await svc.try_auto_approve("wf-nfr05", 7, datetime(2026, 10, 21, 12, 0, 0))

    assert out["auto_approved"] is False
    text = sampled()
    assert "自动审批被护栏拦截" in text
    assert "workflow_id=wf-nfr05" in text and "review_id=7" in text


# ---- 8. 调用点归属：查不出谁打的，等于没修上面两条 ----

def test_桥接日志的调用点与来源库名都对(sampled):
    logging.getLogger("app.services.probe_logger").warning("归属探针消息")

    text = sampled()
    line = next(ln for ln in text.splitlines() if "归属探针消息" in ln)
    assert "logging:callHandlers" not in line, "调用点仍被标成标准库内部帧"
    assert "src=app.services.probe_logger" in line, "标准库 logger 名没带进落盘行"
    # {name} 是调用方模块的 dotted name（pytest 会带 tests. 前缀，故用 in 而非 ==）
    assert "test_nfr05_structured_logging" in line


# ---- 9. T02847：启动步骤失败也必须带异常类型与堆栈 ----

async def test_启动步骤失败落结构化行且带异常类型(sampled, monkeypatch, tmp_path):
    """真实跑一次迁移函数让它失败：断言的是落盘字节里有没有 exc_type/堆栈，
    不是「log_key_failure 被调用过」。"""
    import sqlite3

    from app import main as main_mod
    import app.paths as paths_mod

    class _ExplodingConn:
        def cursor(self):
            raise RuntimeError("database is locked")

        def close(self):
            pass

    monkeypatch.setattr(paths_mod, "resolve_db_path", lambda: tmp_path / "probe.db")
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: _ExplodingConn())

    await main_mod._migrate_playlog_indexes()

    text = sampled()
    assert "domain=startup event=play_log 表索引迁移失败" in text
    assert "exc_type=RuntimeError" in text, "启动失败行仍然只有 str(e)"
    assert "database is locked" in text
    assert "Traceback (most recent call last)" in text, "启动失败行没有堆栈，查不出抛点"


def test_启动期失败站点统一走结构化出口():
    """静态门禁：任何启动失败都不许退回 `logger.warning("[startup] … 失败: {}", e)`。

    单测里只能真实触发一两个步骤，剩下三十多处靠这里兜住「改回去」。
    """
    import re
    from pathlib import Path

    src = (Path(ls.__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

    legacy = re.findall(
        r'logger\.(?:warning|error)\(\s*"\[startup\][^"]*失败: \{\}"', src
    )
    assert not legacy, f"启动失败又退回单行 str(e)：{legacy}"
    assert "_LOG_MATERIAL_MIGRATE_FAIL" not in src, "material 迁移失败的日志模板常量应随统一出口删除"
    startup_sites = src.count('domain="startup"')
    assert startup_sites >= 30, f"启动结构化站点只剩 {startup_sites} 处，疑似有站点改回明文日志"
    assert "startup" in ls.KEY_FAILURE_DOMAINS, "startup 未登记为关键失败域，按域检索会漏"
