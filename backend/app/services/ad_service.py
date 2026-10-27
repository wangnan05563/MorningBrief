"""广告服务：素材管理、投放规则、排期与生效投放。"""
from calendar import monthrange
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.manager import cache
from app.cache.version import AD_PLACEMENT_CACHE, bump_version, current_version
from app.core.exceptions import BizError, NotFoundError
from app.models import AdMaterial, AdPlacement
from app.models.ad_placement import AdPosition

# 生效投放缓存 TTL 25h：覆盖目标日期全天 + 1h 时区容差
ACTIVE_PLACEMENT_TTL = 25 * 3600

# 合法广告位枚举值，用于入参校验
VALID_POSITIONS = {p.value for p in AdPosition}

# 投放展示状态（T02602）：只有「启用 + 今天落在闭区间内」才与真实播放一致
PLACEMENT_DISABLED = "disabled"
PLACEMENT_PENDING = "pending"
PLACEMENT_ACTIVE = "active"
PLACEMENT_EXPIRED = "expired"


def derive_placement_status(
    enabled: Optional[int],
    start_date: Optional[date],
    end_date: Optional[date],
    today: Optional[date] = None,
) -> str:
    """按开关与日期闭区间派生投放状态，口径与 get_active_placements 一致。

    停用优先于日期态：开关是运营的显式干预，先显示这一个；重新启用后
    日期派生的「待投放 / 生效中 / 已过期」才接管。服务端统一给字段，
    避免 PC、移动端、排期日历各算一遍（T02602）。
    """
    if enabled == 0:
        return PLACEMENT_DISABLED
    ref = today or date.today()
    if start_date and ref < start_date:
        return PLACEMENT_PENDING
    if end_date and ref > end_date:
        return PLACEMENT_EXPIRED
    return PLACEMENT_ACTIVE


def _placement_status(p: "AdPlacement", today: date) -> str:
    enabled = p.enabled if p.enabled is not None else 1
    return derive_placement_status(enabled, p.start_date, p.end_date, today)


def placement_cache_key(version: int, target_date: date) -> str:
    """「生效投放」缓存键，带共享版本号（T02600）。"""
    return f"ad:placement:v{version}:{target_date.isoformat()}"


class AdService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # 进程内 TTLCache，替代原 Redis cache-aside（直接存 dict，无需 json 序列化）
        self.cache = cache

    async def invalidate_active_cache(self) -> None:
        """清掉**本进程**的「生效投放」缓存（T02491 / FR-UX-203 D14）。

        跨进程的正确性不靠它：TTLCache 是进程内单例，`delete_pattern` 只能清当前 worker，
        `UVICORN_WORKERS>1` 或 launcher 的 sched/api 角色分裂时，别的 worker 仍会命中旧键
        最长 25h（T02600）。跨进程失效由 `app.cache.version` 的版本号承担——写操作与数据
        同事务 bump 版本，读方按版本取键，旧键自然没人再读。

        这里保留本地清理，只做两件事：本进程立刻省掉一次无谓的 miss-回源-写回，
        以及把已经没人读的旧键从 maxsize 里腾出来。必须在数据库提交之后调用。
        """
        await self.cache.delete_pattern("ad:placement:*")

    # ---- 素材管理 ----

    async def list_materials(self, page: int, size: int, keyword: str | None = None) -> dict:
        """广告素材分页列表。

        keyword 按素材名称模糊搜索（D16）：投放对话框的素材下拉原先硬截断在前 100 条，
        `filterable` 只能在已加载的 100 条里找，第 101 条起的素材「在列表里根本不存在」。
        有了服务端搜索，前端才能把「搜不到」和「没上传」区分开。
        """
        conds = []
        kw = (keyword or "").strip()
        if kw:
            conds.append(AdMaterial.name.like(f"%{kw}%"))

        count_result = await self.db.execute(
            select(func.count(AdMaterial.id)).where(*conds)
        )
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        result = await self.db.execute(
            select(AdMaterial)
            .where(*conds)
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

    async def list_placements(self, page: int, size: int, enabled: Optional[int] = None) -> dict:
        """投放规则分页列表，带素材名称；enabled 可筛选启用/停用（D13）。"""
        conditions = []
        if enabled is not None:
            conditions.append(AdPlacement.enabled == enabled)

        count_stmt = select(func.count(AdPlacement.id))
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * size
        # join 素材表取名称，避免列表项二次查询
        list_stmt = (
            select(AdPlacement, AdMaterial.name)
            .join(AdMaterial, AdPlacement.material_id == AdMaterial.id)
            .order_by(AdPlacement.start_date.desc())
            .offset(offset)
            .limit(size)
        )
        for cond in conditions:
            list_stmt = list_stmt.where(cond)
        result = await self.db.execute(list_stmt)
        rows = result.all()
        today = date.today()

        list_data = [
            {
                "id": p.id,
                "material_id": p.material_id,
                "material_name": m_name,
                "position": p.position if p.position else None,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                "enabled": p.enabled if p.enabled is not None else 1,
                # 状态由服务端派生（T02602）：只看 enabled 会把 12 月排期和过期投放
                # 都显示成「投放中」，与 C 端真实播放不一致
                "status": _placement_status(p, today),
            }
            for p, m_name in rows
        ]
        return {"total": total, "list": list_data}

    async def set_placement_enabled(self, placement_id: int, enabled: int) -> dict:
        """投放启用/停用（M7 FR-M702 移动端启停）。

        Args:
            enabled: 1=启用，0=停用
        """
        p = await self.db.get(AdPlacement, placement_id)
        if p is None:
            raise ValueError(f"投放不存在: {placement_id}")
        if enabled == 1:
            # T02927 / D24：重新启用同样要查冲突。只拦新建的话，
            # 「两条都停用、再依次启用」就能绕过，护栏等于不存在。
            await self._assert_no_enabled_overlap(
                p.position,
                p.start_date,
                p.end_date,
                exclude_id=p.id,
                field="enabled",
            )
        p.enabled = enabled
        await self.db.flush()
        # T02600：与 create/delete 同口径，版本 bump 交给调用方（routers/admin/ads.py）
        # 的那次 commit 一起提交；这里不 commit，否则启停与版本跳变会分成两个事务，
        # 留下「数据已改、版本未跳」的窗口。
        await bump_version(self.db, AD_PLACEMENT_CACHE)
        # 启停后回传由服务端派生的状态：前端不做二次推算，切换即落位（T02602）
        return {
            "id": p.id,
            "enabled": p.enabled,
            "status": _placement_status(p, date.today()),
        }

    async def _find_enabled_overlaps(
        self,
        position: str,
        start_date: date,
        end_date: date,
        exclude_id: Optional[int] = None,
    ) -> list:
        """查同广告位、启用中、与给定闭区间相交的投放（含素材名）。"""
        conditions = [
            AdPlacement.position == position,
            AdPlacement.enabled == 1,
            # 闭区间相交：两段 [s1,e1]、[s2,e2] 有交集 ⇔ s1<=e2 且 e1>=s2
            AdPlacement.start_date <= end_date,
            AdPlacement.end_date >= start_date,
        ]
        if exclude_id is not None:
            # 重新启用时排除自己，否则「启用」永远和自身冲突
            conditions.append(AdPlacement.id != exclude_id)
        result = await self.db.execute(
            select(AdPlacement, AdMaterial.name)
            .join(AdMaterial, AdPlacement.material_id == AdMaterial.id)
            .where(*conditions)
            .order_by(AdPlacement.id)
        )
        return result.all()

    async def _assert_no_enabled_overlap(
        self,
        position: str,
        start_date: date,
        end_date: date,
        exclude_id: Optional[int] = None,
        field: str = "dateRange",
    ) -> None:
        """同一广告位同一时段只允许一条启用中的投放（T02927 / D24）。

        裁决：不允许重叠。C 端每个广告位每期只播一条（get_active_placements
        每个 position 只留一个结果），重叠入库等于让「播哪条」由数据库返回顺序
        决定。停用的投放不参与冲突判定——「先停用旧的再建新的」是运营唯一的
        可逆替换路径，停用记录本身也要留作追溯；但之后想把旧的重启同样会被
        拦下，否则只校验新建就是可以绕过的假护栏。
        """
        rows = await self._find_enabled_overlaps(
            position, start_date, end_date, exclude_id
        )
        if not rows:
            return

        conflicts = [
            {
                "id": p.id,
                "material_id": p.material_id,
                "material_name": name,
                "position": p.position,
                "start_date": p.start_date.isoformat(),
                "end_date": p.end_date.isoformat(),
            }
            for p, name in rows
        ]
        shown = "、".join(
            f"「{c['material_name']}」（#{c['id']}，"
            f"{c['start_date']} ~ {c['end_date']}）"
            for c in conflicts[:3]
        )
        more = f" 等 {len(conflicts)} 条" if len(conflicts) > 3 else ""
        message = (
            f"该广告位在所选区间内已有启用中的投放：{shown}{more}；"
            "请先停用或调整日期区间"
        )
        # INT-UX-01：字段级明细 + 结构化冲突列表，界面不用再去切字符串
        raise BizError(
            code=400,
            message=message,
            data={
                "errors": [{"field": field, "message": message}],
                "conflicts": conflicts,
            },
        )

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

        # 起止日期校验：区间是**闭区间**（get_active_placements 用 end_date >= 目标日），
        # 所以 start == end 是合法的「只投一天」；旧写法 `start >= end` 把单日投放一并拒掉，
        # 还把英文字段名原样弹给运营（D15）。只有倒序才是真的错。
        if start_date > end_date:
            raise BizError(
                code=400,
                message="结束日期不能早于开始日期；只投一天可让开始与结束为同一天",
                data={
                    "errors": [
                        {
                            "field": "dateRange",
                            "message": "日期区间倒序：结束日期早于开始日期（含首尾，同一天可投）",
                        }
                    ]
                },
            )

        # T02927 / D24：同位区间重叠不再入库。重叠时 C 端每个广告位只能挑一条播，
        # 挑哪条由数据库返回顺序决定，排期页看到两条、实际只播一条。
        await self._assert_no_enabled_overlap(position, start_date, end_date)

        placement = AdPlacement(
            material_id=material_id,
            position=AdPosition(position),
            start_date=start_date,
            end_date=end_date,
        )
        self.db.add(placement)
        await self.db.flush()
        # T02600：版本与数据同事务跳，commit 前 bump（分开提交会留「数据已改、版本未跳」窗口）
        await bump_version(self.db, AD_PLACEMENT_CACHE)
        await self.db.commit()
        await self.invalidate_active_cache()
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
        await bump_version(self.db, AD_PLACEMENT_CACHE)
        await self.db.commit()
        await self.invalidate_active_cache()

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
        today = date.today()

        placements = [
            {
                "id": p.id,
                "material_id": p.material_id,
                "material_name": m_name,
                "position": p.position if p.position else None,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                # 排期视图要能看出「已停用」，否则停用的投放看着照播（T02491 / D14）
                "enabled": p.enabled,
                # 待投放/已过期同样要可见（T02602）：日历不能把未来或已结束的排期
                # 读成今天在播
                "status": _placement_status(p, today),
            }
            for p, m_name in rows
        ]
        return {"placements": placements}

    async def get_active_placements(self, target_date: date) -> dict:
        """查询某天生效的投放，cache-aside 缓存到 TTLCache。

        C 端每期播放都会读此接口，缓存避免高频查库。
        V1.2 改造：TTLCache 直接存 dict，无需 json 序列化/反序列化。

        T02600：缓存键带**共享版本号**。`invalidate_active_cache()` 只能清本进程的
        TTLCache，多 worker（`launcher.py` workers>1 走 sched/api 双进程）下别的
        进程仍会命中旧值直到 25h TTL 到期——停用一条广告要等一天才对全端生效。
        键里带上 DB 里的版本号后，任何进程的写操作 bump 一次，所有进程的下一次读
        就落到新键上，旧键随 TTL 自然淘汰。版本号是一行主键 SELECT，比下面的
        join 便宜一个数量级，「缓存省掉查库」变成「省掉复杂查库」而不是不查库。
        """
        version = await current_version(self.db, AD_PLACEMENT_CACHE)
        cache_key = placement_cache_key(version, target_date)
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # join 素材取 file_url 与 duration，C 端拼接音频时直接可用
        # enabled 过滤（T02491 / D14）：此前只按日期区间查，停用后 C 端照样播出，
        # 「停用」这条唯一的可逆干预路径等于没有。
        result = await self.db.execute(
            select(AdPlacement, AdMaterial.file_url, AdMaterial.duration)
            .join(AdMaterial, AdPlacement.material_id == AdMaterial.id)
            .where(
                AdPlacement.start_date <= target_date,
                AdPlacement.end_date >= target_date,
                AdPlacement.enabled == 1,
            )
            # T02927：稳定排序。新建/重启已禁止重叠，但历史脏数据里可能仍有同
            # 广告位同日多条；没有 ORDER BY 时返回顺序由执行计划决定，而下面的
            # dict 赋值是「后写覆盖」——同一日期两次查询可能给出不同素材，且
            # 不确定结果还会被缓存 25h。按 id 升序后固定为「最新创建的那条生效」，
            # 行为可预期（探针无法模拟执行计划差异，排序本身由源码 grep 验收）。
            .order_by(AdPlacement.id)
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
