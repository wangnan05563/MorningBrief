## 补充｜第二路独立评审（源码走查）与已交付报告的交叉校验

> 本节由**并行的第二路评审**追加，不改动上方原回传内容。
> 第二路线：5 个并行切片做**纯源码走查**（未启动应用、未改动任何 xianyu 文件），产出 289 条（高 64 / 中 145 / 低 80）。
> 第二路交付物：`D:\code\otherProjects\20_News\_validate\ux_t02324\T02324_ux_review.md`（217,864 B / 1,220 行，含逐菜单表 + §6 四处菜单定义源完整漂移对照表 + §7 汇总优先级矩阵）。
> 比对基准：`17_xianyu/docs/requirements/2026-10-17-逐菜单UX评审与优化建议.md`（commit `28909370` + `58f42d9c`，200 条 / P0 53）。

### 一、两路重合度（结论一致性）

| 口径 | 数值 |
|---|---|
| 我的 64 条高 → 他报已列为 P0 | **33 条**（逐条编号可对应） |
| 我的 64 条高 → 他报列为 P1/P2（优先级分歧） | **11 条** |
| 我的 64 条高 → 他报无对应条目 | **20 条**（下表二，其中 13 条已代码复验） |
| 他报 53 条 P0 → 我的走查未覆盖 | **13 条**（下表三） |

两路对**六大系统性根因**的判断一致：静默失败、脏检查失效、确认范式三套并存、深链不消费、引导文案漂移、菜单多源漂移。他报的 §3.9/§4.14/N 系列与我的 §3 跨页共性/§4.1/§6 壳层节互为独立复现，可视为对同一批结论的双重确认。

### 二、仅第二路发现的缺陷（已逐条回读源码复验）

按严重性排序，★ = 建议直接提级到快速赢面批（T02337）。

| # | 菜单 | 缺陷（证据为本次复验所得） | 他报状态 |
|---|---|---|---|
| ★P1 | 菜单管理 | **「保存」必然 422**：前端 `menuApi.update` PUT `{items:[{menu_key,…}]}`（`frontend/src/api/menu.ts:65-66`），后端 `MenuUpdateBody` 要求 `{menus:[{key…}]}` 且 `key` 必填（`backend/.../web/routes/api_menu.py:28-39`）。字段名与包装名双双不匹配 → 该页所有改动都提交不落库 | 无对应条目（他报 §6-7 自陈"后端契约仅在矛盾点校验"，此为漏检成因） |
| ★P2 | 智能客服 | 后端下发 `faq_confirm`/`intent`（`modules/chatbot/orchestrator.py:44,49` 定义，`:169`、`:243` 实际 yield），前端 `SSE_EVENT_HANDLERS` 只有 token/sources/tool_call/error/escalate/done（`pages/Chatbot/index.tsx:170-177`）→ 模糊命中分支 `return` 前只发 `faq_confirm`，界面**不渲染任何回复** | 无对应条目 |
| ★H2 | 抢单策略 | 「安全护栏」写死承诺 `auto_buy_score ≥ 80 才启用 auto 模式`（`pages/Config/BuyerStrategy.tsx:361`），而阈值控件 `min={0}`（`:150`）且后端无 80 下限 → 设 30 就按 30 分自动拍下（真金风险） | 无对应条目 |
| ★G1 | 实时日志 | 全文件无 `scrollTop/scrollHeight/autoScroll`（`pages/Logs/Logs.tsx` 内联 `maxHeight:500` 固定容器），而 `guides/menuGuides.ts:71` 承诺"自动滚动" | 无对应条目 |
| B5 | 内网穿透 | `handleSaveConfig` 以 `tunnel_name: config?.tunnel_name || ''` 等 **5 个命名隧道字段**回写，`loadConfig` 失败后点保存即以空串覆盖已持久化配置（`pages/Maintenance/Tunnel.tsx:505-524`）；仅 `cpolar_authtoken` 有"空即不改"保护，反证其余字段是遗漏 | 4.6-2 为相邻但不同症状（脏字段被忽略） |
| C3 | 登录 | 会话 Cookie 值用明文 `<Input>` 承载（`pages/Login/index.tsx:459-468`，无 `type=password`、无掩码开关），值常驻 DOM，截图/肩窥即泄露 | §6-2 自陈"Cookie 更新弹窗未逐步进" |
| A1 | 仪表盘 | 首屏 `statsApi.overview()`/`priceApi.histogram()`/两个 `trend()` 全部 `.catch(() => null)`（`pages/Dashboard/index.tsx:80,83,99,100`）→ 后端不可用时渲染成"全 0 正常态"，无失败提示与重试 | 无对应条目（N10 只覆盖 `/api/menu` 的 error 丢弃） |
| A10 | 客服配置 | `onChange={(v) => v && updateConfig(…)}` 共 11 处（`pages/Chatbot/Config.tsx:214,223,267,285,320,330,339,372,448,542,551`）：值为 0 或清空时 falsy → **静默不发送**，用户改不动也没有任何反馈 | 无对应条目 |
| A11 | 数据库维护 | 主键单元格可编辑但后端 `continue` 跳过（`web/routes/api_db_admin.py:649-651`），前端仍弹「已更新」 | 4.2-3 为空串场景，非主键 |
| A15 | 智能客服 | 流一开始就把全部 pending 消息标「已送达 ✓」（`pages/Chatbot/index.tsx:109-112,202-205`），收到 `error` 不回滚该标记 | 无对应条目 |
| B4 | 批量采集 | 「清空全部」= `days==0` 跨账号 `DELETE FROM BatchRefreshHistoryRow`（`api_batch_refresh.py:386-392`），UI 只有 Popconfirm 且不点名"其它账号的历史也删" | 4.4-3 只指出不给条数 |
| B6 | 菜单管理 | `GET /api/menu` 直接过滤 `visible=True`（`services/menu_manager.py:203`）→ 被隐藏的项在管理页也消失，无法单独恢复，只能"重置全部" | 4.10-5 是"本页自身不在 registry" |
| B7 | 登录 | 「自动关闭 Edge/Chrome 并导入」零确认即结束浏览器进程（`pages/Login/index.tsx:601-623,1042-1065`），不提示会丢其它标签页未提交内容 | §6-2 自陈弹窗未逐步进 |
| D6 | 全局壳层 | 偏好项「最小化保留页面状态」是**假承诺**：`SheetWorkspace` 只渲染 activeSheet 且 `SheetContent.tsx:33-56` 以 `key={sheet.id}` 重挂载 → 切页签即丢筛选/分页/未保存表单 | 3.9-2 相邻（未保存改动跨页污染）判 P1 |
| E4 | 移动端/确认抢单 | 桌面确认页跳转移动端一律 `navigate('/m/')`，而 `mobile/routes.tsx` 全表**无 `confirm-buy` 路由** → 手机通知里的确认深链被丢回移动首页、参数全清 | 4.14-1/2 方向相反（有路由无入口） |
| N1 | 抢单记录 | 失败订单看不到 `error`/`screenshot`（字段已在 `api/types.ts:581-582`，不在列定义 `Orders.tsx:508-569`），行内唯一动作是删除 | 无对应条目 |
| N2 | 事件时间线 | 进入页面即从通知订阅**静默改写** `eventTypeFilter`（`pages/Timeline/index.tsx:37-65`），异常只 `console.warn`（`:45-48`）→ 列表"少一半"无解释 | 无对应条目 |
| L1 | 通知渠道 | `serverchan`/`pushplus` 默认 `enabled: true`（`NotifierChannels/constants.ts:37,48,61`）而凭据为空时无任何角标/提示，空凭据只在点"发送测试"时才报"请先填写"（`index.tsx:166`）→ 用户以为已配好，实际静默丢通知 | 无对应条目 |
| I3 | 智能客服 | 撤回入口条件 `canRecall && !msg.status` 永不成立（`pages/Chatbot/index.tsx:1514`），而帮助中心两处承诺"2 分钟内可撤回"（`HelpCenterModal.tsx:18`、`pages/Help/index.tsx:654`） | 全文无"撤回"条目 |
| A4 | 商品中心 | 卡片视图删除图标恒可点（`ItemList.tsx:1146` 仅变色不禁用），落入 `if (!selectedTask || !linkId) return`（`:642-643`）静默无事；表格视图则 `disabled`（`:804`）→ 同操作双视图两套标准 | 2.3-6 只述表格侧置灰无说明 |

（其余 4 条为「部分重叠/口径更严」：B2 接管 Modal 打开即重置 `phase='confirm'` 可重复 `POST /takeover`、C2 后端两份敏感清单 `_SHARE_REDACT_PATHS`/`SENSITIVE_KEYS`（`api_config.py:300-313,697-702`）同样漏 ntfy 三键、B1 三套确认他报判 P2、A6 价格行情 4 个 hook 吞错他报判 P1。）

### 三、仅原报告发现的缺陷（第二路源码走查的盲区，已抽验 2 条为真）

- **2.11-1** `exportApi.buildUrl` 返回 `/api/export/<dataset>` **未加 `API_BASE`**（`api/export.ts:56`），`download` 又用 `location.href` 直跳（`:60-62`）——已复验为真；这条比我记录的 A16（无条件报"正在导出"）更根本。
- **4.5-1** 「可用策略」5 个 Tag 纯展示不可点，`anticrawlApi.setStrategy`（`api/anticrawl.ts:156`）**全仓零调用**——已复验为真（调用点只有同名局部 setter）。
- 其余 11 条属"必须跑起来才看得见"或跨字段语义类：2.4-2 未选任务对全库静默重算、2.7-2 有错仍显示「ERROR 0」、2.7-3 停止/暂停复用同一 `PauseCircleOutlined`、2.8-1 错误日志无聚合去重（真机 1,869 条多为同文重复）、4.1-2 dry-run 显示绿色「删除 0 条」、4.2-1 导入确认框写"请选择冲突处理"而 `mode` 恒 `'insert'`、4.2-2 导出忽略搜索条件、4.4-1 `running→idle` 无完成汇总、4.6-2 `handleStart` 忽略脏字段、4.10-1 保存后不失效菜单缓存、3.9-1 8 个配置页生效时机一律不明。
- 结论：**两路互补**——他报有真机截图（73 张 PNG）与运行时观测，我这条路对**前后端契约、字段级 falsy/兜底、跨页一致性**更敏感。

### 四、需要修正的交叉冲突（诚实记录）

`2.7-2`（他报 P0）与我的 `G3`（我判高）是**同一根因的两个症状**：后端 `events.level` 存小写缩写 `err`/`warn`/`info`（`api_logs.py:177-180` 注释 + `api_db_admin.py:620,714` 等实写值），前端两处都按大写全称查表——
- 行着色：`constants/logLevels.ts:3-8` 键为 `ERROR/WARNING/WARN/INFO/DEBUG`，`Logs.tsx:279,315` 用原始 `item.level` 查表 → ERROR 行恒灰（我的 G3，成立）；
- 级别分布：`Logs.tsx:131-141` 先 `toUpperCase()` 再查 `{ERROR,WARNING,INFO,DEBUG}`，`'err'→'ERR'` 不在键内 → 有错也显示「ERROR 0」（他报 2.7-2，成立）。

**我原先在实时日志节写的"同页直方图先 toUpperCase 恰好正常，反证是缺陷"这句推论是错的**，已据他报更正：直方图同样失效，且这条比我原来的推论更严重。修法合并为一条：在边界处统一归一化（后端返回前或前端 `normalizeLevel()`），并补 `err→ERROR`、`warn→WARNING` 别名表。

### 五、计数与口径差异（不影响结论）

- 他报按"优化点"计 200 条（P0 53/P1 111/P2 36），我按"可指认问题"计 289 条（高 64/中 145/低 80）——差在我把同一页面的多个字段级缺陷分条计（例如客服配置 `v && updateConfig` 我按 11 处出现点计 1 条但逐处列行号），以及我把壳层单列为 20 条。
- 他报 §7 自陈的取证盲区恰好是本次增量所在：§6-2 弹窗/抽屉内层未逐步进（→ C3、B7、A15 漏检）、§6-7 后端契约仅在矛盾点校验（→ P1、P2 漏检）。
- 两路均声明"注册菜单 26 项 + registry 外可达 6 页"，菜单口径一致。

### 六、建议（已建派生单 T02352）

1. 以他报为主文档（有真机取证），把上表二的 20 条并入其批次：契约类 2 条新建"后端契约全量核对"批，静默/文案类 12 条并入 T02337（P0∩XS），危害类 6 条并入 T02340（确认与危险文案）。已建派生单 T02352。
2. 排期上把 **P1（菜单保存恒 422）** 插到最前：它不是体验优化而是功能不可用，成本极低（改 1 个字段名 + 1 条集成测试断言），且能顺带暴露同类契约漂移。
3. `G3/2.7-2` 合并为一条修复，并在 §4.1 的"级别"处理上加一句边界归一化规范，避免第三处（导出/告警文案）再犯。
4. 本轮两路评审合计 489 条（去重后约 450），建议不再重复投入第三条走查路；后续以"修复 → 他报编号 + 我表二编号双引用"的验收单号制推进。
