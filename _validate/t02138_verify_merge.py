"""复核：T02138 回传正文是否已并入原单 T01845，且只并入一次。

⚠ /api/tasks?taskNo=xxx 在本服务端不做过滤（返回全局列表首条，实测会读到别的项目的单），
必须按 projectId 拉全量再本地匹配 taskNo。
"""
import json
import os
import re
import urllib.request

CFG = os.path.expanduser("~/.workbuddy/mcp.json")
cfg = json.load(open(CFG, encoding="utf-8"))
srv = cfg["mcpServers"]["mtask"]
base = re.match(r"(https?://[^/]+)", srv["url"]).group(1)
token = srv.get("headers", {}).get("X-Access-Token", "")
PROJECT = "b90a9bca-87f9-4d60-9544-e002ec04a26c"  # News


def get(path):
    req = urllib.request.Request(base + path, headers={"X-Access-Token": token})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def unwrap(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict):
            return inner.get("items") or inner.get("tasks") or [inner]
        if isinstance(inner, list):
            return inner
        return data.get("items") or [data]
    return []


tasks = unwrap(get(f"/api/tasks?projectId={PROJECT}&pageSize=2000"))
by_no = {t.get("task_no") or t.get("taskNo"): t for t in tasks}
print("拉取条数:", len(tasks))

marker = "## 修复（绝对路径与改动点）"
for no in ("T01845", "T02138"):
    t = by_no.get(no)
    if not t:
        print(f"[{no}] 未在项目列表中命中")
        continue
    hr = t.get("handle_result") or ""
    if no == "T01845":
        open("_validate/t02138_t01845_hr.txt", "w", encoding="utf-8").write(hr)
    print(f"[{no}] {t.get('title')[:48]}")
    print(f"       ai_state={t.get('ai_state')} status={t.get('status')} "
          f"verified={t.get('verified')} archived={t.get('archived')}")
    print(f"       handle_result 长度={len(hr)} 标记次数={hr.count(marker)} "
          f"'T02138'={hr.count('T02138')} 'build_configured_channels'={hr.count('build_configured_channels')} "
          f"'1066 passed'={hr.count('1066 passed')}")
