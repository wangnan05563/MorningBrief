# 钉钉通知模块设计

**日期**: 2026-07-14
**状态**: 已确认
**参考**: `17_xianyu/modules/notifier/`、`20_News/backend/app/services/notifier/`

## 1. 背景与目标

### 1.1 现状
项目已有 `app/services/notifier/` 模块（含 `DingTalkNotifier`），但仅发送简单 markdown 告警，不支持：
- 工作流完成/异常的精细化通知
- 钉钉消息内审核操作链接
- 在线试听音频链接
- 前端页面配置化（开关、模板）
- 通知发送日志

### 1.2 目标
- 工作流运行完成或异常后，通过钉钉消息通知管理员
- 钉钉消息内嵌 admin-web 深链，支持在线试听与审核操作
- 前端页面可配置化：开关、Webhook 凭证、消息模板
- 提供预设模板并支持自定义编辑
- 消息格式精美，便于管理员操作
- 通知发送日志可审计、可重发

### 1.3 非目标
- 不实现钉钉机器人回调（审核操作走 admin-web 深链）
- 不实现频道级通知开关（YAGNI）
- 不替换现有 `_alert_operators` 系统级告警路径

## 2. 数据模型

### 2.1 新增表：`notification_template`

消息模板表，支持预设与自定义。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | int | PK, autoincrement | 主键 |
| event_type | str(32) | unique, not null | 事件类型：`workflow.failed` / `workflow.pending_review` / `workflow.published`（工作流完成即 pending_review，无需单独 success 事件） |
| name | str(64) | not null | 模板名称（前端展示） |
| title_template | str(128) | not null | 标题模板，支持 `{{var}}` 变量 |
| body_template | Text | not null | 正文模板，markdown + `{{var}}` 变量 |
| is_preset | int | default 1 | 1=预设（不可删，可编辑）、0=自定义 |
| enabled | int | default 1 | 1=启用、0=禁用 |
| updated_at | datetime | server_default=now, onupdate=now | |

### 2.2 新增表：`notification_log`

通知发送日志表，用于审计与失败重发。

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | int | PK, autoincrement | 主键 |
| event_type | str(32) | not null, index | 触发事件类型 |
| channel | str(16) | not null | 渠道名（dingtalk/wecom/email） |
| title | str(128) | not null | 实际发送标题 |
| status | str(16) | not null | `success` / `failed` / `suppressed` |
| error | Text | default "" | 失败原因 |
| payload | Text | default "" | JSON 字符串，渲染时的上下文变量 |
| workflow_id | str(32) | default "", index | 关联工作流 ID |
| created_at | datetime | server_default=now, index | 创建时间 |

索引：
- `idx_notification_log_created` on (created_at)
- `idx_notification_log_workflow` on (workflow_id)

### 2.3 配置项（复用 `ai_config` 表）

不新建配置表，复用现有 `ai_config` key-value 表，新增以下 key：

| key | 说明 | 默认值 |
|---|---|---|
| `notify_global_enabled` | 全局开关 | "0" |
| `notify_failed_enabled` | 失败通知开关 | "1" |
| `notify_review_enabled` | 待审核通知开关 | "1" |
| `notify_published_enabled` | 已发布通知开关 | "0" |
| `notify_dingtalk_webhook` | 钉钉 Webhook URL | "" |
| `notify_dingtalk_secret` | 钉钉加签密钥（脱敏） | "" |
| `notify_admin_base_url` | admin-web 公网 base URL | "" |

**设计要点**：
- 模板独立成表便于 CRUD 与版本管理
- 配置复用 `ai_config` 保持与 AI 服务一致的配置管理范式
- 日志表支持审计与失败重发
- Webhook 凭证迁移自现有 `ALERT_DINGTALK_WEBHOOK` / `ALERT_DINGTALK_SECRET`，启动时若 `notify_dingtalk_webhook` 为空则从 Settings 回退读取

## 3. 服务层架构

新增模块 `app/services/notification/`：

```
app/services/notification/
├── __init__.py
├── template_service.py      # 模板 CRUD + 变量渲染
├── config_service.py         # 通知配置 CRUD（读写 ai_config）
├── log_service.py            # 通知日志查询/重发
├── renderer.py               # 事件 → 变量上下文 → 模板渲染
└── sender.py                 # 编排：检查开关 → 渲染 → NotifierHub 发送 → 记日志
```

### 3.1 sender.py 核心流程

```python
async def send_workflow_event(
    event_type: str,
    workflow_id: str,
    extra_vars: dict | None = None,
) -> dict:
    """
    工作流事件通知编排。

    流程：
    1. 检查全局开关 + 场景开关（关闭则跳过，记 suppressed 日志）
    2. 频次去重（同 event_type+workflow_id 5 分钟内已发送则跳过）
    3. 加载模板（enabled=1 的对应 event_type 模板）
    4. 构建 var context（renderer.py）
    5. 调用 renderer 渲染 title + body
    6. 调用 NotifierHub.send(NotificationEvent)
    7. 写 notification_log（含实际 payload 与状态）
    """
```

### 3.2 renderer.py 变量上下文

构建模板变量上下文，从 workflow_id 查询关联数据：

| 变量 | 说明 | 数据来源 |
|---|---|---|
| `{{workflow_id}}` | 工作流 ID | 入参 |
| `{{episode_date}}` | 节目日期 | Workflow.episode_date |
| `{{channel_name}}` | 频道名 | Workflow.channel.name |
| `{{audio_url}}` | 音频直链 URL | Review.audio_url |
| `{{review_url}}` | admin-web 审核详情深链 | `{base_url}/review/{review_id}` |
| `{{workflow_url}}` | admin-web 工作流详情深链 | `{base_url}/workflows/{workflow_id}` |
| `{{steps_summary}}` | 步骤摘要（markdown 列表） | WorkflowStep 查询 |
| `{{error_message}}` | 失败原因（仅 failed 模板） | Workflow.error |
| `{{duration_sec}}` | 音频时长秒（仅 success/review 模板） | Episode.duration |
| `{{failed_step}}` | 失败步骤名（仅 failed 模板） | extra_vars 传入 |

### 3.3 URL 构建

`base_url` 优先级：
1. `notify_admin_base_url` 配置（前端可手动填写）
2. `tunnel_service.public_url`（运行时动态获取）
3. `http://localhost:{APP_PORT}`（兜底）

路由：
- `review_url` = `{base_url}/review/{review_id}`（对应 admin-web 路由 `/review/:id`）
- `workflow_url` = `{base_url}/workflows/{workflow_id}`

### 3.4 频次去重

- 键：`f"notify:dedup:{event_type}:{workflow_id}"`
- 存储：TTLCache，5 分钟过期
- 命中去重时记 `suppressed` 日志，不发送

### 3.5 与现有 `_alert_operators` 集成

- `workflow_scheduler._run_workflow` 成功路径后 → 调用 `sender.send_workflow_event("workflow.pending_review", workflow_id)`
- `except StepFailedError` / `except Exception` → 调用 `sender.send_workflow_event("workflow.failed", workflow_id, {"failed_step": ..., "error_message": ...})`
- `_alert_operators` 保留作为系统级告警兜底（备播失败、备份失败等），不删除
- `sender.send_workflow_event` 内部异常时降级调用 `_alert_operators`

## 4. 钉钉消息卡片升级

升级 `DingTalkNotifier.send` 方法：

### 4.1 消息格式

- 接收 `NotificationEvent.extra` 中的 `action_url`（审核/工作流深链）与 `audio_url`
- 渲染为 **actionCard**（替代当前 markdown），支持 `singleTitle` + `singleURL` 按钮
- 正文使用 markdown 格式，含 `<font color>` 上色、`>` 引用、emoji 状态标识
- 卡片标题截断到 24 字符（钉钉 PC 端宽度限制）

### 4.2 消息示例

**待审核**：
```
标题: 📋 待审核 - wf-20260714-0006
正文:
# 📋 新闻待审核

**工作流：** `wf-20260714-0006`
**节目日期：** 2026-07-14
**频道：** 综合资讯
**时长：** <font color="#1890FF">12分58秒</font>

> 音频已合成完成，等待管理员审核发布

🔗 [在线试听](audio_url)
按钮: [前往审核] → review_url
```

**失败**：
```
标题: 🔴 工作流失败 - wf-20260714-0003
正文:
# 🔴 工作流执行失败

**工作流：** `wf-20260714-0003`
**失败步骤：** <font color="#F5222D">stitch</font>
**错误：** 音频时长超出范围...

> 已自动重试 3 次，请人工介入排查
按钮: [查看详情] → workflow_url
```

### 4.3 渲染逻辑

- `NotificationEvent.extra` 新增字段：`action_url`、`action_title`、`audio_url`
- `DingTalkNotifier.send` 检测 `extra.action_url` 存在时使用 actionCard，否则降级为 markdown
- actionCard payload：
  ```json
  {
    "msgtype": "actionCard",
    "actionCard": {
      "title": "...",
      "text": "markdown 正文",
      "singleTitle": "前往审核",
      "singleURL": "https://..."
    }
  }
  ```

## 5. 前端页面

新增 `admin-web/src/views/notification/NotificationConfig.vue`：
- 路由：`/notification`，仅 admin 可访问
- 侧边栏菜单：通知管理（icon: Bell）

### 5.1 页面结构（单页 Tab 切换）

**Tab 1: 基础配置**
- 全局开关（switch）
- 场景开关：失败 / 待审核 / 已发布（3 个 switch）
- 钉钉 Webhook URL（输入框）
- 钉钉加签 Secret（输入框，脱敏）
- admin-web base URL（输入框，placeholder 显示自动检测值）
- 测试发送按钮（发送测试通知，弹窗显示发送结果）

**Tab 2: 消息模板**
- 模板列表表格：事件类型 / 名称 / 启用开关 / 编辑按钮
- 编辑弹窗：
  - 标题模板输入框
  - 正文模板 textarea
  - 可用变量列表（点击插入到光标位置）
  - 预览按钮（调用后端预览接口）

**Tab 3: 发送日志**
- 表格：时间 / 事件类型 / 渠道 / 标题 / 状态 / 操作
- 操作：查看 payload（弹窗展示 JSON）/ 重发按钮
- 分页（每页 20 条）

### 5.2 API 层

新增 `admin-web/src/api/notification.js`：
- `getConfig()` / `saveConfig(data)` / `testSend()`
- `getTemplates()` / `updateTemplate(id, data)` / `previewTemplate(id, data)`
- `getLogs(params)` / `resendLog(id)`

### 5.3 路由配置

`admin-web/src/router/index.js` 新增：
```js
{
  path: 'notification',
  name: 'Notification',
  component: () => import('../views/notification/NotificationConfig.vue'),
  meta: { title: '通知管理', icon: 'Bell', requireRole: 'admin' },
}
```

`admin-web/src/layouts/Layout.vue` 侧边栏新增菜单项。

## 6. API 端点

新增路由 `app/routers/admin/notification.py`，前缀 `/admin/api/v1/notification`：

| Method | Path | 功能 | 权限 |
|---|---|---|---|
| GET | `/config` | 获取通知配置 | admin |
| PUT | `/config` | 保存通知配置 | admin |
| POST | `/test` | 发送测试通知 | admin |
| GET | `/templates` | 模板列表 | admin |
| PUT | `/templates/{id}` | 更新模板 | admin |
| POST | `/templates/{id}/preview` | 预览模板渲染效果 | admin |
| GET | `/logs` | 日志列表（分页） | admin |
| POST | `/logs/{id}/resend` | 重发某条日志 | admin |

所有端点需 admin 权限（`require_admin`）。

### 6.1 请求/响应示例

**GET /config 响应**：
```json
{
  "global_enabled": true,
  "failed_enabled": true,
  "review_enabled": true,
  "published_enabled": false,
  "dingtalk_webhook": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
  "dingtalk_secret": "****abcd",
  "admin_base_url": "",
  "auto_detected_base_url": "https://xxx.trycloudflare.com"
}
```

**PUT /config 请求**：
```json
{
  "global_enabled": true,
  "failed_enabled": true,
  "review_enabled": true,
  "published_enabled": false,
  "dingtalk_webhook": "https://...",
  "dingtalk_secret": "****abcd",
  "admin_base_url": ""
}
```

**POST /test 响应**：
```json
{
  "success": true,
  "message": "测试通知已发送",
  "results": [{"channel": "dingtalk", "success": true}]
}
```

## 7. 集成点

### 7.1 workflow_scheduler.py

- `_run_workflow` 成功路径（`_update_workflow_status(success)` 后）：
  ```python
  await self._send_notification("workflow.pending_review", workflow_id)
  ```
- `except StepFailedError`：
  ```python
  await self._send_notification("workflow.failed", workflow_id, {
      "failed_step": e.step_name,
      "error_message": str(e),
  })
  ```
- `except Exception`：
  ```python
  await self._send_notification("workflow.failed", workflow_id, {
      "error_message": str(e),
  })
  ```
- 新增辅助方法 `_send_notification`，调用 `sender.send_workflow_event`，异常时降级到 `_alert_operators`

### 7.2 review_service.py

- `handle_action` approve 后 → 发送 `workflow.published` 通知（依赖 `notify_published_enabled` 开关）
- 由路由层在 publish 成功后调用 `sender.send_workflow_event`

### 7.3 lifespan 启动

- 初始化预设模板（若 `notification_template` 表为空，插入 3 条预设：failed/pending_review/published）
- 从 `ai_config` 加载通知配置覆盖到 `DingTalkNotifier`（热更新）

### 7.4 预设模板内容

**workflow.pending_review**：
- 标题：`📋 待审核 - {{workflow_id}}`
- 正文：
  ```
  # 📋 新闻待审核

  **工作流：** `{{workflow_id}}`
  **节目日期：** {{episode_date}}
  **频道：** {{channel_name}}
  **时长：** <font color="#1890FF">{{duration_sec}}秒</font>

  > 音频已合成完成，等待管理员审核发布

  🔗 [在线试听]({{audio_url}})
  ```

**workflow.failed**：
- 标题：`🔴 工作流失败 - {{workflow_id}}`
- 正文：
  ```
  # 🔴 工作流执行失败

  **工作流：** `{{workflow_id}}`
  **失败步骤：** <font color="#F5222D">{{failed_step}}</font>
  **错误：** {{error_message}}

  > 已自动重试 3 次，请人工介入排查
  ```

**workflow.success**（已移除，工作流完成即 pending_review）

**workflow.published**：
- 标题：`🚀 节目已发布 - {{workflow_id}}`
- 正文：
  ```
  # 🚀 节目已发布

  **工作流：** `{{workflow_id}}`
  **节目日期：** {{episode_date}}
  **频道：** {{channel_name}}

  > 审核通过，节目已发布上线
  ```

## 8. 测试计划

### 8.1 单元测试（pytest）

- `backend/tests/test_notification_template_service.py`
  - 模板 CRUD
  - 变量渲染（`{{var}}` 替换）
  - 缺失变量降级为空字符串
- `backend/tests/test_notification_sender.py`
  - 全局开关关闭 → 跳过发送，记 suppressed 日志
  - 场景开关关闭 → 跳过发送，记 suppressed 日志
  - 频次去重（5 分钟内同 event_type+workflow_id）
  - 发送成功 → 记 success 日志
  - 发送失败 → 记 failed 日志
- `backend/tests/test_notification_dingtalk.py`
  - actionCard payload 渲染
  - 签名计算（已有测试覆盖）
  - 降级为 markdown（无 action_url 时）
- `backend/tests/test_notification_api.py`
  - GET/PUT /config
  - POST /test
  - GET/PUT /templates
  - POST /templates/{id}/preview
  - GET /logs
  - POST /logs/{id}/resend

### 8.2 集成测试

- `backend/tests/test_notification_integration.py`
  - 工作流成功 → 收到 pending_review 通知（mock NotifierHub）
  - 工作流失败 → 收到 failed 通知（mock NotifierHub）
  - 配置关闭 → 不发送但记 suppressed 日志
  - 模板渲染包含正确变量值

### 8.3 手动验证

1. 启动后端 + 前端
2. 访问 `/notification` 配置页
3. 填写钉钉 Webhook + Secret
4. 点击"测试发送"按钮 → 钉钉群收到测试消息
5. 编辑模板 → 点击"预览"查看渲染效果
6. 触发工作流（手动触发或等待 cron）→ 钉钉群收到通知
7. 钉钉消息按钮点击 → 跳转 admin-web 审核页
8. 审核通过 → 钉钉群收到 published 通知（若开关开启）
9. 查看发送日志 Tab → 看到所有通知记录

### 8.4 验证命令

```powershell
# 后端单元测试
cd backend
python -m pytest tests/test_notification_*.py -v

# 后端集成测试
python -m pytest tests/test_notification_integration.py -v

# 前端构建验证
cd ../admin-web
npm run build
```

## 9. 附加优化

1. **通知发送日志**：记录每条通知的 channel/event/status/payload，支持前端查看历史与失败重发
2. **测试发送按钮**：配置页一键发送测试通知，验证 webhook 有效性
3. **频次限制**：同类事件 5 分钟内去重（避免工作流连续失败刷屏）
4. **公网 URL 自适应**：通过 tunnel_service 获取公网地址，未启用隧道时降级为 `http://localhost:{port}`
5. **模板变量预览**：前端编辑模板时提供变量列表与渲染预览
6. **配置热更新**：保存配置后同步更新 `DingTalkNotifier` 实例（调用 `NotifierHub.reload()`）

## 10. 文件清单

### 新增文件
- `backend/app/models/notification_template.py`
- `backend/app/models/notification_log.py`
- `backend/app/services/notification/__init__.py`
- `backend/app/services/notification/template_service.py`
- `backend/app/services/notification/config_service.py`
- `backend/app/services/notification/log_service.py`
- `backend/app/services/notification/renderer.py`
- `backend/app/services/notification/sender.py`
- `backend/app/routers/admin/notification.py`
- `admin-web/src/views/notification/NotificationConfig.vue`
- `admin-web/src/api/notification.js`
- `backend/tests/test_notification_template_service.py`
- `backend/tests/test_notification_sender.py`
- `backend/tests/test_notification_dingtalk.py`
- `backend/tests/test_notification_api.py`
- `backend/tests/test_notification_integration.py`

### 修改文件
- `backend/app/models/__init__.py` - 导入新模型
- `backend/app/services/notifier/channels/dingtalk.py` - 升级 actionCard 渲染
- `backend/app/services/notifier/base.py` - NotificationEvent.extra 已有，无需改动
- `backend/app/services/workflow_scheduler.py` - 集成 sender 调用
- `backend/app/routers/admin/__init__.py` 或 `main.py` - 注册新路由
- `backend/app/main.py` - lifespan 初始化预设模板
- `admin-web/src/router/index.js` - 新增路由
- `admin-web/src/layouts/Layout.vue` - 新增菜单项
