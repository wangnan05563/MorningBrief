# 他报（17_xianyu T02324 UX 评审）问题清单机械提取

源文件：`D:\code\otherProjects\17_xianyu\docs\requirements\2026-10-17-逐菜单UX评审与优化建议.md`（157,718 字节 / 870 行）

提取口径（纯机械，无本人判断）：
- 编号取 §5.2 排序矩阵的 ID（`2.4-2`＝§2.4 表第 2 条；`N7`＝§1.2 列表第 7 条），优先级取矩阵所在分块（P0/P1/P2）。
- 症状取 §1–§4 正文条目原文压缩至 ≤40 字，保留原文按钮名/字段名/接口名。
- 证据列原样照抄正文条目破折号后（或括号内）的代码引用标签，仅去掉 Markdown 的 `file:///` URL 包裹；正文未给 `文件:行号` 的条目如实标注"正文无行号"。
- 顺序按原报告 §5.2 矩阵行序（成本 XS→S→M 分块），非页面顺序。

## P0（逐条，全量，不要省略）

| 编号 | 所属页面/章节 | 一句话症状（≤40字，保留原文关键名词） | 证据（文件:行号，原样照抄，多个用逗号） |
|---|---|---|---|
| 2.2-1 | 任务管理（§2.2 `/tasks`） | 关联面板「删除该关联」点击静默无响应，`linkColumns` 以 `[]` 依赖闭包捕获 | TaskList.tsx:724-730,[:575] |
| 2.3-2 | 商品列表（§2.3 `/items`） | 登录失效 Alert「重新登录」跳 `/?redirect=/items` 回仪表盘，redirect 被忽略成死循环 | ItemList.tsx:829 |
| 2.3-4 | 商品列表（§2.3 `/items`） | 卡片视图 `key={item.link_id}`，实时搜索 `link_id` 恒 0 致复用错行、高亮串位 | ItemList.tsx:1088 |
| 2.4-2 | 评估明细（§2.4 `/evaluations`） | 「重新评估」未选任务时对全库静默重算，无确认、无消耗提示 | Evaluations/index.tsx:591,useEvalBatch.ts:142-154 |
| 2.4-3 | 评估明细（§2.4 `/evaluations`） | 批量 AI 评估逐条 `catch {}` 吞错，结束仍弹"批量评估完成，共处理 N 项" | useEvalBatch.ts:100-109 |
| 2.7-2 | 实时日志（§2.7 `/logs`） | 级别分布 `dist` 键为 `ERROR`，小写 `err` 不在键内，有错误时仍显示「ERROR 0」 | Logs.tsx:133 |
| 2.7-3 | 实时日志（§2.7 `/logs`） | 主开关"停止实时流"与内层"暂停"复用同一 `PauseCircleOutlined` | Logs.tsx:175,[:186] |
| 2.9-2 | 通知中心（§2.9 `/notifications`） | 铃铛抽屉「查看全部 →」跳 `/orders` 而非 `/notifications` | MainLayout.tsx:753 |
| 2.11-1 | 数据导出（§2.11 `/export`） | `buildUrl` 返回 `/api/export/...` 未加 `API_BASE`，`/xianyu` 子路径下被代理拦截 | api/export.ts:56 vs api/event.ts:33 |
| 3.5-1 | 通知渠道（§3.5 `/config/notifier`） | 所有字段一律 `Input.Password`，Server URL/Chat ID/Topic 被掩码，`secret` 标志从未使用 | ChannelCard.tsx:85,constants.ts:67,[:80],[:107],[:134] |
| 3.9-1 | 配置管理组跨页共性（§3.9） | 8 页中仅抢单策略告知"无需重启"，其余页保存后生效时机一律不明 | 正文无行号（真机 8 个配置页截图核对按钮文案） |
| 4.1-2 | 系统清理（§4.1 `/maintenance`） | dry-run 时数据库结果区显示绿色「删除 0 条」，后端 `dry_run` 恒返回 `total_deleted=0` | Cleanup.tsx:182 + api_maintenance.py:321-338 |
| 4.5-2 | 反爬登录管理（§4.5 `/anticrawl`） | 「停止会话」零确认，停掉 TokenRenewer 等于放任登录态过期后重新扫码 | index.tsx:336-347,[:972-981] |
| 4.8-1 | 关于（§4.8 `/about`） | 用户协议/隐私条款/官方社区/报告问题/联系我们全指 `https://example.com/...` 与 `mailto:dev@example.com` | AboutMenuList.tsx:16-25 |
| 4.10-1 | 菜单管理（§4.10 `/menu-admin`） | 保存后不失效菜单缓存，未调 `invalidateMenuCache`/`refresh`，侧栏最长 5 分钟不更新 | MenuAdmin/index.tsx:115-144 |
| 4.10-4 | 菜单管理（§4.10 `/menu-admin`） | 关闭 sheet 无未保存拦截，dirty 只有一枚橙色"未保存"Tag | MenuAdmin/index.tsx:173 |
| N7 | 全局导航外壳（§1.2） | 深链刷新看不到自己在哪：`openKeys` 用 `useState(autoOpenKeys)` 初值锁死空数组 | MainLayout.tsx:172,322-339 |
| N12 | 全局导航外壳（§1.2） | `fetchTodayAlert` 失败被 `.catch(() => {})` 吞，告警抽屉永久 `<Spin/>` | MainLayout.tsx:181,756-758 |
| N15 | 全局导航外壳（§1.2） | 演练横幅与 `.sheet-workspace{height:100%}` 使页面底部被裁掉约 40px | MainLayout.tsx:654-660、SheetWorkspace/sheet.css:6-10 |
| N16 | 全局导航外壳（§1.2） | 演练横幅把任务名逐个拼接、无去重无省略，占两行把结论挤到末尾 | MainLayout.tsx:656、layout/DryRunBanner.tsx |
| N19 | 全局导航外壳（§1.2） | 「已自动替换 sheet」通知固定右上角，遮挡 Header 全部操作按钮 | sheetNotifications.tsx:30-50 |
| 2.1-1 | 仪表盘（§2.1 `/`） | 「趋势大图」Modal 无任何入口：`setTrendOpen` 全仓无置 true 调用 | Dashboard/index.tsx:58,[:388] |
| 2.1-4 | 仪表盘（§2.1 `/`） | 异常雷达订单链接用裸 `<a href="/orders?ref=...">`，`basename=/xianyu` 下 404 | AlertRadar.tsx:58,[:76] |
| 2.2-2 | 任务管理（§2.2 `/tasks`） | 「全部启动」只作用当前页 `tasks`（limit=pageSize），第 2 页任务不启动 | TaskList.tsx:611-616,[:917] |
| 2.2-4 | 任务管理（§2.2 `/tasks/new`） | 新建任务核心路径最少 7 步，Step3/4/5 全默认"沿用全局"仍强制经过，无快速创建 | TaskEditor.tsx:414-421 |
| 2.4-1 | 评估明细（§2.4 `/evaluations`） | 行内「手动抢单」直接下真实订单，无任何 Modal.confirm | useEvalBatch.ts:170-175 |
| 2.5-1 | 抢单记录（§2.5 `/orders`） | 「待处理/已成功/已失败/人工接管」四卡只统计当前页，翻页数字全变 | Orders.tsx:404-411,[:577-580] |
| 2.7-4 | 实时日志（§2.7 `/logs`） | "导出 CSV/LOG"提示"导出当前日志"，实为固定 URL 不带 query/level/task，导全量 | Logs.tsx:244-245,api/event.ts:33 |
| 3.1-1 | 价格策略（§3.1 `/config/price`） | 脏检测失效：`strategy` 本地 state，改滑块后 `hasChanges()` 仍 false，「重置」保持禁用 | PriceStrategy.tsx:87,[:193] |
| 3.1-2 | 价格策略（§3.1 `/config/price`） | 直方图失败静默换模拟数据无标注；「刷新预览数据」是 500ms setTimeout 假动作 | PriceStrategy.tsx:74-81,[:433-439] |
| 3.4-2 | 搜索参数（§3.4 `/config/search`） | 「操作延迟」保存时静默覆盖 antidetect 的 `max_delay_ms/qps/fail_pause_threshold` | SearchConfig.tsx:128-131 |
| 3.6-2 | AI 服务（§3.6 `/config/ai`） | Embedding Tab 无保存按钮，只有"测试连接"却隐式 PUT 保存；LLM 测试同样先保存 | EmbeddingConfigForm.tsx:207-225,index.tsx:197-203,[:155] |
| 3.8-1 | 配置版本（§3.8 `/config/version`） | 「分享配置（已脱敏）」`SENSITIVE_KEYS` 仅 4 项，漏 `telegram_bot_token`/`dingtalk_secret`/`ntfy_token`/`wecom_webhook` | VersionManager.tsx:120,[:408],[:422] |
| 4.1-1 | 系统清理（§4.1 `/maintenance`） | 「确认清理缓存？此操作不可撤销。」未说 `webview_data_*` 是登录 Cookie 与反爬指纹 | Cleanup.tsx:88 + api_maintenance.py:141-142 |
| 4.2-1 | 数据库维护（§4.2 `/maintenance/db`） | 导入确认框写「请选择冲突处理：」，实际只有 `跳过冲突`，`mode` 恒 `'insert'` | DatabaseAdmin.tsx:533-556 + api_db_admin.py:825 |
| 4.2-2 | 数据库维护（§4.2 `/maintenance/db`） | 导出按钮无 loading/行数预估，后端忽略搜索条件导出全表（`events` 大表） | DatabaseAdmin.tsx:648-653 + api_db_admin.py:768-773 |
| 4.4-1 | 批量采集（§4.4 `/batch-refresh`） | `running→idle` 只靠轮询改 UI，无完成 toast、无结果汇总面板 | BatchRefresh.tsx:219-237,[:369-372] |
| 4.5-3 | 反爬登录管理（§4.5 `/anticrawl`） | 5 个 `fetch*` 全部只 `console.error`，401/超时后呈"半空卡片"，无错误态与重试 | index.tsx:227-287 |
| 4.6-1 | 内网穿透（§4.6 `/maintenance/tunnel`） | 文案「配置已保存，下次启动隧道时生效」，实际每次 POST /config 后台线程 stop 隧道 | Tunnel.tsx:523 + api_tunnel.py:265-282 |
| 4.6-2 | 内网穿透（§4.6 `/maintenance/tunnel`） | `handleStart` 仅在 `formProvider !== config.provider` 时先保存，其余脏字段被静默忽略 | Tunnel.tsx:456-462 |
| N1 | 全局导航外壳（§1.2） | 同页四处叫法不同：`/items` 商品中心vs商品列表、`/evaluations`、`/chatbot` | config/menu_registry.yaml:26,33,179 vs MainLayout.tsx:59,61,109 vs sheetRegistry.tsx:57,59,83 |
| 2.8-1 | 错误日志（§2.8 `/logs/errors`） | 无聚合去重：真机"新建 1,869"多为 RuntimeError/TypeError 同文重复行 | ErrorLogs.tsx:519 |
| 2.9-1 | 通知中心（§2.9 `/notifications`） | 两套口径冲突：顶栏铃铛 Badge＝今日告警（`failed+timeout+low_eval`）与本页 `unreadCount` 无关 | MainLayout.tsx:156-158,Notifications/index.tsx:71-79 |
| 2.11-2 | 数据导出（§2.11 `/export`） | `download` 走 `location.href`，try/catch 捕不到 HTTP 错误，失败仍弹"正在导出…" | Export/index.tsx:88-94,api/export.ts:60-62 |
| 3.6-1 | AI 服务（§3.6 `/config/ai`） | 「保存配置」按钮在 Tab 内容底部左侧，无重置、无脏检测、无 DiffPreviewModal | ModelConfigForm.tsx:249 |
| 3.7-1 | 客服配置（§3.7 `/config/chatbot`） | 全站唯一"即改即存"页，无 Diff 预览无回滚入口，连拖 Slider 连环 toast+连环 PUT | Chatbot/Config.tsx:99-118,[:109] |
| 3.9-2 | 配置管理组跨页共性（§3.9） | 8 页共享 configStore，未保存改动跨页污染，关 sheet/切标签无拦截直接丢 | 正文无行号（关联 §4.10-4 同一实例） |
| 4.2-3 | 数据库维护（§4.2 `/maintenance/db`） | 编辑提交丢弃空串字段，用户无法把任何字段清空/置 NULL 且界面无说明 | DatabaseAdmin.tsx:452-457 |
| 4.3-1 | 向量数据库维护（§4.3 `/maintenance/vector`） | 菜单/命令面板双入口缺失只能手输 URL；「客服配置 › 向量库维护」有第二套同名 UI | VectorAdmin.tsx:37-426,VectorAdminPanel.tsx |
| 4.5-1 | 反爬登录管理（§4.5 `/anticrawl`） | 「可用策略」5 个 Tag 纯展示不可点，`anticrawlApi.setStrategy` 全仓零调用 | index.tsx:577-586,api/anticrawl.ts:156-157 |
| 4.11-1 | 确认抢单（§4.11 `/confirm-buy`） | 花钱且不可逆动作无二次确认，主按钮直接触发（tip「创建待支付订单并提交抢单」） | ConfirmBuy/index.tsx:194-204 |
| 4.11-2 | 确认抢单（§4.11 `/confirm-buy`） | 不显示快照时间/剩余接管窗口/是否已售，也无"刷新商品" | ConfirmBuy/index.tsx:157-184 |
| N11 | 全局导航外壳（§1.2） | 告警抽屉与 `/notifications` 两套计数与已读模型，抽屉三类列表项不可点，低分评估跳抢单记录 | MainLayout.tsx:156-158,665-758、pages/Notifications/index.tsx:73 |

## P1（逐条，全量）

| 编号 | 所属页面/章节 | 一句话症状（≤40字） | 证据（文件:行号） |
|---|---|---|---|
| 2.1-3 | 仪表盘（§2.1） | 「可视化配置入口」区实为 11 个功能页快捷入口，与侧边菜单完全重复 | Dashboard/index.tsx:304-383 |
| 2.1-5 | 仪表盘（§2.1） | 「调度器未运行」警告只说"请启动调度器"，无可操作按钮/指引 | Dashboard/index.tsx:250-258 |
| 2.2-6 | 任务管理（§2.2） | 「半自动：通知+自动抢单（需确认）」与「需确认：通知+人工确认抢单」几乎同义 | TaskEditor.tsx:74-79 |
| 2.2-8 | 任务管理（§2.2 详情） | 详情页「状态/模式」直接显示英文原值 `running`、`confirm`，排除词显示原始 JSON | TaskDetail.tsx:460-468 |
| 2.3-1 | 商品列表（§2.3） | 侧栏/标签栏叫「商品中心」，帮助文档叫「商品列表」两套并存 | sheetRegistry.tsx:57,Help/index.tsx:199 |
| 2.4-4 | 评估明细（§2.4） | 菜单名「卖家评估」vs 页面/帮助「评估明细」，页面实际评估商品 | menu_registry.yaml,Help/index.tsx:220 |
| 2.4-5 | 评估明细（§2.4） | 「订单」列 key `order_status` 未注册进 `COLUMN_DEFINITIONS`，列配置管不到 | Evaluations/index.tsx:55-75 |
| 2.4-7 | 评估明细（§2.4） | 「阈值通过率计算器」的"总数"实为当前页条数（传 `list.items.length`） | Evaluations/index.tsx:265,[:694] |
| 2.4-10 | 评估明细（§2.4） | 数据不足 Alert 让用户"建议在 Dashboard 页面重新登录"，无直达按钮 | Evaluations/index.tsx:604 |
| 2.5-2 | 抢单记录（§2.5） | 筛选下拉无「演练」选项，表内却有 `dry_run` 红 Tag 与普通单混排 | Orders.tsx:592-597 |
| 2.5-3 | 抢单记录（§2.5） | 「商品ID」列为纯文本，无法跳商品详情/原帖 | Orders.tsx:510 |
| 2.5-6 | 抢单记录（§2.5） | 待处理列表金额有 sorter、时间列无 sorter，无法快速找最新待接管单 | Orders.tsx:513,[:521] |
| 2.6-1 | 事件时间线（§2.6） | 过滤标签云暴露内部术语「发现商品（旧枚举）」 | eventTypes.ts:65 |
| 2.6-2 | 事件时间线（§2.6） | 「共 N 条」上限 500 且后端 `items[:limit]` 静默截断，4 张统计卡无限定语 | Timeline/index.tsx:74,TimelineList.tsx:117,timeline.py:76 |
| 2.7-1 | 实时日志（§2.7） | 搜索行级别 Tag 恒灰：后端 `events.level` 存小写，`LEVEL_COLOR` 只有大写键 | Logs.tsx:279,logLevels.ts:2-8,api_logs.py:177-181 |
| 2.7-5 | 实时日志（§2.7） | 搜索 toast 只报返回条数（≤100），后端 `total_estimate` 弃用 | Logs.tsx:52,api/event.ts:27 |
| 2.8-5 | 错误日志（§2.8） | 「批量清理」`cleanup(30).then` 无 catch，失败静默 | ErrorLogs.tsx:391 |
| 2.9-7 | 通知中心（§2.9） | `markRead` 成功后不 reload，"未读"筛选下已读项仍滞留列表 | Notifications/index.tsx:82-93 |
| 3.1-3 | 价格策略（§3.1） | 「命中预览」只算上下限，`market_ratio`/`top_n` 开关不影响结果 | PriceStrategy.tsx:136-137 |
| 3.2-1 | 评估规则（§3.2） | Alert 说权重总和"建议为 100（否则归一化）"，实际保存硬性拦截"必须为 100" | EvalRules.tsx:355,[:298] |
| 3.3-3 | 抢单策略（§3.3） | 「价格容差」输入框无 % 显示，仅 help 解释"0.05=5%"，易误填 5 | BuyerStrategy.tsx:241-252 |
| 3.4-1 | 搜索参数（§3.4） | 按钮文案「保存配置」异于其余页；失败仅"预览失败，请重试"丢后端详情 | SearchConfig.tsx:187,[:159-160] |
| 3.5-3 | 通知渠道（§3.5） | 免打扰/22 事件订阅无生效说明（是否需重启通知服务） | 正文无行号 |
| 3.6-3 | AI 服务（§3.6） | 关闭总开关用原生 `globalThis.confirm`；切换预设失败仅"切换预设失败" | AIConfig/index.tsx:94,[:131] |
| 3.7-2 | 客服配置（§3.7） | 失败反馈"更新失败"无原因，且失败后静默回滚本地状态 | Chatbot/Config.tsx:111,[:113-114] |
| 3.7-3 | 客服配置（§3.7） | 「启用智能客服」「PII 脱敏」开关无二次确认 | Chatbot/Config.tsx:203-207,[:566-570] |
| 3.8-2 | 配置版本（§3.8） | 导入的 JSON.parse/diff 预览失败统一"文件解析失败" | VersionManager.tsx:209-211 |
| 3.8-3 | 配置版本（§3.8） | 回滚/恢复后未提示其他配置页需重新打开加载新值（store `original` 不失效） | 正文无行号 |
| 4.1-3 | 系统清理（§4.1） | Select 选项「临时文件」实际执行 `_cleanup_pycache`，`/tmp/xianyu_*` 统计 Windows 恒 0 | Cleanup.tsx:286 + api_maintenance.py:130,[:192-193] |
| 4.4-3 | 批量采集（§4.4） | 「确认清空全部历史记录？」与「清理 30 天前」都不给将被删除条数 | BatchRefresh.tsx:1059-1075 |
| 4.7-2 | 智能客服（§4.7） | 侧栏「智能客服」vs 面板/标签「智能客服对话」，且与「客服配置」同用 `MessageOutlined` | sheetRegistry.tsx:83 |
| 4.9-3 | 帮助文档（§4.9） | `Anchor` 以 window 为滚动容器，实际滚动在 `.sheet-content-area`，锚点不可靠 | sheet.css:14-20 |
| 4.9-4 | 帮助文档（§4.9） | 不在 registry、无侧栏入口，仅 Header 问号与命令面板；引导悬浮按钮 `href="#/help"` 失效 | 正文无行号（见 N22） |
| 4.10-5 | 菜单管理（§4.10） | 本页自身不在 registry，无法被隐藏/排序，也不在命令面板 | 正文无行号（即 N2） |
| 4.11-5 | 确认抢单（§4.11） | 不在 registry/命令面板，`ROUTE_LABELS` 无此键 → 面包屑只剩「首页」 | 正文无行号 |
| 4.13-3 | 新手引导（§4.13） | 执行模式只给 notify/confirm/auto，缺 `semi_auto` | Onboarding/index.tsx:173-177 |
| N3 | 全局导航外壳（§1.2） | 命令面板与菜单集合不等：内网穿透搜不到，`/tasks/new` 等 7 页无面板项 | MainLayout.tsx:88-115 |
| N6 | 全局导航外壳（§1.2） | 分组图标取 `items[0].icon`；registry 内重复图标 4 组（Bell/Dollar/Message/CloudDownload×2） | useMenuConfig.tsx:162、menu_registry.yaml:70,76,104,113,157,179,186 |
| N17 | 全局导航外壳（§1.2） | 切 sheet 后停在旧滚动位置：重置目标 `#main-content` 从不滚动 | MainLayout.tsx:481-487、sheet.css:14-20 |
| N22 | 全局导航外壳（§1.2） | 无引导页悬浮按钮 `href="#/help"` 在 `basename="/xianyu"` 下只改 hash，点了不跳转 | GuideController.tsx:167,187 |
| 2.1-2 | 仪表盘（§2.1） | 「待支付/成功/失败」三张统计卡共用同一条 `sparklines.orders` 迷你曲线 | StatCardsSection.tsx:65,[:78],[:91] |
| 2.1-7 | 仪表盘（§2.1） | 切换直方图任务触发整页 `Spin` 重刷（事件流/KPI 全部接口），全页闪断 | Dashboard/index.tsx:83,[:205-209] |
| 2.2-9 | 任务管理（§2.2） | 操作列 6 元素（编辑/启动/停止/复制/更多/删除）叠加 9 列；可点「采集周期」Tag 无暗示 | TaskList.tsx:841-883 |
| 2.3-3 | 商品列表（§2.3） | DB 模式下地区/品牌下拉只从当前页提取，翻页后选项集变化 | ItemList.tsx:653-660 |
| 2.3-5 | 商品列表（§2.3） | 标题列渲染为去样式 button，"点击＝采集+新开原帖"双重副作用只靠 Tooltip 发现 | ItemList.tsx:716-722 |
| 2.4-6 | 评估明细（§2.4） | 分析面板两张卡都有"目标通过率滑块 + 建议阈值"（10-90 与 10-100），结果可能不同 | Evaluations/index.tsx:236-281 |
| 2.4-8 | 评估明细（§2.4） | 品牌筛选选项仅来自当前列表，选中后只剩该品牌，换品牌须先 allowClear | Evaluations/index.tsx:471-473 |
| 2.5-4 | 抢单记录（§2.5） | 接管倒计时归零显示"已超时"红字，但「确认完成/取消接管」照常可点 | Orders.tsx:310-340 |
| 2.6-3 | 事件时间线（§2.6） | 展开态用数组下标记忆，翻页/刷新后跳条；payload 只渲染前 12 字段无复制 | Timeline/index.tsx:22,TimelineItem.tsx:190 |
| 2.7-6 | 实时日志（§2.7） | 结构化搜索无时间范围项，后端 `start` 参数未暴露 | Logs.tsx:213-243 |
| 2.7-7 | 实时日志（§2.7） | 断流只弹一次即 `stopStream()`：不清 `streamLogs` 也不改标题，无「点击重连」 | Logs.tsx:88-91,[:297],[:304] |
| 2.7-9 | 实时日志（§2.7） | 加载失败 `message.error` 与空态"暂无日志"共用，错误态无内联重试 | Logs.tsx:42,[:311] |
| 2.8-2 | 错误日志（§2.8） | 与实时日志职责边界不清，错误项无法一键跳对应实时日志/事件 | ErrorLogs.tsx:56 |
| 2.8-3 | 错误日志（§2.8） | 无时间范围筛选、`limit=100` 且无分页，海量新建无法回溯 | ErrorLogs.tsx:85 |
| 2.8-4 | 错误日志（§2.8） | 「错误类型」为自由文本 Input 而非既有类型下拉，易输错 | ErrorLogs.tsx:423 |
| 2.9-3 | 通知中心（§2.9） | 「已读」＝total−unread，而 total 随筛选变化（选"未读"恒 0） | Notifications/index.tsx:65,[:145] |
| 2.9-5 | 通知中心（§2.9） | 无勾选式批量删除，仅"全部已读/清空已读"两把大锤 | Notifications/index.tsx:96-143 |
| 2.9-6 | 通知中心（§2.9） | 「查看详情 →」`target=_blank` 新开浏览器页，破坏 SheetWorkspace 且不标已读 | Notifications/index.tsx:283 |
| 2.10-1 | 价格行情（§2.10） | 对比图 `limit=20` 含大量 0 样本的"演练测试"空条占满 y 轴 | useCategoryComparison.ts:25,[:44] |
| 2.10-4 | 价格行情（§2.10） | 两卡默认时间窗不一致（"全部时间" vs "近 30 天"）且筛选不持久化 | useCategoryComparison.ts:17,useSoldRange.ts:29 |
| 2.10-5 | 价格行情（§2.10） | 加载失败与空数据都渲染同一 `Empty`，无 `message.error`/内联重试 | useCategoryComparison.ts:30-32 |
| 2.11-4 | 数据导出（§2.11） | 状态/等级为自由文本 Input（示例只写 placeholder），无校验易输错 | Export/index.tsx:156-171 |
| 2.11-5 | 数据导出（§2.11） | 页名"数据导出"但仅 CSV 单格式、无字段勾选，列定义为英文原始名 | Export/index.tsx:128-133 |
| 3.1-5 | 价格策略（§3.1） | 「捡漏价格分位数」滑块直接写 store，与其余 4 卡本地 state 混用两种数据流 | PriceStrategy.tsx:217 |
| 3.2-2 | 评估规则（§3.2） | `pass_score`/`auto_buy_score` 与「抢单策略」页重复编辑同一字段，无互链提示 | EvalRules.tsx:506-540 vs BuyerStrategy.tsx:149-178 |
| 3.5-2 | 通知渠道（§3.5） | 后端返回脱敏值时用户"改一半"即提交坏值；发送测试仅校验空字段 | NotifierChannels/index.tsx:164-168 |
| 3.6-4 | AI 服务（§3.6） | 预算区第三个独立保存按钮「保存预算设置」，一页三种保存语义 | BudgetSettings.tsx:66 |
| 4.1-4 | 系统清理（§4.1） | 清理后 `loadStatus()` 命中后端 60s 缓存（`cached_ttl(60)`），概览数字不变 | Cleanup.tsx:102 + api_maintenance.py:70 |
| 4.1-5 | 系统清理（§4.1） | target 选 `vacuum`/`sold_items` 时「保留天数」仍可编辑；VACUUM 锁库无提示 | Cleanup.tsx:348-363,[:101-104] |
| 4.2-4 | 数据库维护（§4.2） | 删除确认只显示「主键：xxx」无业务摘要；删 `accounts` 掉登录态却无风险提示 | DatabaseAdmin.tsx:388-392,[:46-58] |
| 4.2-5 | 数据库维护（§4.2） | 级联预览失败仅灰字但确认可提交；审计抽屉先开后填（`loadAuditLog()` 未 await） | DatabaseAdmin.tsx:146-148,[:573],[:836-870] vs VectorAdmin.tsx:204-206 |
| 4.3-2 | 向量数据库维护（§4.3） | 两套危险操作强度不一致：本页手输 `CONFIRM_DELETE`，客服配置同一「清空集合」只有 Popconfirm | VectorAdmin.tsx:89-122,VectorAdminPanel.tsx:210-220 |
| 4.3-4 | 向量数据库维护（§4.3） | chatbot 未启用只弹一次 toast，4 张统计卡显 `-`；`last_snapshot_at.slice(5,16)` 丢年份 | VectorAdmin.tsx:58-66,[:241-268],[:259] |
| 4.4-4 | 批量采集（§4.4） | 概览卡「总执行次数」用筛选后的 `total`；状态/来源持久化而 task_id/日期不持久化 | BatchRefresh.tsx:963-999,[:713-724] |
| 4.4-5 | 批量采集（§4.4） | 暂停/继续/停止禁用态 tooltip 仍是动作描述（「暂停当前批次，采集完成后生效」） | BatchRefresh.tsx:373-376 vs [:612-647] |
| 4.5-4 | 反爬登录管理（§4.5） | 「主动失效」确认标题用英文层名「确认失效 session 层？」，未说后果与自愈 | index.tsx:364-379,[:668-680] |
| 4.5-6 | 反爬登录管理（§4.5） | Cookie 弹窗称「原子更新」未说合并还是覆盖；「从浏览器导入」静默丢手改内容 | index.tsx:854-857 + api_anticrawl.py:503 |
| 4.6-3 | 内网穿透（§4.6） | `loadStatus/loadConfig` 失败只 `console.error`，表单回落 `cloudflare`，页面仍显示「○ 已停止」 | Tunnel.tsx:406-431,[:559-560],[:731] |
| 4.6-4 | 内网穿透（§4.6） | 同页两套持久化模型（表单需保存 vs 向导立即落库）；步骤②③置灰只靠 `opacity:0.5` | Tunnel.tsx:184-219,[:299],[:340] |
| 4.7-1 | 智能客服（§4.7） | 页面自带 `Layout + Sider` 嵌进外壳成三列竖条，正文宽度被吃掉约 340px | Chatbot/index.tsx:872,[:871-1046] |
| 4.7-3 | 智能客服（§4.7） | 首访引导因缺 `.page-container` 永不触发；转人工后仅 `message.warning` 无后续状态 | Chatbot/index.tsx:721 |
| 4.7-4 | 智能客服（§4.7） | 模型下拉把 `model.id` 直接当 label，普通用户看到裸模型串 | Chatbot/index.tsx:994 |
| 4.9-1 | 帮助文档（§4.9） | 内层 `Sider` 用 `collapsedWidth={0}`+`breakpoint="lg"`+`trigger={null}`，≤1024px 目录无法展开 | Help/index.tsx:780-782 |
| 4.10-3 | 菜单管理（§4.10） | 页内又渲染一套 `Layout + Header` 形成双层标题栏；"返回上一页"用 `navigate(-1)` | MenuAdmin/index.tsx:240-252,[:258] |
| 4.11-3 | 确认抢单（§4.11） | 文案说"通过评估并触发了半自动模式通知"，却不展示评估分与通过理由 | 正文无行号 |
| 4.12-1 | 登录（§4.12） | 全站称"扫码登录/扫码重登录"，登录页并无扫码 Tab | Onboarding/index.tsx:96、UserMenu.tsx:95 |
| 4.13-2 | 新手引导（§4.13） | 步骤间无校验，"跳过"可一路走到"设置完成"，未登录也提示成功 | Onboarding/index.tsx:272 |
| 4.14-1 | 移动端（§4.14 `/m/*`） | 有路由无入口：`/m/items/`、`/m/evaluations/`、`/m/timeline/`、`/m/anticrawl/` 打不开 | mobile/routes.tsx |
| 4.14-3 | 移动端（§4.14） | 移动 KPI 指标贴错标签：「发现商品」取 `tasks.total`、「通知失败」取 `orders.failed` | Mobile Dashboard.tsx:78-87 |
| 4.14-4 | 移动端（§4.14） | 硬编码 `#E20613`/`#C9A961` 与桌面品牌橙 `#FF6200` 冲突，暗色下不可读 | Mobile Dashboard.tsx:102,[:110],[:156] + main.tsx:18 |
| 4.14-5 | 移动端（§4.14） | Tab 叫「告警」实为通知中心；`/m/chatbot-config/` 与 `/config/chatbot` 无对应；`/m/market` 不同源 | TabBar.tsx:16-22（§4.14 现状描述） |
| N2 | 全局导航外壳（§1.2） | 五个页面只有单一隐藏入口：`/menu-admin`、`/maintenance/vector`、`/onboarding`、`/confirm-buy`、`/help` | AccountSwitcher.tsx:334,387、App.tsx:114、Dashboard/index.tsx:241、api/templates.py:460 |
| N5 | 全局导航外壳（§1.2） | 分组降级规则自相矛盾：单项分组降级为裸顶层项，隐藏到只剩 1 项时 SubMenu 突变且图标改变 | useMenuConfig.tsx:148-171 |
| N10 | 全局导航外壳（§1.2） | 首屏三段全屏 Spin 串行；`useMenuConfig` 的 `error` 被丢弃，`/api/menu` 失败侧栏静默空白无重试 | MainLayout.tsx:172,373-399、useMenuConfig.tsx:205-246 |
| N21 | 全局导航外壳（§1.2） | 引导向导被 `.page-container` 硬门槛拦住，7 个已配引导页永不触发（29 条仅 22 页可触发） | guides/GuideController.tsx:94、guides/menuGuides.ts |
| 2.2-3 | 任务管理（§2.2） | 三套确认模式并存（自研行内装备确认+5s 撤销 / Popconfirm / Modal.confirm），5s 后无声恢复 | TaskList.tsx:84-134 vs Orders.tsx:554 |
| 2.2-5 | 任务管理（§2.2 编辑） | Steps 无 `onChange` 不可点选跳步；除 Step0 关键词外各步零校验 | TaskEditor.tsx:564 |
| 2.6-5 | 事件时间线（§2.6） | 未知事件类型显示英文片段 `payment_done`、数据质量显示「数据: full」；无时间筛选与自动刷新 | TimelineItem.tsx:73,[:158] |
| 2.9-4 | 通知中心（§2.9） | 无"标记未读"、无按级别/类别/时间筛选、无分页（limit 100） | Notifications/index.tsx:62,[:201-218] |
| 2.10-2 | 价格行情（§2.10） | 无下钻：条形图与明细表行均无 onClick，无法从品类进入商品 | CategoryComparisonChart.tsx:48,CategoryStatsTable.tsx:85 |
| 2.11-3 | 数据导出（§2.11） | 无行数预估/预览，limit 上限 50000 盲导，无异步任务进度反馈 | Export/index.tsx:78-95 |
| 3.3-2 | 抢单策略（§3.3） | 「单日抢单数量上限」承认仍在 `buyer_config.py`"待 UI 化"，此页无法完成安全闭环 | BuyerStrategy.tsx:363-366 |
| 3.9-3 | 配置管理组跨页共性（§3.9） | 保存范式实为 4 种（configStore+Diff / 本地 state+PUT / 防抖自动 PUT / 原生 confirm） | 正文无行号（跨页共性） |
| 4.1-6 | 系统清理（§4.1） | 原生 `confirm` 与全站 antd Modal 风格割裂 | 正文无行号（关联 §3.6-3、§3.7-3） |
| 4.3-3 | 向量数据库维护（§4.3） | 「按来源文件删除」是自由文本，无候选列表、删除前不显示命中条数 | VectorAdmin.tsx:180-199 + api_vector_admin.py:272-291 |
| 4.4-2 | 批量采集（§4.4） | 「立即触发批量采集」无二次确认、无范围预估（待采商品数） | BatchRefresh.tsx:276-290,[:595-606] |
| 4.10-2 | 菜单管理（§4.10） | 引导文案承诺"拖拽排序"，页面只有数字输入，且 `custom_label`/`group` API 已支持却无 UI | menuGuides.ts:191,api/menu.ts:49-55 |
| 4.12-2 | 登录（§4.12） | 「浏览器登录」与「浏览器导入」仅差二字机制完全不同，首屏 4 Tab 过载 | Login/index.tsx:1156-1235,[:1300-1341]（现状描述） |
| 4.13-1 | 新手引导（§4.13） | 第 1/4 步要求回终端执行 `python -m xianyu_hunter qr-login` / `worker` | Onboarding/index.tsx:103,[:220] |
| 4.13-4 | 新手引导（§4.13） | 页内 `<Link to="/config/notifier">` 直接挂载 MainLayout；无进度持久化，刷新回第 1 步 | Onboarding/index.tsx:204 |
| N23 | 全局导航外壳（§1.2） | `App.tsx` 28 条子路由永不渲染（`MainLayout` 不渲染 `<Outlet/>`），双事实源漂移 | App.tsx:93-131、MainLayout.tsx:659、SheetWorkspace/SheetContent.tsx:36 |

## P2（逐条，全量）

| 编号 | 所属页面/章节 | 一句话症状（≤40字） |
|---|---|---|
| 2.1-6 | 仪表盘（§2.1） | 事件流徽标显示 `events.length`（最多 100）但列表仅渲染 50 条 |
| 2.2-7 | 任务管理（§2.2） | 卡片视图分页只有上/下一页按钮，无 total/pageSize 切换 |
| 2.3-6 | 商品列表（§2.3） | 进实时模式后分页消失、删除按钮置灰，无任何一次性说明 |
| 2.5-5 | 抢单记录（§2.5） | 菜单叫「抢单记录」空态却写"暂无订单记录"；接管失败仅"接管失败" |
| 2.7-8 | 实时日志（§2.7） | `startStream` 立即弹"已开启实时日志流"，首帧前无"连接中"态 |
| 2.8-6 | 错误日志（§2.8） | 列表 `error_message` 截断 80 字，无展开/悬浮全文 |
| 2.8-7 | 错误日志（§2.8） | 状态文案在三处硬编码（标签/详情 Select/筛选） |
| 2.10-3 | 价格行情（§2.10） | 明细列序 P25,P75,P10,P90 非单调，且 P10/P90 缺排序 |
| 2.10-6 | 价格行情（§2.10） | 下拉占位"选择品类"实为任务列表，"品类/任务"术语混用 |
| 2.10-7 | 价格行情（§2.10） | y 轴品类名截断 12 字（"联想 DDR4 3200"），仅 tooltip 有全名 |
| 2.11-6 | 数据导出（§2.11） | 无导出历史/条件记忆 |
| 3.1-4 | 价格策略（§3.1） | 回滚入口不统一：本页用 RevertIcon，评估规则用「⏪」emoji |
| 3.3-1 | 抢单策略（§3.3） | 保存按钮硬编码橙色 `backgroundColor:'#FF6200'`，偏离全局 primary |
| 3.4-3 | 搜索参数（§3.4） | 「等效 QPS」实际展示"次/分钟"，名不副实 |
| 4.5-5 | 反爬登录管理（§4.5） | 本页用 `style={{padding:24}}` 且无页头标题/说明行，与同组 4 页不一致 |
| 4.6-5 | 内网穿透（§4.6） | 「在新窗口打开公网地址」是无 children 无 `aria-label` 的纯图标按钮；停止无确认 |
| 4.8-2 | 关于（§4.8） | 8 条链接一律挂"外链箭头"图标，但「帮助文档」是站内 Link、「开源软件声明」开 Modal |
| 4.8-3 | 关于（§4.8） | 「关于」有 4 个入口（侧栏/Header `i`/命令面板/`g+a`），页内 `<Link to="/help">` 绕过 sheet |
| 4.11-4 | 确认抢单（§4.11） | 次按钮文案"取消"、tip"放弃抢单并返回评估列表"，按钮名与实际动作不符 |
| 4.12-3 | 登录（§4.12） | `AccountSwitcher` 传 `?mode=add` 但 Login 只读 `redirect`，两场景表现完全相同 |
| N4 | 全局导航外壳（§1.2） | 快捷键不可发现：`g+i` 跳「事件时间线」而非商品列表，面板行右侧只显示 path |
| N8 | 全局导航外壳（§1.2） | 无匹配菜单项时侧栏错误高亮「仪表盘」（`selectedKey` 兜底 `'/'`），向量页高亮「系统清理」 |
| N13 | 全局导航外壳（§1.2） | 桌面 30s 轮询不随 `document.hidden` 暂停（移动端却做了） |
| 2.2-10 | 任务管理（§2.2） | 「沉默」标签基于 `updated_at`（编辑也算更新），刚编辑的无命中任务显示"活跃" |
| 2.6-4 | 事件时间线（§2.6） | 行首 emoji 🛒/🟠/📌 与色点重复编码；分隔线硬编码 `#f0f0f0` 暗色不可见 |
| 3.2-3 | 评估规则（§3.2） | 阈值滑块无单位后缀（"件"/"天"仅藏在标签里）；「⏪」emoji 按钮不可主题化 |
| 3.7-4 | 客服配置（§3.7） | 用 `marginLeft:16` 手排 label+控件，无 Form 校验，与其他配置页脱节 |
| 4.12-4 | 登录（§4.12） | 登录页无主题切换入口，暗色下玻璃卡对比度不可控；无"返回控制台/跳过登录"出口 |
| 4.14-6 | 移动端（§4.14） | 深页（如 `/m/logs/`）无任何全局导航，只能点品牌回仪表盘再找网格 |
| N9 | 全局导航外壳（§1.2） | 面包屑只有「首页 > 当前页」两级无分组层，详情页无法回列表，部分页只剩「首页」 |
| N14 | 全局导航外壳（§1.2） | Header 右侧 7 个 28px 纯图标 + 一个纯色点表调度器状态；「帮助」「关于」构成四重入口 |
| N20 | 全局导航外壳（§1.2） | 断点三套并存（768/600/`breakpoint="lg"`），601–768px 死区正文仅约 450px |
| 2.4-9 | 评估明细（§2.4） | 筛选时机不统一：任务/品牌/状态自动重查，商品ID/评分/价格须点「查询」 |
| 4.9-2 | 帮助文档（§4.9） | 搜索只匹配 `title/intro` 却写"搜索章节…"，搜「权重 100」必现"未找到匹配的章节" |
| 4.14-2 | 移动端（§4.14） | 桌面有移动全无：内网穿透/向量库维护/菜单管理/帮助/时间线/告警抽屉/命令面板 |
| N18 | 全局导航外壳（§1.2） | 80px 竖排标签栏 7 字以上标题顶到 `maxHeight:80`；`maxSheets:5` 循环替换静默丢页 |

## 结构索引

### 报告一级/二级章节标题与覆盖页面

- `§0 评审范围、输入材料与取证方法`（0.1 菜单清单 / 0.2 取证方法 / 0.3 结论概览）——不产问题条目，给出 4 套文案表（registry 26、面包屑 29 键、命令面板 26 项、sheetRegistry 34 项）与 200 条总账。
- `§1 全局导航外壳（跨菜单，影响所有页面）`（1.1 现状 / 1.2 问题清单 23 条 / 1.3 优化建议）——覆盖侧边栏分组、Header 按钮组、Sheet 标签栏、命令面板、快捷键、今日告警抽屉、账号切换器、用户菜单、演练横幅、引导向导、断点、`App.tsx` 路由；编号 N1–N23。
- `§2 逐菜单评审 · 数据查看组`（80 条）——2.1 仪表盘 `/`；2.2 任务管理 `/tasks`+`/tasks/new`+`/tasks/:id`+`/tasks/:id/edit`；2.3 商品列表 `/items`；2.4 评估明细 `/evaluations`；2.5 抢单记录 `/orders`；2.6 事件时间线 `/timeline`；2.7 实时日志 `/logs`；2.8 错误日志 `/logs/errors`；2.9 通知中心 `/notifications`；2.10 价格行情 `/price-dashboard`；2.11 数据导出 `/export`；2.12 本组小结（无新条目）。
- `§3 逐菜单评审 · 配置管理组`（31 条）——3.1 价格策略 `/config/price`；3.2 评估规则 `/config/eval`；3.3 抢单策略 `/config/buyer`；3.4 搜索参数 `/config/search`；3.5 通知渠道 `/config/notifier`；3.6 AI 服务 `/config/ai`；3.7 客服配置 `/config/chatbot`；3.8 配置版本 `/config/version`；3.9 本组跨页共性小结（含 3 条：3.9-1/2/3）。
- `§4 逐菜单评审 · 系统维护与其他组`（66 条，14 个页面/层）——4.1 系统清理 `/maintenance`；4.2 数据库维护 `/maintenance/db`；4.3 向量数据库维护 `/maintenance/vector`（未注册）；4.4 批量采集 `/batch-refresh`；4.5 反爬登录管理 `/anticrawl`；4.6 内网穿透 `/maintenance/tunnel`；4.7 智能客服 `/chatbot`；4.8 关于 `/about`；4.9 帮助文档 `/help`；4.10 菜单管理 `/menu-admin`；4.11 确认抢单 `/confirm-buy`；4.12 登录 `/login`；4.13 新手引导 `/onboarding`；4.14 移动端 `/m/*`；4.15 本组小结（无新条目）。
- `§5 汇总优先级矩阵`——5.1 口径说明（优先级/成本/ID 规则/200 条总数）；5.2 排序矩阵（P0 53、P1 111、P2 36，另附"按菜单汇总"35 行）；5.3 快速赢面清单（P0 且成本 XS 共 21 条）；5.4 专题打包 T1–T6 + 排期建议。
- `§6 限制与未覆盖项`（8 条）。
- `§7 复核记录`（6 条）。

### 专题打包 T1–T6 成员编号（§5.4）

- T1 导航元数据单一事实源：`N1 N2 N3 N5 N6 N9 N23 2.3-1 2.4-4 4.3-1 4.7-2 4.9-4 4.10-5 4.11-5`（14 条；第 1 批 1 周）。
- T2 通知与告警模型统一：`N11 N12 N19 2.9-1 2.9-2 2.9-3 2.9-7`（7 条；第 2 批 2 周）。
- T3 确认范式与危险操作文案：`2.2-3 2.4-1 2.4-2 3.6-3 3.7-3 4.1-1 4.1-6 4.2-1 4.2-4 4.4-2 4.4-3 4.5-2 4.11-1 4.11-2`（14 条；第 2 批 2 周）。
- T4 失败态与任务收尾反馈：`N10 2.7-7 2.7-9 2.8-5 2.10-5 2.11-2 3.1-2 3.4-1 3.7-2 4.2-2 4.3-4 4.4-1 4.5-3 4.6-3`（14 条；第 3 批 3–4 周）。
- T5 SheetWorkspace 外壳可用性：`N7 N15 N16 N17 N18 N20 N21 N22 4.7-1 4.9-1 4.9-3`（11 条；第 1 批 1 周）。
- T6 统计口径限定语：`2.4-7 2.5-1 2.6-2 2.9-3 4.4-4`（5 条；第 3 批 3–4 周）。
- 交叉引用：§5.3 快速赢面 21 条＝P0 中成本 XS 的全部行（`2.2-1、2.3-2、2.3-4、2.4-2、2.4-3、2.7-2、2.7-3、2.9-2、2.11-1、3.5-1、3.9-1、4.1-2、4.5-2、4.8-1、4.10-1、4.10-4、N7、N12、N15、N16、N19`）。

### 「无显著缺陷」类声明

- 报告中**不存在**任何"某页面无显著缺陷/未发现问题"的声明：33 个页面/层 + 外壳 + 跨页共性均有条目，最少的页面也有 3 条（如 §3.2 评估规则、§3.4 搜索参数、§3.5 通知渠道、§3.8 配置版本、§4.8 关于、§3.9）。
- 与"无缺陷"最接近的定性正面表述：§3.5「信息架构是组内最佳」、§3.8「是本组防护意识最好的页面」、§4.2「是维护组防护最完整的页面」、§4.4「是维护组状态机最完整的页面」、§4.6「失败指引做得相当好」、§3.3「文案范式值得推广」。
- 「无 P0」页面共 9 个（据 §5.2 按菜单汇总 P0 列为 0）：价格行情、移动端、事件时间线、智能客服、帮助文档、新手引导、登录、评估规则、抢单策略。
- 明确的"未覆盖/未取证"声明：§6-2 弹窗抽屉内层未逐一步进（DiffPreviewModal、模板市场、接管三步 Modal 第 2/3 步、Cookie 更新弹窗、告警抽屉内三层列表）；§6-3 未做系统性 a11y 审计；§6-4 未量化性能、未覆盖 1920 宽屏与手机真机尺寸；§6-5 未做真实用户可用性测试；§6-6 移动端仅截图 8 页、其余 18 条 `/m/*` 路由未逐页取证；§6-7 后端契约仅在矛盾点校验；§0.2-1 唯一失败捕获点为 Header 铃铛告警抽屉（30s 超时未落盘），故 §1 抽屉内容只以代码为证。

### 移动端章节 / 控制台噪声取证 / 副作用声明

- 移动端章节：**有独立章节 §4.14「移动端（`/m/*`，26 条路由 / 5 个 Tab）」**，6 条问题（4×P1 + 2×P2，无 P0）；现状描述列出 5 Tab（仪表盘/任务/抢单/告警/客服，`TabBar.tsx:16-22`）+ 仪表盘两张网格卡共 16 项，真机截图 8 张（`mobile_dashboard.png` 等）；条目内容：有路由无入口（`/m/items/` 等 4 个）、桌面有移动全无清单、KPI 指标贴错标签、硬编码色值与桌面橙冲突、命名漂移（Tab「告警」实为通知中心）、深页无全局导航。§6-6 声明其余 18 条路由未逐页取证；N13 以移动端 `MobileHeader.tsx:40-43` 的 `document.hidden` 处理为桌面反例对照；N20 以 `useMobileDetect.ts:11` 的 `<=600` 断点为死区成因之一。
- 控制台噪声取证：**有**。§0.2-4 记：31 个路由页面整页取证过程中 `console.error` / `pageerror` 累计 0 条（无 JS 运行时报错），并声明命令面板、窄屏与移动端共 12 个捕获点未单独采集控制台数据；§7-6 收尾复算把原"43 个页面加载 0 报错"表述修正为"仅在 31 个路由页面采集且累计 0 条"。
- 副作用声明：**有**。§6-8「取证副作用（须知悉）」：以 `--no-with-scheduler` 纯查看模式启动（§0.2-1 同述），未启动调度器与浏览器实例，不会触发采集或抢单；**但**后端启动过程自动尝试内网穿透失败，并向已配置的通知渠道**真实推送了 1 条 `system.error` 通知（1/1 渠道成功）**；截图目录内含配置页明文密钥回显，验收后整目录删除不入库（`.gitignore` 已覆盖 `scripts/.screenshots/`），相关密钥建议按环境策略轮换。

### 计数一致性核对

- 报告声明（§0.3 / §5.1）：P0 53、P1 111、P2 36，合计 200；分组 23（外壳）+80（数据查看）+31（配置）+66（维护与其他）=200；成本 XS 84 / S 84 / M 32；P0 且成本 XS 21 条、P0 且成本 ≤S 41 条。
- §5.2 矩阵实测行数：P0 块 53 行、P1 块 111 行、P2 块 36 行 = 200 行；成本实测 XS 21+40+23=84、S 20+55+9=84、M 12+16+4=32；P0 中 XS 21 条与 §5.3 名单完全一致，XS+S=41 与 §0.3 一致。
- 正文条目实测：§1.2 23 条、§2.1–§2.11 依次 7/10/6/10/6/5/9/7/7/7/6=80、§3.1–§3.9 依次 5/3/3/3/3/4/4/3/3=31、§4.1–§4.14 依次 6/5/4/5/6/5/4/3/4/5/5/4/4/6=66，总 200，矩阵每个编号均能在正文找到唯一对应条目，无缺失、无多余。§5.2「按菜单汇总」35 行合计亦为 200，且各页 P0/P1/P2 与矩阵逐行数一致。
- **本次实际提取行数：P0 53、P1 111、P2 36，合计 200 —— 与报告声明完全一致，无抽样。**
- 提取过程中发现的原报告内部不一致（均属交叉引用/归类口径，不影响 200 条总数）：
  1. §1.3 末尾"优先级：P0（1、7、12、15、16、19…）"只列 6 条，而 §5.2/§7-4 给导航外壳层 7 条 P0（多计 N11）。
  2. §2.9-2 正文建议写"改跳 `/notifications`（与 **N11** 同批）"，§5.2 矩阵同一行写成"（与 **N19** 同批）"，交叉引用不一致。
  3. §2.12 小结称"当前页数据被当成全量呈现"这一类"重复出现 **4** 次"，§5.4 T6 却列 **5** 个成员并写"重复出现 5 次"（多出的 2.9-3 为已读计数问题）。
  4. 页面归类冲突：§2 引言称"data_view 的 9 项 + 概览仪表盘 + 另含 2 个未注册数据页（数据导出、价格行情）"＝12 页，但 §2 实际只有 11 个小节且 §2.12 自陈"共 11 个页面"；`config/menu_registry.yaml` 实测 `/price-dashboard` 属 data_view 第 9 项、`/export` 属 other 组（与 §0.1 line 15/28 一致），而 §2.10/§2.11 小节标题把两者标为"未注册菜单"，与 §0.1 的"有路由但未注册" 6 页清单相互矛盾。
  5. §7-1 称复核范围为"导航外壳 23 条 + A/C/D/E 四组 21 条 P0 结论"，23+21=44 与矩阵 P0 总数 53（外壳 P0 仅 7 条、非外壳 P0 实为 46 条）口径不吻合，未说明"21 条"的取数口径。
  6. §0.3 称 P0 中"含 11 条**功能性缺陷**"，但全文（正文与矩阵）均未逐条标注哪 11 条属功能性缺陷，无法机械核对。
  7. §4 引言"maintenance 5 项 + 向量数据库维护（未注册）+ other 3 项，以及 6 个未注册辅助页与移动端"中，向量页在"6 个未注册辅助页"里被重复计一次；同组实际条目为 4.1–4.14 共 14 个页面/层（与 §4.15 一致），而 other 组的 `/export` 已被移到 §2.11 评审。
  8. 证据密度不均：正文有 10 条（3.5-3、3.8-3、3.9-1、3.9-2、3.9-3、4.1-6、4.9-4、4.10-5、4.11-3、4.11-5，多为跨页共性或"不在 registry"类条目）未给 `文件:行号` 代码证据，与 §0.2-2"每条问题标注 `文件:行号`"、§0.3"全部带代码证据"的表述不完全一致。
