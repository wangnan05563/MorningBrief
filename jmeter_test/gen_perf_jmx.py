# -*- coding: utf-8 -*-
"""Programmatic generator for morningbrief_perf_plan.jmx.

Builds the canonical JMeter hashTree structure recursively so XML nesting is
always balanced (every component is followed by a sibling <hashTree> holding its
children; leaf components use <hashTree/>).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "morningbrief_perf_plan.jmx")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---- property node helpers -------------------------------------------------
def sp(name, value):
    """stringProp"""
    return ("stringProp", {"name": name}, value)


def bp(name, value):
    """boolProp"""
    return ("boolProp", {"name": name}, value)


def ip(name, value):
    """intProp"""
    return ("intProp", {"name": name}, value)


def ep(name, etype, children=None):
    """elementProp"""
    return ("elementProp", {"name": name, "elementType": etype}, children or [])


def cp(name, children=None):
    """collectionProp"""
    return ("collectionProp", {"name": name}, children or [])


def dp(name, value):
    """doubleProp (name/text + value/text pair)"""
    return ("doubleProp", {}, [("name", {}, name), ("value", {}, value)])


def obj_prop(name_val, value_class, value_children):
    """objProp (direct property tag, NOT elementProp)"""
    return ("objProp", {}, [("name", {}, name_val),
                            ("value", {"class": value_class}, value_children)])


# ---- component node --------------------------------------------------------
def comp(tag, guiclass, testclass, testname, props=None, children=None):
    attrs = {"guiclass": guiclass, "testclass": testclass, "testname": testname}
    return ("COMP", tag, attrs, props or [], children or [])


# ---- emitters --------------------------------------------------------------
def emit_prop(node, depth):
    pad = "  " * depth
    tag, attrs, content = node
    attrstr = "".join(f' {k}="{esc(v)}"' for k, v in attrs.items())
    if isinstance(content, str):
        if content == "":
            return f"{pad}<{tag}{attrstr}/>"
        return f"{pad}<{tag}{attrstr}>{esc(content)}</{tag}>"
    lines = [f"{pad}<{tag}{attrstr}>"]
    for c in content:
        lines.append(emit_prop(c, depth + 1))
    lines.append(f"{pad}</{tag}>")
    return "\n".join(lines)


def emit_comp(c, depth):
    _, tag, attrs, props, children = c
    pad = "  " * depth
    attrstr = "".join(f' {k}="{esc(v)}"' for k, v in attrs.items())
    lines = [f"{pad}<{tag}{attrstr}>"]
    for p in props:
        lines.append(emit_prop(p, depth + 1))
    if not children:
        lines.append(f"{pad}</{tag}>")
        lines.append(f"{pad}<hashTree/>")
    else:
        lines.append(f"{pad}</{tag}>")
        lines.append(f"{pad}<hashTree>")
        for ch in children:
            lines.append(emit_comp(ch, depth + 1))
        lines.append(f"{pad}</hashTree>")
    return "\n".join(lines)


# ---- HTTP sampler helpers --------------------------------------------------
def get_sample(name, path):
    return comp("HTTPSamplerProxy", "HttpTestSampleGui", "HTTPSamplerProxy", name,
                props=[sp("HTTPSampler.path", path),
                       sp("HTTPSampler.method", "GET"),
                       bp("HTTPSampler.follow_redirects", "true")])


def post_sample(name, path, body):
    return comp("HTTPSamplerProxy", "HttpTestSampleGui", "HTTPSamplerProxy", name,
                props=[bp("HTTPSampler.postBodyRaw", "true"),
                       ep("HTTPsampler.Arguments", "Arguments", [
                           cp("Arguments.arguments", [
                               ep("", "HTTPArgument", [
                                   bp("HTTPArgument.always_encode", "false"),
                                   sp("Argument.value", body),
                                   sp("Argument.meta_data", "application/json")])])]),
                       sp("HTTPSampler.path", path),
                       sp("HTTPSampler.method", "POST"),
                       bp("HTTPSampler.follow_redirects", "true")])


def delete_sample(name, path):
    return comp("HTTPSamplerProxy", "HttpTestSampleGui", "HTTPSamplerProxy", name,
                props=[sp("HTTPSampler.path", path),
                       sp("HTTPSampler.method", "DELETE"),
                       bp("HTTPSampler.follow_redirects", "true")])


def post_no_body(name, path):
    return comp("HTTPSamplerProxy", "HttpTestSampleGui", "HTTPSamplerProxy", name,
                props=[sp("HTTPSampler.path", path),
                       sp("HTTPSampler.method", "POST"),
                       bp("HTTPSampler.follow_redirects", "true")])


# ---- shared save config for ResultCollectors -------------------------------
SAVE_CFG = [
    ("time", "true"), ("latency", "true"), ("timestamp", "true"),
    ("success", "true"), ("label", "true"), ("code", "true"), ("message", "true"),
    ("threadName", "true"), ("dataType", "true"), ("encoding", "false"),
    ("assertions", "true"), ("subresults", "true"), ("responseData", "false"),
    ("samplerData", "false"), ("xml", "false"), ("fieldNames", "true"),
    ("responseHeaders", "false"), ("requestHeaders", "false"),
    ("responseDataOnError", "false"),
    ("saveAssertionResultsFailureMessage", "true"),
    ("assertionsResultsToSave", "0"),
    ("bytes", "true"), ("sentBytes", "true"), ("url", "true"),
    ("threadCounts", "true"), ("idleTime", "true"), ("connectTime", "true"),
]


def result_collector(guiclass, name):
    cfg_items = [(n, {}, v) for n, v in SAVE_CFG]
    return comp("ResultCollector", guiclass, "ResultCollector", name,
                props=[bp("ResultCollector.error_logging", "false"),
                       obj_prop("saveConfig", "SampleSaveConfiguration", cfg_items),
                       sp("filename", "")])


def header_manager(name, token_var):
    headers = [
        ("Content-Type", "application/json"),
        ("Accept", "application/json"),
        ("User-Agent", "MorningBriefJMeter/1.0"),
        ("Authorization", f"Bearer ${{{token_var}}}"),
    ]
    return comp("HeaderManager", "HeaderPanel", "HeaderManager", name,
                props=[cp("HeaderManager.headers", [
                    ep("", "Header", [sp("Header.name", n), sp("Header.value", v)])
                    for n, v in headers])])


# ---- build scenario blocks -------------------------------------------------
def read_block():
    samplers = [
        get_sample("01_健康检查_GET_health_live", "${PATH_PREFIX}/api/health/live"),
        get_sample("02_频道列表_GET_channels", "${PATH_PREFIX}/api/v1/channels"),
        get_sample("03_今日节目_GET_episodes_today", "${PATH_PREFIX}/api/v1/episodes/today"),
        get_sample("04_历史列表_GET_episodes_history",
                   "${PATH_PREFIX}/api/v1/episodes/history?page=${__Random(1,50)}&size=20&channel_id=${__Random(1,30)}"),
        get_sample("05_节目详情_GET_episodes_id", "${PATH_PREFIX}/api/v1/episodes/${__Random(1,1000)}"),
        get_sample("06_节目稿件_GET_episodes_script", "${PATH_PREFIX}/api/v1/episodes/${__Random(1,1000)}/script"),
        get_sample("07_搜索_GET_episodes_search_科技",
                   "${PATH_PREFIX}/api/v1/episodes/search?keyword=%E7%A7%91%E6%8A%80&page=${__Random(1,20)}&size=10"),
        get_sample("07b_搜索_GET_episodes_search_财经",
                   "${PATH_PREFIX}/api/v1/episodes/search?keyword=%E8%B4%A2%E7%BB%8F&page=${__Random(1,20)}&size=10"),
        get_sample("07c_搜索_GET_episodes_search_体育",
                   "${PATH_PREFIX}/api/v1/episodes/search?keyword=%E4%BD%93%E8%82%B2&page=${__Random(1,20)}&size=10"),
        get_sample("08_最近播放_GET_playlogs_recent", "${PATH_PREFIX}/api/v1/playlogs/recent"),
        get_sample("09_收藏列表_GET_favorites", "${PATH_PREFIX}/api/v1/favorites?page=1&size=20"),
    ]
    return comp("IfController", "IfControllerPanel", "IfController", "读场景开关",
                props=[sp("IfController.condition",
                          '${__jexl3("${__P(scenario,read)}"=="read" || "${__P(scenario,read)}"=="baseline" || '
                          '"${__P(scenario,read)}"=="peak" || "${__P(scenario,read)}"=="soak")}'),
                       bp("IfController.evaluateAll", "false"),
                       bp("IfController.useExpression", "true")],
                children=[comp("GenericController", "LogicControllerGui",
                               "GenericController", "读混合", children=samplers)])


def write_block():
    samplers = [
        post_sample("W1_播放进度上报_POST_playlogs_progress",
                    "${PATH_PREFIX}/api/v1/playlogs/progress",
                    '{"episode_id": ${__Random(1,1000)}, "position": ${__Random(0,600)}, "duration": 600, "completed": false}'),
        post_sample("W2_发布评论_POST_comments",
                    "${PATH_PREFIX}/api/v1/comments",
                    '{"episode_id": ${__Random(1,1000)}, "content": "性能测试评论内容用于压测写入路径"}'),
        post_sample("W3_添加收藏_POST_favorites",
                    "${PATH_PREFIX}/api/v1/favorites",
                    '{"episode_id": ${__Random(1,1000)}}'),
        delete_sample("W4_取消收藏_DELETE_favorites",
                      "${PATH_PREFIX}/api/v1/favorites/${__Random(1,1000)}"),
        post_no_body("W5_订阅频道_POST_subscriptions",
                     "${PATH_PREFIX}/api/v1/subscriptions/channels/${__Random(1,30)}"),
        delete_sample("W6_取消订阅_DELETE_subscriptions",
                      "${PATH_PREFIX}/api/v1/subscriptions/channels/${__Random(1,30)}"),
        post_sample("W7_提交反馈_POST_feedbacks",
                    "${PATH_PREFIX}/api/v1/feedbacks",
                    '{"category": "bug", "content": "性能测试反馈内容用于验证写入路径的稳定性与吞吐指标采集。", "contact": "perf@test.com"}'),
    ]
    return comp("IfController", "IfControllerPanel", "IfController", "写场景开关",
                props=[sp("IfController.condition",
                          '${__jexl3("${__P(scenario,read)}"=="write" || "${__P(scenario,read)}"=="peak")}'),
                       bp("IfController.evaluateAll", "false"),
                       bp("IfController.useExpression", "true")],
                children=[comp("GenericController", "LogicControllerGui",
                               "GenericController", "写混合", children=samplers)])


def admin_block():
    json_extractor = comp("JSONPostProcessor", "JSONPostProcessorGui", "JSONPostProcessor", "提取AdminToken",
                          props=[sp("JSONPostProcessor.referenceNames", "ADMIN_TOKEN"),
                                 sp("JSONPostProcessor.jsonPathExprs", "$.data.token"),
                                 sp("JSONPostProcessor.match_numbers", "1")])
    a0 = comp("HTTPSamplerProxy", "HttpTestSampleGui", "HTTPSamplerProxy", "A0_Admin登录_POST_auth_login",
              props=[bp("HTTPSampler.postBodyRaw", "true"),
                     ep("HTTPsampler.Arguments", "Arguments", [
                         cp("Arguments.arguments", [
                             ep("", "HTTPArgument", [
                                 bp("HTTPArgument.always_encode", "false"),
                                 sp("Argument.value", '{"username": "admin", "password": "admin123"}'),
                                 sp("Argument.meta_data", "application/json")])])]),
                     sp("HTTPSampler.path", "${PATH_PREFIX}/admin/api/v1/auth/login"),
                     sp("HTTPSampler.method", "POST"),
                     bp("HTTPSampler.follow_redirects", "true")],
              children=[json_extractor])
    a_other = [
        get_sample("A1_统计概览_GET_stats_overview",
                   "${PATH_PREFIX}/admin/api/v1/stats/overview?date=${__time(yyyy-MM-dd)}"),
        get_sample("A2_统计趋势_GET_stats_trend",
                   "${PATH_PREFIX}/admin/api/v1/stats/trend?metric=play_count&range=7d"),
        get_sample("A3_频道健康_GET_stats_channel_health",
                   "${PATH_PREFIX}/admin/api/v1/stats/channel-health?range_days=7"),
        get_sample("A4_频道管理_GET_admin_channels", "${PATH_PREFIX}/admin/api/v1/channels"),
        get_sample("A5_稿件管理_GET_admin_scripts_id", "${PATH_PREFIX}/admin/api/v1/scripts/${__Random(1,84)}"),
        get_sample("A6_工作流列表_GET_admin_workflows", "${PATH_PREFIX}/admin/api/v1/workflows"),
        get_sample("A7_今日工作流_GET_admin_workflows_today", "${PATH_PREFIX}/admin/api/v1/workflows/today"),
        get_sample("A8_队列任务_GET_admin_queue_tasks", "${PATH_PREFIX}/admin/api/v1/queue/tasks"),
        get_sample("A9_数据库行_GET_db_admin_rows", "${PATH_PREFIX}/admin/api/v1/db-admin/tables/episode/rows"),
        get_sample("A10_自动审批统计_GET_auto_review_stats", "${PATH_PREFIX}/admin/api/v1/auto-review/stats"),
        get_sample("A11_素材管理_GET_admin_materials", "${PATH_PREFIX}/admin/api/v1/materials"),
        get_sample("A12_广告素材_GET_ads_materials", "${PATH_PREFIX}/admin/api/v1/ads/materials"),
    ]
    once = comp("OnceOnlyController", "OnceOnlyControllerGui", "OnceOnlyController",
                "Admin登录(每线程一次)", children=[a0])
    return comp("IfController", "IfControllerPanel", "IfController", "Admin场景开关",
                props=[sp("IfController.condition", '${__jexl3("${__P(scenario,read)}"=="admin")}'),
                       bp("IfController.evaluateAll", "false"),
                       bp("IfController.useExpression", "true")],
                children=[comp("GenericController", "LogicControllerGui",
                               "GenericController", "Admin读",
                               children=[header_manager("HTTP 头管理(Admin)", "ADMIN_TOKEN"),
                                         once] + a_other)])


def thread_group():
    return comp("ThreadGroup", "ThreadGroupGui", "ThreadGroup", "场景线程组",
                props=[
                    ep("ThreadGroup.main_controller", "LoopController", [
                        bp("LoopController.continue_forever", "true"),
                        sp("LoopController.loops", "-1")]),
                    sp("ThreadGroup.num_threads", "${__P(threads,50)}"),
                    sp("ThreadGroup.ramp_time", "${__P(ramp_up,30)}"),
                    bp("ThreadGroup.scheduler", "true"),
                    sp("ThreadGroup.duration", "${__P(duration,180)}"),
                    sp("ThreadGroup.on_sample_error", "continue"),
                ],
                children=[
                    comp("ConstantThroughputTimer", "TestBeanGUI", "ConstantThroughputTimer", "吞吐量控制器",
                         props=[ip("calcMode", "2"),
                                dp("throughput", "999999.0")]),
                    comp("ResponseAssertion", "AssertionGui", "ResponseAssertion", "HTTP 200 断言",
                         props=[cp("Asserion.test_strings", [sp("49586", "200")]),
                                sp("Assertion.test_field", "Assertion.response_code"),
                                bp("Assertion.assume_success", "false"),
                                ip("Assertion.test_type", "8")]),
                    comp("ResponseAssertion", "AssertionGui", "ResponseAssertion", "业务成功断言",
                         props=[cp("Asserion.test_strings", [sp("94887234", '"code":0')]),
                                sp("Assertion.test_field", "Assertion.response_data"),
                                bp("Assertion.assume_success", "false"),
                                ip("Assertion.test_type", "2")]),
                    read_block(),
                    write_block(),
                    admin_block(),
                    result_collector("SummaryReport", "汇总报告"),
                    result_collector("StatVisualizer", "聚合报告"),
                ])


def test_plan():
    udv = [
        ("HOST", "${__P(host,127.0.0.1)}"),
        ("PORT", "${__P(port,8000)}"),
        ("PROTOCOL", "${__P(protocol,http)}"),
        ("PATH_PREFIX", "${__P(path_prefix,)}"),
        ("AUTH_TOKEN", "${__P(auth_token,)}"),
        ("ADMIN_TOKEN", "${__P(admin_token,)}"),
        ("SCENARIO", "${__P(scenario,read)}"),
        ("EPISODE_ID", "${__P(episode_id,57)}"),
    ]
    return comp("TestPlan", "TestPlanGui", "TestPlan", "MorningBrief 全接口性能测试",
                props=[
                    bp("TestPlan.functional_mode", "false"),
                    bp("TestPlan.serialize_threadgroups", "false"),
                    ep("TestPlan.user_defined_variables", "Arguments", [
                        cp("Arguments.arguments", [
                            ep(name, "Argument", [
                                sp("Argument.name", name),
                                sp("Argument.value", val)]) for name, val in udv])]),
                ],
                children=[
                    comp("ConfigTestElement", "HttpDefaultsGui", "ConfigTestElement", "HTTP 请求默认值",
                         props=[ep("HTTPsampler.Arguments", "Arguments", [cp("Arguments.arguments")]),
                                sp("HTTPSampler.domain", "${HOST}"),
                                sp("HTTPSampler.port", "${PORT}"),
                                sp("HTTPSampler.protocol", "${PROTOCOL}"),
                                sp("HTTPSampler.path", "")]),
                    header_manager("HTTP 头管理(C端)", "AUTH_TOKEN"),
                    comp("CookieManager", "CookiePanel", "CookieManager", "Cookie 管理器",
                         props=[bp("CookieManager.clearEachIteration", "true")]),
                    thread_group(),
                ])


def main():
    tp = test_plan()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<jmeterTestPlan version="1.2" properties="5.0">',
             '  <hashTree>']
    lines.append(emit_comp(tp, 2))
    lines.append('  </hashTree>')
    lines.append('</jmeterTestPlan>')
    xml = "\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(xml)
    print("WROTE", OUT, "bytes=", len(xml))


if __name__ == "__main__":
    main()
