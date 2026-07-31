# 频道级数据隔离

> 共享来源：news-code-dev / news-backend-code-review / news-auto-testing

## 核心规则

多频道部署场景下，各频道数据严格隔离。所有数据库查询必须带上 `channel_id` 过滤条件，防止跨频道数据泄露。

### 数据库查询隔离
- 所有业务查询必须按 `channel_id` 过滤
- 全局工作流（`channel_id=None`）允许 `IS NULL` 查询
- 禁止 `OR channel_id IS NULL` 兜底（跨频道污染风险）
- crawler 0-count 检查时禁止 OR NULL 兜底

### 频道级配置覆盖
- 频道字段优先于全局配置（intro_prompt/outro_prompt 等）
- 频道字段为空时 fallback 到全局默认值
- `schedule_time` 变更触发 cron 任务重注册
- `is_active` 禁用时取消 queued 工作流

### 测试验证（testing 阶段 11）
- 静态扫描：SQLAlchemy `or_` 兜底逻辑 + SQL 原生 OR NULL
- crawler 0-count 逻辑的 OR NULL 兜底检查
- `or_` 导入但未使用残留检查

## 后端维度索引

- backend-review：频道级数据查询隔离 + 配置覆盖

## 开发规范索引

- code-dev 频道隔离规范：数据隔离最佳实践

## 测试阶段索引

- testing 阶段 11：频道级数据隔离预检
