# 架构模式

本文档描述 MorningBrief 项目的核心架构模式，供开发新功能、修复缺陷和优化时参考。

## 四层架构

项目后端采用清晰的四层分离架构，每一层职责单一，依赖方向固定：

```
routers (HTTP 入口)
    ↓ 调用
services (业务逻辑)
    ↓ 调用
models (数据持久化)
    ↓ 调用
core (基础设施：数据库连接、Redis、认证、日志)
```

**设计意图**：
- routers 层只负责解析 HTTP 请求、参数校验、调用 service、格式化响应，不包含任何业务逻辑
- services 层封装全部业务规则，可以独立于 HTTP 协议被测试和复用
- models 层只做 ORM 映射，不包含业务逻辑
- core 层提供可复用的基础设施能力（数据库会话、Redis 客户端、认证依赖等）

**判断信号**：
- 路由文件中出现 `if/else` 业务判断 → 应下沉到 service 层
- service 文件中导入具体路由模块 → 违反依赖方向，应反向
- model 文件中有业务逻辑 → 应移到 service 层

## 工作流编排模式

新闻生产链路（RSS 抓取 → LLM 改写 → TTS 合成 → 音频拼接 → 审核发布）采用**状态机 + 分布式锁 + 重试**模式：

### 状态机

每个工作流实例（如一次新闻播报生成）都有一个状态字段，典型流转如下：

```
pending → running → success
              ↘ failed ↗
```

- `pending`：任务已创建，等待调度器触发
- `running`：任务正在执行中
- `success`：任务完成，结果可消费
- `failed`：任务执行失败，可重试或人工介入

**实现要点**：
- 状态变更通过数据库事务保证原子性
- 使用 `UPDATE ... WHERE status = :old_status` 防止并发冲突
- 定时巡检任务扫描 `running` 状态超时的任务，标记为 `failed` 以便重试

### 分布式锁

工作流调度器使用 Redis 分布式锁防止同一任务被多个 worker 重复执行：

```python
lock_key = f"workflow_lock:{task_id}"
acquired = await redis.set(lock_key, "1", nx=True, ex=settings.WORKFLOW_LOCK_TTL)
if not acquired:
    logger.info(f"Task {task_id} already being processed, skipping")
    return
```

**设计意图**：
- `nx=True` 确保只有第一个获取锁的 worker 能执行
- `ex` 设置锁超时时间，防止 worker 崩溃后锁永远不释放
- 锁持有者必须在完成任务后主动释放锁

### 重试机制

工作流步骤支持可配置的重试策略：

```python
async def execute_with_retry(func, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)  # 指数退避
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

**设计意图**：
- 指数退避避免对下游服务造成压力
- 最大重试次数通过配置驱动，不同步骤可配置不同值
- 最终失败记录日志并更新状态为 `failed`

## 缓存模式

采用 **cache-aside（旁路缓存）** 模式：

```
读取流程：
1. 查 Redis 缓存
2. 命中 → 返回缓存数据
3. 未命中 → 查数据库 → 写入缓存 → 返回

写入流程：
1. 更新数据库
2. 删除（而非更新）缓存 key
```

**为什么不更新缓存而是删除？**
- 避免并发写入导致缓存脏数据
- 下次读取时自动重建缓存，保证最终一致性
- 对于读多写少的场景（如新闻列表），这是最优策略

**缓存失效策略**：
- 写操作后主动删除相关缓存 key
- 设置 TTL 作为兜底，防止缓存永不过期
- 批量删除使用 Redis key pattern 匹配（谨慎使用，避免影响其他业务）

**判断信号**：
- 缓存 key 没有设置 TTL → 可能导致内存泄漏
- 写入操作只更新缓存不删除 → 可能导致脏数据
- 同一数据有多个缓存 key → 一致性难以保证

## 认证模式

采用 **JWT + httpOnly cookie + 黑名单** 三重机制：

### JWT 签发与验证

```
登录流程：
1. 用户提交微信凭证
2. 后端验证凭证，获取用户信息
3. 签发 JWT（包含 user_id、role、exp）
4. 将 JWT 写入 httpOnly cookie
5. 返回成功响应

请求流程：
1. 中间件从 cookie 提取 JWT
2. 验证签名（使用 hmac.compare_digest 防时序攻击）
3. 检查是否在黑名单中
4. 通过 → 注入当前用户信息到请求上下文
5. 失败 → 返回 401
```

### Token 黑名单

使用 Redis 存储已注销的 token：

```python
blacklist_key = f"token:blacklist:{jti}"
await redis.setex(blacklist_key, token_exp_time - now, "1")
```

**设计意图**：
- JWT 本身无状态，无法主动作废
- 黑名单用于支持"退出登录"和"强制下线"场景
- 过期时间与 JWT exp 保持一致，自动清理

### 权限分级

- 公开接口：健康检查、微信登录
- 认证接口：需要有效 JWT
- 管理员接口：需要 admin 角色
- 内部接口：仅限 localhost 访问（如工作流触发接口）

**判断信号**：
- 内部接口没有 IP 校验 → 安全风险
- JWT 比较使用 `==` 而非 `hmac.compare_digest` → 时序攻击风险
- 退出登录后 token 未被加入黑名单 → 仍可继续使用

## 审核模式

新闻播报内容采用三态审核机制：

```
pending（待审核）→ approved（已通过）→ 发布到小程序
      ↘ rejected（已拒绝）→ 通知作者
```

### 审核规则

- 自动审核：敏感词过滤（AC 自动机）、长度校验
- 人工审核：运营后台审核队列
- 定时巡检：扫描超过 N 小时未审核的内容，发送告警

### 审核状态同步

审核状态变更后需要同步更新：
1. 数据库中的播报状态
2. 小程序端的展示逻辑（只显示 approved 内容）
3. 缓存中的审核计数（如有）

**判断信号**：
- 审核状态变更后未更新缓存 → 数据不一致
- 小程序端展示了 pending 状态的内容 → 审核逻辑缺陷

## 异步模式

### asyncio.create_task 保留引用

```python
# 正确做法
task = asyncio.create_task(long_running_job())
# 保留 task 引用，防止被 GC 回收

# 错误做法
asyncio.create_task(long_running_job())  # 无引用，可能被 GC
```

**为什么需要保留引用？**
- Python GC 会在没有引用时将 task 对象回收
- 回收后 task 可能不会被执行，导致静默失败
- 保留引用确保 task 被执行完毕

### asyncio.to_thread 阻塞 IO

```python
# 音频拼接是 CPU/IO 密集型操作，需要在线程池中执行
result = await asyncio.to_thread(pydub_audio_concat, audio_files)
```

**为什么用 to_thread 而不是直接调用？**
- FastAPI 运行在 asyncio 事件循环上
- 阻塞操作会阻塞整个事件循环，影响其他请求
- `to_thread` 将阻塞操作放到线程池，不阻塞事件循环

**判断信号**：
- 工作流中有 `time.sleep()` → 应改为 `await asyncio.sleep()`
- 音频处理直接调用 → 应包裹在 `asyncio.to_thread` 中
- create_task 没有保留引用 → 可能被 GC

## 降级模式

AI 链路中的关键环节都有降级策略：

### LLM 改写降级

```
正常流程：原始稿件 → LLM 改写 → 口语化稿件
降级流程：原始稿件 → 模板替换 → 口语化稿件
```

- 当 LLM API 超时或返回错误时，使用模板降级
- 模板降级效果不如 LLM，但能保证流程不中断
- 降级期间记录告警日志

### TTS 合成降级

```
正常流程：文本 → 阿里云 NLS → 音频文件
降级流程：文本 → 跳过 → 标记待处理
```

- 当 TTS 服务不可用时，跳过该集
- 标记为 `pending_tts` 状态，后续重试
- 不影响其他已成功合成的集

### COS 上传降级

```
正常流程：音频文件 → 上传 COS → 返回 URL
降级流程：音频文件 → 本地临时存储 → 返回临时 URL
```

- 当 COS 不可用时，使用本地临时存储
- 后续有定时任务尝试重新上传到 COS
- 临时 URL 有时效限制

**判断信号**：
- LLM 调用失败直接抛出异常 → 应有降级策略
- TTS 失败导致整个工作流中断 → 应跳过当前集继续
- 没有降级日志记录 → 故障排查困难

## 配置驱动

所有可变的参数通过配置管理，不硬编码在代码中：

```python
# settings.py - 统一配置入口
class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    REDIS_URL: str = Field("redis://localhost:6379", env="REDIS_URL")
    LLM_API_KEY: str = Field(..., env="DASHSCOPE_API_KEY")
    CACHE_TTL_SEC: int = Field(3600, env="CACHE_TTL_SEC")
    WORKFLOW_MAX_RETRIES: int = Field(3, env="WORKFLOW_MAX_RETRIES")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

settings = Settings()
```

**设计意图**：
- 不同环境（dev/staging/prod）使用不同的 .env 文件
- 配置变更无需修改代码，重启即可生效
- 敏感信息（API Key）通过环境变量注入，不提交到代码库

**判断信号**：
- 代码中出现硬编码的 URL/Key → 应移到配置
- 不同环境需要改代码才能切换 → 应使用配置驱动
- 配置分散在多个文件中 → 应统一到 settings.py
