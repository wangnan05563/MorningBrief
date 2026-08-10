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
import os
import re
from contextlib import asynccontextmanager
from email.utils import formatdate
from pathlib import Path

from loguru import logger

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response


def _read_range_sync(full_path: str, start: int, content_length: int) -> bytes:
    """同步读取文件指定字节范围（供 async 上下文通过 asyncio.to_thread 调用，避免阻塞事件循环）。"""
    with open(full_path, "rb") as f:
        f.seek(start)
        return f.read(content_length)


class CORSStaticFiles(StaticFiles):
    """支持 Range 请求 + CORS 头的 StaticFiles 子类。

    用于 /audio 和 /bgm 路径，解决真机 BackgroundAudioManager 播放失败问题：
    1. 真机系统音频播放器需要 Range 请求支持（用于流式播放和 seek），
       Starlette StaticFiles 默认不支持 Range，导致 src:null errCode:0
    2. 开发者工具走 webview 受 CORS 限制，缺少头会 ERR_BLOCKED_BY_RESPONSE
    音频/封面属公开资源，允许跨域无安全风险；API 路径不受影响。
    """

    async def get_response(self, path: str, scope) -> Response:  # NOSONAR S3776: Range 请求分块响应逻辑不可再拆分
        # 优先处理 Range 请求：真机 BackgroundAudioManager 必须依赖 Range 才能流式播放
        # Starlette StaticFiles 不支持 Range，需自行实现 RFC 7233 分块响应
        request_headers = scope.get("headers", [])
        range_header = None
        for k, v in request_headers:
            if k.decode("latin-1").lower() == "range":
                range_header = v.decode("latin-1")
                break

        if range_header and range_header.startswith("bytes="):
            full_path = os.path.join(self.directory, path)
            if os.path.isfile(full_path):
                file_size = os.path.getsize(full_path)
                file_mtime = os.path.getmtime(full_path)
                # 解析 Range: bytes=start-end（end 可省略，表示到文件末尾）
                range_spec = range_header[6:].split(",")[0].strip()
                range_match = re.match(r"^(\d*)-(\d*)$", range_spec)
                if range_match:
                    start_str, end_str = range_match.groups()
                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else file_size - 1
                    # 边界保护：start 不超过文件大小，end 不超过文件末尾
                    start = min(start, file_size - 1)
                    end = min(end, file_size - 1)
                    if start <= end:
                        content_length = end - start + 1
                        content = await asyncio.to_thread(_read_range_sync, full_path, start, content_length)
                        # 206 Partial Content：满足 RFC 7233，真机播放器据此分块加载
                        response = Response(
                            content=content,
                            media_type=self._get_media_type(path),
                            status_code=206,
                        )
                        response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
                        response.headers["Accept-Ranges"] = "bytes"
                        response.headers["Content-Length"] = str(content_length)
                        response.headers["Access-Control-Allow-Origin"] = "*"
                        response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
                        response.headers["Access-Control-Allow-Headers"] = "Range"
                        response.headers["Access-Control-Expose-Headers"] = "Content-Range, Accept-Ranges"
                        # 缓存头：音频文件内容不可变（文件名含 workflow_id），
                        # 标记 immutable 让小程序网络栈与 Tailscale 边缘节点缓存，
                        # 二次播放可直接走缓存，减少 Funnel 中转回源
                        response.headers["Cache-Control"] = "public, max-age=86400, immutable"
                        response.headers["ETag"] = f'"{file_size}-{int(file_mtime)}"'
                        response.headers["Last-Modified"] = formatdate(file_mtime, usegmt=True)
                        return response

        # 非 Range 请求或文件不存在时走默认逻辑（含 404 处理）
        response = await super().get_response(path, scope)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        # 允许 Range 请求头：浏览器音频元素拖动进度条时会发送 Range 请求
        response.headers["Access-Control-Allow-Headers"] = "Range"
        response.headers["Access-Control-Expose-Headers"] = "Content-Range, Accept-Ranges"
        # 标记支持 Range：真机播放器据此决定是否发起分块请求
        response.headers["Accept-Ranges"] = "bytes"
        # 非 Range 请求也加缓存头：完整文件下载场景同样受益于缓存
        try:
            full_path = os.path.join(self.directory, path)
            if os.path.isfile(full_path):
                file_size = os.path.getsize(full_path)
                file_mtime = os.path.getmtime(full_path)
                response.headers["Cache-Control"] = "public, max-age=86400, immutable"
                response.headers["ETag"] = f'"{file_size}-{int(file_mtime)}"'
                response.headers["Last-Modified"] = formatdate(file_mtime, usegmt=True)
        except (OSError, ValueError):
            # 文件不存在或路径异常时跳过缓存头，不影响主流程
            pass
        return response

    def _get_media_type(self, path: str) -> str:
        """根据文件扩展名推断 MIME 类型，缺失时回退到 application/octet-stream。"""
        return mimetypes.guess_type(path)[0] or "application/octet-stream"

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
from app.middleware.path_prefix import PathPrefixMiddleware
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
from app.routers.api.comments import router as c_comments_router
from app.routers.api.channels import router as c_channels_router
from app.routers.api.subscriptions import router as c_subscriptions_router
from app.routers.api.users import router as c_users_router
from app.routers.api.cos import router as c_cos_router

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
# 关于页面（系统元信息 + 检查更新）
from app.routers.admin.about import router as b_about_router
# 数据库维护与系统清理模块（仅 admin）
from app.routers.admin.db_admin import router as b_db_admin_router
from app.routers.admin.maintenance import router as b_maintenance_router
# 自动审批模块（配置管理 + 统计 + 历史 + 重试）
from app.routers.admin.auto_review import router as b_auto_review_router
from app.routers.admin.backup import router as b_backup_router
# 通知管理（钉钉消息通知，仅 admin）
from app.routers.admin.notification import router as b_notification_router
from app.routers.admin.cos import router as b_cos_router
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


async def _seed_default_admin() -> None:  # NOSONAR
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


async def _migrate_channel_schema() -> None:  # NOSONAR
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
            ("bgm_gap_mode", "TEXT"),
            ("enable_thinking_question", "INTEGER"),
            ("rss_sources", "TEXT"),
            ("keywords", "TEXT"),
            ("min_duration_sec", "INTEGER"),
            # 展示排序权重：缓存命中判定以现有列集合为准，新增列需追加到此列表
            # NOT NULL DEFAULT 0 回填存量频道，避免 NULL 排序歧义
            ("display_order", "INTEGER NOT NULL DEFAULT 0"),
            # 频道级素材周期回溯天数：为空时回退 rewriter 动态值（3/7/14 天）
            ("material_lookback_days", "INTEGER"),
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


async def _migrate_material_schema() -> None:  # NOSONAR
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

async def _migrate_cover_url_column() -> None:  # NOSONAR
    """For material table migration: add cover_url column (idempotent).    SQLite create_all does not modify existing table structure.    cover_url stores the og:image cover URL for frontend segment images.    """
    import sqlite3
    from app.paths import resolve_db_path

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(material)")
        existing_cols = {row[1] for row in cur.fetchall()}

        if "cover_url" not in existing_cols:
            cur.execute("ALTER TABLE material ADD COLUMN cover_url VARCHAR(512)")
            conn.commit()
            logger.info("[startup] material migration done, added cover_url column")
    except Exception as e:
        logger.warning("[startup] material cover_url migration failed: %s", e)
    finally:
        conn.close()



async def _migrate_hls_url_columns() -> None:  # NOSONAR
    """为 episode / review 表追加 hls_url 列（幂等）。

    为什么单独迁移：SQLite create_all 不修改已存在表结构。
    hls_url 存放 HLS m3u8 清单 URL，配合小程序 BackgroundAudioManager.protocol='hls'
    实现分片流式播放。为空表示该节目未生成 HLS，客户端回退到 audio_url。
    """
    import sqlite3
    from app.paths import resolve_db_path

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        for table in ("episode", "review"):
            cur.execute(f"PRAGMA table_info({table})")
            existing_cols = {row[1] for row in cur.fetchall()}
            if "hls_url" not in existing_cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN hls_url TEXT")
                logger.info("[startup] {} 表迁移完成，新增 hls_url 列", table)
        conn.commit()
    except Exception as e:
        logger.warning("[startup] hls_url 列迁移失败: {}", e)
    finally:
        conn.close()


async def _migrate_review_auto_approve_columns() -> None:  # NOSONAR
    """为 review 表追加 auto_approved / auto_trigger_reason 列（幂等）。

    为什么单独迁移：SQLite create_all 不修改已存在表结构。
    新增列用于标记系统自动审批通过的记录，便于审批历史追溯与统计。
    - auto_approved: Boolean，True 表示系统自动审批
    - auto_trigger_reason: Text，JSON 字符串，记录命中的规则列表
    """
    import sqlite3
    from app.paths import resolve_db_path

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(review)")
        existing_cols = {row[1] for row in cur.fetchall()}
        if "auto_approved" not in existing_cols:
            # Boolean 在 SQLite 中存储为 0/1，与现有 status 字段模式一致
            cur.execute("ALTER TABLE review ADD COLUMN auto_approved BOOLEAN DEFAULT 0")
            logger.info("[startup] review 表迁移完成，新增 auto_approved 列")
        if "auto_trigger_reason" not in existing_cols:
            cur.execute("ALTER TABLE review ADD COLUMN auto_trigger_reason TEXT")
            logger.info("[startup] review 表迁移完成，新增 auto_trigger_reason 列")
        conn.commit()
    except Exception as e:
        logger.warning("[startup] review 自动审批列迁移失败: {}", e)
    finally:
        conn.close()


async def _migrate_playlog_indexes() -> None:  # NOSONAR
    """播放日志表索引迁移：为已存在的 play_log 表追加复合索引（幂等）。

    SQLite 的 create_all 不会为已存在的表新增索引，需显式 CREATE INDEX。

    两个索引分别优化 /recent 的两段查询：
    1. idx_user_played_at：WHERE user_id=? ORDER BY played_at DESC 的分页查询
    2. idx_user_episode_played_at：子查询 WHERE user_id=? GROUP BY episode_id
       MAX(played_at) 的覆盖索引，避免回表全表扫描
    压测显示该接口 P95 达 498ms，加索引后预期 <100ms。

    CREATE INDEX IF NOT EXISTS 天然幂等，无需额外检测。
    """
    import sqlite3
    from app.paths import resolve_db_path

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_play_log_idx_user_played_at "
            "ON play_log (user_id, played_at)"
        )
        # 覆盖索引：子查询 SELECT user_id, episode_id, MAX(played_at) 可完全走索引
        # 避免 GROUP BY 时的全表扫描，用户播放记录多时收益显著
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_play_log_user_episode_played_at "
            "ON play_log (user_id, episode_id, played_at)"
        )
        conn.commit()
        logger.info("[startup] play_log 表索引迁移完成（idx_user_played_at + idx_user_episode_played_at）")
    except Exception as e:
        logger.warning("[startup] play_log 表索引迁移失败: %s", e)
    finally:
        conn.close()


async def _migrate_fts5_index() -> None:  # NOSONAR
    """创建 FTS5 全文索引虚拟表并同步现有数据（幂等）。

    为什么用 FTS5：LIKE '%关键词%' 无法走索引，全表扫描。
    episode 表数据量增长后搜索接口 P95 显著上升。
    FTS5 是 SQLite 原生全文索引，支持 MATCH 查询，性能比 LIKE 高 10-100 倍。

    虚拟表结构：
    - episode_fts(title) 仅索引标题字段
    - content='episode' content_rowid='id' 映射到 episode 表主键

    同步策略：
    - 首次创建后用 INSERT ... SELECT 把现有 episode.title 灌入 FTS 表
    - 触发器在 episode INSERT/UPDATE/DELETE 时自动同步 FTS 表
    - 幂等：IF NOT EXISTS + 触发器名固定，重复执行不会报错
    """
    import sqlite3
    from app.paths import resolve_db_path

    db_path = str(resolve_db_path())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # 检查 SQLite 是否支持 FTS5（极少数精简编译可能未启用）
        try:
            cur.execute("SELECT fts5(NULL)")
        except Exception:
            logger.warning("[startup] SQLite 未启用 FTS5 扩展，搜索降级为 LIKE")
            return

        # 创建 FTS5 虚拟表（content 映射到 episode 表）
        cur.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS episode_fts "
            "USING fts5(title, content='episode', content_rowid='id')"
        )

        # 触发器：episode INSERT 后同步插入 FTS
        cur.execute(
            "CREATE TRIGGER IF NOT EXISTS episode_fts_ai AFTER INSERT ON episode "
            "BEGIN "
            "INSERT INTO episode_fts(rowid, title) VALUES (new.id, new.title); "
            "END"
        )
        # 触发器：episode DELETE 后同步删除 FTS
        cur.execute(
            "CREATE TRIGGER IF NOT EXISTS episode_fts_ad AFTER DELETE ON episode "
            "BEGIN "
            "INSERT INTO episode_fts(episode_fts, rowid, title) VALUES ('delete', old.id, old.title); "
            "END"
        )
        # 触发器：episode UPDATE 后同步更新 FTS
        cur.execute(
            "CREATE TRIGGER IF NOT EXISTS episode_fts_au AFTER UPDATE ON episode "
            "BEGIN "
            "INSERT INTO episode_fts(episode_fts, rowid, title) VALUES ('delete', old.id, old.title); "
            "INSERT INTO episode_fts(rowid, title) VALUES (new.id, new.title); "
            "END"
        )

        # 首次创建时灌入现有数据：检查 FTS 表是否为空
        cur.execute("SELECT COUNT(*) FROM episode_fts")
        fts_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM episode")
        ep_count = cur.fetchone()[0]
        if fts_count == 0 and ep_count > 0:
            cur.execute(
                "INSERT INTO episode_fts(rowid, title) "
                "SELECT id, title FROM episode"
            )
            logger.info(
                "[startup] FTS5 索引初始化完成，灌入 %d 条历史数据", ep_count
            )
        else:
            logger.info("[startup] FTS5 索引就绪（%d 条已索引）", fts_count)

        conn.commit()
    except Exception as e:
        logger.warning("[startup] FTS5 索引迁移失败: %s", e)
    finally:
        conn.close()


async def _seed_default_channels() -> None:  # NOSONAR
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


def _make_loop_exception_handler():
    """构造事件循环异常处理器，过滤 Windows Proactor 连接重置噪声。

    Windows asyncio ProactorEventLoop 在客户端（浏览器 audio 标签、Range 请求）
    提前关闭 TCP 连接时，_call_connection_lost 回调会抛 ConnectionResetError
    [WinError 10054]。这是 TCP 半关闭的正常行为，不属于服务端错误，但会被
    事件循环默认异常处理器以 ERROR 级别写入日志，污染监控并触发误告警。
    此处将其降级为 DEBUG 日志保留可观察性，其余异常走默认处理流程。

    过滤规则固定不配置化：WinError 10054 + ProactorBasePipeTransport 是
    Windows 平台 asyncio 的已知行为，配置开关只会增加运维负担而无业务价值。
    """
    def handler(loop, context):
        exception = context.get("exception")
        # 仅过滤 Windows Proactor 管道传输的连接重置：浏览器提前断开的已知噪声
        if isinstance(exception, ConnectionResetError):
            transport = context.get("transport")
            transport_cls = transport.__class__.__name__ if transport else ""
            if "ProactorBasePipeTransport" in transport_cls:
                logger.debug(
                    "忽略 Windows Proactor 连接重置（客户端提前关闭连接的已知行为）: %s",
                    context.get("message", ""),
                )
                return
        # 非过滤范围的异常走默认处理：确保真实错误仍被记录和告警
        loop.default_exception_handler(context)

    return handler


@asynccontextmanager
async def lifespan(app: FastAPI):  # NOSONAR S3776: 生命周期初始化含多步资源准备与异常兜底
    """应用生命周期：启动时初始化资源，关闭时清理。"""
    # 初始化日志系统（幂等：launcher.py 已提前调用则此处 no-op）
    # 覆盖直接 import app.main 的场景（如 pytest）
    try:
        from app.paths import resolve_log_dir
        log_dir = str(resolve_log_dir())
    except Exception:
        log_dir = settings.LOG_DIR
    setup_logging(log_level=settings.LOG_LEVEL, log_dir=log_dir)

    # 注册事件循环异常处理器：过滤浏览器提前断开连接导致的 WinError 10054 噪声
    # 必须在业务逻辑启动前注册，否则首个请求断开就会污染日志
    # 用 get_running_loop 而非 get_event_loop：lifespan 在事件循环内执行，前者更准确
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_make_loop_exception_handler())
    logger.info("[startup] 事件循环异常处理器已注册（过滤 Windows Proactor 连接重置噪声）")

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

    # material table cover_url column migration (idempotent)
    try:
        await _migrate_cover_url_column()
    except Exception as e:
        logger.warning("[startup] material cover_url migration failed: %s", e)


    # episode/review 表 hls_url 列迁移（幂等追加，用于 HLS 分片播放）
    try:
        await _migrate_hls_url_columns()
    except Exception as e:
        logger.warning("[startup] hls_url 列迁移失败: %s", e)

    # review 表 auto_approved / auto_trigger_reason 列迁移（幂等追加，用于自动审批标记）
    try:
        await _migrate_review_auto_approve_columns()
    except Exception as e:
        logger.warning("[startup] review 自动审批列迁移失败: %s", e)

    # play_log 表索引迁移（幂等追加 idx_user_played_at 复合索引，优化 /recent 查询）
    try:
        await _migrate_playlog_indexes()
    except Exception as e:
        logger.warning("[startup] play_log 表索引迁移失败: %s", e)

    # FTS5 全文索引迁移（幂等创建虚拟表 + 触发器 + 历史数据灌入）
    try:
        await _migrate_fts5_index()
    except Exception as e:
        logger.warning("[startup] FTS5 索引迁移失败: %s", e)

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

    # 从 SQLite 加载 COS 配置覆盖到 Settings 单例（前端「云端配置」页修改热生效）
    from app.services.cos_config_service import CosConfigService
    try:
        async with AsyncSessionLocal() as session:
            cos_svc = CosConfigService(session)
            await cos_svc.apply_config_to_settings()
    except Exception as e:
        logger.warning("[startup] 加载 COS 配置失败，使用 .env 默认值: %s", e)

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

    # 启动播放进度写缓冲的周期 flush（P1 优化：进程内聚合 + 定时批量落库）
    from app.services.play_write_buffer import play_write_buffer
    await play_write_buffer.start()

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

    # 停止播放进度写缓冲并执行最终 flush（先停，避免关闭后仍有事件入队）
    from app.services.play_write_buffer import play_write_buffer
    await play_write_buffer.stop()

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


def create_app() -> FastAPI:  # NOSONAR
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

    # 路径前缀重写：最后注册（LIFO 最外层最先执行），剥离 /news 前缀
    # 直接访问后端时浏览器按 Vite base='/news/' 请求 /news/admin/api/...，
    # 重写为 /admin/api/... 以命中后端路由（Funnel/Vite proxy 场景前缀已剥离，不受影响）
    app.add_middleware(PathPrefixMiddleware)

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
    app.include_router(c_comments_router)
    app.include_router(c_channels_router)
    app.include_router(c_subscriptions_router)
    app.include_router(c_users_router)
    # C 端 COS 直传（预签名上传）
    app.include_router(c_cos_router)

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
    app.include_router(b_auto_review_router)
    app.include_router(b_backup_router)
    # 通知管理（钉钉消息通知）
    app.include_router(b_notification_router)
    # 云端存储 COS 配置与管理
    app.include_router(b_cos_router)
    # 关于页面（系统元信息 + 检查更新）
    app.include_router(b_about_router)
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
    app.mount("/audio", CORSStaticFiles(directory=str(audio_dir)), name="audio")

    # 挂载 /bgm 静态目录：频道 BGM 文件（预制 + 用户上传），前端试听用
    # 目录与 paths.resolve_bgm_dir() 一致，开发态/打包态均自动创建
    try:
        from app.paths import resolve_bgm_dir
        bgm_dir = resolve_bgm_dir()
    except Exception:
        bgm_dir = Path("data/bgm")
    bgm_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/bgm", CORSStaticFiles(directory=str(bgm_dir)), name="bgm")

    # 挂载 /avatars 静态目录：C 端用户上传的头像图片
    # 用普通 StaticFiles 即可：头像图片无需 Range 请求支持（浏览器 <image> 直接整文件加载）
    # 路径与 paths.resolve_avatar_dir() 一致，开发态/打包态均自动创建目录
    try:
        from app.paths import resolve_avatar_dir
        avatar_dir = resolve_avatar_dir()
    except Exception:
        avatar_dir = Path("data/avatars")
    avatar_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/avatars", StaticFiles(directory=str(avatar_dir)), name="avatars")

    # 挂载前端 SPA（B 端运营后台）
    # 路径区分模式（Tailscale Funnel /news/ 前缀）下需同时支持两种访问：
    # 1. Funnel 转发：前缀已剥离，后端收到 /assets/x.js、/review 等原路径
    # 2. 直接访问后端：浏览器按 Vite base='/news/' 请求 /news/assets/x.js、/news/review
    # 因此 /assets 和 /news/assets 都需挂载，fallback 也需识别并剥离 /news/ 前缀
    dist_dir = resolve_admin_dist()
    if dist_dir and dist_dir.exists():
        # /assets 目录：JS/CSS/图片等静态资源（Vite 构建产物）
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
            # 路径区分模式：直接访问后端时浏览器按 base='/news/' 请求资源
            app.mount("/news/assets", StaticFiles(directory=str(assets_dir)), name="news_assets")

        # SPA history 模式 fallback：未匹配的 GET 请求返回 index.html
        # 必须在所有 API 路由之后注册，否则会覆盖 API 路由
        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str):
            # API 路径不 fallback，返回 404（避免 API 404 被误返回 index.html）
            # 同时识别带 /news/ 前缀的 API 路径（直接访问后端场景）
            if full_path.startswith(("api/", "admin/api/", "news/admin/api/")):
                raise HTTPException(status_code=404, detail="Not Found")
            # 剥离 /news/ 前缀：直接访问后端时浏览器按 base='/news/' 请求前端路由
            rel_path = full_path[5:] if full_path.startswith("news/") else full_path
            # 尝试返回根目录下的静态文件（如 favicon.ico、login/*.png）
            candidate = (dist_dir / rel_path).resolve()
            dist_resolved = dist_dir.resolve()
            if str(candidate).startswith(str(dist_resolved) + "\\") and candidate.is_file():
                return FileResponse(str(candidate))
            # SPA history 模式：返回 index.html，由前端路由接管
            return FileResponse(str(dist_dir / "index.html"))

    return app


app = create_app()
