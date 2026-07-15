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
