"""构建元信息模块。

由构建脚本（build_info.py）在打包时写入；开发态使用默认值。
关于页面读取此处的 __version__ / build_date / git_sha 展示系统元信息。

为何独立成文件：
- 隔离构建期写入与运行期读取，避免 main.py 启动时执行 git 命令拖慢首屏
- 打包态由 PyInstaller datas 打入 _MEIPASS，开发态直接读取源码值
"""
from __future__ import annotations

# 默认值：开发态未执行 build_info.py 时使用
# 构建脚本会覆盖这三个字段，写入实际版本/日期/SHA
__version__ = "1.0.0"
build_date = "2026-07-20"
git_sha = "unknown"
