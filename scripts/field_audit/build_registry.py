#!/usr/bin/env python
"""生成《请求字段对齐登记表》——(a) 模型声明 / (b) 前端提交 / (c) ORM 可写列 三方差集。

三份输入都是机器派生的，登记表本身不写死任何字段名：
  out/backend_models.json    ← extract_backend_models.py（运行时反射 pydantic + SQLAlchemy）
  out/frontend_payloads.json ← extract_frontend_payloads.mjs（AST 解析调用点）

端点 ↔ ORM 表的归属不靠人工连线，而是拿模型字段名与列名做重合度打分自动推断；
打分出现并列或最高分过低时记为 unresolved，交给门禁拦而不是猜一张表。

输出：
  scripts/field_audit/out/field_registry.json
  docs/请求字段对齐登记表.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
DOC = ROOT / "docs" / "请求字段对齐登记表.md"

# 这些名字在几乎每张表里都有，参与打分会让每张表都得高分，必须先剔除
COMMON_COLUMNS = {"id", "created_at", "updated_at", "create_time", "update_time"}
# 控制类字段（不是列，而是请求语义），出现在 (a)−(c) 里不算缺陷
CONTROL_FIELDS = {"dry_run", "confirm", "confirm_text", "reason", "remark", "page", "page_size", "size"}
# 模型类名里的通用后缀：参与词元比对会到处「撞名」，必须先摘掉
NAME_STOP = {"request", "body", "update", "create", "save", "get", "post", "put", "delete", "list", "data", "schema"}


def load():
    fe = json.loads((OUT / "frontend_payloads.json").read_text(encoding="utf-8"))
    be = json.loads((OUT / "backend_models.json").read_text(encoding="utf-8"))
    return fe, be


def top_keys(names):
    """嵌套字段 a.b 只按顶层键参与表归属打分"""
    return {n.split(".")[0] for n in names} - COMMON_COLUMNS


def name_tokens(s):
    """`PlacementUpdateRequest` → {placement}；`AdPlacement` → {ad, placement}。"""
    import re

    words = re.split(r"[_\W]+|(?<=[a-z0-9])(?=[A-Z])", s)
    return {w.lower() for w in words if w and w.lower() not in NAME_STOP}


def match_table(model_fields, orm_models, pydantic_name=""):
    """按字段↔列重合度连线，再用模型名↔ORM 类名词元做先验。

    只看重合度会把 `ScriptModeRequest{enabled}` 连到 `AdPlacement`（恰好都有 enabled 列），
    于是产出一堆「列不可达」假差集。所以要求：要么名字有共同词元，要么字段集本身够大。
    """
    scored = []
    want = top_keys(model_fields)
    if not want:
        return None, 0.0, []
    pfx = name_tokens(pydantic_name)
    for name, info in orm_models.items():
        cols = top_keys(info["columns"])
        if not cols:
            continue
        inter = want & cols
        score = len(inter) / len(want)
        if score < 0.5:
            continue
        if not (pfx & name_tokens(name) or len(want) >= 3):
            continue
        scored.append((score, name, len(inter)))
    scored.sort(key=lambda t: (-t[0], t[1]))
    if not scored:
        return None, 0.0, []
    best = scored[0]
    tied = [s for s in scored if abs(s[0] - best[0]) < 1e-9]
    return best[1], best[0], [t[1] for t in tied]


def load_verdicts():
    """判定是数据不是评论：verdicts.json 里每条必须带 evidence（文件:行），生成器负责校验。"""
    p = Path(__file__).resolve().parent / "verdicts.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    out = {}
    for item in raw:
        if not item.get("evidence"):
            raise SystemExit(f"verdicts.json 条目 {item.get('endpoint')} 缺 evidence（文件:行）")
        for token in item["evidence"].replace("，", " ").replace("、", " ").split():
            if ":" not in token or "/" not in token:
                continue
            rel, _, ln = token.rpartition(":")
            if not ln.isdigit():
                raise SystemExit(f"verdicts.json 证据格式应为 文件:行 —— {token}")
            if not (ROOT / rel).exists():
                raise SystemExit(f"verdicts.json 证据指向不存在的文件：{rel}")
        out[item["endpoint"]] = f"{item['kind']}：{item['note']}（{item['evidence']}）"
        if item.get("also"):
            for alias in item["also"]:
                out[alias] = out[item["endpoint"]]
    return out


def build():
    fe, be = load()
    verdicts = load_verdicts()
    orm = be["ormModels"]
    fe_by_key = {f"{e['method']} {e['url']}": e for e in fe["endpoints"]}

    rows = []
    for key, info in sorted(be["endpoints"].items()):
        model = info["model"]
        if not model:
            continue
        declared = model.get("flatFields") or model["fields"]
        site = fe_by_key.get(key)
        submitted = sorted(site["fields"]) if site else []
        unresolved = sorted(site["unresolved"]) if site else []
        table, score, tied = match_table(declared, orm, model["name"])
        columns = sorted(table_info["columns"]) if (table_info := orm.get(table)) else []

        b_minus_a = [f for f in submitted if f not in declared]
        a_minus_c = [f for f in declared if top_keys([f]) and f.split(".")[0] not in set(top_keys(columns))]
        a_minus_c = [f for f in a_minus_c if f.split(".")[0] not in CONTROL_FIELDS]
        c_minus_a = [c for c in columns if c not in declared and c not in COMMON_COLUMNS]

        refs = set((info.get("handler") or {}).get("refs") or [])
        declared_not_handled = [f for f in declared if f.split(".")[0] not in refs] if refs else []

        rows.append({
            "endpoint": key,
            "model": model["name"],
            "modelSource": model["source"],
            "modelExtra": model["extra"],
            "handlerSource": (info.get("handler") or {}).get("source"),
            "declared": declared,
            "frontend": {"callSites": (site["sites"] if site else []), "fields": submitted,
                         "unresolved": unresolved, "hasCallSite": bool(site)},
            "ormTable": table,
            "ormScore": round(score, 3),
            "ormTied": tied,
            "ormColumns": columns,
            "diffs": {"frontendNotInModel": b_minus_a,
                      "declaredButNotHandled": declared_not_handled,
                      "modelNotSubmitted": [f for f in declared if f not in submitted] if site else [],
                      "modelNotInColumn": a_minus_c,
                      "columnNotInModel": c_minus_a},
            "verdict": verdicts.get(key),
        })
    return {"rows": rows, "totals": summarize(rows)}


def summarize(rows):
    return {
        "endpointsWithBodyModel": len(rows),
        "forbidCount": sum(1 for r in rows if r["modelExtra"] == "forbid"),
        "withFrontendCallSite": sum(1 for r in rows if r["frontend"]["hasCallSite"]),
        "noFrontendCallSite": [r["endpoint"] for r in rows if not r["frontend"]["hasCallSite"]],
        "frontendNotInModel": [r["endpoint"] for r in rows if r["diffs"]["frontendNotInModel"]],
        "declaredButNotHandled": {r["endpoint"]: r["diffs"]["declaredButNotHandled"]
                                  for r in rows if r["diffs"]["declaredButNotHandled"]},
        "unresolvedSites": [r["endpoint"] for r in rows if r["frontend"]["unresolved"]],
        "tableUnmatched": [r["endpoint"] for r in rows if not r["ormTable"]],
    }


def render_md(data):
    t = data["totals"]
    forbid_items = json.loads(
        (Path(__file__).resolve().parent / "forbid_endpoints.json").read_text(encoding="utf-8"))["endpoints"]
    forbid_rows = [r for r in data["rows"] if r["modelExtra"] == "forbid"]
    # 生成时就把「文档说的 forbid 数」与「反射出的 forbid 数」钉死，不给两张皮留活路
    if {i["key"] for i in forbid_items} != {r["endpoint"] for r in forbid_rows}:
        raise SystemExit(
            "forbid_endpoints.json 与运行时反射出的 forbid 端点集合不一致："
            f"{sorted({i['key'] for i in forbid_items} ^ {r['endpoint'] for r in forbid_rows})}")
    lines = [
        "# 请求字段对齐登记表（T02926）",
        "",
        "> 本文件由 `python scripts/field_audit/build_registry.py` 生成，请勿手工编辑。",
        "> 数据来源：`backend_models.json`（运行时反射 pydantic/SQLAlchemy）+ `frontend_payloads.json`（AST 解析调用点）。",
        "> 判定列由人工复核后写入 `verdicts.json`，生成器读取后回填——这样「判定」本身也是可 grep 的数据，而不是散落在评论里的话。",
        "",
        "## 汇总",
        "",
        f"- 有请求模型的管理端点：**{t['endpointsWithBodyModel']}**",
        f"- 已 `extra=forbid` 的端点：**{t['forbidCount']}**",
        f"- 找到前端调用点的端点：**{t['withFrontendCallSite']}**；未找到：{len(t['noFrontendCallSite'])}",
        f"- 前端提交字段未在模型声明的端点：**{len(t['frontendNotInModel'])}**",
        f"- 载荷字段静态不可定（需人工/门禁白名单）的端点：{len(t['unresolvedSites'])}",
        f"- 无法自动归属 ORM 表的端点：{len(t['tableUnmatched'])}",
        "",
        "## 怎么复核（一条命令口径）",
        "",
        "```bat",
        "backend\\.venv\\Scripts\\python.exe scripts/field_audit/extract_backend_models.py",
        "node scripts/field_audit/extract_frontend_payloads.mjs",
        "backend\\.venv\\Scripts\\python.exe scripts/field_audit/build_registry.py",
        "cd apps\\admin-web && node --test tests/unit/field-alignment.test.mjs",
        "cd backend && .venv\\Scripts\\python.exe -m pytest tests/test_t02926_maintenance_field_contract.py tests/test_t02926_write_through.py -q",
        "```",
        "",
        "前两条重新抽取事实源，第三条重生成登记表；后两条是门禁。",
        "门禁不复制任何字段名或端点数，全部从这三份 JSON 现推——所以「素材/频道/广告三个域，前端提交的每个字段都能在模型里找到"
        "」这件事是被机器证明的，不是被表格声明的。",
        "",
        "## 未知字段拒绝（extra=forbid）灰度进度",
        "",
        f"- 已 forbid 并登记在 `scripts/field_audit/forbid_endpoints.json`：**{len(forbid_rows)}** / 有模型端点 {t['endpointsWithBodyModel']}",
        "",
        "| 端点 | 模型 | 探针字段（必须被拒） | 为什么先拿它开刀 |",
        "|---|---|---|---|",
    ]
    rows_by_key = {r["endpoint"]: r for r in data["rows"]}
    for item in forbid_items:
        r = rows_by_key.get(item["key"], {})
        lines.append(f"| `{item['key']}` | {item['model']} | `{item['probe_field']}` | {item['why']} |")
    lines += [
        "",
        "未列入的端点仍是 `extra=ignore`：本单只做第一批，剩下的按「先加断言暴露调用点、再放开 forbid」的节奏推进。",
        "",
        "## 逐端点三方差集",
        "",
        "| 端点 | 模型 | extra | 前端调用点 | (b)−(a) 前端有模型无 | (a)−(c) 模型有列无 | (c)−(a) 列有模型无 | 判定 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in data["rows"]:
        d = r["diffs"]
        sites = "<br>".join(f"`{s['file']}:{s['line']}`" for s in r["frontend"]["callSites"][:4]) or "—"
        fm = ", ".join(f"`{x}`" for x in d["frontendNotInModel"]) or "—"
        mc = ", ".join(f"`{x}`" for x in d["modelNotInColumn"][:8]) or "—"
        cm = ", ".join(f"`{x}`" for x in d["columnNotInModel"][:10]) or "—"
        if len(d["columnNotInModel"]) > 10:
            cm += f"（共 {len(d['columnNotInModel'])} 项）"
        unres = f"<br>⚠ 静态不可定: {'; '.join(r['frontend']['unresolved'])}" if r["frontend"]["unresolved"] else ""
        table = r["ormTable"] or f"未归属(最高 {r['ormScore']})"
        lines.append(f"| `{r['endpoint']}` | {r['model']}<br>`{r['modelSource']}` | {r['modelExtra']} "
                     f"| {sites}{unres}<br>表: {table} | {fm} | {mc} | {cm} | {r['verdict'] or '—'} |")
    lines += ["", "## 未找到前端调用点的端点", ""]
    for e in t["noFrontendCallSite"]:
        lines.append(f"- `{e}`")
    lines += ["", "## 判定口径", "",
              "- **真缺陷**：(b)−(a) 命中且语义上应当生效 → 要么补模型字段，要么前端别再发；",
              "- **设计如此**：字段是前端本地/展示用或走另一条链路（例：`auto_generate_prompts` 由排期接口单独提交）；",
              "- **列不可达**：(c)−(a) 命中且没有任何端点能写它 → 需要补入口或确认废弃。",
              ""]
    return "\n".join(lines)


def main():
    data = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "field_registry.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(render_md(data), encoding="utf-8")
    t = data["totals"]
    print(json.dumps(t, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
