"""应用配置管理（V1.2：SQLite + TTLCache 替代 MySQL + Redis）。

使用 pydantic-settings 从环境变量加载配置，统一入口避免散落的 os.getenv 调用。
按职责分组，便于维护时定位配置项。
"""
import socket
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> str:
    """运行时解析 .env 路径，兼容开发态与打包态。

    旧逻辑用 Path(__file__).resolve().parent.parent / ".env" 拼绝对路径。
    打包（PyInstaller）后 __file__ 指向 _MEIPASS 临时解压目录，
    该目录不存在 .env，导致打包态下所有配置项（含 WX_APPID/WX_SECRET）
    全部走默认值空字符串，表现为小程序微信登录报 "appid missing"。

    修复：打包态改为读 exe 同级目录的 .env（dist/MorningBrief/.env 或安装目录），
    与 app/paths.py 的 resolve_env_path() 语义一致；开发态仍读 backend/.env。
    """
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).parent / ".env")
    return str(Path(__file__).resolve().parent.parent / ".env")


def detect_lan_ip() -> str:
    """通过 UDP socket 探测本机局域网 IP（不实际发送数据包）。

    原理：UDP connect 不发起握手，仅更新 socket 的本地路由表，
    从而拿到出口网卡的 IP。比 gethostbyname(gethostname()) 更可靠，
    后者在 Windows 上常返回 127.0.0.1 或虚拟网卡 IP。

    失败时回退到 127.0.0.1，保证开发工具内可用。
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 8.8.8.8 是 Google DNS，仅用于路由查询，不会真正发包
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        # 排除回环地址，没有有效局域网 IP 时回退
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        # 无网络环境（离线开发）会抛 OSError，忽略并回退
        pass
    return "127.0.0.1"


def get_all_lan_ips() -> list[str]:
    """获取本机所有 IPv4 地址（排除回环、Tailscale、APIPA）。

    用于真机调试模式：后端通过 /api/health 暴露所有局域网 IP，
    小程序从 Tailscale 引导地址拉取后加入候选，实现自动发现。

    排除规则：
    - 127.x.x.x：回环地址
    - 100.64-127.x.x.x：Tailscale CGNAT 段，真机通常不可达
    - 169.254.x.x：APIPA 自动配置地址（无 DHCP 时分配）
    """
    ips: set[str] = set()
    # 方式 1：getaddrinfo 获取 hostname 绑定的所有 IP
    # Windows 上通常能返回所有网卡的 IP
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    # 方式 2：UDP connect 获取默认路由出口 IP（补充方式 1 可能遗漏的网卡）
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
        finally:
            s.close()
    except OSError:
        pass

    def _is_lan_ip(ip: str) -> bool:
        """过滤回环、Tailscale CGNAT、APIPA 地址。"""
        if ip.startswith("127."):
            return False
        if ip.startswith("169.254."):
            return False
        # Tailscale CGNAT 段：100.64.0.0 - 100.127.255.255
        if ip.startswith("100."):
            parts = ip.split(".")
            if len(parts) == 4:
                try:
                    second = int(parts[1])
                    if 64 <= second <= 127:
                        return False
                except ValueError:
                    pass
        return True

    return [ip for ip in ips if _is_lan_ip(ip)]


class Settings(BaseSettings):
    """全局配置，字段与 backend/.env.example 一一对应。"""

    model_config = SettingsConfigDict(
        # .env 路径运行时解析：开发态读 backend/.env，打包态读 exe 同级 .env。
        # 避免依赖 CWD，且修复打包态下 __file__ 指向 _MEIPASS 临时目录导致
        # .env 加载不到、WX_APPID 等配置落空的问题（见 _resolve_env_file）。
        env_file=_resolve_env_file(),
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
    # 项目仓库地址（用于检查更新），留空时不检查更新
    REPO_URL: str = ""

    # ---- SQLite 数据库（V1.2 替代 MySQL） ----
    # 路径策略：开发态用相对路径 ./data/news.db；
    #   打包后由 app/paths.py.resolve_db_path() 解析为 exe 同级 ./data/news.db
    SQLITE_DB_PATH: str = "./data/news.db"
    SQLITE_JOURNAL_MODE: str = "WAL"     # WAL 模式：读不阻塞写
    # 写冲突时自动等待时间（毫秒）。
    # P1 安全网：P0-1 已用全局写锁把应用层提交串行化，正常不会出现并发写竞争；
    # 此处保留合理余量，兜底极端场景（如启动迁移/后台落库与请求写短暂重叠）下的 BUSY 等待，
    # 避免瞬时 BUSY 直接报错。过长会掩盖真实死锁，10s 是安全上限。
    SQLITE_BUSY_TIMEOUT_MS: int = 10000  # 写冲突时自动等待 10 秒（原 5000）
    SQLITE_SYNCHRONOUS: str = "NORMAL"   # NORMAL：性能与持久性平衡（WAL 下安全）

    # ---- 水平扩展（只读场景） ----
    # uvicorn worker 数。默认 1：单进程事件循环 + 进程内写锁 + 进程内 TTLCache，
    # 三者强耦合，workers>1 会破坏"全局写锁串行化"与"缓存一致性"（各 worker 独立缓存/锁）。
    # 因此 workers>1 仅在【纯读 / 几乎无写】或已切换到 MySQL+Redis 共享态（见架构决策）时安全。
    # 当前默认 1；如需读扩展，请同步将缓存/写锁改为 Redis/分布式锁后再调大。
    UVICORN_WORKERS: int = 1

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
    # 微信公众平台 API（jscode2session / cgi-bin/token / msg_sec_check）
    # 仅在微信变更域名时才需修改，默认值对齐官方文档
    WX_API_BASE: str = "https://api.weixin.qq.com"

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
    # 阿里云 NLS 网关地址（异步长文本 TTS 入口）
    # 仅在阿里云变更域名/区域时才需修改，默认值对齐 NLS 官方文档
    ALIYUN_TTS_ENDPOINT: str = "https://nls-gateway.cn-shanghai.aliyuncs.com/rest/v1/tts/async"
    # 音量/语速/基频调节（NLS tts_request 参数）
    # volume: [0, 100]，默认 50；speech_rate/pitch_rate: [-500, 500]，默认 0
    ALIYUN_TTS_VOLUME: int = 50
    ALIYUN_TTS_SPEECH_RATE: int = 0
    ALIYUN_TTS_PITCH_RATE: int = 0
    TTS_RETRY_ATTEMPTS: int = 3

    # ---- TTS Provider 选择（前端可在 ai_config 表覆盖） ----
    # 可选值：aliyun / edge / tencent / kokoro / piper
    # - edge：微软免费方案，无需 API Key（云端，需联网）
    # - kokoro：Apache 2.0 本地离线神经网络 TTS，免费高质量，需 pip install kokoro misaki[zh]
    # - piper：MIT 本地离线轻量 TTS，免费，需 pip install piper-tts + 下载语音模型
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
    # 腾讯云 TTS 服务 endpoint（云 API 3.0 入口）
    # 仅在腾讯云变更域名时才需修改，默认值对齐官方文档
    TENCENT_TTS_ENDPOINT: str = "https://tts.tencentcloudapi.com/"

    # ---- Kokoro TTS（Apache 2.0 本地离线神经网络 TTS，免费高质量） ----
    # 启用需：pip install kokoro misaki[zh]（中文 G2P），首次使用会从 HuggingFace
    # 下载模型权重（中文 ~165MB），之后完全离线。详见 requirements-tts-extra.txt
    # 语言代码：z=中文普通话 / a=美式 / b=英式 / e=西 / f=法 / h=印地 / i=意 / j=日 / p=葡
    KOKORO_LANG: str = "z"
    # 音色 ID（须与 lang 匹配）：z 系 zf_*(女)/zm_*(男)，如 zf_xiaoxiao(新闻女声)
    KOKORO_VOICE: str = "zf_xiaoxiao"
    # 语速倍率（>1 加快，<1 减慢），0 视为默认 1.0
    KOKORO_SPEED: float = 1.0

    # ---- Piper TTS（MIT 本地离线轻量 TTS，免费） ----
    # 启用需：pip install piper-tts，并下载语音模型（python -m piper.download_voices <voice>）
    # 模型为 .onnx + .onnx.json 文件，置于 PIPER_VOICE_DIR 目录
    # 中文推荐：zh_CN-huayan-medium（女声，22050Hz）
    PIPER_VOICE: str = "zh_CN-huayan-medium"
    # 模型文件目录（含 {PIPER_VOICE}.onnx 与 .onnx.json），相对/绝对路径皆可
    PIPER_VOICE_DIR: str = "./models/piper"
    # 语速（length_scale，>1 变慢，<1 变快），0 视为默认 1.0
    PIPER_LENGTH_SCALE: float = 1.0
    # 音量 [0, 1]，0 视为默认 0.5
    PIPER_VOLUME: float = 0.5
    # 音色随机性（noise_scale），影响自然度，默认 0.667
    PIPER_NOISE_SCALE: float = 0.667

    # ---- TTS 交叉音色（段落间轮流换声，避免同质化） ----
    # JSON 字符串：{"enabled": bool, "strategy": "round_robin"|"random"|"interval",
    # "interval": int, "voices": {provider: [voice_key, ...]}}
    # 仅 edge/aliyun/tencent/kokoro 支持多音色；piper 为单说话人模型，交叉音色不生效（参数被忽略）。
    TTS_CROSS_VOICE: str = "{}"

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

    # ---- 播放统计 ----
    # 播放计数阈值（秒）：用户收听超过此值才计入 play_count，避免误触点击也算播放量
    # 30 秒阈值覆盖用户切歌/试听前几秒退出的场景，是真实收听意图的最低门槛
    PLAY_COUNT_THRESHOLD_SEC: int = 30

    # ---- 音频码率配置 ----
    # 语音播报场景 64kbps 已足够（MP3 单声道 44100Hz），128kbps 是音乐标准过度
    # 64k 相比 128k 文件体积减半，下载时间减半，对 Tailscale Funnel 链路收益显著
    # 如需提升音质可调高至 96k 或 128k
    AUDIO_BITRATE: str = "64k"

    # ---- HLS 分片配置（V1.3 新增） ----
    # 开启后拼接阶段会同步生成 m3u8 + ts 分片，小程序设置 protocol='hls' 可分片流式播放，
    # 首字延迟从 mp3 整文件下载的 300-1000ms 降到 200-500ms（仅需下载首个 ts 分片）
    # 关闭时仅生成 mp3，小程序回退到 audio_url 播放
    HLS_ENABLE: bool = True
    # 单分片时长（秒）：HLS 规范推荐 6-10s，过短分片数过多元数据开销大，过长首字延迟增加
    # 10 分钟节目 + 6s 分片 = 100 个 ts，元数据占比约 2%
    HLS_SEGMENT_SEC: int = 6
    # HLS 播放列表类型：vod（点播，固定时长）/ event（直播事件，分片只增不删）
    # 节目是固定时长的录音，用 vod 让播放器支持任意 seek
    HLS_PLAYLIST_TYPE: str = "vod"

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
    # 段间 BGM 模式（全局默认，频道可覆盖）：
    #   "silence" = 段间真实静音（停顿可感知，推荐）；"bridge" = 段间 BGM 桥接（旧版行为）
    BGM_GAP_MODE: str = "silence"

    # ---- 爬虫配置 ----
    # 去重表保留天数：3 天后过期，允许爬虫重新爬取同源新闻
    # 原值 7 天对"删除工作流后重跑"场景偏长，3 天覆盖一个工作日周期足够
    CRAWLER_DEDUP_TTL_DAYS: int = 3
    CRAWLER_QPS_DEFAULT: int = 1
    CRAWLER_USER_AGENT: str = "MorningBriefBot/1.0"
    # 文章最大年龄（天）：published_at 超过此值的 entries 视为历史存量并过滤
    # 背景：部分 RSS 源（如人民网 ent/culture）更新缓慢，长期返回 1-3 年前的历史文章，
    # 首次入库后 dedup 锁住 URL，导致后续爬取 0 入库（wf-20260728-0011 故障根因）。
    # 过滤后若 0 条则降级保留全部（避免阻断），并 WARNING 告警提示源质量问题
    CRAWLER_MAX_ARTICLE_AGE_DAYS: int = 14

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"             # V1.2：改为 exe 同级相对路径

    # ---- FFmpeg 依赖 ----
    # BtbN/FFmpeg-Builds 共享构建下载源（gpl-shared，含 ffmpeg.exe/ffprobe.exe + DLL）
    # 大陆访问 GitHub 较慢时可切换镜像源
    FFMPEG_DOWNLOAD_URL: str = (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-win64-gpl-shared.zip"
    )
    # 下载超时（秒）：GitHub release 经 CDN 分发，通常较快但需容错大文件场景
    FFMPEG_DOWNLOAD_TIMEOUT_SEC: int = 300
    # subprocess 检测超时（秒）：未安装时 Windows 报错很快，已安装时 -version 秒回
    FFMPEG_CHECK_TIMEOUT_SEC: int = 10

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

    # ---- 自动审批模块（V1.4 新增） ----
    # 自动审批统计查询默认时间范围（天），未指定 start_date 时回溯 N 天
    AUTO_REVIEW_STATS_DEFAULT_DAYS: int = 7
    # 自动审批执行超时（秒）：超时则视为失败，触发告警与手动干预流程
    AUTO_REVIEW_EXECUTION_TIMEOUT_SEC: int = 30
    # 自动审批失败时是否自动通知管理员（通过 NotifierHub 推送）
    AUTO_REVIEW_NOTIFY_ON_FAILURE: bool = True

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

    @property
    def audio_base_url_resolved(self) -> str:
        """音频/封面静态资源最终生效的对外访问 URL。

        解析优先级：
        1. 显式配置的 AUDIO_BASE_URL（.env 中非空值）—— 生产环境必须配置公网域名
        2. 自动检测的本机局域网 IP + APP_PORT —— 开发环境零配置即可真机调试

        设计原因：硬编码 IP 在切换 WiFi/路由器后会失效（如 192.168.1.65 → 192.168.0.65），
        导致小程序"网络异常"。留空触发自动检测可避免此问题。
        """
        if self.AUDIO_BASE_URL:
            return self.AUDIO_BASE_URL.rstrip("/")
        return f"http://{detect_lan_ip()}:{self.APP_PORT}"


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复读取 .env 文件。"""
    return Settings()
