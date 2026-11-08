"""单发探针：覆盖批量流量排除的出站/破坏性/SSE 端点。

原则：
- 不触发真实出站调用（LLM/TTS/COS/微信/Cloudflare/升级下载）。
- 破坏性端点仅用不存在的 id 或空列表，制造 404/校验响应，证明路由已注册。
- 有 JSON 体的写端点发送残缺 JSON，FastAPI 在进入业务逻辑前即 422。
- 无体、无路径参数且会出站的端点标记 static-only，不执行。

输出 results/probes.json。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
CASES = json.loads((HERE / "runtime" / "cases.json").read_text(encoding="utf-8"))
INV = {(r["method"], r["path"]): r for r in
       json.loads((HERE / "inventory.json").read_text(encoding="utf-8"))}
TOK = json.loads((HERE / "runtime" / "tokens.json").read_text(encoding="utf-8"))
CONFIG = json.loads((HERE / "perf_config.json").read_text(encoding="utf-8"))
BASE = f"http://{CONFIG['sandbox']['host']}:{CONFIG['sandbox']['port']}"
SAFE_GETS = {"/admin/api/v1/ai/voices", "/admin/api/v1/about/upgrade/status"}


def headers(path: str) -> dict:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if path.startswith("/api/internal/"):
        h["X-Internal-Token"] = TOK.get("internal_token", "")
    elif path.startswith("/admin/"):
        h["Authorization"] = f"Bearer {TOK['admin_token']}"
    elif path.startswith("/api/v1/"):
        h["Authorization"] = f"Bearer {TOK['c_token']}"
    return h


def send(method: str, url: str, body: bytes | None, path: str, timeout: float = 5) -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers=headers(path))
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(2048)
            return {"status": "probed", "code": resp.status,
                    "ms": round((time.time() - t0) * 1000, 1),
                    "note": data[:200].decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        return {"status": "probed", "code": e.code,
                "ms": round((time.time() - t0) * 1000, 1),
                "note": e.read(200).decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001 - 连接类异常统一记录
        return {"status": "no-response", "code": 0,
                "ms": round((time.time() - t0) * 1000, 1),
                "note": type(e).__name__}


def is_json_body(method: str, path: str, case: dict) -> bool:
    if case.get("body") is not None:
        return True
    rb = (INV.get((method, path)) or {}).get("request_body") or []
    return any("application/json" in x for x in rb)


def probe_sse(path: str) -> dict:
    url = BASE + path
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers(path)), timeout=4) as r:
            first = r.read(64)
            return {"status": "sse", "code": r.status,
                    "ms": round((time.time() - t0) * 1000, 1),
                    "note": f"stream opened, first bytes={first[:32]!r}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "sse", "code": 0, "ms": round((time.time() - t0) * 1000, 1),
                "note": type(e).__name__}


def main() -> None:
    out: dict[str, dict] = {}
    for c in CASES:
        if c["coverage"] not in ("external", "destructive", "sse"):
            continue
        method, path, label = c["method"], c["path"], c["label"]
        cpath = c["case_path"]
        if c["sse"]:
            out[label] = probe_sse(cpath)
            continue
        if method == "GET":
            if path in SAFE_GETS:
                out[label] = send("GET", BASE + cpath, None, path)
            else:
                out[label] = {"status": "static-only", "code": "",
                              "note": "GET 可能触发第三方/付费出站，按代码路径覆盖"}
            continue
        if c["body"] is not None and isinstance(c["body"], list) and method == "POST":
            out[label] = send(method, BASE + cpath, json.dumps(c["body"]).encode(), path)
            continue
        if is_json_body(method, path, c):
            out[label] = send(method, BASE + cpath, b'{"__probe__":', path)
            continue
        if method == "DELETE" and "{" in path:
            out[label] = send(method, BASE + cpath, None, path)
            continue
        if method == "DELETE":
            out[label] = {"status": "static-only", "code": "",
                          "note": "集合级删除会清空夹具，不执行"}
            continue
        out[label] = {"status": "static-only", "code": "",
                      "note": "无请求体且可能触发外部动作，不执行"}
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "probes.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    from collections import Counter
    print(f"[ok] 探针 {len(out)} 条：{dict(Counter(v['status'] for v in out.values()))}")


if __name__ == "__main__":
    main()
