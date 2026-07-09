"""{module} 路由 - {description}."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_token
from app.core.database import get_db
from app.core.response import success, error
from app.schemas.{module} import {EntityCreate, {Entity}Update}
from app.services.{service_name} import {ServiceName}Service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/{module}", tags=["{module}"])


async def get_{name}_service(
    db: AsyncSession = Depends(get_db),
) -> {ServiceName}Service:
    """获取{entity}服务实例。"""
    return {ServiceName}Service(db)


@router.get("/{item_id}")
async def get_{name}(
    item_id: int,
    service: Annotated[{ServiceName}Service, Depends(get_{name}_service)],
):
    """获取单个{entity}。

    Args:
        item_id: {entity} ID
    """
    result = await service.get_{name}(item_id)
    if not result:
        return error(code=404, message="{entity}不存在")
    return success(data=result)


@router.get("/")
async def list_{name}(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    service: Annotated[{ServiceName}Service, Depends(get_{name}_service)],
):
    """分页获取{entity}列表。

    Args:
        page: 页码
        page_size: 每页数量（最大 100）
    """
    items, total = await service.list_{name}(page, page_size)
    return success(data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/")
async def create_{name}(
    data: {EntityCreate},
    service: Annotated[{ServiceName}Service, Depends(get_{name}_service)],
):
    """创建{entity}。

    Args:
        data: {entity} 创建数据
    """
    try:
        result = await service.create_{name}(data.model_dump())
        return success(data=result.to_dict(), message="{entity}创建成功")
    except Exception as e:
        logger.exception(f"创建{entity}失败: data={data}")
        return error(code=500, message="服务器内部错误")


@router.put("/{item_id}")
async def update_{name}(
    item_id: int,
    data: {Entity}Update,
    service: Annotated[{ServiceName}Service, Depends(get_{name}_service)],
):
    """更新{entity}。

    Args:
        item_id: {entity} ID
        data: 更新数据
    """
    result = await service.update_{name}(item_id, data.model_dump(exclude_unset=True))
    if not result:
        return error(code=404, message="{entity}不存在")
    return success(data=result.to_dict(), message="{entity}更新成功")


@router.delete("/{item_id}")
async def delete_{name}(
    item_id: int,
    service: Annotated[{ServiceName}Service, Depends(get_{name}_service)],
):
    """删除{entity}。

    Args:
        item_id: {entity} ID
    """
    success = await service.delete_{name}(item_id)
    if not success:
        return error(code=404, message="{entity}不存在")
    return success(message="{entity}删除成功")
