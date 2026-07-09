# SonarQube 扫描报告模板

## 📊 {项目名称} SonarQube 扫描报告

**扫描时间**：{日期}
**扫描范围**：{功能模块名称}
**项目Key**：{projectKey}
**运行环境**：{local/ci/cloud}
**扫描方式**：{MCP/降级 sonar-scanner}

---

### 一、质量门禁状态

**整体状态**：✅ 通过 / ❌ 未通过

| 指标 | 当前值 | 阈值 | 状态 |
|------|--------|------|------|
| 新代码覆盖率 | {value}% | ≥80% | ✅/❌ |
| 新代码重复率 | {value}% | ≤3% | ✅/❌ |
| 新增问题数 | {value} | 0 | ✅/❌ |
| 新增安全问题数 | {value} | 0 | ✅/❌ |

---

### 二、扫描文件清单

#### 后端（Python / FastAPI）

| 层级 | 文件 | 行数 | 问题数 |
|------|------|------|--------|
| api | {filename} | {lines} | {count} |
| services | {filename} | {lines} | {count} |
| core | {filename} | {lines} | {count} |
| models | {filename} | {lines} | {count} |
| web | {filename} | {lines} | {count} |
| utils | {filename} | {lines} | {count} |

#### 前端（TypeScript / React）

| 层级 | 文件 | 行数 | 问题数 |
|------|------|------|--------|
| pages | {filename} | {lines} | {count} |
| components | {filename} | {lines} | {count} |
| hooks | {filename} | {lines} | {count} |
| services | {filename} | {lines} | {count} |
| store | {filename} | {lines} | {count} |
| utils | {filename} | {lines} | {count} |

**扫描文件总数**：{count}
**涉及代码行数**：{lines}

---

### 三、问题统计

#### 按严重级别

| 级别 | 数量 | 占比 |
|------|------|------|
| BLOCKER | {count} | {pct}% |
| CRITICAL | {count} | {pct}% |
| MAJOR | {count} | {pct}% |
| MINOR | {count} | {pct}% |
| INFO | {count} | {pct}% |
| **合计** | **{total}** | **100%** |

#### 按质量维度

| 维度 | 数量 | 占比 |
|------|------|------|
| SECURITY | {count} | {pct}% |
| RELIABILITY | {count} | {pct}% |
| MAINTAINABILITY | {count} | {pct}% |

#### 按语言分布

| 语言 | 数量 | 占比 |
|------|------|------|
| Python | {count} | {pct}% |
| TypeScript | {count} | {pct}% |
| JavaScript | {count} | {pct}% |

---

### 四、问题详情

#### 🔴 BLOCKER 级别

| # | 规则 | 文件 | 行号 | 描述 | 维度 | 语言 |
|---|------|------|------|------|------|------|
| 1 | {rule} | {file} | {line} | {message} | {category} | {language} |

#### 🟠 CRITICAL 级别

| # | 规则 | 文件 | 行号 | 描述 | 维度 | 语言 |
|---|------|------|------|------|------|------|
| 1 | {rule} | {file} | {line} | {message} | {category} | {language} |

#### 🟡 MAJOR 级别

| # | 规则 | 文件 | 行号 | 描述 | 维度 | 语言 |
|---|------|------|------|------|------|------|
| 1 | {rule} | {file} | {line} | {message} | {category} | {language} |

#### 🟢 MINOR / INFO 级别

| # | 规则 | 文件 | 行号 | 描述 | 维度 | 语言 |
|---|------|------|------|------|------|------|
| 1 | {rule} | {file} | {line} | {message} | {category} | {language} |

---

### 五、硬约束合规性检查

| # | 约束名称 | 严重级别 | 检查结果 | 违规位置 | 说明 |
|---|----------|----------|----------|----------|------|
| 1 | no_hardcoded_credentials | CRITICAL | ✅/❌ | {location} | {message} |
| 2 | no_hardcoded_sonar_token | CRITICAL | ✅/❌ | {location} | {message} |
| 3 | hmac_compare_digest_for_token | CRITICAL | ✅/❌ | {location} | {message} |
| 4 | webview_no_devnull_redirect | MAJOR | ✅/❌ | {location} | {message} |
| 5 | webview_create_new_console | MAJOR | ✅/❌ | {location} | {message} |
| 6 | webview_private_mode_false | MAJOR | ✅/❌ | {location} | {message} |
| 7 | hf_endpoint_mirror | MAJOR | ✅/❌ | {location} | {message} |
| 8 | auth_whitelist_endpoints | MAJOR | ✅/❌ | {location} | {message} |
| 9 | fetch_credentials_include | MAJOR | ✅/❌ | {location} | {message} |
| 10 | kbmanager_whitelist_only | MAJOR | ✅/❌ | {location} | {message} |

**硬约束违规阻止合并**：{是/否}

---

### 六、修复建议

#### 问题 1：{规则ID} — {问题描述}

- **严重级别**：{severity}
- **所在文件**：{file}:{line}
- **语言**：{python/typescript}
- **问题分析**：{analysis}
- **修复方案**：{solution}
- **修复策略**：{auto_fix/manual_review/skip}
- **修复代码**：

```{language}
// 修复前
{before_code}

// 修复后
{after_code}
```

- **验证方法**：{verification}

---

### 七、修复结果

#### 修复统计

| 状态 | 数量 | 占比 |
|------|------|------|
| 已修复 (fixed) | {count} | {pct}% |
| 跳过 (skipped) | {count} | {pct}% |
| 误报 (falsepositive) | {count} | {pct}% |
| 接受 (accept) | {count} | {pct}% |
| **合计** | **{total}** | **100%** |

#### 跳过原因分布

| 原因 | 数量 |
|------|------|
| 误报 | {count} |
| 超阈值（severity 低于 fix_threshold） | {count} |
| 策略跳过（skip） | {count} |
| 需人工审查（manual_review） | {count} |

---

### 八、验证结果

#### 重新扫描对比

| 指标 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| 问题总数 | {count} | {count} | {delta} |
| BLOCKER | {count} | {count} | {delta} |
| CRITICAL | {count} | {count} | {delta} |
| MAJOR | {count} | {count} | {delta} |

#### 测试运行结果

- **测试命令**：{test_command}
- **执行状态**：✅ 通过 / ❌ 失败
- **测试详情**：{test_details}

#### 新增问题

| # | 规则 | 文件 | 行号 | 描述 | 处理建议 |
|---|------|------|------|------|----------|
| 1 | {rule} | {file} | {line} | {message} | {suggestion} |

---

### 九、代码亮点 ✨

以下文件通过扫描**零问题**，代码质量优秀：

| 文件 | 行数 | 亮点说明 |
|------|------|----------|
| {filename} | {lines} | {highlight} |

---

### 十、结论与建议

**整体评价**：{overall_assessment}

**必须修复**（阻塞发布）：
1. {blocker_item}

**建议修复**（当前迭代）：
1. {critical_item}

**后续优化**：
1. {major_item}

**测试覆盖率建议**：
- 当前覆盖率：{current_coverage}%
- 目标覆盖率：≥80%
- 建议优先补充测试的模块：{test_suggestion}

**凭据安全检查**：
- 是否检测到硬编码凭据：{是/否}
- 凭据来源验证：{环境变量/.env/硬编码}
- 报告脱敏：✅ 不包含任何 token、密码等敏感信息

---

### 附录：访问地址

- SonarQube Dashboard: {host}/dashboard?id={project_key}
- 质量门禁详情: {host}/quality_gates/show/{project_key}
- 项目问题列表: {host}/project/issues?id={project_key}
- 安全热点: {host}/project/security_hotspots?id={project_key}
