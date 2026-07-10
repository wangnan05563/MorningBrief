"""应用配置管理（V1.2：SQLite + TTLCache 替代 MySQL + Redis）。

使用 pydantic-settings 从环境变量加载配置，统一入口避免散落的 os.getenv 调用。
按职责分组，便于维护时定位配置项。
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，字段与 backend/.env.example 一一对应。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 应用配置 ----
    APP_ENV: str = "production"
    APP_DEBUG: bool = False
    APP_HOST: str = "127.0.0.1"          # V1.2：单机部署仅监听本地
    APP_PORT: int = 8000
    APP_TIMEZONE: str = "Asia/Shanghai"

    # ---- SQLite 数据库（V1.2 替代 MySQL） ----
    # 路径策略：开发态用相对路径 ./data/news.db；
    #   打包后由 app/paths.py.resolve_db_path() 解析为 exe 同级 ./data/news.db
    SQLITE_DB_PATH: str = "./data/news.db"
    SQLITE_JOURNAL_MODE: str = "WAL"     # WAL 模式：读不阻塞写
    SQLITE_BUSY_TIMEOUT_MS: int = 5000   # 写冲突时自动等待 5 秒
    SQLITE_SYNCHRONOUS: str = "NORMAL"   # NORMAL：性能与持久性平衡（WAL 下安全）

    # ---- 缓存（V1.2 替代 Redis，进程内 TTLCache 无需外部配置） ----
    CACHE_DEFAULT_TTL_SEC: int = 300     # 默认 TTL 5 分钟
    CACHE_MAXSIZE: int = 10000           # 单桶最大条目数

    # ---- JWT ----
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7          # C 端 token 有效期
    JWT_ADMIN_EXPIRE_HOURS: int = 2   # B 端 token 有效期
    # V1.2：C 端黑名单通过 COS 对象共享（SCF 读取），B 端黑名单写本地 SQLite
    JWT_BLACKLIST_COS_PREFIX: str = "jwt_blacklist/"
    JWT_BLACKLIST_CACHE_TTL_SEC: int = 300

    # ---- 微信小程序 ----
    WX_APPID: str = ""
    WX_SECRET: str = ""

    # ---- 通义千问 LLM API ----
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL: str = "qwen-max"
    LLM_TIMEOUT_SEC: int = 30
    LLM_RETRY_ATTEMPTS: int = 3

    # ---- 阿里云 TTS API ----
    ALIYUN_TTS_API_KEY: str = ""
    ALIYUN_TTS_VOICE: str = "xiaoyun"
    ALIYUN_TTS_SAMPLE_RATE: int = 44100
    ALIYUN_TTS_FORMAT: str = "mp3"
    ALIYUN_TTS_TIMEOUT_SEC: int = 60
    TTS_RETRY_ATTEMPTS: int = 3

    # ---- 腾讯云 COS（对象存储 + C 端 API 共享层） ----
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_REGION: str = "ap-guangzhou"
    COS_BUCKET: str = ""
    COS_CDN_DOMAIN: str = ""

    # ---- 云函数 SCF（V1.2 新增：C 端 5 个接口承载层） ----
    SCF_REGION: str = "ap-guangzhou"
    SCF_NAMESPACE: str = "default"
    SCF_RUNTIME: str = "Python3.9"
    SCF_MEMORY_MB: int = 512
    SCF_TIMEOUT_SEC: int = 30

    # ---- 告警通知 ----
    ALERT_SMS_ACCESS_KEY: str = ""
    ALERT_SMS_SECRET_KEY: str = ""
    ALERT_SMS_SIGN_NAME: str = ""
    ALERT_SMS_TEMPLATE_CODE: str = ""
    ALERT_SMS_PHONE: str = ""
    ALERT_WECOM_WEBHOOK: str = ""

    # ---- 工作流调度 ----
    WORKFLOW_CRON_HOUR: int = 5
    WORKFLOW_BACKUP_CHECK_HOUR: int = 6
    WORKFLOW_BACKUP_CHECK_MINUTE: int = 30
    WORKFLOW_LOCK_TTL_SEC: int = 1800

    # ---- 爬虫配置 ----
    CRAWLER_DEDUP_TTL_DAYS: int = 7
    CRAWLER_QPS_DEFAULT: int = 1
    CRAWLER_USER_AGENT: str = "20NewsBot/1.0"

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"             # V1.2：改为 exe 同级相对路径

    # ---- 数据库维护模块（V1.2 新增，对标 17_xianyu db_admin） ----
    # 危险操作确认令牌：删除/批量删除/导入须传此值，防止误操作
    DB_ADMIN_CONFIRM_TOKEN: str = "CONFIRM_DELETE"
    # 单次查询/批量删除行数上限，防止全表扫描 OOM
    DB_ADMIN_MAX_PAGE_SIZE: int = 1000
    # 单次导入行数上限，防止大文件解析阻塞事件循环
    DB_ADMIN_MAX_IMPORT_ROWS: int = 5000
    # 审计日志查询上限
    DB_ADMIN_AUDIT_LOG_LIMIT: int = 500

    # ---- 系统清理模块（V1.2 新增，对标 17_xianyu maintenance） ----
    # 旧 JWT 黑名单保留天数（过期后可清理）
    MAINTENANCE_BLACKLIST_RETAIN_DAYS: int = 7
    # 旧爬虫去重记录保留天数
    MAINTENANCE_DEDUP_RETAIN_DAYS: int = 7
    # 旧 AI 用量日志保留天数（统计价值低，按月清理）
    MAINTENANCE_AI_USAGE_RETAIN_DAYS: int = 90
    # 旧播放日志保留天数（统计价值递减，按季清理）
    MAINTENANCE_PLAYLOG_RETAIN_DAYS: int = 90
    # 大日志文件阈值（MB），超限可清理
    MAINTENANCE_LARGE_LOG_MB: int = 10

    # ---- 派生属性 ----
    @property
    def sqlite_url(self) -> str:
        """SQLAlchemy 异步 SQLite DSN（aiosqlite 驱动）。

        路径解析优先用 paths.py（区分打包态/开发态），
        回退到 SQLITE_DB_PATH 配置项。
        """
        try:
            from app.paths import resolve_db_path
            db_path = str(resolve_db_path())
        except Exception:
            # 测试或 paths.py 不可用时回退到配置值
            db_path = self.SQLITE_DB_PATH
        # aiosqlite 驱动要求路径前加 /
        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取 .env 文件。"""
    return Settings()
