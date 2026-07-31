# 数据库规则

本文档定义 MorningBrief 项目的数据库开发规则。

## 表设计规范

### 命名规范

- 表名：复数小写 + 下划线（`news_items`, `user_roles`）
- 字段名：小写 + 下划线（`created_at`, `user_id`）
- 主键：`id`（INTEGER AUTO_INCREMENT）
- 外键：`{referenced_table}_id`（`user_id` 引用 `users` 表）
- 索引：`idx_{table}_{column(s)}`（`idx_news_items_category`）

### 必备字段

每张业务表应包含：

```sql
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
created_at DATETIME NOT NULL,
updated_at DATETIME NOT NULL,
is_deleted TINYINT(1) NOT NULL DEFAULT 0  -- 软删除
```

### 字段类型选择

| 场景 | 类型 | 说明 |
|------|------|------|
| 状态/类型 | VARCHAR(20) | 存储枚举 .value |
| 布尔值 | TINYINT(1) | MySQL 无原生 bool |
| 金额 | DECIMAL(10,2) | 不用 FLOAT |
| 长文本 | TEXT | 正文、描述 |
| JSON | JSON | 灵活结构 |
| IP 地址 | VARCHAR(45) | 支持 IPv6 |

## 索引规范

### 何时创建索引

- 高频查询的 WHERE 条件字段
- JOIN 关联字段
- ORDER BY 排序字段（如果查询量大）
- 唯一约束字段

### 联合索引遵循最左前缀原则

```sql
-- 索引 (category, status)
-- 可加速以下查询：
-- WHERE category = 'tech'
-- WHERE category = 'tech' AND status = 'active'
-- 但不能加速：WHERE status = 'active'（缺少最左前缀 category）

CREATE INDEX idx_news_category_status ON news_items(category, status);
```

### 索引限制

- 单表索引不超过 5 个
- 低基数字段（如 is_deleted）不适合单独建索引
- 避免在频繁写入的表上创建过多索引

## 查询规范

### 分页查询必须 LIMIT

```python
# 正确
stmt = select(NewsModel).limit(100).offset(0)

# 错误：返回全表
stmt = select(NewsModel)
```

### 避免 SELECT *

```python
# 正确：只查询需要的字段
stmt = select(NewsModel.id, NewsModel.title)

# 错误
stmt = select(NewsModel)
```

### 使用 EXPLAIN 分析慢查询

```sql
EXPLAIN SELECT * FROM news_items WHERE category = 'tech' ORDER BY created_at DESC;
```

关注：
- `type`：应该是 `ref` 或 `range`，避免 `ALL`（全表扫描）
- `rows`：扫描的行数越少越好
- `Extra`：避免出现 `Using filesort`、`Using temporary`

## 事务规范

### 事务粒度尽量小

```python
# 正确：只在必要时使用事务
async with db.begin():
    await db.execute(insert(User).values(...))
    await db.execute(insert(Profile).values(...))

# 错误：整个函数包裹在事务中
async def process_workflow():
    async with db.begin():
        # 包含 HTTP 调用、TTS 合成等耗时操作
        await fetch_rss()
        await synthesize_tts()
```

### 乐观锁防止并发覆盖

```python
# 更新时检查版本号
stmt = (
    update(NewsModel)
    .where(
        NewsModel.id == news_id,
        NewsModel.version == current_version,  # 乐观锁
    )
    .values(content=new_content, version=current_version + 1)
)
```

## 迁移规范

### Alembic 迁移要求

- 每次模型变更必须生成迁移脚本
- 迁移脚本必须幂等（可重复执行）
- 禁止手动修改已执行的迁移脚本

### 生成迁移

```bash
# 自动生成迁移
alembic revision --autogenerate -m "add_news_categories_table"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 数据迁移

```python
"""添加 default 值的迁移。"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. 添加可空列
    op.add_column('news_items', sa.Column('category', sa.String(50), nullable=True))
    
    # 2. 填充默认值
    op.execute("UPDATE news_items SET category = 'general' WHERE category IS NULL")
    
    # 3. 改为 NOT NULL
    op.alter_column('news_items', 'category', nullable=False)
```

## 连接池配置

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,          # 连接池大小
    max_overflow=10,       # 超出 pool_size 后的最大额外连接
    pool_timeout=30,       # 获取连接的超时时间
    pool_recycle=3600,     # 连接回收时间（防止 MySQL 断开）
    pool_pre_ping=True,    # 使用前检查连接有效性
)
```

## 外键约束防御性处理

### 不依赖 SQLite PRAGMA foreign_keys 开关，手动处理关联表

**为什么**：SQLite 默认不开启 `PRAGMA foreign_keys = ON`，且项目测试环境也未开启此开关。如果代码依赖外键约束的 `ON DELETE CASCADE` 或 `ON DELETE SET NULL` 行为，在测试环境会出现父记录删除后子表外键仍指向已删除记录的问题。手动处理关联表保证测试环境与生产环境行为一致，不依赖数据库配置开关。

**判断逻辑**：
- 不依赖 `PRAGMA foreign_keys` 开关，手动处理关联表的外键
- 删除父记录前必须先 UPDATE 子表外键为 NULL（或删除子表记录）
- 测试环境默认未开启 `PRAGMA foreign_keys`，手动 UPDATE 保证行为一致

**固定流程**：
1. 识别父表与子表的关联关系（外键约束）
2. 删除父记录前，先 UPDATE 子表外键为 NULL（或按业务删除子表记录）
3. 再 DELETE 父表记录
4. 整个流程用事务包裹，保证原子性

**正确做法**：
```python
# ✅ 删除父记录前先 UPDATE 子表外键为 NULL
async def delete_channel(db: AsyncSession, channel_id: int) -> None:
    """删除频道，手动处理关联表外键。

    不依赖 PRAGMA foreign_keys 开关，手动 UPDATE 保证测试/生产行为一致。
    """
    async with db.begin():
        # 1. 先 UPDATE 子表外键为 NULL
        await db.execute(
            update(Material)
            .where(Material.channel_id == channel_id)
            .values(channel_id=None)
        )
        await db.execute(
            update(PlayProgress)
            .where(PlayProgress.channel_id == channel_id)
            .values(channel_id=None)
        )
        # 2. 再 DELETE 父表记录
        await db.execute(
            delete(Channel).where(Channel.id == channel_id)
        )
```

**错误做法**：
```python
# ❌ 依赖 PRAGMA foreign_keys ON DELETE SET NULL，测试环境未开启会失败
async def delete_channel(db: AsyncSession, channel_id: int) -> None:
    async with db.begin():
        # 直接删除父记录，依赖外键约束自动 SET NULL
        # 测试环境 PRAGMA foreign_keys 默认 OFF，子表外键仍指向已删除记录
        await db.execute(
            delete(Channel).where(Channel.id == channel_id)
        )

# ❌ 仅开启 PRAGMA 但不手动处理，生产环境切换数据库时可能失效
async def delete_channel(db: AsyncSession, channel_id: int) -> None:
    await db.execute(text("PRAGMA foreign_keys = ON"))  # 仅当前连接生效
    await db.execute(delete(Channel).where(Channel.id == channel_id))
    # 连接池复用时其他连接未开启 PRAGMA，行为不一致
```

**规则**：
- 不依赖 `PRAGMA foreign_keys` 开关，手动处理关联表外键
- 删除父记录前必须先 UPDATE 子表外键为 NULL（或删除子表记录）
- 整个流程用事务包裹（`async with db.begin()`），保证原子性
- 多个关联表按依赖顺序处理（先处理叶子表，再处理中间表，最后处理父表）

**适用场景**：测试环境与生产环境外键约束行为不一致的场景；SQLite 单机部署项目
**不适用场景**：明确开启外键约束且数据完整性要求高的场景（如金融系统）；PostgreSQL/MySQL 等默认开启外键约束的数据库
