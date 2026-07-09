# 异步并发规则

本文档定义 20_News 项目的异步并发开发规则。

## asyncio.create_task 规则

### 必须保留引用

```python
# 正确：保留 task 引用
task = asyncio.create_task(process_item(item))
task.add_done_callback(lambda t: logger.info(f"Done: {t.result()}"))

# 错误：无引用，可能被 GC 回收
asyncio.create_task(process_item(item))
```

**为什么**：Python GC 会在没有引用时回收 task 对象，导致 task 不被执行。

### 批量任务管理

```python
async def process_batch(items: list):
    """批量处理任务。"""
    tasks = []
    for item in items:
        task = asyncio.create_task(process_single(item))
        tasks.append(task)
    
    # 等待所有任务完成
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 检查异常
    for item, result in zip(items, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to process {item}: {result}")
```

## asyncio.to_thread 规则

### 阻塞操作必须使用 to_thread

```python
# 正确：阻塞操作放线程池
async def process_audio(file_path: str):
    loop = asyncio.get_event_loop()
    result = await asyncio.to_thread(load_audio_file, file_path)
    return result

# 错误：直接调用阻塞函数
async def process_audio_bad(file_path: str):
    result = load_audio_file(file_path)  # 阻塞事件循环！
    return result
```

**为什么**：FastAPI 运行在 asyncio 事件循环上，阻塞操作会阻塞所有其他请求。

### 适用场景

以下操作需要包裹在 `asyncio.to_thread` 中：
- pydub 音频处理
- PIL 图像处理
- 正则表达式复杂匹配
- 任何同步第三方库调用

## 异步 HTTP 请求

### 使用 httpx.AsyncClient

```python
# 正确：异步 HTTP 客户端
async def fetch_multiple(urls: list[str]) -> list[str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        responses = await asyncio.gather(
            *[client.get(url) for url in urls],
            return_exceptions=True
        )
        return [
            r.text if isinstance(r, httpx.Response) else str(r)
            for r in responses
        ]

# 错误：使用同步 requests
def fetch_bad(urls: list[str]) -> list[str]:
    results = []
    for url in urls:
        response = requests.get(url)  # 阻塞！
        results.append(response.text)
    return results
```

## 并发控制

### 使用 Semaphore 限制并发数

```python
# 限制并发 RSS 抓取数量为 5
rss_semaphore = asyncio.Semaphore(5)

async def fetch_with_limit(url: str):
    async with rss_semaphore:
        return await client.get(url)
```

**为什么**：避免同时发起过多请求导致：
- 被目标网站封禁
- 本地内存溢出
- 网络带宽耗尽

## 异步锁

### 使用 asyncio.Lock 保护共享资源

```python
class Counter:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._count = 0
    
    async def increment(self):
        async with self._lock:
            self._count += 1
```

**注意**：分布式场景（多 worker）使用 Redis 锁而非 asyncio.Lock。

## 事件循环最佳实践

### 禁止使用 time.sleep

```python
# 错误
time.sleep(1)  # 阻塞事件循环

# 正确
await asyncio.sleep(1)  # 不阻塞
```

### 避免在回调中使用 await

```python
# 错误：回调中不能直接使用 await
task = asyncio.create_task(some_async_func())
task.add_done_callback(lambda t: await process_result(t.result()))

# 正确：使用单独的协程处理
async def handle_task_done(task):
    try:
        result = task.result()
        await process_result(result)
    except Exception as e:
        logger.error(f"Task failed: {e}")

task = asyncio.create_task(some_async_func())
task.add_done_callback(lambda t: asyncio.create_task(handle_task_done(t)))
```
