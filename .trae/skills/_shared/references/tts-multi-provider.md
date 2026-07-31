# TTS 多 Provider 架构

> 共享来源：news-code-dev 维度 12 / news-backend-code-review 维度 106-112 / news-frontend-code-review 维度 91-94

## 核心规则

TTS（文字转语音）采用多 Provider 抽象架构，支持阿里云、Edge-TTS、腾讯云等提供商，通过抽象基类 + 工厂注册表 + 降级链路实现 Provider 无感切换。

### 抽象基类模式（code-dev 规范 R109）
- 所有 Provider 必须继承 `TTSProvider` 抽象基类
- 必须实现 `synthesize()` 抽象方法
- 推荐实现 `test_connection()` 方法
- `_PROVIDER_REGISTRY` 工厂注册表管理所有已实现 Provider

### 降级链路（code-dev 规范 R110）
- `_parse_fallback_chain` 函数从配置读取降级顺序
- 主 Provider 失败时自动降级到 fallback Provider
- 所有 Provider 失败时抛出 TTSError（含尝试顺序）
- 降级循环外一次性 `check_budget`，不在循环内重复校验

### 凭证 fallback 链（code-dev 规范 R111）
- 三级优先级：显式参数 > 专用配置 > 通用配置（如 COS 凭证）
- 全空时需报明确错误，不可静默通过

### 异常分类体系
- `TTSProviderError`：不可重试（凭证无效）
- `TTSRateLimitError`：可重试（频率超限）
- `TTSTimeoutError`：可重试（请求超时）
- `TTSServiceError`：可重试（服务端 5xx）

## 后端维度索引

- backend-review 维度 106-108：TTS 多 Provider 架构 + 降级链路 + 异常分类
- backend-review 维度 109-112：edge-tts 版本预检 + 凭证 fallback + 版本兼容

## 前端维度索引

- frontend-review 维度 91-94：Provider 切换 UI + 表单联动 + 音色动态渲染 + 测试连接分发
