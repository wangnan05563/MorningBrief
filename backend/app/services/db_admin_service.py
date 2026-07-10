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
- 危险操作令牌：删除/批量删除/导入须传 confirm_token
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
from app.core.exceptions import BizError, NotFoundError, ParamError
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

# ---- 敏感字段脱敏配置 ----
# 1. 精确列名脱敏：列名完全匹配时脱敏
SENSITIVE_COLUMNS: set[str] = {"password_hash", "token", "secret"}
# 2. 模糊匹配脱敏：ai_config 表的 config_key 含这些子串时，config_value 脱敏
SENSITIVE_KEY_PATTERNS: list[str] = ["key", "secret", "password", "token"]

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
    """脱敏行数据中的敏感字段。"""
    for col in row.keys():
        if _is_sensitive_column(table, col):
            # ai_config 表的 config_value 动态判断
            if table == "ai_config" and col == "config_value":
                key_val = str(row.get("config_key", "")).lower()
                if any(p in key_val for p in SENSITIVE_KEY_PATTERNS):
                    row[col] = "***"
            else:
                row[col] = "***"
    return row


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

        # 过滤：仅保留有效且非主键且非空的字段
        filtered = {k: v for k, v in values.items() if k in valid_cols}
        # 空字符串视为不更新（避免误清空），但显式 None 表示置空
        filtered = {k: v for k, v in filtered.items() if v is not None and v != ""}
        if not filtered:
            raise ParamError("无有效更新字段")

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

        return {"table": table, "relations": relations, "total_affected": total_affected}

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

        inserted = 0
        skipped = 0
        errors = []

        for i, row in enumerate(rows):
            try:
                filtered = {k: v for k, v in row.items() if k in valid_cols}
                if not filtered:
                    skipped += 1
                    continue

                cols = ", ".join(filtered.keys())
                placeholders = ", ".join(f":{k}" for k in filtered.keys())
                # replace 模式：INSERT OR REPLACE（SQLite 原生支持，主键冲突时替换）
                verb = "INSERT OR REPLACE INTO" if mode == "replace" else "INSERT INTO"
                sql = f"{verb} {table} ({cols}) VALUES ({placeholders})"
                await self.db.execute(text(sql), filtered)
                inserted += 1
            except Exception as e:
                errors.append({"row": i + 1, "error": str(e)})
                skipped += 1

        await self.db.flush()
        return {
            "ok": True,
            "total": len(rows),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
        }

    # ---- 审计日志 ----

    async def write_audit(
        self,
        action: str,
        target: Optional[str] = None,
        operator: Optional[str] = None,
        detail: Optional[dict] = None,
    ) -> None:
        """写入审计日志。失败不抛异常（审计不应阻断主流程）。"""
        try:
            log = AuditLog(
                category="db_admin",
                action=action,
                target=target,
                operator=operator,
                detail=json.dumps(detail, ensure_ascii=False, default=str) if detail else None,
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
