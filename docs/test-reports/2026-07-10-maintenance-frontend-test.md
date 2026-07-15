# 系统清理模块前端测试报告

| 项目 | 内容 |
|------|------|
| 测试日期 | 2026-07-10 |
| 测试模块 | 系统清理（Maintenance） |
| 测试工具 | Chrome DevTools MCP + PowerShell API 测试 |
| 服务地址 | http://127.0.0.1:8000 |
| 测试账号 | admin / admin123 |

## 测试概览

| 维度 | 总数 | 通过 | 失败 | 跳过 |
|------|------|------|------|------|
| 页面加载 | 1 | 1 | 0 | 0 |
| 按钮交互 | 4 | 4 | 0 | 0 |
| API 端点 | 4 | 4 | 0 | 0 |
| 控制台错误 | 1 | 1 | 0 | 0 |
| **总计** | **10** | **10** | **0** | **0** |

**整体结论：PASS** - 系统清理模块前端验证全部通过。

## 1. 页面加载测试

### 系统清理页 `/maintenance`

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 页面导航 | PASS | 菜单点击"系统清理"成功导航到 /maintenance |
| 页面标题 | PASS | 显示"系统清理"标题（h2） |
| 存储状态卡片 | PASS | 数据库(1.84 MB) + 日志文件(0.0 KB) + 缓存(0 条) 三卡片正常渲染 |
| 缓存清理表单 | PASS | 清理目标下拉 + 预览模式开关 + 预览清理按钮 |
| 数据库清理表单 | PASS | 清理目标 + 保留天数(30) + 预览模式 + 预览清理按钮 |
| 日志清理表单 | PASS | 清理目标 + 保留天数(7) + 预览模式 + 预览清理按钮 |
| 使用说明 | PASS | 6 条提示完整显示 |
| 控制台错误 | PASS | 无 error 级别消息 |

## 2. 按钮交互测试

| 按钮名称 | 预期行为 | 实际结果 | 状态 |
|----------|----------|----------|------|
| 刷新状态 | state_change | 按钮变 disabled 加载中，状态数据刷新 | PASS |
| 缓存清理-预览清理 | state_change | 显示清理结果：TTLCache 0 条 + __pycache__ 17 目录(1.03 MB) + 临时文件 0 个 | PASS |
| 数据库清理-预览清理 | state_change | 显示 7 项清理结果：播放日志/工作流/审核/黑名单/爬虫去重/AI用量/VACUUM | PASS |
| 日志清理-预览清理 | state_change | 显示"无需清理"（无日志文件）+ "预览完成"提示 | PASS |

## 3. API 端点测试

| API 名称 | 方法 | 路径 | 状态码 | code | 状态 |
|----------|------|------|--------|------|------|
| 清理-存储状态 | GET | /admin/api/v1/maintenance/status | 200 | 0 | PASS |
| 清理-缓存预览 | POST | /admin/api/v1/maintenance/cache | 200 | 0 | PASS |
| 清理-数据库预览 | POST | /admin/api/v1/maintenance/database | 200 | 0 | PASS |
| 清理-日志预览 | POST | /admin/api/v1/maintenance/logs | 200 | 0 | PASS |

### API 响应数据示例

**存储状态**：
```json
{
  "db": {"db_size_mb": 1.81, "playlog_count": 0, "workflow_count": 1, "dedup_count": 246},
  "logs": {"file_count": 0, "total_size_mb": 0.0},
  "cache": {"ttlcache_count": 0, "pycache_count": 0, "temp_files": 0}
}
```

**缓存清理预览**：
```json
{
  "target": "all", "dry_run": true,
  "cleaned": ["TTLCache 将清空 0 条", "__pycache__ 将清理 17 个目录（1.03 MB）", "临时文件 将删除 0 个"],
  "errors": []
}
```

**数据库清理预览**：
```json
{
  "target": "all", "days": 30, "dry_run": true, "total_deleted": 0,
  "cleaned": ["播放日志 将删除 0 条", "工作流记录 将删除 0 条", "审核记录 将删除 0 条", 
              "过期黑名单 将删除 0 条", "爬虫去重 将删除 0 条", "AI 用量日志 将删除 0 条", "VACUUM 预览完成"],
  "errors": []
}
```

## 4. 网络请求验证

| reqid | 方法 | URL | 状态 |
|-------|------|-----|------|
| 347 | GET | /admin/api/v1/maintenance/status | 200 |
| 348 | POST | /admin/api/v1/maintenance/cache | 200 |
| 349 | POST | /admin/api/v1/maintenance/database | 200 |
| 350 | POST | /admin/api/v1/maintenance/logs | 200 |

## 5. 截图

| 截图文件 | 说明 |
|----------|------|
| maintenance-page.png | 页面初始加载状态 |
| maintenance-all-preview.png | 三个清理预览全部执行后状态 |

截图路径：`docs/test-reports/screenshots/`

## 6. 问题与修复

### 测试过程中发现的问题

| 问题 | 分类 | 严重级别 | 处理方式 |
|------|------|----------|----------|
| 路由文件模块级单例缺少 db 参数 | code_defect | FAIL | 已修复：改为 per-request 实例化 |
| 路由层重复调用 write_audit | code_defect | FAIL | 已修复：移除路由层调用，服务层内部已处理 |
| 路由层未传递 admin_name 参数 | code_defect | FAIL | 已修复：补充 admin_name=admin.username |
| PowerShell 后台进程导致服务退出 | environment | WARN | 改用 Start-Process -NoNewWindow 启动 |

### 修复的文件

1. [maintenance.py](file:///d:/code/otherProjects/MorningBrief/backend/app/routers/admin/maintenance.py) - 路由层 per-request 实例化 + 移除重复审计调用 + 补充 admin_name 参数

## 7. 测试结论

系统清理模块前端验证**全部通过**，可以交付。

- 页面渲染完整，布局符合马卡龙配色 + card-soft 样式规范
- 三个清理功能（缓存/数据库/日志）的预览模式均正常工作
- 所有 API 端点返回正确结果（code=0）
- 控制台无错误，网络请求全部 200
- 审计日志由服务层内部处理，路由层无重复调用
