# 安全规则

本文档定义 MorningBrief 项目的安全开发规则，涵盖认证、授权、数据安全等方面。

## JWT 安全

### Token 验证

- 必须使用 `hmac.compare_digest` 比较 token，防止时序攻击
- Token .secret 必须从环境变量读取，禁止硬编码
- Token 必须设置合理的过期时间（建议 24 小时）

```python
import hmac

# 正确
if not hmac.compare_digest(provided_token, expected_token):
    raise AuthenticationError("Token 无效")

# 错误
if provided_token != expected_token:  # 时序攻击风险
    raise AuthenticationError("Token 无效")
```

### Token 黑名单

- 退出登录时必须将 token 加入 Redis 黑名单
- 黑名单 key 设置 TTL 等于 token 剩余有效期
- 定期清理过期的黑名单 entry

## 密码安全

- 密码必须使用 bcrypt/scrypt 哈希存储
- 禁止明文存储密码
- 禁止在日志中记录密码

```python
from passlib.hash import bcrypt

# 哈希密码
hashed = bcrypt.hash(password)

# 验证密码
if bcrypt.verify(password, hashed):
    # 密码正确
    pass
```

## SQL 注入防护

- 所有数据库查询必须使用参数化查询
- 禁止使用字符串拼接构建 SQL

```python
# 正确：参数化查询
stmt = select(User).where(User.username == username)

# 错误：字符串拼接
stmt = f"SELECT * FROM users WHERE username = '{username}'"
```

## 敏感信息保护

- API Key、数据库密码等敏感信息通过环境变量注入
- `.env` 文件加入 `.gitignore`
- 日志中禁止记录敏感信息

```python
# 正确：从配置读取
api_key = settings.DASHSCOPE_API_KEY

# 错误：硬编码
api_key = "sk-xxx..."
```

## XSS 防护

- 前端渲染用户输入时使用 `v-text` 而非 `v-html`
- 后端 API 响应设置 CORS 白名单
- 使用 httpOnly cookie 存储 token，防止 JS 读取

## CSRF 防护

- 使用 SameSite cookie 属性
- 敏感操作（写操作）验证 Origin/Referer 头

## 速率限制

- 登录接口限制频率（如 5 次/分钟）
- 使用 Redis 计数器 + Lua 脚本保证原子性

```lua
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('GET', key)
if not current then
    redis.call('SETEX', key, window, 1)
    return 1
end

if tonumber(current) >= limit then
    return 0  -- 超出限制
end

redis.call('INCR', key)
return 1
```

## 文件上传安全

- 限制上传文件类型（白名单）
- 限制文件大小
- 文件名随机化，不使用用户上传的原文件名
- 上传目录禁止执行脚本

## 内部接口保护

- localhost 内部接口必须验证来源 IP
- 工作流触发接口等内部 API 不能暴露在公网

```python
async def verify_internal(request: Request):
    client_host = request.client.host
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="Internal access only")
```

## 凭证脱敏规范

### 正则保留 key 名只抹去 value

**为什么**：日志输出、错误信息、测试断言中可能包含凭证信息（API Key / Token / Secret / Password / AppKey）。直接整体替换为 `***` 会丢失字段名上下文，无法定位是哪个凭证泄露；正确做法是保留 key 名，仅抹去 value，便于日志排查同时不暴露凭证。

**判断逻辑**：
- 正则匹配保留 key 名，仅抹去 value
- 替换为 `m.group(1) + "***"`（保留 key 名 + 分隔符 + 脱敏标记），而非整体替换为 `***`
- 适用凭证类型：token / secret / key / password / appkey（不区分大小写）

**固定流程**：
1. 识别输出文本中可能包含凭证的字段（key=value 或 key: value 格式）
2. 用正则匹配凭证字段：`(?i)((?:token|secret|key|password|appkey)\s*[:=]\s*)\S+`
3. 替换 value 为 `***`，保留 key 名和分隔符

**正确做法**：
```python
import re

# ✅ 保留 key 名，仅抹去 value
def mask_credentials(text: str) -> str:
    """脱敏文本中的凭证信息，保留 key 名便于排查。

    匹配 token/secret/key/password/appkey 字段（不区分大小写），
    保留 key 名和分隔符，仅将 value 替换为 ***。
    """
    pattern = r"(?i)((?:token|secret|key|password|appkey)\s*[:=]\s*)\S+"
    return re.sub(
        pattern,
        lambda m: m.group(1) + "***",  # 保留 key 名 + 分隔符 + 脱敏标记
        text,
    )

# 示例
# 输入：'api_key=sk-abc123, token=xyz789'
# 输出：'api_key=***, token=***'
# 输入：'Authorization: Bearer sk-secret123'
# 输出：'Authorization: Bearer ***'（key 字段不匹配，Bearer 不在清单内，需扩展）
```

**错误做法**：
```python
# ❌ 整体替换为 ***，丢失 key 名上下文
def mask_credentials(text: str) -> str:
    pattern = r"(?i)(?:token|secret|key|password|appkey)\s*[:=]\s*\S+"
    return re.sub(pattern, "***", text)
    # 输入：'api_key=sk-abc123, token=xyz789'
    # 输出：'***, ***'  # 无法区分是哪个凭证

# ❌ 仅匹配固定字段名，遗漏 appkey 等
def mask_credentials(text: str) -> str:
    # 仅匹配 api_key，遗漏 token/secret/password/appkey
    return re.sub(r"api_key=\S+", "api_key=***", text)

# ❌ 不区分大小写，遗漏 Token/TOKEN 等变体
def mask_credentials(text: str) -> str:
    # 仅匹配小写 token，遗漏 Token/TOKEN
    return re.sub(r"token=\S+", "token=***", text)
```

**规则**：
- 正则必须不区分大小写（`(?i)` 前缀），覆盖 Token/TOKEN/Secret/SECRET 等变体
- 替换时保留 key 名和分隔符（`m.group(1) + "***"`），不整体替换
- 凭证类型清单至少包含：token / secret / key / password / appkey
- 日志输出、错误信息、测试断言中的凭证必须经过脱敏处理

**适用场景**：日志输出、错误信息、测试断言、调试信息中包含凭证的场景
**不适用场景**：非凭证类文本（如普通业务数据）；配置文件中的凭证（应通过环境变量管理）

## 内存泄漏防护（Blob URL 释放）

### blob URL 必须在组件卸载、列表刷新、删除操作时释放

**为什么**：`URL.createObjectURL(blob)` 创建的 blob URL 会持续占用内存，浏览器不会自动回收（除非页面卸载）。如果组件卸载、列表刷新、删除操作时不调用 `URL.revokeObjectURL(url)` 释放，blob 数据会驻留在内存中，长时间运行后导致浏览器内存泄漏，页面卡顿甚至崩溃。

**判断逻辑**：
- blob URL 创建后必须在适当时机释放：组件卸载、列表刷新、删除操作
- 按需加载策略：首次点击才请求音频/文件数据，避免列表加载时并发请求
- 释放时机：组件 `onUnmounted`、列表 `refresh`、删除元素后

**固定流程**：
1. 创建 blob URL 时记录引用（保存到 ref/reactive）
2. 在以下时机释放：组件卸载（`onUnmounted`）、列表刷新（`refresh`）、删除元素后
3. 释放后将引用置为 null，避免悬空引用
4. 按需加载：列表加载时不请求二进制数据，首次点击才请求

**正确做法**：
```javascript
// ✅ Vue 3 组件：blob URL 在卸载/刷新/删除时释放
import { ref, onUnmounted } from 'vue'

const audioUrl = ref(null)
const audioUrls = ref([])  // 列表场景

// 按需加载：首次点击才请求音频数据
async function playAudio(materialId: string) {
  // 已存在 blob URL 则复用，避免重复创建
  if (audioUrl.value) {
    return
  }
  const blob = await fetchAudioBlob(materialId)
  audioUrl.value = URL.createObjectURL(blob)
}

// 列表刷新时释放所有 blob URL
async function refreshList() {
  // 释放旧 blob URL，避免内存泄漏
  audioUrls.value.forEach(url => URL.revokeObjectURL(url))
  audioUrls.value = []
  // 重新加载数据（不预加载二进制，按需加载）
  await loadList()
}

// 删除元素后释放对应 blob URL
async function deleteItem(id: string) {
  const idx = audioUrls.value.findIndex(item => item.id === id)
  if (idx >= 0) {
    URL.revokeObjectURL(audioUrls.value[idx].url)  // 释放被删除元素的 blob URL
    audioUrls.value.splice(idx, 1)
  }
  await apiDeleteItem(id)
}

// 组件卸载时释放所有 blob URL
onUnmounted(() => {
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = null
  }
  audioUrls.value.forEach(url => URL.revokeObjectURL(url))
  audioUrls.value = []
})
```

**错误做法**：
```javascript
// ❌ 创建 blob URL 但不释放，组件卸载后内存泄漏
async function playAudio(materialId: string) {
  const blob = await fetchAudioBlob(materialId)
  audioUrl.value = URL.createObjectURL(blob)
  // 无 onUnmounted 释放，无 refresh 释放，无 delete 释放
}

// ❌ 列表加载时预加载所有二进制数据，并发请求 + 内存堆积
async function loadList() {
  const items = await apiListItems()
  // 列表加载时并发请求所有音频数据（应按需加载）
  items.forEach(async (item) => {
    const blob = await fetchAudioBlob(item.id)
    item.audioUrl = URL.createObjectURL(blob)
  })
}

// ❌ 删除元素后不释放对应 blob URL
async function deleteItem(id: string) {
  await apiDeleteItem(id)
  // 未调用 URL.revokeObjectURL 释放被删除元素的 blob URL
  // 数组虽 splice，但 blob URL 仍占用内存
}
```

**规则**：
- blob URL 创建后必须记录引用，便于后续释放
- 释放时机：组件卸载（`onUnmounted`）、列表刷新（`refresh`）、删除元素后
- 释放后必须将引用置为 null，避免悬空引用
- 列表加载时不预加载二进制数据，按需加载（首次点击才请求）
- 多个 blob URL 用数组管理，批量释放

**适用场景**：音频/视频播放、文件预览、图片二进制展示
**不适用场景**：静态资源 URL（如 `https://example.com/image.png`，浏览器自动管理）
