### 系统清理（`/maintenance`）

- **现状描述**：一屏三块清理能力（缓存 / 数据库 / 日志）+ 顶部存储状态卡，代码在 `frontend/src/pages/Maintenance/Cleanup.tsx`（根容器 `:203` 有 `page-container`，引导锚点合规）。每块结构一致：范围下拉（Cache `:279-288`、DB `:334-345`、Log `:408-417`）+「仅预览」开关（`:291-298` 等）+ 主按钮 + 内联结果区（`renderResult :174-200`）。真实执行走 `globalThis.confirm`（`:88/:116/:143`），结果来自 `POST /api/maintenance/{cache|database|logs}`（`frontend/src/api/maintenance.ts:10-11`，后端 `backend/xianyu_hunter/web/routes/api_maintenance.py`）。菜单四项 label 在 `config/menu_registry.yaml:141-147`、`sheetRegistry.tsx:71`、`MainLayout.tsx:72,105` 三处一致，是本切片唯一完全对齐的项。

- **问题清单**
  1. `[高]` 「清理范围 → 浏览器数据」选项（`Cleanup.tsx:285`）与其确认文案（`:88`「确认清理缓存？此操作不可撤销。」）—— 后端该分支会 `shutil.rmtree` 掉 `data/webview_data_*`，而注释明确该目录"存放反检测指纹/cookies"（`api_maintenance.py:140-152`），删除即全部闲鱼登录态失效；UI 既不点名"会登出账号、需去反爬登录管理重新导入 Cookie"，也不区分它与"清理 pycache"的量级差 —— 首次用户一次顺手清理即可打瘫整条抢单链路且不知如何恢复；高频用户则长期把最危险的一项当成普通缓存清理。
  2. `[中]` 三个真实删除都只靠浏览器原生对话框（`:88/:116/:143`）—— 不显示用户当前所选 `target`/`days`，不显示预计条数，暗色模式下为刺眼白底；同页日志分支已改用 `message`（`:159-164`），同组数据库维护用输入 `CONFIRM_DELETE`（`DatabaseAdmin.tsx:394-404`）—— 高频：确认时只能靠记忆判断自己选了什么范围。
  3. `[中]` 预览态与真实执行态按钮文案完全相同（`:309` "清理缓存"、`:383` "清理数据库"、`:458` "清理日志"，而 `dry_run` 默认 true：`:42-55`），且缓存/数据库分支在 `dry_run` 下不发任何反馈（`:101-104`、`:129-132` 仅在 `!dry_run` 时 `message.success`）—— 移动端同功能按钮文案会切成「预览」/「立即执行」（`frontend/src/mobile/pages/Cleanup/index.tsx:109,128`）并给 `message.info` 预览回执（`:79-82`）—— 首次用户点"清理数据库"其实只做了预览，却以为数据库已瘦身；桌面端比移动端落后。
  4. `[中]` 「临时文件」一词在本页有三种含义（`:286` 选项 label="临时文件"）—— 后端该 target 实际删源码目录下 `__pycache__`（`api_maintenance.py:192-193` + `:156-168`），而状态统计的 `temp_files` 又是 `/tmp/xianyu_*`（`:130`，Windows 上恒为 0），卡片描述却写"清理浏览器数据目录和 Python 缓存文件"（`Cleanup.tsx:272`）但没有"Python 缓存"这一独立选项 —— 高频：想只清 pycache 做不到，只能连浏览器数据一起清（回到问题 1）。
  5. `[中]` 状态卡与清理结果互相矛盾：真实执行后立刻 `loadStatus()`（`:102/:130/:162`），但 `/api/maintenance/status` 带 `@cached_ttl(60, stale_while_revalidate=True)`（`api_maintenance.py:70`）—— 数据库/日志"释放 X MB"与刷新后显示的体积对不上，用户判为"清理没生效"，再点一次真实删除 —— 首次/高频都痛。
  6. `[中]` 删除前看不到作用范围：状态卡只展示 tasks/items/events 三张表（`:227`，`api/types.ts:756-761` 也只声明这三个），后端其实还统计了 `orders/task_links/notifications`（`api_maintenance.py:80`）—— 而 `old_items` 依赖 `task_links` 判定"未关联"（`:239`）、`sold_items` 删的正是 `task_links`（`:266-282`）—— 用户在信息不全的"存储状态"下授权跨表删除，且没有同组 DatabaseAdmin 那样的级联预览。
  7. `[中]` 日志清理选项 `all` label 为「全部清理」（`:415`）—— 后端 `all` 只删"早于 N 天 或 &gt;10MB"的文件（`api_maintenance.py:407-410`），绝不会清空目录；天数输入在 `all` 下仍显示（条件 `:421` 包含 `all`）掩盖了这一点 —— 首次用户按字面预期后磁盘没释放，反复执行真实删除。
  8. `[中]` 无"清理记录"回执入口：清理动作写 `events` 表 `type=maintenance.*`（`api_maintenance.py:437-451`），但本页没有任何查看历史/审计的按钮；同组两个维护页都有审计抽屉（`DatabaseAdmin.tsx:573`、`VectorAdmin.tsx:222`）—— 高频排障"昨天到底删了什么"只能去事件时间线手搜，且后端审计写失败是 `except: pass`（`:452-453`）静默丢弃。
  9. `[低]` 「保留天数」对 `vacuum`/`sold_items` 无意义却常驻（`:348-363`；后端这两支不读 days：`api_maintenance.py:256-283,286-305`），移动端已按 target 隐藏（`mobile/pages/Cleanup/index.tsx:225`）。
  10. `[低]` 结果区硬编码颜色（`:180` `#52c41a`、`:192` `#ff4d4f`）且仅靠颜色区分成功/失败；清理明细用 12px 灰字逐条平铺（`:184-188`），清 `__pycache__` 动辄上百条会把卡片撑成一屏 —— 与页面其余部分使用 `var(--xh-*)` token 的约定不一致。
  11. `[低]` 页头没有标题，只有一行 secondary 文案"缓存清理 · 数据库清理 · 日志清理"（`:206-208`），而同组 VectorAdmin 有 `h2` + 说明（`VectorAdmin.tsx:216-219`）；菜单名"系统清理"也窄于本页实际能力（它还做 VACUUM）。

- **优化建议**
  1. 「浏览器数据」选项改为独立危险项：文案改「浏览器数据（含闲鱼登录态/Cookie）」，确认框内点名"删除后需在『反爬登录管理』重新导入 Cookie"，并把它从 `all` 组合里剔除（`api_maintenance.py:189`）。成本：低（文案 + Select label）。
  2. 用统一危险确认组件替换 `globalThis.confirm`，在正文回显"范围=已售商品关联 / 保留 30 天 / 预览命中 412 条"，沿用 `dry_run` 预览计数作为确认素材（数据已在返回值 `cleaned`/`total_deleted` 里）。成本：中。
  3. 按钮文案随 `dry_run` 切换为「预览可清理内容」/「立即清理」，预览分支补 `message.info(count)`（照抄 `:159-160` 与移动端 `:100-131`）。成本：低。
  4. 选项与统计口径统一：`temp` → label 改「Python 缓存（\_\_pycache\_\_）」，另加 `pycache`/`temp` 两个真选项（后端 `:130` 与 `:192` 拆分）；状态卡增显 `temp_files`。成本：中（前后端各一处）。
  5. 清理成功后由后端失效 `maintenance_status` 缓存 key（`api_maintenance.py:70`），或前端刷新时带 `force=1` 查询参。成本：低。
  6. 状态卡补齐 orders/task_links/notifications 计数（后端已返回，仅需扩 `api/types.ts:755-772` 与 `Cleanup.tsx:227`），并在确认框列出"将影响的表 + 条数"。成本：低-中。
  7. `all` label 改「按天数 + 大文件（合并清理）」，`large_logs`/`all` 场景的天数说明写明 cutoff 语义。成本：低。
  8. 页头加「清理记录」按钮，`GET /api/maintenance/audit-log`（复用 `api_db_admin.py:924-956` 模式，前缀换 `maintenance.%`）+ 与 DatabaseAdmin 同构的抽屉。成本：中。
  9. `target` 为 `vacuum`/`sold_items` 时隐藏天数（照抄移动端 `:225`）。成本：低。
  10. 结果区改 `&lt;Alert type=success/error&gt;` + `Collapse` 折叠明细，颜色换 token。成本：低。
  11. 加 `h2` 标题「系统清理」+ 一句话说明（含 VACUUM），与 VectorAdmin 对齐。成本：低。

- **优先级**：**高**。理由：本页是整组唯一会把"登录态"和"业务数据"一并真删的入口，而它的确认强度（原生 confirm 一句话）与最危险的选项（浏览器数据）严重不匹配；同时它的成功/失败回执被 60s 缓存与"预览无反馈"双重削弱，用户无法核对结果。

---

### 数据库维护（`/maintenance/db`）

- **现状描述**：左 220px 表列表 + 右侧动态列 Grid 的在线 CRUD 工作台（`frontend/src/pages/Maintenance/DatabaseAdmin.tsx:594-745`，根容器 `:567` 有 `page-container`），工具栏含 新增/批量删除/导入/导出 CSV/导出 JSON/查看表结构/搜索（`:638-667`），删除前做级联影响预览并要求输入 `CONFIRM_DELETE`（`:383-444`），另有表结构抽屉（`:801-833`）与审计日志抽屉（`:836-870`）。后端 11 张表白名单、应用层级联、审计写 `events` 表 `type=db_admin.*`（`backend/xianyu_hunter/web/routes/api_db_admin.py:45-57,245-276,924-956`），明确不做 DDL（`:11-12`）。整体是维护组里安全设计最成熟的一页（预览 + token + 审计三件齐全），问题集中在"编辑语义"和"回执"。

- **问题清单**
  1. `[高]` 编辑弹窗的主键字段可以输入（`ColumnFormFields :165-211` 全程未传 `disabled`，尽管 `:171` 注释声称"主键在 update 时禁用编辑"）—— 后端更新时把主键直接丢弃（`api_db_admin.py:650-651 continue`）—— 用户改主键点「更新」得到 `message.success('已更新')`（`:463`），实际主键原封不动，且下一次读到的还是旧值 —— 首次用户反复重试以为页面坏了；高频用户会以为数据被改了而去改别的字段，造成真实数据错乱。
  2. `[高]` 无法把任何字段清空：提交前统一丢弃空值（`:454-457 if (v === '' || v === undefined) continue`），后端只更新传入的列（`api_db_admin.py:658-659`）—— 想清掉 `orders.error`、`task_links.note`、`sellers.credit_score` 等（列语义见 `:157-217`）永远清不掉，但仍提示"已更新"；若整行字段都被清空则后端抛 400「没有可更新字段」（`:656`），对用户完全不可理解 —— 高频运维最痛（纠错场景基本都是"把脏值置空"）。
  3. `[中]` 删除成功回执丢掉级联明细：`handleDelete` 只报「已删除」（`:360`），`handleBatchDelete` 只报 `affected/requested`（`:372-373`），而后端两条路径都返回了 `cascade` 字典（`api_db_admin.py:715,755`）—— 删 1 条 `tasks` 会连带删 `items/orders/events/task_links/task_deps`（`:246-254`），量级可达数千条，用户在结果里完全看不到 —— 首次/高频都无法事后核对影响面。
  4. `[中]` 点击行内「删除」后先 `await` 级联预览才弹窗（`:383-387` + `buildCascadeHtml :132-149`），期间按钮无 loading、无占位 —— 慢盘/大表下"点了没反应"数秒（首次用户会连点多次弹出多个确认框）；而预览失败时只渲染一句灰字「级联预览加载失败」（`:147`）却仍可输入 token 完成删除（`:387-411`）—— 影响未知的不可逆操作被放行。
  5. `[中]` 切表时未清空上一张表的 `columns`/`rows`（`:230-241` 状态，`:308-316` 仅 `loadSchema` + 重置分页/搜索）—— 新表数据加载中，Grid 仍是"旧列头 + 旧行/新行混排"，此时点击行内操作会用旧表的主键列名去操作新表（`pkCol!` 取自 `columns`：`:326,462,710`）—— 属真实误删/误改风险（时序窗口需实测确认，但代码路径无任何防护）。
  6. `[中]` 「导出 CSV / 导出 JSON」无视当前搜索且无进度反馈（`:648-653` → `api/dbAdmin.ts:69-74` 只传 `format`；后端 `api_db_admin.py:775 SELECT * FROM {table}`）—— `events` 表全量导出可达数十万行，`handleExport`（`:479-493`）没有任何 loading 态，按钮点下去长时间无响应；同时页顶 Alert 又把它当唯一的备份手段推荐（`:582-592`）—— 用户以为导出的是筛选结果，事后发现备份/取数口径不对。
  7. `[中]` 审计日志抽屉与错误态同形：`:573` 不 `await` 就 `setAuditDrawerOpen(true)`，`loadAuditLog`（`:496-505`）失败只 `message.error` + `console.warn` —— 抽屉照常打开并显示"暂无数据"的空表，恰好在刚做完批量删除最需要核对时，用户会误判"删除没被记录"；此外本页只查 `type LIKE 'db_admin.%'`（`api_db_admin.py:934`），同组"系统清理"记的 `maintenance.*`（`api_maintenance.py:438`）与向量库审计（另一张 `chatbot_audit_logs` 表，`api_vector_admin.py:56-61`）在这里一律查不到 —— 页头"所有写操作均记录审计日志"（`:570`）的承诺跨页不成立。
  8. `[中]` 导入弹窗谎称有选择：确认文案「请选择冲突处理：」（`:540`）但只有一个 okText「跳过冲突」（`:542`），`mode` 硬编码 `'insert'`（`:546`），后端 `replace` 分支与 `INSERT OR REPLACE` 早已实现（`api_db_admin.py:844-845`，`api/dbAdmin.ts:81`）—— 想覆盖同主键记录只能先手工删；同时 5000 行上限（`api_db_admin.py:822`）在 UI 无任何提示（`:777,789` 两段说明文字只讲格式），用户选完 2 万行文件才收到一条报错。
  9. `[低]` 表中文名单前端另硬编码一份（`TABLE_LABELS :46-58`）与后端 `ALLOWED_TABLES`（`api_db_admin.py:45-57`）两处维护，未命中即退化为裸英文表名（`:624`）；`t.rows.toLocaleString()`（`:627`）只给行数不给表含义。
  10. `[低]` 确认 token 定义重复三处（本页 `:40` 本地 `const CONFIRM_TOKEN`、`api/dbAdmin.ts:12`、`api/vectorAdmin.ts:5`），且用 `Input.Password` 掩码输入（`:395,427`）—— 用户在执行不可逆删除时看不到自己敲了什么，大小写错一位就反复失败（提示语"区分大小写"就在旁边 `:394`）。
  11. `[低]` 选中表用告警色（`background: var(--xh-bg-warning)` + 3px `#FF6200`，`:613-614`）与"危险/告警"语义撞色；文件末尾自造局部 `Text` 组件硬编码 `#999`（`:876-878`，用于 `NULL` 占位 `:345`、列类型 `:177`），暗色模式对比度差且偏离 `var(--xh-text-tertiary)`；审计"操作"列颜色只区分 `failed`/其他（`:854`），高危 `batch_delete`（后端记 `level=warn`，`api_db_admin.py:754`）与 `create` 同为蓝。
  12. `[低]` `Sider width={220}` 固定（`:596`）无响应式；`PAGE_SIZE = 50`（`:60`）且 `showSizeChanger: false`（`:727`），百万行 `events` 要 2 万次翻页，也没有"仅查看最近 N 天"的快捷过滤。

- **优化建议**
  1. `ColumnFormFields` 在 `mode==='update'` 时对 `col.primary_key` 传 `disabled` 并显示锁图标 tooltip；或前端提交时剔除主键（与后端 `:650` 对齐）。成本：低。
  2. 提交不再丢弃 `''`，改为对可空列显式传 `null`（表单加「置空」小开关），不可空列校验必填；「没有可更新字段」改前端拦截并提示"请至少修改一个字段"。成本：中。
  3. 删除成功后用 `Alert`/`notification` 展示 `result.cascade` 明细（"删除 items.task_id 1 832 条…"），并把 `loadTables()` 的行数变化一并呈现为"本表 12→11 行"。成本：低。
  4. 行内删除按钮加 `loading`（预览期间），预览失败时把 okButton 保持 disabled 并要求重试预览，不允许"影响未知也能删"。成本：低。
  5. `setActiveTable` 同批 `setColumns([]) / setRows([]) / setSelectedRowKeys([])`，或在渲染层用 `columns 与 activeTable 是否匹配` 做守卫；`pkCol` 缺失时禁用编辑/删除列。成本：低。
  6. 导出按钮加 `loading` 与"导出整表（当前筛选不生效）/导出筛选结果"二选一，`exportRows` 增加 `search` 透传（后端 `:760-776` 补 `WHERE` 复用 `DbAdminSearchService`）。成本：中。
  7. 审计抽屉失败时显示错误态 + 「重试」而非空表；后端把 `events` 审计查询的 `type` 前缀扩为 `('db_admin.','maintenance.')`，或新增"维护审计"统一视图；页头文案改为"本页操作记录在审计日志（仅 db_admin 前缀）"。成本：低-中。
  8. 导入确认框改为 `Radio`「跳过冲突 / 按主键覆盖」映射 `mode`，说明区列出"单次上限 5000 行、列名需与 schema 一致"。成本：低。
  9. `TABLE_LABELS` 由后端在 `/api/db-admin/tables` 直接返回 `label`（`api_db_admin.py:493-504`），前端删掉硬编码表。成本：低。
  10. token 常量收敛到一处并导出（`api/dbAdmin.ts:12`），输入框改 `Input` 明文 + 粘贴禁止。成本：低。
  11. 选中态改中性高亮（`token.colorPrimaryBg`），`Text` 直接用 `Typography.Text`；审计标签集中为 `AUDIT_LEVEL_COLOR` 映射，delete/batch_delete/import 归 danger 色。成本：低。
  12. `Sider` 折叠为窄屏下拉选表；`showSizeChanger: true` + `pageSizeOptions`，并加"时间倒序/最近 7 天"快捷。成本：低-中。

- **优先级**：**高**（问题 1、2）。它们是"提示成功但数据未变"的典型误导，且都发生在唯一的结构化纠错通道（在线编辑）上；其余问题多为 中 回执/作用范围缺失，本页的确认强度基线反而应作为其他维护页的对齐目标。

---

### 批量采集（`/batch-refresh`）

- **现状描述**：双 Tab（当前执行 / 执行历史，Tab 选择持久化 `frontend/src/pages/Maintenance/BatchRefresh.tsx:131-152`，根容器 `:138` 有 `page-container`）。当前执行页 = 进度卡 + 4 指标 + 左「配置热更新/任务控制」右「变更日志」（`:378-698`），历史页 = 4 状态统计 + 筛选卡 + 表格 + 详情抽屉（`:960-1122`）。后端 `api_batch_refresh.py` 在调度器缺失时返回 `status="unavailable"`（`:60-77`）、历史接口同时返回筛选后 `total` 与全量 `status_counts`（`:316-323`）。三处 label「批量采集」一致（`menu_registry.yaml:155-161`、`sheetRegistry.tsx:75`、`MainLayout.tsx:77,107`）。

- **问题清单**
  1. `[高]` 「清空全部」按钮是跨账号全表删除（`:1067-1075` → `handleCleanup(0)` `:808-817`；后端 `api_batch_refresh.py:386-392` 当 `days==0` 时直接 `DELETE FROM BatchRefreshHistoryRow`，注释明写"为什么不分用户：days=0 是全局清空"，而 `days&gt;0` 分支按 `user_id` 隔离 `:394`）—— Popconfirm 只写"确认清空全部历史记录？此操作不可恢复"，未提示"包含其他账号的执行历史" —— 多账号部署下一次误点抹掉同伴的全部追溯数据；且该不可逆操作只有 Popconfirm，同组 DatabaseAdmin/VectorAdmin 要求输入 `CONFIRM_DELETE`。
  2. `[中]` 概览四卡的口径互相矛盾：「总执行次数」取筛选后的分页 `total`（`:966-969`），「已完成/已取消/已失败」取未按筛选过滤的聚合 `status_counts`（`:975-996`；后端 `api_batch_refresh.py:316` 仅按 `user_id`）—— 一旦带筛选，出现"总执行次数 5、已完成 200"这种自相矛盾组合，用户判为数据丢失或统计坏了 —— 首次与高频都会误判。
  3. `[中]` 数字 0 在同一页有两种相反语义：配置项 tooltip「0=永不清理」（`:582`；后端 `api_batch_refresh.py:39-40`）与「清空全部」用 `days=0`（`:1069`；后端 `:375,380`）—— 用户可能把保留天数设 0 以为"立刻清理"，实际是永不自动清理。
  4. `[中]` 调度器不可用时把唯一能纠正它的开关禁掉了：Alert 明确告诉用户"需 ② `batch_refresh.enabled=true`"（`:400`），但保存按钮 `disabled={unavailable}`（`:519`）、整张表单 `disabled={unavailable}`（`:531`）—— 后端在 unavailable 时其实允许热更新配置（`api_batch_refresh.py:112-113` 注释"调度器未启动时，仍允许更新全局 config 单例"）—— 首次用户陷入"要按提示改，但 UI 不让改"，只能去手改 yaml + 重启后端。
  5. `[中]` 停止态渲染成失败态、且提示先于结果：`stopping` 时 `Progress status='exception'`（`:439-444`）显示红色失败进度条，`handleStop` 立刻断言"停止请求已发送，未处理的商品已持久化，下次触发将从断点续传"（`:324`），而后端只保证请求 500ms 内返回、实际生效在当前 item 之后（`api_batch_refresh.py:167-169`）—— 若持久化失败，用户已经收到了一条成功断言（需实测确认后端失败路径）。
  6. `[中]` 状态未知被显示为"未启动"：`loadStatus` 失败仅 `message.error` 且 `status` 保持 `null`（`:204-207`），指标 formatter 兜底 `'unavailable'`（`:466`），四种状态 Alert 在 `null` 时全部不渲染（`:395-430`）—— 网络中断/401 时页面呈现"调度器状态=未启动 + 配置已禁用"，与真实故障毫无区分，用户会去重启正常运行的采集 —— 三态里 error 完全缺位。
  7. `[中]` 「重置」按钮不会真正重查（`:776-784`：清 state 后 `setTimeout(loadList, 0)`，`loadList` 是 `useCallback([buildQuery])` 的旧闭包，`buildQuery` 仍携带旧筛选值 `:732-752`）—— 清空筛选后表格仍显示上一次筛选的结果（且无任何提示），用户以为"还有数据"或以为重置失效（闭包时序需实测确认，代码路径明确）。
  8. `[低]` 「变更日志条数 X / 50」分母是接口返回上限而非总量（`:494-497`；后端 `api_batch_refresh.py:183` 固定 `[-50:]`，内存上限 `_MAX_CHANGE_LOG=1000` 见 `:51`）—— X=50 时无法区分"正好 50 条"和"已丢弃若干"，同页说明又并列"内存上限 1000"，两套数字。
  9. `[低]` 后端专门下发的 `control_available` 字段（`api_batch_refresh.py:193`）前端从未使用，控制按钮可用性由本地 `running/paused/inProgress` 推断（`:617,631,643`）—— 状态机演进时按钮语义必然漂移。
  10. `[低]` 历史筛选持久化不一致：`filterStatus/filterSource` 用 `usePersistentState`（`:713-722`），`task_id`/日期区间用普通 `useState`（`:723-724`）—— 刷新后一半条件保留一半丢失，用户以为是筛选 bug。
  11. `[低]` 变更日志「商品 ID」是纯文本（`:667-672`）不能跳商品详情，也不展示变更前后值（后端只存 `changed_fields` 名单，`api_batch_refresh.py:949-955`）—— 高频排障"价格变成多少"必须去商品列表手搜；详情抽屉完成度 Progress 用 `(success+failed)/total` 漏算 `skipped`（`:1183`），已完成的批次显示不足 100%，与状态"已完成"打架。
  12. `[低]` `autoRefresh` 持久化为 true 后每次进入页签即 3s/10s 轮询（`:167-171`、`:219-237`）却无"正在每 3 秒轮询"的可见提示；切换页签会重挂载组件（`components/SheetWorkspace/SheetContent.tsx:50-52`），进度条与 `forceFastPoll`（`:175`）、表单 dirty 标记（`:185`）全部丢失。

- **优化建议**
  1. `days=0` 分支后端改为按 `user_id` 过滤，或前端「清空全部」拆成「清空本账号全部」并加 `CONFIRM_TOKEN` 输入（复用 `DatabaseAdmin.tsx:387-411` 模式）；文案明确作用范围。成本：低-中。
  2. 概览四卡统一到同一查询：要么 `status_counts` 也带筛选（后端 `api_batch_refresh.py:316` 透传筛选条件），要么卡片标题改「筛选结果数 / 全部已完成」。成本：低。
  3. 配置项文案把 `0` 改为「不清理」并把清空按钮文案改为「立即清空历史（不受保留天数影响）」；两处不再共用同一个数字隐喻。成本：低。
  4. `unavailable` 时不禁用 `enabled` 与 `interval_minutes`（后端支持热更新），只在 UI 标注"调度器未运行，保存后下次启动生效"。成本：低。
  5. `stopping` 用 `status='normal'` + 灰色 + "停止中"文案；`handleStop` 成功提示降级为"停止请求已发送"，待状态转 `idle` 后由状态 Alert 给出最终回执。成本：低。
  6. 引入 error 态：`loadStatus` 失败时 `setStatus(null)` 改为记录 `error`，指标区显示"状态获取失败 + 重试"，不再兜底成"未启动"。成本：低。
  7. `handleReset` 改为在 state 更新后由 `useEffect`/依赖驱动重查（或让 `loadList` 接受显式 query 参数），避免旧闭包。成本：低。
  8. 指标改「变更日志（最近 50 条，内存保留 1000）」去掉 `/50` 假分母；后端补 `change_log_total` 字段。成本：低。
  9. 按钮 disabled 条件改用 `status.control_available`。成本：低。
  10. `task_id`/日期区间一并持久化（或反之取消前两者的持久化），保持单一口径。成本：低。
  11. 商品 ID 加 `Link`/`openSheetWithNotification` 跳详情；后端 `changed_fields` 升级为 `{field, before, after}`，详情抽屉按 `success+failed+skipped` 计完成度。成本：中。
  12. 轮询中在开关旁显示"每 3s 自动刷新（上次 12:03:11）"；把轮询提升到 store 或将进度写入 sheetStore 以免切页签丢失。成本：中。

- **优先级**：**高**（问题 1）。跨账号不可逆清空 + 确认强度低于同组基线；其余 error 态缺失与重置无效为 中，属"状态缺失导致误判"的集中区。

---

### 反爬登录管理（`/anticrawl`）

- **现状描述**：六卡栅格（登录策略评估 / 会话管理 / 健康检查 / Cookie 分层管理 / 指纹信息 / 频率伪装统计）+ Cookie 更新弹窗，代码在 `frontend/src/pages/AntiCrawl/index.tsx`（会话卡、健康卡已拆为 `SessionCardCol :905-986`、`HealthCardCol :992-1074`）。为压 Sonar 复杂度，全部数据加载被抽成模块级 `fetch*`（`:227-287`）、全部操作被抽成 `run*`（`:308-443`）。后端 `api_anticrawl.py` 提供 strategy/session/health/fingerprint/freq/cookies 六族接口（`frontend/src/api/anticrawl.ts:154-211`）。菜单 label 四处一致（`menu_registry.yaml:162-168`、`sheetRegistry.tsx:76`、`MainLayout.tsx:78,108`）。

- **问题清单**
  1. `[高]` 五个数据加载全部静默吞错（`fetchStrategy :227-237`、`fetchSession :239-246`、`fetchFingerprint :248-255`、`fetchFreqStats :257-264`、`fetchCookieLayers :266-276`，catch 内只有 `console.error`，无 `message`、无 error state）—— 而 JSX 全用 `strategy &amp;&amp;`、`session &amp;&amp;`、`cookieLayers &amp;&amp;`、`freqStats &amp;&amp;`、`fingerprint?.profile ?` 条件渲染（`:567`、`:934`、`:648`、`:712`、`:776`）—— 后端未启动/401/500 时整页六张卡片变成空白，只剩页顶一个「刷新」按钮（`:544-548`），用户完全无法区分"系统还没有数据"与"接口全部失败" —— 首次用户（最常见就是刚装完未登录）看到的就是一个空壳页面，且会得出"反爬没配置"的错误结论。
  2. `[中]` 页面根元素不是 `page-container`（`:543 &lt;div style={{ padding: 24 }}&gt;`）—— 本页引导以 `.page-container` 为高亮锚（`frontend/src/guides/menuGuides.ts:171-173`）—— 首次引导 Tour 对本菜单整段无法定位、无法展示。
  3. `[中]` 引导文案描述了本页不存在的能力：`menuGuides.ts:171-173` 写"管理闲鱼登录态、Cookie 注入、多账号轮换与 QPS/延迟反爬策略，风控触发自动暂停"，但本页没有任何账号轮换 UI、没有 QPS/延迟配置项（只有统计展示 `:759-836`），"策略"仅是一个 `recommended` 只读 Tag（`:572`）+ 一个初始化按钮（`:590-599`）—— 首次用户按引导来找"轮换"和"QPS 设置"会完全找不到，且不知道去哪。
  4. `[中]` 破坏性/影响运行态的操作确认口径过低且不说明后果：「停止会话」无任何确认直接执行（`:972-981` → `runStopSession :336-347`），实际会停掉 TokenRenewer 后台续期（本页自己的 Alert 就写着"登录/导入/注入完成后会自动启动 TokenRenewer 后台续期" `:925-933`）；「初始化协调器」会重启浏览器协调器（Launch/CDP 切换 `:590-599`）也无影响说明；「主动失效」层有 `Modal.confirm` 但标题直接抛内部层名 `确认失效 ${layer} 层？`（`:365-366`），只有 `identity` 提示级联后果（`:368`），`session`/`tracking` 的后果一概空白 —— 高频用户在最需要"停一停"的地方最看不到提示。
  5. `[中]` 「CDP 模式」开关是前端本地偏好（`:462-464 usePersistentState('xh.anticrawl.useCdp')`、UI `:563`），真实生效模式由后端 `initialize` 返回（`:312` 模板 `协调器已初始化（${result.mode} 模式）`），而 `handleAsyncResult`（`:120-132`）优先展示 `result.message` —— 用户以开关判断当前模式，可能与后端实际模式相反（后端 `message` 内容需实测确认）；开关旁也没有"切换需重新初始化才生效"的说明。
  6. `[中]` 轮询无条件执行且失败静默：`:493-508` 三个 `setInterval`（会话 10s、频率 10s、Cookie 层 30s），而代码注释写的是"会话活跃时每 10 秒刷新"（`:495`）与实现不符（无条件轮询）；轮询走的还是同一批静默 `fetch*` —— 页面上的"运行时间/Token 年龄/Cookie 层状态"可能是几分钟前的旧值，界面无"最后更新时间"与"数据陈旧"提示（`:934-958` 只显示数值）。
  7. `[中]` Cookie 更新弹窗与"分层"标题不符（`:840-896`）：标题「分层更新 Cookie」（`:841`）但输入是一个整串 `TextArea`（`:882-888`），无按 identity/session/tracking 分组、无勾选只更新某层，分层完全交给后端自动分类（说明文字 `:854-857`）；「从浏览器导入（覆盖文本框）」（`:870-878`）覆盖用户手工编辑内容前无任何确认（`runImportFromBrowser :399-418` 直接 `setCookieInput`）。
  8. `[低]` 中英混杂 + 实现细节直呈：卡片标题与字段名混用「CDP 模式」（`:563`）、「UA」「Profile」「GPU」「Stealth 脚本」（`:715,717,734,743`）、Cookie 层名直接渲染英文 key（`:657 {layer}`），中文解释却只在底部 Alert（`:692-694`）；`Stealth 脚本 N 个（指纹 + AWSC 伪装）`（`:743-745`）对运营用户无行动指引。
  9. `[低]` 空态把两种原因合并成一句话：指纹卡空态提示"CDP 模式或未初始化"（`:751`）—— 用户不知道自己是哪种、下一步该点哪个按钮（两个动作分别在本页左上和右上卡片）；频率伪装卡只出数字（`:776-827`），无健康区间/趋势参照，说明 Alert 是面向开发的算法描述"使用对数正态分布…"( `:828-834`)。
  10. `[低]` 状态可视化两套并存：`Badge`（`:653-660`、`:920`）与硬编码 `valueStyle` 颜色（`:940,953,1032-1053` 的 `#52c41a/#ff4d4f/#8c8c8c`）；WAF 状态用 `Statistic` 显示中文标签但无颜色语义（`:1049-1055`，映射表 `:65-69`），"已熔断"与"正常"同色同形。

- **优化建议**
  1. 统一 `useRequest` 式三态：每个 `fetch*` 失败时写入 `error` 状态，卡片渲染 `Alert type=error + 重试`，页顶加一条"X 项数据加载失败"汇总；首次进入若无任何数据且接口 401，直接引导到登录/初始化。成本：中。
  2. 根元素改 `&lt;div className="page-container"&gt;`（`:543`）。成本：极低。
  3. 修正 `menuGuides.ts:171-173` 文案与本页实际能力一致（去掉"多账号轮换/QPS 策略"，或把这些能力真的搬进来）；卡内空态加"去账号管理"跳转。成本：低。
  4. 「停止会话」加 `Modal.confirm` 说明"停止后 _m_h5_tk 不再自动续期，X 分钟后登录态失效"；「初始化协调器」说明"会重启浏览器会话，运行中任务可能中断"；「主动失效」标题用中文层名映射（复用 `:692-694` 的说明），并给出每层失效后果。成本：低-中。
  5. CDP 开关旁显示后端回报的实际模式（`strategy`/`session` 里补 `mode` 字段），未初始化时标注"仅影响下次初始化"。成本：中。
  6. 轮询改为活跃态才轮（按注释意图），并在卡片 extra 展示"更新于 HH:mm:ss / 数据可能已过期"；轮询连续失败 3 次转为错误态。成本：低-中。
  7. 弹窗改为三个 `Collapse` 分组各自的 cookie 列表 + "只更新本层"开关；导入前若文本框非空则二次确认覆盖。成本：中。
  8. 术语中文化并集中映射（`UA→浏览器标识`、`Profile→指纹配置`），实现细节（Stealth/AWSC）移到 tooltip。成本：低。
  9. 指纹空态拆成两种情形判断（`session.active`/`strategy` 是否 CDP）；频率统计加阈值参照（如噪声占比合理区间）与"异常时怎么办"链接。成本：中。
  10. 状态展示统一为一个 `STATE_TAG` 映射（含 WAF/健康/Cookie 层），颜色走 token，`已熔断` 用 red+图标。成本：低。

- **优先级**：**高**（问题 1）。反爬登录态是整条抢单链路的前置条件，而本页在接口异常时呈现为"安静的空白页"，用户既不知道坏了、也不知道去哪修；紧随其后的是引导锚点缺失（问题 2/3，首次用户第一跳就断）。

---

### 内网穿透（`/maintenance/tunnel`）

- **现状描述**：顶部状态卡（Tag + 公网地址 + 启动/停止/新窗口打开）+ 下载失败指引 + Tailscale 授权向导 + Cloudflare 固定域名三步向导（`NamedTunnelWizard :125-380`）+ Provider 配置卡 + 使用说明（`frontend/src/pages/Maintenance/Tunnel.tsx:382-862`）。配置为"本地编辑态 → 保存"（`:391-396`、`handleSaveConfig :505-532`），后端把整个 `tunnel` 段覆盖写入 `config.yaml` 并热重载（`backend/xianyu_hunter/web/routes/api_tunnel.py:233-283`）。label 在 `menu_registry.yaml:169-175`、`sheetRegistry.tsx:74`、`ROUTE_LABELS MainLayout.tsx:75` 三处一致，但 `COMMAND_ITEMS`（`MainLayout.tsx:88-115`）漏了它。

- **问题清单**
  1. `[高]` 「保存配置」在配置未加载成功时会清空已配置的固定域名凭证：`loadConfig` 的 catch 只有 `console.error`（`:427-431`，注释还写明"401 表示未登录"），`config` 保持 `null`；随后 `handleSaveConfig` 用 `config?.X || ''` 提交 `tunnel_name/tunnel_id/credentials_file/hostname/cert_file`（`:517-521`），后端整段覆盖 `config.yaml` 的 `tunnel` 键（`api_tunnel.py:244-256,259`）—— 一次超时/401 之后点保存，命名隧道 ID、凭证路径、hostname、cert_file 全部被写成空串，需要重新走 `cloudflared login` 授权。同函数里 `cpolar_authtoken` 有"空即不改"的后端保护（`api_tunnel.py:241-242`），这五个字段没有 —— 证明是遗漏而非设计。
  2. `[高]` 保存配置会立即掐断正在运行的隧道，而提示说"下次启动才生效"：后端保存成功后异步 `old_service.stop()`（`api_tunnel.py:267-281`）；前端固定文案「配置已保存，下次启动隧道时生效」（`:523`），且运行中时「保存配置」按钮既不禁用也无确认（`:825-832`）—— 用户正用手机经隧道访问后台，点保存即断连，UI 却声称没有影响；`handleStart` 在 provider 与已保存不一致时还会**静默先保存**（`:459-462`），等于启动动作顺带断了旧隧道再建新隧道。
  3. `[中]` 「停止」隧道零确认（`:596-605` → `handleStop :489-500`）—— 公网地址立即失效、外部回链（如通知里的 `/confirm-buy` 深链，见 `sheetRegistry.tsx:79-81`）全部断裂；这是"关闭服务暴露面"的操作，破坏性高于同组多数删除，确认强度却是最低的一档（同组要输入 `CONFIRM_DELETE`）。
  4. `[中]` Cloudflare 授权轮询无超时、无取消、按钮被锁死：`startLoginPoll` 每 2.5s 轮询且无次数上限（`:165-173`），期间登录按钮 `disabled={loginLoading || loginPolling}`（`:285-294`，文案变"等待授权中..." `:222-227`）—— 用户没在浏览器完成授权就永远卡在此态，只能刷新整页；更糟的是切换页签会卸载向导组件（`:155-157 stopLoginPoll` + `SheetContent.tsx:50-52` key 重挂载），后端 provider 仍是 `waiting`（`api_tunnel.py:315-335`），回到页面后按钮退回"执行登录"，用户以为要重新授权（成本：重复触发 login 进程）。
  5. `[中]` 状态未知被显示为"已停止"：`loadStatus` catch 只 `console.error`（`:406-413`），`status` 为 `null` 时 `isRunning=false` → 顶部 Tag 显示「○ 已停止」+「隧道未启动，暂无公网地址」（`:559-561,580`），运行中的轮询只在 `status==='running'` 时启动（`:443-453`）—— 接口抖动一次就把正在运行的隧道显示为已停止（需实测确认轮询停止后是否再自愈），用户会去"再点一次启动"，触发 #2 的整段配置覆盖。
  6. `[中]` 页面无 `page-container` 根元素（`:552 &lt;Space direction="vertical"&gt;`；loading 分支更是一个裸全屏 Spin `:538-544`）—— 本页引导锚点 `.page-container`（`guides/menuGuides.ts:159-161`）定位不到，首次引导整段失效。
  7. `[中]` 未保存脏态完全隐形：Provider/端口/二进制路径/开机自启都是本地 state（`:391-396`），顶部 Tag 刻意跟随表单选择（注释 `:546-548`、实现 `:548-564`）—— 用户改了 Provider 没保存，页顶已经显示新 Provider，看起来"已生效"；对照同组 MenuAdmin 至少有「未保存」Tag + 保存按钮 disabled（`MenuAdmin/index.tsx:173,287`），同组两套口径。
  8. `[低]` 公网暴露风险无任何提示：地址以 `Text type="success" strong` + 一键复制常显（`:569-578`）、「在新窗口打开」用 `window.open`（`:606-612`），使用说明只讲流程"复制公网地址，在手机浏览器打开即可远程访问"（`:846`）—— 全文没有一句说明"这会把运营后台暴露到公网"，而后端 `status/start/stop` 本身免鉴权（`api_tunnel.py:5-6,144-204`）。
  9. `[低]` 向导把服务器文件路径当主信息展示（`:261` `cert_file`、`:333` `credentials_file` 均为 `Text code copyable`）；步骤 2/3 仅用 `opacity 0.5` 表示不可用（`:299,340`）而无"请先完成第①步"文案；`createName`/`dnsHostname` 在挂载时一次性取 config（`:136,138`），`onConfigChanged` 后输入框不回同步，用户看不到刚持久化的值。
  10. `[低]` 本页保存配置绕开了全站配置页范式（`configStore` 载入 → 编辑 → dry-run Diff → 保存；`DiffPreviewModal` 已被 5 个配置页使用，如 `pages/Config/EvalRules.tsx:762`），而它覆盖写的是整个 `tunnel` 段，"改了哪几个键"最该被核对。
  11. `[低]` 「内网穿透」不在 Command Palette 项里（`MainLayout.tsx:88-115`），老用户 Ctrl+K 搜"内网穿透/tunnel"均无结果，尽管它是 `menu_registry.yaml` 正式菜单。

- **优化建议**
  1. `loadConfig` 失败进入 error 态：禁用「保存配置」「启动隧道」并给"配置未加载，重试"；同时后端在 `cert_file/tunnel_id/hostname/credentials_file/tunnel_name` 上复制"空值=不修改"语义（`api_tunnel.py:244-256`）。成本：低（前端）+低（后端各字段 `or existing`）。
  2. 运行中保存前 `Modal.confirm` 说明"保存会立即断开当前隧道（含手机访问）"，成功文案改为"配置已保存，隧道已重建"；`handleStart` 的隐式保存改为显式提示。成本：低。
  3. 停止加 `Popconfirm`（"停止后公网地址立即失效，依赖它的推送回链将无法访问"）。成本：低。
  4. 授权轮询加 60 次/3 分钟超时 + 「取消等待」按钮；把轮询状态提升到 store（或由 `GuideController` 同级机制持有），切页签不中断。成本：中。
  5. `status===null` 时 Tag 显示"状态未知"并给重试；把 error 与 stopped 在视觉上分开。成本：低。
  6. 根容器改 `&lt;div className="page-container"&gt;`（含 loading 分支）。成本：极低。
  7. 脏态提示：`form*` 任一与 `config` 不等时，在「保存配置」旁显示 `Tag color="orange"&gt;未保存`，顶部 Tag 改跟随 `config.provider`。成本：低。
  8. 启动成功后追加一条 warning Alert："此地址可被任意持有者访问，请确认已开启登录保护；停止隧道即回收"。成本：低。
  9. 路径类字段折叠到 tooltip/「详情」抽屉；禁用步骤加 `Tooltip` 说明前置条件；`useEffect` 同步 `config` 到向导输入框。成本：低。
  10. 保存前复用 `DiffPreviewModal`（旧 `tunnel` 段 vs 新段）。成本：中。
  11. `COMMAND_ITEMS` 补 `/maintenance/tunnel`（并把该数组改为由 `/api/menu` 派生，见共性问题 1）。成本：低。

- **优先级**：**高**（问题 1、2）。一条是"静默丢失已完成的 Cloudflare 授权与隧道凭证"的不可逆配置破坏，一条是"提示与实际行为相反 + 无确认"，都发生在维护组里唯一会把本地服务暴露到公网的页面上。

---

### 向量数据库维护（`/maintenance/vector`）

- **现状描述**：页头 + 风险 Alert + 4 张状态卡 + Tabs（备份与恢复 / 数据清理）+ 创建快照弹窗 + 审计抽屉（`frontend/src/pages/Maintenance/Tunnel.tsx` 之外，本页 `frontend/src/pages/Maintenance/VectorAdmin.tsx:212-426`，根容器 `:213` 有 `page-container`）。危险操作统一走 `openDangerConfirm` 输入 `CONFIRM_DELETE`（`:90-122`），后端 `api_vector_admin.py` 校验 token（`:47-53`）、审计写 `chatbot_audit_logs`（`:56-61`）、chatbot 未启用时 403 `CHATBOT_DISABLED`（`:32-44`）。**在 `config/menu_registry.yaml` 里没有条目**，但 `sheetRegistry.tsx:73` 有路由注册。

- **问题清单**
  1. `[中]` 菜单不可达（注册表漂移）：`sheetRegistry.tsx:73` 已注册且 `ROUTE_LABELS MainLayout.tsx:74` 有 label，但 `menu_registry.yaml` 的 maintenance 组只有 5 项（`config/menu_registry.yaml:140-175`）→ 侧栏永远不显示，`COMMAND_ITEMS`（`MainLayout.tsx:88-115`）也没有 → Ctrl+K 搜不到；唯一入口是手输 `basename` 前缀 URL（`/xianyu/maintenance/vector）。而 `guides/menuGuides.ts:153-155` 已为它配好 Tour（因入口缺失，几乎不可能触发）—— 首次用户完全不知道有这页，高频用户每次手敲 URL。
  2. `[中]` 「按来源删除」是纯自由文本且无命中预览（`:362-372`）：后端没有任何列出 `source_file` 取值或预估条数的接口（`api_vector_admin.py` 内 `source_file` 仅出现在请求体与删除实现 `:126,283-287`）—— 拼错时 `deleted=0` 仍弹绿色成功「已删除 0 条片段」（`Cleanup` 同页 `VectorAdmin.tsx:191`），用户以为文档已清理而知识库仍在检索它；同组 DatabaseAdmin 删除前会做级联预览（`DatabaseAdmin.tsx:132-149`），同组两套口径。
  3. `[中]` 快照信息不足以支撑"恢复"这一覆盖式决策：表格只有 ID/类型/大小/时间（`:300-311`），没有片段数/来源清单/是否含最新导入；恢复确认只写"将用快照 X 覆盖当前集合，当前数据将丢失"（`:128-131`），且恢复前不会自动为当前集合建一份快照 —— 一次误恢复就把新导入全部抹掉，且只能回到所选旧快照。
  4. `[中]` 操作后状态数字 60s 不更新：`/api/vector-admin/status` 带 `@cached_ttl(60)`（`api_vector_admin.py:138`），而 `loadAll` 在恢复/删除/清空/按来源删除后立即重拉（`:136,152,171,194`）——「已清空 N 条片段」之后「片段数」卡仍显示 N（`:241`），用户判为失败而重复执行不可逆操作。
  5. `[中]` 审计抽屉打开时机与同页族相反：`loadAuditLogs` 先 `await` 再 `setAuditDrawerOpen(true)`（`:202-210`）—— 点击「审计日志」（`:222`）后数秒毫无反应；而 DatabaseAdmin 是不 `await` 立即开（`DatabaseAdmin.tsx:573`）导致失败也开空抽屉 —— 两个同构功能两种坏法，都缺 loading/error。
  6. `[低]` chatbot 未启用是本页常态，但界面无持续解释：`loadAll` 对 `CHATBOT_DISABLED` 只 `message.error` 一次（`:59-65`），随后统计卡显示 `'-'`（`:241,250,258,267`）、快照表空，没有"智能客服未启用 → 本页不可用"的常驻 `Result/Alert`，也没有跳「客服配置」的动作。
  7. `[低]` 服务器路径与脆弱的时间切片：「集合名」卡下方常驻展示 `status.persist_path`（`:269-271`）暴露部署目录；「快照数」用 `last_snapshot_at.slice(5, 16)` 定长切片拼"（最近 …）"（`:259`），跨年份/含时区偏移时显示成残片，语义不可靠。
  8. `[低]` 审计日志"操作"列一律蓝 Tag（`:417`）不区分 `snapshot_restore`/`cleanup_all` 等高危动作；后端返回的 `old_value_hash/new_value_hash`（`api/vectorAdmin.ts:29-30`）前端完全不显示（`:405-422`）—— 无法核对"这次到底动了什么"。
  9. `[低]` 「备份与恢复」和「数据清理」两个 Tab 风险级别天差地别却同层平铺，第二个 Tab 直接展示两个 danger 按钮（`:350-374`）且没有同组 Cleanup 的 dry-run 预览开关（`Cleanup.tsx:291-298`）—— 三个"清理"页三种安全模型。
  10. `[低]` 页头 title「向量数据库维护」（`:216`）与任务/文档口径"向量库维护"不一致；图标与 `/maintenance/db` 同为 `DatabaseOutlined`（`sheetRegistry.tsx:72-73`）—— 多页签同时打开时页签图标不可区分。

- **优化建议**
  1. 在 `menu_registry.yaml` maintenance 组补 `key: vector_admin`（`sort_order: 205`），或明确标注该页为内部页并在 MenuAdmin/命令面板中登记。成本：低。
  2. 新增 `GET /api/vector-admin/sources`（去重 `source_file` + 片段数），把 `Input`（`:363-369`）换成带计数与搜索的 `Select`；删除前展示"将删除 N 条"，`deleted===0` 时改 `message.warning('未匹配到片段')`。成本：中。
  3. 快照行加"片段数 + 来源数"列（`_list_snapshots :89-133` 顺带统计），恢复弹窗加复选框"恢复前先为当前集合创建快照"（默认勾上，复用 `createSnapshot :47-50`）。成本：中。
  4. 写操作后由后端失效 `vector_status` 缓存 key，或前端刷新带 `?force=1`。成本：低。
  5. 抽屉改为"立即打开 + 内部 `loading` + 失败显示错误态与重试"，与 DatabaseAdmin 统一为同一个 `AuditLogDrawer` 组件。成本：低-中。
  6. `CHATBOT_DISABLED` 时整页替换为 `Result` + 「前往客服配置」按钮（`/config/chatbot`）。成本：低。
  7. 路径移入 tooltip；时间统一用 `dayjs` 格式化，不再 `slice`。成本：低。
  8. 审计操作按动作类型上色（集中映射，`restore/cleanup/delete`→red/orange），并把 hash 差异展示为"变更前后"两列。成本：低。
  9. 给「数据清理」Tab 也提供 dry-run 预估（依赖建议 2 的 count 接口），并在 Tab label 上加警示图标。成本：中。
  10. 统一 title 口径；向量页图标换 `ClusterOutlined`（已在 `useMenuConfig.tsx:31` 图标映射表中）。成本：极低。

- **优先级**：**中**（若按"数据可恢复性"看，建议 3 的缺失接近 高）。最刺眼的是入口缺失（问题 1）与"删 0 条也算成功"的误导回执（问题 2）：前者让用户根本找不到这页，后者让用户以为脏文档已清除。

---

### 菜单管理（`/menu-admin`）

- **现状描述**：自建 `Layout` + 页头（返回 / 标题 / 刷新 / 重置为默认 / 保存(N)）+ 单卡表格，行内用 `Switch` 改可见性、`InputNumber` 改排序，脏项显示「未保存」Tag（`frontend/src/pages/MenuAdmin/index.tsx:239-319`、列定义 `:164-231`）。数据全部来自 `GET/PUT /api/menu`（`frontend/src/api/menu.ts:59-71`，后端 `api_menu.py`、`menu_manager.py`）。registry 有路由（`sheetRegistry.tsx:82`），`menu_registry.yaml` 无条目。

- **问题清单**
  1. `[高]` 「保存」必定失败（契约不一致）：前端 PUT 体 `{ items: [{ menu_key, visible, sort_order }] }`（`api/menu.ts:65-66`，载荷由 `MenuAdmin/index.tsx:117-123` 构造，字段名 `menu_key`）；后端要求 `{ menus: [{ key, ... }] }` 且 `menus`/`key` 均为必填（`api_menu.py:28-39`）—— Pydantic 恒返回 422，用户点保存只得一句"保存失败，请重试"（`:140`），整页唯一写路径不可用 —— 首次用户完全无法完成"隐藏某个菜单"这一主任务；而「重置为默认」是无 body 的 POST（`api/menu.ts:70`，`api_menu.py:82-92`）反而能成功，于是形成"改不动、但能一键清掉"的更糟组合。
  2. `[高]` 隐藏即永久消失：本页数据源就是给侧栏用的 `GET /api/menu`，而 `MenuManager.get_menus` 末尾 `merged = [m for m in merged if m["visible"]]`（`menu_manager.py:203`，docstring 也写"仅返回 visible=True 的项" `api_menu.py:46`）—— 任何被隐藏的菜单项会从管理表格里彻底消失，用户无法把它再打开，唯一出路是「重置为默认」并连带丢弃其它自定义排序（受问题 1 影响，隐藏通常发生在其它写入路径；需实测确认）。这是不可逆的配置陷阱。
  3. `[中]` 入口与面包屑缺失：全仓对该页的唯一主动入口是账号切换器下拉项（`components/layout/AccountSwitcher.tsx:387` → `navigate('/menu-admin')` `:334`），`menu_registry.yaml` 无该项、`COMMAND_ITEMS`（`MainLayout.tsx:88-115`）无该项、`ROUTE_LABELS`（`:55-85`）也无该项 —— 面包屑只剩「首页」（计算逻辑 `:341-352`），页签标题却叫"菜单管理"，同组 /maintenance/vector 至少有 ROUTE_LABELS（`:74`），两种残缺。
  4. `[中]` 页面无 `page-container`（根元素 `&lt;Layout style={{height:'100%'}}&gt;` `:240`，内容区 `Content padding:16` `:294`）—— 本页 Tour 锚点（`guides/menuGuides.ts:189-191`）失效；同时页内自建 `Header`（`:241-293`）与 App 顶栏/页签栏叠成三层头部，垂直空间被吃掉约 120px。
  5. `[中]` 引导与说明承诺不存在的能力：guide 文案「拖拽排序、隐藏/显示侧边栏菜单项，配置按用户隔离保存，可一键重置」（`menuGuides.ts:191`）但实现只有数字输入排序、无拖拽（`:214-227`）；卡内说明「保存后立即生效，影响所有页面的侧边栏展示」（`:298`）—— Command Palette 用的是硬编码 `COMMAND_ITEMS` 且不受 `visible` 过滤（`MainLayout.tsx:471-475`），隐藏项仍能 Ctrl+K 打开 —— 首次用户按引导找"拖拽"、按说明预期"隐藏后彻底不可访问"，两处都落空。
  6. `[中]` 「重置为默认」作用范围文案错误且确认强度最低：Popconfirm 写"将清除所有自定义菜单配置"（`:273-275`），后端只删当前用户记录（`api_menu.py:82-92`、`menu_manager.py:261-275 DELETE ... WHERE user_id = :uid`）—— 多账号共享部署下用户会误判影响所有人（或因反之低估：共享 `default` 用户时确实互相覆盖，`api_menu.py:49` 的 user_id 兜底）；它是本页唯一能成功的写操作，却只有 Popconfirm，而同组不可逆删除要求输入 `CONFIRM_DELETE`。
  7. `[中]` 改了排序数字但表格顺序不动：`sortedRows` 按原始 `sort_order` 排序（`:234-237`）而非 `editSortOrder` —— 用户调数字只看到「未保存」Tag 出现（`:173`），行位置毫无变化，判为"改错了/没生效"；叠加问题 1，保存不上 → 永远看不到排序效果。
  8. `[低]` 加载失败 = 空表格：`loadMenus` catch 只 `message.error`（`:77-79`），`rows` 保持 `[]` → `Table` 显示默认空态（`:307-314`），用户以为"系统没有任何菜单项"；错误态与空态同形，且无内嵌重试。
  9. `[低]` 无离开挽留：`hasDirty`（`:112`）只用于保存按钮 disabled（`:287`），页签关闭/切换无任何确认 —— 多页签模型下切页签即重挂载（`SheetContent.tsx:50-52`），全部未保存修改静默丢弃。
  10. `[低]` 类别配色本地定义 `CATEGORY_TAG_COLOR`（`:46-52`）与 `MENU_GROUP_LABELS`（`api/menu.ts:18-26`）分处两文件，另一消费方 `useMenuConfig.tsx:163` 只用 label 不用颜色 —— 全站"类别"没有单一视觉定义源；`MenuItemUpdate` 前端类型还带着 `group`/`custom_label` 字段（`api/menu.ts:53-54`）而后端契约里没有（`api_menu.py:28-32`），DB 里却有 `group_name/custom_label`（`menu_manager.py:237`）—— 类型层已经与两端同时漂移。

- **优化建议**
  1. 修正契约（二选一：前端改 `client.put('/api/menu', { menus: items.map(i =&gt; ({key: i.menu_key, ...})) })`，或后端接受 `items`/`menu_key` 别名），并补一条集成测试锁死；同时给 `Table` 加错误态。成本：极低-低。**这是本页第一优先修复项。**
  2. 后端新增 `GET /api/menu?include_hidden=true`（或 `GET /api/menu/admin` 返回全量含 `visible=false`），MenuAdmin 改用它；`useMenuConfig` 继续用现有过滤视图。成本：低。
  3. 把 `menu-admin` 补进 `menu_registry.yaml`（`category: other`）与 `ROUTE_LABELS`，并让命令面板由 `/api/menu` 派生（见共性问题 1）。成本：低。
  4. 根元素加 `className="page-container"`，去掉页内 `Header`，把 返回/刷新/重置/保存 收进 `Card` 的 `extra` 或 `page-container` 顶部工具条。成本：低。
  5. 文案与实现对齐：要么把 guide 改成「开关控制可见性、输入排序值调整顺序」，要么真的实现 `dnd` 排序；"影响所有页面"补一句"命令面板(Ctrl+K)不受影响"。成本：低。
  6. Popconfirm 文案改「仅重置**当前账号**的菜单可见性与排序，其它账号不受影响」，并在正文显示"当前有 N 项自定义 / M 项被隐藏"；重置前建议先展示将被清掉的非默认项列表。成本：低。
  7. `sortedRows` 改用 `editSortOrder` 实时排序，并在列头提示"排序为预览顺序，保存后生效"。成本：低。
  8. 加载失败显示 `Result status="error" + 重试`，空数据与错误分别文案。成本：低。
  9. 页签关闭/路由离开时对 `hasDirty` 做 `Modal.confirm`（或由 sheetStore 记录 dirty）。成本：中。
  10. 类别颜色/标签集中到 `api/menu.ts` 一并导出，前后端契约字段（`group`/`custom_label`）要么实装要么删除。成本：低。

- **优先级**：**高**（问题 1、2）。这是一整页唯一功能坏掉的情况：保存恒失败 + 一旦隐藏就无法恢复，用户会永久失去侧栏菜单项的控制权。