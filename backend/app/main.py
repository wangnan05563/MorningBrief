"""
FastAPI 应用入口

单体应用架构：业务服务 + APScheduler + AI 工作流模块在同一进程内。
启动顺序：FastAPI 应用初始化 → 建表（首次启动）→ 注册异常处理 → 挂载路由 → 启动调度器。

V1.2 起：
- 数据库改为 SQLite（嵌入式，无需外部容器）
- 缓存改为进程内 TTLCache（无需外部 Redis）
- 启动时通过 SQLAlchemy Base.metadata.create_all 自动建表（开发态）
"""
import asyncio
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

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
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.paths import resolve_admin_dist
from app.routers.health import router as health_router
# C 端路由（小程序）
from app.routers.api.auth import router as c_auth_router
from app.routers.api.episodes import router as c_episodes_router
from app.routers.api.playlogs import router as c_playlogs_router
from app.routers.api.favorites import router as c_favorites_router
from app.routers.api.feedbacks import router as c_feedbacks_router
from app.routers.api.channels import router as c_channels_router
from app.routers.api.subscriptions import router as c_subscriptions_router
from app.routers.api.users import router as c_users_router

# B 端路由（运营后台）
from app.routers.admin.auth import router as b_auth_router
from app.routers.admin.reviews import router as b_reviews_router
from app.routers.admin.ads import router as b_ads_router
from app.routers.admin.stats import router as b_stats_router
from app.routers.admin.tunnel import router as b_tunnel_router
from app.routers.admin.workflows import router as b_workflows_router
from app.routers.admin.ai_config import router as b_ai_config_router
from app.routers.admin.channels import router as b_channels_router
from app.routers.admin.queue import router as b_queue_router
from app.routers.admin.materials import router as b_materials_router
from app.routers.admin.scripts import router as b_scripts_router
from app.routers.admin.audio import router as b_audio_router
from app.routers.admin.system import router as b_system_router
from app.routers.admin.events import router as b_events_router
from app.routers.admin.feedbacks import router as b_feedbacks_router
# 数据库维护与系统清理模块（仅 admin）
from app.routers.admin.db_admin import router as b_db_admin_router
from app.routers.admin.maintenance import router as b_maintenance_router
from app.routers.admin.backup import router as b_backup_router
# 通知管理（钉钉消息通知，仅 admin）
from app.routers.admin.notification import router as b_notification_router
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


async def _seed_default_admin() -> None:
    """首次启动自动 seed 默认 admin 用户（幂等）。

    解决 dev/exe 模式数据库路径不一致导致登录失败的问题：
    seed_admin.py 默认路径曾指向 dist/MorningBrief/data/news.db，
    与开发态运行时 backend/data/news.db 不一致。
    在 lifespan 中调用确保无论何种模式启动，admin 用户都被创建。
    """
    import sqlite3
    from app.paths import resolve_db_path
    from app.core.security import hash_password

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM admin_user WHERE username = ?', ('admin',))
        if cur.fetchone()[0] > 0:
            return
        cur.execute(
            'INSERT INTO admin_user (username, password_hash, role, status, nickname) VALUES (?, ?, ?, 1, ?)',
            ('admin', hash_password('admin123'), 'admin', 'Admin'),
        )
        conn.commit()
        logger.info("[startup] 默认 admin 用户已创建（admin/admin123）")
    finally:
        conn.close()


async def _migrate_channel_schema() -> None:
    """频道表结构迁移：为已存在的 channel 表追加新列（幂等）。

    SQLite 的 create_all 不会修改已存在表结构，新增字段需显式 ALTER TABLE。
    通过 PRAGMA table_info 检测列是否存在，已存在则跳过，实现幂等迁移。

    新增字段：schedule_time / intro_prompt / outro_prompt / constraint_prompt / rewrite_template
    """
    import sqlite3
    from app.paths import resolve_db_path

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        # PRAGMA table_info 返回 (cid, name, type, notnull, dflt_value, pk)
        cur.execute("PRAGMA table_info(channel)")
        existing_cols = {row[1] for row in cur.fetchall()}

        new_columns = [
            ("schedule_time", "TEXT"),
            ("intro_prompt", "TEXT"),
            ("outro_prompt", "TEXT"),
            ("constraint_prompt", "TEXT"),
            ("rewrite_template", "TEXT"),
            ("bgm_path", "TEXT"),
            ("bgm_volume", "REAL"),
            ("segment_gap_sec", "REAL"),
            ("enable_thinking_question", "INTEGER"),
            ("rss_sources", "TEXT"),
            ("keywords", "TEXT"),
        ]
        added = 0
        for col_name, col_type in new_columns:
            if col_name not in existing_cols:
                cur.execute(f"ALTER TABLE channel ADD COLUMN {col_name} {col_type}")
                added += 1
        if added > 0:
            conn.commit()
            logger.info("[startup] channel 表迁移完成，新增 %d 列", added)
    except Exception as e:
        logger.warning("[startup] channel 表迁移失败: %s", e)
    finally:
        conn.close()


async def _migrate_material_schema() -> None:
    """素材表结构迁移：为已存在的 material 表追加 channel_id 列（幂等）。

    SQLite 的 create_all 不会修改已存在表结构，新增字段需显式 ALTER TABLE。
    channel_id 用于频道级素材隔离：crawler 入库时写入频道 ID，rewriter 按频道选题。
    历史遗留数据 channel_id 为 NULL，rewriter 回退到全局素材池兼容旧数据。
    """
    import sqlite3
    from app.paths import resolve_db_path

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(material)")
        existing_cols = {row[1] for row in cur.fetchall()}

        if "channel_id" not in existing_cols:
            cur.execute("ALTER TABLE material ADD COLUMN channel_id INTEGER")
            conn.commit()
            logger.info("[startup] material 表迁移完成，新增 channel_id 列")
    except Exception as e:
        logger.warning("[startup] material 表迁移失败: %s", e)
    finally:
        conn.close()


async def _seed_default_channels() -> None:
    """首次启动自动 seed 默认频道（幂等）。

    调用 seed_channels.seed() 插入 8 个默认新闻频道，按 name 幂等。
    """
    import sqlite3
    from app.paths import resolve_db_path
    from seed_channels import DEFAULT_CHANNELS

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        inserted = 0
        for name, description in DEFAULT_CHANNELS:
            cur.execute('SELECT COUNT(*) FROM channel WHERE name = ?', (name,))
            if cur.fetchone()[0] > 0:
                continue
            cur.execute(
                'INSERT INTO channel (name, description, is_active) VALUES (?, ?, 1)',
                (name, description),
            )
            inserted += 1
        if inserted > 0:
            conn.commit()
            logger.info("[startup] 默认频道已 seed，新增 %d 个", inserted)
    finally:
        conn.close()


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

    # 自动 seed 默认 admin 用户（幂等，确保 dev/exe 模式均可登录）
    try:
        await _seed_default_admin()
    except Exception as e:
        logger.warning("[startup] 自动创建默认 admin 用户失败: %s", e)

    # channel 表结构迁移（幂等追加 schedule_time / prompt / rss_sources / keywords 字段）
    try:
        await _migrate_channel_schema()
    except Exception as e:
        logger.warning("[startup] channel 表迁移失败: %s", e)

    # material 表结构迁移（幂等追加 channel_id 字段，用于频道级素材隔离）
    try:
        await _migrate_material_schema()
    except Exception as e:
        logger.warning("[startup] material 表迁移失败: %s", e)

    # 自动 seed 默认频道（幂等，确保工作流监控页频道选项非空）
    try:
        await _seed_default_channels()
    except Exception as e:
        logger.warning("[startup] 自动 seed 默认频道失败: %s", e)

    # 从 SQLite 加载 AI 配置覆盖到 Settings 单例（前端修改的配置热生效）
    from app.services.ai_config_service import AIConfigService
    from app.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as session:
            svc = AIConfigService(session)
            await svc.apply_config_to_settings()
    except Exception as e:
        logger.warning("[startup] 加载 AI 配置失败，使用 .env 默认值: %s", e)

    # 初始化通知预设模板（幂等：已存在的 event_type 跳过）
    # 与 AI 配置同一 session，避免重复创建连接
    try:
        from app.services.notification.template_service import TemplateService
        async with AsyncSessionLocal() as session:
            tpl_svc = TemplateService(session)
            inserted = await tpl_svc.seed_preset_templates()
            if inserted > 0:
                logger.info("[startup] 通知预设模板已 seed，新增 %d 条", inserted)
    except Exception as e:
        logger.warning("[startup] 通知预设模板初始化失败: %s", e)

    # 启动 APScheduler 定时任务（工作流调度 + 播放日志落库 + 黑名单清理）
    from app.services.workflow_scheduler import workflow_scheduler
    await workflow_scheduler.start()

    # 启动 EventBus 后台消费任务（工作流状态事件分发）
    # create_task 保留引用到 app.state，避免被 GC 回收导致任务中途取消
    from app.core.event_bus import get_event_bus
    event_bus = get_event_bus()
    app.state.event_bus_task = asyncio.create_task(event_bus.run_forever())
    logger.info("[startup] EventBus 已启动")

    # 内网穿透：注入 on_started 回调，隧道启动成功后发送通知
    # 用 daemon 线程而非 asyncio：cloudflared/cpolar 是阻塞子进程，线程不占用事件循环
    from app.services.tunnel_service import get_tunnel_service, set_tunnel_service, TunnelService
    from app.services.tunnel_notifications import notify_tunnel_started, notify_autostart_failed
    try:
        # 注入带通知回调的 TunnelService 实例
        tunnel_svc = TunnelService(on_started=notify_tunnel_started)
        set_tunnel_service(tunnel_svc)
        cfg = tunnel_svc.get_config()
        if cfg.get("auto_start"):
            import threading

            def _auto_start_tunnel():
                try:
                    url = tunnel_svc.start()
                    logger.info("[startup] 内网穿透隧道已自动启动: %s", url)
                except Exception as e:
                    # 自动启动失败不影响主服务：日志 + 通知双保障
                    logger.warning("[startup] 内网穿透自动启动失败: %s", e)
                    notify_autostart_failed(str(e))

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

    # 停止 EventBus：设置 _running=False，run_forever 下次轮询时退出
    from app.core.event_bus import get_event_bus
    get_event_bus().stop()
    event_bus_task = getattr(app.state, "event_bus_task", None)
    if event_bus_task:
        await asyncio.wait_for(event_bus_task, timeout=2.0)
    logger.info("[shutdown] EventBus 已停止")

    from app.database import engine
    await engine.dispose()
    logger.info("[shutdown] SQLite 引擎已释放")


def create_app() -> FastAPI:
    """应用工厂，便于测试时创建独立实例。"""
    app = FastAPI(
        title="MorningBrief 语音新闻播报 API",
        version="1.0.0",
        description="全自动 AI 内容生产工作流 + 微信小程序播报服务",
        docs_url="/docs" if settings.is_dev else None,
        redoc_url="/redoc" if settings.is_dev else None,
        lifespan=lifespan,
    )

    # RequestId 中间件：为每个请求注入全局流水号，贯穿全部日志
    app.add_middleware(RequestIdMiddleware)

    # 限流中间件：按客户端 IP 滑动窗口限流，防止恶意刷接口
    # 注册在 RequestId 之后（LIFO 后注册先执行）：限流前先有 request_id 便于日志关联
    app.add_middleware(RateLimitMiddleware)

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
    app.include_router(c_favorites_router)
    app.include_router(c_feedbacks_router)
    app.include_router(c_channels_router)
    app.include_router(c_subscriptions_router)
    app.include_router(c_users_router)

    # B 端（运营后台）
    app.include_router(b_auth_router)
    app.include_router(b_reviews_router)
    app.include_router(b_ads_router)
    app.include_router(b_stats_router)
    app.include_router(b_tunnel_router)
    app.include_router(b_workflows_router)
    app.include_router(b_ai_config_router)
    app.include_router(b_channels_router)
    app.include_router(b_queue_router)
    app.include_router(b_materials_router)
    app.include_router(b_scripts_router)
    app.include_router(b_audio_router)
    app.include_router(b_system_router)
    app.include_router(b_events_router)
    app.include_router(b_feedbacks_router)
    app.include_router(b_db_admin_router)
    app.include_router(b_maintenance_router)
    app.include_router(b_backup_router)
    # 通知管理（钉钉消息通知）
    app.include_router(b_notification_router)
    # 内部（工作流调度）
    app.include_router(internal_workflow_router)

    # 挂载 /audio 静态目录：TTS 本地存储回退的音频文件（COS 未配置时使用）
    # 路径与 uploader._local_root() 一致，开发态/打包态均自动创建目录
    try:
        from app.paths import resolve_data_dir
        audio_dir = Path(resolve_data_dir()) / "audio_cache"
    except Exception:
        audio_dir = Path("data/audio_cache")
    audio_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")

    # 挂载 /bgm 静态目录：频道 BGM 文件（预制 + 用户上传），前端试听用
    # 目录与 paths.resolve_bgm_dir() 一致，开发态/打包态均自动创建
    try:
        from app.paths import resolve_bgm_dir
        bgm_dir = resolve_bgm_dir()
    except Exception:
        bgm_dir = Path("data/bgm")
    bgm_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/bgm", StaticFiles(directory=str(bgm_dir)), name="bgm")

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
