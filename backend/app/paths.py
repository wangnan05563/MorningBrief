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

    打包态：exe 所在目录（如 C:\\Program Files\\20_News\\）
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

    打包态：随 Inno Setup 安装到 ./ffmpeg/bin/ffmpeg.exe
    开发态：依赖系统 PATH
    """
    if is_frozen():
        bundled = get_app_root() / "ffmpeg" / "bin" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)
    return "ffmpeg"


def resolve_admin_dist() -> Path | None:
    """B 端运营后台静态资源目录（Vue 构建产物）。

    打包态：嵌入 PyInstaller datas（_MEIPASS 临时目录）
    开发态：backend/app/static/admin/dist
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "app" / "static" / "admin" / "dist"
    dev_dist = get_app_root() / "app" / "static" / "admin" / "dist"
    return dev_dist if dev_dist.exists() else None
