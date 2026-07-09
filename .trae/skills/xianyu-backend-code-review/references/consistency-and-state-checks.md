# 一致性与状态检测审查（Consistency & State Checks）

> **配套技能**：[xianyu-backend-code-review](../SKILL.md)
> **重点**：跨字段一致性 / 多入口参数一致性 / 性能优化 / 异常脱敏 / 计数器语义 / 状态检测关键词覆盖 / 问题排查方法论
> **复盘来源**：实时搜索与后台搜索结果不一致、价格采集优先级错配、DOM 选择器过宽、N+1 查询、异常消息泄露 token、计数器语义漂移、状态关键词遗漏、修复后无验证日志等问题复盘
> **配置驱动**：所有阈值、关键词清单、字段优先级等参数在 `config.yaml` 的 `consistency_and_state_checks` 节点管理，不硬编码

---

## 维度 18: 跨字段一致性与多入口参数一致性

### B-REVIEW-MULTI-ENTRY-PARAM-MERGE

- **检查点名称**：多入口调用参数合并一致性
- **所属维度**：维度 18 跨字段一致性与多入口参数一致性
- **问题描述**：Live 搜索只用 `task.search_filters`，不合并全局 `search.filter_tags`；而 Worker 搜索合并两者。导致实时搜索与后台搜索结果不一致——同样的关键词在不同入口得到不同结果集，用户难以复现和排查。
- **检查方法**：grep 所有调用 `collector.search` / `live_search` 的入口（api 路由、worker、调度器、CLI），逐一确认参数合并逻辑是否一致；如不一致必须提取为独立函数复用。
- **正面示例**：
```python
# 提取为独立函数，所有入口复用同一逻辑
def _merge_search_filters(task_filters: list[str], global_filters: list[str]) -> list[str]:
    """合并任务级与全局级过滤标签，保持顺序并去重。"""
    seen = set(task_filters)
    result = list(task_filters)
    for f in global_filters:
        if f not in seen:
            result.append(f)
            seen.add(f)
    return result

# Worker 入口
combined = _merge_search_filters(task.search_filters or [], config.search.filter_tags)
# Live 入口（与 Worker 完全一致）
combined = _merge_search_filters(task.search_filters or [], config.search.filter_tags)
```
- **反面示例**：
```python
# Worker 合并全局配置，Live 不合并（行为不一致）
# Worker:
combined = list(set(task_filters + global_filters))
# Live:
filters = task.get("search_filters") or []
```
- **适用场景**：任何有多入口调用同一底层 API 的场景（搜索 / 采集 / 通知 / 下单）
- **不适用场景**：明确需要差异化的场景（如 fast 模式跳过某些过滤）

---

### B-REVIEW-CONFIG-KEY-MATCH

- **检查点名称**：配置值格式与映射表键名匹配
- **所属维度**：维度 18 跨字段一致性与多入口参数一致性
- **问题描述**：`config.yaml` 的 `filter_tags` 配置为中文 `[包邮]`，但代码中 `XIANYU_FILTER_MAP` 键名是英文 `free_shipping`，导致配置项永远匹配不上映射表，运行时静默失效。
- **检查方法**：对比 `config.yaml` 中的枚举值与代码中映射表的键名，确认命名规范一致；新增配置项时双向校验配置文件与映射表；用 grep 验证配置项在映射表中存在。
- **正面示例**：
```python
# config.yaml 与代码键名严格对齐
# config.yaml: filter_tags: ["free_shipping"]
XIANYU_FILTER_MAP = {
    "free_shipping": {"filterTags": "postageFree"},
}

# 启动时校验配置项在映射表中存在
for tag in config.search.filter_tags:
    if tag not in XIANYU_FILTER_MAP:
        logger.warning("配置 filter_tags 含未知键名 {}，已忽略", tag)
```
- **反面示例**：
```python
# config.yaml 写中文，代码键名是英文 → 永远匹配不上
# config.yaml: filter_tags: ["包邮"]
XIANYU_FILTER_MAP = {"free_shipping": {"filterTags": "postageFree"}}
# 启动时不校验，配置静默失效
```
- **适用场景**：任何使用映射表 / 枚举的配置项（filter_tags / sort_type / regions / status 等）
- **不适用场景**：用户可读的展示文案（如前端 i18n 文本）

---

## 维度 8: 性能优化

### B-REVIEW-PRICE-FIELD-PRIORITY

- **检查点名称**：价格采集字段优先级
- **所属维度**：维度 8 性能优化
- **问题描述**：`_PRICE_KEYS` 优先取 `promoPrice`（促销价），与官网展示的 `price`（挂牌价）不一致，导致采集价格与用户实际看到的页面价格不符，影响抢单判断与历史价格分析。
- **检查方法**：grep `_PRICE_KEYS` 定义，确认 `price` 在 `promoPrice` 之前；价格字段优先级列表提取为模块级常量并注释排序理由。
- **正面示例**：
```python
# 优先取挂牌价（与官网展示一致），其次取促销价
_PRICE_KEYS = ("price", "promoPrice", "promotionPrice", "soldPrice", "originalPrice")
```
- **反面示例**：
```python
# 优先取促销价，与官网展示不符
_PRICE_KEYS = ("promoPrice", "promotionPrice", "price", ...)
```
- **适用场景**：任何从外部 API 采集价格字段（商品 / 订单 / 评估）
- **不适用场景**：明确需要采集促销价的场景（如促销活动分析）

---

### B-REVIEW-DOM-SELECTOR-EXCLUSION

- **检查点名称**：DOM 选择器干扰元素排除
- **所属维度**：维度 8 性能优化
- **问题描述**：`[class*='price']` 选择器过宽，匹配到原价 / 运费 / 划线价等非目标元素，导致价格提取错误（如取到运费 5 元而非商品价 100 元）。
- **检查方法**：grep 所有 CSS 选择器定义，确认含 `price` / `Price` 的选择器有 `:not()` 排除干扰元素；选择器列表提取为模块级常量便于统一维护。
- **正面示例**：
```python
# 排除原价 / 运费 / 划线价等干扰元素
_PRICE_SELECTOR = (
    "[class*='price--']:not([class*='original']):not([class*='postage'])"
    ":not([class*='shipping']):not([class*='line-through'])"
)
```
- **反面示例**：
```python
# 过宽选择器，匹配到原价 / 运费等
_PRICE_SELECTOR = "[class*='price--']"
```
- **适用场景**：任何从 DOM 提取特定字段的场景（价格 / 标题 / 销量 / 卖家）
- **不适用场景**：只有一个匹配元素的简单 DOM（无干扰元素）

---

### B-REVIEW-UNIT-CONVERSION-CONSISTENCY

- **检查点名称**：同类型解析函数单位转换一致性
- **所属维度**：维度 8 性能优化
- **问题描述**：`_coerce_price` 支持"万"单位转换（如 "1.2万" → 12000），但 `parse_price_from_text` 不支持，导致同一类数据在不同解析路径下结果不一致。
- **检查方法**：grep 所有价格解析函数（`_coerce_price` / `parse_price_from_text` / `_extract_price` 等），确认单位转换逻辑一致；公共逻辑提取为独立 helper 复用。
- **正面示例**：
```python
# 提取公共单位转换 helper
_WAN_PATTERN = re.compile(r"([\d.]+)\s*万")

def _convert_wan_unit(text: str) -> str:
    """统一处理 '万' 单位转换。"""
    def _replace(m: re.Match) -> str:
        return str(int(float(m.group(1)) * 10000))
    return _WAN_PATTERN.sub(_replace, text)

def _coerce_price(raw) -> float | None:
    text = _convert_wan_unit(str(raw))
    # ...

def parse_price_from_text(text: str) -> float | None:
    text = _convert_wan_unit(text)
    # ...
```
- **反面示例**：
```python
# 两个解析函数单位转换逻辑不一致
def _coerce_price(raw):
    if "万" in str(raw):
        return float(str(raw).replace("万", "")) * 10000
    # ...

def parse_price_from_text(text):
    # 不支持 "万" 单位
    return float(text)
```
- **适用场景**：任何有多个解析同一类型数据的函数（价格 / 销量 / 评分 / 时间）
- **不适用场景**：明确不需要单位转换的场景（如纯数字字段）

---

### B-REVIEW-BATCH-PREQUERY

- **检查点名称**：循环内数据库查询批量预查询
- **所属维度**：维度 8 性能优化
- **问题描述**：去重检查在循环内逐个查询数据库（`for item: repo.get_recently_collected_item_ids([item.id], window)`），导致 N+1 查询，N 个商品触发 N 次 DB 往返。
- **检查方法**：检查循环内是否有数据库查询，确认有批量预查询 + set / dict 缓存；循环前一次性查询所有 ID，循环内只查缓存。
- **正面示例**：
```python
# 循环前批量预查询
all_ids = [item.id for item in new_items]
recent_collected_cache = self.repo.get_recently_collected_item_ids(all_ids, window)

# 循环内用缓存，零 DB 查询
recent_ids = recent_collected_cache or set()
for item in new_items:
    if item.id in recent_ids:
        continue  # 已采集过，跳过
    # 处理新商品
```
- **反面示例**：
```python
# 循环内逐个查询，N+1 性能问题
for item in new_items:
    recent_ids = self.repo.get_recently_collected_item_ids([item.id], window)
    if item.id in recent_ids:
        continue
```
- **适用场景**：任何在循环内查询数据库的场景（去重 / 关联查询 / 状态检查）
- **不适用场景**：循环次数极少（≤ 3）或单次查询成本极低

---

### B-REVIEW-JSON-EXTRACT-QUERY

- **检查点名称**：JSON 字段查询用 json_extract 替代 LIKE
- **所属维度**：维度 8 性能优化
- **问题描述**：`payload.like('%"data_source"%')` 全表扫描且容易误匹配（如 `data_source_v2` 字段），应使用 `json_extract` 精准提取 JSON 字段值。
- **检查方法**：grep `.like(` 检查是否有 JSON 字段用了 LIKE 而非 `json_extract`；JSON 字段查询必须用 `func.json_extract(field, '$.key')` 精准匹配。
- **正面示例**：
```python
from sqlalchemy import func

# 精准提取 JSON 字段值，可走索引（如有表达式索引）
stmt = select(EventRow).where(
    func.json_extract(EventRow.payload, '$.data_source') == 'official'
)
```
- **反面示例**：
```python
# LIKE 全表扫描 + 可能误匹配
stmt = select(EventRow).where(
    EventRow.payload.like('%"data_source": "official"%')
)
```
- **适用场景**：SQLite / MySQL 的 JSON 字段查询（payload / config / metadata 等）
- **不适用场景**：非 JSON 字段的模糊查询（如 title LIKE '%关键词%')

---

## 维度 7: 安全性

### B-REVIEW-ERROR-SANITIZE

- **检查点名称**：异常消息脱敏
- **所属维度**：维度 7 安全性
- **问题描述**：`str(e)[:500]` 可能包含 token / Cookie / webhook URL 等敏感信息，写入日志或返回前端会泄露凭据。
- **检查方法**：grep `str(e)` / `str(exc)` / `repr(e)` 检查是否经过 `_sanitize_error` 处理；任何写入日志 / DB / 响应的异常消息必须脱敏。
- **正面示例**：
```python
# 统一脱敏函数，过滤 token / cookie / webhook 等敏感模式
_SENSITIVE_PATTERNS = [
    (re.compile(r"(token=)[^&\s]+"), r"\1***"),
    (re.compile(r"(cookie2=)[^;]+"), r"\1***"),
    (re.compile(r"(webhook_url=)[^\s]+"), r"\1***"),
]

def _sanitize_error(msg: str, max_len: int = 500) -> str:
    """脱敏异常消息中的敏感字段。"""
    for pattern, repl in _SENSITIVE_PATTERNS:
        msg = pattern.sub(repl, msg)
    return msg[:max_len]

error_msg = _sanitize_error(str(e))
logger.warning("采集失败 item={}: {}", item_id, error_msg)
```
- **反面示例**：
```python
# 直接截断，可能泄露 token / cookie
error_msg = str(e)[:500]
logger.warning("采集失败: %s", error_msg)  # 日志泄露
return {"detail": error_msg}  # 前端泄露
```
- **适用场景**：任何将异常消息存储或传输到外部的场景（日志 / DB / API 响应 / SSE 事件）
- **不适用场景**：仅在内存中处理的异常（不持久化 / 不传输）

---

## 维度 9: 异步与状态管理

### B-REVIEW-COUNTER-SEMANTICS

- **检查点名称**：计数器语义一致性
- **所属维度**：维度 9 异步与状态管理
- **问题描述**：`_consecutive_collect_failures` 成功时不清零，语义从"连续失败"漂移为"累计失败"，导致连续失败阈值提前触发误暂停。
- **检查方法**：检查所有 `_consecutive` / `_continuous` 命名的计数器，确认成功时有清零操作；命名必须与语义匹配（`_consecutive_*` 成功清零，`_total_*` 累计不清零）。
- **正面示例**：
```python
# 成功时清零，保持"连续失败"语义
async def collect(self, item_id: str) -> None:
    try:
        result = await self._do_collect(item_id)
        self._consecutive_collect_failures = 0  # 成功清零
        return result
    except Exception:
        self._consecutive_collect_failures += 1
        if self._consecutive_collect_failures >= self.threshold:
            await self._pause_on_failures()
```
- **反面示例**：
```python
# 成功时不清零，语义漂移为"累计失败"
async def collect(self, item_id):
    try:
        return await self._do_collect(item_id)
        # 缺少 self._consecutive_collect_failures = 0
    except Exception:
        self._consecutive_collect_failures += 1
```
- **适用场景**：任何有 `_consecutive` / `_continuous` 命名的计数器
- **不适用场景**：确实需要累计统计的计数器（应命名为 `_total_*`）

---

### B-REVIEW-ROUND-RESET

- **检查点名称**：新一轮处理重置上一轮状态
- **所属维度**：维度 9 异步与状态管理
- **问题描述**：连续失败计数器未在新一轮开始时重置，导致上一轮的失败累积到本轮，触发误暂停。
- **检查方法**：检查 `run_once` / 处理循环入口，确认跨轮次状态（计数器 / 标志位 / 临时缓存）有重置；重置时机在循环开始处明确注释。
- **正面示例**：
```python
async def run_once(self) -> None:
    """单轮处理入口：重置上一轮状态。"""
    # 新一轮开始，重置上一轮的连续失败计数
    self._consecutive_collect_failures = 0
    self._round_temp_cache.clear()
    logger.debug("新一轮处理开始，已重置上一轮状态")

    for item in self._pending_items():
        await self._process(item)
```
- **反面示例**：
```python
async def run_once(self):
    # 未重置 _consecutive_collect_failures，上一轮失败累积到本轮
    for item in self._pending_items():
        await self._process(item)
```
- **适用场景**：任何跨轮次累积的状态（计数器 / 临时缓存 / 标志位）
- **不适用场景**：需要跨轮次保留的历史数据（如历史价格趋势）

---

## 维度 11: 状态检测完整性

### B-REVIEW-STATUS-KEYWORD-COVERAGE

- **检查点名称**：状态检测关键词覆盖完整性
- **所属维度**：维度 11 状态检测完整性
- **问题描述**：`is_sold` 关键词未覆盖"宝贝不存在 / 走丢 / 已删除"等文案，导致已下架商品被误判为在售，持续推送给用户造成困扰。
- **检查方法**：grep 所有关键词检测列表（`is_sold` / `is_offline` / `is_blocked` 等），确认覆盖所有平台文案变体；定期用真实页面文本回归测试关键词覆盖率。
- **正面示例**：
```python
# 覆盖所有已售 / 下架 / 不存在的文案变体
SOLD_TEXT_KEYWORDS: tuple[str, ...] = (
    "已售", "已售出", "已售完", "已售罄", "宝贝已售", "商品已售",
    "已下架", "已卖出", "卖掉了",
    "宝贝不存在", "宝贝走丢了", "该宝贝不存在", "商品不存在",
    "已删除", "已被删除",
)

def check_text_sold(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in SOLD_TEXT_KEYWORDS)
```
- **反面示例**：
```python
# 只有一个关键词，覆盖不全
def is_sold(text: str) -> bool:
    return "已售" in text
```
- **适用场景**：任何通过文本关键词检测页面状态的场景（已售 / 下架 / 风控 / 限流）
- **不适用场景**：有明确 DOM 结构标识状态的场景（如 `<div class="sold-out">`）

---

### B-REVIEW-STATUS-KEYWORD-CONSTANT

- **检查点名称**：状态检测关键词提取为模块级常量
- **所属维度**：维度 11 状态检测完整性
- **问题描述**：关键词列表在函数内定义，多处消费点各自维护，新增文案时容易漏改。
- **检查方法**：确认关键词列表是模块级常量（`tuple` / `frozenset`），非函数内定义；多处消费点必须 import 同一常量复用。
- **正面示例**：
```python
# 模块级常量 + 纯函数复用
SOLD_TEXT_KEYWORDS: frozenset[str] = frozenset({
    "已售", "已售出", "已售完", "卖掉了", "已下架",
})

def check_text_sold(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in SOLD_TEXT_KEYWORDS)

# 多处消费点统一 import
from xianyu_hunter.modules.collector_utils import check_text_sold
```
- **反面示例**：
```python
# 函数内定义，多处重复维护
def _detail_parse(text):
    sold_keywords = ["已售", "已售出"]  # 函数内定义
    if any(kw in text for kw in sold_keywords):
        return True

def _parser_parse(text):
    if "已售" in text:  # 内联关键词，漏了"卖掉了"
        return True
```
- **适用场景**：任何有关键词列表的场景（状态检测 / 错误码识别 / 反爬识别）
- **不适用场景**：仅一次性使用的简单判断（如 `if status == "ok"`）

---

## 维度 13: 问题排查方法论

### B-REVIEW-DEBUG-LOG-AFTER-FIX

- **检查点名称**：修复后添加调试日志验证
- **所属维度**：维度 13 问题排查方法论
- **问题描述**：价格修复后未添加日志确认 DOM 提取的实际值，导致后续回归无法快速定位是采集错误还是修复未生效。
- **检查方法**：确认数据提取类修复有对应的调试日志，记录关键字段最终采用的值；日志级别用 `INFO`（生产可见）或 `DEBUG`（开发可见），不可省略。
- **正面示例**：
```python
# 修复后添加日志，便于回归验证
price = self._extract_price_from_dom(page)
logger.info(
    "详情页 {} 最终采用价格: {} (来源: {}, 候选: {})",
    item_id, price, price_source, price_candidates,
)
return price
```
- **反面示例**：
```python
# 修复后无日志，无法验证是否生效
price = self._extract_price_from_dom(page)
return price
```
- **适用场景**：任何涉及数据提取 / 转换的修复（价格 / 标题 / 状态 / 销量）
- **不适用场景**：纯逻辑修复（如条件判断 / 流程控制，无数据提取）

---

## 维度 14: Cookie 状态管理

### B-REVIEW-SESSION-COOKIE-TIMESTAMP

- **检查点名称**：Session Cookie 内嵌 timestamp 过期检测
- **所属维度**：维度 14 Cookie 状态管理
- **问题描述**：`_m_h5_tk` 等 session cookie 的 `expires=-1`（浏览器会话级），但值内嵌服务端 timestamp（格式 `{token}_{ts_ms}`）+ 服务端 TTL（默认 1200 秒）。仅看 `cookie.expires` 会误判为"永不过期"，导致已过期的 session cookie 仍被标记为有效，引发 RGV587_ERROR 反爬。同时，TokenRenewer 标记 session 失效后 `/cookies/layers` 又恢复 session valid，造成状态振荡。
- **检查方法**：grep `cookie_map` / `cookie_layers` / `sync_state_from_cookies` 构造处，确认均调用 `is_session_cookie_expired()` 过滤；检查函数实现是否解析 `{token}_{ts_ms}` 格式并按 TTL 判定。
- **正面示例**：
```python
# 模块级常量 + 配置驱动
_SESSION_COOKIE_TTL_SEC = 1200  # 默认值，运行时从 auth.session_cookie_ttl_sec 覆盖

def is_session_cookie_expired(cookie_value: str, ttl_sec: int | None = None) -> bool:
    """
    检测 session cookie 内嵌 timestamp 是否过期。

    为什么这么做：_m_h5_tk 等 cookie 的 expires=-1（session cookie），
    但值内嵌服务端 timestamp + TTL，仅看 expires 会误判有效。
    解析失败时保守返回 False（认为未过期），避免误把合法 cookie 判失效触发振荡。
    """
    if not cookie_value or "_" not in cookie_value:
        return False  # 解析失败保守返回 False
    try:
        ts_ms = int(cookie_value.rsplit("_", 1)[-1])
        ttl = ttl_sec if ttl_sec is not None else _SESSION_COOKIE_TTL_SEC
        return (time.time() * 1000 - ts_ms) / 1000 > ttl
    except (ValueError, IndexError):
        logger.warning("session cookie timestamp 解析失败，保守认为未过期")
        return False

# 所有 cookie_map 构造处统一过滤
cookie_map = {
    name: value for name, value in raw_cookies.items()
    if name not in session_cookie_names or not is_session_cookie_expired(value)
}
```
- **反面示例**：
```python
# 仅看 expires 字段，误判 session cookie 永不过期
cookie_map = {
    name: cookie.value for name, cookie in cookies.items()
    if cookie.expires == -1 or cookie.expires > time.time()  # ❌ 漏判内嵌 timestamp
}

# 解析失败返回 True，误判失效触发振荡
def is_expired(value: str) -> bool:
    try:
        return int(value.rsplit("_", 1)[-1]) < time.time() - 1200
    except Exception:
        return True  # ❌ 误判失效
```
- **适用场景**：Session Cookie 内嵌 timestamp 的过期检测（淘宝/天猫 `_m_h5_tk` / `_m_h5_tk_enc` 等）、多入口 cookie 状态聚合、cookie 分层管理（identity / session / tracking）
- **不适用场景**：纯持久化 cookie（`expires > 0` 由浏览器管理过期）、无 timestamp 内嵌的 session cookie、单入口无聚合场景

---

### B-REVIEW-COOKIE-FILTER-ENTRY-ALIGN

- **检查点名称**：多入口 cookie 过滤逻辑一致性
- **所属维度**：维度 14 Cookie 状态管理
- **问题描述**：TokenRenewer 用 `is_m5tk_expired` 标记 session 失效，但 `/cookies/layers` 端点的第一步 JSON 同步、第二步浏览器内存兜底、第三步 `force_restore_layers` 各自独立判断 cookie 有效性，部分入口过滤了过期 session cookie、部分入口没过滤，导致状态在"失效 ↔ 恢复"之间振荡。
- **检查方法**：grep 所有构造 `cookie_map` / `cookie_layers` 的入口（TokenRenewer / worker / api_anticrawl / cookie_rotator），确认均调用同一份 `is_session_cookie_expired()` 函数；禁止各入口各写一套判定逻辑。
- **正面示例**：
```python
# 所有入口统一引用同一函数
from xianyu_hunter.modules.cookie_utils import is_session_cookie_expired

# TokenRenewer 入口
if is_session_cookie_expired(m5tk_value):
    await self._invalidate_session_layer()

# /cookies/layers 第一步 JSON 同步
cookie_map = {n: v for n, v in raw.items() if not is_session_cookie_expired(v)}

# /cookies/layers 第二步浏览器内存兜底
browser_cookies = {n: v for n, v in await bc.cookies() if not is_session_cookie_expired(v)}
```
- **反面示例**：
```python
# TokenRenewer 自写一套判定
def _is_m5tk_expired(self, value: str) -> bool:
    ts = int(value.split("_")[-1])
    return time.time() - ts / 1000 > 1200  # 硬编码 TTL

# /cookies/layers 另写一套
cookie_map = {n: v for n, v in raw.items() if v}  # ❌ 不过滤过期 session cookie

# force_restore_layers 又一套
if collector.has_searched:
    self._restore_session_layer()  # ❌ 无视 timestamp 直接恢复
```
- **适用场景**：任何有多入口构造 cookie_map / cookie_layers 的场景（TokenRenewer / worker / API 端点 / force_restore）
- **不适用场景**：单入口单消费者的简单 cookie 处理

---

### B-REVIEW-SESSION-COOKIE-CONFIG

- **检查点名称**：Session Cookie TTL 与名单配置化
- **所属维度**：维度 14 Cookie 状态管理
- **问题描述**：TTL（1200 秒）和 cookie 名单（`_m_h5_tk` / `_m_h5_tk_enc`）硬编码在代码中，无法适应不同平台或服务端策略变更（如淘宝调整 TTL 为 1800 秒时需改代码重新部署）。
- **检查方法**：grep `1200` / `_m_h5_tk` 等魔法值，确认均从 `auth.session_cookie_ttl_sec` + `auth.session_cookie_names` 读取；`config/auth.yaml` 含对应配置项 + `*.example.yaml` 同步。
- **正面示例**：
```python
# config/auth.yaml
auth:
  session_cookie_ttl_sec: 1200  # 淘宝 _m_h5_tk 服务端 TTL
  session_cookie_names: ["_m_h5_tk", "_m_h5_tk_enc"]

# 代码中从配置读取
ttl = get_config().auth.session_cookie_ttl_sec
names = get_config().auth.session_cookie_names
```
- **反面示例**：
```python
# 硬编码 TTL 和 cookie 名
_SESSION_COOKIE_TTL = 1200  # ❌ 硬编码
_SESSION_COOKIE_NAMES = ["_m_h5_tk", "_m_h5_tk_enc"]  # ❌ 硬编码

def is_expired(value: str) -> bool:
    return int(value.split("_")[-1]) / 1000 + 1200 < time.time()  # ❌ 硬编码
```
- **适用场景**：任何有可变参数的 cookie 处理逻辑（TTL / 名单 / 域名）
- **不适用场景**：平台固定不变的 cookie 规则（如 `_tb_token_` 无 timestamp 内嵌）

---

## 配置参数总览

所有阈值、关键词清单、字段优先级等参数在 `config.yaml` 的 `consistency_and_state_checks` 节点管理：

```yaml
consistency_and_state_checks:
  # 维度 18: 跨字段一致性
  multi_entry_param_merge:
    enabled: true
    entry_scan_patterns: ["collector.search", "live_search", "worker.search"]
    require_shared_helper: true
  config_key_match:
    enabled: true
    mapping_tables: ["XIANYU_FILTER_MAP", "SORT_TYPE_MAP", "REGION_MAP"]
    validate_on_startup: true

  # 维度 8: 性能优化
  price_field_priority:
    enabled: true
    required_first_field: "price"
    price_keys_whitelist: ["price", "promoPrice", "promotionPrice", "soldPrice", "originalPrice"]
  dom_selector_exclusion:
    enabled: true
    exclusion_keywords: ["original", "postage", "shipping", "line-through"]
    audit_selectors: ["price", "title", "seller"]
  unit_conversion_consistency:
    enabled: true
    supported_units: ["万", "千", "亿"]
    function_patterns: ["_coerce_*", "parse_*_from_text", "_extract_*"]
  batch_prequery:
    enabled: true
    max_loop_query_count: 0  # 循环内 DB 查询数上限（0 = 禁止）
    cache_required: true
  json_extract_query:
    enabled: true
    json_field_patterns: ["payload", "config", "metadata", "extra"]
    use_json_extract: true

  # 维度 7: 安全性
  error_sanitize:
    enabled: true
    sensitive_patterns:
      - "token="
      - "cookie2="
      - "webhook_url="
      - "api_key="
      - "set-cookie:"
    max_length: 500

  # 维度 9: 异步与状态管理
  counter_semantics:
    enabled: true
    consecutive_patterns: ["_consecutive_*", "_continuous_*"]
    require_reset_on_success: true
  round_reset:
    enabled: true
    entry_functions: ["run_once", "_process_round", "_scheduler_tick"]
    reset_fields: ["_consecutive_*", "_round_temp_*"]

  # 维度 11: 状态检测完整性
  status_keyword_coverage:
    enabled: true
    audit_functions: ["is_sold", "is_offline", "is_blocked", "is_limited"]
    require_all_variants: true
  status_keyword_constant:
    enabled: true
    require_module_level: true
    allowed_types: ["tuple", "frozenset"]

  # 维度 13: 问题排查方法论
  debug_log_after_fix:
    enabled: true
    fix_categories: ["data_extraction", "price_calculation", "status_detection"]
    log_level: "INFO"

  # 维度 14: Cookie 状态管理
  session_cookie_timestamp:
    enabled: true
    require_timestamp_parse: true
    parse_fail_return_false: true  # 解析失败保守返回 False
    ttl_config_key: "auth.session_cookie_ttl_sec"
    ttl_default: 1200
  cookie_filter_entry_align:
    enabled: true
    entry_scan_patterns: ["cookie_map", "cookie_layers", "sync_state_from_cookies", "force_restore_layers"]
    require_shared_helper: "is_session_cookie_expired"
  session_cookie_config:
    enabled: true
    require_config_file: "config/auth.yaml"
    require_example_sync: true
    forbidden_hardcode_patterns: ["1200", "_m_h5_tk"]
```

---

## 审查 checklist

| 类别 | 检查项 |
|---|---|
| 多入口一致性 | 同一底层 API 的多个入口参数合并逻辑是否一致？是否提取为共享 helper？ |
| 配置键名匹配 | config.yaml 枚举值与代码映射表键名是否对齐？启动时是否校验？ |
| 价格字段优先级 | `_PRICE_KEYS` 中 `price` 是否在 `promoPrice` 之前？ |
| DOM 选择器排除 | 含 price/Price 的选择器是否有 `:not()` 排除干扰元素？ |
| 单位转换一致性 | 同类型解析函数的单位转换逻辑是否一致？是否提取公共 helper？ |
| 批量预查询 | 循环内是否有 DB 查询？是否改为循环前批量预查询 + 缓存？ |
| JSON 字段查询 | JSON 字段是否用 `json_extract` 而非 LIKE？ |
| 异常消息脱敏 | `str(e)` 是否经过 `_sanitize_error` 处理？是否泄露 token/cookie？ |
| 计数器语义 | `_consecutive_*` 计数器成功时是否清零？命名与语义是否匹配？ |
| 跨轮次重置 | `run_once` 入口是否重置上一轮的计数器 / 临时缓存？ |
| 状态关键词覆盖 | 状态检测关键词是否覆盖所有平台文案变体？ |
| 状态关键词常量化 | 关键词列表是否提取为模块级常量？多处消费是否复用？ |
| 修复后调试日志 | 数据提取类修复是否有调试日志记录最终采用值？ |
| Session Cookie timestamp 检测 | `_m_h5_tk` 等 session cookie 是否解析内嵌 timestamp 并按 TTL 判定过期？解析失败是否保守返回 False？ |
| 多入口过滤一致性 | 所有 `cookie_map` / `cookie_layers` 构造处是否统一调用 `is_session_cookie_expired()`？ |
| TTL 与名单配置化 | TTL 和 cookie 名单是否走 `config/auth.yaml`？是否有硬编码 `1200` / `_m_h5_tk`？ |

---

## 常用检查脚本

```bash
# grep 多入口调用 collector.search / live_search
rg "collector\.(search|live_search)" src/xianyu_hunter/

# grep _PRICE_KEYS 定义
rg "_PRICE_KEYS\s*=" src/xianyu_hunter/

# grep DOM 选择器含 price 但无 :not()
rg "\[class\*='price" src/xianyu_hunter/ | rg -v ":not\("

# grep 循环内 DB 查询
rg "for\s+\w+\s+in.*:" src/xianyu_hunter/ -A 3 | rg "repo\.|session\.|db\."

# grep JSON 字段用 LIKE 而非 json_extract
rg "\.like\(.*%.*%" src/xianyu_hunter/ | rg "payload|config|metadata"

# grep str(e) 未脱敏
rg "str\(e\)|str\(exc\)|repr\(e\)" src/xianyu_hunter/ | rg -v "_sanitize_error"

# grep _consecutive 计数器
rg "_consecutive_\w+\s*[+=]" src/xianyu_hunter/

# grep 状态关键词列表（函数内定义视为违规）
rg "(已售|卖掉了|已下架|宝贝不存在)" src/xianyu_hunter/

# grep cookie_map / cookie_layers 构造处，确认均调用 is_session_cookie_expired
rg "cookie_map\s*=" src/xianyu_hunter/ -A 2 | rg -v "is_session_cookie_expired"

# grep 硬编码 TTL 1200 或 cookie 名 _m_h5_tk（应走配置）
rg "(1200|_m_h5_tk)" src/xianyu_hunter/ | rg -v "config|example|test|default|注释"

# grep is_session_cookie_expired 实现是否解析 {token}_{ts_ms} 格式
rg "is_session_cookie_expired" src/xianyu_hunter/ -A 10 | rg "rsplit|split.*_"
```

---

## 维度 19: 命名一致性验证

> **复盘来源**：`AttributeError: 'XxxRepository' object has no attribute '_Session'` —— 类定义是 `self._session`（小写 s），外部模块调用 `repo._Session()`（大写 S），跨模块访问私有属性时大小写拼写错误。
> **配套规范**：[coding-standards.md §2.13 命名一致性验证](../../xianyu-hunter-dev/references/coding-standards.md#213-命名一致性验证)

### B-REVIEW-NAMING-CONSISTENCY

- **检查点名称**：类内属性命名一致性与跨模块引用匹配
- **所属维度**：维度 19 命名一致性验证
- **问题描述**：类内属性 `_session` 与外部调用 `_Session` 大小写不一致；类似还有 `_url` vs `_URL`、`_http_client` vs `_httpClient` 等。这类问题在 Python 中无编译期检查，运行时才抛 `AttributeError`，且堆栈跟踪可能距错误点很远（如属性在 `__init__` 定义、外部模块访问时才报错），定位成本高。
- **检查方法**：
  1. Grep 类定义的所有 `self._xxx` 属性名
  2. 对每个属性名生成大小写 / 单复数 / 前缀变体
  3. Grep 全代码库搜索变体，确认无拼写错误引用
  4. 重点检查跨模块引用（`import` 后访问的属性）
- **正面示例**：
```python
# 类内属性命名一致，外部通过公共方法访问
class HttpClient:
    def __init__(self, base_url: str):
        self._base_url = base_url        # snake_case
        self._session = aiohttp.ClientSession()
        self._MAX_RETRIES = 3            # 常量 UPPER_SNAKE

    async def get(self, path: str):
        # 类内访问自身属性
        return await self._session.get(f"{self._base_url}{path}")

# 外部模块通过公共方法访问
client = HttpClient("https://api.example.com")
data = await client.get("/users")  # ✅ 不直接引用 _base_url / _session
```
- **反面示例**：
```python
# 类内大小写不一致 + 外部引用拼写错误
class HttpClient:
    def __init__(self):
        self._Session = ...  # ❌ 大写 S，违反 PEP 8（实例属性应 snake_case）

# 外部引用
client._session()  # ❌ 大小写错误，应为 _Session
```
- **审查方法（属性名变体 Grep 法）**：

```bash
# 步骤 1：提取类定义的所有 self._xxx 属性名
rg "self\.(_[a-zA-Z]\w*)" src/xianyu_hunter/ -r '$1' | sort -u

# 步骤 2：对每个属性名生成变体（手动或脚本生成）
# 大小写变体：_session → _Session, _SESSION
# 单复数变体：_url → _urls, _urls → _url
# 前缀变体：_x → __x, x → _x

# 步骤 3：Grep 全代码库搜索变体（示例：检查 _session 的变体）
rg "\._(Session|SESSION|sessions)\b" src/xianyu_hunter/

# 步骤 4：重点检查跨模块引用
rg "from.*import.*\b\w+\b" src/xianyu_hunter/ -A 5 | rg "\._\w+"
```

- **关键约束**：
  - 类内属性命名必须全类一致（大小写、复数、前缀 `_` / `__`）
  - 实例属性用 `snake_case`，常量用 `UPPER_SNAKE_CASE`，私有用 `_` 前缀
  - 跨模块引用必须与定义完全一致（含大小写）
  - 跨模块访问 `_` 前缀私有属性应优先通过公共方法封装（详见 maintainability.md §B-REVIEW-PRIVATE-ATTR-ENCAPSULATION）

- **适用场景**：
  - 任何有类属性 / 实例属性的代码审查
  - 跨模块引用类属性的场景
  - 重命名属性后的回归检查
  - 多人协作项目中属性命名风格统一

- **不适用场景**：
  - 局部变量（函数内变量无跨模块访问问题）
  - 类型注解（TypeAlias / TypeVar 命名遵循独立规范）
  - 测试代码内部 Mock 对象的属性

---

## 参考

- 完整版审查要点：[SKILL.md](../SKILL.md)
- [编码与 I/O 审查](encoding-and-io.md)
- [项目编码规范](../../xianyu-hunter-dev/references/project-rules.md)
