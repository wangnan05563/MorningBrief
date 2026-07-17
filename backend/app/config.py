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
    # 初始 admin 密码：为空时启动自动生成随机密码并打印到日志，避免硬编码弱密码
    ADMIN_INITIAL_PASSWORD: str = ""
    # 音频/封面等静态资源的对外访问基础 URL
    # 留空时回退到 http://localhost:8000（仅开发工具可用）
    # 真机测试需设为电脑局域网 IP，如 http://10.232.253.113:8000
    AUDIO_BASE_URL: str = ""

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
    ALIYUN_TTS_APPKEY: str = ""
    ALIYUN_TTS_VOICE: str = "xiaoyun"
    ALIYUN_TTS_SAMPLE_RATE: int = 44100
    ALIYUN_TTS_FORMAT: str = "mp3"
    ALIYUN_TTS_TIMEOUT_SEC: int = 60
    # 音量/语速/基频调节（NLS tts_request 参数）
    # volume: [0, 100]，默认 50；speech_rate/pitch_rate: [-500, 500]，默认 0
    ALIYUN_TTS_VOLUME: int = 50
    ALIYUN_TTS_SPEECH_RATE: int = 0
    ALIYUN_TTS_PITCH_RATE: int = 0
    TTS_RETRY_ATTEMPTS: int = 3

    # ---- TTS Provider 选择（前端可在 ai_config 表覆盖） ----
    # 可选值：aliyun / edge / tencent；edge 为微软免费方案，无需 API Key
    TTS_PROVIDER: str = "aliyun"

    # ---- Edge-TTS（微软免费方案，无需 API Key） ----
    EDGE_TTS_VOICE: str = "zh-CN-XiaoxiaoNeural"
    EDGE_TTS_RATE: str = ""         # 语速调节，如 "+10%" / "-10%"
    EDGE_TTS_VOLUME: str = ""       # 音量调节，如 "+20%" / "-10%"
    EDGE_TTS_PITCH: str = ""        # 基频调节，如 "+5Hz" / "-3Hz"

    # ---- 腾讯云 TTS（基础语音合成 TextToVoice） ----
    # 凭证 fallback 到 COS_SECRET_ID/SECRET_KEY（项目已用 COS 可复用）
    TENCENT_TTS_SECRET_ID: str = ""
    TENCENT_TTS_SECRET_KEY: str = ""
    TENCENT_TTS_REGION: str = "ap-guangzhou"
    TENCENT_TTS_VOICE_TYPE: int = 101011
    TENCENT_TTS_VOLUME: int = 0     # 音量 [-10, 10]，0 为默认
    TENCENT_TTS_SPEED: int = 0      # 语速 [-2, 6]，0 为默认

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
    # 钉钉群机器人 Webhook + 加签密钥
    ALERT_DINGTALK_WEBHOOK: str = ""
    ALERT_DINGTALK_SECRET: str = ""
    # 邮件 SMTP（运维告警存档用）
    ALERT_EMAIL_SMTP_HOST: str = ""
    ALERT_EMAIL_SMTP_PORT: int = 587
    ALERT_EMAIL_SMTP_USER: str = ""
    ALERT_EMAIL_SMTP_PASSWORD: str = ""
    ALERT_EMAIL_TO: str = ""

    # ---- 工作流调度 ----
    WORKFLOW_CRON_HOUR: int = 5
    WORKFLOW_BACKUP_CHECK_HOUR: int = 6
    WORKFLOW_BACKUP_CHECK_MINUTE: int = 30
    WORKFLOW_LOCK_TTL_SEC: int = 1800

    # ---- 节目时长控制 ----
    # 目标节目时长（秒），默认 10 分钟。与稿件字数呈反向关联：
    # 时长增大 → 所需字数增多；时长减小 → 所需字数减少
    # rewriter 按此时长 + TTS 实际语速反算所需字数，动态调整段数与每段字数
    TARGET_DURATION_SEC: int = 600

    # ---- 背景音乐（BGM）配置 ----
    # BGM 文件路径：绝对路径或相对项目根目录的路径。文件不存在时降级为无 BGM 模式
    # （仅插入段间静音过渡，不叠加背景音）
    # 推荐使用节奏舒缓、无明显旋律的轻音乐，避免与新闻内容冲突
    BGM_PATH: str = "assets/bgm.mp3"
    # BGM 主音量（0.0-1.0）：TTS 播报期间的垫底音量，建议 0.10-0.20
    # TTS 段间 0.5s 静音过渡处 BGM 自然浮现，形成衔接节奏感
    BGM_VOLUME: float = 0.15
    # TTS 段间过渡时长（秒）：段与段之间插入的静音长度，BGM 在此时段显现
    SEGMENT_GAP_SEC: float = 0.5

    # ---- 爬虫配置 ----
    # 去重表保留天数：3 天后过期，允许爬虫重新爬取同源新闻
    # 原值 7 天对"删除工作流后重跑"场景偏长，3 天覆盖一个工作日周期足够
    CRAWLER_DEDUP_TTL_DAYS: int = 3
    CRAWLER_QPS_DEFAULT: int = 1
    CRAWLER_USER_AGENT: str = "MorningBriefBot/1.0"

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"             # V1.2：改为 exe 同级相对路径

    # ---- API 限流（对标 17_xianyu anti_detect 滑动窗口） ----
    # 每分钟全局请求上限，防止恶意刷接口触发工作流
    RATE_LIMIT_PER_MINUTE: int = 120
    # internal 路由鉴权 token（空字符串时仅校验 localhost，配置后双因素校验）
    INTERNAL_API_TOKEN: str = ""

    # ---- AI 预算控制（对标 17_xianyu ai_usage.py） ----
    # 每日 LLM token 上限（input+output 合计），超限拒绝调用
    AI_BUDGET_DAILY_TOKEN_LIMIT: int = 500000
    # 每日费用上限（USD），超限拒绝调用
    AI_BUDGET_DAILY_COST_LIMIT_USD: float = 5.0
    # 每分钟最大调用次数（按 service_type 分桶，LLM/TTS 各自独立限流）
    # 默认 60 对齐通义千问 qwen-max dashscope 默认 RPM 限制
    AI_BUDGET_RATE_LIMIT_PER_MIN: int = 60
    # 预算持久化文件路径（服务重启后回填今日记录）
    AI_BUDGET_FILE: str = "./data/ai_budget.json"

    # ---- 数据库维护模块（V1.2 新增，对标 17_xianyu db_admin） ----
    # 危险操作确认令牌：删除/批量删除/导入须传此值，防止误操作
    # 默认空字符串，空值时拒绝执行危险操作（须配置后才能使用 db_admin 危险操作）
    DB_ADMIN_CONFIRM_TOKEN: str = ""
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
