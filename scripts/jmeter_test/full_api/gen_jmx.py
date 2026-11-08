"""配置驱动 JMX 生成：基线全端点、压测分组、4 小时 soak。

用例来自 runtime/cases.json（由 seed_auth.py 依据 OpenAPI 清单生成），
权重/线程档/时长来自 perf_config.json；本脚本不含业务常量。
"""
from __future__ import annotations

import json
import xml.sax.saxutils as X
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE / "runtime"
JMX_DIR = HERE / "jmx"
CONFIG = json.loads((HERE / "perf_config.json").read_text(encoding="utf-8"))
CASES = json.loads((RUNTIME / "cases.json").read_text(encoding="utf-8"))
FIX = json.loads((RUNTIME / "fixtures.json").read_text(encoding="utf-8"))

BY_LABEL = {c["label"]: c for c in CASES}
DEFAULT_PORT = CONFIG["sandbox"]["port"]
SENTINEL = CONFIG["secrets"]["admin_password_sentinel"]


def _node(tag: str, inner: str = "") -> str:
    return tag + ("<hashTree>" + inner + "</hashTree>" if inner else "<hashTree/>")


def _headers() -> str:
    return (
        '<HeaderManager guiclass="HeaderPanel" testclass="HeaderManager" testname="HTTP Headers" enabled="true">'
        '<collectionProp name="HeaderManager.headers">'
        '<elementProp name="" elementType="Header"><stringProp name="Header.name">Authorization</stringProp>'
        '<stringProp name="Header.value">Bearer ${__P(token,)}</stringProp></elementProp>'
        '<elementProp name="" elementType="Header"><stringProp name="Header.name">X-Internal-Token</stringProp>'
        '<stringProp name="Header.value">${__P(internal_token,)}</stringProp></elementProp>'
        '<elementProp name="" elementType="Header"><stringProp name="Header.name">Content-Type</stringProp>'
        '<stringProp name="Header.value">application/json</stringProp></elementProp>'
        '</collectionProp></HeaderManager>'
    )


def _sampler(case: dict, timeout_ms: int) -> str:
    label = case["label"]
    params = case.get("params") or {}
    body = case.get("body")
    parts = []
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        # 凭据不进脚本：哨兵换成 JMeter 属性，运行时由 run_suite 用 -Jadmin_password 注入
        raw = raw.replace(SENTINEL, "${__P(admin_password,)}")
        parts.append(
            '<elementProp name="" elementType="HTTPArgument">'
            '<boolProp name="HTTPArgument.always_encode">false</boolProp>'
            '<stringProp name="Argument.name"></stringProp>'
            f'<stringProp name="Argument.value">{X.escape(raw)}</stringProp>'
            '<stringProp name="Argument.metadata">=</stringProp>'
            '</elementProp>'
        )
        post_raw = "true"
    else:
        for k, v in params.items():
            parts.append(
                f'<elementProp name="{X.escape(str(k))}" elementType="HTTPArgument">'
                '<boolProp name="HTTPArgument.always_encode">true</boolProp>'
                f'<stringProp name="Argument.name">{X.escape(str(k))}</stringProp>'
                f'<stringProp name="Argument.value">{X.escape(str(v))}</stringProp>'
                '<stringProp name="Argument.metadata">=</stringProp>'
                '</elementProp>'
            )
        post_raw = "false"
    args = (
        '<elementProp name="HTTPsampler.Arguments" elementType="Arguments" '
        'guiclass="HTTPArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">'
        f'<collectionProp name="Arguments.arguments">{"".join(parts)}</collectionProp></elementProp>'
    )
    return (
        '<HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" '
        f'testname="{X.escape(label)}" enabled="true">{args}'
        '<stringProp name="HTTPSampler.domain">${__P(host,127.0.0.1)}</stringProp>'
        f'<stringProp name="HTTPSampler.port">${{__P(port,{DEFAULT_PORT})}}</stringProp>'
        '<stringProp name="HTTPSampler.protocol">http</stringProp>'
        f'<stringProp name="HTTPSampler.path">{X.escape(case["case_path"])}</stringProp>'
        f'<stringProp name="HTTPSampler.method">{case["method"]}</stringProp>'
        '<boolProp name="HTTPSampler.follow_redirects">false</boolProp>'
        '<boolProp name="HTTPSampler.auto_redirects">false</boolProp>'
        '<boolProp name="HTTPSampler.use_keepalive">true</boolProp>'
        f'<boolProp name="HTTPSampler.postBodyRaw">{post_raw}</boolProp>'
        f'<stringProp name="HTTPSampler.connect_timeout">{timeout_ms}</stringProp>'
        f'<stringProp name="HTTPSampler.response_timeout">{timeout_ms}</stringProp>'
        '</HTTPSamplerProxy>'
    )


def _thread_group(name: str, threads: int, ramp: int, duration: int | None, loops: int, samplers: list[dict], timeout_ms: int) -> str:
    if duration:
        loop_cfg = (
            '<boolProp name="LoopController.continue_forever">false</boolProp>'
            '<stringProp name="LoopController.loops">-1</stringProp>'
        )
        sched = (
            '<boolProp name="ThreadGroup.scheduler">true</boolProp>'
            f'<stringProp name="ThreadGroup.duration">{duration}</stringProp>'
        )
    else:
        loop_cfg = (
            '<boolProp name="LoopController.continue_forever">false</boolProp>'
            f'<stringProp name="LoopController.loops">{loops}</stringProp>'
        )
        sched = '<boolProp name="ThreadGroup.scheduler">false</boolProp><stringProp name="ThreadGroup.duration"></stringProp>'
    tg = (
        '<ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" '
        f'testname="{X.escape(name)}" enabled="true">'
        '<stringProp name="ThreadGroup.on_sample_error">continue</stringProp>'
        '<elementProp name="ThreadGroup.main_controller" elementType="LoopController" '
        'guiclass="LoopControlPanel" testclass="LoopController" testname="Loop Controller" enabled="true">'
        f'{loop_cfg}</elementProp>'
        f'<stringProp name="ThreadGroup.num_threads">{threads}</stringProp>'
        f'<stringProp name="ThreadGroup.ramp_time">{ramp}</stringProp>'
        f'{sched}'
        '<boolProp name="ThreadGroup.same_user_on_next_iteration">true</boolProp>'
        '</ThreadGroup>'
    )
    inner = _node(_headers()) + "".join(_node(_sampler(c, timeout_ms)) for c in samplers)
    return _node(tg, inner)


def build(name: str, threads: int, ramp: int, duration: int | None, loops: int, samplers: list[dict], timeout_ms: int) -> Path:
    tp = (
        '<TestPlan guiclass="TestPlanGui" testclass="TestPlan" '
        f'testname="{X.escape(name)}" enabled="true">'
        '<boolProp name="TestPlan.functional_mode">false</boolProp>'
        '<boolProp name="TestPlan.tearDown_on_shutdown">true</boolProp>'
        '<boolProp name="TestPlan.serialize_threadgroups">false</boolProp>'
        '<elementProp name="TestPlan.user_defined_variables" elementType="Arguments" '
        'guiclass="ArgumentsPanel" testclass="Arguments" testname="UDV" enabled="true">'
        '<collectionProp name="Arguments.arguments"/></elementProp>'
        '<stringProp name="TestPlan.user_define_classpath"></stringProp>'
        '</TestPlan>'
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6.3">\n<hashTree>\n'
        + _node(tp, _thread_group(name, threads, ramp, duration, loops, samplers, timeout_ms))
        + '\n</hashTree>\n</jmeterTestPlan>\n'
    )
    JMX_DIR.mkdir(parents=True, exist_ok=True)
    path = JMX_DIR / f"{name}.jmx"
    path.write_text(xml, encoding="utf-8")
    return path


def cases_for(labels: list[str]) -> list[dict]:
    missing = [l for l in labels if l not in BY_LABEL]
    if missing:
        raise SystemExit(f"[fail] 用例缺失：{missing}")
    return [BY_LABEL[l] for l in labels]


def weighted(weights: dict[str, int]) -> list[dict]:
    out = []
    for label, count in weights.items():
        out.extend(cases_for([label]) * count)
    return out


def main() -> None:
    base = CONFIG["baseline"]
    stress = CONFIG["stress"]
    soak = CONFIG["soak"]

    baseline_c = [c for c in CASES if c["group"].startswith("C") and c["execute_baseline"]]
    baseline_b = [c for c in CASES if not c["group"].startswith("C") and c["execute_baseline"]]
    build("baseline_c", 1, 0, None, base["loops"], baseline_c, base["response_timeout_ms"])
    build("baseline_admin", 1, 0, None, base["loops"], baseline_b, base["response_timeout_ms"])

    read_weights = {
        "GET /api/v1/episodes/today": 5,
        "GET /api/v1/channels": 2,
        "GET /api/v1/episodes/history": 2,
        "GET /api/v1/episodes/{episode_id}": 2,
        "GET /api/v1/episodes/{episode_id}/script": 2,
        "GET /api/v1/episodes/search": 2,
        "GET /api/v1/favorites": 1,
        "GET /api/v1/playlogs/recent": 1,
        "GET /api/v1/playlogs/progress/{episode_id}": 1,
        "GET /api/v1/subscriptions/channels": 1,
        "GET /api/v1/users/stats": 1,
    }
    write_weights = {
        "POST /api/v1/playlogs/progress": 8,
        "POST /api/v1/comments": 4,
        "POST /api/v1/favorites": 2,
        "DELETE /api/v1/favorites/{episode_id}": 2,
        "POST /api/v1/subscriptions/channels/{channel_id}": 1,
        "DELETE /api/v1/subscriptions/channels/{channel_id}": 1,
        "POST /api/v1/feedbacks": 1,
        "PUT /api/v1/users/profile": 1,
    }
    admin_weights = {
        "GET /admin/api/v1/stats/overview": 3,
        "GET /admin/api/v1/m/dashboard-summary": 3,
        "GET /admin/api/v1/workflows": 2,
        "GET /admin/api/v1/reviews": 2,
        "GET /admin/api/v1/materials": 2,
        "GET /admin/api/v1/channels": 1,
        "GET /admin/api/v1/queue/tasks": 1,
        "GET /admin/api/v1/audit-logs": 1,
        "GET /admin/api/v1/m/inbox": 1,
        "GET /admin/api/v1/feedbacks": 1,
        "GET /admin/api/v1/db-admin/tables/{table}/rows": 1,
        "GET /admin/api/v1/stats/trend": 1,
    }
    for tier in stress["read_tiers"]:
        build(f"stress_c_read_{tier}", tier, stress["ramp_sec"], stress["duration_sec"], 0,
              weighted(read_weights), base["response_timeout_ms"])
    for tier in stress["write_tiers"]:
        build(f"stress_c_write_{tier}", tier, stress["ramp_sec"], stress["duration_sec"], 0,
              weighted(write_weights), base["response_timeout_ms"])
    for tier in stress["admin_tiers"]:
        build(f"stress_admin_read_{tier}", tier, stress["ramp_sec"], stress["duration_sec"], 0,
              weighted(admin_weights), base["response_timeout_ms"])

    soak_c_weights = {
        "GET /api/v1/episodes/today": 11,
        "GET /api/v1/channels": 4,
        "GET /api/v1/episodes/history": 4,
        "GET /api/v1/episodes/{episode_id}": 4,
        "GET /api/v1/episodes/{episode_id}/script": 3,
        "GET /api/v1/episodes/search": 3,
        "GET /api/v1/favorites": 2,
        "GET /api/v1/playlogs/recent": 2,
        "GET /api/v1/playlogs/progress/{episode_id}": 2,
        "GET /api/v1/subscriptions/channels": 2,
        "GET /api/v1/users/stats": 1,
        "POST /api/v1/playlogs/progress": 1,
        "POST /api/v1/comments": 1,
        "POST /api/v1/favorites": 1,
    }
    soak_admin_weights = {
        "GET /admin/api/v1/m/dashboard-summary": 2,
        "GET /admin/api/v1/stats/overview": 2,
        "GET /admin/api/v1/workflows": 1,
        "GET /admin/api/v1/reviews": 1,
        "GET /admin/api/v1/m/inbox": 1,
        "GET /admin/api/v1/materials": 1,
    }
    build("soak_c", soak["threads"], soak["ramp_sec"], soak["duration_sec"], 0,
          weighted(soak_c_weights), base["response_timeout_ms"])
    build("soak_admin", soak["admin_threads"], soak["ramp_sec"], soak["duration_sec"], 0,
          weighted(soak_admin_weights), base["response_timeout_ms"])
    print(f"[ok] JMX 已生成：{len(list(JMX_DIR.glob('*.jmx')))} 个 → {JMX_DIR}")
    print(f"     基线 C={len(baseline_c)}  B/内部={len(baseline_b)}")
    total = sum(1 for c in CASES)
    print(f"     全量用例 {total}，含外部依赖/SSE 的 {sum(1 for c in CASES if not c['execute_baseline'])} 条由独立探针覆盖")


if __name__ == "__main__":
    main()
