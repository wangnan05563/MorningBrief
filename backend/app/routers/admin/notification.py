"""B 端通知管理路由。

端点：
- GET  /admin/api/v1/notification/config       获取通知配置（敏感字段脱敏）
- PUT  /admin/api/v1/notification/config       保存通知配置（热更新 NotifierHub）
- POST /admin/api/v1/notification/test         发送测试通知
- GET  /admin/api/v1/notification/templates    模板列表
- PUT  /admin/api/v1/notification/templates/{id}  更新模板
- POST /admin/api/v1/notification/templates/{id}/preview  预览模板渲染效果
- GET  /admin/api/v1/notification/logs         日志列表（分页）
- POST /admin/api/v1/notification/logs/{id}/resend  重发某条日志

所有端点需 admin 权限，防止运营误改通知配置。
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin, AdminPayload
from app.core.exceptions import ParamError
from app.core.response import success
from app.database import get_db
from app.services.notification.config_service import NotificationConfigService
from app.services.notification.log_service import LogService
from app.services.notification.sender import get_notification_sender
from app.services.notification.template_service import (
    TemplateService,
    extract_variables,
)

router = APIRouter(prefix="/admin/api/v1/notification", tags=["B端-通知管理"])


class SaveConfigBody(BaseModel):
    global_enabled: bool = False
    failed_enabled: bool = True
    review_enabled: bool = True
    published_enabled: bool = False
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""
    admin_base_url: str = ""


class UpdateTemplateBody(BaseModel):
    name: str | None = None
    title_template: str | None = None
    body_template: str | None = None
    enabled: bool | None = None


class PreviewTemplateBody(BaseModel):
    """预览模板时手动传入变量值（不传则用空字符串）。"""
    variables: dict[str, str] = {}


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取通知配置（敏感字段脱敏）+ 自动检测的 base_url。"""
    svc = NotificationConfigService(db)
    data = await svc.get_config()
    return success(data=data)


@router.put("/config")
async def save_config(
    body: SaveConfigBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """保存通知配置（热更新 NotifierHub，新凭证立即生效）。"""
    svc = NotificationConfigService(db)
    await svc.save_config(body.model_dump())
    return success(message="配置已保存")


@router.post("/test")
async def test_send(
    admin: AdminPayload = Depends(require_admin),
):
    """发送测试通知（不走开关检查，直接发送一条测试消息）。"""
    sender = get_notification_sender()
    result = await sender.send_test()
    return success(data=result)


@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """获取所有消息模板。"""
    svc = TemplateService(db)
    templates = await svc.list_templates()
    return success(data=[
        {
            "id": t.id,
            "event_type": t.event_type,
            "name": t.name,
            "title_template": t.title_template,
            "body_template": t.body_template,
            "is_preset": t.is_preset,
            "enabled": t.enabled,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            # 提取模板中引用的变量名，供前端展示可用变量列表
            "variables": extract_variables(t.title_template) + extract_variables(t.body_template),
        }
        for t in templates
    ])


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    body: UpdateTemplateBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """更新模板（仅允许修改 name/title_template/body_template/enabled）。"""
    svc = TemplateService(db)
    tpl = await svc.update_template(template_id, body.model_dump(exclude_none=True))
    if tpl is None:
        raise ParamError("模板不存在")
    return success(data={
        "id": tpl.id,
        "event_type": tpl.event_type,
        "name": tpl.name,
        "title_template": tpl.title_template,
        "body_template": tpl.body_template,
        "is_preset": tpl.is_preset,
        "enabled": tpl.enabled,
        "updated_at": tpl.updated_at.isoformat() if tpl.updated_at else None,
    })


@router.post("/templates/{template_id}/preview")
async def preview_template(
    template_id: int,
    body: PreviewTemplateBody,
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """预览模板渲染效果（用传入的变量值渲染标题与正文）。"""
    svc = TemplateService(db)
    tpl = await svc.get_template_by_id(template_id)
    if tpl is None:
        raise ParamError("模板不存在")

    from app.services.notification.template_service import render_template
    title = render_template(tpl.title_template, body.variables)
    body_text = render_template(tpl.body_template, body.variables)
    return success(data={"title": title, "body": body_text})


@router.get("/logs")
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(require_admin),
):
    """分页查询通知发送日志（按创建时间倒序）。"""
    svc = LogService(db)
    data = await svc.list_logs(
        page=page, page_size=page_size, event_type=event_type, status=status,
    )
    return success(data=data)


@router.post("/logs/{log_id}/resend")
async def resend_log(
    log_id: int,
    admin: AdminPayload = Depends(require_admin),
):
    """重发某条日志（用日志中记录的 payload 重新渲染并发送）。"""
    sender = get_notification_sender()
    result = await sender.resend_log(log_id)
    return success(data=result)
