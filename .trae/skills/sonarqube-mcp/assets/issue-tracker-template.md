# Xianyu SonarQube 扫描问题记录模板

## 扫描信息

- **扫描日期**：{date}
- **扫描范围**：{scope}
- **项目Key**：{projectKey}
- **执行人**：{executor}
- **扫描方式**：{MCP/降级 sonar-scanner}
- **运行环境**：{local/ci/cloud}

## 问题记录

| # | Issue Key | 规则ID | 严重级别 | 类型 | 文件 | 行号 | 描述 | 语言 | 处理方式 | 处理人 | 处理日期 |
|---|-----------|--------|----------|------|------|------|------|------|----------|--------|----------|
| 1 | {key} | {rule} | {severity} | {type} | {file} | {line} | {message} | {language} | 修复/误报/接受 | {name} | {date} |

## 修复记录

### 修复 1

- **Issue Key**：{key}
- **规则**：{rule}
- **语言**：{python/typescript}
- **修复策略**：{auto_fix/manual_review}
- **修复前代码**：
```{language}
{before}
```
- **修复后代码**：
```{language}
{after}
```
- **验证结果**：✅ 已通过 / ❌ 未通过
- **验证详情**：{verification_details}

## 误报记录

### 误报 1

- **Issue Key**：{key}
- **规则**：{rule}
- **误报原因**：{reason}
- **SonarQube状态变更**：OPEN → FALSE_POSITIVE
- **comment**：{comment}

## 接受记录（可接受债务）

### 接受 1

- **Issue Key**：{key}
- **规则**：{rule}
- **接受原因**：{business_reason}
- **补偿措施**：{mitigation}
- **SonarQube状态变更**：OPEN → ACCEPT
- **comment**：{comment}

## 硬约束违规记录

| # | 约束名称 | 严重级别 | 违规位置 | 违规内容 | 处理方式 | 处理状态 |
|---|----------|----------|----------|----------|----------|----------|
| 1 | {constraint_name} | {severity} | {location} | {violation} | 修复/豁免 | ✅/❌ |

## 验证结果

- **重新扫描**：✅ 已执行 / ❌ 未执行
- **修复前后对比**：
  - 修复前问题数：{before_count}
  - 修复后问题数：{after_count}
  - 减少数量：{delta}
- **测试运行**：✅ 通过 / ❌ 失败 / ⏭️ 跳过
- **新增问题**：{count} 个
- **硬约束合规**：✅ 全部通过 / ❌ 存在违规

## 凭据安全检查

- **硬编码凭据检测**：✅ 未发现 / ❌ 发现 {count} 处
- **凭据来源验证**：{环境变量/.env/硬编码}
- **报告脱敏验证**：✅ 不包含敏感信息
