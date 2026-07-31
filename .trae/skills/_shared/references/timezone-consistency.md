# 时区一致性

> 共享来源：news-code-dev 规范 8/33/162 / news-backend-code-review 维度 38/142 / news-frontend-code-review / news-auto-testing

## 核心规则

项目统一使用本地时间（Asia/Hong_Kong），所有时间相关代码必须保持一致，避免 UTC 与本地时间混用导致的 8 小时时区差。

### 时间函数规范
- 生产代码统一使用 `utcnow_naive()`（项目封装的本地时间函数）
- 禁止使用 `datetime.utcnow()`（Python 3.12+ 弃用）
- 禁止使用 `datetime.now()` 无 tzinfo（与 ORM 时区不一致）

### ORM 模型时间字段
- 禁止 `func.now()` 作为 default（SQLite `func.now()` 返回 UTC）
- 时间字段写入时显式赋值项目统一时区源函数
- `AuditLog` 等特殊模型可白名单豁免

### 测试时间基线对齐（testing 阶段 73、75）
- 测试代码必须使用与生产一致的时间函数
- 禁止测试用 `datetime.utcnow()`
- 时间比较使用近似断言（`abs(actual - expected) < epsilon`）
- epsilon 按数据库精度配置（SQLite 2s / MySQL 1s）
- flaky 测试中的时区类根因需对齐时间基线

### SQLite 时区一致性（testing 阶段 82）
- 扫描 mapped_column 的 default 参数
- 反向校验时间字段写入处是否显式赋值
- 排除模型白名单

## 后端维度索引

- backend-review 维度 38：时区与时间函数规范
- backend-review 维度 142：ORM 时间字段默认值规范

## 开发规范索引

- code-dev 规范 8/33/162：时间函数使用 + ORM 时区

## 前端维度索引

- frontend-review：前端时间格式化与时区处理

## 测试阶段索引

- testing 阶段 73：时区敏感测试基线对齐
- testing 阶段 75：flaky 测试根因修复验证
- testing 阶段 82：SQLite 时区一致性测试
