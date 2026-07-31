"""B 端统计路由。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AdminPayload, get_current_admin
from app.core.exceptions import BizError
from app.core.response import success
from app.database import get_db
from app.services.stats_service import StatsService

router = APIRouter(prefix="/admin/api/v1/stats", tags=["B端-统计"])

# range 字符串到天数的映射，前端只允许这三个枚举值
RANGE_MAP = {"7d": 7, "30d": 30, "90d": 90}


@router.get("/overview")
async def get_overview(
    target_date: date = Query(..., description="日期，格式 YYYY-MM-DD", alias="date"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    svc = StatsService(db)
    data = await svc.get_overview(target_date=target_date)
    return success(data=data)


@router.get("/trend")
async def get_trend(
    metric: str = Query(..., description="指标：dau/play_count/completion_rate/avg_listen_duration"),
    range_str: str = Query("7d", alias="range", description="区间：7d/30d/90d"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    # range 在路由层解析为天数，service 只接收 int
    range_days = RANGE_MAP.get(range_str)
    if range_days is None:
        raise BizError(code=400, message=f"不支持的 range: {range_str}")
    svc = StatsService(db)
    data = await svc.get_trend(metric=metric, range_days=range_days)
    return success(data=data)


@router.get("/channel-health")
async def get_channel_health(
    range_days: int = Query(7, ge=1, le=30, description="回溯天数，默认 7 天（与 FALLBACK_DAYS 对齐）"),
    db: AsyncSession = Depends(get_db),
    admin: AdminPayload = Depends(get_current_admin),
):
    """频道素材健康度仪表盘。

    用于运维发现长期无新素材的频道、RSS 源衰退、关键词命中率异常等问题。
    返回每个频道近 N 天入库趋势 + 当日 pending 数 + 健康状态（healthy/warning/critical）。
    """
    svc = StatsService(db)
    data = await svc.get_channel_health(range_days=range_days)
    return success(data=data)


@router.get("/rss-health")
async def get_rss_health(
    refresh: bool = Query(False, description="true 时立即触发一次巡检（耗时约 5-15s）"),
    admin: AdminPayload = Depends(get_current_admin),
):
    """RSS 源可达性健康度。

    默认返回最近一次巡检结果（不触发新巡检，响应快）。
    refresh=true 时立即触发一次巡检，适合运维手动验证源状态。
    巡检任务每 2 小时自动执行一次，连续失败 3 次的源会自动 WARNING 日志。
    """
    from app.services.rss_source_service import check_all_sources, get_source_status
    if refresh:
        data = await check_all_sources()
    else:
        data = get_source_status()
    return success(data=data)


@router.get("/llm-metrics")
async def get_llm_metrics(
    admin: AdminPayload = Depends(get_current_admin),
):
    """LLM 字数硬约束重试命中率指标。

    返回自进程启动以来累计的计数与派生率：
    - total_calls: _rewrite_one 总调用次数（基线）
    - triggered: 触发硬约束重试的次数（首次生成字数 <70% 目标）
    - improved: 重试后字数有改善的次数
    - not_improved: 重试未改善（含异常失败）的次数
    - trigger_rate: 触发率 = triggered / total_calls × 100
    - improve_rate: 改善率 = improved / triggered × 100
    - not_improve_rate: 未改善率 = not_improved / triggered × 100

    用于运维评估 P2-2 改进效果：触发率高说明 LLM 字数缩水严重需优化 prompt；
    改善率低说明硬约束后缀效果不佳需更换策略。
    """
    from app.workflow.llm.rewriter import get_word_count_retry_stats
    data = get_word_count_retry_stats()
    return success(data=data)
