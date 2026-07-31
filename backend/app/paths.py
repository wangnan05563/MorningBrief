"""路径解析模块（V1.2 新增）。

核心问题：PyInstaller 打包后 __file__ 指向临时解压目录，
用户数据（SQLite、日志、.env）必须放在 exe 同级目录，否则升级后丢失。

设计原则：
- 可写数据（data/、logs/、.env）放在 exe 同级目录
- 只读资源（YAML 配置、前端静态文件）在 _MEIPASS 临时目录
- 参考 D:\\code\\otherProjects\\17_xianyu\\app\\paths.py 的成熟实现
"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否为 PyInstaller 打包模式。"""
    return getattr(sys, "frozen", False)


def get_app_root() -> Path:
    """获取应用根目录。

    打包态：exe 所在目录（如 C:\\Program Files\\MorningBrief\\）
    开发态：backend/ 目录（app 包的父目录）
    """
    if is_frozen():
        return Path(sys.executable).parent.resolve()
    # 开发态：app/paths.py 的上两级 = backend/
    return Path(__file__).parent.parent.resolve()


def resolve_data_dir() -> Path:
    """数据目录（SQLite 数据库、WAL 文件）。"""
    data_dir = get_app_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def resolve_db_path() -> Path:
    """SQLite 数据库文件路径。"""
    return resolve_data_dir() / "news.db"


def resolve_bgm_dir() -> Path:
    """BGM 文件根目录（预制 + 用户上传）。

    结构：
    - data/bgm/preset/   预制 BGM，随安装包分发或用户自行放入
    - data/bgm/custom/   用户上传的 BGM，按 {channel_id}_{filename} 命名
    """
    bgm_dir = resolve_data_dir() / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    (bgm_dir / "preset").mkdir(exist_ok=True)
    (bgm_dir / "custom").mkdir(exist_ok=True)
    return bgm_dir


def resolve_avatar_dir() -> Path:
    """用户头像文件目录。

    C 端用户上传的头像图片存放在此目录，由 /avatars 静态挂载对外提供访问。
    与 bgm/ 同级：均为用户/运维产生的可写文件，放 data/ 下随 exe 同级持久化。
    """
    avatar_dir = resolve_data_dir() / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    return avatar_dir


def resolve_log_dir() -> Path:
    """日志目录。"""
    log_dir = get_app_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def resolve_env_path() -> Path:
    """ .env 配置文件路径（exe 同级）。"""
    return get_app_root() / ".env"


def resolve_ffmpeg_path() -> str:
    """FFmpeg 可执行文件路径。

    优先使用项目自带的 ffmpeg.exe（./ffmpeg/bin/），保证滤镜支持一致性
    （loudnorm/silenceremove 等滤镜需要完整构建，精简版 ffmpeg 不支持）。
    仅当项目未附带 ffmpeg 时，才回退到系统 PATH。
    """
    bundled = get_app_root() / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return "ffmpeg"


def resolve_ffprobe_path() -> str:
    """FFprobe 可执行文件路径。

    与 resolve_ffmpeg_path 对称：优先项目自带，回退 PATH。
    """
    bundled = get_app_root() / "ffmpeg" / "bin" / "ffprobe.exe"
    if bundled.exists():
        return str(bundled)
    return "ffprobe"


def resolve_admin_dist() -> Path | None:
    """B 端运营后台静态资源目录（Vue 构建产物）。

    查找顺序：
    1. exe 同级 admin-web/dist（build-exe.ps1 外置复制，便于前端独立更新）
    2. _MEIPASS/app/static/admin/dist（PyInstaller datas 打包态）
    3. backend/app/static/admin/dist（开发态）
    """
    app_root = get_app_root()
    # 优先：exe 同级外置目录（build-exe.ps1 复制到此，前端可独立更新无需重建 exe）
    ext_dist = app_root / "admin-web" / "dist"
    if ext_dist.exists():
        return ext_dist
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            packed = Path(meipass) / "app" / "static" / "admin" / "dist"
            if packed.exists():
                return packed
    # 开发态：项目根目录下的 admin-web/dist（vite 构建产物）
    dev_dist = app_root.parent / "admin-web" / "dist"
    return dev_dist if dev_dist.exists() else None


def resolve_rss_sources_path() -> Path:
    """RSS 源配置文件路径（rss.yaml，只读资源）。

    rss.yaml 为只读资源，打包态随 PyInstaller datas 打入 _MEIPASS，
    开发态位于 backend/app/workflow/crawler/sources/rss.yaml。
    与 resolve_bgm_dir 等可写数据路径不同：可写数据走 exe 同级目录，
    只读资源走打包目录，避免升级时 rss.yaml 被旧版本覆盖。
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "app" / "workflow" / "crawler" / "sources" / "rss.yaml"
    # 开发态：app/paths.py 的上两级 = backend/
    return get_app_root() / "app" / "workflow" / "crawler" / "sources" / "rss.yaml"
