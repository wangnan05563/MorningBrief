"""
应用配置管理

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
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_TIMEZONE: str = "Asia/Shanghai"

    # ---- MySQL ----
    MYSQL_HOST: str = "mysql"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "news_db"
    MYSQL_USER: str = "news_app"
    MYSQL_PASSWORD: str = ""
    MYSQL_ROOT_PASSWORD: str = ""
    MYSQL_POOL_SIZE: int = 20
    MYSQL_POOL_RECYCLE: int = 3600

    # ---- Redis ----
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # ---- JWT ----
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7          # C 端 token 有效期
    JWT_ADMIN_EXPIRE_HOURS: int = 2   # B 端 token 有效期

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

    # ---- 腾讯云 COS ----
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_REGION: str = "ap-guangzhou"
    COS_BUCKET: str = ""
    COS_CDN_DOMAIN: str = ""

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
    LOG_DIR: str = "/app/logs"

    # ---- 派生属性 ----
    @property
    def mysql_dsn(self) -> str:
        """SQLAlchemy 异步 MySQL DSN（aiomysql 驱动，纯 Python 无需 C 编译）。"""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL。"""
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取 .env 文件。"""
    return Settings()
