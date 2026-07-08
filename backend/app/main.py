"""
FastAPI 应用入口

单体应用架构：业务服务 + APScheduler + AI 工作流模块在同一进程内。
启动顺序：FastAPI 应用初始化 → 注册异常处理 → 挂载路由 → 启动调度器。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.routers.health import router as health_router
# C 端路由（小程序）
from app.routers.api.auth import router as c_auth_router
from app.routers.api.episodes import router as c_episodes_router
from app.routers.api.playlogs import router as c_playlogs_router
# B 端路由（运营后台）
from app.routers.admin.auth import router as b_auth_router
from app.routers.admin.reviews import router as b_reviews_router
from app.routers.admin.ads import router as b_ads_router
from app.routers.admin.stats import router as b_stats_router
from app.routers.admin.workflows import router as b_workflows_router
# 内部路由（工作流调度）
from app.routers.internal.workflow import router as internal_workflow_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化资源，关闭时清理。"""
    # 启动 APScheduler 定时任务（工作流调度 + 播放日志落库 + 备播检查）
    from app.services.workflow_scheduler import workflow_scheduler
    await workflow_scheduler.start()

    yield

    # 关闭阶段：先停调度器（等待运行中任务），再关 Redis 连接池
    await workflow_scheduler.stop()
    from app.redis_client import redis_client
    await redis_client.close()


def create_app() -> FastAPI:
    """应用工厂，便于测试时创建独立实例。"""
    app = FastAPI(
        title="20_News 语音新闻播报 API",
        version="1.0.0",
        description="全自动 AI 内容生产工作流 + 微信小程序播报服务",
        docs_url="/docs" if settings.is_dev else None,
        redoc_url="/redoc" if settings.is_dev else None,
        lifespan=lifespan,
    )

    # CORS：开发环境允许本地调试，生产环境通过 Nginx 同源
    if settings.is_dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 注册全局异常处理
    register_exception_handlers(app)

    # 挂载路由
    # 健康检查
    app.include_router(health_router)
    # C 端（小程序）
    app.include_router(c_auth_router)
    app.include_router(c_episodes_router)
    app.include_router(c_playlogs_router)
    # B 端（运营后台）
    app.include_router(b_auth_router)
    app.include_router(b_reviews_router)
    app.include_router(b_ads_router)
    app.include_router(b_stats_router)
    app.include_router(b_workflows_router)
    # 内部（工作流调度）
    app.include_router(internal_workflow_router)

    return app


app = create_app()
