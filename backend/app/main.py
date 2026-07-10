"""
FastAPI 应用入口

单体应用架构：业务服务 + APScheduler + AI 工作流模块在同一进程内。
启动顺序：FastAPI 应用初始化 → 建表（首次启动）→ 注册异常处理 → 挂载路由 → 启动调度器。

V1.2 起：
- 数据库改为 SQLite（嵌入式，无需外部容器）
- 缓存改为进程内 TTLCache（无需外部 Redis）
- 启动时通过 SQLAlchemy Base.metadata.create_all 自动建表（开发态）
"""
import mimetypes
from contextlib import asynccontextmanager

from loguru import logger

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Windows 注册表可能缺少常见前端文件类型的 MIME 映射，导致 FileResponse 返回 text/plain，
# 浏览器拒绝执行 JS 模块（Strict MIME type checking）。此处显式注册以确保正确返回。
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
# PWA 清单文件：浏览器要求 application/manifest+json 才会解析
mimetypes.add_type("application/manifest+json", ".webmanifest")

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_setup import setup_logging
from app.middleware.request_id import RequestIdMiddleware
from app.paths import resolve_admin_dist
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
from app.routers.admin.tunnel import router as b_tunnel_router
from app.routers.admin.workflows import router as b_workflows_router
from app.routers.admin.ai_config import router as b_ai_config_router
# 数据库维护与系统清理模块（仅 admin）
from app.routers.admin.db_admin import router as b_db_admin_router
from app.routers.admin.maintenance import router as b_maintenance_router
# 内部路由（工作流调度）
from app.routers.internal.workflow import router as internal_workflow_router

settings = get_settings()


async def _init_sqlite_schema() -> None:
    """首次启动自动建表（开发态/单机 exe 部署用）。

    生产环境如需迁移可改用 Alembic；MVP 阶段直接 create_all 简化运维。
    所有 ORM 模型须在调用前完成导入，否则 Base.metadata 不知道这些表。
    """
    # 触发模型导入（避免循环依赖不在顶部导入）
    from app import models  # noqa: F401
    from app.database import Base, engine, normalize_metadata_for_sqlite

    # 规范化索引名以适配 SQLite 全局唯一约束（幂等）
    normalize_metadata_for_sqlite()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[startup] SQLite schema 已就绪")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化资源，关闭时清理。"""
    # 初始化日志系统（幂等：launcher.py 已提前调用则此处 no-op）
    # 覆盖直接 import app.main 的场景（如 pytest）
    try:
        from app.paths import resolve_log_dir
        log_dir = str(resolve_log_dir())
    except Exception:
        log_dir = settings.LOG_DIR
    setup_logging(log_level=settings.LOG_LEVEL, log_dir=log_dir)

    # 首次启动建表（SQLite 嵌入式，开发与生产共用此路径）
    await _init_sqlite_schema()

    # 从 SQLite 加载 AI 配置覆盖到 Settings 单例（前端修改的配置热生效）
    from app.services.ai_config_service import AIConfigService
    from app.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as session:
            svc = AIConfigService(session)
            await svc.apply_config_to_settings()
    except Exception as e:
        logger.warning("[startup] 加载 AI 配置失败，使用 .env 默认值: %s", e)

    # 启动 APScheduler 定时任务（工作流调度 + 播放日志落库 + 黑名单清理）
    from app.services.workflow_scheduler import workflow_scheduler
    await workflow_scheduler.start()

    # 内网穿透自动启动：auto_start=True 时后台线程启动隧道
    # 用 daemon 线程而非 asyncio：cloudflared/cpolar 是阻塞子进程，线程不占用事件循环
    from app.services.tunnel_service import get_tunnel_service
    try:
        tunnel_svc = get_tunnel_service()
        cfg = tunnel_svc.get_config()
        if cfg.get("auto_start"):
            import threading

            def _auto_start_tunnel():
                try:
                    url = tunnel_svc.start()
                    logger.info("[startup] 内网穿透隧道已自动启动: %s", url)
                except Exception as e:
                    # 自动启动失败不影响主服务，仅记录日志
                    logger.warning("[startup] 内网穿透自动启动失败: %s", e)

            threading.Thread(target=_auto_start_tunnel, daemon=True).start()
    except Exception as e:
        logger.warning("[startup] 读取隧道配置失败，跳过自动启动: %s", e)

    yield

    # 关闭阶段：先停隧道（避免隧道继续转发流量到已关闭的服务），再停调度器，再关数据库引擎
    try:
        from app.services.tunnel_service import get_tunnel_service
        get_tunnel_service().stop()
    except Exception as e:
        logger.warning("[shutdown] 停止内网穿透隧道失败: %s", e)

    await workflow_scheduler.stop()
    from app.database import engine
    await engine.dispose()
    logger.info("[shutdown] SQLite 引擎已释放")


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

    # RequestId 中间件：为每个请求注入全局流水号，贯穿全部日志
    app.add_middleware(RequestIdMiddleware)

    # CORS：开发环境允许本地调试；生产环境单机 exe + 云函数 SCF 直连
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

    # 挂载路由  # NOSONAR
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
    app.include_router(b_tunnel_router)
    app.include_router(b_workflows_router)
    app.include_router(b_ai_config_router)
    app.include_router(b_db_admin_router)
    app.include_router(b_maintenance_router)
    # 内部（工作流调度）
    app.include_router(internal_workflow_router)

    # 挂载前端 SPA（B 端运营后台）
    # API 路由已在前注册，不会被覆盖；未匹配的 GET 请求 fallback 到 index.html
    dist_dir = resolve_admin_dist()
    if dist_dir and dist_dir.exists():
        # /assets 目录：JS/CSS/图片等静态资源（Vite 构建产物）
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # SPA history 模式 fallback：未匹配的 GET 请求返回 index.html
        # 必须在所有 API 路由之后注册，否则会覆盖 API 路由
        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str):
            # API 路径不 fallback，返回 404（避免 API 404 被误返回 index.html）
            if full_path.startswith(("api/", "admin/api/")):
                raise HTTPException(status_code=404, detail="Not Found")
            # 尝试返回根目录下的静态文件（如 favicon.ico）
            candidate = (dist_dir / full_path).resolve()
            dist_resolved = dist_dir.resolve()
            if str(candidate).startswith(str(dist_resolved) + "\\") and candidate.is_file():
                return FileResponse(str(candidate))
            # SPA history 模式：返回 index.html，由前端路由接管
            return FileResponse(str(dist_dir / "index.html"))

    return app


app = create_app()
