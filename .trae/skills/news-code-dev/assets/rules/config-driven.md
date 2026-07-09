# 配置驱动规则

本文档定义 20_News 项目的配置驱动开发规则。

## 配置层次

```
.env（环境变量，最高优先级）
    ↓ 覆盖
settings.py（Pydantic BaseSettings，默认值）
    ↓ 读取
代码中使用 settings.XXX
```

## Settings 定义

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置。"""
    
    # ===== 数据库 =====
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    
    # ===== Redis =====
    REDIS_URL: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    CACHE_TTL_SEC: int = Field(3600, env="CACHE_TTL_SEC")
    
    # ===== LLM =====
    DASHSCOPE_API_KEY: str = Field(..., env="DASHSCOPE_API_KEY")
    LLM_API_URL: str = Field("https://dashscope.aliyuncs.com/api/v1/aigc/text-generation/generation", env="LLM_API_URL")
    LLM_MODEL: str = Field("qwen-max", env="LLM_MODEL")
    LLM_TIMEOUT: float = Field(60.0, env="LLM_TIMEOUT")
    
    # ===== TTS =====
    TTS_APP_KEY: str = Field(..., env="TTS_APP_KEY")
    TTS_VOICE_NAME: str = Field("xiaoyan", env="TTS_VOICE_NAME")
    
    # ===== COS =====
    COS_SECRET_ID: str = Field(..., env="COS_SECRET_ID")
    COS_SECRET_KEY: str = Field(..., env="COS_SECRET_KEY")
    COS_BUCKET: str = Field(..., env="COS_BUCKET")
    COS_REGION: str = Field("ap-shanghai", env="COS_REGION")
    
    # ===== JWT =====
    JWT_SECRET: str = Field(..., env="JWT_SECRET")
    JWT_ALGORITHM: str = Field("HS256", env="JWT_ALGORITHM")
    JWT_EXPIRE_SECONDS: int = Field(86400, env="JWT_EXPIRE_SECONDS")
    
    # ===== 工作流 =====
    WORKFLOW_MAX_RETRIES: int = Field(3, env="WORKFLOW_MAX_RETRIES")
    WORKFLOW_LOCK_TTL: int = Field(3600, env="WORKFLOW_LOCK_TTL")
    RSS_FEED_URLS: str = Field("", env="RSS_FEED_URLS")  # 逗号分隔
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()


settings = get_settings()
```

## Field 使用

```python
from pydantic import Field

# 带描述的字段
MAX_PAGE_SIZE: int = Field(
    default=100,
    ge=1,
    le=1000,
    description="每页最大数量"
)

# 必填字段
API_KEY: str = Field(..., description="API 密钥")
```

## 环境变量文件

```bash
# .env.example（提交到仓库的模板）
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/news_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=change-me-in-production
DASHSCOPE_API_KEY=sk-xxx

# .env（不提交到仓库）
# 从 .env.example 复制，填入实际值
```

## 配置变更流程

1. 修改 `settings.py` 中的默认值
2. 更新 `.env.example`（如有新字段）
3. 通知团队成员更新本地 `.env`
4. 重启服务生效

**为什么不用热重载**：
- Python 配置对象是缓存的单例
- 热重载需要重新导入模块，容易出错
- 重启是最安全的配置更新方式

## 禁止硬编码的场景

| 场景 | 错误做法 | 正确做法 |
|------|----------|----------|
| API Key | `api_key = "sk-xxx"` | `api_key = settings.API_KEY` |
| URL | `"http://localhost:3306"` | `settings.DATABASE_URL` |
| 超时 | `timeout=30` | `settings.REQUEST_TIMEOUT` |
| 重试次数 | `max_retries=3` | `settings.WORKFLOW_MAX_RETRIES` |
| 缓存 TTL | `ttl=3600` | `settings.CACHE_TTL_SEC` |

## 多环境配置

```python
# 通过环境变量切换配置
import os

env = os.getenv("APP_ENV", "development")

if env == "production":
    # 生产环境配置
    settings.CACHE_TTL_SEC = 7200
    settings.WORKFLOW_MAX_RETRIES = 5
elif env == "staging":
    # 预发环境配置
    settings.CACHE_TTL_SEC = 1800
else:
    # 开发环境配置（默认）
    settings.CACHE_TTL_SEC = 300
```

更好的方式是通过不同的 `.env` 文件：

```bash
# .env.development
APP_ENV=development
DATABASE_URL=mysql+aiomysql://...

# .env.production
APP_ENV=production
DATABASE_URL=mysql+aiomysql://prod-db:3306/news_db
```

Docker Compose 中指定：

```yaml
services:
  app:
    env_file:
      - .env.production
```
