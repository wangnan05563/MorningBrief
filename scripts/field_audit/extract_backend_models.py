"""抽取「后端请求模型声明字段 + 路由映射 + ORM 可写列」——登记表的数据源之二。

运行：backend/.venv/Scripts/python.exe scripts/field_audit/extract_backend_models.py
输出：scripts/field_audit/out/backend_models.json

为什么走运行时导入而不是文本解析：
extra='ignore' 是 pydantic 的**默认**，文本里看不到；只有读
model_config / model_fields 才能区分「显式 forbid」「显式 allow」「默认 ignore」。
路由→模型的绑定同理，靠 FastAPI 自己的 dependant 才不会漏掉别名与嵌套 body。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from pydantic import BaseModel  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402


def normalize(path: str) -> str:
    """`/admin/api/v1/materials/{material_id}` → `materials/*`，与前端口径对齐。"""
    parts = [p for p in path.split("/") if p]
    if parts[:3] == ["admin", "api", "v1"]:
        parts = parts[3:]
    return "/" + "/".join("*" if p.startswith("{") else p for p in parts)


def _unwrap(annotation):
    """Optional[X] / Union[...] → 里面的 BaseModel 类（可能多个）。"""
    import typing

    out = []
    if annotation is None:
        return out
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    for arg in typing.get_args(annotation):
        if arg is type(None):
            continue
        if isinstance(arg, type) and issubclass(arg, BaseModel):
            out.append(arg)
        else:
            out.extend(_unwrap(arg))
    return out


def flat_fields(model: type[BaseModel], prefix: str = "", depth: int = 2) -> list[str]:
    """字段路径清单：嵌套 body 也展开（pydantic 对嵌套模型同样默认 ignore）。"""
    names: list[str] = []
    for name, info in model.model_fields.items():
        names.append(f"{prefix}{name}")
        if depth > 0:
            for sub in _unwrap(info.annotation):
                names.extend(flat_fields(sub, f"{prefix}{name}.", depth - 1))
    return sorted(set(names))


def model_info(model: type[BaseModel]) -> dict:
    cfg = model.model_config
    # model_config 是 dict（ConfigDict 就是 TypedDict），不是带属性的对象：
    # 早先按 `.extra` 取会永远拿到 None，于是「已 forbid 的模型数」被误报成 0
    extra = cfg.get("extra") if isinstance(cfg, dict) else getattr(cfg, "extra", None)
    if extra is None:  # 未显式声明 → pydantic v2 默认 ignore（缺陷家族的体质）
        extra = "ignore"
    return {
        "name": model.__name__,
        "module": model.__module__,
        "source": source_of(model),
        "extra": extra,
        "fields": sorted(model.model_fields),
        "flatFields": flat_fields(model),
    }


def source_of(model: type[BaseModel]) -> str:
    import inspect

    try:
        file = inspect.getsourcefile(model)
        line = inspect.getsourcelines(model)[1]
    except (TypeError, OSError):
        return "?"
    rel = str(Path(file).relative_to(ROOT)).replace("\\", "/") if file else "?"
    return f"{rel}:{line}"


def handler_refs(endpoint) -> dict | None:
    """处理函数里出现过的名字（标识符 + 字符串常量）。

    这是第四个比对轴：模型**声明了**某字段、前端也**提交了**，但处理函数一次都没引用它
    —— 三方差集全都看不见，结果就是「PUT 返回 200 而 DB 未变」。
    用 AST 而不是文本子串：文本会把 `source` 匹配进 `source_type`，把不可见的漏报又变回可见的误报。
    """
    import ast
    import inspect

    try:
        src = inspect.getsource(endpoint)
        line = inspect.getsourcelines(endpoint)[1]
        file = inspect.getsourcefile(endpoint)
    except (TypeError, OSError):
        return None
    refs: set[str] = set()
    try:
        tree = ast.parse(_dedent(src))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs.add(node.id)
        elif isinstance(node, ast.Attribute):
            refs.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            refs.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            refs.add(node.value)
    rel = str(Path(file).relative_to(ROOT)).replace("\\", "/") if file else "?"
    return {"source": f"{rel}:{line}", "refs": sorted(refs)}


def _dedent(src: str) -> str:
    import textwrap

    return textwrap.dedent(src)


endpoints: dict[str, dict] = {}
for route in app.routes:
    methods = getattr(route, "methods", None)
    path = getattr(route, "path", None)
    if not methods or not path or "admin" not in path:
        continue
    dependant = getattr(route, "dependant", None)
    bodies = getattr(dependant, "body_params", None) or []
    model = None
    for bp in bodies:
        ann = getattr(bp, "type_", None)
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            model = ann
            break
    handler = handler_refs(getattr(route, "endpoint", None))
    for method in sorted(methods):
        if method in ("GET", "HEAD", "OPTIONS"):
            continue
        key = f"{method} /{normalize(path).lstrip('/')}"
        endpoints[key] = {
            "raw_path": path,
            "endpoint": getattr(route, "name", "?"),
            "model": model_info(model) if model else None,
            "handler": handler,
        }

orm_models = {}
for mapper in Base.registry.mappers:
    cls = mapper.class_
    cols = [c.name for c in mapper.columns]
    orm_models[cls.__name__] = {
        "table": cls.__tablename__,
        "source": source_of(cls),
        "columns": sorted(cols),
    }

result = {
    "adminPrefix": "/admin/api/v1",
    "endpoints": {k: endpoints[k] for k in sorted(endpoints)},
    "ormModels": {k: orm_models[k] for k in sorted(orm_models)},
}

out_dir = ROOT / "scripts/field_audit/out"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "backend_models.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"endpoints={len(endpoints)} ormModels={len(orm_models)}")
for k, v in sorted(endpoints.items()):
    if v["model"]:
        print(f"  {k} -> {v['model']['name']} extra={v['model']['extra']} n={len(v['model']['fields'])}")
    else:
        print(f"  {k} -> (无 body 模型)")
