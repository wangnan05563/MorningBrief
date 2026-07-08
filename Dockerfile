# 20_News FastAPI 单体应用镜像
# 基础镜像：Python 3.11 slim（含 FFmpeg）
FROM python:3.11-slim

# 系统依赖：
# - ffmpeg: 音频拼接
# - libxml2-dev/libxslt-dev: newspaper3k 依赖
# - gcc: 编译 Python 扩展
# - curl: 健康检查
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libxml2-dev \
    libxslt-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ .

# 暴露端口
EXPOSE 8000

# 启动命令：uvicorn + 多 worker（MVP 用 1 worker，避免 APScheduler 重复触发）
# APScheduler 仅在主进程运行，多 worker 会导致重复调度
# 模块路径 app.main:app —— main.py 位于 /app/app/main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
