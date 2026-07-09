"""V1.2 重构后启动验证脚本（临时，验证后可删）。

验证点：
1. app 包能完整 import（所有模块无残留 redis/mysql 依赖）
2. SQLite schema create_all 能成功建表
3. 14 张表全部存在（11 业务 + 3 辅助：jwt_blacklist、crawler_dedup、play_progress）
4. cache_manager 读写正常
5. FastAPI app 能创建
"""
import asyncio
import os
import sys

# 设置测试环境变量（避免缺少 .env 报错）
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("JWT_SECRET", "test-secret-32chars-minimum-aaa")
os.environ.setdefault("SQLITE_DB_PATH", "./data/test_init.db")

from sqlalchemy import inspect

from app.cache.manager import cache
from app.database import Base, engine
from app.main import _init_sqlite_schema, create_app


async def verify():
    # 1. 建表
    print("=== 1. SQLite 建表 ===")
    await _init_sqlite_schema()
    print("OK: schema create_all 成功")

    # 2. 列出所有表
    print("\n=== 2. 表清单 ===")
    async with engine.connect() as conn:
        tables = await conn.run_sync(
            lambda c: inspect(c).get_table_names()
        )
    print(f"共 {len(tables)} 张表:")
    for t in sorted(tables):
        print(f"  - {t}")

    expected = {
        "user", "admin_user", "script", "material", "ad_material",
        "ad_placement", "workflow", "workflow_step", "review",
        "episode", "play_log",
        "jwt_blacklist", "crawler_dedup", "play_progress",
    }
    actual = set(tables)
    missing = expected - actual
    extra = actual - expected
    if missing:
        print(f"FAIL: 缺少表 {missing}")
        sys.exit(1)
    if extra:
        print(f"WARN: 多出表 {extra}")
    print(f"OK: 14 张表全部存在")

    # 3. cache_manager 读写
    print("\n=== 3. CacheManager 读写 ===")
    await cache.set("test_key", {"data": "hello"}, ttl=60)
    val = await cache.get("test_key")
    assert val == {"data": "hello"}, f"cache get 失败: {val}"
    print("OK: cache set/get 正常")

    # 自定义 TTL 验证（25h，验证元组解包修复）
    await cache.set("long_key", {"data": "long"}, ttl=25 * 3600)
    val2 = await cache.get("long_key")
    assert val2 == {"data": "long"}, f"long TTL cache get 失败: {val2}"
    print("OK: 自定义 TTL（25h）cache 读写正常（元组解包修复验证通过）")

    # 4. FastAPI app 创建
    print("\n=== 4. FastAPI 应用创建 ===")
    app = create_app()
    routes = [r.path for r in app.routes]
    print(f"共 {len(routes)} 个路由")
    print("OK: FastAPI app 创建成功")

    # 5. 关闭 engine
    await engine.dispose()
    print("\n=== 全部验证通过 ===")


if __name__ == "__main__":
    asyncio.run(verify())
