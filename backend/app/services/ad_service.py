"""广告服务：素材管理、投放规则、排期与生效投放。"""
from calendar import monthrange
from datetime import date, datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.core.exceptions import BizError, NotFoundError
from app.models import AdMaterial, AdPlacement
from app.models.ad_placement import AdPosition

# 生效投放缓存 TTL 25h：覆盖目标日期全天 + 1h 时区容差
ACTIVE_PLACEMENT_TTL = 25 * 3600

# 合法广告位枚举值，用于入参校验
VALID_POSITIONS = {p.value for p in AdPosition}


class AdService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # 进程内 TTLCache，替代原 Redis cache-aside（直接存 dict，无需 json 序列化）
        self.cache = cache

    # ---- 素材管理 ----

    async def list_materials(self, page: int, size: int) -> dict:
        """广告素材分页列表。"""
        count_result = await self.db.execute(
            select(func.count(AdMaterial.id))
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        result = await self.db.execute(
            select(AdMaterial)
            .order_by(AdMaterial.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        materials = result.scalars().all()

        list_data = [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "file_url": m.file_url,
                "duration": m.duration,
                "is_default": m.is_default,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in materials
        ]
        return {"total": total, "list": list_data}

    async def create_material(
        self, name: str, description: str, file_url: str, duration: int
    ) -> int:
        """新建广告素材，返回素材 id。"""
        material = AdMaterial(
            name=name,
            description=description,
            file_url=file_url,
            duration=duration,
        )
        self.db.add(material)
        await self.db.flush()
        await self.db.commit()
        return material.id

    async def delete_material(self, material_id: int) -> None:
        """删除素材：有关联投放时拒绝，避免悬空引用。"""
        # 先查关联投放，存在则禁止删除
        count_result = await self.db.execute(
            select(func.count(AdPlacement.id)).where(
                AdPlacement.material_id == material_id
            )
        )
        if (count_result.scalar() or 0) > 0:
            raise BizError(code=400, message="该素材有关联投放，无法删除")

        result = await self.db.execute(
            select(AdMaterial).where(AdMaterial.id == material_id)
        )
        material = result.scalar_one_or_none()
        if material is None:
            raise NotFoundError("素材不存在")

        await self.db.delete(material)
        await self.db.commit()

    # ---- 投放规则 ----

    async def list_placements(self, page: int, size: int) -> dict:
        """投放规则分页列表，带素材名称。"""
        count_result = await self.db.execute(
            select(func.count(AdPlacement.id))
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        # join 素材表取名称，避免列表项二次查询
        result = await self.db.execute(
            select(AdPlacement, AdMaterial.name)
            .join(AdMaterial, AdPlacement.material_id == AdMaterial.id)
            .order_by(AdPlacement.start_date.desc())
            .offset(offset)
            .limit(size)
        )
        rows = result.all()

        list_data = [
            {
                "id": p.id,
                "material_id": p.material_id,
                "material_name": m_name,
                "position": p.position if p.position else None,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
            }
            for p, m_name in rows
        ]
        return {"total": total, "list": list_data}

    async def create_placement(
        self,
        material_id: int,
        position: str,
        start_date: date,
        end_date: date,
    ) -> int:
        """新建投放规则，校验素材存在、广告位合法、日期区间有效。"""
        # 素材存在性校验
        mat_result = await self.db.execute(
            select(AdMaterial.id).where(AdMaterial.id == material_id)
        )
        if mat_result.scalar_one_or_none() is None:
            raise BizError(code=400, message="素材不存在")

        # 广告位合法性校验
        if position not in VALID_POSITIONS:
            raise BizError(code=400, message=f"非法广告位: {position}")

        # 起止日期校验：end 必须晚于 start
        if start_date >= end_date:
            raise BizError(code=400, message="start_date 必须早于 end_date")

        placement = AdPlacement(
            material_id=material_id,
            position=AdPosition(position),
            start_date=start_date,
            end_date=end_date,
        )
        self.db.add(placement)
        await self.db.flush()
        await self.db.commit()
        return placement.id

    async def delete_placement(self, placement_id: int) -> None:
        """删除投放规则。"""
        result = await self.db.execute(
            select(AdPlacement).where(AdPlacement.id == placement_id)
        )
        placement = result.scalar_one_or_none()
        if placement is None:
            raise NotFoundError("投放规则不存在")

        await self.db.delete(placement)
        await self.db.commit()

    # ---- 排期与生效投放 ----

    async def get_schedule(self, month: str) -> dict:
        """按月查询投放排期，month 格式 '2026-07'。"""
        # 解析月份首末日，用于区间重叠查询
        first_day = datetime.strptime(month, "%Y-%m").date()
        _, last_day_num = monthrange(first_day.year, first_day.month)
        last_day = date(first_day.year, first_day.month, last_day_num)

        # 取与该月有重叠的投放：start <= 月末 AND end >= 月初
        result = await self.db.execute(
            select(AdPlacement, AdMaterial.name)
            .join(AdMaterial, AdPlacement.material_id == AdMaterial.id)
            .where(
                AdPlacement.start_date <= last_day,
                AdPlacement.end_date >= first_day,
            )
            .order_by(AdPlacement.start_date)
        )
        rows = result.all()

        placements = [
            {
                "id": p.id,
                "material_id": p.material_id,
                "material_name": m_name,
                "position": p.position if p.position else None,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
            }
            for p, m_name in rows
        ]
        return {"placements": placements}

    async def get_active_placements(self, target_date: date) -> dict:
        """查询某天生效的投放，cache-aside 缓存到 TTLCache。

        C 端每期播放都会读此接口，缓存避免高频查库。
        V1.2 改造：TTLCache 直接存 dict，无需 json 序列化/反序列化。
        """
        cache_key = f"ad:placement:{target_date.isoformat()}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # join 素材取 file_url 与 duration，C 端拼接音频时直接可用
        result = await self.db.execute(
            select(AdPlacement, AdMaterial.file_url, AdMaterial.duration)
            .join(AdMaterial, AdPlacement.material_id == AdMaterial.id)
            .where(
                AdPlacement.start_date <= target_date,
                AdPlacement.end_date >= target_date,
            )
        )
        rows = result.all()

        # 三段广告位分别填充，缺位为 None
        data = dict.fromkeys(("head", "mid", "tail"), None)
        for p, file_url, duration in rows:
            data[p.position] = {
                "material_id": p.material_id,
                "file_url": file_url,
                "duration": duration,
            }

        await self.cache.set(cache_key, data, ttl=ACTIVE_PLACEMENT_TTL)
        return data
