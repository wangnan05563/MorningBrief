# SonarQube 闭环规范

> 共享来源：news-backend-code-review 维度 73-90 / news-frontend-code-review 维度 57-74 / news-auto-testing 阶段 20-31

## 核心规则

SonarQube 扫描闭环覆盖三个阶段：扫描前环境预检 → 扫描执行 → 扫描后问题修复与回归验证。

### 扫描前环境预检（testing 阶段 20-22、28）
- 服务模式检测：dev/exe/docker 模式自动识别
- Node.js 版本兼容性检查（v24 与 SonarJS bridge 不兼容）
- PowerShell 版本检查（PS5 需 .bat 封装扫描命令）
- SonarQube 服务可达性检查 + SONAR_TOKEN 配置检查
- scanner 路径（SONAR_SCANNER_HOME）验证

### 扫描与问题管理（testing 阶段 23）
- 7 步 SQ-Loop 模式：执行扫描 → 等待完成 → 拉取 OPEN 问题 → diff 识别新增 → 判断阻塞 → 报告
- 二次扫描回归验证：修复未引入新问题
- 问题严重级别分类：BLOCKER/CRITICAL → FAIL，MAJOR → WARN

### 扫描后修复验证（testing 阶段 27、29、31）
- NOSONAR 注释位置正确性（见 nosonar 注释位置规则）
- 并行子代理修复结果二次核查（文件存在性、NOSONAR 写入、位置正确性、文件组互斥）
- NOSONAR 抑制 vs 代码修复决策矩阵（must_fix_rules 禁止抑制）

## 后端维度索引

- backend-review 维度 73-77：SonarQube 规则映射（S7503/S6395/S7504/S1481/S1128）
- backend-review 维度 78-80：未使用变量/import + 异常处理
- backend-review 维度 81-90：认知复杂度 + 安全规则 + 修复决策

## 前端维度索引

- frontend-review 维度 57-60：未使用 import/变量 + DOM API 替换
- frontend-review 维度 61-74：注释规范 + import 排序 + 异常处理

## 测试阶段索引

- testing 阶段 20-22：服务模式检测 + API 登录协议适配 + 路由路径预验证
- testing 阶段 23：SonarQube 二次扫描回归（7 步 SQ-Loop）
- testing 阶段 27-28：NOSONAR 位置验证 + 扫描环境兼容性预检
- testing 阶段 29：并行子代理修复结果二次核查
- testing 阶段 31：NOSONAR 抑制 vs 代码修复决策验证
