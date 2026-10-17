根目录 `D:\code\otherProjects\20_News`（以下 file:line 均相对于此），只读复核，未改代码。

**R3（须先技术方案）** 守卫思路对，但有三坑：① `_is_sensitive_column` 对 `ai_config.config_value` 是整列命中（backend/app/services/db_admin_service.py:113-114），真实脱敏却按 config_key 动态判断（:134-137），按列剔除会误伤非密钥配置；字面量 `***` 极少见，但静默剔除会掩盖意图，建议敏感列前端不回传、只提交脏字段（views/maintenance/DatabaseAdmin.vue:390,499,512），后端直接拒绝并提示走专用重置。② 更关键：`import_rows` 的 replace 用 `INSERT OR REPLACE`（db_admin_service.py:466-468），SQLite 是整行删插，只剔除敏感列会把未提交的凭据置 NULL，仍毁数据；须改 `ON CONFLICT DO UPDATE` 仅更新显式列。③ 更新审计记录全量 values（routers/admin/db_admin.py:150），会把新密钥明文写进 audit_log，需脱敏。

**R1（须先技术方案）** 恢复瞬间回放会插 DOM，与 2 秒静默窗（utils/message.js:13-28）冲突。推荐：success/error/warning 入 FIFO，去重、上限 3~5、TTL；等 `_isRestoring` 结束再聚合补发；confirm/prompt 保持 reject、绝不回放（:55-63）；loading 不入队。更稳的是页内常驻通知区，移动端 INT-M101 已实现（routers/admin/mobile.py:51、views/mobile/Message.vue），桌面可复用。

**R2（可进 PRD，前端最小改）** 现有全量 GET/PUT（routers/admin/cos.py:57-80），bucket/cdn 无条件写（cos_config_service.py:139-143）；改 patch 要区分「缺省/清空」，属契约变更。「加载失败禁用保存+重试」更小且贴合现状；但草稿在失败后仍会恢复（CosConfig.vue:242-245），必须同时跳过或标记。

**R7（拆分）** 改 `reason = value.trim()` 即可（ManageAlert.vue:59）。同页 reload 失败回落 `enabled:false`（:41-44），会显示「生产运行正常」；后端维护检查异常按非维护放行（mobile_service.py:337-343、workflow_scheduler.py:614-624），DB 故障时停服失效。状态 upsert 幂等，但重复调用重复审计（:359-377），应先判已停。规格要求 super_admin+二次验证（运营端移动端适配-需求规格说明书.md:159,211），现角色仅 admin/operator（models/admin_user.py:13-21），接口只校验 reason（routers/admin/mobile.py:129-140）。

**R4（引导可进 PRD；审核状态进 PRD 决策）** 锚点命不中（guideConfig.js:71；WorkflowList.vue:54,72），兜底 `.top-bar .el-button` 会命中「重置」。现有 aria-label 来自 `label="手动触发"`（IconButton.vue:20,64），最短改 `[aria-label="手动触发"]` 并删错误兜底；长期 data-guide 更稳，但 IconButton 根是 tooltip，需显式透传。审核后端 4 态（models/review.py:13-25），前端 3 tab（ReviewList.vue:4-6）；SRS 明写三栏（需求规格说明书.md:400），第 4 tab 是产品决策，最稳是「已通过」内加 replaced 子筛选，后端 status 过滤已支持（review_service.py:64-66）。

**R5（可进 PRD）** 后端秒有模型注释（models/play_log.py:32），改后端会破坏契约，应前端改标签，两处都要改（StatsOverview.vue:84、mobile/Home.vue:54）。同接口隐患：完播率卡片 ×100（StatsOverview.vue:83,140），趋势按 0~1 却标「%」（:99）；Home 直接把 0~1 拼 `%`（Home.vue:52）。建议后端补 unit 元数据。

**R6（超时可进 PRD，须先实测网关）** `/ai/chat` 用 LLM_TIMEOUT_SEC，默认 30（config.py:216），前端全局 15s（api/index.js:18）先掐断。建议 `{ timeout: 130000 }`（UI 上限 120，AIConfig.vue:131），留响应余量，勿设 120000 与后端同时到点。仓内未发现 nginx 配置，公网经 Tailscale Funnel（api/cos.js:5-6），反代超时无法静态确认，须实测；低于 120s 只能流式/异步。

**A. 文档冲突/已写未实现**
- R7：SRS 要求 super_admin+二次验证（移动SRS:159,211），角色模型无此角色、接口无二次验证。
- R4：加第 4 tab 与 SRS 三栏冲突（需求规格说明书.md:400），详细设计却有 replaced（详细设计说明书.md:510）。
- R5：违反 SRS 验收「指标计算口径明确」（需求规格说明书.md:430），同一 completion_rate 三处三种刻度。
- R1：常驻收件箱已是 P0（移动SRS:125；mobile.py:51），不要再造第二套。

**B. 清单**
可进 PRD：R7 作用域与加载错误态（2FA 另立）；R5 前端统一格式化；R4 引导选择器+e2e、审核状态先定产品口径；R2 加载失败禁存（含草稿）。
先技术方案：R3 敏感列拒绝策略+import upsert+审计脱敏；R1 队列聚合与通知中心边界；R2 patch/乐观锁；R7 super_admin/二次验证；R6 网关不足时的流式方案。

Sources: [Tailscale CLI](https://tailscale.com/docs/reference/tailscale-cli)