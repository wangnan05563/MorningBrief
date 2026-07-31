# 跨项目迁移 7 步法

> 共享来源：news-code-dev 规范 86-88 / news-frontend-code-review 维度 75-77 / news-backend-code-review 维度 89-90 / news-auto-testing 阶段 32-36

## 核心规则

跨项目模块迁移必须遵循 7 步标准流程，缺任一步骤则判定为不完整迁移。

### 7 步标准流程（testing 阶段 32）

1. **requirement_confirm**：需求文档或对话记录确认
2. **architecture_align**：5 项对齐（目录结构/技术栈/依赖库/命名约定/路径风格）
3. **backend_dev**：后端代码落地实现
4. **frontend_dev**：前端代码落地实现
5. **test_write**：测试用例编写
6. **test_execute**：测试实际执行（非仅编写）
7. **build_verify**：构建验证（前端 `npm run build` / 后端 `pyinstaller`）

### 辅助验证阶段

- **阶段 33**：前端嵌套目录相对路径校验（views 子目录下 `@use` / `import` 路径层级正确性）
- **阶段 34**：UI 图标跨库迁移存在性验证（目标图标库中图标名存在性检查 + 映射建议）
- **阶段 35**：模块级单例缓存测试隔离验证（`_reset_cache_for_test` 函数存在性 + 测试调用）
- **阶段 36**：多版本 Python 环境测试执行预检（系统 Python 路径 + pytest 可用性 + 依赖完整性）

### 判断信号

```bash
# 信号 1：缺少测试执行步骤（仅编写未执行）
grep -rn "test_write" .trae/skills/news-code-dev/ && \
  grep -rn "test_execute" .trae/skills/news-code-dev/

# 信号 2：缺少构建验证步骤
grep -rn "build_verify" .trae/skills/news-code-dev/
```

## 后端维度索引

- backend-review 维度 89-90：迁移架构对齐 + 后端代码规范

## 前端维度索引

- frontend-review 维度 75-77：嵌套路径校验 + 图标迁移 + 构建验证

## 测试阶段索引

- testing 阶段 32：跨项目模块迁移 7 步法验证
- testing 阶段 33-36：嵌套路径 + 图标迁移 + 缓存隔离 + Python 环境预检
