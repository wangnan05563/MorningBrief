"""导出后端全部 API 路由清单（OpenAPI 口径），供全接口压测覆盖率核对。

用法：
    backend/.venv/Scripts/python.exe scripts/jmeter_test/full_api/export_inventory.py

只导入 app 构建路由表，不启动服务、不连接数据库。
输出 inventory.json + inventory.md 到本目录。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SQLITE_DB_PATH", str(HERE / "_inventory_no_db.sqlite"))
os.environ.setdefault("SQLITE_JOURNAL_MODE", "WAL")


def classify(path: str) -> str:
    if path.startswith("/admin/api/"):
        return "B端-运营后台"
    if path.startswith("/api/v1/"):
        return "C端-用户"
    if path.startswith("/internal/"):
        return "内部-工作流"
    return "其他"


def main() -> int:
    from app.main import app  # noqa: WPS433 (deliberate late import)

    openapi = app.openapi()
    rows = []
    for path in sorted(openapi.get("paths", {})):
        item = openapi["paths"][path]
        for method, op in item.items():
            if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue
            params = [
                {
                    "name": p.get("name"),
                    "in": p.get("in"),
                    "required": p.get("required", False),
                }
                for p in op.get("parameters", [])
            ]
            body = None
            rb = op.get("requestBody")
            if rb:
                content = rb.get("content", {})
                body = sorted(content.keys())
            rows.append(
                {
                    "group": classify(path),
                    "method": method.upper(),
                    "path": path,
                    "operation_id": op.get("operationId", ""),
                    "summary": op.get("summary", ""),
                    "tags": op.get("tags", []),
                    "security": op.get("security", []),
                    "params": params,
                    "request_body": body,
                }
            )

    rows.sort(key=lambda r: (r["group"], r["path"], r["method"]))
    (HERE / "inventory.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["group"], []).append(row)
    lines = ["# API 全量清单", "", f"- 端点总数（method+path）：**{len(rows)}**", ""]
    for group, items in groups.items():
        lines.append(f"## {group}（{len(items)}）")
        lines.append("")
        lines.append("| # | 方法 | 路径 | 鉴权 | 请求体 | 平台 |")
        lines.append("|---|------|------|------|--------|------|")
        for i, r in enumerate(items, 1):
            auth = "是" if r["security"] else "-"
            body = ",".join(r["request_body"]) if r["request_body"] else "-"
            lines.append(
                f"| {i} | {r['method']} | `{r['path']}` | {auth} | {body} | {','.join(r['tags'])} |"
            )
        lines.append("")
    (HERE / "inventory.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] endpoints={len(rows)}")
    for group, items in groups.items():
        print(f"  {group}: {len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
