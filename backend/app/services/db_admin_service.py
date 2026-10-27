"""数据库维护服务（对标 17_xianyu api_db_admin）。

功能：
- 表浏览（16 张表白名单 + 行数统计）
- 动态表结构反射（SQLAlchemy Inspector，免维护硬编码）
- 行级查询（分页 + 文本列 LIKE 搜索 + 列排序）
- 行 CRUD（新增/更新/删除/批量删除）
- 级联影响预览 + 应用层级联删除
- CSV/JSON 流式导出
- CSV/JSON 导入
- 审计日志写入与查询

安全措施：
- 表白名单：禁止访问 sqlite_master 等系统表
- 标识符正则校验：防 ORDER BY / 列名注入
- 参数化绑定：所有 WHERE 条件用 :param 绑定
- 敏感字段脱敏：password_hash / API key 类字段
- 危险操作确认：删除/批量删除/导入须手输确认文本，服务端配置只作总开关
"""
import csv
import io
import json
import logging
import re
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit_reason import audit_detail
from app.core.exceptions import BizError, NotFoundError, ParamError
from app.core.logging_setup import log_key_failure, redact_credentials, unwrap_echo_exception
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
settings = get_settings()

# ---- 表白名单（16 张表，按业务域分组） ----
# 命名规范：与 ORM __tablename__ 完全一致
ALLOWED_TABLES: dict[str, str] = {
    "user": "C 端用户",
    "admin_user": "B 端运营",
    "script": "稿件",
    "material": "爬取素材",
    "ad_material": "广告素材",
    "ad_placement": "广告投放规则",
    "workflow": "工作流",
    "workflow_step": "工作流步骤",
    "review": "审核",
    "episode": "节目",
    "play_log": "播放日志",
    "jwt_blacklist": "JWT 黑名单",
    "crawler_dedup": "爬虫去重",
    "play_progress": "播放进度",
    "ai_config": "AI 配置",
    "ai_usage_log": "AI 用量日志",
}

# ---- 表关系映射（级联删除预览用） ----
# key: 被删主表, value: [{table: 关联表, fk: 外键列, action: cascade|set_null, label: 描述}]
# 仅声明业务上有意义的关联，未声明的视为无级联
TABLE_RELATIONS: dict[str, list[dict]] = {
    "ad_material": [
        {"table": "ad_placement", "fk": "material_id", "action": "cascade", "label": "投放规则将一并删除"},
    ],
    "workflow": [
        {"table": "workflow_step", "fk": "workflow_id", "action": "cascade", "label": "工作流步骤将一并删除"},
    ],
    "script": [
        {"table": "review", "fk": "script_id", "action": "cascade", "label": "审核记录将一并删除"},
        {"table": "episode", "fk": "script_id", "action": "set_null", "label": "节目 script_id 置空"},
    ],
    "review": [
        {"table": "episode", "fk": "review_id", "action": "set_null", "label": "节目 review_id 置空"},
    ],
    "user": [
        {"table": "play_log", "fk": "user_id", "action": "cascade", "label": "播放日志将一并删除"},
    ],
    "episode": [
        {"table": "play_log", "fk": "episode_id", "action": "cascade", "label": "播放日志将一并删除"},
    ],
}

# 未声明的下游数据：预览与删除都不会处理，必须显式告知运维（T02490 / FR-UX-202 M33）。
# 口径：这里只写「确实存在引用但本服务不处理」的表，不做全链删除（那是系统清理页的语义）。
UNDECLARED_DOWNSTREAM: dict[str, str] = {
    "workflow": (
        "本预览只覆盖已声明的关联表（workflow_step）。"
        "script / review / episode / play_log 等下游数据不会随之删除，可能留下悬空引用；"
        "需要按全链路清理请到「系统清理」页选择「指定工作流全链清理」。"
    ),
}

# ---- 敏感字段脱敏配置 ----
# 1. 精确列名脱敏：列名完全匹配时脱敏
SENSITIVE_COLUMNS: set[str] = {"password_hash", "token", "secret"}
# 2. 模糊匹配脱敏：ai_config 表的 config_key 含这些子串时，config_value 脱敏
# NFR-UX-01（T02519）补 webhook：钉钉/企微机器人地址形如
# `https://oapi.dingtalk.com/robot/send?access_token=<凭据>`，URL 本身就带凭据，
# 通知配置又与 AI 服务配置同存 `ai_config` 表 ⇒ 数据库维护页浏览 ai_config 时
# 会把机器人密钥原样列出（而它不在 key/secret/password/token 任一子串里）。
SENSITIVE_KEY_PATTERNS: list[str] = ["key", "secret", "password", "token", "webhook"]

# 标识符正则：仅允许字母/数字/下划线，防 SQL 注入
_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$", re.ASCII)


def _validate_table(table: str) -> str:
    """校验表名在白名单内，返回小写表名。"""
    if table not in ALLOWED_TABLES:
        raise NotFoundError(f"表 {table} 不存在或不在白名单内")
    return table


def _validate_identifier(name: str) -> str:
    """校验列名/排序字段为合法标识符，防 ORDER BY 注入。"""
    if not name or not _IDENT_RE.match(name):
        raise ParamError(f"非法标识符: {name}")
    return name


# M20：由数据库自动维护的时间戳列。业务日期列（如 ad_placement.start_date）不在其中，
# 仍归运营手工填写——只锁「行创建/更新时间」这一族固定列名，避免误伤可编辑字段。
_AUTO_MAINTAINED_TIME_COLUMNS = {"created_at", "updated_at", "create_time", "update_time"}


def _is_auto_maintained_time_column(column: str, col_type: str) -> bool:
    """M20：识别由数据库自动维护的时间戳列（界面应只读、提交时剔除）。

    只认「行创建/更新时间」这一族固定列名，且必须是日期时间类型——
    业务日期列（如 ad_placement.start_date）仍归运营手工维护，不能顺手锁掉。
    """
    if column not in _AUTO_MAINTAINED_TIME_COLUMNS:
        return False
    t = (col_type or "").upper()
    return "DATE" in t or "TIMESTAMP" in t


def _is_sensitive_column(table: str, column: str) -> bool:
    """判断某列是否为敏感字段（需脱敏）。"""
    if column in SENSITIVE_COLUMNS:
        return True
    # ai_config 表特殊处理：config_key 含 key/secret/password/token 时，config_value 脱敏
    if table == "ai_config" and column == "config_value":
        return True  # 实际是否脱敏取决于该行 config_key，在序列化时动态判断
    return False


def _serialize_value(val: Any) -> Any:
    """将数据库值序列化为 JSON 可传输格式。"""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def _mask_sensitive(table: str, row: dict) -> dict:
    """脱敏行数据中的敏感字段（与写回守卫、审计脱敏共用 `_row_sensitive_columns` 口径）。"""
    for col in _row_sensitive_columns(table, row):
        row[col] = "***"
    return row


_MASK_SENTINEL_RE = re.compile(r"^\*{2,}$")


def _is_mask_sentinel(val: Any) -> bool:
    """识别列表接口下发的脱敏占位值（形如 `***`）。"""
    return isinstance(val, str) and bool(_MASK_SENTINEL_RE.match(val.strip()))


def _row_sensitive_columns(table: str, row: dict) -> set[str]:
    """按整行数据判断该行哪些列敏感（ai_config.config_value 是否敏感取决于 config_key）。"""
    sensitive = {col for col in row if col in SENSITIVE_COLUMNS}
    if table == "ai_config" and "config_value" in row:
        key_val = str(row.get("config_key", "")).lower()
        if any(p in key_val for p in SENSITIVE_KEY_PATTERNS) or _value_is_credential_blob(
            row.get("config_value")
        ):
            sensitive.add("config_value")
    return sensitive


def _blob_has_credential_key(node: Any, depth: int = 0) -> bool:
    """递归看 JSON 结构里是否存在"键名带凭据语义且值非空"的叶子。"""
    if depth > 6:
        return False
    if isinstance(node, dict):
        for key, value in node.items():
            name = str(key).lower()
            if _SECRET_KEY_RE.search(name) or any(p in name for p in SENSITIVE_KEY_PATTERNS):
                if value not in (None, "", "***"):
                    return True
            elif _blob_has_credential_key(value, depth + 1):
                return True
        return False
    if isinstance(node, list):
        return any(_blob_has_credential_key(item, depth + 1) for item in node[:50])
    return False


def _value_is_credential_blob(val: Any) -> bool:
    """config_value 自身是"配置包"JSON 且内含凭据字段时，整行按敏感处理。

    NFR-UX-01（T02519）：`llm_preset_configs` 这类行的 config_key 不含
    key/secret/token 子串 ⇒ 原行级判定认为它不敏感，但值里逐个预设存着明文 API Key，
    数据库维护页浏览/导出即把全部预设凭据一次列出。
    """
    if not isinstance(val, str):
        return False
    text = val.strip()
    if not text.startswith(("{", "[")) or len(text) > 200_000:
        return False
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return False
    return _blob_has_credential_key(parsed)


def _mask_writeback_message(cols: list[str]) -> str:
    return (
        f"敏感字段 {', '.join(cols)} 传入的是脱敏占位值，保存会用 *** 覆盖真实凭据；"
        "请留空保持原值，或通过对应的专用配置入口修改"
    )


def _mask_field_message(col: str) -> str:
    """单个字段的说明：前端直接把它挂到对应输入框上，不需要切整句中文。"""
    return (
        f"字段 {col} 传入的是脱敏占位值，保存会用 *** 覆盖真实凭据；"
        "请留空保持原值，或通过对应的专用配置入口修改"
    )


def _mask_writeback_error(cols: list[str]) -> BizError:
    """INT-UX-01：拒绝哨兵回写时同时给出字段级明细。

    只有聚合中文时，运营端知道「这次保存会覆盖凭据」却不知道该清空哪个输入框——
    而最常见的触发路径正是「把列表页看到的 *** 原样提交回来」，
    于是提示变成一句无法据此行动的警告。明细走信封的 data 位。
    """
    return BizError(
        code=400,
        message=_mask_writeback_message(cols),
        data={"errors": [{"field": col, "message": _mask_field_message(col)} for col in cols]},
    )


_SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api_?key|access_?key|private_?key)", re.IGNORECASE
)


def _mask_audit_detail(detail: Any, table: Optional[str] = None) -> Any:
    """审计详情脱敏：按列名语义 + 白名单表的行级敏感判定，避免把新密钥明文写进 audit_log。"""
    if isinstance(detail, dict):
        row_ctx = table if table in ALLOWED_TABLES else None
        sensitive = _row_sensitive_columns(row_ctx, detail) if row_ctx else set()
        # 审计详情常只带被改的那一列（update 提交 {"values": {"config_value": ...}}），
        # 此时拿不到 config_key 语义，按 fail-safe 一律脱敏。
        if row_ctx == "ai_config" and "config_value" in detail and "config_key" not in detail:
            sensitive.add("config_value")
        masked = {}
        for key, value in detail.items():
            if isinstance(value, (dict, list)):
                masked[key] = _mask_audit_detail(value, table)
            elif _SECRET_KEY_RE.search(str(key)) or key in sensitive:
                masked[key] = value if value in (None, "") else "***"
            else:
                masked[key] = value
        return masked
    if isinstance(detail, list):
        return [_mask_audit_detail(item, table) for item in detail]
    return detail


class DbAdminService:
    """数据库维护服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- 表浏览 ----

    async def list_tables(self) -> list[dict]:
        """列出所有白名单表及行数。"""
        tables = []
        for name, label in ALLOWED_TABLES.items():
            try:
                result = await self.db.execute(text(f"SELECT COUNT(*) FROM {name}"))
                rows = result.scalar() or 0
            except Exception as e:
                # 表不存在时容错（首次启动未建表）
                logger.warning("统计表 %s 行数失败: %s", name, e)
                rows = 0
            tables.append({"name": name, "label": label, "rows": rows})
        return tables

    async def get_table_schema(self, table: str) -> dict:
        """反射表结构（SQLAlchemy Inspector）。"""
        table = _validate_table(table)

        def _reflect(sync_session):
            # run_sync 传入的是 Session 对象，inspect 需要 Connection
            conn = sync_session.connection()
            insp = inspect(conn)
            cols = insp.get_columns(table)
            pk_cols = insp.get_pk_constraint(table)
            return cols, pk_cols

        cols, pk_info = await self.db.run_sync(_reflect)
        pk_names = set(pk_info.get("constrained_columns", []))

        columns = []
        for col in cols:
            col_name = col["name"]
            columns.append({
                "name": col_name,
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "default": str(col["default"]) if col.get("default") is not None else None,
                "primary_key": col_name in pk_names,
                # 敏感列标记，前端可据此隐藏或脱敏显示
                "sensitive": _is_sensitive_column(table, col_name),
                # M20：时间戳列由 server_default / onupdate 维护。界面此前当普通文本可编辑，
                # 保存时把 isoformat() 的 `2026-10-17T22:01:00` 原样回写，与库内空格分隔格式
                # 不一致；「保留天数」清理与排序直接对该列做字符串/时间比较，格式漂移即失效。
                # 判定放在后端（权威来源：列类型 + 列名），前端据此只读并跳过提交。
                "auto_maintained": _is_auto_maintained_time_column(col_name, str(col["type"])),
            })

        if not pk_names:
            raise ParamError(f"表 {table} 无主键，不支持行级操作")

        return {"table": table, "label": ALLOWED_TABLES[table], "columns": columns}

    # ---- 行级查询 ----

    async def list_rows(
        self,
        table: str,
        limit: int = 50,
        offset: int = 0,
        order_by: Optional[str] = None,
        order_dir: str = "ASC",
        search: Optional[str] = None,
    ) -> dict:
        """分页查询表数据，支持排序和文本列 LIKE 搜索。"""
        table = _validate_table(table)

        # 参数校验：limit/offset 防越界
        limit = max(1, min(limit, settings.DB_ADMIN_MAX_PAGE_SIZE))
        offset = max(0, offset)
        if order_dir.upper() not in ("ASC", "DESC"):
            order_dir = "ASC"

        # 获取列名（用于搜索和排序校验）
        schema = await self.get_table_schema(table)
        col_names = [c["name"] for c in schema["columns"]]
        text_cols = [
            c["name"] for c in schema["columns"]
            if "TEXT" in c["type"].upper() or "VARCHAR" in c["type"].upper() or "CHAR" in c["type"].upper()
        ]

        # WHERE 条件构建：文本列 OR LIKE 搜索
        params: dict[str, Any] = {}
        where_clause = ""
        if search and text_cols:
            conditions = []
            for i, col in enumerate(text_cols):
                param_key = f"search_{i}"
                conditions.append(f"{col} LIKE :{param_key}")
                params[param_key] = f"%{search}%"
            where_clause = " WHERE " + " OR ".join(conditions)

        # ORDER BY 校验：列名必须在表结构内
        order_clause = ""
        if order_by:
            order_by = _validate_identifier(order_by)
            if order_by not in col_names:
                raise ParamError(f"排序列 {order_by} 不存在")
            order_clause = f" ORDER BY {order_by} {order_dir}"

        # 总数
        count_sql = f"SELECT COUNT(*) FROM {table}{where_clause}"
        total = (await self.db.execute(text(count_sql), params)).scalar() or 0

        # 分页查询
        query_sql = f"SELECT * FROM {table}{where_clause}{order_clause} LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        result = await self.db.execute(text(query_sql), params)
        rows = []
        for row in result.mappings():
            row_dict = {k: _serialize_value(v) for k, v in row.items()}
            rows.append(_mask_sensitive(table, row_dict))

        return {
            "table": table,
            "label": ALLOWED_TABLES[table],
            "total": total,
            "limit": limit,
            "offset": offset,
            "rows": rows,
        }

    # ---- 行 CRUD ----

    async def create_row(self, table: str, values: dict) -> dict:
        """新增一行数据。"""
        table = _validate_table(table)
        if not values:
            raise ParamError("新增数据不能为空")

        # 列名校验：必须在表结构内
        schema = await self.get_table_schema(table)
        valid_cols = {c["name"] for c in schema["columns"]}
        filtered = {k: v for k, v in values.items() if k in valid_cols and v is not None and v != ""}
        if not filtered:
            raise ParamError("无有效字段")

        blocked = sorted(
            col
            for col in filtered
            if col in _row_sensitive_columns(table, filtered) and _is_mask_sentinel(filtered[col])
        )
        if blocked:
            raise _mask_writeback_error(blocked)

        cols = ", ".join(filtered.keys())
        placeholders = ", ".join(f":{k}" for k in filtered.keys())
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"

        try:
            await self.db.execute(text(sql), filtered)
            await self.db.flush()
        except Exception as e:
            # 主键冲突/唯一约束冲突
            if "UNIQUE constraint failed" in str(e):
                raise BizError(code=409, message=f"唯一约束冲突: {e}")
            raise

        return {"ok": True, "table": table}

    async def update_row(self, table: str, pk_value: str, values: dict) -> dict:
        """更新一行数据（主键不可更新）。"""
        table = _validate_table(table)
        schema = await self.get_table_schema(table)
        pk_col = self._get_single_pk_column(schema)
        valid_cols = {c["name"] for c in schema["columns"] if not c["primary_key"]}

        # 只按「列存在且非主键」过滤。空串/None 是用户把字段清空后的真实值，不是「没填」：
        # 前端按脏字段提交，出现在 payload 里就意味着要改。这里再把它们丢掉，被清空的列会
        # 从 SET 子句里消失，接口照样返回成功，用户看到的是「改了没生效」。
        filtered = {k: v for k, v in values.items() if k in valid_cols}
        if not filtered:
            raise ParamError("无有效更新字段")

        probe = dict(filtered)
        if table == "ai_config" and "config_value" in filtered and "config_key" not in filtered:
            current = (
                await self.db.execute(
                    text(f"SELECT config_key, config_value FROM {table} WHERE {pk_col} = :pk"),
                    {"pk": self._coerce_pk(pk_value, schema)},
                )
            ).mappings().first()
            if current:
                probe["config_key"] = current["config_key"]
                # 敏感性判定用「库内旧值」补位：配置包行（如 llm_preset_configs）的
                # config_key 不含凭据子串，只有读旧值才知道它内部存着明文 API Key——
                # 列表页看到的是 ***，把它原样存回去必须同样被拦，否则真实凭据被哨兵覆盖。
                if not _value_is_credential_blob(probe.get("config_value")):
                    probe["config_value"] = current["config_value"]
        blocked = sorted(
            col
            for col in filtered
            if col in _row_sensitive_columns(table, probe) and _is_mask_sentinel(filtered[col])
        )
        if blocked:
            raise _mask_writeback_error(blocked)

        set_clause = ", ".join(f"{k} = :{k}" for k in filtered.keys())
        params = dict(filtered)
        params["pk"] = self._coerce_pk(pk_value, schema)
        sql = f"UPDATE {table} SET {set_clause} WHERE {pk_col} = :pk"

        result = await self.db.execute(text(sql), params)
        await self.db.flush()
        return {"ok": True, "affected": result.rowcount}

    async def delete_row(self, table: str, pk_value: str) -> dict:
        """删除一行（含应用层级联）。"""
        table = _validate_table(table)
        schema = await self.get_table_schema(table)
        pk_col = self._get_single_pk_column(schema)
        pk_val = self._coerce_pk(pk_value, schema)

        # 级联删除
        cascade_affected = await self._cascade_delete(table, [pk_val])

        # 删除主表记录
        sql = f"DELETE FROM {table} WHERE {pk_col} = :pk"
        result = await self.db.execute(text(sql), {"pk": pk_val})
        await self.db.flush()

        return {"ok": True, "affected": result.rowcount, "cascade": cascade_affected}

    async def batch_delete(self, table: str, ids: list) -> dict:
        """批量删除（上限 DB_ADMIN_MAX_PAGE_SIZE）。"""
        table = _validate_table(table)
        if not ids:
            raise ParamError("删除 ID 列表不能为空")
        if len(ids) > settings.DB_ADMIN_MAX_PAGE_SIZE:
            raise ParamError(f"单次最多删除 {settings.DB_ADMIN_MAX_PAGE_SIZE} 行")

        schema = await self.get_table_schema(table)
        pk_col = self._get_single_pk_column(schema)
        # ID 类型转换
        pk_values = [self._coerce_pk(str(v), schema) for v in ids]

        # 级联删除
        cascade_affected = await self._cascade_delete(table, pk_values)

        # 批量删除主表
        sql = f"DELETE FROM {table} WHERE {pk_col} IN :pks"
        result = await self.db.execute(
            text(sql).bindparams(bindparam("pks", expanding=True)),
            {"pks": pk_values},
        )
        await self.db.flush()

        return {
            "ok": True,
            "requested": len(ids),
            "affected": result.rowcount,
            "cascade": cascade_affected,
        }

    # ---- 级联预览 ----

    async def cascade_preview(self, table: str, ids: list) -> dict:
        """预览级联删除影响范围（不执行删除）。"""
        table = _validate_table(table)
        schema = await self.get_table_schema(table)
        pk_values = [self._coerce_pk(str(v), schema) for v in ids]

        relations = []
        total_affected = 0
        for rel in TABLE_RELATIONS.get(table, []):
            rel_table = rel["table"]
            # 防御性校验：关联表也必须在白名单内
            if rel_table not in ALLOWED_TABLES:
                continue
            fk = _validate_identifier(rel["fk"])
            # 统计关联表受影响行数
            count_sql = f"SELECT COUNT(*) FROM {rel_table} WHERE {fk} IN :pks"
            count_result = await self.db.execute(
                text(count_sql).bindparams(bindparam("pks", expanding=True)),
                {"pks": pk_values},
            )
            count = count_result.scalar() or 0
            relations.append({
                "table": rel_table,
                "fk": fk,
                "action": rel["action"],
                "count": count,
                "description": rel["label"],
            })
            if rel["action"] == "cascade":
                total_affected += count

        return {
            "table": table,
            "relations": relations,
            "total_affected": total_affected,
            "undeclared_downstream": UNDECLARED_DOWNSTREAM.get(table),
        }

    # ---- 导出 ----

    async def export_rows(self, table: str, fmt: str) -> tuple[list[dict], list[str], str]:
        """导出表数据为 CSV 或 JSON。

        在 session 内一次性读取（16 张表数据量可控），返回行列表 + 列名 + 文件名，
        由路由层包装为 StreamingResponse。避免生成器跨 session 生命周期问题。
        """
        table = _validate_table(table)
        if fmt not in ("csv", "json"):
            raise ParamError("导出格式仅支持 csv 或 json")

        schema = await self.get_table_schema(table)
        col_names = [c["name"] for c in schema["columns"]]

        # 读取全部行（脱敏），SQLite 单表数据量可控
        query_sql = f"SELECT * FROM {table} LIMIT :limit"
        result = await self.db.execute(
            text(query_sql), {"limit": settings.DB_ADMIN_MAX_PAGE_SIZE * 10}
        )
        rows = []
        for row in result.mappings():
            row_dict = _mask_sensitive(table, {k: _serialize_value(v) for k, v in row.items()})
            rows.append(row_dict)

        filename = f"{table}_export.{fmt}"
        return rows, col_names, filename

    # ---- 导入 ----

    async def import_rows(
        self, table: str, rows: list[dict], mode: str = "insert"
    ) -> dict:
        """导入数据（insert 或 replace 模式）。

        上限 DB_ADMIN_MAX_IMPORT_ROWS，超过拒绝。
        """
        table = _validate_table(table)
        if not rows:
            raise ParamError("导入数据不能为空")
        if len(rows) > settings.DB_ADMIN_MAX_IMPORT_ROWS:
            raise ParamError(f"单次最多导入 {settings.DB_ADMIN_MAX_IMPORT_ROWS} 行")
        if mode not in ("insert", "replace"):
            raise ParamError("导入模式仅支持 insert 或 replace")

        schema = await self.get_table_schema(table)
        valid_cols = {c["name"] for c in schema["columns"]}
        pk_col = self._get_single_pk_column(schema)

        inserted = 0
        updated = 0
        skipped = 0
        errors = []

        for i, row in enumerate(rows):
            try:
                filtered = {k: v for k, v in row.items() if k in valid_cols}
                if not filtered:
                    skipped += 1
                    continue

                blocked = sorted(
                    col
                    for col in filtered
                    if col in _row_sensitive_columns(table, filtered)
                    and _is_mask_sentinel(filtered[col])
                )
                if blocked:
                    errors.append({
                        "row": i + 1,
                        "error": _mask_writeback_message(blocked),
                        "fields": blocked,
                    })
                    skipped += 1
                    continue

                cols = ", ".join(filtered.keys())
                placeholders = ", ".join(f":{k}" for k in filtered.keys())
                if mode == "replace":
                    # INSERT OR REPLACE 是整行删插，只带部分列会把未提交的列（含凭据）清空；
                    # 而 INSERT ... ON CONFLICT DO UPDATE 仍要按插入行校验 NOT NULL，
                    # 部分列导入同样会被拒。故冲突时走纯 UPDATE，只改显式提供的列。
                    if pk_col not in filtered:
                        errors.append({"row": i + 1, "error": f"replace 模式缺少主键列 {pk_col}"})
                        skipped += 1
                        continue
                    if await self._pk_exists(table, pk_col, filtered[pk_col]):
                        update_cols = [c for c in filtered if c != pk_col]
                        if not update_cols:
                            errors.append({"row": i + 1, "error": f"仅含主键列 {pk_col}，无可更新字段"})
                            skipped += 1
                            continue
                        set_clause = ", ".join(f"{c} = :{c}" for c in update_cols)
                        params = {c: filtered[c] for c in update_cols}
                        params["pk"] = filtered[pk_col]
                        await self.db.execute(
                            text(f"UPDATE {table} SET {set_clause} WHERE {pk_col} = :pk"), params
                        )
                        updated += 1
                    else:
                        await self.db.execute(
                            text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"), filtered
                        )
                        inserted += 1
                else:
                    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
                    await self.db.execute(text(sql), filtered)
                    inserted += 1
            except Exception as e:
                # NFR-UX-05（T02523）：这里原先只把错误塞进返回值给前端，日志文件里
                # 一行都没有 —— 「导入」是 PRD 点名的四类关键失败之一，事后翻日志
                # 完全看不到发生过什么（抽样实测：导入失败行数 0）。
                # 记的是坐标（表/模式/行号）+ 异常类型 + 底层错误消息；
                # str(SQLAlchemyError) 自带 `[SQL: ...] [parameters: ...]`，
                # unwrap + 脱敏两层都挡一遍，绑定参数（可能就是刚写入的凭据明文）不落盘。
                clean = unwrap_echo_exception(e)
                log_key_failure(
                    domain="import",
                    event="逐行写入失败",
                    exc=clean,
                    level="error",
                    with_traceback=False,
                    table=table,
                    mode=mode,
                    row=i + 1,
                )
                errors.append({"row": i + 1, "error": redact_credentials(str(clean))})
                skipped += 1

        await self.db.flush()
        if errors:
            # 汇总行：给「这次导入到底坏在哪一类」一个可检索的落点
            log_key_failure(
                domain="import",
                event="导入结束（存在失败行）",
                level="warning",
                with_traceback=False,
                table=table,
                mode=mode,
                failed=len(errors),
                total=len(rows),
            )
        return {
            "ok": True,
            "total": len(rows),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }

    async def _pk_exists(self, table: str, pk_col: str, pk_value: Any) -> bool:
        result = await self.db.execute(
            text(f"SELECT 1 FROM {table} WHERE {pk_col} = :pk"), {"pk": pk_value}
        )
        return result.first() is not None

    async def _import_constraints(self, table: str, columns: set[str]) -> dict:
        """反射唯一/CHECK/外键约束，供 dry-run 静态预判。

        T02894：预览此前只算 NOT NULL 与主键冲突，UNIQUE/CHECK/FK 要到真写才炸，
        于是「预览 0 错误」而「导入报错」——两本账对不上。
        """
        def _reflect(sync_session):
            conn = sync_session.connection()
            insp = inspect(conn)
            uniques: list[tuple[str, ...]] = []
            seen: set[tuple[str, ...]] = set()

            def _add(cols):
                key = tuple(c for c in (cols or []) if c)
                if key and key not in seen and set(key) <= columns:
                    seen.add(key)
                    uniques.append(key)

            for uc in insp.get_unique_constraints(table):
                _add(uc.get("column_names"))
            for ix in insp.get_indexes(table):
                if ix.get("unique"):
                    _add(ix.get("column_names"))
            checks = [
                c["sqltext"] for c in insp.get_check_constraints(table)
                if c.get("sqltext")
            ]
            fks = [
                {
                    "columns": fk.get("constrained_columns") or [],
                    "referred_table": fk.get("referred_table"),
                    "referred_columns": fk.get("referred_columns") or [],
                }
                for fk in insp.get_foreign_keys(table)
            ]
            return {"unique": uniques, "checks": checks, "foreign_keys": fks}

        try:
            return await self.db.run_sync(_reflect)
        except Exception:
            # 反射失败时退回旧能力（NOT NULL/主键），不能让预览整体不可用
            logger.warning("导入预览：约束反射失败，退化为仅检查 NOT NULL/主键", exc_info=True)
            return {"unique": [], "checks": [], "foreign_keys": []}

    async def _constraint_error(
        self,
        table: str,
        row: dict,
        *,
        col_types: dict[str, str],
        constraints: dict,
        pk_col: Optional[str],
        is_update: bool,
        seen_uniques: dict,
        row_no: int,
        fk_enforced: bool = True,
    ) -> Optional[str]:
        """按表约束判断这一行真写时会不会失败；返回首条可读原因。"""
        for cols in constraints["unique"]:
            if not set(cols) <= set(row):
                continue
            values = tuple(row[c] for c in cols)
            if any(v is None for v in values):
                continue  # SQLite 唯一索引对 NULL 不去重
            key = (cols, values)
            first = seen_uniques.get(key)
            if first and not (is_update and first[1] == row.get(pk_col)):
                return f"违反唯一约束 ({', '.join(cols)})：与第 {first[0]} 行重复，导入会失败"
            where = " AND ".join(f"{c} = :u{i}" for i, c in enumerate(cols))
            params = {f"u{i}": v for i, v in enumerate(values)}
            sql = f"SELECT 1 FROM {table} WHERE {where}"
            if is_update and pk_col and pk_col in row:
                sql += f" AND {pk_col} != :pk"
                params["pk"] = row[pk_col]
            if (await self.db.execute(text(sql), params)).first() is not None:
                return f"违反唯一约束 ({', '.join(cols)})：值与库内已有记录重复，导入会失败"
            seen_uniques[key] = (row_no, row.get(pk_col))

        for sqltext in constraints["checks"]:
            why = await self._check_violation(sqltext, row, col_types)
            if why:
                return why

        for fk in constraints["foreign_keys"]:
            if not fk_enforced:
                # SQLite 默认关闭外键；开关没开时真写不会失败，预览也不该报错
                break
            cols, ref_cols = fk["columns"], fk["referred_columns"]
            ref_table = fk["referred_table"]
            if len(cols) != len(ref_cols) or not cols or not ref_table:
                continue
            if not set(cols) <= set(row) or any(row[c] is None for c in cols):
                continue
            where = " AND ".join(f"{c} = :f{i}" for i, c in enumerate(ref_cols))
            params = {f"f{i}": row[c] for i, c in enumerate(cols)}
            exists = await self.db.execute(
                text(f"SELECT 1 FROM {_validate_identifier(ref_table)} WHERE {where}"), params
            )
            if exists.first() is None:
                shown = ", ".join(f"{c}={row[c]}" for c in cols)
                return f"违反外键约束：{ref_table} 中没有匹配记录（{shown}），导入会失败"
        return None

    async def _check_violation(
        self, sqltext: str, row: dict, col_types: dict[str, str]
    ) -> Optional[str]:
        """把 CHECK 表达式交给数据库求值（只读 SELECT），避免自己写 SQL 解析器。

        SQLite 的 CHECK 为 NULL 时视为通过，故用 `(expr) IS NOT 0` 区分「不满足」。
        表达式引用多列且本行缺列（会由默认值补齐）时无法静态判定，跳过。
        """
        ref_cols = [
            c for c in col_types
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(c)}(?![A-Za-z0-9_])", sqltext)
        ]
        if not ref_cols or any(c not in row for c in ref_cols):
            return None
        expr = sqltext
        params: dict[str, Any] = {}
        for i, col in enumerate(ref_cols):
            value = row[col]
            col_type = col_types[col].upper()
            if isinstance(value, str):
                try:
                    if "INT" in col_type and value.strip().lstrip("-").isdigit():
                        value = int(value)
                    elif any(t in col_type for t in ("REAL", "FLOAT", "NUMERIC", "DECIMAL")):
                        value = float(value)
                except ValueError:
                    pass
            params[f"c{i}"] = value
            expr = re.sub(
                rf'"?\b{re.escape(col)}\b"?', f":c{i}", expr
            )
        try:
            result = await self.db.execute(text(f"SELECT ({expr}) IS NOT 0 AS ok"), params)
            ok = result.scalar_one()
        except Exception:
            # 表达式超出可静态判定范围（函数/子查询等）：宁可漏报也不误报
            logger.info("导入预览：CHECK 约束无法静态求值，跳过：%s", sqltext)
            return None
        return None if ok else f"违反 CHECK 约束（{sqltext}），导入会失败"


    @staticmethod
    def parse_import_payload(content: str, fmt: str = "csv") -> list[dict]:
        """用标准 csv/json 解析导入文本，正确处理引号内逗号、CRLF、BOM。"""
        text_content = (content or "").strip()
        if not text_content:
            raise ParamError("导入内容不能为空")
        # 去掉 UTF-8 BOM（Excel 导出的 CSV 常带），否则首列名会变成 `\ufeffid`
        if text_content.startswith("\ufeff"):
            text_content = text_content[1:]
        if fmt == "json":
            try:
                parsed = json.loads(text_content)
            except json.JSONDecodeError as e:
                raise ParamError(f"JSON 解析失败: {e}")
            if not isinstance(parsed, list):
                raise ParamError("JSON 必须是数组格式")
            return [dict(item) for item in parsed if isinstance(item, dict)]
        if fmt != "csv":
            raise ParamError("导入格式仅支持 csv 或 json")
        # newline="" 让 csv 自己处理引号内的 \r\n，避免按行 split 把多行字段切成垃圾行
        reader = csv.DictReader(io.StringIO(text_content, newline=""))
        if not reader.fieldnames:
            raise ParamError("CSV 缺少表头行")
        rows = []
        for raw in reader:
            if not any((v or "").strip() for v in raw.values()):
                continue
            rows.append(
                {
                    (key or "").strip(): (
                        value.strip() if isinstance(value, str) else value
                    )
                    for key, value in raw.items()
                    if key is not None
                }
            )
        return rows

    async def preview_import(
        self, table: str, rows: list[dict], mode: str = "insert"
    ) -> dict:
        """dry-run 预览：只读地算出预计新增/更新/冲突跳过/错误行，不落库。"""
        table = _validate_table(table)
        if not rows:
            raise ParamError("导入数据不能为空")
        if len(rows) > settings.DB_ADMIN_MAX_IMPORT_ROWS:
            raise ParamError(f"单次最多导入 {settings.DB_ADMIN_MAX_IMPORT_ROWS} 行")
        if mode not in ("insert", "replace"):
            raise ParamError("导入模式仅支持 insert 或 replace")

        schema = await self.get_table_schema(table)
        valid_cols = {c["name"] for c in schema["columns"]}
        col_types = {c["name"]: c["type"] for c in schema["columns"]}
        pk_col = self._get_single_pk_column(schema)
        # 真正会卡住 INSERT 的列：NOT NULL、表上没有 DEFAULT、且不是自增主键。
        # 主键排除在外：insert 模式允许省略自增主键让 SQLite 自己填。
        required_cols = sorted(
            c["name"]
            for c in schema["columns"]
            if not c["nullable"] and c["default"] is None and not c["primary_key"]
        )
        constraints = await self._import_constraints(table, valid_cols)
        try:
            fk_enforced = bool((await self.db.execute(text("PRAGMA foreign_keys"))).scalar())
        except Exception:
            fk_enforced = True  # 非 SQLite 后端按「外键总是生效」处理
        seen_uniques: dict = {}

        to_insert = 0
        to_update = 0
        conflicts = 0
        errors = []
        notices = []

        for i, row in enumerate(rows):
            filtered = {k: v for k, v in row.items() if k in valid_cols}
            if not filtered:
                errors.append({"row": i + 1, "error": "该行没有匹配当前表的列"})
                continue

            blocked = sorted(
                col
                for col in filtered
                if col in _row_sensitive_columns(table, filtered)
                and _is_mask_sentinel(filtered[col])
            )
            if blocked:
                errors.append({
                    "row": i + 1,
                    "error": _mask_writeback_message(blocked),
                    "fields": blocked,
                })
                continue

            unknown = sorted(set(row) - valid_cols)
            if unknown:
                # INT-UX-02：这一行仍然会被写进去（只是丢掉多余的列），所以它是提示，
                # 不是错误。原先塞进 errors 里，预览说「错误 1 行」而导入实际「新增 1 行、
                # 0 错误」——两本账对不上，运营照着预览的 error_rows 决定要不要提交就被误导。
                notices.append({
                    "row": i + 1,
                    "columns": unknown,
                    "message": f"列不在表结构内，导入时将忽略: {', '.join(unknown)}",
                })

            if mode == "replace":
                if pk_col not in filtered:
                    errors.append({"row": i + 1, "error": f"replace 模式缺少主键列 {pk_col}"})
                    continue
                is_update = await self._pk_exists(table, pk_col, filtered[pk_col])
                if is_update and set(filtered) == {pk_col}:
                    # 与 import_rows 同一道闸门：只给主键的 UPDATE 无列可写，实际会被拒
                    errors.append({"row": i + 1, "error": f"仅含主键列 {pk_col}，无可更新字段"})
                    continue
            else:
                if pk_col in filtered and await self._pk_exists(table, pk_col, filtered[pk_col]):
                    conflicts += 1
                    errors.append(
                        {"row": i + 1, "error": f"主键 {filtered[pk_col]} 已存在，insert 模式将跳过"}
                    )
                    continue
                is_update = False

            if not is_update:
                # 只有真正走 INSERT 的行才要检查：走 UPDATE 时未提供的列保持原值，
                # 不会因为这次没带上而被 NOT NULL 卡住。
                missing = [c for c in required_cols if filtered.get(c) is None]
                if missing:
                    errors.append({
                        "row": i + 1,
                        "error": f"缺少必填列（NOT NULL 且无默认值），导入会失败: {', '.join(missing)}",
                        "fields": missing,
                    })
                    continue

            # T02894：唯一/CHECK/外键约束此前只在真写时才炸，预览却算作可写。
            # 这里与 import_rows 的失败面逐项对齐，避免 error_rows 少报。
            constraint_error = await self._constraint_error(
                table,
                filtered,
                col_types=col_types,
                constraints=constraints,
                pk_col=pk_col,
                is_update=is_update,
                seen_uniques=seen_uniques,
                row_no=i + 1,
                fk_enforced=fk_enforced,
            )
            if constraint_error:
                errors.append({"row": i + 1, "error": constraint_error})
                continue

            if is_update:
                to_update += 1
                conflicts += 1
            else:
                to_insert += 1

        return {
            "table": table,
            "mode": mode,
            "primary_key": pk_col,
            "total": len(rows),
            "to_insert": to_insert,
            "to_update": to_update,
            "conflicts": conflicts,
            "error_rows": len(errors),
            "errors": errors[:50],
            "notice_rows": len(notices),
            "notices": notices[:50],
            "columns": sorted(valid_cols),
        }

    # ---- 审计日志 ----

    async def write_audit(
        self,
        action: str,
        target: Optional[str] = None,
        operator: Optional[str] = None,
        detail: Optional[dict] = None,
        reason: str = "",
    ) -> None:
        """写入审计日志。失败不抛异常（审计不应阻断主流程）。"""
        try:
            log = AuditLog(
                category="db_admin",
                action=action,
                target=target,
                operator=operator,
                detail=audit_detail(_mask_audit_detail(detail, target), reason=reason) if detail else None,
            )
            self.db.add(log)
            await self.db.flush()
        except Exception as e:
            # 审计失败仅记录日志，不阻断业务操作
            logger.error("写入审计日志失败: %s", e, exc_info=True)

    async def list_audit_logs(self, limit: int = 100) -> list[dict]:
        """查询数据库维护审计日志。"""
        limit = max(1, min(limit, settings.DB_ADMIN_AUDIT_LOG_LIMIT))
        sql = (
            "SELECT id, category, action, target, operator, detail, created_at "
            "FROM audit_log WHERE category = 'db_admin' "
            "ORDER BY created_at DESC LIMIT :limit"
        )
        result = await self.db.execute(text(sql), {"limit": limit})
        logs = []
        for row in result.mappings():
            d = {k: _serialize_value(v) for k, v in row.items()}
            # detail 反序列化为 dict
            if d.get("detail"):
                try:
                    d["detail"] = json.loads(d["detail"])
                except (json.JSONDecodeError, TypeError):
                    pass
            # 读侧再脱敏一次：修复前写入的历史审计行仍是明文，
            # 只有展示层也过滤，才不会再从审计日志里读到旧密钥。
            if isinstance(d.get("detail"), (dict, list)):
                d["detail"] = _mask_audit_detail(d["detail"], d.get("target"))
            logs.append(d)
        return logs

    # ---- 辅助方法 ----

    @staticmethod
    def _get_single_pk_column(schema: dict) -> str:
        """从 schema 获取唯一主键列名（联合主键拒绝）。"""
        pk_cols = [c["name"] for c in schema["columns"] if c["primary_key"]]
        if len(pk_cols) != 1:
            raise ParamError(f"仅支持单主键表，当前主键列: {pk_cols}")
        return pk_cols[0]

    @staticmethod
    def _coerce_pk(pk_value: str, schema: dict) -> Any:
        """将前端传入的主键字符串转换为正确的类型。

        SQLite 主键多为 INTEGER，但 workflow.id 为 VARCHAR(64)。
        """
        pk_col = None
        for c in schema["columns"]:
            if c["primary_key"]:
                pk_col = c
                break
        if not pk_col:
            raise ParamError("无主键列")

        col_type = pk_col["type"].upper()
        if "INT" in col_type:
            try:
                return int(pk_value)
            except ValueError:
                raise ParamError(f"主键类型应为整数: {pk_value}")
        # 字符串主键（如 workflow.id）
        return pk_value

    async def _cascade_delete(self, table: str, pk_values: list) -> dict:
        """应用层级联删除（cascade 删除关联行，set_null 置空外键）。

        在同一事务内执行，保证原子性。
        """
        cascade_affected: dict[str, int] = {}
        for rel in TABLE_RELATIONS.get(table, []):
            rel_table = rel["table"]
            if rel_table not in ALLOWED_TABLES:
                continue
            fk = _validate_identifier(rel["fk"])
            if rel["action"] == "cascade":
                sql = f"DELETE FROM {rel_table} WHERE {fk} IN :pks"
                result = await self.db.execute(
                    text(sql).bindparams(bindparam("pks", expanding=True)),
                    {"pks": pk_values},
                )
                cascade_affected[rel_table] = result.rowcount
            elif rel["action"] == "set_null":
                sql = f"UPDATE {rel_table} SET {fk} = NULL WHERE {fk} IN :pks"
                result = await self.db.execute(
                    text(sql).bindparams(bindparam("pks", expanding=True)),
                    {"pks": pk_values},
                )
                cascade_affected[rel_table] = result.rowcount
        await self.db.flush()
        return cascade_affected
