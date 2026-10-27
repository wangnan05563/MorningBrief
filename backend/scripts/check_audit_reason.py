"""T03321 门禁：口径内的高危审计写入点必须带 reason。

口径来源：`docs/T02909_审计读口权限裁决与类别登记.md` 第 6 节 +
`app/core/audit_reason.py` 的 `NO_REASON_REQUIRED`。

用法：
    cd backend && python scripts/check_audit_reason.py

判定：
- `AuditLog(action=<字面量>)` 且 (文件, action) 未登记豁免 → 口径内，必须带 reason；
- action 不可静态解析（包装函数把 action 当参数透传）→ 不能证明豁免，按口径内处理（fail-closed）；
- 「带 reason」= detail 里调用了 `audit_detail(...)`，或 dict 字面量直接含 `"reason"` 键；
- 登记了豁免却在代码里找不到对应写入点 → 红（防死豁免让口径悄悄放开）。
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.audit_reason import NO_REASON_REQUIRED  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _action_of(node: ast.Call):
    for kw in node.keywords:
        if kw.arg == "action":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return kw.value.value
            return None
    return None


def _detail_of(node: ast.Call):
    for kw in node.keywords:
        if kw.arg == "detail":
            return kw.value
    return None


def _dict_has_reason(node) -> bool:
    return isinstance(node, ast.Dict) and any(
        isinstance(k, ast.Constant) and k.value == "reason" for k in node.keys
    )


def _has_reason(detail) -> bool:
    if detail is None:
        return False
    if _dict_has_reason(detail):
        return True
    for sub in ast.walk(detail):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name) and func.id == "audit_detail":
                return True
            # json.dumps({"reason": ...})：历史已带原因的写法
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "dumps"
                and sub.args
                and _dict_has_reason(sub.args[0])
            ):
                return True
    return False


def collect_from_source(source: str, relpath: str):
    """返回该文件里的写入点：dict(relpath, file_key, line, action, has_reason, exempt)。"""
    file_key = relpath.split("backend/app/", 1)[-1]
    sites = []
    tree = ast.parse(source, filename=relpath)
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "AuditLog"
        ):
            continue
        action = _action_of(node)
        exempt = action is not None and (file_key, action) in NO_REASON_REQUIRED
        sites.append({
            "relpath": relpath,
            "file_key": file_key,
            "line": node.lineno,
            "action": action,
            "has_reason": _has_reason(_detail_of(node)),
            "exempt": exempt,
        })
    return sites


def scan():
    sites = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8-sig")
        relpath = "backend/app/" + path.relative_to(APP_ROOT).as_posix()
        sites.extend(collect_from_source(source, relpath))
    return sites


def report(sites):
    required = [s for s in sites if not s["exempt"]]
    missing = [s for s in required if not s["has_reason"]]
    used = {(s["file_key"], s["action"]) for s in sites if s["exempt"]}
    unused = sorted(set(NO_REASON_REQUIRED) - used)

    lines = [
        "T03321 审计 reason 门禁（口径见 docs/T02909_审计读口权限裁决与类别登记.md 第 6 节）",
        f"写入点总数: {len(sites)}",
        f"口径内应带 reason: {len(required)}",
        f"已带 reason: {len(required) - len(missing)}",
        f"豁免（配置类）: {len(sites) - len(required)}",
        f"缺 reason: {len(missing)}",
    ]
    for s in missing:
        action = s["action"] if s["action"] is not None else "<?>（action 不可静态解析）"
        lines.append(f"  [缺] {s['relpath']}:{s['line']} action={action}")
    for relpath, action in unused:
        lines.append(f"  [死豁免] {relpath} action={action} 没有对应写入点")
    return "\n".join(lines), missing, unused


def main() -> int:
    text, missing, unused = report(scan())
    print(text)
    return 1 if missing or unused else 0


if __name__ == "__main__":
    sys.exit(main())
