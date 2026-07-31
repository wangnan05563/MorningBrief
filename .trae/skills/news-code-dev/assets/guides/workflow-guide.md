# 工作流开发指南

本文档面向 MorningBrief 项目工作流开发，涵盖 RSS 抓取、LLM 改写、TTS 合成、敏感词过滤、音频处理和调度器等核心模块。

## 1. 工作流架构总览

### 整体流程

```
RSS 源 → 抓取新闻 → LLM 改写 → 敏感词过滤 → TTS 合成 → 音频拼接 → 审核发布
                                          ↓
                                    (降级: 跳过)
                                          ↓
                                    (告警通知)
```

### 状态机设计

每个工作流实例（一次完整的新闻播报生成）有一个状态：

```python
class WorkflowStatus(Enum):
    PENDING = "pending"      # 等待调度
    RUNNING = "running"      # 正在执行
    SUCCESS = "success"      # 完成
    FAILED = "failed"        # 失败（可重试）
    CANCELLED = "cancelled"  # 已取消
```

**为什么使用状态机**：
- 可追踪工作流进度
- 支持断点续传（失败后从当前步骤继续）
- 便于监控和告警

### 调度器设计

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# 每小时执行一次新闻抓取
scheduler.add_job(
    fetch_and_process,
    trigger='cron',
    hour='*',
    misfire_grace_time=300,  # 允许 5 分钟延迟
    coalesce=True,  # 合并错过的执行
)
```

## 2. RSS 爬虫开发

### RSS 抓取服务

```python
"""RSS 源管理 - 负责从配置的 RSS 源抓取新闻。"""
import logging
from typing import list
from xml.etree import ElementTree

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RSSFetcher:
    """RSS 源抓取器。"""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self.client = http_client or httpx.AsyncClient(
            timeout=settings.RSS_FETCH_TIMEOUT
        )

    async def fetch_feeds(self, feed_urls: list[str]) -> list[dict]:
        """从多个 RSS 源抓取新闻。"""
        all_items = []
        tasks = [self._fetch_feed(url) for url in feed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for url, result in zip(feed_urls, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch RSS from {url}: {result}")
                continue
            all_items.extend(result)
        
        return all_items

    async def _fetch_feed(self, url: str) -> list[dict]:
        """抓取单个 RSS 源。"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return self._parse_xml(response.text)
        except httpx.HTTPError as e:
            logger.warning(f"RSS fetch failed for {url}: {e}")
            return []

    def _parse_xml(self, xml_content: str) -> list[dict]:
        """解析 RSS XML，提取新闻条目。"""
        root = ElementTree.fromstring(xml_content)
        items = []
        
        for item in root.findall('.//item'):
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            pub_date = item.findtext('pubDate', '')
            description = item.findtext('description', '')
            
            if title and link:
                items.append({
                    "title": title.strip(),
                    "link": link.strip(),
                    "pub_date": pub_date,
                    "description": description.strip()[:500],  # 限制长度
                })
        
        return items
```

### 去重逻辑

**为什么需要去重**：同一新闻可能出现在多个 RSS 源中。

```python
class NewsDeduplicator:
    """新闻去重器。"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def is_duplicate(self, link: str) -> bool:
        """检查链接是否已存在（基于 URL 去重）。"""
        key = f"news:dedup:{hashlib.md5(link.encode()).hexdigest()}"
        exists = await self.redis.exists(key)
        if not exists:
            # 标记为已处理，TTL 7 天
            await self.redis.setex(key, 7 * 86400, "1")
        return bool(exists)

    async def filter_duplicates(self, items: list[dict]) -> list[dict]:
        """批量去重。"""
        unique_items = []
        for item in items:
            if not await self.is_duplicate(item["link"]):
                unique_items.append(item)
        return unique_items
```

## 3. LLM 改写开发

### LLM 改写服务

```python
"""LLM 改写服务 - 将新闻稿件改写为口语化表达。"""
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# LLM Prompt 模板
NEWS_REWRITE_PROMPT = """你是一个专业的新闻播客撰稿人。请将以下新闻稿件改写为适合口播的播客稿。

要求：
1. 语言口语化，像朋友聊天一样自然
2. 保留关键事实和数据
3. 适当添加过渡语和连接词
4. 控制在 500 字以内
5. 不要添加原文没有的信息

原始稿件：
{content}

请输出改写后的播客稿："""


class LLMRewriteService:
    """LLM 改写服务。"""

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self.client = http_client or httpx.AsyncClient(
            timeout=settings.LLM_TIMEOUT,
            headers={
                "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        self.api_url = settings.LLM_API_URL

    async def rewrite(self, content: str, max_retries: int = 3) -> str:
        """改写新闻稿件，支持重试。"""
        prompt = NEWS_REWRITE_PROMPT.format(content=content)
        
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    self.api_url,
                    json={
                        "model": settings.LLM_MODEL,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except httpx.HTTPError as e:
                logger.warning(
                    f"LLM rewrite attempt {attempt + 1} failed: {e}"
                )
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except (KeyError, IndexError) as e:
                logger.error(f"Unexpected LLM response format: {e}")
                raise

    async def rewrite_with_fallback(self, content: str) -> str:
        """改写，失败时使用模板降级。"""
        try:
            return await self.rewrite(content)
        except Exception as e:
            logger.warning(f"LLM rewrite failed, using fallback: {e}")
            return self._template_rewrite(content)

    def _template_rewrite(self, content: str) -> str:
        """模板降级：简单截取前 N 字。"""
        if len(content) <= 200:
            return content
        return content[:200] + "..."
```

### Prompt 管理

**为什么 Prompt 要单独管理**：
- Prompt 变更频繁，不应硬编码在代码中
- 便于 A/B 测试不同 Prompt 的效果
- 支持不同场景使用不同 Prompt

```python
# prompts/news_rewrite_v1.json
{
    "system": "你是一个专业的新闻播客撰稿人...",
    "template": "请将以下新闻稿件改写为适合口播的播客稿...",
    "params": {
        "temperature": 0.7,
        "max_tokens": 1000
    }
}
```

## 4. 敏感词过滤开发

### AC 自动机过滤器

```python
"""敏感词过滤 - 使用 AC 自动机高效匹配敏感词。"""
import logging
from aho_corasick import AhoCorasick

logger = logging.getLogger(__name__)


class SensitiveWordFilter:
    """敏感词过滤器（AC 自动机实现）。"""

    def __init__(self):
        self.ac = AhoCorasick()
        self._loaded = False

    def load_words(self, words: list[str]):
        """加载敏感词列表。"""
        for word in words:
            self.ac.add(word.strip())
        self.ac.compile()
        self._loaded = True
        logger.info(f"Loaded {len(words)} sensitive words")

    def check(self, text: str) -> dict:
        """检查文本是否包含敏感词。
        
        Returns:
            {"matched": bool, "words": [...], "positions": [...]}
        """
        if not self._loaded:
            logger.error("Sensitive word filter not initialized")
            return {"matched": False, "words": [], "positions": []}

        matches = list(self.ac.scan(text))
        return {
            "matched": len(matches) > 0,
            "words": [m[0] for m in matches],
            "positions": [m[1] for m in matches],
        }

    def replace(self, text: str, replacement: str = "***") -> str:
        """替换敏感词。"""
        result = text
        for word, _ in self.ac.scan(text):
            result = result.replace(word, replacement)
        return result
```

**为什么在启动时初始化**：AC 自动机构建是 CPU 密集型操作，延迟加载会导致首次请求超时。

### 词库管理

```python
# 词库文件格式（words.txt）
# 每行一个敏感词
政治敏感词1
政治敏感词2
...

# 加载词库
async def load_sensitive_words() -> list[str]:
    """从数据库或文件加载敏感词库。"""
    # 优先从数据库加载（支持动态更新）
    stmt = select(SensitiveWordModel)
    result = await db.execute(stmt)
    words = [row.word for row in result.scalars()]
    return words
```

## 5. TTS 合成开发

### 阿里云 NLS TTS 服务

```python
"""TTS 合成服务 - 使用阿里云 NLS 将文本转为语音。"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class TTSService:
    """TTS 合成服务。"""

    def __init__(self, http_client=None):
        self.client = http_client or httpx.AsyncClient(
            timeout=settings.TTS_TIMEOUT
        )
        self.app_key = settings.TTS_APP_KEY

    async def synthesize(self, text: str, voice: str = "xiaoyan") -> dict:
        """合成语音，返回任务 ID。
        
        阿里云 TTS 是异步 API：
        1. 提交合成任务，获得 task_id
        2. 轮询 task_id 状态
        3. 完成后下载音频文件
        """
        # 步骤 1：提交任务
        submit_url = "https://nls-speech.cn-shanghai.aliyuncs.com/tts/start"
        response = await self.client.post(submit_url, json={
            "app_key": self.app_key,
            "text": text,
            "voice": voice,
            "format": "mp3",
            "sample_rate": 16000,
        })
        response.raise_for_status()
        result = response.json()
        task_id = result["task_id"]
        
        # 步骤 2：轮询状态
        audio_url = await self._poll_task(task_id)
        
        # 步骤 3：下载音频
        audio_data = await self._download_audio(audio_url)
        
        return {
            "task_id": task_id,
            "audio_data": audio_data,
            "format": "mp3",
        }

    async def _poll_task(self, task_id: str, max_attempts: int = 30) -> str:
        """轮询 TTS 任务状态。"""
        for _ in range(max_attempts):
            status_url = f"https://nls-speech.cn-shanghai.aliyuncs.com/tts/task/status?task_id={task_id}"
            response = await self.client.get(status_url)
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "completed":
                return result.get("audio", "")
            
            if result.get("status") == "failed":
                raise TTSError(f"TTS task failed: {result}")
            
            await asyncio.sleep(1)
        
        raise TTSError(f"TTS task timeout: {task_id}")

    async def _download_audio(self, url: str) -> bytes:
        """下载音频文件。"""
        response = await self.client.get(url)
        response.raise_for_status()
        return response.content
```

### 任务降级

**为什么需要降级**：TTS 服务可能不可用，不能让整个工作流中断。

```python
async def synthesize_with_fallback(self, text: str) -> Optional[bytes]:
    """TTS 合成，失败时返回 None（跳过该段）。"""
    try:
        result = await self.synthesize(text)
        return result["audio_data"]
    except TTSError as e:
        logger.error(f"TTS synthesis failed: {e}")
        # 记录告警
        await alert_service.send("TTS合成失败", str(e))
        return None
```

## 6. 音频后处理开发

### 音量归一化和静音切除

```python
"""音频后处理 - 音量归一化、静音切除。"""
import logging
from io import BytesIO

from pydub import AudioSegment
from pydub.silence import detect_nonsilent

logger = logging.getLogger(__name__)


class AudioProcessor:
    """音频处理器。"""

    TARGET_VOLUME_DB = -20.0  # 目标音量（dB）

    def normalize_volume(self, audio: AudioSegment) -> AudioSegment:
        """归一化音频音量。"""
        difference = self.TARGET_VOLUME_DB - audio.dBFS
        return audio.apply_gain(difference)

    def remove_silence(
        self, audio: AudioSegment, min_silence_len: int = 500, silence_thresh: int = -30
    ) -> AudioSegment:
        """切除静音段。
        
        Args:
            audio: 输入音频
            min_silence_len: 最小静音长度（毫秒）
            silence_thresh: 静音阈值（dB）
        """
        nonsilent_data = []
        for start, end in detect_nonsilent(
            audio, min_silence_len=min_silence_len, threshold=silence_thresh
        ):
            nonsilent_data.append(audio[start:end])
        
        if not nonsilent_data:
            return audio
        
        return nonsilent_data[0] + b"".join(
            [bytes(b) for b in nonsilent_data[1:]]
        )

    def process(self, audio: AudioSegment) -> AudioSegment:
        """完整处理流程。"""
        audio = self.normalize_volume(audio)
        audio = self.remove_silence(audio)
        return audio
```

**为什么用 to_thread**：pydub 是同步库，直接在事件循环中执行会阻塞。

```python
async def process_audio_async(self, audio_bytes: bytes) -> bytes:
    """异步包装音频处理。"""
    loop = asyncio.get_event_loop()
    audio = await loop.run_in_executor(
        None, lambda: AudioSegment.from_mp3(BytesIO(audio_bytes))
    )
    processed = self.process(audio)
    output = BytesIO()
    processed.export(output, format="mp3")
    return output.getvalue()
```

## 7. 音频拼接开发

### 多集音频拼接

```python
"""音频拼接 - 将多集 TTS 音频合并为完整播报。"""
import logging
from typing import list

from pydub import AudioSegment

logger = logging.getLogger(__name__)


class AudioConcatenator:
    """音频拼接器。"""

    def concatenate(self, audio_segments: list[AudioSegment]) -> AudioSegment:
        """拼接多个音频片段。"""
        if not audio_segments:
            return AudioSegment.silent(duration=0)
        
        # 添加间隔静音（每集之间 0.5 秒静音）
        silence = AudioSegment.silent(duration=500)
        result = audio_segments[0]
        
        for segment in audio_segments[1:]:
            result = result + silence + segment
        
        return result

    async def concatenate_async(self, audio_files: list[str]) -> bytes:
        """异步拼接音频文件。"""
        # 使用 to_thread 避免阻塞事件循环
        loop = asyncio.get_event_loop()
        
        def _concatenate():
            segments = [AudioSegment.from_mp3(f) for f in audio_files]
            concatenated = self.concatenate(segments)
            output = BytesIO()
            concatenated.export(output, format="mp3")
            return output.getvalue()
        
        return await asyncio.to_thread(_concatenate)
```

## 8. 调度器开发

### APScheduler 配置

```python
"""调度器管理 - 使用 APScheduler 定时触发工作流。"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.workflows.news_workflow import NewsWorkflow

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """工作流调度器。"""

    def __init__(self, redis_client):
        self.scheduler = AsyncIOScheduler()
        self.redis = redis_client
        self.workflow = NewsWorkflow(redis_client)

    def start(self):
        """启动调度器。"""
        # 每小时整点执行新闻抓取和处理
        self.scheduler.add_job(
            self._fetch_and_process,
            trigger=CronTrigger(minute=0),
            id="news_fetch_job",
            name="每小时新闻抓取",
            misfire_grace_time=300,
            coalesce=True,
        )
        
        # 每天凌晨 2 点执行审核巡检
        self.scheduler.add_job(
            self._audit_check,
            trigger=CronTrigger(hour=2, minute=0),
            id="audit_check_job",
            name="审核巡检",
        )
        
        # 每天凌晨 3 点执行缓存预热
        self.scheduler.add_job(
            self._warmup_cache,
            trigger=CronTrigger(hour=3, minute=0),
            id="warmup_cache_job",
            name="缓存预热",
        )
        
        self.scheduler.start()
        logger.info("Workflow scheduler started")

    async def _fetch_and_process(self):
        """抓取并处理新闻。"""
        task_id = f"batch_{int(time.time())}"
        logger.info(f"Starting batch workflow: {task_id}")
        
        # 获取分布式锁
        lock_key = f"workflow:lock:batch:{task_id}"
        acquired = await self.redis.set(lock_key, "1", nx=True, ex=3600)
        if not acquired:
            logger.info(f"Batch workflow {task_id} already running, skipping")
            return
        
        try:
            await self.workflow.execute_batch(task_id)
        except Exception as e:
            logger.exception(f"Batch workflow {task_id} failed")
            await alert_service.send("工作流失败", str(e))
        finally:
            await self.redis.delete(lock_key)

    async def _audit_check(self):
        """审核巡检：扫描超时未审核的内容。"""
        overdue_count = await self.workflow.check_overdue_audits()
        if overdue_count > 0:
            logger.warning(f"Found {overdue_count} overdue audit items")
            await alert_service.send(
                "审核超时告警",
                f"有 {overdue_count} 条内容超过 24 小时未审核"
            )
```

### 锁和重试

**为什么工作流需要锁**：防止同一批次被多次触发。

```python
async def execute_batch(self, task_id: str):
    """执行批量工作流。"""
    # 状态更新为 running
    await self._update_status(task_id, WorkflowStatus.RUNNING)
    
    try:
        # 1. 抓取 RSS
        items = await self.rss_fetcher.fetch_feeds(settings.RSS_FEED_URLS)
        
        # 2. 去重
        items = await self.deduplicator.filter_duplicates(items)
        
        # 3. LLM 改写
        for item in items:
            item["rewritten"] = await self.llm.rewrite_with_fallback(
                item["description"]
            )
        
        # 4. 敏感词过滤
        for item in items:
            check_result = self.sensitive_filter.check(item["rewritten"])
            if check_result["matched"]:
                logger.warning(f"News contains sensitive words: {check_result['words']}")
                item["status"] = "blocked"
                continue
        
        # 5. TTS 合成
        for item in items:
            if item.get("status") == "blocked":
                continue
            audio = await self.tts.synthesize_with_fallback(item["rewritten"])
            if audio:
                item["audio_data"] = audio
        
        # 6. 入库
        await self._save_to_database(items)
        
        # 状态更新为 success
        await self._update_status(task_id, WorkflowStatus.SUCCESS)
        
    except Exception as e:
        await self._update_status(task_id, WorkflowStatus.FAILED)
        raise
```

## 9. 工作流重跑/重试语义

### 重跑应在原工作流上执行，不创建新工作流

**为什么**：工作流重跑（retry）的目标是从指定步骤开始重新执行，复用上游成功步骤的产物。如果重跑时创建新工作流，会丢失原工作流的执行历史和上游成功产物，无法实现断点续跑；同时原工作流的状态会停留在 failed，污染监控统计。

**判断逻辑**：
- 重跑必须在原工作流上执行（复用原 `workflow_id`），不创建新工作流
- 全新工作流触发应使用 `trigger_workflow`，而不是重跑接口
- 重跑前必须校验：`from_step` 之前的步骤必须 success 且有 result

**固定流程**：
1. 校验前驱步骤：`from_step` 之前的所有步骤状态为 success 且有 result 产物
2. 删除步骤记录：删除 `from_step` 及其之后的所有步骤记录
3. 重置工作流状态：将工作流状态重置为 `queued`
4. 入队重跑：将当前 `workflow_id` 入队等待调度器执行
5. 调度器从 `from_step` 开始执行，复用前驱步骤的 result 产物

**正确做法**：
```python
# ✅ 在原工作流上重跑，复用 workflow_id
async def retry_from_step(self, workflow_id: str, from_step: str) -> dict:
    """在原工作流上从指定步骤重跑。

    规则：
    1. 校验 from_step 之前的步骤必须 success 且有 result
    2. 删除 from_step 及之后步骤记录
    3. 重置工作流状态为 queued
    4. 入队当前 workflow_id（不创建新工作流）
    """
    # 1. 前驱校验：from_step 之前的步骤必须 success 且有 result
    upstream_steps = await self._get_steps_before(workflow_id, from_step)
    for step in upstream_steps:
        if step.status != "success" or step.result is None:
            raise BusinessError(
                f"重跑 {from_step} 需要前驱步骤 {step.name} 成功且有产物，"
                f"当前状态: {step.status}"
            )

    # 2. 删除 from_step 及之后步骤记录
    await self.db.execute(
        delete(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .where(WorkflowStep.step_order >= from_step_order)
    )

    # 3. 重置工作流状态为 queued
    await self.db.execute(
        update(Workflow)
        .where(Workflow.id == workflow_id)
        .values(status="queued", started_at=None, completed_at=None)
    )
    await self.db.commit()

    # 4. 入队当前 workflow_id（不创建新工作流）
    await self.scheduler.enqueue(workflow_id)
    return {"workflow_id": workflow_id, "from_step": from_step}
```

**错误做法**：
```python
# ❌ 创建新工作流，丢失原工作流历史和上游产物
async def retry_from_step(self, original_workflow_id: str, from_step: str) -> dict:
    new_workflow_id = generate_uuid()  # 创建新工作流
    # 复制原工作流的上游产物到新工作流（复杂且易错）
    await self._copy_upstream_results(original_workflow_id, new_workflow_id, from_step)
    await self.scheduler.enqueue(new_workflow_id)  # 入队新工作流
    return {"workflow_id": new_workflow_id}  # 返回新 ID，前端跳转新页面

# ❌ 未校验前驱步骤，from_step 之前的步骤可能失败或无产物
async def retry_from_step(self, workflow_id: str, from_step: str) -> dict:
    await self.db.execute(
        update(Workflow).where(Workflow.id == workflow_id).values(status="queued")
    )
    await self.scheduler.enqueue(workflow_id)  # 前驱步骤可能无 result，重跑会失败

# ❌ 全新工作流触发用重跑接口
async def trigger_new_workflow(self):
    # 应使用 trigger_workflow，而不是创建一个 failed 工作流再重跑
    wf = await self._create_workflow(status="failed")
    await self.retry_from_step(wf.id, "crawl")  # 误用重跑接口
```

**规则**：
- 重跑接口必须复用原 `workflow_id`，禁止创建新工作流
- 重跑前必须校验 `from_step` 之前的步骤状态为 success 且有 result
- 删除 `from_step` 及之后步骤记录，重置工作流状态为 queued
- 入队当前 `workflow_id`，调度器从 `from_step` 开始执行
- 全新工作流触发应使用 `trigger_workflow`，不是重跑接口

**适用场景**：工作流任意步骤重跑、断点续跑、失败后从指定步骤恢复
**不适用场景**：全新工作流触发（应用 `trigger_workflow`）、工作流取消后重新触发
