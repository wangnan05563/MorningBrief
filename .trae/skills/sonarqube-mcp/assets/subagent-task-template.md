# 并行修复子代理任务模板

> 本文件由 SKILL.md Phase 5 与 references/scan-workflow.md 第 7 节共享引用。  
> 启动子代理时主智能体一次性读取本文件，避免在主上下文常驻模板文本。

## 子代理任务 Prompt 模板

```
请对以下 SonarQube 问题进行修复：

## 分配的问题清单
<issues JSON>

## 修复要求
1. 对每个 issue：
   - 使用 Read 工具读取对应文件理解上下文
   - 分析根因（结合 SonarQube 规则详情）
   - 使用 Edit 工具实施修复
   - 记录修复内容（位置、方法、验证）
2. 修复原则：
   - 只修改必要部分，不顺便修改旁边的代码
   - 注释解释"为什么"而非"做什么"
   - 不引入新的代码问题
3. 返回修复报告（JSON 格式）：
   {
     "fixed": [{ "issue_key": "...", "file": "...", "method": "...", "status": "fixed" }],
     "skipped": [{ "issue_key": "...", "reason": "..." }]
   }
```

## 修复策略（按 rule ID 配置，详见 scan_config.json -> fix_strategies）

| 策略 | 含义 |
|------|------|
| `auto_fix` | 可自动修复，子代理直接执行 |
| `manual_review` | 需人工审查，子代理输出建议供用户决策 |
| `skip` | 跳过修复，仅记录 |

## 并行判断逻辑

- 文件组数 > 1 且 `scan.parallel_agents` > 1：启用并行子代理
- 同一文件内多个 issue：串行处理（避免 Edit 冲突）
- 子代理分配规则：每个子代理 `scan.files_per_agent` 个文件
