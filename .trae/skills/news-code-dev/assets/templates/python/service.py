"""{module} 服务层 - {description}."""
import json
import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)


class {ServiceName}Service:
    """{description}服务。"""

    def __init__(self, db_session: AsyncSession, redis_client=None):
        self.db = db_session
        self.redis = redis_client

    async def get_{name}(self, id: int) -> dict[str, Any] | None:
        """获取单个{entity}。

        使用 cache-aside 模式：先查缓存，未命中再查数据库。

        Args:
            id: {entity} ID

        Returns:
            {entity} 数据字典，不存在返回 None
        """
        cache_key = f"{self.__class__.__name__.lower()}:get:{id}"
        
        # 先查缓存
        if self.redis:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        # 缓存未命中，查数据库
        stmt = select(Model).where(Model.id == id)
        result = await self.db.execute(stmt)
        obj = result.scalar_one_or_none()

        if not obj:
            return None

        data = obj.to_dict()

        # 写入缓存，设置过期时间防止脏数据
        if self.redis:
            await self.redis.setex(cache_key, settings.CACHE_TTL_SEC, json.dumps(data))

        return data

    async def list_{name}(
        self,
        page: int = 1,
        page_size: int = 20,
        **filters,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页获取{entity}列表。

        Args:
            page: 页码（从 1 开始）
            page_size: 每页数量
            filters: 过滤条件

        Returns:
            (数据列表, 总数)
        """
        # 构建查询条件
        stmt = select(Model)
        count_stmt = select(Model.id)
        
        for key, value in filters.items():
            if value is not None:
                column = getattr(Model, key, None)
                if column:
                    stmt = stmt.where(column == value)
                    count_stmt = count_stmt.where(column == value)

        # 查询总数（用于分页）
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.all())

        # 查询数据，限制返回数量防止大查询
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        stmt = stmt.order_by(Model.created_at.desc())
        
        result = await self.db.execute(stmt)
        items = [row.to_dict() for row in result.scalars().all()]

        return items, total

    async def create_{name}(self, data: dict[str, Any]) -> Model:
        """创建{entity}。

        Args:
            data: {entity} 数据字典

        Returns:
            创建的{entity}模型实例
        """
        obj = Model(**data)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)

        # 创建后清除相关缓存
        if self.redis:
            await self.redis.delete(f"{self.__class__.__name__.lower()}:list:*")

        return obj

    async def update_{name}(self, id: int, data: dict[str, Any]) -> Model | None:
        """更新{entity}。

        更新后删除缓存，下次读取时自动重建。

        Args:
            id: {entity} ID
            data: 更新的字段

        Returns:
            更新后的{entity}，不存在返回 None
        """
        stmt = (
            update(Model)
            .where(Model.id == id)
            .values(**data)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()

        if result.rowcount == 0:
            return None

        # 删除旧缓存
        if self.redis:
            cache_key = f"{self.__class__.__name__.lower()}:get:{id}"
            await self.redis.delete(cache_key)

        return await self.get_{name}(id)

    async def delete_{name}(self, id: int) -> bool:
        """删除{entity}。

        Args:
            id: {entity} ID

        Returns:
            是否删除成功
        """
        stmt = update(Model).where(Model.id == id).values(is_deleted=True)
        result = await self.db.execute(stmt)
        await self.db.commit()

        # 删除缓存
        if self.redis:
            await self.redis.delete(f"{self.__class__.__name__.lower()}:get:{id}")

        return result.rowcount > 0
