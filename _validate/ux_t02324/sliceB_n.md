### 菜单：数据查看 > 抢单记录（`/orders`）
**现状描述**：4 张状态统计卡 + 单状态筛选 + 后端分页表格 + 列配置，接管走三步 Modal，并有 SSE 自动刷新。整体骨架完整，但「查不到失败原因」「统计口径错」两处直接削弱本页核心价值。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 2/5 | 仪表盘告警雷达与后端通知均发深链 `/orders?ref=<id>`（`pages/Dashboard/components/AlertRadar.tsx:58,76`、`backend/.../services/notification_engine.py:63`），但 `Orders.tsx:1-18` 无 `useSearchParams`，`ref` 从不消费 → 落到第 1 页未筛选列表，被告警的那条多半在后面的页 | 读取 `ref`：命中则调 `orderApi.get`（`api/order.ts:26`）直接弹详情/高亮行，或自动填入筛选并提示「已定位订单 xx」 | 低 | 高 |
| 2 | 5/3 | 顶部「待处理/已成功/已失败/人工接管」4 卡按**当前页**自行统计（`Orders.tsx:404-411`），翻页或改 pageSize 后数字突变，语义却像全局统计 | 用后端全局 counts（`statsApi`/list 返回聚合字段），卡标题加「本页」亦可作为低成本止血 | 低 | 高 |
| 3 | 2/5 | 状态为 `takeover_pending` 的行按钮写「查看」（`Orders.tsx:551`），但 Modal 打开即把 phase 重置为 `confirm`（`125-132`），再次显示「确认接管」并会对已接管订单重复 `POST /takeover`（`184`） | phase 初值按 `order.status` 推导（takeover_pending → progress + 用行内 `takeover_remaining_sec` 起倒计时） | 低 | 高 |
| 4 | 1/3 | 失败订单看不到失败原因/截图：`OrderItem.error`、`screenshot` 字段存在（`api/types.ts:581-582`）却不在列定义（`Orders.tsx:508-569`），而行内「删除」常驻，用户唯一动作是删掉；首次引导还承诺「含…失败原因与截图」（`guides/menuGuides.ts:53`） | 加 `expandable` 行展示 error + 截图缩略图（点击预览），或行点击复用 `orderApi.get` 打开详情抽屉 | 中 | 高 |
| 5 | 6/3 | 状态标签颜色失效：`Orders.tsx:518` 查 `ORDER_STATUS_CONFIG[s]?.color`，但该表无 `pending` 键（`constants/orderStatus.ts:6-18` 只有 `pending_pay`）→「待处理」标签恒为灰色，而同名统计卡是橙色（`577`）；同时 `STATUS_TEXT`（`33-41`）与常量表 label 双源维护 | 在 `orderStatus.ts` 补 `pending`，删除页内 `STATUS_TEXT` 改读 `label` | 低 | 中 |
| 6 | 2 | 筛选仅「状态」一项（`586-598`），后端其实支持 `task_id`/`item_id`/时间（`api/order.ts:6-11`）；`dry_run` 可显示（`40`）却不在筛选下拉且不计入统计 → 演练记录与真实成交混排，高频用户无法隔离 | 补任务/关键词/日期范围筛选，`dry_run` 进下拉并在统计区单列 | 中 | 中 |
| 7 | 5 | 「接管截止」列显示「x分x秒」（`529-537`）但列表只在 `buy.succeeded/failed` 事件刷新（`468`），秒数不 tick、接管类事件不触发刷新；SSE 静默重试 10 次后彻底放弃（`456`）无任何界面提示 | 列内本地秒级 tick 或订阅 takeover 事件；重连失败时在表格上方挂 Alert「实时已断开·点击重连」 | 低 | 中 |
| 8 | 4/5 | 接管完成页「利润计算器」把买入价默认成卖出价（`53,57`），首屏「净赚」即为红色负值（手续费）（`92-95`），像亏了钱 | 买入价留空 + placeholder「输入实际买入价」，未输入前不显示净赚 | 低 | 低 |

**三源一致性**：menu_registry.yaml:39-45（抢单记录/ThunderboltOutlined//orders/data_view）＝ MainLayout ROUTE_LABELS:60 ＝ COMMAND_ITEMS:92 ＝ sheetRegistry:58 ＝ App.tsx:100，**四处 label/图标/path/分组一致**。仅图标语义问题：`ThunderboltOutlined` 同时用于「抢单策略」/config/buyer（registry:97-103）与「确认抢单」（sheetRegistry:81），命令面板里三者难以区分。

---

### 菜单：数据查看 > 事件时间线（`/timeline`）
**现状描述**：4 统计卡 + 数据源/任务下拉 + 事件类型标签行 + 客户端 30 条分页列表，可展开 payload。信息密度不错，但过滤语义对普通用户不可见。

| # | 维度 | 问题（具体证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 2/5 | 进入页面即从通知订阅**静默**改写 `eventTypeFilter`（`pages/Timeline/index.tsx:37-65`），异常只 `console.warn`（`45-48`）；用户看到列表"少了一半"且顶部标签高亮，无任何解释 | 同步后 `message.info('已按通知订阅过滤 N 类事件')` + 面板顶部可关闭的说明条 | 低 | 高 |
| 2 | 2 | 事件类型标签交互反直觉：当前为「显示全部」时点任一标签＝**只选这一个**（`components/TimelineFilter.tsx:83-85`），而文案写「显示全部事件类型」（`62-66`），用户预期是"排除这类" | 明确双模式（白名单/黑名单），或点标签=切换该项并把文案改成「点击可只看/排除」 | 低 | 中 |
| 3 | 2 | 数据固定 `limit: 500`（`index.tsx:74`），时间过滤/翻页均无；第 501 条之前的历史永不可达且无「仅最近 500 条」提示 | 加日期范围筛选 + 后端 offset 翻页，或至少标注「仅显示最近 500 条」 | 中 | 中 |
| 4 | 5 | 过滤逻辑写两遍（`index.tsx:79-82` 与 `92-94`），二者口径一旦分叉就出现「统计卡数字 ≠ 列表条数」；统计卡基于全量 500（`111-114`）而列表只 30 条（`82`）且无时间窗标题 | 抽单一 `applyFilter()`；统计卡标题加「近 N 条内」限定语 | 低 | 中 |
| 5 | 6/2 | 实时性与同组不一致：抢单记录有 SSE 自动刷新（`pages/Orders/Orders.tsx:446-500`），本页只有手动「刷新」（`TimelineFilter.tsx:47`）——事件流页面却要看新事件得反复点 | 复用同一 SSE 范式（订阅 `app_event` → 防抖 load） | 中 | 中 |
| 6 | 2 | 展开态用全局行号 `globalIdx` 记忆（`index.tsx:102-108`），行 key 是 `${item.id}-${idx}`（`TimelineList.tsx:41`）→ 翻页后第 2 页第 1 条继承第 1 页第 1 条的展开状态 | 改为按 `item.id` 存 `Set<string>` | 低 | 低 |
| 7 | 3/6 | 图标体系破窗：列表圆点用 emoji 🛒🔴🟠📌（`TimelineList.tsx:52-58`）、任务标签前缀 📋（`TimelineItem.tsx:83,221`），与全站 AntD 图标/`TipButton` 规范不符，暗色主题下不可着色且无 ARIA 语义 | 换 `ShoppingCartOutlined/WarningOutlined/PushpinOutlined` 并复用 `dotColor` | 低 | 低 |
| 8 | 4 | 引导文案承诺「可按键类型与**级别**过滤」（`guides/menuGuides.ts:65`），UI 无任何级别筛选控件（level 仅用于配色，`TimelineList.tsx:36-46`）；「键类型」疑为错别字 | 文案对齐实现，或补 level 下拉 | 低 | 低 |

**三源一致性**：registry:46-52（事件时间线/FieldTimeOutlined//timeline）＝ ROUTE_LABELS:62 ＝ COMMAND_ITEMS:94 ＝ sheetRegistry:60 ＝ App.tsx:102，一致。

---

### 菜单：数据查看 > 实时日志（`/logs`）
**现状描述**：左「结构化搜索」右「原始日志/实时流」双栏；SSE 手动开关 + 暂停缓冲 + 清空。功能齐全，但作为「实时」页面缺少实时页面最基本的自动跟随与断线可见性。

| # | 维度 | 问题（具体证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 5/2 | 日志流**没有自动滚动**：`pages/Logs/Logs.tsx:301` 固定 `maxHeight:500` 滚动容器，无 `scrollTop` 副作用 → 新日志追加在底部，用户停在顶部误判「卡住了」；引导却声称「自动滚动」（`guides/menuGuides.ts:71`） | 追加时 `el.scrollTop = el.scrollHeight`（仅在贴底时），并加「跟随底部」开关 | 低 | 高 |
| 2 | 5 | 断线即彻底停流且无恢复入口：`onerror` 只 `message.warning('日志流连接断开')` + `stopStream()`（`Logs.tsx:88-91`），引导声称「断线自动重连」（`menuGuides.ts:71`）；同页 `Orders.tsx:446-480` 已有退避重连范式可抄 | 指数退避重连 + 卡片内「已断开·重连中/点击重连」状态标签 | 低 | 高 |
| 3 | 3/6 | 级别色全废：`LEVEL_COLOR` 键为大写（`constants/logLevels.ts:3-8`），后端返回的是小写存储值（`backend/.../routes/api_logs.py:177-180`，items 原样返回见 `:194`），而 `Logs.tsx:279,315` 直接用 `item.level` 查表 → ERROR 行也显示灰色；同页直方图先 `toUpperCase()`（`:135`）恰好正常，反证是缺陷 | 统一在查表前 `String(item.level).toUpperCase()`，或改常量表兼容小写 | 低 | 高 |
| 4 | 2/6 | 筛选只作用于左栏：SSE 连接不带任何过滤参数（`Logs.tsx:66`），右栏标题也无「实时流不受筛选影响」说明；暂停缓冲上限 500、显示上限 200（`75,77,110`）均无截断提示，「实时流」统计卡（`162`）数字恒 ≤200 易被当成总量 | 卡片副标题说明流不受筛选，或在 stream 侧做 level 客户端过滤；缓冲触顶时显示「仅保留最近 200 条」 | 低 | 中 |
| 5 | 4 | 「导出CSV / 导出LOG」tip 写「导出**当前**日志」（`Logs.tsx:244-245`），但 `api/event.ts:33` `exportUrl` 只拼 `format`，完全忽略 query/level/task_id → 导出内容与用户预期不符 | tip 改「导出全部日志」，或把当前筛选并入导出 URL | 低 | 中 |
| 6 | 2 | 搜索结果硬顶 `limit: 100`（`Logs.tsx:48`）且成功提示 `找到 N 条匹配`（`:52`）在恰好 100 时误导；后端已支持 `offset`/时间范围/tag/stage（`api_logs.py:99-131,151-186`）前端一律未暴露，`matched_levels` 直方图也无视、前端自算（`Logs.tsx:132-140`） | 暴露起止时间与 stage/tag 筛选，N===limit 时提示「仅前 100 条，请缩小范围」 | 中 | 中 |
| 7 | 5/1 | URL 同步是半程：每次键入即 `setSearchParams`（`Logs.tsx:30-36`），刷新后筛选条件能恢复（`17-19`）但结果不自动搜索，用户以为筛选丢了；同时 query 写进 URL 会参与 sheet 身份匹配（`hooks/useSheetSync.ts:33-38`） | 载入时若 URL 带 query 则自动执行一次 `search()`；或仅点搜索后写 URL | 低 | 低 |

**三源一致性**：registry:53-59（实时日志/FileTextOutlined//logs）＝ ROUTE_LABELS:63 ＝ COMMAND_ITEMS:95 ＝ sheetRegistry:61 ＝ App.tsx:103，一致。

---

### 菜单：数据查看 > 错误日志（`/logs/errors`）
**现状描述**：左列表（勾选+批量）右详情（5 Tab，含堆栈/请求/AI 上下文），筛选持久化 + 搜索历史药丸，是全组完成度最高的一页。

| # | 维度 | 问题（具体证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 2 | 搜索历史药点击后只填输入框、不触发查询（`pages/Logs/ErrorLogs.tsx:441`），用户点完仍需再按「搜索」，看起来像"没反应" | `onClick={() => { setFilterType(kw); doSearch() }}` | 低 | 中 |
| 2 | 5 | 「批量清理」`cleanup(30)` 无 `.catch`（`387-395`），失败时**静默**（同页其它操作均有 `message.error`），Popconfirm 也不显示将要删除的条数 | 补 catch + 失败提示；确认文案里带「命中 N 条」 | 低 | 中 |
| 3 | 2 | 列表硬顶 `limit: 100`（`85`）无分页控件，超出即不可达且界面无任何截断提示；筛选只有状态 + 错误类型（`411-430`），无时间范围 | 后端返回 total 时显示「仅最近 100 条」并加 offset/日期筛选 | 中 | 中 |
| 4 | 2 | 「全选」复选框只在已有勾选时才出现（`453`）→ 无法一次全选，必须先勾 1 条，与工具栏标题「全选」互相矛盾 | 把全选/清空行常驻（无勾选时禁用批量按钮） | 低 | 低 |
| 5 | 5 | 详情面板状态 `Select`（`270-280`）无 loading/disabled，连续切换会并发 `updateStatus` 并按响应乱序回写（`144-146`）；`useEffect` 依赖漏 `aiFormat`（`131-136`）靠手动 `handleAiFormatChange` 兜住 | Select 期间禁用并展示 loading；切换前 abort 上一请求 | 低 | 低 |
| 6 | 4/3 | 错误消息超 80 字硬截断加「...」（`568-570`）却无 Tooltip，不点开详情就看不到完整消息；空态「暂无错误日志」（`512`）不区分「筛选后无结果」与「确实没有」，也不教下一步（如查看通知渠道/清筛选） | 加 Tooltip 全文；空态按是否有筛选区分文案并给「清除筛选」按钮 | 低 | 低 |

**三源一致性**：registry:60-66（错误日志/BugOutlined//logs/errors）＝ ROUTE_LABELS:64 ＝ COMMAND_ITEMS:96 ＝ sheetRegistry:62 ＝ App.tsx:104，一致。

---

### 菜单：数据查看 > 通知中心（`/notifications`）
**现状描述**：未读/已读统计 + 全部已读/清空已读 + all/unread/read 切换 + 列表（乐观标记已读、删除）。可用，但通知与跳转链路是断的。

| # | 维度 | 问题（具体证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 2/5 | 「查看详情 →」是裸 `<a href={item.link} target="_blank">`（`pages/Notifications/index.tsx:283`），而后端写入的 link 是 `/orders?ref=<id>`（`notification_engine.py:63`）与 `/dashboard#login`（`:116`）；SPA 挂在 `basename="/xianyu"`（`main.tsx:86`，vite `base:'/xianyu/'`）→ 整页跳出到根路径 404，`/dashboard` 本身也不是注册路径（`sheetRegistry.tsx:52` 是 `/`） | 拦截点击：内部 link 走 `openSheetWithNotification` + 补 `/xianyu` 前缀；后端 link 统一为相对路由 | 低 | 高 |
| 2 | 2 | 行本身不可点：未读通知只能靠「标记已读」按钮（`233-243`），点击标题/正文无任何反应，也不打开链接 → 与全站"点行进详情"习惯冲突 | 行点击 = 有 link 则跳转并顺带标记已读；无 link 则仅标记已读 | 低 | 中 |
| 3 | 5 | 在「未读」筛选下点标记已读后，条目**仍留在列表**（乐观更新只改 `read_at`，`82-93`，不重载），红点消失而条目不消失，用户以为操作失败 | 未读视图下把该项移出列表（或 `loadList()`） | 低 | 中 |
| 4 | 1/6 | 与顶栏铃铛是两套「通知」面且互相误导：铃铛 tip「打开今日告警通知」（`MainLayout.tsx:602-611`）打开的是 `statsApi.today()` 告警抽屉，其底部「查看全部 →」固定跳 `/orders`（`:753`），而抽屉里的「低分评估」分属评估页；本页数据来自 `notificationApi` 且无未读轮询（`78-79` 仅挂载拉取） | 铃铛菜单化分列两个入口（今日告警 / 通知中心 + 未读角标），抽屉「查看全部」按分类跳对应页；本页接入未读轮询或 SSE | 中 | 中 |
| 5 | 2 | 列表 `limit: 100` 无分页（`62`），而后端支持 `offset`（`api/notifications.ts:31-35`）；筛选只有已读态（`200-219`），5 类 category/3 级 level 均不可筛（`26-32`） | 补分页与 category/level 快捷筛选（标签即筛选） | 中 | 中 |
| 6 | 4 | 空态「暂无通知」（`224`）不教下一步；本页与「通知渠道」配置页（`/config/notifier`）之间无互链，首次用户不知道通知为何不来 | 空态加「去通知渠道配置」按钮；标题区展示当前订阅摘要 | 低 | 低 |

**三源一致性**：registry:67-73（通知中心/BellOutlined//notifications）＝ ROUTE_LABELS:84 ＝ COMMAND_ITEMS:114 ＝ sheetRegistry:78 ＝ App.tsx:121，一致；但 `BellOutlined` 与「通知渠道」同图标（registry:111-117），命令面板两项视觉重复。

---

### 菜单：数据查看 > 价格行情（`/price-dashboard`）
**现状描述**：4 张卡（品类横向对比图 / 捡漏价格参考 / 价格评估 / 品类统计表），逻辑已拆入 4 hook + 4 组件。分析价值高，但**失败态与口径一致性**明显缺位。

| # | 维度 | 问题（具体证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 5 | 4 个数据 hook 全部静默吞错：`hooks/useCategoryComparison.ts:30`、`useCategoryStats.ts:19`、`useSoldRange.ts:44`、`useBargainEval.ts:32` 均无 `message.error`/错误态 → 请求失败被渲染成「暂无对比数据」（`components/CategoryComparisonChart.tsx:58`）、「暂无统计数据」（`CategoryStatsTable.tsx:93`），用户以为没数据而不去重试 | hook 暴露 `error`，卡片内 `Alert type=error` + 重试按钮（全站其它页均 `message.error`，此为规范偏离） | 低 | 高 |
| 2 | 1/6 | 同屏两套时间窗：图表默认 `rangeDays=0`「全部时间」（`useCategoryComparison.ts:17` + `constants.ts:19-24`），捡漏参考/价格评估默认 30 天（`useSoldRange.ts:26`），两套数字并排展示且无任何口径标注，唯一提示只在「未选任务」时（`SoldRangeCard.tsx:70-78`） | 页级统一时间窗（一次改四处）；或每卡标题下固定副标题写明窗口 | 中 | 中 |
| 3 | 2 | 分析结果不可下钻：条形图不可点（`CategoryComparisonChart.tsx:48`）、明细表无 `onRow`（`CategoryStatsTable.tsx:85-94`），看不到某品类的商品/任务；对比图固定 `limit: 20`（`useCategoryComparison.ts:26`）且界面未说明「仅前 20 个品类」 | 点击柱/行跳 `/items?keyword=` 或 `/tasks/:id`；图卡副标题标注 Top 20 | 中 | 中 |
| 4 | 6 | 根容器用内联 `padding: 24`（`pages/PriceDashboard/index.tsx:32`）而缺 `.page-container`，违反 `guides/menuGuides.ts:8` 声明的全站约定（同组 Orders/Timeline/Logs/ErrorLogs/Notifications 均有）；后果是该页首次引导 Tour 无法高亮、只能居中显示（`guides/GuideController.tsx:110-111`） | 换 `<div className="page-container">` | 低 | 中 |
| 5 | 5 | 空态文案与真实原因错配：`SoldRangeCard.tsx:135` 一律写「建议先执行实时搜索采集更多商品」，但任务列表加载失败时（`useSoldRange.ts:63` catch 后 `tasks=[]`）实际是「无任务/接口失败」，下拉也会空白无提示 | 分支文案：`tasks.length===0` → 「无可用任务，去任务管理新建」；失败 → 错误 + 重试 | 低 | 中 |
| 6 | 3/6 | 统计表分位列顺序 P25/P75/P10/P90（`CategoryStatsTable.tsx:61-64`）与排序项定义顺序（`constants.ts:10-13`）不一致，扫读困难；9 列 `scroll.x=960`（`92`）却无列配置/列宽持久化（同组 Orders 已用 `useColumnConfig`，`Orders.tsx:384-391`） | 列序改 P10/P25/中位/P75/P90；接入列配置 | 低 | 低 |
| 7 | 2 | 四张卡各带一个刷新按钮（`CategoryComparisonChart.tsx:81`、`SoldRangeCard.tsx:155`、`BargainEvalCard.tsx:106-113`、`CategoryStatsTable.tsx:75`），盯盘需连点 4 次，且无页级刷新/自动刷新，筛选与选择状态也全不持久化 | 卡头加「全部刷新」，或用 `usePersistentState` 记忆任务与时间窗 | 低 | 低 |
| 8 | 4 | 价格评估的两个 disabled 按钮（`BargainEvalCard.tsx:111`、`135`）无解释性 tip（外层 tip 只说功能），用户不明白为何不能点 | disabled 时 tip 改「请先输入大于 0 的价格」 | 低 | 低 |

**三源一致性**：label/图标/path/分组四处一致 —— registry:74-80（价格行情/DollarOutlined//price-dashboard/data_view）＝ ROUTE_LABELS:76 ＝ COMMAND_ITEMS:97 ＝ sheetRegistry:77。**但 App.tsx:93-129 缺 `price-dashboard` 路由**（其余 5 页皆有，见 App.tsx:100/102/103/104/121）；当前不发作是因为 MainLayout 不渲染 `<Outlet/>` 而由 `SheetWorkspace` 接管内容区（`MainLayout.tsx:657-659`），路由表已沦为死码并持续漂移。另有图标冲突：`DollarOutlined` 同时用于「价格行情」与「价格策略」（registry:74-80 vs 83-89）。

---

### 跨菜单共性问题（切片内 6 页共同承担）
1. **切页签即丢状态**：`SheetWorkspace/index.tsx:49,75` 只渲染 activeSheet，`SheetContent.tsx:47` 以 `key={sheet.id}` 重挂载 → 实时流缓冲、搜索结果、选中行、展开态、滚动位置全部清空；与 `minimizeInsteadOfClose` 偏好（`stores/sheetStore.ts:27`）叠加后用户更困惑。建议：页签内容 keep-alive（隐藏而非卸载）或至少持久化各页筛选。成本 高，优先级 中。
2. **键盘覆盖不全且助记冲突**：`MainLayout.tsx:118-128` 的 `g` 序列里 `i→/timeline`（助记更像"事件"却与"商品/items"撞车），而 `/logs/errors`、`/notifications`、`/price-dashboard` 无任何快捷键；表格也都不支持方向键选行。成本 低。
3. **重复点击防护不均**：Orders/Notifications 关键动作有 `Popconfirm`（`Orders.tsx:554`、`Notifications:174`），ErrorLogs 的批量删除有（`490-503`），但「接管/确认完成/全部标记已读」仅靠 `loading` 兜底；建议危险操作统一 confirm 范式。成本 低。
4. **空态普遍不教下一步**：`Orders.tsx:605`「暂无订单记录」、`TimelineList.tsx:15`「暂无匹配的时间线数据」、`Logs.tsx:268`「输入条件后搜索」均为纯占位，无「清除筛选/去配置/去新建」引导；筛选后无结果与真的无数据也不区分。成本 低，中。

**未发现显著体验缺陷的维度**：抢单记录与错误日志的列配置/持久化、通知中心的乐观更新回滚（`Notifications/index.tsx:84-92,116-128`）实现规范，未见问题。