"""累计口径标注测试（T02508 / FR-UX-503）。

「自进程启动累计」类指标（LLM 重试计数、RSS 源连续失败次数）重启即归零，
接口必须同时回传累计起点，否则页面上的百分比没有可读的时间窗。
这里锁两件事：
1. `runtime_fields()` 给的起点/进程号本身可信（本地 naive、可解析、等于当前进程）；
2. 两个进程内指标端点确实把它们并进了响应，且 service 层没有被顺手改脏
   （口径属于"这次响应怎么解读"，是接口层职责，不该写进计数器本身）。
"""
import os
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.runtime import PROCESS_STARTED_AT, PROCESS_PID, runtime_fields
from app.core.security import create_access_token
from app.database import get_db, normalize_metadata_for_sqlite
from app.main import create_app
from app.workflow.llm.rewriter import get_word_count_retry_stats


def _admin_token() -> str:
    token, _, _ = create_access_token(
        "1", token_type="admin", extra_claims={"username": "admin", "role": "admin"}
    )
    return token


async def _override_get_db():
    """两个端点都不读库，占位覆盖依赖即可（与 test_llm_metrics_smoke 同法）。"""

    class _StubSession:
        pass

    yield _StubSession()


def _client() -> TestClient:
    normalize_metadata_for_sqlite()
    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_runtime_fields_shape():
    """起点可解析、无时区后缀、等于进程真实启动信息。"""
    fields = runtime_fields()
    assert set(fields) == {"started_at", "pid"}
    assert fields["pid"] == os.getpid() == PROCESS_PID
    assert datetime.fromisoformat(fields["started_at"]) == PROCESS_STARTED_AT.replace(microsecond=0)
    assert "+00:00" not in fields["started_at"], "项目时间口径是本地 naive，不带时区后缀"
    # 同一进程内多次调用必须返回同一个起点，否则页面每次刷新都在"重新计时"
    assert runtime_fields() == fields


def test_llm_metrics_carries_cumulative_scope():
    """/stats/llm-metrics 在计数之外必须带 started_at / pid。"""
    data = _client().get(
        "/admin/api/v1/stats/llm-metrics",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    ).json()["data"]

    assert data["started_at"] == PROCESS_STARTED_AT.isoformat(timespec="seconds")
    assert data["pid"] == PROCESS_PID


def test_rss_health_carries_cumulative_scope():
    """/stats/rss-health（不触发巡检）同样带口径字段，且原有结构不变。"""
    data = _client().get(
        "/admin/api/v1/stats/rss-health",
        headers={"Authorization": f"Bearer {_admin_token()}"},
    ).json()["data"]

    assert data["pid"] == PROCESS_PID
    assert datetime.fromisoformat(data["started_at"]) == PROCESS_STARTED_AT.replace(microsecond=0)
    # 原有字段仍在：口径是"补"上去的，不是把响应换掉
    for key in ("total", "ok", "fail", "sources"):
        assert key in data, f"响应缺原有字段 {key}"


def test_retry_stats_service_itself_stays_pure():
    """service 只负责计数；口径由接口层加，避免两处各写一份起点。"""
    keys = set(get_word_count_retry_stats())
    assert "started_at" not in keys and "pid" not in keys
