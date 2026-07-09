# NOSONAR 抑制注释位置规则

> **单一信息源**：本文件是 NOSONAR 位置判断的单一可信源。配置驱动的位置规则表见 [config/fix_strategies.json -> nosonar_position_rules](file:///d:/code/otherProjects/17_xianyu/.trae/skills/sonarqube-mcp/config/fix_strategies.json)。本文件提供背景、原理与决策树，子代理修复时优先查表，本文件用于理解为何要查表。

---

## 背景

SonarQube 的 `# NOSONAR` 抑制注释能让分析器忽略该行的问题，但有一个关键限制：**必须放在问题所在物理行的末尾**。不同 SonarQube 规则报问题时的物理行不同，例如：

- S107（参数过多）报的是**第一个参数所在行**，不是 `def` 行
- S7483（timeout 参数）报的是 **timeout 参数所在行**，不是 `def` 行
- S125（注释代码）报的是**被识别为代码的注释行**
- S5850（正则优先级）报的是**正则赋值行**

如果 NOSONAR 放错了行，扫描后 OPEN 数不会下降，需要二次修复。

---

## 核心原则

| 原则 | 说明 |
|------|------|
| 大小写 | 必须是大写 `# NOSONAR`，不能是 `# nosonar` 或 `# NOsonar` |
| Python 注释格式 | 用 `# NOSONAR`（井号 + 空格 + NOSONAR） |
| TypeScript/JavaScript 注释格式 | 用 `// NOSONAR`（双斜杠 + 空格 + NOSONAR） |
| JSX 标签内部 | 用 `/* NOSONAR */`（标签外仍用 `// NOSONAR`） |
| 必须在注释中 | NOSONAR 必须在 `#` 或 `//` 注释中，在 docstring 字符串内**不生效** |
| SonarQube 不识别 `# noqa` | Python 的 `# noqa` 是 flake8 指令，SonarQube 默认不识别 |
| 物理行精确匹配 | NOSONAR 必须在 SonarQube 报告的 `issue.line` 所在物理行末尾 |

---

## 决策树

```
子代理修复一个 OPEN issue 时：

1. 查 fix_strategies.json -> nosonar_position_rules 表
   ├─ 找到 rule_pattern 匹配的条目
   │   ├─ position = "issue_line"      → 在 issue.line 末尾追加 NOSONAR
   │   ├─ position = "first_param_line" → 在函数第一个参数所在行末尾追加 NOSONAR
   │   ├─ position = "n/a"             → 该规则不需要 NOSONAR，用其他方式修复
   │   └─ 未找到                       → 用默认规则（position = "issue_line"）
   │
2. 确定注释格式
   ├─ Python       → # NOSONAR
   ├─ TS/JS（标签外）→ // NOSONAR
   └─ JSX 标签内   → /* NOSONAR */
   │
3. 检查 NOSONAR 是否在有效位置
   ├─ 在 # 或 // 注释中              → ✅ 有效
   ├─ 在 docstring 字符串内           → ❌ 无效，需先转为 # 注释
   └─ 在普通字符串内                  → ❌ 无效
   │
4. 修复后扫描验证
   ├─ OPEN 数下降                   → ✅ NOSONAR 生效
   └─ OPEN 数未下降                  → ❌ NOSONAR 位置错误，按 failure_recovery -> nosonar_not_effective 重新放置
```

---

## 高频规则位置速查表

> 完整数据源：`config/fix_strategies.json -> nosonar_position_rules`

| 规则 | position | 说明 | 示例 |
|------|----------|------|------|
| python:S107 | first_param_line | 报第一个参数行，不是 def 行 | `def foo(\n    x: int,  # NOSONAR\n    y: int\n):` |
| python:S7483 | issue_line | 报 timeout 参数行 | `async def f(self, loc, timeout: float = 0.8) -> None:  # NOSONAR` |
| python:S125 | issue_line | 报被识别为代码的注释行；docstring 起始行需先转为 # 注释 | `# 暂停状态描述  # NOSONAR` |
| python:S5850 | issue_line | 报正则赋值行 | `content = re.sub(r'...', '', content)  # NOSONAR` |
| python:S1172 | n/a | 通过重命名 _ 前缀解决，不需要 NOSONAR | `def f(_started_at: datetime):` |
| typescript:S6551 | issue_line | 报模板字符串插值行；typeof 收窄后仍误报用 // NOSONAR | `typeof v === 'object' ? JSON.stringify(v) : String(v) // NOSONAR` |
| typescript:S6754 | issue_line | 报 useState 调用行；已正确解构仍误报用 // NOSONAR | `const [mode, setMode] = useState<ThemeMode>(() => { // NOSONAR` |
| typescript:S6848 | issue_line | 报非原生交互元素行；拖放容器用 /* NOSONAR */ | `<div /* NOSONAR - 拖放容器非交互元素 */>` |
| *（默认） | issue_line | 未在表中显式列出的规则，NOSONAR 放在 issue.line 末尾 | - |

---

## 常见错误与修复

### 错误 1：NOSONAR 放在 def 行但规则报参数行

**错误示例（python:S107）**：

```python
def foo(  # NOSONAR  ← 错误：S107 报的是参数行不是 def 行
    x: int,
    y: int,
):
```

**正确示例**：

```python
def foo(
    x: int,  # NOSONAR  ← 正确：放在第一个参数所在行
    y: int,
):
```

### 错误 2：NOSONAR 在 docstring 内

**错误示例（python:S125 报在 docstring 起始行）**：

```python
"""批量采集执行历史领域数据访问  # NOSONAR  ← 错误：NOSONAR 在字符串内不生效

提供批量采集历史的保存、查询、更新等方法。
"""
```

**正确示例**：

```python
# 批量采集执行历史领域数据访问  # NOSONAR  ← 正确：先转为 # 注释
"""
提供批量采集历史的保存、查询、更新等方法。
"""
```

### 错误 3：使用小写 NOSONAR

**错误示例**：

```python
timeout: float = 0.8,  # nosonar  ← 错误：必须大写
```

**正确示例**：

```python
timeout: float = 0.8,  # NOSONAR  ← 正确：大写
```

### 错误 4：使用 Python # noqa

**错误示例**：

```python
def foo(  # noqa: S107  ← 错误：SonarQube 默认不识别 # noqa
    x: int,
):
```

**正确示例**：

```python
def foo(
    x: int,  # NOSONAR  ← 正确：SonarQube 原生抑制注释
):
```

### 错误 5：JSX 标签内用 // NOSONAR

**错误示例**：

```tsx
<div // NOSONAR  ← 错误：JSX 标签内不能用 // 注释
  onClick={...}
>
```

**正确示例**：

```tsx
<div /* NOSONAR - 拖放容器非交互元素 */
  onClick={...}
>
```

---

## 与配置的关系

| 配置节点 | 作用 |
|----------|------|
| `config/fix_strategies.json -> nosonar_position_rules` | 位置规则的配置化数据源（rule_pattern → position 映射） |
| `config/core_config.json -> nosonar_validation` | 校验开关与回退策略 |
| `config/core_config.json -> verify.validate_nosonar_position` | 修复后扫描若 OPEN 数未下降，自动触发 NOSONAR 位置校验 |
| `config/core_config.json -> failure_recovery.mappings[nosonar_not_effective]` | NOSONAR 未生效时的恢复动作（重新放置） |

---

## 子代理 prompt 模板片段

子代理修复 OPEN issue 时，主代理在 prompt 中应包含以下指令：

```
## NOSONAR 位置规则（重要）

修复时若需要使用 # NOSONAR 抑制注释，必须按以下步骤确定位置：

1. 查 fix_strategies.json -> nosonar_position_rules 表，按 rule ID 匹配 position
2. position = "issue_line"      → 在 SonarQube 报告的 issue.line 末尾追加 NOSONAR
3. position = "first_param_line" → 在函数第一个参数所在行末尾追加 NOSONAR
4. position = "n/a"             → 该规则不需要 NOSONAR，用其他方式修复
5. 未找到 rule                  → 用默认规则（issue_line）

注释格式：
- Python: # NOSONAR
- TypeScript/JavaScript: // NOSONAR
- JSX 标签内: /* NOSONAR */

关键限制：
- NOSONAR 必须大写
- 必须在 # 或 // 注释中，在 docstring 字符串内不生效
- SonarQube 不识别 Python # noqa
```
