# -*- mode: python ; coding: utf-8 -*-
"""
MorningBrief PyInstaller 打包配置

产物结构（COLLECT 模式，目录形式）：
  dist/MorningBrief/
    MorningBrief.exe              ← 启动入口
    _internal/               ← Python 运行时 + 依赖 + app 代码
      app/                   ← FastAPI 应用
        workflow/            ← AI 工作流模块
          crawler/sources/   ← 爬虫源配置 YAML
          llm/prompts/       ← LLM 提示词模板
          llm/sensitive_words.txt
          tts/voices.yaml    ← TTS 音色配置
    .env                     ← 配置文件（外置，用户编辑）
    admin-web/dist/          ← 前端构建产物（外置，由 FastAPI StaticFiles 服务）

注意事项：
- V1.2 起爬虫改为 httpx + selectolax，无 scrapy/playwright 动态导入
- .env 外置让用户可编辑 SQLite 路径、COS、LLM 等配置
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ============================================================
# 隐式导入收集
# ============================================================

# 关键：collect_submodules/collect_data_files 依赖 Python 标准 import 机制
# 定位包，而 pathex 仅作用于 Analysis 阶段，不影响 spec 执行时的 sys.path。
# 若不把 backend 加入 sys.path，collect_submodules('app') 会静默返回空列表，
# 导致 app 包完全缺失，exe 启动时报 "Could not import module 'app.main'"。
_project_root = os.path.abspath('.')
_backend_dir = os.path.join(_project_root, 'backend')
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# V1.2 起爬虫改为 httpx + selectolax，不再依赖 scrapy/playwright/newspaper
hiddenimports = []

# app 包是项目自身的代码，但 launcher.py 通过字符串 "app.main:app"
# 让 uvicorn 在运行时动态导入，PyInstaller 静态分析看不到这种依赖。
# 必须显式收集整个 app 包的所有子模块，否则 exe 启动时报
# "Error loading ASGI app. Could not import module 'app.main'"
hiddenimports += collect_submodules('app')

hiddenimports += collect_submodules('selectolax')
hiddenimports += collect_submodules('jieba')
hiddenimports += collect_submodules('ahocorasick')
hiddenimports += collect_submodules('apscheduler')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('uvicorn.protocols')
hiddenimports += collect_submodules('uvicorn.lifespan')
hiddenimports += collect_submodules('uvicorn.loops')

# SQLAlchemy 异步驱动 + 进程内缓存 + RSS 解析
hiddenimports += ['aiosqlite', 'cachetools', 'feedparser']

# Pydantic v2 内部模块
hiddenimports += ['pydantic', 'pydantic_settings', 'pydantic.deprecated']

# edge-tts：edge_tts.Communicate 通过字符串动态导入，PyInstaller 静态分析看不到
hiddenimports += collect_submodules('edge_tts')

# COS SDK（cos-python-sdk-v5 无动态导入，无需额外 hiddenimport）

# ============================================================
# 数据文件收集
# ============================================================

# app 包内的 YAML/TXT 配置文件需打包到 exe 中
# collect_data_files 递归收集包目录下的非 .py 文件
# 注：PyInstaller 6.x 的 collect_data_files 不支持 include_patterns 参数
#      这些目录下只有 .txt/.yaml/.yml 配置文件，无需过滤
datas = []
datas += collect_data_files('app.workflow.crawler.sources')
datas += collect_data_files('app.workflow.llm')
datas += collect_data_files('app.workflow.llm.prompts')
datas += collect_data_files('app.workflow.tts')

# certifi CA 证书：edge-tts 使用 certifi.where() 指定 SSL 证书路径，
# 若不收集 cacert.pem，打包后 SSL 握手失败，服务端返回 403
datas += collect_data_files('certifi')

# 显式补充关键配置文件（确保路径正确）
# 格式：(源文件相对路径, 目标目录相对路径)
# 注：_project_root / _backend_dir 已在文件开头定义（需先于 collect_submodules）
explicit_datas = [
    # 爬虫源配置
    (os.path.join(_backend_dir, 'app', 'workflow', 'crawler', 'sources', 'lists.yaml'),
     os.path.join('app', 'workflow', 'crawler', 'sources')),
    (os.path.join(_backend_dir, 'app', 'workflow', 'crawler', 'sources', 'rss.yaml'),
     os.path.join('app', 'workflow', 'crawler', 'sources')),
    # LLM 提示词与敏感词
    (os.path.join(_backend_dir, 'app', 'workflow', 'llm', 'prompts', 'rewrite.txt'),
     os.path.join('app', 'workflow', 'llm', 'prompts')),
    (os.path.join(_backend_dir, 'app', 'workflow', 'llm', 'sensitive_words.txt'),
     os.path.join('app', 'workflow', 'llm')),
    # TTS 音色配置
    (os.path.join(_backend_dir, 'app', 'workflow', 'tts', 'voices.yaml'),
     os.path.join('app', 'workflow', 'tts')),
]

for src, dst in explicit_datas:
    if os.path.exists(src):
        datas.append((src, dst))

# ============================================================
# Analysis
# ============================================================

a = Analysis(
    [os.path.join(_backend_dir, 'launcher.py')],
    pathex=[_backend_dir],
    binaries=[
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'ffmpeg.exe'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'ffprobe.exe'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'avutil-61.dll'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'avcodec-63.dll'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'avformat-63.dll'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'avdevice-63.dll'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'avfilter-12.dll'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'swresample-7.dll'), 'ffmpeg/bin'),
        (os.path.join(_backend_dir, 'ffmpeg', 'bin', 'swscale-10.dll'), 'ffmpeg/bin'),
    ],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除测试框架（减小体积）
        'pytest', '_pytest', 'pytest_asyncio',
        'tests',
        # 排除 tkinter（未使用）
        'tkinter',
        # 排除 SQLAlchemy 可选数据库驱动（仅使用 aiosqlite）
        'pysqlite2', 'MySQLdb', 'psycopg2', 'psycopg2-binary',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ============================================================
# PYZ（Python 字节码压缩包）
# ============================================================

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ============================================================
# EXE（入口可执行文件）
# ============================================================

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MorningBrief',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,        # 控制台模式，显示 uvicorn 日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(_project_root, 'assets', 'MorningBrief.ico'),  # exe 应用图标
)

# ============================================================
# COLLECT（目录模式，便于外置 .env 和前端产物）
# ============================================================

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MorningBrief',
)
