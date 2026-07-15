# 错误处理规则

本文档定义 MorningBrief 项目的错误处理规则。

## 自定义异常体系

### 异常分类

```python
class NewsAPIError(Exception):
    """新闻 API 基础异常。"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(self.message)

class AuthenticationError(NewsAPIError):
    """认证失败。"""
    def __init__(self, message: str = "认证失败"):
        super().__init__(code=2000, message=message)

class AuthorizationError(NewsAPIError):
    """权限不足。"""
    def __init__(self, message: str = "权限不足"):
        super().__init__(code=2001, message=message)

class ValidationError(NewsAPIError):
    """参数校验失败。"""
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(code=1000, message=message)

class BusinessError(NewsAPIError):
    """业务规则失败。"""
    def __init__(self, message: str = "业务错误"):
        super().__init__(code=3000, message=message)

class ExternalServiceError(NewsAPIError):
    """第三方服务失败。"""
    def __init__(self, message: str = "外部服务错误"):
        super().__init__(code=4000, message=message)
```

### 错误码范围

| 范围 | 含义 | 示例 |
|------|------|------|
| 0 | 成功 | - |
| 1000-1999 | 参数校验 | 1001: 必填字段缺失 |
| 2000-2999 | 认证授权 | 2000: 认证失败 |
| 3000-3999 | 业务规则 | 3001: 审核未通过 |
| 4000-4999 | 第三方服务 | 4001: LLM 调用失败 |
| 5000-5999 | 系统错误 | 5000: 数据库连接失败 |

## 全局异常处理器

```python
@app.exception_handler(NewsAPIError)
async def handle_api_error(request: Request, exc: NewsAPIError):
    """处理自定义 API 异常。"""
    logger.warning(f"API error: code={exc.code}, message={exc.message}")
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "message": exc.message, "data": None}
    )

@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    """处理未预期的异常。"""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"code": 5000, "message": "服务器内部错误", "data": None}
    )
```

**为什么区分两类异常处理器**：
- 已知异常（NewsAPIError）返回友好错误信息
- 未知异常（Exception）不暴露内部细节，只返回通用错误

## 日志规范

### 日志级别使用

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| DEBUG | 调试信息（详细流程） | 变量值、中间结果 |
| INFO | 正常业务流程 | 请求开始/结束、状态变更 |
| WARNING | 异常情况但不影响流程 | 重试、降级、缓存未命中 |
| ERROR | 错误但不影响服务 | 单个请求失败、第三方调用失败 |
| CRITICAL | 严重错误，服务可能不可用 | 数据库连接断开、内存溢出 |

### 日志格式

```python
# 正确：结构化日志
logger.info(
    "News fetched successfully",
    extra={"news_id": news_id, "duration_ms": duration, "source": "rss"}
)

# 错误：字符串拼接
logger.info(f"News fetched: {news_id} in {duration}ms from rss")
```

**为什么使用 extra**：结构化日志便于 ELK 等日志系统采集和分析。

### 错误日志必须包含 traceback

```python
# 正确
try:
    await llm.rewrite(content)
except LLMError as e:
    logger.exception(f"LLM rewrite failed: content_id={content_id}")
    # logger.exception 自动包含 exc_info=True

# 错误
except LLMError as e:
    logger.error(f"LLM rewrite failed: {e}")  # 没有 traceback
```

## 错误传播

### 不要吞掉异常

```python
# 错误：静默失败
try:
    await process_news(item)
except Exception:
    pass  # 吞掉了异常，无法排查问题

# 正确：记录并处理
try:
    await process_news(item)
except Exception as e:
    logger.error(f"Failed to process news: {item['id']}", exc_info=True)
    # 可以选择：
    # 1. 抛出异常让上层处理
    # 2. 降级处理
    # 3. 标记为失败继续
```

### 工作流中的错误处理

```python
async def execute_step(self, step_name: str, func, *args):
    """执行工作流步骤，支持重试和降级。"""
    try:
        result = await func(*args)
        logger.info(f"Step {step_name} completed successfully")
        return StepResult(success=True, data=result)
    except DegradableError as e:
        # 可降级错误：使用降级策略
        logger.warning(f"Step {step_name} degraded: {e}")
        result = await self._degrade(step_name, *args)
        return StepResult(success=True, data=result, degraded=True)
    except UnrecoverableError as e:
        # 不可恢复错误：标记失败
        logger.error(f"Step {step_name} failed unrecoverably: {e}")
        return StepResult(success=False, error=str(e))
    except Exception as e:
        # 未知错误：记录并抛出
        logger.exception(f"Step {step_name} failed unexpectedly")
        raise
```

## 前端错误处理

### 统一错误提示

```typescript
// 响应拦截器中统一处理
request.interceptors.response.use(
  (response) => {
    const { code, message } = response.data
    if (code !== 0) {
      ElMessage.error(message || '请求失败')
      return Promise.reject(new Error(message))
    }
    return response.data
  },
  (error) => {
    // HTTP 错误（4xx, 5xx）
    const message = error.response?.data?.message || '网络错误'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)
```

### 用户友好的错误信息

```typescript
// 不要直接暴露技术细节给用户
// 错误：ElMessage.error('Database connection timeout at line 42')

// 正确：使用业务语言
ElMessage.error('服务暂时不可用，请稍后重试')
```
