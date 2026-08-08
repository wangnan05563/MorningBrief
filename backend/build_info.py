"""构建元信息生成器。

在打包 / 发布前运行，将真实的版本号、构建日期、Git SHA 写入
``app/_build_info.py``，替换其内硬编码的默认值。

为什么需要它（历史问题）：
- ``app/_build_info.py`` 的默认值 git_sha="unknown" / build_date="2026-07-20"
  / version="1.0.0" 长期未更新，导致「关于」页永远显示 unknown SHA、
  固定的构建日期；检查更新也基于过时的 version="1.0.0" 比较，结果不可靠。
- 之前的打包脚本（build-exe.ps1）与发布脚本（push_to_github.ps1）从未调用
  任何生成器覆盖该文件，所以每次发布都带着同一份过期默认值。

本脚本作为单一真相来源，被两条流水线在收集/打包文件前调用，
保证 _build_info.py 在每次发布时都被刷新。

版本号优先级：
1. 同级 ``VERSION`` 文件（一行纯版本号，如 1.2.3）——推荐人工维护
2. 最近的 git tag（git describe --tags），自动去掉前缀 v
3. 兜底常量 "1.0.0"（无 tag 且无 VERSION 时）

用法：
    python backend/build_info.py
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone

# UTC+8（与 about.py / 项目其他模块一致）
_CST = timezone(timedelta(hours=8))

# 兜底版本号（仅在无 VERSION 文件且无 git tag 时使用）
_FALLBACK_VERSION = "1.0.0"

# 脚本与 app 包的相对位置：backend/build_info.py -> backend/app/_build_info.py
_HERE = os.path.dirname(os.path.abspath(__file__))
_TARGET = os.path.join(_HERE, "app", "_build_info.py")
_VERSION_FILE = os.path.join(_HERE, "VERSION")


def _read_version_file() -> str | None:
    """读取同级 VERSION 文件的首行非空白内容。"""
    if not os.path.isfile(_VERSION_FILE):
        return None
    try:
        with open(_VERSION_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    except OSError:
        return None
    return None


def _git(*args: str) -> str | None:
    """在 backend 目录执行 git 命令，失败返回 None。"""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=_HERE,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode != 0:
            return None
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _detect_version() -> str:
    """确定版本号：VERSION 文件 > git tag > 兜底。"""
    from_file = _read_version_file()
    if from_file:
        return from_file

    # git describe --tags：有 tag 时返回 如 v1.2.3-2-gabc123；
    # --abbrev=0 仅取最近 tag 本身（v1.2.3）。无 tag 时失败返回 None。
    tag = _git("describe", "--tags", "--abbrev=0")
    if tag:
        return tag.lstrip("vV")

    return _FALLBACK_VERSION


def _detect_git_sha() -> str:
    """获取短 SHA；非 git 仓库或命令失败时返回 'unknown'。"""
    sha = _git("rev-parse", "--short", "HEAD")
    return sha or "unknown"


def _detect_build_date() -> str:
    """构建日期（UTC+8，YYYY-MM-DD）。"""
    return datetime.now(_CST).strftime("%Y-%m-%d")


def generate() -> dict[str, str]:
    """生成并写入 _build_info.py，返回写入的字段。"""
    fields = {
        "version": _detect_version(),
        "build_date": _detect_build_date(),
        "git_sha": _detect_git_sha(),
    }

    content = (
        '"""构建元信息模块（由 build_info.py 自动生成，请勿手动编辑）。\n'
        '\n'
        '包含 __version__ / build_date / git_sha，供关于页面与检查更新使用。\n'
        '开发态若未运行本脚本，则使用下方默认值；发布/打包前务必运行以保持最新。\n'
        '"""\n'
        "from __future__ import annotations\n\n"
        f'__version__ = "{fields["version"]}"\n'
        f'build_date = "{fields["build_date"]}"\n'
        f'git_sha = "{fields["git_sha"]}"\n'
    )

    os.makedirs(os.path.dirname(_TARGET), exist_ok=True)
    with open(_TARGET, "w", encoding="utf-8") as f:
        f.write(content)

    return fields


if __name__ == "__main__":
    result = generate()
    print(
        f"[build_info] wrote {os.path.relpath(_TARGET)}: "
        f"version={result['version']} "
        f"build_date={result['build_date']} "
        f"git_sha={result['git_sha']}"
    )
