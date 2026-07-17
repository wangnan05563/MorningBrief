"""B 端数据库维护路由（对标 17_xianyu api_db_admin）。

仅 admin 角色可访问（require_admin 依赖）。
所有写操作（删除/批量删除/导入）须传 confirm_token 校验。
"""
import csv
import hmac
import io
import json
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import AdminPayload, require_admin
from app.core.exceptions import ParamError
from app.core.response import success
from app.database import get_db
from app.services.db_admin_service import DbAdminService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/admin/api/v1/db-admin", tags=["B端-数据库维护"])

# 危险操作确认令牌常量，前端须输入此值
CONFIRM_TOKEN = settings.DB_ADMIN_CONFIRM_TOKEN


class RowCreateRequest(BaseModel):
    """新增行请求体。"""
    values: dict


class RowUpdateRequest(BaseModel):
    """更新行请求体。"""
    values: dict


class BatchDeleteRequest(BaseModel):
    """批量删除请求体。"""
    ids: list
    confirm_token: str


class CascadePreviewRequest(BaseModel):
    """级联预览请求体。"""
    ids: list


class ImportRequest(BaseModel):
    """导入请求体。"""
    rows: list[dict]
    mode: str = "insert"  # insert | replace
    confirm_token: str


def _validate_confirm_token(token: str) -> None:
    """校验危险操作确认令牌。

    空值拒绝执行：DB_ADMIN_CONFIRM_TOKEN 未配置时禁止危险操作。
    使用 hmac.compare_digest 常量时间比较，防御时序攻击。
    """
    if not CONFIRM_TOKEN:
        raise ParamError("服务器未配置 DB_ADMIN_CONFIRM_TOKEN，危险操作被禁止")
    if not hmac.compare_digest(token, CONFIRM_TOKEN):
        raise ParamError("confirm_token 校验失败")


# ---- 表浏览 ----

@router.get("/tables")
async def list_tables(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """列出所有白名单表及行数。"""
    svc = DbAdminService(db)
    tables = await svc.list_tables()
    return success(data=tables)


@router.get("/tables/{table}/schema")
async def get_table_schema(
    table: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """反射表结构。"""
    svc = DbAdminService(db)
    schema = await svc.get_table_schema(table)
    return success(data=schema)


# ---- 行级查询 ----

@router.get("/tables/{table}/rows")
async def list_rows(
    table: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order_by: str | None = Query(None),
    order_dir: str = Query("ASC"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """分页查询表数据。"""
    svc = DbAdminService(db)
    data = await svc.list_rows(
        table=table, limit=limit, offset=offset,
        order_by=order_by, order_dir=order_dir, search=search,
    )
    return success(data=data)


# ---- 行 CRUD ----

@router.post("/tables/{table}/rows")
async def create_row(
    table: str,
    body: RowCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """新增一行。"""
    svc = DbAdminService(db)
    result = await svc.create_row(table, body.values)
    await svc.write_audit(action="create", target=table, operator=admin.username, detail=body.values)
    await db.commit()
    return success(data=result)


@router.patch("/tables/{table}/rows/{pk_value:path}")
async def update_row(
    table: str,
    pk_value: str,
    body: RowUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """更新一行（主键不可更新）。"""
    svc = DbAdminService(db)
    result = await svc.update_row(table, pk_value, body.values)
    await svc.write_audit(
        action="update", target=table, operator=admin.username,
        detail={"pk": pk_value, "values": body.values},
    )
    await db.commit()
    return success(data=result)


@router.delete("/tables/{table}/rows/{pk_value:path}")
async def delete_row(
    table: str,
    pk_value: str,
    confirm_token: str = Query(..., description="危险操作确认令牌"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """删除一行（含级联）。"""
    _validate_confirm_token(confirm_token)
    svc = DbAdminService(db)
    result = await svc.delete_row(table, pk_value)
    await svc.write_audit(
        action="delete", target=table, operator=admin.username,
        detail={"pk": pk_value, "result": result},
    )
    await db.commit()
    return success(data=result)


@router.post("/tables/{table}/rows/batch-delete")
async def batch_delete(
    table: str,
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """批量删除（上限 DB_ADMIN_MAX_PAGE_SIZE）。"""
    _validate_confirm_token(body.confirm_token)
    svc = DbAdminService(db)
    result = await svc.batch_delete(table, body.ids)
    await svc.write_audit(
        action="batch_delete", target=table, operator=admin.username,
        detail={"ids": body.ids, "result": result},
    )
    await db.commit()
    return success(data=result)


# ---- 级联预览 ----

@router.post("/tables/{table}/cascade-preview")
async def cascade_preview(
    table: str,
    body: CascadePreviewRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """预览级联删除影响范围。"""
    svc = DbAdminService(db)
    data = await svc.cascade_preview(table, body.ids)
    return success(data=data)


# ---- 导出 ----

@router.get("/tables/{table}/export")
async def export_rows(
    table: str,
    format: str = Query("csv", description="导出格式：csv | json"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """导出表数据为 CSV 或 JSON。"""
    svc = DbAdminService(db)
    rows, col_names, filename = await svc.export_rows(table, format)

    if format == "csv":
        # CSV：UTF-8 BOM 头，Excel 兼容
        buf = io.StringIO()
        buf.write("\ufeff")  # BOM
        writer = csv.writer(buf)
        writer.writerow(col_names)
        for row in rows:
            writer.writerow([row.get(c) for c in col_names])
        content = buf.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        # JSON：标准数组
        content = json.dumps(rows, ensure_ascii=False, default=str, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


# ---- 导入 ----

@router.post("/tables/{table}/import")
async def import_rows(
    table: str,
    body: ImportRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """导入数据（insert 或 replace 模式）。"""
    _validate_confirm_token(body.confirm_token)
    svc = DbAdminService(db)
    result = await svc.import_rows(table, body.rows, body.mode)
    await svc.write_audit(
        action="import", target=table, operator=admin.username,
        detail={"mode": body.mode, "total": len(body.rows), "result": result},
    )
    await db.commit()
    return success(data=result)


# ---- 审计日志 ----

@router.get("/audit-log")
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """查询数据库维护审计日志。"""
    svc = DbAdminService(db)
    logs = await svc.list_audit_logs(limit)
    return success(data=logs)
