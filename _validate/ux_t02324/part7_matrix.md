## 7. 汇总优先级矩阵

### 7.1 高优先级全部 64 条（按治理批次归组，可直接排期）

**批次 A｜失败被静默吞掉 / 回执与实际结果不符（18 条，成本多为低）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| A1 | 仪表盘 | 首屏 5 接口全 `.catch(()=>null)`，后端挂了渲染成"全 0 空态"且无重试 | `pages/Dashboard/index.tsx:80,83,99,100` | 低 |
| A2 | 仪表盘 | 「调度器未运行」Alert 只说"请启动"却无任何动作按钮（同页欢迎卡就有） | `index.tsx:250-258` vs `:229-247` | 低 |
| A3 | 任务管理 | 关联商品删除静默失效：`linkColumns` useMemo 依赖为空数组，闭包捕获空 `linkTaskId` | `pages/Tasks/TaskList.tsx:653,730,574-575` | 低 |
| A4 | 商品中心 | 卡片视图删除图标恒可点，落到 `if(!selectedTask||!linkId) return` 静默无事 | `pages/Items/ItemList.tsx:1146,642-643` vs 表格 `:804` | 低 |
| A5 | 卖家评估 | 批量 AI 评估逐项 `catch {}`，全失败也报「批量评估完成，共处理 N 项」 | `pages/Evaluations/hooks/useEvalBatch.ts:101,109` | 低 |
| A6 | 价格行情 | 4 个数据 hook 全部静默吞错，失败渲染成「暂无数据」 | `pages/PriceDashboard/hooks/useCategoryComparison.ts:30`、`useCategoryStats.ts:19`、`useSoldRange.ts:44`、`useBargainEval.ts:32` | 低 |
| A7 | 价格策略 | 直方图接口失败时塞入硬编码假数据 `counts:[5,12,28,…]`，预览三指标由它算出 | `pages/Config/PriceStrategy.tsx:74-81,124-146,407-422` | 低 |
| A8 | 价格策略 | 「刷新预览数据」是 `setTimeout(500ms)` 假动作，不发请求却报「预览已刷新」 | `PriceStrategy.tsx:427-442` | 低 |
| A9 | 搜索参数 | `catch` 丢后端原因，只报「预览失败，请重试」（同组 4 页用 `extractApiError`） | `pages/Config/SearchConfig.tsx:159-160` | 低 |
| A10 | 客服配置 | `onChange={(v)=>v&&updateConfig(…)}`：值为 0 或清空时静默不发送 | `pages/Chatbot/Config.tsx:214,223,267,285,320,330,339,372,448,542,551` | 低 |
| A11 | 数据库维护 | 主键可编辑但后端 `continue` 丢弃，仍弹「已更新」 | `pages/Maintenance/DatabaseAdmin.tsx:165-211,463` + `routes/api_db_admin.py:649-651` | 低 |
| A12 | 数据库维护 | 空值提交前被丢弃 → 任何字段都清不掉，仍报「已更新」 | `DatabaseAdmin.tsx:454-457` + `api_db_admin.py:658-659` | 中 |
| A13 | 反爬登录管理 | 5 个 `fetch*` 全部只 `console.error`，接口挂 = 六张卡空白 | `pages/AntiCrawl/index.tsx:227-276` + 条件渲染 `:567,648,712,776,934` | 中 |
| A14 | 内网穿透 | 保存会异步 `stop()` 掐断运行中隧道，文案却称「下次启动隧道时生效」 | `pages/Maintenance/Tunnel.tsx:523,825-832` + `routes/api_tunnel.py:267-281` | 低 |
| A15 | 智能客服 | 流一开始就把全部 pending 消息标「已送达 ✓」，收到 `error` 也不回滚 | `pages/Chatbot/index.tsx:109-112,202-205` | 低 |
| A16 | 数据导出 | blob 下载后**无条件** `message.success('正在导出…')`，失败路径无提示 | `pages/Export/index.tsx:78-95` | 中 |
| A17 | 全局壳层 | 菜单接口失败＝空白侧栏无任何提示（只解构 `menus/loading`，丢弃 `error`） | `components/layout/MainLayout.tsx:172` + `hooks/useMenuConfig.tsx:223-227,245` | 低 |
| A18 | 全局壳层 | 告警轮询 `.catch(()=>{})` 使 Badge 停在 0；抽屉失败后永久 `<Spin/>` | `MainLayout.tsx:180-182,756-758` | 低 |

**批次 B｜破坏性/不可逆操作防护不足（8 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| B1 | 任务管理 | 危险操作确认三套标准：行内 armConfirm 5 秒后**无提示自动撤销**、模板删除单击即删、详情页停止零确认 | `TaskList.tsx:84-97,1432-1439,335-338`、`TaskDetail.tsx:453` | 中 |
| B2 | 抢单记录 | `takeover_pending` 打开 Modal 即重置 `phase='confirm'`，可对已接管订单重复 `POST /takeover` | `pages/Orders/Orders.tsx:551,125-132,184` | 低 |
| B3 | 系统清理 | 「浏览器数据」实际 `rmtree` 掉存 cookies/反检测指纹的 `webview_data_*`，UI 不点名会登出全部账号 | `Cleanup.tsx:285,88` + `routes/api_maintenance.py:140-152` | 低 |
| B4 | 批量采集 | 「清空全部」= `days==0` 跨账号 `DELETE FROM BatchRefreshHistoryRow`，只有 Popconfirm | `BatchRefresh.tsx:1067-1075,808-817` + `api_batch_refresh.py:386-392` | 低-中 |
| B5 | 内网穿透 | `loadConfig` 失败后点保存，命名隧道 5 个字段以空串覆盖写入 yaml（仅 authtoken 有"空即不改"保护，反证是遗漏） | `Tunnel.tsx:517-521` + `api_tunnel.py:244-256` | 低 |
| B6 | 菜单管理 | 隐藏项被 `GET /api/menu` 直接过滤，管理页里也看不到 → 无法单独恢复，只能"重置全部" | `services/menu_manager.py:203` | 低 |
| B7 | 登录 | 「自动关闭 Edge/Chrome 并导入」零确认即结束浏览器进程，未提示会丢失其它标签页未提交内容 | `pages/Login/index.tsx:601-623,1042-1065` | 低 |
| B8 | 确认抢单 | 真金下单单击即提交，无 `Modal.confirm`、无勾选、无提交锁，成功后不可撤销 | `pages/ConfirmBuy/index.tsx:194-203,186-191` | 低 |

**批次 C｜凭证与敏感数据（3 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| C1 | 配置版本 | 「分享配置」脱敏是死代码：`SENSITIVE_KEYS` 在响应顶层替换，而密钥在 `config.*` 下，弹窗却断言"已替换为 ***" | `pages/Config/VersionManager.tsx:120-133,422` + `routes/api_config.py:458-467` | 低 |
| C2 | 配置版本 | 后端两份敏感清单均漏 `ntfy_token`（真实 Access Token），导出/分享文件原文泄露 | `api_config.py:697-702,300-313` vs `api/types.ts:134-136` | 低 |
| C3 | 登录 | 会话 Cookie 用明文 `Input` 承载并自动回填，无掩码、离开不清空，值直接进 DOM | `pages/Login/index.tsx:459-468,844` | 低 |

**批次 D｜脏检查与保存链路（6 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| D1 | 价格策略 | 策略卡改本地 state，`hasChanges()` 恒 false → 「重置」永久禁用，切页签丢改动无保护 | `PriceStrategy.tsx:235-379,193` | 低 |
| D2 | 搜索参数 | 保存时静默反推并覆盖未展示字段（`qps=round(60/interval)`、`max_delay_ms=interval*1500`） | `SearchConfig.tsx:129-131` | 低 |
| D3 | 搜索参数 | 同 D1：9 字段全本地 state，重置禁用、改动静默丢失 | `SearchConfig.tsx:65-77,184` | 低 |
| D4 | AI 服务 | 「测试连接」先保存整份配置且无提示；Embedding Tab 没有保存按钮，只能靠测试连接落库 | `pages/Config/AIConfig/index.tsx:153-156,198-203`、`components/EmbeddingConfigForm.tsx` | 低 |
| D5 | 配置版本 | 回滚/恢复后不通知其它已打开的配置页签（`configStore` 仅 mount 时 load）→ 旧值页签点保存把刚回滚的配置覆盖回去 | `VersionManager.tsx:45-59` + `stores/configStore.ts:40-50` | 低 |
| D6 | 全局壳层 | 「最小化保留页面状态」承诺落空：只渲染 activeSheet 且 `key={sheet.id}` 重挂载，切页签即丢筛选/分页/未保存表单 | `SheetPreferences.tsx:119-125` vs `SheetWorkspace/SheetContent.tsx:33-56`、`index.tsx:75` | 高 |

**批次 E｜深链与跳转契约（5 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| E1 | 商品中心 | 登录失效横幅「重新登录」跳 `/?redirect=/items` 落仪表盘（那里没有登录入口） | `ItemList.tsx:826-831` | 低 |
| E2 | 抢单记录 | 告警雷达与后端通知都发 `/orders?ref=<id>`，本页无 `useSearchParams`，`ref` 从不消费 | `Orders.tsx:1-18` + `Dashboard/components/AlertRadar.tsx:58,76` + `services/notification_engine.py:63` | 低 |
| E3 | 通知中心 | 「查看详情」是裸 `<a href={item.link} target=_blank>`，link 为 `/orders?ref=`、`/dashboard#login` → 在 `basename=/xianyu` 下跳出 404 | `pages/Notifications/index.tsx:283` + `notification_engine.py:63,116` | 低 |
| E4 | 确认抢单 | 移动端一律 `navigate('/m/')` 且无 `/m/confirm-buy` 路由 → 手机通知里的确认链接被丢回移动首页，参数全清 | `App.tsx:80` + `mobile/routes.tsx` | 中 |
| E5 | 全局壳层 | 两处全局浮动帮助按钮 `href="#/help"` 在 BrowserRouter 下不跳转，点了只改 hash | `guides/GuideController.tsx:167,187` | 低 |

**批次 F｜统计口径与作用范围（2 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| F1 | 任务管理 | 「全部启动」与确认标题称"所有"，实际只作用当前页未运行任务 | `TaskList.tsx:906-916,624,612` | 低 |
| F2 | 抢单记录 | 顶部 4 张状态卡按当前页自行统计，翻页/改 pageSize 数字突变 | `Orders.tsx:404-411` | 低 |

**批次 G｜实时流基本能力（3 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| G1 | 实时日志 | 无自动滚动（引导却声称"自动滚动"），新日志追加在视口外被判"卡住" | `pages/Logs/Logs.tsx:301` + `guides/menuGuides.ts:71` | 低 |
| G2 | 实时日志 | 断线即彻底停流、无重连入口（同产品 `Orders` 已有退避重连范式） | `Logs.tsx:88-91` vs `Orders/Orders.tsx:446-480` | 低 |
| G3 | 实时日志 | `LEVEL_COLOR` 键为大写、后端返回小写 → ERROR 行恒灰（同页直方图先 `toUpperCase()` 恰好正常，反证是缺陷） | `constants/logLevels.ts:3-8` vs `routes/api_logs.py:177-180,194` + `Logs.tsx:279,315` | 低 |

**批次 H｜业务校验缺失（2 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| H1 | 评估规则 | `pass_score/auto_buy_score` 与抢单策略页重复编辑同一字段，后者无交叉校验 → 可落盘 `pass>auto` 非法组合 | `EvalRules.tsx:223,297-301` vs `BuyerStrategy.tsx:85-92` | 中 |
| H2 | 抢单策略 | 「安全护栏」称 `auto_buy_score≥80 才启用 auto`，UI 允许 0-100、后端无下限 → 设 30 就 30 分自动拍下 | `BuyerStrategy.tsx:361,150` + `domain/evaluation.py:73`、`modules/worker.py:997` | 低 |

**批次 I｜文案/引导与实现漂移（5 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| I1 | 卖家评估 | 横幅让用户"在 Dashboard 页面重新登录闲鱼"——全站无此菜单名，实际入口是反爬登录管理 | `pages/Evaluations/index.tsx:604` | 低 |
| I2 | 抢单策略 | 首屏副标题"notify/confirm 模式不受影响"对本页第一卡即错（pass_score 会推送确认） | `BuyerStrategy.tsx:128` vs `:179-181` | 低 |
| I3 | 智能客服 | 撤回入口因 `canRecall && !msg.status` 永不显示，而帮助中心两处承诺"2 分钟内可撤回" | `Chatbot/index.tsx:1514` + `Chatbot/components/HelpCenterModal.tsx:18` + `pages/Help/index.tsx:654` | 低 |
| I4 | 关于 | 五个外链仍是 `https://example.com/…` 占位（协议/隐私/社区/反馈 + `mailto:dev@example.com`） | `pages/About/AboutMenuList.tsx:16,17,23,24,25` | 低 |
| I5 | 新手引导 | 一键复制的两条命令 CLI 中不存在：`python -m xianyu_hunter qr-login`、`… worker`（实际是 `login`/`run`/`web`） | `pages/Onboarding/index.tsx:103,108,220,225` vs `backend/xianyu_hunter/__main__.py` 命令集 | 低 |

**批次 J｜列表渲染正确性（1 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| J1 | 商品中心 | 实时结果 `link_id=0` 却用作 `rowKey`/卡片 `key`，一屏大量重复 key，行状态错乱 + 控制台告警 | `ItemList.tsx:641,1052,1088` | 低 |

**批次 K｜控件语义错配（2 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| K1 | 通知渠道 | 所有字段无条件 `Input.Password`，`constants.ts` 的 `secret?` 从未被消费（URL/ChatID/Topic 也被掩码） | `NotifierChannels/components/ChannelCard.tsx:85-90` vs `constants.ts:20` | 低 |
| K2 | 通知渠道 | 「发送测试」把可选字段当必填拦截（`ntfy_token` placeholder 明写"可选"）→ 公共 ntfy.sh 主题永远测不了 | `NotifierChannels/index.tsx:164-169` vs `constants.ts:134` | 低 |

**批次 L｜状态未知被误显示（3 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| L1 | 通知渠道 | `serverchan`/`pushplus` 默认 `enabled:true` 但空凭据无任何提示，用户以为已配好、实际静默丢通知 | `constants.ts:37,48` + `index.tsx:166` | 低 |
| L2 | 客服配置 | 模块未启用只弹一次 error，随后永久停在"加载中…"卡片，无重试入口 | `Chatbot/Config.tsx:62,186-188` | 低 |
| L3 | 全局壳层 | 页签栈满/未找到时零提示，URL 被 `replace` 顶回，点菜单"纹丝不动"；`maxSheets=1` 时彻底锁死 | `stores/sheetStore.ts:320-336` + `sheetNotifications.tsx:25-53` + `hooks/useSheetSync.ts:40-45` | 中 |

**批次 M｜交互范式不一致（2 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| M1 | 卖家评估 | 同一工具栏混用两种触发模型：5 类条件选中即查询，商品 ID/价格区间必须点「查询」 | `pages/Evaluations/index.tsx:500,529,543,583,614` vs `:588` | 中 |
| M2 | 客服配置 | 逐字段 500ms 防抖 PUT 且每次都弹 `message.success('配置已更新')`，连改 5 项=5 条 toast 叠盖 | `pages/Chatbot/Config.tsx:99-118` | 低 |

**批次 N｜关键信息不可达 / 状态被暗中改变（2 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| N1 | 抢单记录 | 失败订单看不到 `error`/`screenshot`（字段已存在却不在列定义），行内唯一动作是删除 | `Orders.tsx:508-569` vs `api/types.ts:581-582`；引导承诺见 `guides/menuGuides.ts:53` | 中 |
| N2 | 事件时间线 | 进入页面即从通知订阅静默改写 `eventTypeFilter`，异常只 `console.warn`，用户看到列表"少一半"无解释 | `pages/Timeline/index.tsx:37-65,45-48` | 低 |

**批次 P｜前后端契约/事件不匹配（2 条）**

| # | 菜单 | 问题 | 证据 | 成本 |
|---|---|---|---|---|
| P1 | 菜单管理 | 保存必然 422：前端 PUT `{items:[{menu_key,…}]}`，后端要求 `{menus:[{key,…}]}`（`key` 必填） | `api/menu.ts:66` + `pages/MenuAdmin/index.tsx:117-123` vs `routes/api_menu.py:27-39` | 极低 |
| P2 | 智能客服 | 后端下发 `faq_confirm`/`intent`，前端 `SSE_EVENT_HANDLERS` 无对应 handler 被丢弃；模糊命中路径只发 `faq_confirm` → 用户提问后**一句话都不回**且无错误 | `pages/Chatbot/index.tsx:170-177,695-696` vs `modules/chatbot/orchestrator.py:45,49,240-245` | 中 |

### 7.2 排期批次建议

| 顺序 | 批次 | 条数 | 主要成本 | 为什么排在这里 |
|---|---|---|---|---|
| 1 | A 静默失败 / 假回执 | 18 | 多为低 | 它不修，其它所有修复的验证结果都不可信；且 A17/A18（壳层）一次改动覆盖全站 |
| 2 | B 不可逆操作防护 | 8 | 低-中 | 误点代价最大（丢登录态、跨账号删数据、真金下单、杀掉浏览器） |
| 3 | C 凭证与敏感数据 | 3 | 低 | 3 处均为"泄露面"问题，改动小、收益确定 |
| 4 | P 前后端契约 | 2 | 极低/中 | P1 是一个按钮完全失效，修它只需改字段名 + 一条集成测试 |
| 5 | E 深链与跳转契约 | 5 | 低 | 告警→处理动作的闭环目前全断，修完 A 批次才看得出效果 |
| 6 | D 脏检查与保存链路 | 6 | 低（D6 为高） | D1-D5 可随 `useConfigSave` 一起抽公共层；D6 需架构决策，单列 |
| 7 | G/H/K/L/N | 12 | 低为主 | 各自独立、可用小 PR 快速清账 |
| 8 | F/M/J | 5 | 中 | 涉及接口或交互范式统一，需要一次跨页改动 |
| 9 | I 文案与引导漂移 | 5 | 低 | 建议同时建立「引导文案一致性断言」防止复发（见 §6 壳层建议 18） |

### 7.3 逐菜单优先级一览

| 组 | 菜单（path） | 高 | 中 | 低 | 合计 | 本菜单最痛的一点 |
|---|---|---|---|---|---|---|
| overview | 仪表盘（`/`） | 2 | 5 | 1 | 8 | 后端挂了也显示"全 0 正常态"（A1） |
| data_view | 任务管理（`/tasks`） | 3 | 5 | 0 | 8 | 关联商品删除点了没反应（A3） |
| data_view | 商品中心（`/items`） | 3 | 4 | 1 | 8 | 实时结果重复 key + 重新登录跳错页（J1/E1） |
| data_view | 卖家评估（`/evaluations`） | 3 | 4 | 1 | 8 | 全失败也报"批量评估完成"（A5） |
| data_view | 抢单记录（`/orders`） | 4 | 3 | 1 | 8 | 深链 `ref` 不消费 + 统计口径按当前页（E2/F2） |
| data_view | 事件时间线（`/timeline`） | 1 | 4 | 3 | 8 | 静默改写筛选（N2） |
| data_view | 实时日志（`/logs`） | 3 | 3 | 1 | 7 | 实时页无自动滚动/不重连（G1/G2） |
| data_view | 错误日志（`/logs/errors`） | 0 | 3 | 3 | 6 | **无高优先级缺陷**，本组完成度最高 |
| data_view | 通知中心（`/notifications`） | 1 | 4 | 1 | 6 | 通知链接跳出 SPA 404（E3） |
| data_view | 价格行情（`/price-dashboard`） | 1 | 4 | 3 | 8 | 4 个 hook 全静默吞错（A6） |
| config | 价格策略（`/config/price`） | 3 | 2 | 2 | 7 | 失败塞假数据驱动预览（A7） |
| config | 评估规则（`/config/eval`） | 1 | 3 | 4 | 8 | 分数交叉校验只在一页（H1） |
| config | 抢单策略（`/config/buyer`） | 2 | 4 | 2 | 8 | 护栏 ≥80 是假承诺（H2） |
| config | 搜索参数（`/config/search`） | 3 | 3 | 2 | 8 | 保存时静默改写 QPS（D2） |
| config | 通知渠道（`/config/notifier`） | 3 | 4 | 1 | 8 | 默认启用 + 空凭据静默丢通知（L1） |
| config | AI 服务（`/config/ai`） | 1 | 5 | 1 | 7 | 测试连接先保存整份配置（D4） |
| config | 客服配置（`/config/chatbot`） | 3 | 4 | 1 | 8 | 清空/置 0 静默不发送（A10） |
| config | 配置版本（`/config/version`） | 3 | 3 | 2 | 8 | 分享脱敏死代码 + ntfy_token 泄露（C1/C2） |
| maintenance | 系统清理（`/maintenance`） | 1 | 7 | 3 | 11 | 「浏览器数据」= 删登录态（B3） |
| maintenance | 数据库维护（`/maintenance/db`） | 2 | 6 | 4 | 12 | 主键改了报成功但被丢弃（A11） |
| maintenance | 批量采集（`/batch-refresh`） | 1 | 6 | 5 | 12 | 清空全部 = 跨账号删除（B4） |
| maintenance | 反爬登录管理（`/anticrawl`） | 1 | 6 | 3 | 10 | 接口失败 = 整页空白（A13） |
| maintenance | 内网穿透（`/maintenance/tunnel`） | 2 | 5 | 4 | 11 | 保存静默清空隧道凭证（B5） |
| maintenance | 向量库维护（`/maintenance/vector`） | 0 | 5 | 5 | 10 | **无高优先级缺陷**；但菜单入口整体缺失（注册表无条目） |
| maintenance | 菜单管理（`/menu-admin`） | 2 | 5 | 3 | 10 | 保存恒 422 + 隐藏不可恢复（P1/B6） |
| other | 智能客服（`/chatbot`） | 3 | 5 | 4 | 12 | 提问后一句话都不回（P2） |
| other | 数据导出（`/export`） | 1 | 3 | 3 | 7 | 导出结果不可知（A16） |
| other | 关于（`/about`） | 1 | 4 | 5 | 10 | 五个外链是占位域名（I4） |
| 关联 | 帮助文档（`/help`） | 0 | 4 | 2 | 6 | **无高优先级缺陷**；搜索只匹配标题与引言 |
| 关联 | 登录（`/login`） | 2 | 3 | 3 | 8 | Cookie 明文 + 零确认杀浏览器（C3/B7） |
| 关联 | 新手引导（`/onboarding`） | 1 | 5 | 1 | 7 | 两条复制即用命令不存在（I5） |
| 关联 | 确认抢单（`/confirm-buy`） | 2 | 3 | 3 | 8 | 移动端链路全断 + 下单无确认（E4/B8） |
| 壳层 | 导航/页签/命令面板/告警/移动端 | 7 | 11 | 2 | 20 | 空白侧栏、承诺落空、栈满锁死（A17/A18/D6/L3） |

（合计列含 1 处跨节重复计数：菜单管理的 P1/B6 在壳层节各记一次，故"合计"求和为 291，去重后为 289。）

### 7.4 中（145 条）/ 低（80 条）优先级的主题分布

| 主题 | 中 | 低 | 说明 |
|---|---|---|---|
| 三处定义源漂移（label/图标/分组/面包屑/命令面板） | 4 | 1 | 已在 §6 给出完整对照表；`/help` 页签图标 `BlockOutlined` 与命令面板 `QuestionCircleOutlined` 不一致即为一例 |
| 引导/帮助文案与实现不符 | 12 | 3 | 除 §7.1 批次 I 的 5 条高危外，另有 `menuGuides.ts:71,101,113,119,125,137,171-173,185,191` 十处需一并校正 |
| 分页/上限截断（`limit:100/500` 无提示） | 11 | 2 | `ErrorLogs.tsx:85`、`Notifications/index.tsx:62`、`Timeline/index.tsx:74`、`Logs.tsx:48`、`TaskDetail.tsx:207`、`useCategoryComparison.ts:26`、`VectorAdmin`、`BatchRefreshHistory` 等，属同一类"数据不可达却不说" |
| 空态不教下一步 / 筛选后无结果与真无数据不区分 | 9 | 6 | 全仓 `Empty` 文案通病，建议抽 `EmptyWithActions` 组件 |
| 视觉与布局（列宽、双层滚动、emoji 破窗、硬编码色） | 8 | 21 | `PriceDashboard/index.tsx:32`、`Evaluations/index.tsx:43,469`、`TimelineList.tsx:52-58`、约 30 处硬编码 `#52c41a/#ff4d4f/#FF6200` |
| 持久化口径不一致（`usePersistentState` 半套） | 7 | 3 | `useEvalFilters.ts:52-91`、`BatchRefresh.tsx:713-724`、`AntiCrawl:462-464` |
| 危险操作确认强度差异（非高危等级） | 7 | 1 | 与批次 B 同源，可在 `dangerConfirm` 抽取时一并处理 |
| 错误提示不统一（固定短语 vs `extractApiError`） | 6 | 0 | `VersionManager.tsx:54,78,97,115,137,181` 等，与 A9 同一修法 |
| 术语门槛（实现名词外露） | 5 | 8 | `Config.tsx:263,272,281,383,565`、`AntiCrawl:715-745`、`Login:1310` |
| 键盘/可发现性（助记不可见、无方向键选行） | 4 | 2 | `MainLayout.tsx:118-128` 定义 9 条但 UI 无任何呈现 |
| 其它（图标语义、状态色、文案润色） | 15 | 13 | 逐条见各菜单节 |

### 7.5 未发现显著体验缺陷的对象

按要求明示（这些页面经 6 维度逐项核对，无可指认的**高**优先级缺陷）：

- **错误日志（`/logs/errors`）**：筛选持久化、列配置、批量删除确认、详情 5 Tab 均规范；仅存 6 条中低问题（搜索历史药丸不触发查询、批量清理无 catch、`limit:100` 无提示、全选非常驻、状态 Select 无 loading、长消息无 Tooltip）。
- **向量库维护（`/maintenance/vector`）**：确认强度（输入 `CONFIRM_DELETE`）与审计落库齐全，是全组安全设计基线之一；主要缺陷是菜单入口缺失与"删 0 条也算成功"的回执。
- **帮助文档（`/help`）**：内容组织完整，缺陷集中在检索范围、折叠后无法再展开、`Anchor` 容器错配三项（均中优先级）。
- 另需点名两处**实现规范、可作为范本**的局部：抢单记录与错误日志的列配置持久化（`Orders.tsx:384-391`、`useColumnConfig`）、通知中心的乐观更新回滚（`Notifications/index.tsx:84-92,116-128`）、通知渠道页的信息架构（分类 + 推荐 + 额度说明 + 免打扰时间轴）与评估规则的字段级回滚 + 交叉校验设计。
