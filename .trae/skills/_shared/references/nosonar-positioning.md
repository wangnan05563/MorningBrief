# NOSONAR 注释位置规则

> 共享来源：news-code-dev SQ 闭环补充 / news-frontend-code-review / news-backend-code-review / news-auto-testing 阶段 27-31

## 核心规则

NOSONAR 注释用于抑制 SonarQube 规则告警，但注释位置必须正确，否则 SonarQube 无法识别。不同语言/文件类型的注释语法不同。

### Python 后端规则

- **单行 def**：`def func(args):  # NOSONAR` → PASS
- **多行 def**：NOSONAR 必须在首行 `def func_name(` 行尾
  - ❌ 错误：在返回类型行尾 `) -> ReturnType:  # NOSONAR`（SonarQube 不识别）
  - ✅ 正确：在 `def func_name(` 行尾 `def func_name(  # NOSONAR`
- **其他单行场景**（if/for/with/赋值）：PASS（无歧义）
- 必须大写 `NOSONAR`（`nosonar` / `NoSonar` 不识别）
- `#` 前必须有至少一个空格

### 前端文件规则

| 文件类型 | 正确语法 | 错误语法 |
|---------|---------|---------|
| `.js` / `.vue <script>` | `// NOSONAR` 或 `/* NOSONAR */` | `<!-- NOSONAR -->` |
| `.vue <template>` | `<!-- NOSONAR -->` | `// NOSONAR` |
| `.wxml` | `<!-- NOSONAR -->` | `// NOSONAR` |
| `.wxss` | `/* NOSONAR */` | `<!-- NOSONAR -->` |

### NOSONAR 决策矩阵（testing 阶段 31）

| 规则分类 | 处理方式 |
|---------|---------|
| **must_fix_rules**（S5446/S930/S2817/S5886/S3699） | 必须修复代码，**禁止**用 NOSONAR 抑制 |
| **can_suppress_rules**（S3776/S7503/S125/S6353） | 可抑制，但需含原因注释 `# NOSONAR S3776: 原因` |
| **unknown_rules** | 需人工决策 |

## 后端维度索引

- backend-review：Python NOSONAR 位置规则 + 决策矩阵

## 前端维度索引

- frontend-review：前端多文件类型 NOSONAR 语法

## 测试阶段索引

- testing 阶段 27：NOSONAR 注释位置正确性验证
- testing 阶段 29：并行子代理修复结果二次核查
- testing 阶段 31：NOSONAR 抑制 vs 代码修复决策验证
