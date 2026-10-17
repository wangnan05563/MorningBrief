# xianyu 逐菜单 UX 评审与优化建议（T02324）

评审日期：2026-10-17 ｜ 评审对象：`D:\code\otherProjects\17_xianyu`（前端 React18 + AntD5 + Vite，后端 FastAPI）
评审方式：5 个并行评审切片（按一级分组切分）+ 关键结论人工复核

## 0. 评审口径（先读这一节，否则会误读后面的结论）

### 0.1 覆盖范围

| 类别 | 数量 | 说明 |
|---|---|---|
| 一级菜单 | **26** | `config/menu_registry.yaml` 全部条目（overview 1 / data_view 9 / config 8 / maintenance 5 / other 3） |
| registry 之外、用户实际可到达的界面 | **6** | `/help`、`/login`、`/onboarding`、`/confirm-buy`、`/menu-admin`、`/maintenance/vector` |
| 全局壳层 | 1 | 侧栏 / 顶栏 / 页签工作区 / 命令面板 / 告警抽屉 / 键盘助记 |
| 移动端 | 1 | `/m/*` 路径体系与桌面端映射口径（只在壳层节评审，不重复评审每个移动页） |
| 二级/三级界面 | 随所属菜单 | 子页签、抽屉、弹窗、向导步骤、二次确认、空/加载/错误态 |

**结论规模**：289 条可指认问题（高 **64** / 中 **145** / 低 **80**）。其中 2 条在「菜单管理」与「全局壳层」两节各记一次（同一根因），已按去重后计数。

### 0.2 方法与素材限制

任务要求的输入素材（界面截图、可交互原型）**未提供**，因此本轮为**源码走查 + 前后端契约交叉核对**：每条结论落到 `文件:行号`，能由代码确定的问题直接判定；只有运行时才能确认的现象一律标注「**需实测确认**」，不当作已证实缺陷。评审期间未启动应用、未改动任何 xianyu 文件。

**同任务已有另一路交付**：本报告与 `17_xianyu/docs/requirements/2026-10-17-逐菜单UX评审与优化建议.md`（commit `28909370`，200 条 / P0 53，含 73 张真机截图取证）是同一任务下**并行完成的两路独立评审**，方法不同（源码走查 vs 真机渲染）、计数口径不同（见 §8.5）。§8 给出逐条交叉校验：两路重合 44 条、本路独有 20 条（含 2 条前后端契约缺陷）、他报独有 13 条、本路 1 处判断错误已更正。排期请以他报为主文档，§8.2 作为增量并入。

三条必要前提（若按常规 SPA 直觉判断会得出错误结论）：

1. `frontend/src/App.tsx` 的路由表**已失效**——`MainLayout` 不渲染 `<Outlet/>`，内容区由 `components/SheetWorkspace` 接管，页面组件真正注册处是 `components/SheetWorkspace/sheetRegistry.tsx`（33 条）。
2. SPA 挂在 `basename="/xianyu"` 下（`frontend/src/main.tsx:86`）——任何原生 `<a href="/xxx">` 都会跳出应用。
3. 菜单存在**三处定义源**且彼此漂移：`config/menu_registry.yaml`（后端 26 项）、`sheetRegistry.tsx` 的 `title`、`MainLayout.tsx` 的 `ROUTE_LABELS`(:55-85) 与 `COMMAND_ITEMS`(:88-115)。完整对照见 §6 末尾漂移表。

### 0.3 优先级判定口径

高 = 数据/凭证不可逆损失、破坏性操作可被误触发、**点了没反应或提示与实际结果不符**、跳出 SPA 的坏链、错误被静默吞掉导致用户以为成功。
中 = 明显增加完成任务的步数、状态缺失导致误判、术语或文案混乱导致误解。
低 = 视觉与文案打磨。

每条问题在正文中标注它更刺痛「**首次使用**」还是「**高频操作**」。成本按改动面估计：低=单文件文案/props；中=需前后端协同或抽公共组件；高=涉及架构（如页签 keep-alive）。

### 0.4 结论摘要：六个系统性根因

后面的 289 条问题不是 289 个孤立缺陷，绝大多数落在 6 类可一次性治理的模式上：

| # | 根因 | 典型证据 | 波及面 |
|---|---|---|---|
| R1 | **失败被静默吞掉**：`.catch(() => null)` / `catch {}` / 只 `console.error`，随后渲染成「空数据」甚至报成功 | `pages/Dashboard/index.tsx:80,83,99,100`、`pages/AntiCrawl/index.tsx:227-276`、`pages/PriceDashboard/hooks/use*.ts`、`components/layout/MainLayout.tsx:180-182`、`hooks/useEvalBatch.ts:101,109` | ≥ 9 个菜单 |
| R2 | **脏检查形同虚设**：编辑态放本地 `useState`，`hasChanges()` 恒 false → 「重置」永久禁用 + 切页签即丢改动，且全组无未保存离开保护 | `pages/Config/PriceStrategy.tsx:235-379` + `:193`、`pages/Config/SearchConfig.tsx:65-77` + `:184`、`components/SheetWorkspace/SheetContent.tsx:33-56` | 配置组 8 页 + 维护组 2 页 |
| R3 | **破坏性操作确认口径三套并存**：原生 `confirm()` / `Popconfirm` / 输入 `CONFIRM_DELETE`，同级危险动作强度相差两个量级 | `pages/Maintenance/Cleanup.tsx:88`、`pages/Tasks/TaskList.tsx:84-97`、`pages/Maintenance/DatabaseAdmin.tsx:394-404`、`pages/Config/AIConfig/index.tsx:94-97` | 全仓 |
| R4 | **深链与参数不消费**：告警/通知发出的 `/orders?ref=` 从不读取，跳转用原生 `<a>` 或 `navigate` 绕过页签模型 | `pages/Orders/Orders.tsx:1-18`、`pages/Dashboard/components/AlertRadar.tsx:58,76`、`pages/Notifications/index.tsx:283`、`guides/GuideController.tsx:167,187` | ≥ 6 个菜单 |
| R5 | **文案/引导与实现漂移**：`menuGuides.ts`、`pages/Help`、页内说明描述不存在的能力或错误命令，且无任何一致性断言 | `pages/Onboarding/index.tsx:103,108,220,225`（`qr-login`/`worker` 两条命令 CLI 均不存在）、`guides/menuGuides.ts:71,101,113,119,125`、`pages/Evaluations/index.tsx:604` | 全站 |
| R6 | **单一事实源名不副实**：菜单 label/图标/分组三处各自维护，`category`/`group`/`group_name` 同一条数据三种叫法，接口契约前后端不匹配 | `api/menu.ts:66` vs `routes/api_menu.py:28-39`、`services/menu_manager.py:203`、`config/menu_registry.yaml` vs `sheetRegistry.tsx` vs `MainLayout.tsx` | 导航层 + 菜单管理页 |

**修复顺序建议**（理由见 §7.2）：先修「静默失败」三件（R1 壳层两条 + 侧栏空白），再修 5 个不可逆风险点（浏览器数据清理、Cookie 明文、隧道凭证清空、真金下单无确认、跨账号清空），然后才是文案/图标/布局打磨。

---

## 目录

- §0 评审口径（含 6 个系统性根因）
- §1 总览与数据查看（一）：仪表盘 / 任务管理 / 商品中心 / 卖家评估
- §2 数据查看（二）：抢单记录 / 事件时间线 / 实时日志 / 错误日志 / 通知中心 / 价格行情
- §3 配置管理：8 页
- §4 系统维护与反爬：7 页（含 §4.1 组内共性）
- §5 其他组与体系外页面：智能客服 / 数据导出 / 关于 / 帮助文档 / 登录 / 新手引导 / 确认抢单
- §6 全局壳层与共性问题（含四处菜单定义源完整漂移对照表）
- §7 汇总优先级矩阵（7.1 高危 64 条清单 / 7.2 排期批次 / 7.3 逐菜单一览 / 7.4 中低风险主题分布 / 7.5 无显著缺陷对象）
- §8 与另一路已交付报告的交叉校验（含本路独有 20 条、他报独有 13 条、1 处我方判断更正；派生单 T02352）

---

## 1. 总览与数据查看（一）

### 菜单：总览 > 仪表盘

**现状描述**：单页总览，自上而下为欢迎/调度器 Alert、4 张统计卡、KPI 星级卡、事件流、价格直方图+AI 分析、预警雷达、11 张"可视化配置入口"卡片。数据来自 5 个并行 API + SSE 事件流；卡片点击通过原生 `navigate` 跳转，而侧边栏走 SheetWorkspace 页签模型，两套导航并存。

**问题与建议**：

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 5 反馈与状态 | 首屏 5 个接口全部 `.catch(() => null)` 兜底（`frontend/src/pages/Dashboard/index.tsx:80,83,99,100`），后端不可用时页面渲染成"全 0 数据"的静默空态，无任何失败提示或重试按钮，首次用户会误判"系统正常但没数据" | 任一请求失败时置 error 态，顶部 Alert「数据加载失败」+ 重试按钮 | 低 | 高 |
| 2 | 1 信息架构 | 趋势大图 TrendModal 不可达：`trendOpen` 仅在 58 行声明、393 行被置 false（`index.tsx:58,393`），全文件 grep 无任何 `setTrendOpen(true)`，198-201 的数据加载逻辑与 387-395 的 Modal 成为死功能，用户想看 7/30/90 天趋势无入口 | 在 KPI 卡或事件流卡标题挂"查看趋势"按钮打开 Modal；确属废弃则删除组件 | 低 | 中 |
| 3 | 2 操作流程 | "调度器未运行"警告（`index.tsx:250-258`）描述写"请启动调度器"却没有任何操作按钮/跳转，是死胡同提示；对照同页欢迎 Alert（229-247）就带"创建任务/查看引导"两个动作按钮 | Alert 的 action 区加「去启动」按钮（调控制接口或跳系统维护页），形成"提示→行动"闭环 | 低 | 高 |
| 4 | 1 信息架构 | 3 张订单统计卡点击都跳未过滤的抢单记录页（`components/StatCardsSection.tsx:57,70,83` 均 `onNavigate('/orders')`），且 `onNavigate={navigate}`（`index.tsx:261`）为原生路由，绕过后端菜单驱动的开页签模型，与侧边栏行为不一致 | 跳转时携带状态预筛选（如"待确认"），并统一改走 openSheetWithNotification | 低 | 中 |
| 5 | 3 视觉与布局 | 预警雷达"评估异常 score<0.5"标题（`components/AlertRadar.tsx:86`）用 0-1 分制，列表条目 `score {e.score}`（95 行）又显示原始分值；全站评估分为 0-100 分制（如评估页 Slider），同屏两套单位，用户无法判断阈值含义 | 统一 0-100 分制，标题改「评估异常 score<50」 | 低 | 中 |
| 6 | 6 一致性与规范 | 预警雷达订单链接用原生 `<a href={'/orders?ref='+o.id}>`（`AlertRadar.tsx:58,76`），点击整站刷新、已开页签全部丢失；事件流卡 Badge 显示 `events.length` 全量计数（`components/EventStreamSection.tsx:32`）但列表只渲染 `slice(0, 50)`（42 行），超 50 条时角标与可见条数不符 | 改用应用内跳转/开页签；Badge 封顶显示 `50+` 或注明"最多展示 50 条" | 低 | 中 |
| 7 | 4 文案与提示 | AI 分析结果的 Alert 级别靠中文子串嗅探判定（`components/PriceHistogramCard.tsx:255`：`includes('未配置')||includes('失败')||includes('错误')` 才 warning），正常分析文本一旦含这些词即被误标为警告色，反之异常文案不含词则伪装成 success | 让后端返回 `{status, text}` 结构化字段，前端按 status 定级别 | 低 | 中 |
| 8 | 1 信息架构 | 底部"可视化配置入口"11 张卡片（`index.tsx:304-384`，如 380 行"策略与会话监控"卡）与左侧边栏菜单完全重复且同样走原生 navigate，首次用户面对两套导航不知道哪个是"正门" | 精简为 3-4 个高频入口或直接删除，统一依赖侧边栏+命令面板 | 低 | 低 |

**三源一致性**：dashboard 三源一致——`config/menu_registry.yaml:9-15`（label 仪表盘、path `/`、DashboardOutlined、overview）↔ `MainLayout.tsx:56,89`（'/': '仪表盘'、命令面板同图标）↔ `sheetRegistry.tsx:52`（'/' 仪表盘同图标）。但两处越界：欢迎 Alert 的"查看引导"跳 `/onboarding`（`index.tsx:241`），该路由在三个事实源均无登记且渲染于 MainLayout 之外（`frontend/src/App.tsx:92`），属体系外页面，点击后脱离页签工作区（已归入问题 6/8 相关的导航模型不一致）。

---

### 菜单：数据查看 > 任务管理（含子视图 新建任务 / 任务详情 / 编辑任务）

**现状描述**：列表页含表格/卡片双视图、状态筛选、全部启动、模板库抽屉；点击任务名进编辑页。详情为单页 Descriptions+四页签（含评估记录上限 50 条）；新建/编辑是 6 步向导，支持 AI 解析、模板与克隆预填、草稿自动保存。行内控制（启动/停止/删除）用自定义二次确认。

**问题与建议**：

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 5 反馈与状态 | 关联商品删除静默失效：`linkColumns` 的 useMemo 依赖为空数组（`frontend/src/pages/Tasks/TaskList.tsx:653,730`），闭包永久捕获首帧的 `handleRemoveLink`（574 行），其 `if (!linkTaskId) return`（575 行）取到的是初始空值——点击删除图标（724 行）既不发请求也无任何提示 | 依赖数组补 `[linkTaskId, loadLinks]` 或改 ref 方案；失败时给出 message | 低 | 高 |
| 2 | 4 文案与提示 | "全部启动"按钮（`TaskList.tsx:906-916`）与确认框标题"确认启动所有任务？"（624 行）宣称"所有"，实际只作用于当前页 `tasks.filter(t => t.status !== 'running')`（612 行），分页场景下用户以为全部已启动 | 文案改「启动本页 N 个未运行任务」，或由后端提供全量启动接口 | 低 | 高 |
| 3 | 6 一致性与规范 | 危险操作确认三套标准：任务停止/删除走行内 armConfirm 且 5 秒后**无任何提示地自动撤销**（`TaskList.tsx:84-97`，用户回来直接点第二下会以为没反应）；私有模板删除单击即删（1432-1439 →335-338 无确认）；任务详情页停止单击立即执行（`TaskDetail.tsx:453`） | 统一 Popconfirm（带倒计时或过期提示）；模板删除至少加确认 | 中 | 高 |
| 4 | 4 文案与提示 | 详情页直接渲染英文枚举：状态 `<Tag>{task.status}</Tag>`（`TaskDetail.tsx:460`）、模式 `{task.mode}`（462）、风险 `{lvl}`（366），成功提示 `操作成功: ${action}`（340 行显示 restart 等代码）；而列表页已有中文映射 `statusLabels`（`TaskList.tsx:25-30`），同产品双标，首次用户无法解读 | 复用列表页映射渲染中文，action 也走 label 映射 | 低 | 中 |
| 5 | 1 信息架构 | 状态筛选下拉只有 运行中/已暂停/已停止 三项（`TaskList.tsx:941-945`），但系统存在 deleted 状态且有中文标签"已删除"（29 行）——软删任务后无法找回、也无法按状态审计 | 筛选选项补 deleted（默认隐藏列表亦含删除态时可过滤） | 低 | 中 |
| 6 | 2 操作流程 | 详情评估记录页签硬上限 50 条（`TaskDetail.tsx:207` `limit: 50`），标题却显示"评估记录 (50)"（545 行）让人误以为总共只有 50 条，页内无翻页也无跳转评估页的深链 | 页签加「查看全部评估」链接跳 /evaluations?task_id=…，标题改「评估记录（最近 50 条）」 | 低 | 中 |
| 7 | 2 操作流程 | 编辑向导校验后置：6 步（`TaskEditor.tsx:414-421`）仅在第 0 步查关键词非空（423-429 `if (current === 0 && !formData.keyword)`），后续步骤离开时不校验，错误到最终提交才暴露；且带 AI/模板/克隆预填进入时，已有草稿被**静默丢弃**（191-198 行仅在有 prefill 时跳过恢复，无提示），用户可能覆盖未保存的心血 | 每步离开前做本步必填校验；prefill 与草稿冲突时 Modal 询问用哪个 | 中 | 中 |
| 8 | 5 反馈与状态 | 列表加载对每个任务串行/并行补一次 `taskLinkApi.count`（`TaskList.tsx:213-222`，216 行），N+1 请求随任务数线性增长，任务多时首屏明显变慢；批量操作失败统一 `message.error('操作失败'/'批量操作失败')`（132,383,476 行）不展示后端真实原因 | 列表接口随带 count 字段；错误统一提取 detail 展示 | 中 | 中 |

**三源一致性**：`/tasks` 三源一致（`menu_registry.yaml:18-24` 任务管理/UnorderedListOutlined/data_view ↔ `MainLayout.tsx:57,90` ↔ `sheetRegistry.tsx:53`）。差异在子视图：新建/详情/编辑三个标题只存在于 `sheetRegistry.tsx:54-56`，`MainLayout.tsx:58` 的 ROUTE_LABELS 仅有 `/tasks/new`，`/tasks/:id`、`/tasks/:id/edit` 无对应标签（面包屑靠前缀回退到"任务管理"），菜单注册表也无子级条目——层级信息只在页签层存在，group/图标三源无冲突。

---

### 菜单：数据查看 > 商品中心 (/items，前端称"商品列表")

**现状描述**：以"任务选择器 + DB 历史 / 实时搜索双模式"组织，工具栏一行约 12 个筛选与视图控件，表格/卡片双视图，行展开看详情，支持列配置持久化与 CSV 导出。实时模式数据与 DB 数据合并展示（`_isLive` 标记）。

**问题与建议**：

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 6 一致性与规范 | 登录态失效横幅的"重新登录"按钮实际跳转 `/?redirect=/items`（`frontend/src/pages/Items/ItemList.tsx:826-831`，829 行），即回到仪表盘——仪表盘上并没有任何登录入口，点击后横幅原地消失、问题未解；同产品 `pages/Evaluations/hooks/useEvalBatch.ts:36` 的同类错误又指引去「Cookie 注入」页面，两套指引互相矛盾 | 统一指向真实登录页（sheetRegistry:76 的 /anticrawl 反爬登录管理），文案与指引一致 | 低 | 高 |
| 2 | 5 反馈与状态 | 实时搜索结果 `link_id=0`（641 行注释），而表格与卡片都以 `link_id` 作 key：`rowKey="link_id"`（1052）、卡片 `key={item.link_id}`（1088）——一屏实时结果产生大量重复 key，React 行状态（选中/展开/动画）错乱并刷控制台警告 | rowKey 改函数式 `link_id || ('live-'+item_id+index)` | 低 | 高 |
| 3 | 6 一致性与规范 | 删除按钮双标：表格视图对不可删行 `disabled={!record.link_id || liveMode}`（804），卡片视图删除图标恒可点（1146 仅变色不禁用），点击落入 `handleDelete` 的 `if (!selectedTask || !linkId) return`（642-643）静默无事发生，用户以为"点了没反应"是卡顿 | 卡片视图同样 disabled + tip 说明原因 | 低 | 高 |
| 4 | 6 一致性与规范 | 删除商品关联为不可恢复操作（804 行 tip 自述"不可恢复"）但两视图均**无二次确认**，单击即 `taskLinkApi.remove`（644-648） | 加 Popconfirm，与任务管理危险操作口径统一 | 低 | 中 |
| 5 | 1 信息架构 | DB 模式下地区/品牌下拉选项只从**当前页** items 提取（653-660，651-652 行注释自认"跨页场景需用户清空筛选后重新选择"），筛选后选项集进一步塌缩，用户无从知晓还有别的可选项 | 后端提供 distinct 选项接口；至少在控件 tooltip 标注"仅当前页" | 中 | 中 |
| 6 | 3 视觉与布局 | 工具栏单行堆叠约 12 个控件（838-962：任务选择、关键词、地区、品牌、价格、排序、视图切换、管理任务、列配置、导出等），无分组分隔，1024-1366px 桌面窗口下换行混乱、重点（实时搜索按钮）被稀释 | 拆为主行（任务+搜索+模式）+ 折叠"更多筛选"；核心动作视觉强化 | 中 | 中 |
| 7 | 4 文案与提示 | "列配置"按钮在卡片视图被禁用（946），但 tooltip 仍是通用的"拖拽调整列顺序或显示/隐藏字段"（943），未解释为何不可用；禁用态按钮的说明本应回答"为什么" | 禁用时 tip 改「列配置仅在表格视图可用」 | 低 | 低 |
| 8 | 2 操作流程 | 实时模式两处均隐藏分页器（`{!liveMode && (<Pagination …`，1065-1067 与 1165-1167），结果超出一屏时既无翻页也无"加载更多"，想扩大视野只能重设条件再触发整轮搜索（有 60s 冷却成本） | 实时模式提供"加载更多/上限提示"，并显示已抓取条数 | 中 | 中 |

**三源一致性**：label 漂移——注册表 `config/menu_registry.yaml:25-31` 为「商品中心」，前端两源均为「商品列表」（`MainLayout.tsx:59,91`；`sheetRegistry.tsx:57`）。侧边栏菜单来自 /api/menu 渲染"商品中心"，而打开的页签标题和命令面板显示"商品列表"，同一页面两名并存（维度 1/6 问题，建议改 yaml 或前端统一，成本：低）。path `/items`、图标 ShoppingOutlined、分组 data_view 三源一致。

---

### 菜单：数据查看 > 卖家评估 (/evaluations，前端称"评估明细")

**现状描述**：单行长条工具栏承载 14+ 筛选控件，下方 6 张结果分类统计卡 + 宽表格（固定横向滚动 2170px），支持行展开、批量 AI 评估/官方采集、列配置与导出。筛选状态部分持久化到 localStorage，部分筛选即时触发查询、部分需点"查询"。

**问题与建议**：

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 6 一致性与规范 | 同一工具栏混用两种触发模型：任务（`pages/Evaluations/index.tsx:500`）、品牌（529）、在售/已售（543）、含越界价（583）、分类卡（614）选中即 `setPage(1); setTimeout(list.load, 0)` 自动查询，而商品 ID、价格区间必须点"查询"按钮（588），用户无法预测改哪个条件会立刻刷表 | 统一为"改动即失效、点查询生效"或全部自动触发（ID/文本框防抖），并保持一致 | 中 | 高 |
| 2 | 5 反馈与状态 | 批量 AI 评估循环内逐项 `catch {}` 吞错（`hooks/useEvalBatch.ts:101`），结束后无条件 `message.success('批量评估完成，共处理 N 项')`（109）——全部失败也报"完成"，用户以为已评估；对照同文件批量采集会报「成功 X，失败 Y」（138），双标 | 复用 succeeded/failed 计数，失败>0 时用 warning 并列出失败项 | 低 | 高 |
| 3 | 6 一致性与规范 | 筛选持久化半套：itemId/taskId/分数/日期/品牌/在售状态用 `usePersistentState` 写 localStorage（`hooks/useEvalFilters.ts:52-83`），结果分类/价格区间/含越界为普通 useState（85-91）——刷新后页面呈现"大部分条件被恢复、少数条件被清空"的混合态，结果集悄然变化 | 三类补齐持久化，或全部不持久化并说明 | 低 | 中 |
| 4 | 3 视觉与布局 | 分类统计卡中"价格区间"卡 `hoverable` 但无 onClick（`index.tsx:327`，其余五卡 318-319 均 hoverable+onSelect），悬停浮起承诺可点，点击无响应 | 去掉 hoverable，或点击联动价格筛选 | 低 | 中 |
| 5 | 4 文案与提示 | 数据不足横幅让用户"在 Dashboard 页面重新登录闲鱼"（`index.tsx:604`）：全站菜单名是"仪表盘"（MainLayout.tsx:56、sheetRegistry.tsx:52），不存在叫 Dashboard 的页面，且登录操作实际在反爬登录管理页——首次用户按文案根本找不到去处 | 改「在左侧『反爬登录管理』页面重新注入 Cookie」，并给可点击链接 | 低 | 高 |
| 6 | 5 反馈与状态 | 导出反馈失真：`ExportButton` 在调用下载后**同步**弹「正在导出 items 数据...」（`components/ExportButton.tsx:40-41`），catch 只能捕获同步异常，网络失败后无失败提示、成功也无落盘确认 | download 返回 Promise，按结果发 success/error | 低 | 中 |
| 7 | 2 操作流程 | 低于阈值商品的行动列只显示占位文本"未达阈值/已下单/已售"（`hooks/useEvalColumns.tsx:14-18,455-457`），无任何手动干预入口；数据不足且低分时两个 AI 按钮还被禁用（393,400 `isDataInsufficient && score<60`）——想复核一条可疑评估只能去商品中心另行操作 | 占位态旁加"强制重评/手动抢单"次级入口（带确认） | 中 | 中 |
| 8 | 3 视觉与布局 | 表格横向滚动宽度为硬编码魔数：SCROLL_X=2170（`index.tsx:43`）与折叠面板时 2180（469），而列配置允许用户显隐/重排列（941 行注释），宽度不随之自适应——隐藏多列后右侧留大片空白 | scroll.x 按可见列宽求和动态计算 | 低 | 低 |

**三源一致性**：label 漂移——注册表 `config/menu_registry.yaml:32-38` 为「卖家评估」（AuditOutlined），前端两源均为「评估明细」（`MainLayout.tsx:61,93`；`sheetRegistry.tsx:59`），侧边栏与页签/命令面板显示不同名（维度 6，低成本统一）。另有语义偏差：页面实际评估的是**商品成色与抢单决策**（行动列为 可抢/通过/驳回），"卖家评估"名不副实（维度 1，建议以"评估明细"为准修改 yaml label）。path、图标、分组 data_view 三源一致。
---

## 2. 数据查看（二）

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
---

## 3. 配置管理

### 菜单：配置管理 > 价格策略
**现状描述**：左右分栏「4 策略卡 + 直方图/命中预览」，顶部重置/保存，走 configStore 的 dry-run Diff 预览（`frontend/src/pages/Config/PriceStrategy.tsx:189-200`）。预览区视觉冲击好，但预览数据与脏检查链路有实质缺陷。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 5/4 | 直方图接口失败时**静默塞入硬编码假数据** `counts:[5,12,28,35,…]`（`PriceStrategy.tsx:74-81`），而"策略命中预览"的总商品数/通过/过滤三个 Statistic 直接由它计算（`:124-146`、`:407-422`）→ 用户按假数据调阈值 | 失败改为 Empty+重试按钮，卡片标题加"示例数据"水印；禁止 mock 驱动统计 | 低 | 高 |
| 2 | 2/5 | "刷新预览数据"按钮是假动作：`setTimeout(500ms)` 后 `message.success('预览已刷新')`，**未重新请求** `priceApi.histogram`（`:427-442`），而 tip 写"重新生成策略命中预览数据" | onClick 真调 histogram 接口；加载中 disabled | 低 | 高 |
| 3 | 5/6 | 本页**无 `if(!config)` 早退**（`:43-56`），加载中先用 `defaultConfig` ¥10000/¥100 渲染，config 到达后数值跳变（`:32-41`）；其他 4 页均有早退（`EvalRules.tsx:211`、`BuyerStrategy.tsx:61`、`SearchConfig.tsx:115`、`NotifierChannels/index.tsx:211`） | 统一早退 Spin；或 config 到达前禁用编辑区 | 低 | 中 |
| 4 | 2/6 | 四个策略卡改本地 `strategy`（`:235/255/279/299/343/359/379`），只有分位数滑块走 store（`:217`）→ 用户改了上下限后 `hasChanges()` 仍为 false，顶部"放弃未保存的修改并重置"**保持禁用**（`:193`）；切页签卸载即丢改动、无任何离开保护 | 每次 onChange 同时 `update({price_strategy:…})`；SheetWorkspace 关签前脏守卫 | 低 | 高 |
| 5 | 2 | `max_price`/`min_price` 的 InputNumber **无 min/max**（`:259-264`、`:303-308`）可输入负数/超大值；`min>max` 会过滤掉全部商品且无提示；本页无任何 `validateBeforeSave`（对比 `EvalRules.tsx:297-301`） | 补 InputNumber 边界 + 保存前 `min<max` 校验并定位到字段 | 低 | 中 |
| 6 | 1/4 | 卡标题"策略配置（4 种策略独立开关）"（`:205`）实际含 5 个编辑块，第 1 个"捡漏价格分位数"写的是 `bargain_price` 不是 `price_strategy`（`:207-225`），引导也只说"四组开关"（`frontend/src/guides/menuGuides.ts:95`） | 分位数单列一卡并在标题说明生效对象 | 低 | 低 |
| 7 | 3/6 | `market_ratio`（`:337-351`）与 `top_n`（`:375-385`）只有 Slider 无 InputNumber，上下限则是双控件 → 无法精确输入 0.65 或 Top7 | WeightSlider 式复用，四卡控件形态统一 | 低 | 低 |

**三源一致性**：`config/menu_registry.yaml:83-89`（price_strategy / 价格策略 / DollarOutlined / `/config/price` / config）＝ `MainLayout.tsx:65`、`:98` ＝ `sheetRegistry.tsx:63`，label/path/icon/group 全部一致。**唯一问题**：图标 DollarOutlined 与「价格行情」撞车（`menu_registry.yaml:74-80`、`MainLayout.tsx:97`、`sheetRegistry.tsx:77`），侧栏折叠 64px（`MainLayout.tsx:495`）时两菜单不可区分。

### 菜单：配置管理 > 评估规则
**现状描述**：左权重雷达图+滑块/阈值，右双分数滑块+AI 开关组+热力图+关键词（`EvalRules.tsx:338-760`）。是全组校验最认真的一页（权重总和、分数次序、字段级回滚）。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 4 | Alert 写"权重总和为 X，**建议**为 100（否则分数会被归一化）"（`:352-363`），但 `validateBeforeSave` 是**硬阻断**"权重总和必须为 100"（`:298`）→ 用户按"建议"理解后点保存被无理由拒绝 | 文案改"必须为 100"，并把"一键归一化"按钮放进保存失败的 toast 里 | 低 | 中 |
| 2 | 4 | 热力图注脚"绿色区=通过，橙色区=自动抢单"（`:734`），而 `visualMap.inRange.color` 只有灰→蓝四档 `['#f5f5f5','#bae7ff','#69c0ff','#1890ff']`（`:106`），图上不存在绿/橙 | 删掉错误注脚，或叠加 pass/auto 阈值参考线并据实描述 | 低 | 中 |
| 3 | 1/6 | `pass_score`/`auto_buy_score` 与「抢单策略」页重复编辑同一字段：本页有交叉校验（`:223`、`:297-301`），`BuyerStrategy.tsx:85-92` 完全没有 → 从抢单策略页可落盘 `pass>auto` 的非法组合 | 校验下沉到 configStore/后端规则；两页共用一个"分数区间"组件 | 中 | 高 |
| 4 | 1 | 卡标题"阈值配置（一票否决标识）"（`:423`）下前 3 项（在售数/发帖数/品类占比，`:424-449`）并不是一票否决，而打了"一票否决"标签后第 3 项 help 又写"注册不满此天数**加风险分**"（`:475-480`）→ 分组语义自相矛盾 | 拆"职业识别阈值"与"一票否决"两卡 | 低 | 中 |
| 5 | 6 | 权重滑块传了 `revertPath/originalValue/onRevert`（`:379-381` 等），阈值滑块一律不传（`:424-480`）→ 同类控件一半能单项回滚一半不能 | WeightSlider 统一传回滚参数 | 低 | 低 |
| 6 | 4 | 梯度评分表"价格分调整"列出现 `-25 / -50`（`:124`、`:129`）两种值未说明分别对应何种偏离；表头"以 600-800 元为例"（`:703`）是硬编码示例，不读用户任务实际区间 | 拆两列（偏离下限/偏离上限扣分），或按选中任务动态渲染 | 低 | 低 |
| 7 | 1/2 | 4 个 AI 开关（`:562/584/607/654`）打开即消耗 token，只有小字说明（`:570`、`:592`）无量级/预估、无二次确认（对比 `AIConfig/index.tsx:93-97` 关闭有确认）；卡标题"职业关键词（标签编辑器 + 拖拽排序）"（`:743`）是开发术语 | 高消耗开关加"预计成本"提示；标题改"职业关键词" | 低 | 低 |
| 8 | 5 | 评估分布热力图仅挂载时拉一次（`:197-209`），文案承诺"近 7 天数据"（`:734`）却无刷新入口、无数据时间戳 | 复用 `useAutoRefresh` 或加刷新按钮+"更新于" | 低 | 低 |

**三源一致性**：`menu_registry.yaml:90-96`（评估规则/SafetyCertificateOutlined/`/config/eval`）＝ `MainLayout.tsx:66`、`:99` ＝ `sheetRegistry.tsx:64`，一致。**引导说谎**：`menuGuides.ts:101` 称"权重变更对新任务生效"，页面/后端均无此限定（保存即 `reload_config()`，`api_config.py:266`），与同组"修改后保存即可生效"的表述冲突。

### 菜单：配置管理 > 抢单策略
**现状描述**：分数阈值 + 6 项运行时参数 + 账号轮换 + 模式说明 + 安全护栏（`BuyerStrategy.tsx:124-391`），全部实时写 store，Diff 保存。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 4 | 页头副标题"这些参数控制 auto 模式下的抢单行为。**notify / confirm 模式不受影响**"（`:128`），但同页"分数阈值/pass_score"说明"≥ 此分数会**推送给用户确认**"（`:179-181`）→ 首屏引导语对本页第一卡就是错的 | 改为"分数阈值影响全部模式；其余参数仅 auto 模式" | 低 | 高 |
| 2 | 4 | "安全护栏"称"auto_buy_score ≥ 80 才启用 auto 模式"（`:361`），但 UI 允许 0-100 任意值（`:150 min={0}`）且后端无 80 下限（`backend/…/domain/evaluation.py:73` 仅默认参数、`modules/worker.py:997` 直读配置值）→ 设 30 就会 30 分自动拍下 | 前端对 `auto<80 且存在 auto 任务` 给红字警告；或后端加真实下限 | 低 | 高 |
| 3 | 2 | `updateAutoBuyScore/updatePassScore` 无次序校验（`:75-92`），且 `clamp()` 静默改写输入（输入 150→100 无提示，`:68-72`） | 与评估规则共校验；clamp 时 message.warning 告知 | 低 | 中 |
| 4 | 5/4 | 生效范围三处打架：`:190`"修改后保存即可生效，无需重启服务"、`:292`"已创建的调度器实例会在下次启动时读取新值"、后端 `api_config.py:282-283` 返回 `restart_required:true / restart_note`——前端**从未消费**该字段（全 src 无 `restart_required` 引用） | 保存成功 toast 依据 `restart_required` 提示"部分参数需重启调度器" | 低 | 中 |
| 5 | 1/4 | "任务级模式"卡（`:329-356`）纯说明无跳转，文案称"（在「任务管理」中）"（`:331`）；`:159` 又引导用户去一个叫「**评估权重**」的页面——菜单实际叫「评估规则」，该页名不存在 | 文案改「评估规则」；模式卡加"前往任务管理"Link | 低 | 中 |
| 6 | 4 | 护栏第 2 条把用户指向源码 `buyer_config.py`（`:363-366`）"待 UI 化"——桌面 exe 打包后用户无法编辑 | 后端暴露 `daily_order_max` 并加 InputNumber；未做前至少标注"当前版本不可改" | 中 | 中 |
| 7 | 6 | 保存按钮硬编码 `backgroundColor:'#FF6200'`（`:133`），组内其他页用默认 primary；重置图标本页 `UndoOutlined`（`:130`）而价格页用自定义 `RevertIcon`（`PriceStrategy.tsx:193`） | 统一 CTA 与图标 token | 低 | 低 |
| 8 | 1 | 菜单叫"抢单策略"却承载"账号轮换调度"（`:289-326`），与反爬登录管理/系统维护语义重叠 | 迁至反爬页或改菜单名"抢单与账号调度" | 中 | 低 |

**三源一致性**：`menu_registry.yaml:97-103`（key `buy_config`、AimOutlined、`/config/buyer`）＝ `MainLayout.tsx:67`、`:100` ＝ `sheetRegistry.tsx:69`，一致；但 registry key `buy_config` 与 path/组件命名 `buyer`/`BuyerStrategy` 前缀不统一（同组 `search_config`→`SearchConfig` 等则一致），跨源匹配靠猜易错。

### 菜单：配置管理 > 搜索参数
**现状描述**：本地 useState 承载 9 个字段，保存时回写 `antidetect / search / task_scheduler / waf` 四段（`SearchConfig.tsx:120-150`）。摘要卡与预设标签是好设计。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 2 | 保存时**静默反推并覆盖未展示的字段**：`max_delay_ms = interval*1500`、`qps = round(60/interval)`（`:129-131`），用户只调"操作延迟"就改了 QPS 与最大延迟 | 把派生值显式做成只读展示+"高级：手动覆盖"开关 | 低 | 高 |
| 2 | 4/1 | "等效 QPS"标签（`:268-270`）显示"X **次/分钟**"——名称与单位矛盾（QPS=每秒） | 改名"每分钟请求数" | 低 | 中 |
| 3 | 5 | `handleSave` 的 catch 丢后端原因：`message.error('预览失败，请重试')`（`:159-160`），其余 4 页用 `extractApiError`（如 `PriceStrategy.tsx:101`）可显示 `{message, errors}`（`api_config.py:232-236`、`utils/apiError.ts:14-25`）→ 校验失败时用户不知哪个字段错 | 改 `message.error(extractApiError(e),5)` | 低 | 高 |
| 4 | 3/5 | `page_size` 初始化 `sc.page_size ?? 50`（`:94`）与 useState 初始 20（`:67`）不一致，而选项只有 20/40/60/100（`:46-51`）→ 后端为 50 时 Select 显示裸值 50、无匹配标签，用户以为坏了 | 用 Select `options` 兜底动态注入当前值或改 InputNumber | 低 | 中 |
| 5 | 2/6 | 脏检查同价格页失效：全部字段本地 state（`:65-77`），`hasChanges()` 在编辑期恒 false → "重置"按钮禁用（`:184`）、切页签丢改动无保护 | 同 PriceStrategy 修法 | 低 | 高 |
| 6 | 2 | "地区过滤"是自由文本逗号分隔（`:367-372`）无候选无校验，拼错=静默不过滤；同页 `filter_tags` 已有 TagEditor+常用预设（`:382-417`）→ 同类输入两种控件体验落差 | 地区改多选（省/市枚举） | 中 | 中 |
| 7 | 6 | Card 标题混用 emoji（🔍`:196`、⚙️`:251`、⏱`:274`、🛡️`:318`、📍`:361`、📋`:422`）而组内其他页用几何图标/纯文本；同页提示属性混用 `extra`（`:198/214/234/365/380`）与 `help`（`:284/306/327/338`），且 `Form.Item` 无 `<Form>` 包裹 | 定页面级标题与提示规范 | 低 | 低 |
| 8 | 4 | "当前配置摘要"（`:422-453`）漏掉本页新增的任务调度默认值与 WAF 两项，且不区分"已保存值/待保存值" | 摘要补齐并标"未保存" | 低 | 低 |

**三源一致性**：`menu_registry.yaml:104-110`（搜索参数/SearchOutlined/`/config/search`）＝ `MainLayout.tsx:68`、`:101` ＝ `sheetRegistry.tsx:68`，一致。**引导说谎**：`menuGuides.ts:113` 称可配"翻页深度"，页面（`:196-356`）无该字段；且菜单名"搜索参数"下实管 4 个后端配置段（`antidetect` 又被 `pages/Tasks/TaskEditor.tsx` 引用），所有权边界不清。

### 菜单：配置管理 > 通知渠道
**现状描述**：渠道卡片墙（分类/自定义两种排序）+ 拖拽优先级 + 免打扰时间轴 + 22 类事件订阅，支持"发送测试"（`NotifierChannels/index.tsx:222-432`）。信息架构是组内最好的。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 6/3 | `ChannelCard` 对**所有**字段无条件用 `Input.Password`（`components/ChannelCard.tsx:85-90`），而 `constants.ts:20` 定义的 `secret?: boolean` 从未被消费（仅 `:67/:80` 置 true）→ Server URL / Chat ID / Topic / Webhook URL 也被掩码，改一个 URL 要反复点眼睛 | 按 `field.secret` 决定 `Input` 或 `Input.Password` | 低 | 高 |
| 2 | 2 | 测试按钮把可选字段当必填：`emptyFields = ch.fields.filter(f => !credentials[f.key])` 拦截（`index.tsx:164-169`），而 `ntfy_token` placeholder 明写"可选"（`constants.ts:134`）→ 公共 ntfy.sh 主题永远测不了 | `fields[].required` 标志，仅校验必填 | 低 | 高 |
| 3 | 5 | 渠道"默认启用但凭据为空"无任何提示：`serverchan`/`pushplus` `enabled:true`（`constants.ts:37/48`），空凭据只在点测试时才报"请先填写…"（`index.tsx:166`）→ 用户以为已配好，实际静默丢通知 | 卡片角标"未配置凭据"+保存前汇总提示 | 低 | 高 |
| 4 | 3 | 分类排序模式按启用状态二次排序（`index.tsx:194 a.enabled ? -1 : 1`）+ 卡片墙直接渲染分组结果（`:271-283`）→ 切换任一开关时整墙重排，正在输入的凭据卡跳到另一列 | 仅在"自定义"模式重排，或分类模式固定顺序 | 低 | 中 |
| 5 | 4 | "推荐"徽章 Tooltip 硬编码"免费且无每日限制的**微信推送渠道**"（`ChannelCard.tsx:49`），但 `ntfy` 同为 `recommended:true`（`constants.ts:128`）→ ntfy 卡片上显示错误描述 | tooltip 改为 `ch.recommendedNote` 字段 | 低 | 中 |
| 6 | 2 | "发送测试"不提示消耗每日额度：`serverchan`"免费 5 条/天"（`constants.ts:39`）、`pushplus`"免费额度有限"（`:51`），按钮 tip 只说"发送测试推送消息"（`ChannelCard.tsx:93-104`） | tip 加"会占用该渠道每日额度" | 低 | 中 |
| 7 | 1/6 | Diff 预览把**密钥原文**渲染进表格（`components/DiffPreviewModal.tsx:134-145` 无掩码）且路径列显示 `serverchan_send_key` 等后端字段名（`:119`）；GET `/api/config` 也刻意不脱敏凭据（`api_config.py:661-669`），改一个开关时若凭据被顺带改动即明文外显 | Diff 表按敏感键名掩码；路径→人话标签字典 | 低 | 中 |
| 8 | 4/1 | 事件订阅把 `ITEM_FOUND` 标为"发现商品（旧枚举）"与 `ITEM_DISCOVERED`"发现商品"并列（`constants.ts:151-152`），22 项无分组（`index.tsx:377-413`）→ 用户不知该勾哪个 | 隐藏旧枚举或合并；按"任务/商品/购买/安全/系统"分组 | 低 | 低 |

**三源一致性**：`menu_registry.yaml:111-117`（key `notifier`、BellOutlined、`/config/notifier`）＝ `MainLayout.tsx:69`、`:102` ＝ `sheetRegistry.tsx:65`，一致。图标与「通知中心」`notifications` 撞车（`menu_registry.yaml:67-73`、`MainLayout.tsx:114`）。**引导说谎**：`menuGuides.ts:119` 称"**并发**推送"，页面自述是"按顺序尝试推送，失败则降级到下一个渠道"（`index.tsx:317`）；"7+ 渠道"实为 8 个（`constants.ts:31-137`）。

### 菜单：配置管理 > AI 服务
**现状描述**：总开关 + LLM/Embedding 两个 Tab + 用量仪表盘 + 预算卡（`AIConfig/index.tsx:246-359`），走独立 `aiApi` 即时 PUT，不接 configStore。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 2/5 | "测试连接"会**先保存整份配置**再测试且无提示（`index.tsx:153-156`）；Embedding Tab **根本没有保存按钮**（`components/EmbeddingConfigForm.tsx` 仅 `:121` 掩码切换与 `:210` 测试按钮），要落库只能点"测试 Embedding 连接"（`index.tsx:198-203`）→ 按钮语义与副作用不符 | 测试改为"临时参数试连"；Embedding 卡加显式保存按钮 | 低 | 高 |
| 2 | 2 | AI 关闭时整个配置区 `pointerEvents:'none'` + 蒙层（`index.tsx:279-302`），且保存/测试按钮额外 disabled（`ModelConfigForm.tsx:249/257`）→ 想"先填对 Key 再开启"做不到 | 保留可读可编辑，仅在生效层拦截 | 低 | 中 |
| 3 | 6 | 关总开关用浏览器原生 `globalThis.confirm()`（`index.tsx:94-97`），同组/同项目其他危险操作都用 `Modal.confirm`（`VersionManager.tsx:66`、`Chatbot/Config.tsx:139`）→ 主题/暗色不一致、不可本地化样式 | 换 `Modal.confirm` | 低 | 中 |
| 4 | 6/5 | 本页绕过组内统一范式（无 Diff 预览、无重置、无脏检查、`:136-147` 全量 PUT），且同页并存两个保存入口"保存配置"（`ModelConfigForm.tsx:249`）与"保存预算设置"（`BudgetSettings.tsx:66`），无统一"有未保存修改"标识 | 接入统一 useConfigSave + 脏标记 | 中 | 中 |
| 5 | 4/3 | 快捷预设用 `<Tag onClick>` 伪装按钮（`ModelConfigForm.tsx:234-241`），点击即**立即持久化并覆盖** base_url/model/vision_model（`index.tsx:116-133`），若用户有未保存手改直接吞掉、无确认；9 个预设（`constants.ts:4-79`）对"本地/收费/需装模型"差异无标注 | 预设渲染成 Button+当前项高亮，点击弹确认并预览三值 | 低 | 中 |
| 6 | 4 | `ModelConfigForm.tsx:174-176` 承诺"密钥通过系统密钥库（keyring）安全存储，**不写入配置文件**"（后端确有 `_load_secrets_from_keyring`，`backend/xianyu_hunter/config.py:90-96`），但同组通知渠道凭据就是明文 YAML（`api/types.ts:122`）——两页安全承诺相反且无解释，用户误以为所有密钥都进 keyring | 文案限定"仅 AI 密钥"；或统一凭据入 keyring | 低 | 中 |
| 7 | 6/1 | 单一 `showApiKey` 布尔同时控制 LLM 与 Embedding 两 Tab 明文（`index.tsx:317/336`）；预算上限只给 `(USD)`（`BudgetSettings.tsx:39-46`）而用量含 CNY（`api/types.ts` `total_cost_cny`），无换算/口径说明 | showKey 按 Tab 分离；USD 旁注折算 CNY | 低 | 低 |

**三源一致性**：`menu_registry.yaml:118-124`（AI 服务/RobotOutlined/`/config/ai`）＝ `MainLayout.tsx:70`、`:103` ＝ `sheetRegistry.tsx:67`，一致。**引导说谎**：`menuGuides.ts:125` 称本页配"模型、预算上限与 **Prompt**"，`pages/Config/AIConfig/**` 全文无 prompt 字段（grep 无匹配；Prompt 有独立后端路由 `routes/api_prompts.py`）。

### 菜单：配置管理 > 客服配置
**现状描述**：`pages/Chatbot/Config.tsx`（注意：**是单文件 Config.tsx，不是 `Config/` 目录**，`:70` sheetRegistry 亦按此解析）9 个 Tab，逐字段防抖 PUT，另含知识库/向量库/审计三类运维面板。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 5 | 每字段 500ms 防抖 PUT 且**每次都弹** `message.success('配置已更新')`（`Config.tsx:99-118`）→ 连改 5 项=5 条 toast 叠盖；与组内"统一保存+Diff 预览"范式完全相反 | 汇总为底部"保存/已自动保存 HH:mm:ss"状态条 | 低 | 高 |
| 2 | 2 | `onChange={(v) => v && updateConfig(…)}` 反复出现在 `:214/223/267/285/320/330/339/372/448/542/551`：值为 0 或清空时 `v` falsy → **静默不发送**，用户清空输入框后既无报错也无提示，只能靠猜 | 改 `v != null`；越界/清空给 Form 校验反馈 | 低 | 高 |
| 3 | 5 | 模块未启用时只弹一次 `message.error('智能客服模块未启用或加载失败')`（`:62`），随后永久停在 `if (loading || !config) return <Card loading={loading}>加载中...`（`:186-188`）→ 无限"加载中"，无重试入口 | 失败态 Result + 重试按钮 | 低 | 高 |
| 4 | 1/4 | 术语门槛高且无解释：`top_k（1-20）`(`:263`)、`相似度阈值（0-1，热更新）`(`:272`)、`context 最大字符`(`:281`)、`function_calling/fallback`(`:383-384`)、`PII 脱敏`(`:565`)；"热更新"作为后缀出现在 6 个字段（`:298/307/343/538/547`）但全站没说反面是什么（哪些改动需重启） | 每项一句业务解释 + "热更新"改为"改完立即生效" | 低 | 中 |
| 5 | 6 | 布局偏离本组规范：`Typography.Text + 控件 + marginLeft:16` 手排（`:201-226`、`:262-288`），无 Card 分组、无 Form.Item、无 TipButton 说明、范围写进 label；同组其他 7 页均 Card+help | 抽 `ConfigFieldRow` 统一 | 中 | 中 |
| 6 | 6 | 危险操作确认不统一：回滚知识库有 `Modal.confirm`（`:139-151`）、重建有（`components/KBStatusCard.tsx:17-26`），但**删除 FAQ 无确认**（图标按钮直接 `handleDeleteFaq`，`:517` + `:166-175`），关闭"启用智能客服"总开关也无确认（`:203-207`，对比 `AIConfig/index.tsx:93`） | 删除/总关统一 dangerConfirm | 低 | 中 |
| 7 | 2 | FAQ 弹窗 `onOk={() => onSave(form)}`（`:635`）无任何必填校验，空问题/空答案可直接提交（`:639-653`）；"分类"是自由文本（`:650-654`）无候选 → 分类拼错导致匹配与统计分裂 | Form rules + 分类 AutoComplete | 低 | 中 |
| 8 | 1 | 9 个 Tab 平铺（`:194-601`）把配置（基础/RAG/LLM/Agent/转人工）与运维（知识库管理/向量库维护/审计日志）混置；其中"向量库维护"（`:576-579`）与系统维护组的 `/maintenance/vector`（`sheetRegistry.tsx:73`）重复入口 | Tab 分"配置/运维"两组并跳转复用 | 中 | 低 |

**三源一致性**：`menu_registry.yaml:125-131`（客服配置/MessageOutlined/`/config/chatbot`）＝ `MainLayout.tsx:80`（ROUTE_LABELS）、`:110`（COMMAND_ITEMS）＝ `sheetRegistry.tsx:70`，label/path/icon 一致；`menuGuides.ts:129-132` 描述与实际 Tab 相符（RAG/Agent/知识库/FAQ/转人工均存在）。**问题**：与「智能客服」`/chatbot`（`menu_registry.yaml:178-184`）同用 MessageOutlined，折叠侧栏不可区分；且 `MainLayout.tsx:79-81` 把两个 `/config/*` 与 `/chatbot` 排在不同 group 段落，`ROUTE_LABELS` 分组注释与 registry `category` 已错位。

### 菜单：配置管理 > 配置版本
**现状描述**：统计卡 + 备份时间线（分页）+ 回滚/恢复/导出/分享/导入（`VersionManager.tsx:220-432`）。备份列表与导入 diff 预览设计良好。

| # | 维度 | 问题（具体元素 + 证据） | 优化建议 | 成本 | 优先级 |
|---|---|---|---|---|---|
| 1 | 4/6 | "分享配置"脱敏是**死代码**：`SENSITIVE_KEYS` 只列 4 个键（`:120`）且写在 export 响应顶层做替换（`:128-133`），但后端返回结构是 `{schema, exported_at, app, config}`（`api_config.py:458-467`），密钥在 `config.*` 下 → 循环永不命中；弹窗却断言"已替换为 ***"（`:422`），实际显示的是后端"****末4位"（`:705-709`） | 改 `sanitized.config[key]`，或直接调用已实现但前端未接的 `GET /api/config/share`（`api_config.py:411-440`；`api/config.ts:1-36` 无 share 方法） | 低 | 高 |
| 2 | 6 | 后端两份敏感清单 `SENSITIVE_KEYS`（`api_config.py:697-702`）与 `_SHARE_REDACT_PATHS`（`:300-313`）**均不含 ntfy 三键**（`api/types.ts:134-136` `ntfy_server/ntfy_topic/ntfy_token`），而 ntfy_token 是真实 Access Token（`NotifierChannels/constants.ts:134`）→ 导出/分享文件原文泄露 | 补 ntfy_token 进两份清单 + 前端清单从后端取 | 低 | 高 |
| 3 | 4/5 | 引导称"支持**对比**"（`menuGuides.ts:137`），但"查看详情"（`:316-325`）打开的弹窗只列 文件名/备份时间/大小/时间戳（`:384-403`），无任何 diff；变量名仍叫 `diffModalVisible`（`:38`）暴露当初就是想做 diff | 复用 `_diff`/preview 接口做"备份 vs 当前"diff；文案先降级 | 中 | 中 |
| 4 | 2 | 回滚/恢复后**不通知其他配置页签**：`configStore` 只在各页 mount 时 `load()`（`stores/configStore.ts:40-50`），本页 `load()` 只刷新自身（`:45-59`）→ 已打开的价格策略页签仍持旧值，用户点保存会把刚回滚的配置覆盖回去 | `confirmSave` 后调 `useConfigStore.setState({config:null})` 或提示"请重开配置页签" | 低 | 高 |
| 5 | 4 | 两处危险操作确认文案承诺不对称：一键回滚写"回滚前会自动备份当前配置（安全网）"（`:68`），"从备份恢复"确认框（`:86-89`）与详情弹窗底部按钮（`:366-380`）都不说是否留安全网 → 用户不知恢复能否撤销 | 统一措辞并说明是否可再回退 | 低 | 中 |
| 6 | 4 | "备份总数 10 个"（`:257`）不说明上限：后端 `list_backups` 已返回 `keep`（`api_config.py:293-295`，前端类型也有 `api/config.ts:22-25`）却被忽略；`_prune_backups()`（`:133`）会静默淘汰最旧备份 | 显示"最近 10 个（更旧自动清理）" | 低 | 中 |
| 7 | 3 | 备份详情用 `<Statistic>` 展示文件名字符串与时间戳（`:388`、`:399`），靠 `valueStyle fontSize:12` 硬压 —— 语义错误且长文件名会溢出 | 换 `<Descriptions>` | 低 | 低 |
| 8 | 2 | 导入失败提示太笼统："无效的配置文件格式"（`:158-161`）不说期望 schema 与来源版本（export 其实已带 `app.version`，`api_config.py:461-465`）；预览只显示前 20 条（`:171`）无"查看全部 diff"入口（`:187`） | 报错带 schema/版本；预览可展开全量 | 低 | 低 |

**三源一致性**：`menu_registry.yaml:132-138`（配置版本/HistoryOutlined/`/config/version`）＝ `MainLayout.tsx:71`、`:104` ＝ `sheetRegistry.tsx:66`，一致。

### 配置组跨页共性问题
1. **保存范式三分裂**（维度 6）：5 页 configStore+dry-run Diff（`PriceStrategy`/`EvalRules`/`BuyerStrategy`/`SearchConfig`/`NotifierChannels` 共用 `components/DiffPreviewModal.tsx:79-180`）；AI 服务=即时 PUT 且 Embedding 无保存按钮；客服配置=逐字段防抖 PUT 无预览。建议抽 `useConfigSave`（脏检查+Diff+成功/失败文案模板）。成本中，收益最高。
2. **脏检查与"重置"按钮在两页形同虚设**：`PriceStrategy.tsx:193` 与 `SearchConfig.tsx:184` 的 `disabled={!hasChanges()}` 依赖 store，但编辑留在本地 state（`PriceStrategy.tsx:235-379`、`SearchConfig.tsx:206-346`）→ 改了参数按钮仍禁用。全组 8 页**无任何未保存离开保护**，而 SheetWorkspace 切页签即卸载重挂（`MainLayout.tsx:659`），改动静默丢失。成本低。
3. **校验范式只有 1 页**：仅 `EvalRules.tsx:297-301` 做交叉校验；`min_price>max_price`、`pass>auto`、地区/标签非法值都能落盘——后端 `_validate` 只跑 pydantic 类型不含业务规则（`api_config.py:651-658`）。建议把已接入 Diff 弹窗的 ParamCalculator 分级建议（`DiffPreviewModal.tsx:170-177`）升级为阻断+字段定位。成本中。
4. **错误反馈文案不统一**：5 页 `extractApiError`（`PriceStrategy.tsx:101` 等），`SearchConfig.tsx:159-160` 与 `VersionManager.tsx:54/78/97/115/137/181` 用固定短语，丢掉后端 `{message, errors}`（`api_config.py:232-236`）→ 无法定位具体字段。成本低。
5. **危险操作范式无共识**：`Modal.confirm + danger`（`VersionManager.tsx:66-101`）、原生 `confirm()`（`AIConfig/index.tsx:94`）、无确认（`Chatbot/Config.tsx:517` 删 FAQ、`NotifierChannels/index.tsx:70-84` 禁用渠道）。建议统一 `dangerConfirm()` helper。成本低。
6. **密钥呈现三套做法且互不解释**：通知渠道 `Input.Password` 可一键明文（`ChannelCard.tsx:85` + 后端刻意不脱敏 `api_config.py:661-669`）、AI `type=password`+showApiKey（`ModelConfigForm.tsx:152-167`，且声称 keyring 更安全 `:174-176`）、Diff 表格原文展示（`DiffPreviewModal.tsx:134-145`）。缺"留空则不修改"写入语义，每次保存都回传原文。成本中。
7. **引导/文案与实现不符 5 处**（维度 4）：`menuGuides.ts:101`（新任务生效）、`:113`（翻页深度）、`:119`（并发推送）、`:125`（Prompt）、`VersionManager` 引导的"对比"；另有页面内错指「评估权重」（`BuyerStrategy.tsx:159`）。建议把引导文案纳入 e2e 断言（selector+关键字段存在性）。成本低。
8. **三源"单一事实源"名不副实**：`MainLayout.tsx` 实际**没有静态菜单兜底**，只有 `ROUTE_LABELS:55-85` 与 `COMMAND_ITEMS:88-115`；菜单全依赖 `/api/menu`，且 `useMenuConfig.tsx:206/227` 出错时 menus 保持空、`MainLayout.tsx:172` 只解构 `menuItems/loading` 忽略 `error` → 后端菜单接口失败=空白侧边栏无任何提示。同时 `/help`、`/menu-admin`、`/maintenance/vector`、`/confirm-buy` 只存在于 `sheetRegistry.tsx:73/81/82/86`、`COMMAND_ITEMS:111`，不在 `menu_registry.yaml`（违背 `menu_registry.yaml:1-3` 声明）；`COMMAND_ITEMS` 又漏 `/maintenance/tunnel`（registry `:169-175`）。字段命名亦漂移：registry 用 `category:`（`:89`），前端注释与 `MenuItemUpdate.group` 称 `group`（`api/menu.ts:3-7/52`）。成本低-中（生成单一派表 + 构建期一致性测试）。
9. **图标语义冲突集中**：价格策略↔价格行情（DollarOutlined）、通知渠道↔通知中心（BellOutlined）、客服配置↔智能客服（MessageOutlined），在 64px 折叠侧栏（`MainLayout.tsx:495`）不可区分。建议同类页用"对象图标 vs 动作图标"区分。成本低。

**未发现显著体验缺陷**：本次 8 页均有可指认缺陷，无"零问题"页；相对最健康的是 `NotifierChannels` 的信息架构（分类/推荐/额度说明/免打扰时间轴）与 `EvalRules` 的字段级回滚 + 交叉校验设计，可作为其他页的改造范本。
---

## 4. 系统维护与反爬

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
---

## 4.1 系统维护组跨菜单共性问题

本节由本切片内 7 个页面的证据归纳，均可由单点改动收敛：

1. **[高] 同级破坏性操作，确认强度相差两个量级**（R3 的最严重现场）：`DatabaseAdmin`/`VectorAdmin` 要求输入 `CONFIRM_DELETE`（`pages/Maintenance/DatabaseAdmin.tsx:394-404`、`pages/Maintenance/VectorAdmin.tsx:90-122`），`BatchRefresh` 的「清空全部」只有 `Popconfirm`（`pages/Maintenance/BatchRefresh.tsx:1067-1075`），`Cleanup` 的三个真实删除只用浏览器原生 `globalThis.confirm('确认清理缓存？此操作不可撤销。')`（`pages/Maintenance/Cleanup.tsx:88,116,143`），`Tunnel` 的「停止」零确认（`pages/Maintenance/Tunnel.tsx:596-605`）。建议抽 `dangerConfirm({ 范围, 命中条数, 是否可撤销 })` 一个组件，全组按「不可逆 + 影响他人」分级。成本：中（一次性收益覆盖全仓）。
2. **[高] `@cached_ttl(60)` 让"执行完立刻核对结果"变成不可能**：清理后前端马上 `loadStatus()`（`Cleanup.tsx:102,130,162`），但 `/api/maintenance/status` 带 60s 缓存（`web/routes/api_maintenance.py:70`）；向量库同因（`web/routes/api_vector_admin.py:138` vs `VectorAdmin.tsx:136,152,171,194`）。用户看到数字没变 → 判为失败 → **再点一次真实删除**。修法：写操作后由后端失效对应缓存 key，或前端刷新带 `force=1`。成本：低。
3. **[中] 审计回执跨页不互通**：`db_admin.*`（`api_db_admin.py:934`）、`maintenance.*`（`api_maintenance.py:438`）、客服向量库另写 `chatbot_audit_logs`（`api_vector_admin.py:56-61`）三套前缀/三张表，而两个审计抽屉的实现还相反——`DatabaseAdmin.tsx:573` 不 `await` 就打开（失败也显示"暂无数据"），`VectorAdmin.tsx:202-210` 先 `await` 才打开（慢数秒无反应）。建议合并为一个 `AuditLogDrawer` 组件 + 一个查询视图。成本：中。
4. **[中] 预览（dry-run）能力三种做法**：`Cleanup` 有开关且默认 true（`Cleanup.tsx:291-298`、`:42-55`）但预览成功时不发任何反馈（`:101-104`、`:129-132`），`DatabaseAdmin` 删除前强制级联预览（`:132-149`），`VectorAdmin` 的数据清理 Tab 完全没有预览（`:350-374`）；移动端反而比桌面端完整（`mobile/pages/Cleanup/index.tsx:79-82,109,128` 会区分「预览/立即执行」并给回执）。建议桌面端向移动端对齐。成本：低。
5. **[中] 页面无 `.page-container`，引导锚点整段失效**：`AntiCrawl/index.tsx:543` 与 `Maintenance/Tunnel.tsx:552` 用内联 `padding: 24`，而 `guides/menuGuides.ts:159-161,171-173` 已为这两页写好 Tour，容器缺失导致高亮定位失败（`guides/GuideController.tsx:94`）。成本：极低。
6. **[中] 服务器路径与实现术语直接呈给运营用户**：`VectorAdmin.tsx:269-271` 常驻展示 `persist_path`，`Tunnel.tsx:261,333` 把 `cert_file`/`credentials_file` 作为可复制主信息，`AntiCrawl/index.tsx:715-745` 直陈「UA / Profile / GPU / Stealth 脚本 / AWSC」。建议路径入 tooltip，术语换中文并配一句"该数字意味着什么"。成本：低。
7. **[低] 危险/告警语义色被复用为选中态**：`DatabaseAdmin.tsx:613-614` 用 `var(--xh-bg-warning)` + 3px `#FF6200` 表示"当前选中的表"，与本页删除按钮的危险色同形。成本：低。

**本组无「未发现显著体验缺陷」的页面**——7 个页面均有可指认缺陷；其中 `DatabaseAdmin` 的「级联预览 + 输入 token + 审计落库」三件套是全仓最成熟的安全设计，应作为其它维护页的对齐基线（而非反过来的问题页）。

---

## 5. 其他组与体系外页面

### 智能客服（/chatbot）

**现状描述**
`frontend/src/pages/Chatbot/index.tsx`（1533 行）为「左侧会话列表 + 右侧消息流 + 顶部引导卡」的三栏工作台，流式回复不走 `EventSource` 而是自写 `fetch + ReadableStream`（`frontend/src/pages/Chatbot/hooks/useSSEChat.ts`），事件按 `SSE_EVENT_HANDLERS` 查表派发（`index.tsx:170-177`）。后端 `backend/xianyu_hunter/modules/chatbot/orchestrator.py` 会下发 `intent`（`:45`）与 `faq_confirm`（`:49`）两类事件，模糊命中时只 yield `faq_confirm` 且不落库、不进 LLM（`:240-245`）。菜单标签三处不同：registry「智能客服」（`config/menu_registry.yaml:179`）、`ROUTE_LABELS`「智能客服」（`frontend/src/components/layout/MainLayout.tsx:79`）、页签与命令面板「智能客服对话」（`frontend/src/components/SheetWorkspace/sheetRegistry.tsx:83`、`MainLayout.tsx:109`）。入口在 registry「其他」组，二级界面包含 `components/ChatbotOnboarding.tsx`（引导卡 + FAQ 快问）、`components/HelpCenterModal.tsx`（使用说明 + 快捷键表）、模型切换 `hooks/useModelList.ts`。

**问题清单**
1. `[高]` SSE 事件表（`frontend/src/pages/Chatbot/index.tsx:170-177` + 未注册事件丢弃处 `:695-696`、`onComplete` 早退 `:236`）—— 后端 `faq_confirm`/`intent` 两个事件在前端无 handler，被静默丢弃；而模糊命中路径（`orchestrator.py:240-245`）只发 `faq_confirm`，不发 token/done —— 用户提问稍模糊时「消息发出去了，界面一句话都不回」，且没有任何错误提示（首次使用最痛，出现概率高）。
2. `[高]` 用户消息气泡的状态标记 `markSendingUserMessagesAsSent`（定义 `index.tsx:109-112`、调用 `:202-205`）—— 只要流开始就把全部 pending 用户消息标为「已送达 ✓」，即使随后收到 `error` 事件也不回滚 —— 用户看到「已送达」+ 无回复，误判为客服端 bug 或消息已被处理（典型「提示与实际结果不符」）。
3. `[高]` 撤回按钮渲染条件 `canRecall &amp;&amp; !msg.status`（`index.tsx:1514`）—— 只要消息带 `status`（发送后统一被置为 sent，见问题 2）就在 2 分钟窗口内也不显示撤回入口；而 `components/HelpCenterModal.tsx:18` 与 `frontend/src/pages/Help/index.tsx:654` 均明文承诺「2 分钟内可撤回」—— 文档承诺的功能实际不可用，误发敏感信息后无法收回。
4. `[中]` 失败重试语义（`index.tsx:44-45` `filterOutFailedMessages`、重试回填逻辑）—— 重试只把失败文本写回输入框，同时清除**全部**失败消息；一轮里发多条时其余失败消息直接消失且不再出现在历史（`listMessages` 也不含未落库消息）—— 用户丢失待发内容，高频场景下需重新组织话术。
5. `[中]` 历史加载不分页（`index.tsx:610` `listMessages(id, 50)`、`:579` `listSessions(1, 50)`）—— 后端 `backend/xianyu_hunter/web/routes/api_chatbot.py:260-278` 明确返回 `has_more` / `oldest_id`，前端两个字段都未消费，UI 无「加载更多」—— 长会话上滑到顶就「没有更早消息」，用户以为记录丢失；老会话在第 51 条后彻底不可发现。
6. `[中]` 取消流式（`hooks/useSSEChat.ts:127`）—— abort 后已生成的半截回答被整条丢弃，不写入本地列表 —— 长回答中途发现方向不对想停止，结果连已看到的内容也消失，只能重问。
7. `[中]` 快捷回复拉取失败静默（`index.tsx:502-504`）—— `catch` 后仅留空数组，无错误态与重试按钮 —— 快问区「空着」被理解为「本账号没有配置快捷回复」。
8. `[中]` FAQ 卡片点击行为（`components/ChatbotOnboarding.tsx:17` 注释声明「点击即提问」，实际 `index.tsx:866` 只 `setInput(text)`）—— 点完 FAQ 只是把文本填进输入框，仍需再点发送 —— 与卡片暗示的一次交互预期不符，首次用户常以为已经问了。
9. `[低]` 页面根元素无 `className="page-container"`（`index.tsx:871`）—— 首次引导 Tour 门禁 `.page-container`（`frontend/src/guides/GuideController.tsx:94`）找不到目标；`frontend/src/guides/menuGuides.ts` 也未写 `/chatbot` 条目 —— 客服页从不出现在自动引导链路里。
10. `[低]` 局部反馈与规范细节：静态 `message`（`index.tsx:2`，脱离 `main.tsx:64-91` 的 ConfigProvider 主题）、原生 `&lt;checkbox&gt;`（`:1426-1431`）与 AntD 表单控件混排、失败回复渲染字面量 `(空回复)`（`:243`）、新建会话无 pending 态（`:878-886`）。
11. `[低]` 引导卡关闭状态与生命周期冲突（`index.tsx:472-475` 每次切换会话重置本地标记，`components/ChatbotOnboarding.tsx:44-50` 读 `localStorage` 的意图被覆盖）—— 用户每换一个会话都要重新关掉同一张引导卡。
12. `[低]` 死代码造成的状态误判：`personalizeWelcome(..., false)`（`index.tsx:89`）恒为 false 分支；`SESSION_STATUS_MAP`（`:1057-1061`）含 `ended` 状态但后端无接口能产生该值 —— 无实际缺陷但增加「看起来支持」的错觉。

**优化建议**
1. 在 `SSE_EVENT_HANDLERS` 补 `faq_confirm`（渲染为「你是想问 …？/是/否」候选卡片，点击转正式提问）与 `intent`（渲染为轻提示「已识别为：价格咨询」）；同时在 `onComplete` 早退分支加兜底：若无任何 token 且未收到 error，插入「客服没有理解这个问题，换个说法试试」的系统回复。（成本：中）
2. 把 `sent` 标记改为「收到首个 token 或 done 事件后再置为已送达」，收到 `error` 时将该消息回退为 `failed` 并显示重试入口。（成本：低）
3. 撤回条件改为纯时间判定（`Date.now() - msg.createdAt &lt; 120_000 &amp;&amp; msg.role === 'user'`），去掉 `!msg.status`；同时让 Help/HelpCenter 的承诺与实现对齐。（成本：低）
4. 重试改为「按消息 id 原地重发」，`filterOutFailedMessages` 只作用于被用户显式删除的消息；一轮多条失败时逐条提供重试。（成本：中）
5. 消费 `has_more`/`oldest_id` 做上滑翻页（AntD `List` + 「加载中…」骨架），会话列表同样接入分页并在超过 50 条时显示搜索。（成本：中）
6. abort 时保留已累积文本并标记「（已停止）」，允许「继续生成」。（成本：低）
7. 快捷回复失败时展示 `Alert type=warning` + 「重试」按钮，而不是空数组。（成本：低）
8. FAQ 卡片点击后直接 `send(text)`（或在卡片 tooltip 明确「点击填入输入框」）。（成本：低）
9. 页面根 div 加 `className="page-container"`，在 `menuGuides.ts` 补 `/chatbot` 条目（会话列表 / 发送框 / 模型切换 / 帮助中心）。（成本：低）
10. 统一 `App.useApp()` 的 `message`、原生控件替换为 AntD、`(空回复)` 改为「客服未返回内容」并附重试、新建会话期间禁用按钮 + `loading`。（成本：低）
11. 引导卡关闭状态改为「按用户维度」持久化（只读 `localStorage`，不在会话切换 effect 里重置）。（成本：低）
12. 删除 `personalizeWelcome` 的恒假参数与 `ended` 状态映射，或补齐后端能力后再放开。（成本：低）

**优先级**：高 ×3（事件未接导致「点了没反应」、已送达假反馈、撤回不可用但与文档矛盾）/ 中 ×5 / 低 ×4。首要修复方向：**把后端已下发的两类事件接上，并把「送达 / 失败」的视觉状态与后端真实回执绑定**。

---

### 数据导出（/export）

**现状描述**
`frontend/src/pages/Export/index.tsx`（220 行）流程为「选数据集 → 勾选列 → 点导出 → 前端触发 blob 下载」，列定义优先取后端返回（`index.tsx:67-73` 为后端失败时的静态兜底列）。菜单项 `export`，`category: other`，`icon: CloudDownloadOutlined`，`sort_order: 302`（`config/menu_registry.yaml:185-191`，与 `chatbot` 的 300 之间跳过 301）。页签标题、面包屑、命令面板三处均为「数据导出」（`sheetRegistry.tsx:85`、`MainLayout.tsx:83`、`MainLayout.tsx:113`）。引导文案在 `frontend/src/guides/menuGuides.ts:185`，帮助文档章节在 `frontend/src/pages/Help/index.tsx:661-663`。

**问题清单**
1. `[高]` 导出成功提示（`index.tsx:78-95`）—— `message.success('正在导出…')` 在发起下载请求后**无条件**弹出，源码注释自认「无法捕获下载回调」；外层 `try/catch` 对 blob 下载失败路径是死代码 —— 后端 500 / 超时 / 生成空文件时用户看到的仍是成功提示，属于「错误被静默吞掉导致用户以为成功」。
2. `[中]` 列定义兜底无提示（`index.tsx:67-73`）—— 后端接口异常时静默切换到前端硬编码列，同时空态分支（`:105`）实际不可达 —— 用户勾选的列可能与后端真实可导出列不一致，导出的 CSV 少列却毫无提示。
3. `[中]` 枚举字段处理（`index.tsx:155-172`）—— `status` / `level` 作为自由文本列呈现，与系统内已有的枚举定义口径（如 `backend/xianyu_hunter/web/routes/api_db_admin.py:158`）不一致 —— 导出文件里出现中英文混杂枚举值，用户拿去做报表/回传时口径错乱。
4. `[中]` 文档臆造功能（`frontend/src/guides/menuGuides.ts:185`、`frontend/src/pages/Help/index.tsx:661-663`）—— 均描述「任务」数据集与「保存预设」，而页面（220 行全文）无预设持久化能力、数据集列表也不含任务 —— 用户按引导去找不存在的按钮，判定为功能缺失并提反馈。
5. `[低]` 页面根元素无 `className="page-container"`（`index.tsx:203`）—— 引导门禁（`guides/GuideController.tsx:94`）无法定位，且页内滚动容器与 `.sheet-content-area`（`components/SheetWorkspace/sheet.css:14-20`）形成双层滚动 —— 长列表导出配置滚动时「滚不动/双层抖动」。
6. `[低]` 导出按钮无并发保护（`index.tsx:78-95`）—— 可连续点击触发多次大表导出 —— 后端重复负载 + 浏览器多文件下载，用户不知哪份是最新。
7. `[低]` registry `sort_order` 断号（`config/menu_registry.yaml:182` 为 300、`:189` 为 302）—— 「其他」组内没有 301 —— 后续在两者之间插入新项需要重排。

**优化建议**
1. 改为「后端返回流 + 前端可读错误」模式：请求 `application/json` 的下载任务接口（返回文件 id/URL），轮询成功后 `message.success('导出完成，开始下载')` 并触发下载，失败走 `message.error` 并保留错误详情；若必须保留直接下载，至少把提示文案改为中性 `message.loading('正在生成导出文件…')` 且监听 `response.ok` 后再切成功态。（成本：中）
2. 兜底列定义时显式提示：`Alert type=warning「列信息来自本地默认配置，可能与服务端不一致」`+重试按钮；删除不可达空态或让其真正生效。（成本：低）
3. `status`/`level` 用与后端一致的枚举映射（下拉多选 + 中文标签 + 可选「导出原始值」）。（成本：低）
4. 校正 `menuGuides.ts:185` 与 `Help/index.tsx:661-663`，只描述实际存在的数据集与选项；或按文档补齐「保存预设」（本地 `localStorage` 即可）。（成本：低）
5. 根容器加 `page-container`，页内滚动改为依赖 sheet 容器单层滚动。（成本：低）
6. 导出期间按钮 `loading` + 禁用，并给并发导出上限。（成本：低）
7. registry 重排 `sort_order` 为 300/301/302。（成本：低）

**优先级**：高 ×1 / 中 ×3 / 低 ×3。核心是**导出结果不可知**：反馈必须与实际产物绑定。

---

### 关于（/about）

**现状描述**
`frontend/src/pages/About/index.tsx`（65 行）为聚合壳，实际内容由 `BrandCard.tsx`（214 行，品牌/版本/更新检查）与 `AboutMenuList.tsx`（105 行，官网/文档/反馈等外链入口）承担，更新逻辑在 `useUpdateChecker.ts`（251 行），文案在 `i18n.ts`（45 行）。菜单项 `about`，`icon: InfoCircleOutlined`（`config/menu_registry.yaml:192-198`）。该页是用户自助排障的第一落点，但 `frontend/src/guides/menuGuides.ts` 无 `/about` 条目。

**问题清单**
1. `[高]` 外链入口占位域名（`frontend/src/pages/About/AboutMenuList.tsx:16,17,23,24,25`）—— 五个入口的 `href` 仍指向 `example.com` 类占位地址 —— 用户在「关于」里点「官网 / 文档 / 反馈 / 社区 / 协议」全部跳到无意义站点，正是自助排障路径上最不该出现的坏链（首次使用即命中）。
2. `[中]` 版本信息静默失败（`frontend/src/pages/About/index.tsx:28-31`）—— `aboutApi` 异常被吞，版本区显示 `--`，无「加载失败/重试」—— 用户无法区分「未安装」与「接口挂了」，反馈问题时无法报出自己的版本。
3. `[中]` 一键安装无二次确认（`frontend/src/pages/About/useUpdateChecker.ts:224-240`）—— `install` 一次点击即触发覆盖升级，且无「建议先备份配置/数据库」提示 —— 误点后立刻进入升级流程，回退成本高（破坏性操作不可逆）。
4. `[中]` 下载 loading 提前撤下（`useUpdateChecker.ts:220` `message.destroy('update-download')`）—— 下载仍在进行时销毁 key 消息，之后无任何进度/结果提示 —— 用户以为下载结束，实际状态未知（提示与结果不符）。
5. `[中]` 更新状态随页签切换丢失（`components/SheetWorkspace/SheetContent.tsx:33-56` 仅渲染激活 sheet，非激活页组件被卸载）—— 切到别的页签再切回，「检查中/下载中/可安装」全部重置 —— 用户必须守着页面才能拿到结果，与多页签工作区模型直接冲突。
6. `[低]` `i18n.ts:28` 定义 `backToConsole` 但页面未使用 —— 关于页缺「返回控制台」这一最自然的出口。
7. `[低]` 更新结果状态闪退（`useUpdateChecker.ts:105-108`，`latest` 3 秒后自动回 `idle`）—— 用户来不及读完「已是最新版本」—— 反馈消失。
8. `[低]` 图标语义误用（`AboutMenuList.tsx:55`）—— 站内跳转项也使用 `ExportOutlined`（导出/外发语义）—— 用户误以为是外部链接。
9. `[低]` 免责声明只出现在 tooltip（`BrandCard.tsx:57-61`）—— 触屏与键盘用户无法看到，正文亦无「详见…」—— 合规文案可达性差。
10. `[低]` 根元素无 `className="page-container"` 且 `menuGuides.ts` 无 `/about` 条目 —— 无法纳入首次引导。

**优化建议**
1. 用真实地址替换占位域名，并把入口链接集中到一处配置（`config/` 或构建期 env），发布前加一条 lint/脚本断言不含 `example.com`。（成本：低）
2. `aboutApi` 失败时显示 `Alert「版本信息加载失败」+ 重试`，并把后端健康检查一并暴露。（成本：低）
3. `install` 前 `Modal.confirm`：列出版本差异、耗时预估与「更新前建议导出手动备份」提示，确认后再执行。（成本：低）
4. `message.destroy` 改为下载 `finally` 中执行，成功后再 `message.success`，失败 `message.error` + 「查看日志」跳 `/logs/errors`。（成本：低）
5. 更新任务状态上提到 store（`zustand`）或后端任务表，页面重挂载时从 store/接口恢复，保证跨页签与刷新可见。（成本：中）
6. 使用 `backToConsole` 文案加「返回控制台」按钮（`navigate('/')`）。（成本：低）
7. 「已是最新版本」改为常驻 `Result`/`Alert`，由用户手动关闭。（成本：低）
8. 站内项改 `RightOutlined`/`ArrowRightOutlined`，外部项才用 `ExportOutlined` + 外链图标。（成本：低）
9. 免责声明在正文单列一段（折叠即可），tooltip 只作补充。（成本：低）
10. 补 `page-container` 与 `menuGuides.ts` 的 `/about` 条目。（成本：低）

**优先级**：高 ×1 / 中 ×4 / 低 ×5。关于页当前**不具备自助排障能力**（链接是占位、版本读不到、免责声明看不到）。

---

### 帮助文档（/help）

**现状描述**
`frontend/src/pages/Help/index.tsx`（877 行）为单页文档站：`DOC_SECTIONS` 30 章硬编码于 `:106-692`，左侧 AntD `Menu` 目录 + 右侧 `Anchor` 锚点（`:806-811`），顶部关键词搜索（`:751-757`）。该 path **不在 `menu_registry.yaml`**，但已在 `sheetRegistry.tsx:86` 注册（title「帮助文档」、icon `BlockOutlined`），入口有三处：`ROUTE_LABELS`（`MainLayout.tsx:81`）、`COMMAND_ITEMS`（`MainLayout.tsx:111`，icon `QuestionCircleOutlined`）、顶栏帮助按钮。页面位于 `MainLayout` 下（`App.tsx:125-129`），因此**未登录时无法访问**。

**问题清单**
1. `[中]` 搜索范围（`index.tsx:751-757`）—— 仅匹配章节 `title` 与 `intro`，30 章正文（`:106-692`）完全不参与索引 —— 用户按文档里实际写过的关键词搜索却返回「无匹配」，误判「文档没写」，转而提问或提反馈。
2. `[中]` 侧栏折叠后不可逆（`index.tsx:776-783`，`collapsedWidth={0}` + `trigger={null}`）—— 窄屏或窗口缩小后目录宽度归零且无展开触发器 —— 手机上/分屏时整个导航消失，30 章只能靠滚动查找。
3. `[中]` 锚点容器错配（`index.tsx:806-811` 未传 `getContainer`；真实滚动容器为 `.sheet-content-area`，见 `components/SheetWorkspace/sheet.css:14-20`）—— `Anchor` 监听的是 `window`，页签工作区里不发生滚动 —— 目录高亮永不跟随阅读位置（点击能否滚动需实测确认）；页面独立渲染时行为又不同，属「同一文档两种表现」。
4. `[中]` 文档与实现不符三处：`:646` 描述顶栏有「机器人图标」（`MainLayout.tsx:556-652` 顶栏 8 个控件中无该图标）；`:654` 承诺「2 分钟内可撤回」（实现条件在 `pages/Chatbot/index.tsx:1514` 使其不可见）；`:661-663` 描述导出的「任务数据集/保存预设」（`pages/Export/index.tsx` 无此能力）—— 用户按文档找不到元素，最终怀疑自己操作错误。
5. `[低]` 术语与图标不统一：页签用 `BlockOutlined`（`sheetRegistry.tsx:86`），命令面板与顶栏用 `QuestionCircleOutlined`（`MainLayout.tsx:111`、顶栏按钮区）—— 三个入口的视觉线索不一致，用户无法确认自己找的是同一处帮助。
6. `[低]` 根元素无 `className="page-container"` —— 引导 Tour 无法定位帮助页；`menuGuides.ts` 也无条目。

**优化建议**
1. 构建期把 `DOC_SECTIONS` 正文拍平为可检索字符串（或按段落建倒排索引），搜索命中处展示「章节 &gt; 小节」路径并高亮关键词。（成本：中）
2. `collapsedWidth` 改为 48（保留图标）并恢复 `trigger`，或在窄屏用 `Drawer` 承载目录。（成本：低）
3. `Anchor` 传 `getContainer={() =&gt; document.querySelector('.sheet-content-area')}`，并把帮助页在「独立渲染 / 页签内渲染」两种容器下都验一遍。（成本：低）
4. 三条错误内容按实际实现更正；建议加一条约定：Help 文案改动须与对应页面 PR 同期（可用行号注释互指）。（成本：低）
5. 统一入口图标为 `QuestionCircleOutlined`，并在 `sheetRegistry` 与 `menu_registry.yaml` 都补 `help` 项（当前 registry 缺失，见末节漂移表）。（成本：低）
6. 补 `page-container` 与 `/help` 引导条目。（成本：低）

**优先级**：中 ×4 / 低 ×2。帮助页信息量足够，问题集中在**检索不到、导航易丢失、内容与实现漂移**。

---

### 登录（/login）

**现状描述**
`frontend/src/pages/Login/index.tsx`（1345 行）单页四种登录方式，以 Tab 呈现（`:1156-1235`）：浏览器窗口登录（Playwright）、从浏览器导入 Cookie、Cookie 手工注入、Cookie 文件导入；进入时先做 `checkingAuth` 全屏 Spin（`:1142-1154`），成功后 `onLoginSuccess` 消费 URL 里的 `redirect`（`:782`、`:864-872`，800ms 硬编码延时 `:871`）。路由在 `MainLayout` 之外（`App.tsx:90`），因此没有页签与侧栏；教程 Modal 在 `:1300-1342`。

**问题清单**
1. `[高]` 会话 Cookie 明文暴露（`index.tsx:844` 自动拉取并回填 + `:459-468` 明文 `Input` 承载 Cookie 值）—— 无 `type="password"`、无掩码/显示切换、离开页面或失败后不清空，值直接进 DOM —— 肩窥、录屏、共享屏幕、浏览器自动化快照均可拿到闲鱼会话凭证（密钥/敏感数据明文暴露）。
2. `[高]` 「自动关闭 Edge/Chrome 并导入」无二次确认（`:601-623` 两个按钮直接 `onImport('edge', true)` → `handleImportFromBrowser`（`:1042-1065`）触发后端结束浏览器进程）—— 全程没有 `Modal.confirm`，`:592` 的描述也只说「会自动关闭浏览器进程后重试」而没说明会**关掉用户当前所有标签页、丢失未提交表单** —— 一次误点即造成与本项目无关的不可逆数据丢失。
3. `[中]` 四种方式术语高度重叠（`:1156-1235`）—— Tab 名称如「浏览器登录 / 从浏览器导入 / Cookie 注入 / 文件导入」，均围绕「Cookie/浏览器」，无「推荐」标记、无耗时/风险对比、失败后不引导换一种方式 —— 首次用户无法判断该选哪个，典型表现为四种都试一遍仍失败。
4. `[中]` 无出口、无兜底：`:833-837` 明确在未登录时不做跳转，页面外壳（`:1242-1296`）无「返回/稍后再说/查看帮助」入口；而 `/help` 挂在 `MainLayout` 下（`App.tsx:125-129`），未登录访问会被 `api/client.ts:32-51` 再弹回登录页 —— 四种方式全败即**死锁**，用户只能读 `:1300-1342` 那个教程 Modal。
5. `[中]` 跳转竞态与无超时：`:871` 用 800ms `setTimeout` 硬编码跳转，期间无遮罩/loading，用户可再次点击或修改输入（结果被丢弃）；`checkingAuth`（`:1142-1154`）全屏 Spin 无超时，后端未启动时页面永远转圈且不提示「服务不可用」—— 与环境变量的部署方式（`web --with-scheduler`）耦合，用户看不出是没登录还是服务没起。
6. `[低]` 静态 `message`（`index.tsx:8`）—— 脱离 `main.tsx:64-91` 的 ConfigProvider 主题，深色模式下提示条配色突兀。
7. `[低]` 实现术语外露：`:1310` 等处直接出现「Playwright」等内部技术名词 —— 普通用户不理解，也无法据此求助。
8. `[低]` 说明重复：教程 Modal（`:1300-1342`）与各 Tab 内部说明（`:1156-1235`）内容重叠 —— 两处各自演化，已成漂移（例如 `:592` 的按钮名与实际按钮文案「自动关闭 Edge 并导入」措辞不一致）。

**优化建议**
1. Cookie 输入框改 `Input.TextArea type=password` + 显式「显示」开关 + 复制后自动遮蔽；成功后立即清空输入；页面顶部加一句「Cookie 等同登录凭证，请勿截图或分享」。（成本：低）
2. `autoClose` 前 `Modal.confirm`，明确「将强制结束 Edge/Chrome 的全部窗口，未保存内容会丢失，是否继续？」并列出被结束进程数；提供「我自己手动关闭后重试」的替代按钮（成本：低）
3. 四个 Tab 改为「推荐方式 / 其他方式」两段：首个 Tab 打 `推荐` Tag，每个 Tab 增加「需要 30 秒 / 需要安装浏览器 / 会结束浏览器进程」的约束说明；任一方式失败后自动提示「改用 XX 方式」并高亮对应 Tab（成本：中）
4. 增加「查看帮助（无需登录）」与「跳过，先看演示数据」两个出口：把 `/help` 中排障相关章节拆到登录壳层外的只读路由（成本：中）
5. 跳转改为 `navigate(redirect)` 立即执行并显示 `Spin` 遮罩禁用表单；`checkingAuth` 加 8s 超时并区分「未登录」与「后端不可达」（成本：低）
6. 统一改用 `App.useApp()` 的 `message`（成本：低）
7. 面向用户文案去掉内部技术名词，改为「自动打开一个受控浏览器窗口」（成本：低）
8. 说明单一来源化：Tab 内说明与教程 Modal 共用同一份常量（成本：低）

**优先级**：高 ×2 / 中 ×3 / 低 ×3。**凭证明文 + 无确认杀浏览器**是本切片里最严重的两项，与任何其他界面无关也应先修。

---

### 新手引导（/onboarding）

**现状描述**
`frontend/src/pages/Onboarding/index.tsx`（280 行）四步向导：登录（`:103-108`）→ 创建任务 → 通知渠道（`:204`）→ 完成（`:240-257`），每步带命令/参数「复制」按钮，步骤位置存组件 state（`:33`）不持久化，右上角「跳过」（`:272`）。该 path 不在 `menu_registry.yaml`、不在 `sheetRegistry`、不在 `ROUTE_LABELS`/`COMMAND_ITEMS`，独立路由在 `App.tsx:92`，唯一入口是 `frontend/src/pages/Dashboard/index.tsx:241` 的小按钮「查看新手引导说明」。

**问题清单**
1. `[高]` 引导命令不存在：`Onboarding/index.tsx:103,108` 让用户执行 `python -m xianyu_hunter qr-login`、`:220,225` 执行 `python -m xianyu_hunter worker`，而 CLI 实际命令集为 `add/list/status/login(backend/xianyu_hunter/__main__.py:128)/run(:175)/pause/resume/stop/config_show/web(:268-280)` —— 无 `qr-login`、无 `worker` —— 用户「一键复制」得到的命令 100% 报错，引导页把新用户推向「按文档操作却失败」的最差首体验（正确命令是 `login` / `run` / `web --with-scheduler`）。
2. `[中]` 导航不可发现且壳层缺失：`/onboarding` 四处定义源均无记录（对照末节漂移表），只能通过 Dashboard 一个小按钮进入；由于不在 `sheetRegistry`，从外部链接/收藏直达时走 `App.tsx:92` 的独立路由（无侧栏、无页签、无面包屑），与站内其它页面观感完全不同 —— 用户以为打开了另一个系统。
3. `[中]` 首开路径不经过引导：`MainLayout.tsx:365-370` 的登录后逻辑只做 `redirect` 回原页，从不导向 `/onboarding` —— 「登录 → 引导 → 落地页」的自洽路径实际不存在，新用户直接落到仪表盘。
4. `[中]` 向导内跳转导致步骤丢失：`index.tsx:204` `&lt;Link to="/config/notifier"&gt;` 跳出向导，而 `current` 仅在内存（`:33`）—— 返回时从第 1 步重来，「照着引导做一遍」无法闭环。
5. `[中]` 失败被吞：`index.tsx:87` 创建任务失败时只给通用文案，不透出后端 `detail` —— 引导中最关键的一步失败，用户无从自查（如缺 Cookie 导致的失败被说成「创建失败」）。
6. `[中]` 「跳过」与完成态语义矛盾：`:272` 跳过 + `:240-257` 各步均可跳过，可在 4 次点击后抵达「设置完成！」终态，而实际可能一条配置都没写 —— 提示与实际结果不符，用户以为已可用。
7. `[低]` 静态 `message`（`index.tsx:11`）；根元素无 `className="page-container"`（引导 Tour 无法定位）；`:52-67,70-91` 命令块与说明文字混排，无「这是要复制的命令」视觉区分。

**优化建议**
1. 用真实命令替换两条错误命令：登录步骤改 `python -m xianyu_hunter login`（或 `web` 后走界面登录），后台运行步骤改 `python -m xianyu_hunter run` / `web --with-scheduler`；并在 CI 里用 `--help` 输出的命令清单校验引导内所有命令字符串（成本：低）。
2. 把 `/onboarding` 注册进 `sheetRegistry` + `menu_registry.yaml`（`category: other`）+ `ROUTE_LABELS` + `COMMAND_ITEMS`，或明确定位为「登录后一次性向导」并在完成后从菜单隐藏（成本：低）。
3. 首次登录成功（后端记录 `onboarded_at` 为空）时强制/建议进入引导，完成后回到 `redirect` 目标（成本：中）。
4. `current` 持久化到 `localStorage`（键含用户标识），跳出去配置时保留进度并显示「第 3/4 步 · 已完成 2 项」（成本：低）。
5. 失败提示透出后端 `detail`，并在缺 Cookie 时直接给「去登录」按钮（成本：低）。
6. 完成态按实际配置判定：全部跳过时显示「引导已结束，但 4 项设置未完成」并逐项列出跳转入口（成本：低）。
7. 补 `page-container`、改 `App.useApp()`、命令块统一用 `Typography.Paragraph code + copyable`（成本：低）。

**优先级**：高 ×1 / 中 ×5 / 低 ×1。当前引导页的错误命令足以单独构成「新用户第一小时不可用」。

---

### 确认抢单（/confirm-buy）

**现状描述**
`frontend/src/pages/ConfirmBuy/index.tsx`（210 行）由通知/任务详情的深链进入（携带 `item_id`、`task_id`），展示商品信息快照（价格取 DB 值，`:170`）+ 一条常驻 warning `Alert`（`:186-191`），「确认抢单」按钮直接提交（`:194-203`），成功后 `navigate('/orders')`（`:61`）。registry 中无该菜单项，`sheetRegistry.tsx:81` 已注册（title「确认抢单」、`ThunderboltOutlined`，与 `/orders` 同图标），`App.tsx:123` 有路由。是「半自动模式」的资金动作收口页。

**问题清单**
1. `[高]` 移动端整条链路不可用：`App.tsx:80` 对所有非豁免路径一律 `navigate('/m/')`（豁免仅 `/xianyu/m`、`/xianyu/login`），`frontend/src/mobile/routes.tsx` 无 confirm-buy 路由 —— 手机通知里的确认链接被丢回移动端首页，`item_id/task_id` 全清；抢单是强时效动作，等于移动端功能缺失且用户不知道链接曾存在（成本叠加：通知触达主要发生在手机）。
2. `[高]` 真金下单无二次确认：`index.tsx:194-203` 单击即提交，唯一提示是常驻 `Alert`（`:186-191`），无 `Modal.confirm`、无「我已确认价格」勾选、无提交中锁 —— 误点即真实下单且**不可撤销**（成功态只有 `:61` 的「查看订单」）。
3. `[中]` 成功后无撤销/结果闭环：`:61` 直接跳 `/orders`，但下单为异步（订单可能尚未落库），页签被 sheet 栈复用后返回本页面时状态已丢失 —— 用户「点了确认，订单里找不到」，转而重复点击造成重复下单。
4. `[中]` 参数缺失静默降级：`:57` 以 `taskId || undefined` 透传，页面也不显示「来源任务未知」—— 深链参数被截断（例如 URL 编码/转发丢参）时，用户看到的是「正常」的确认页，实际上下文已错。
5. `[中]` 错误码原样外泄且重复提示：`:72-79` 把 503/403/409/500 的原始文案同时渲染进 `Alert`（`:147-155`）并弹 toast，`Alert` 常驻不关闭 —— 满屏技术错误码，用户既不知道能不能重试，也不知道该找谁。
6. `[低]` 价格快照缺时间语境：`:170` 只显示 DB 里的价格，无「采集于 X 分钟前，闲鱼价格可能已变化」—— 用户按快照价格决策，实际成交可能不同。
7. `[低]` 出口名不副实：`:134-136`「返回评估列表」、`:204-206`「取消」不执行 `navigate(-1)` 也不回来源页 —— 「取消」被理解为放弃抢单却没回到任何列表。
8. `[低]` 根元素无 `className="page-container"`；`guides/menuGuides.ts` 与 `Help/index.tsx` 均无该页说明条目 —— 半自动模式最敏感的页面没有任何引导与文档。

**优化建议**
1. 为移动端补 `/m/confirm-buy`（或把豁免表加入 confirm-buy），并在移动端首页/TabBar 暴露待确认列表（成本：中）。
2. 提交前 `Modal.confirm`：展示商品标题、价格、数量、来源任务，要求勾选「我已知晓下单后不可撤销」，确认期间按钮 `loading` 且禁重复提交；可选「48 小时内可取消」的后端能力（成本：低）。
3. 成功后返回订单号并轮询订单落库，落库前显示「正在创建订单…」而非直接跳 `/orders`；跳不过去时提供「留在本页查看结果」（成本：中）。
4. 缺 `item_id`/`task_id` 时改为显式错误态：「链接不完整，请从任务详情或通知重新进入」，并给出入口按钮（成本：低）。
5. 错误码映射为用户文案 + 可操作性（可重试 / 需重新登录 / 稍后再试），重试按钮走 `catch` 分支，`Alert` 可关闭且不再重复弹 toast（成本：低）。
6. 价格旁显示「采集于 12 分钟前」+「刷新价格」按钮（成本：低）。
7. 「取消」改为 `navigate(-1)`，文案与实际目标一致（成本：低）。
8. 补 `page-container`、`menuGuides` 条目与 Help 章节（半自动模式流程）（成本：低）。

**优先级**：高 ×2 / 中 ×3 / 低 ×3。这是全片**唯一直接花钱**的界面，破坏性操作防护等级却最低。

---

## 6. 全局壳层与共性问题

**现状描述**
壳层为 `frontend/src/components/layout/MainLayout.tsx`（834 行）：Sider（折叠 64px）+ 顶栏 8 个控件（`:556-652`）+ 页签区由 `components/SheetWorkspace/index.tsx` 接管（**无 `&lt;Outlet/&gt;`**），动态菜单来自 `hooks/useMenuConfig.tsx` + `api/menu.ts` + `config/menu_registry.yaml`，页签元数据来自 `sheetRegistry.tsx`，面包屑来自 `ROUTE_LABELS`（`:55-85`），命令面板来自 `COMMAND_ITEMS`（`:88-115`）+ `Modal`（`:762-828`），键盘助记 `G_PREFIX_MAP`（`:118-128`）。页签状态由 `stores/sheetStore.ts`（314 行）+ `hooks/useSheetSync.ts` 驱动，偏好见 `SheetPreferences.tsx`，通知见 `sheetNotifications.tsx` 与 `SheetTabs.tsx`。

#### 问题清单
1. `[高]` 菜单接口失败＝空白侧栏且无提示（`MainLayout.tsx:172` 只解构 `{ menus, loading }` 丢弃 `error`；`useMenuConfig.tsx:245` 明明返回 `error`，`:223-227` 首次失败时无旧缓存可保留）—— 后端重启/Cookie 过期瞬间，用户看到没有任何菜单的空壳，`:393-399` 的全屏 Spin 结束后什么都不剩，也没有重试入口 —— 全站不可用却无任何解释（高频、必现于后端重启后）。
2. `[高]` 「最小化保留页面状态」承诺完全落空（`SheetPreferences.tsx:119-125` 明文「关闭按钮改为最小化…保留页面状态」，而 `SheetContent.tsx:33-56` 只渲染 `activeSheet` 且用 `key={sheet.id}` 重挂载，`SheetWorkspace/index.tsx:75` 亦只挂激活页）—— 切换页签即卸载非激活页面：列表筛选、分页、表单未保存内容全部丢失 —— 用户按 UI 承诺行为去切页签再切回，发现「刚才的筛选没了」，属数据/工作丢失。
3. `[高]` 循环替换关闭 + 栈满 = 导航锁死（`sheetStore.ts:320-336` 上限分支、`sheetNotifications.tsx:25-53` 仅对 `replacedSheet` 发通知、`useSheetSync.ts:40-45` 失败时把 URL `replace` 回激活页）—— `reason: 'limit'` 与 `'not_found'` 两种失败**没有任何用户提示**，点了侧栏菜单后 URL 被顶回去、页面纹丝不动，`SheetTabs.tsx` 也没有「关闭其他/全部」入口 —— 用户反复点击同一菜单毫无反馈（典型 高「点了没反应」）；`maxSheets=1`（`SheetPreferences.tsx:37-44` 允许）时更是彻底锁死。
4. `[高]` 原生锚点与 BrowserRouter 冲突（`frontend/src/guides/GuideController.tsx:167` 与 `:187` 两处 `&lt;FloatButton href="#/help"&gt;`；路由是 `BrowserRouter basename="/xianyu"`，见 `main.tsx:86`）—— `#/help` 不是 hash 路由而是无效锚点，点击后仅改变 hash，页面不跳转 —— 全局可见的两个浮动帮助按钮都是死链（用户在任意页面点帮助都无反应）。
5. `[高]` 菜单保存契约不匹配，「菜单管理」必然失败（前端 `api/menu.ts:66` 发 `{ items: [{ menu_key, … }] }`，后端 `backend/xianyu_hunter/web/routes/api_menu.py:28-39` 要求 `{ menus: [{ key, visible, sort_order }] }`；调用点 `pages/MenuAdmin/index.tsx:117-133`）—— PUT 必返 422，`MenuAdmin/index.tsx:138-141` 虽显示错误但用户不知道「改可见性/排序」这件事在本系统里根本存不下去 —— 菜单个性化功能形同不存在。
6. `[高]` 隐藏后的菜单项再也找不回（`menu_manager.py:207` `merged = [m for m in merged if m["visible"]]`，GET 直接过滤隐藏项；而 MenuAdmin 与侧栏都基于这份数据）—— 用户隐藏一个菜单后，菜单管理页面里也看不到它，无法单独恢复，只能「重置全部」（`api/menu.ts:69`）从而丢掉其他自定义 —— 误隐藏即不可逆（局部不可逆操作）。
7. `[高]` 告警轮询失败被静默吞掉（`MainLayout.tsx:180-182` `.catch(() =&gt; {})`，Badge 见 `:603`）—— 拉取告警失败时 Badge 停在 0，用户以为「一切正常」，实际可能连续抢单失败/被反爬拦截 —— 「错误被静默吞掉导致用户以为成功」；抽屉本身还有永久加载态（`:756-758` 失败后一直 `&lt;Spin/&gt;`，无结束、无重试）。
8. `[中]` 告警抽屉条目不可点、出口指向存疑（`MainLayout.tsx:664-759`：条目无 `onClick`，`:753` 的「查看全部」`&lt;Link to="/orders"&gt;` 指向抢单记录而非通知中心 `/notifications`）—— 看到告警却无法就地处理，必须先去另一个页面 —— 增加完成任务步数且易误解告警含义。
9. `[中]` 面包屑前缀匹配取插入序首个 key（`MainLayout.tsx:341-352` 遍历 `ROUTE_LABELS` 做 `startsWith`，而 `ROUTE_LABELS` 里 `'/logs'` 在 `'/logs/errors'` 之前、`'/maintenance'` 在 `'/maintenance/db'` 之前、`'/'` 匹配一切，`:56-84`）—— `/logs/errors` 显示「实时日志」、`/maintenance/db` 显示「系统清理」、`/confirm-buy` 与 `/menu-admin` 显示「仪表盘」—— 用户被误导到错误的心智位置（术语混乱致误解）。
10. `[中]` 键盘助记 `g` 序列不可发现且防护不足（`MainLayout.tsx:118-128` 定义 9 条，无任何 UI 呈现；`COMMAND_ITEMS` 与 `components/Chatbot/HelpCenterModal.tsx` 的快捷键表都不含；监听处 `:259`、`:278-284` 仅排除 `INPUT/TEXTAREA/SELECT`）—— 一是没人知道能用，二是 IME 合成态或非 input 的可编辑区里按 `g` 会意外跳到仪表盘/客服 —— 与输入法/浏览器行为竞争。
11. `[中]` 命令面板覆盖不全且只搜中文（`MainLayout.tsx:88-115` 共 26 项，缺 registry 里可见的 `/maintenance/tunnel`，也缺 `/maintenance/vector`、`/confirm-buy`、`/menu-admin`、`/tasks/new`；匹配逻辑 `:474` 只对中文 `label` 做子串）—— 搜 `export`、`csv`、`log`、`cookie` 一律不命中；菜单里能看到的页面在命令面板里找不到 —— 高频用户的快捷入口不可靠。
12. `[中]` 页签栏缺少管理动作（`SheetTabs.tsx` 全文 365 行：无新增页签入口、无右键菜单、无溢出下拉、无「关闭其他/关闭全部」；`closeAll` 仅在切号/登出路径调用；竖向标签容器 `:293-308`，竖排标题 `writingMode:'vertical-rl'` + `maxHeight:80`（`:234-244`））—— 打开 8 个页签后只能逐个点 ×，7 字以上标题被截断；用户无法批量腾出容量，进而更易命中问题 3 的锁死。
13. `[中]` 页签身份包含 query（`useSheetSync.ts:37` `path = pathname + search`、`sheetStore.ts:314` `s.path === path`）—— 同一页面换个筛选条件就生成多个同名同图标的页签（「商品列表 ×5」），且每个都是独立组件实例 —— 页签栏迅速填满，用户分不清哪个是哪个。
14. `[中]` 回收栈不可恢复（`SheetPreferences.tsx:76-109` 回收列表为纯文本无「恢复」按钮；`sheetStore.ts:527-529` `replacedHistory` 不持久化；`sheetNotifications.tsx:25-53` 撤销窗口仅 5 秒）—— 误关页签 5 秒后永久找不回，刷新也不在 —— 用户只能从菜单重新进入并重建所有筛选（与问题 2 叠加放大损失）。
15. `[中]` 菜单加载/刷新期间的交互死角：`openKeys` 仅在挂载时初始化（`MainLayout.tsx:339`），`useMenuConfig.tsx:101-102` 有 5 分钟模块缓存；`MenuAdmin` 保存成功后未调用 `refresh/invalidateMenuCache` —— 改完菜单侧栏最长 5 分钟不变，且新出现的分组默认折叠，用户以为改动没生效。
16. `[中]` 单项分组被摊平、分组图标借用首项（`useMenuConfig.tsx:150-156` 分组内只有一项时直接升为顶层项，`:162` 分组图标取该组第一个子项的 `icon`）—— 「其他」分组显示为聊天气泡图标；隐藏掉分组里的一项后整个分组标题消失、层级视觉突变 —— 侧栏结构不可预测。
17. `[中]` 移动端与桌面端路径体系整体漂移且存在孤儿路由（`frontend/src/mobile/routes.tsx` 用 `/m/error-logs/`、`/m/tasks/new` 等约 11 组与桌面完全不同的路径名；`components/TabBar.tsx:16-22` 仅 5 项，`pages/Dashboard/index.tsx:16-35` 提供 16 个快捷入口但不含 `/m/timeline/`、`/m/anticrawl/`、`/m/items/`、`/m/evaluations/`）—— 这些页面在移动端无入口（收藏/深链可达但不可发现），且移动端没有任何帮助文档入口；同一条链接在手机与电脑打开的是两个不同页面。
18. `[中]` 首次引导门禁大面积失效：8 个页面根元素缺 `className="page-container"`（`pages/About/index.tsx`、`pages/Export/index.tsx:203`、`pages/Chatbot/index.tsx:871`、`pages/Help/index.tsx`、`pages/ConfirmBuy/index.tsx`、`pages/MenuAdmin/index.tsx`、`pages/AntiCrawl`、`pages/PriceDashboard`），而 `guides/menuGuides.ts`（201 行）已为其中 5 个写好引导内容；`guides/GuideController.tsx:94` 检查不到容器即放弃高亮 —— 已投入编写的引导对「其他」组三个页面全部永不触发。
19. `[低]` 登录态壳层体验：`MainLayout.tsx:382-388` 未登录时只渲染全屏 Spin（无「去登录」「服务是否正常」提示），`:365-370` 的 redirect 与 `sheetStore.ts:484-530 hydrate()` 的先后关系决定落地页签（登录后 redirect 与恢复上次页签互相覆盖，需实测确认）；`sheetStore.ts:532-548` 300ms 防抖写 localStorage，快速关闭多个页签后刷新可能回退一步。
20. `[低]` 懒加载兜底文案与站点语气不符：`utils/lazyRetry.tsx:101-121` 失败时显示「页面加载失败，请重试。」+「刷新页面」裸按钮（自定义样式，非 AntD），且 `retryImport`（`:48-53`）在最终失败时静默 `location.reload()` —— 会打断用户未提交的表单；`SheetContent.tsx:23-29` 的 `NotFoundSheet` 分支在现有 store 逻辑下实际不可达。

#### 优化建议（与编号对应）
1. `MainLayout.tsx:172` 接住 `error`，菜单区渲染 `Result status=warning` +「重新加载菜单」按钮；`useMenuConfig` 首次失败时用 registry 的内置快照兜底渲染（成本：低）。
2. 要么真正保活（`SheetContent` 渲染全部 sheet、非激活项 `display:none`，并对重页加懒激活），要么把 `SheetPreferences.tsx:119-125` 的「保留页面状态」文案改为「最小化仅记录位置，切回会重新加载」；同时对含未保存编辑的页签在关闭/替换前 `Modal.confirm`（成本：中）。
3. `sheetNotifications.tsx` 对 `reason==='limit'` 与 `'not_found'` 都发可见通知（「页签已达上限（10），请关闭一个再打开」并直接打开偏好抽屉），`useSheetSync` 顶回 URL 前先 toast；`SheetTabs.tsx` 增「关闭其他/关闭全部 + 溢出下拉」（成本：中）。
4. 两处 `href="#/help"` 改为 `onClick={() =&gt; navigate('/help')}`（成本：低）。
5. 前后端契约统一：要么后端 `api_menu.py:28-39` 接 `items/menu_key` 并支持 `group/custom_label`，要么前端 `api/menu.ts:66` 改发 `{menus:[{key,…}]}`；并加一条集成测试覆盖 PUT（成本：低）。
6. `menu_manager.py:207` 的过滤改为按调用方区分：`/api/menu?include_hidden=true` 供菜单管理页使用，侧栏仍过滤（成本：低）。
7. 告警轮询失败时 Badge 变灰并加 tooltip「告警获取失败」，抽屉补错误态 + 重试；同时给轮询加指数退避（成本：低）。
8. 抽屉条目 `onClick` 直达对应告警页签，「查看全部」改指 `/notifications`（成本：低）。
9. 面包屑匹配改为「最长前缀优先」（按 key 长度降序），并为 `/confirm-buy`、`/menu-admin`、`/onboarding`、`/tasks/:id` 补 `ROUTE_LABELS`（成本：低）。
10. 助记序列在命令面板底部常驻一行说明（`g` + `d/t/o/e/i/c/l/a/m`），并在 `menuGuides.ts`/Help 快捷键表里同步；监听加 `e.isComposing` 与 `contenteditable` 排除，`g` 需 800ms 内二段式（成本：低）。
11. `COMMAND_ITEMS` 由 `sheetRegistry` + `menu_registry.yaml` 单一来源派生（去掉手写第二份），搜索匹配 `label + path + 英文别名`（成本：中）。
12. 页签栏补：新增（最近页面下拉）、右键菜单（关闭/关闭其他/关闭全部/固定）、溢出 `⋯` 下拉、竖向标题 `maxHeight` 放宽并加 tooltip（成本：中）。
13. 页签身份改为 `pathname`（query 只作为「激活时的当前视图」），同 pathname 复用页签并只更新 search；`sheetStore.ts:314` 相应调整（成本：中）。
14. `SheetPreferences.tsx:76-109` 回收列表每项加「恢复」按钮，撤销窗口延长到 10s 并支持 `Ctrl+Shift+T`；`replacedHistory` 持久化（成本：低）。
15. 抽 `invalidateMenuCache()`，`MenuAdmin` 保存成功后调用并 `message.success('菜单已更新')`；`openKeys` 改为菜单数据变化时按当前激活路径回填（成本：低）。
16. 分组始终渲染 SubMenu（单项不摊平），分组图标用 registry 显式的 `group_icon` 字段（或 `MENU_GROUP_LABELS` 旁配图标表），去掉「取首项图标」（成本：低）。
17. 移动端与桌面共用一套 path 常量表（集中 `routes.ts`），把 `/m/timeline`、`/m/items`、`/m/evaluations`、`/m/anticrawl` 纳入 TabBar 或 Dashboard 快捷入口，并给移动端加帮助入口（成本：中）。
18. 8 个页面根元素统一加 `className="page-container"`（可做成 `&lt;PageContainer&gt;` 布局组件），并补 `/chatbot`、`/about`、`/help`、`/confirm-buy`、`/onboarding` 的 `menuGuides` 条目（成本：低）。
19. 未登录壳层显示「需要登录」+ 按钮；明确登录后 redirect 优先于页签恢复并写入文档注释（成本：低）。
20. `lazyRetry` 刷新前改为「重试」按钮，不自动 `location.reload()`；兜底 UI 用 AntD `Result`；删除不可达的 `NotFoundSheet` 或让其真正生效（成本：低）。

#### 四处菜单定义源 label / 图标 / 分组完整漂移对照表

图例：`—` = 该处不存在该项。registry 列的「分组」取 `category` 值（`config/menu_registry.yaml`），其余三处依次为 `sheetRegistry.tsx:51-87`、`MainLayout.tsx:55-85`、`MainLayout.tsx:88-115`。

| path | registry key / label / icon / category | sheetRegistry title / icon | ROUTE_LABELS | COMMAND_ITEMS label / icon | 漂移结论 |
|---|---|---|---|---|---|
| `/` | dashboard / 仪表盘 / DashboardOutlined / overview | 仪表盘 / DashboardOutlined | 仪表盘 | 仪表盘 / DashboardOutlined | 一致 |
| `/tasks` | tasks / 任务管理 / UnorderedListOutlined / data_view | 任务管理 / UnorderedListOutlined | 任务管理 | 任务管理 / UnorderedListOutlined | 一致 |
| `/tasks/new` | — | 新建任务 / UnorderedListOutlined | 新建任务 | — | 仅壳层有，无菜单、命令面板不可达 |
| `/tasks/:id` | — | 任务详情 / UnorderedListOutlined | — | — | 面包屑落到 `'/'` → 显示「仪表盘」 |
| `/tasks/:id/edit` | — | 编辑任务 / UnorderedListOutlined | — | — | 同上 |
| `/items` | items / **商品中心** / ShoppingOutlined / data_view | **商品列表** / ShoppingOutlined | **商品列表** | **商品列表** / ShoppingOutlined | registry 与其余三处不同名（1 vs 3） |
| `/evaluations` | evaluations / **卖家评估** / AuditOutlined / data_view | **评估明细** / AuditOutlined | **评估明细** | **评估明细** / AuditOutlined | registry 与其余三处不同名 |
| `/orders` | orders / 抢单记录 / ThunderboltOutlined / data_view | 抢单记录 / ThunderboltOutlined | 抢单记录 | 抢单记录 / ThunderboltOutlined | 文案一致，图标与 `/confirm-buy` 撞车 |
| `/timeline` | timeline / 事件时间线 / FieldTimeOutlined / data_view | 事件时间线 / FieldTimeOutlined | 事件时间线 | 事件时间线 / FieldTimeOutlined | 一致 |
| `/logs` | logs / 实时日志 / FileTextOutlined / data_view | 实时日志 / FileTextOutlined | 实时日志 | 实时日志 / FileTextOutlined | 一致 |
| `/logs/errors` | error_logs / 错误日志 / BugOutlined / data_view | 错误日志 / BugOutlined | 错误日志 | 错误日志 / BugOutlined | 文案一致；面包屑被 `'/logs'` 抢先匹配 → 显示「实时日志」 |
| `/notifications` | notifications / 通知中心 / BellOutlined / data_view | 通知中心 / BellOutlined | 通知中心 | 通知中心 / BellOutlined | 一致；与 `/config/notifier` 图标撞车 |
| `/price-dashboard` | price_dashboard / 价格行情 / DollarOutlined / data_view | 价格行情 / DollarOutlined | 价格行情 | 价格行情 / DollarOutlined | 一致；与 `/config/price` 图标撞车 |
| `/config/price` | price_strategy / 价格策略 / DollarOutlined / config | 价格策略 / DollarOutlined | 价格策略 | 价格策略 / DollarOutlined | key 名与 path 不同源（price_strategy↔/config/price）；图标撞车 |
| `/config/eval` | eval_rules / 评估规则 / SafetyCertificateOutlined / config | 评估规则 / SafetyCertificateOutlined | 评估规则 | 评估规则 / SafetyCertificateOutlined | 一致 |
| `/config/buyer` | buy_config / 抢单策略 / AimOutlined / config | 抢单策略 / AimOutlined | 抢单策略 | 抢单策略 / AimOutlined | 一致 |
| `/config/search` | search_config / 搜索参数 / SearchOutlined / config | 搜索参数 / SearchOutlined | 搜索参数 | 搜索参数 / SearchOutlined | 一致 |
| `/config/notifier` | notifier / 通知渠道 / BellOutlined / config | 通知渠道 / BellOutlined | 通知渠道 | 通知渠道 / BellOutlined | 一致；与 `/notifications` 图标撞车 |
| `/config/ai` | ai_config / AI 服务 / RobotOutlined / config | AI 服务 / RobotOutlined | AI 服务 | AI 服务 / RobotOutlined | 一致 |
| `/config/chatbot` | chatbot_config / 客服配置 / MessageOutlined / config | 客服配置 / MessageOutlined | 客服配置 | 客服配置 / MessageOutlined | 一致；与 `/chatbot` 图标撞车 |
| `/config/version` | version / 配置版本 / HistoryOutlined / config | 配置版本 / HistoryOutlined | 配置版本 | 配置版本 / HistoryOutlined | 一致 |
| `/maintenance` | maintenance / 系统清理 / ClearOutlined / maintenance | 系统清理 / ClearOutlined | 系统清理 | 系统清理 / ClearOutlined | 一致（分组名「系统维护」由前端 `MENU_GROUP_LABELS` 造词，见下） |
| `/maintenance/db` | db_admin / 数据库维护 / DatabaseOutlined / maintenance | 数据库维护 / DatabaseOutlined | 数据库维护 | 数据库维护 / DatabaseOutlined | 一致；面包屑被 `'/maintenance'` 抢先 → 显示「系统清理」；图标与 vector 撞车 |
| `/maintenance/vector` | — | 向量数据库维护 / DatabaseOutlined | 向量数据库维护 | — | 无菜单、命令面板不可达，仅能从深链进入 |
| `/maintenance/tunnel` | tunnel / 内网穿透 / GlobalOutlined / maintenance | 内网穿透 / GlobalOutlined | 内网穿透 | **—** | **registry 可见菜单在命令面板缺失**（唯一「能看见却搜不到」项） |
| `/batch-refresh` | batch_refresh / 批量采集 / CloudDownloadOutlined / maintenance | 批量采集 / CloudDownloadOutlined | 批量采集 | 批量采集 / CloudDownloadOutlined | 一致；图标与 `/export` 撞车 |
| `/anticrawl` | anticrawl / 反爬登录管理 / ExperimentOutlined / maintenance | 反爬登录管理 / ExperimentOutlined | 反爬登录管理 | 反爬登录管理 / ExperimentOutlined | 一致 |
| `/chatbot` | chatbot / **智能客服** / MessageOutlined / other | **智能客服对话** / MessageOutlined | **智能客服** | **智能客服对话** / MessageOutlined | **四处三种叫法**：侧栏「智能客服」、页签「智能客服对话」、命令面板「智能客服对话」 |
| `/export` | export / 数据导出 / CloudDownloadOutlined / other | 数据导出 / CloudDownloadOutlined | 数据导出 | 数据导出 / CloudDownloadOutlined | 文案一致；`sort_order` 302 跳号；图标撞车 |
| `/about` | about / 关于 / InfoCircleOutlined / other | 关于 / InfoCircleOutlined | 关于 | 关于 / InfoCircleOutlined | 一致；但 `menuGuides.ts` 无 `/about` 条目 |
| `/help` | **—（registry 完全没有）** | 帮助文档 / **BlockOutlined** | 帮助文档 | 帮助文档 / **QuestionCircleOutlined** | 无菜单项 + 顶栏按钮第三处入口；同一页面三处图标不统一 |
| `/confirm-buy` | — | 确认抢单 / ThunderboltOutlined | **—** | — | 深链页；面包屑显示「仪表盘」；图标与 `/orders` 撞车 |
| `/menu-admin` | — | 菜单管理 / SettingOutlined | **—** | — | 唯一入口为 `components/layout/AccountSwitcher.tsx:334`（下拉项 label 见 `:387`）；无面包屑、无命令面板 |
| `/onboarding` | — | **—（未注册）** | — | — | 仅 `App.tsx:92` 独立路由；入口 `pages/Dashboard/index.tsx:241`；脱离壳层 |

#### 双向缺口
- **registry 有 path 但未注册页面**：无。26 个 registry 项的 path **全部**存在于 `sheetRegistry.tsx`（这条链路是健康的）。
- **页面已注册但 registry 无菜单项（7 条，`sheetRegistry` 33 − registry 26）**：`/tasks/new`、`/tasks/:id`、`/tasks/:id/edit`、`/maintenance/vector`、`/confirm-buy`、`/menu-admin`、`/help`。其中 `/help`、`/maintenance/vector`、`/menu-admin` 是用户会主动找的常规功能，应补进 registry（`/help` 建议 `category: other`）；`/tasks/*`、`/confirm-buy` 属详情页可不进菜单但需补 `ROUTE_LABELS`；`/onboarding` 连 `sheetRegistry` 都缺。
- **命令面板缺口（`COMMAND_ITEMS` 26 项 vs `sheetRegistry` 33 项，缺 7）**：`/tasks/new`、`/tasks/:id`、`/tasks/:id/edit`、`/maintenance/vector`、`/maintenance/tunnel`（registry 可见）、`/confirm-buy`、`/menu-admin`。
- **面包屑缺口**：`/tasks/:id`、`/tasks/:id/edit`、`/confirm-buy`、`/menu-admin`、`/onboarding` 不在 `ROUTE_LABELS`，因 `'/': '仪表盘'` 参与前缀匹配而统一显示「仪表盘」（`MainLayout.tsx:341-352` + `:56`）。
- **引导缺口**：`menuGuides.ts`（201 行）缺 `/chatbot`、`/about`、`/help`、`/confirm-buy`、`/menu-admin`、`/onboarding`；`/export` 条目内容与实际功能不符（`:185`）。

#### `category` vs `group` 字段漂移（同一条数据五种叫法）
- YAML 源字段：`category`（`config/menu_registry.yaml:15` 等全部 26 项）。
- 后端输出：`category`（`backend/xianyu_hunter/web/services/menu_manager.py:185-197`，具体 `:190`）。
- 前端类型：`MenuItem.category`（`frontend/src/api/menu.ts:45`），但其上方注释写「对应 registry 的 **group** 字段」（`:44`），文件头注释亦称与「group 字段对齐」（`:3`、`:17`）—— 注释与真实字段名相反，registry 里根本没有 `group`。
- 更新载荷：`MenuItemUpdate.group` + `custom_label`（`frontend/src/api/menu.ts:53-54`），但后端 PUT 模型 `api_menu.py:28-39` 只有 `key/visible/sort_order` —— 「改分组」「自定义名称」两个能力在后端**不存在**，`menu_manager.py:185-197` 也不输出 `custom_label`（而 `api/menu.ts:34` 注释声称 label「已合并 custom_label」）。
- 存储层：数据库列名又是第三个名字 `group_name`（`menu_manager.py:237-238`）。
- 分组中文名：由前端字典 `MENU_GROUP_LABELS`（`api/menu.ts:18-26`）生成，`maintenance` 显示「系统维护」而 registry 注释与 `/maintenance` 菜单标签都是「系统清理」，两套语义挤在同一分组名下；联合类型还含 `main`/`system`（`:13-14`）与字典项「主要功能/系统」（`:24-25`），registry 中无任何条目使用 —— 死分支。
- 建议：一条链统一为 `group`（YAML → 后端 → 前端 → DB），或统一为 `category`；同时二选一实现或删掉 `custom_label`/`group` 更新能力，并让注释随字段名一起改（成本：低，但需一次前后端同批发布）。

#### 图标重复撞车清单（同一 icon 被多个入口共用）
- `UnorderedListOutlined`：`/tasks`、`/tasks/new`、`/tasks/:id`、`/tasks/:id/edit`（`menu_registry.yaml:20`、`sheetRegistry.tsx:53-56`）—— 任务类四个页签视觉完全相同。
- `DollarOutlined`：`price_dashboard`（`menu_registry.yaml:76`）、`price_strategy`（`:85`），另见 `MainLayout.tsx:97,98` —— 「价格行情」与「价格策略」在侧栏与命令面板里不可分辨。
- `BellOutlined`：`notifications`（`:69`）、`notifier`（`:113`），另见 `MainLayout.tsx:102,114` —— 「通知中心」与「通知渠道」撞车，且前者是数据页、后者是配置页。
- `MessageOutlined`：`chatbot_config`（`:127`）、`chatbot`（`:180`），`MainLayout.tsx:110`、`sheetRegistry.tsx:70,83` —— 两个客服入口同图标；由于 `useMenuConfig.tsx:162`「分组图标取首项图标」，「其他」分组的图标也是聊天气泡。
- `CloudDownloadOutlined`：`batch_refresh`（`:157`）、`export`（`:187`），`MainLayout.tsx:107,113`、`sheetRegistry.tsx:75,85` —— 「批量采集」与「数据导出」在侧栏与页签栏均同图标。
- `DatabaseOutlined`：`db_admin`（`:150`）、`/maintenance/vector`（`sheetRegistry.tsx:73`，仅壳层）—— 两个维护页同图标。
- `ThunderboltOutlined`：`orders`（`:41`）、`/confirm-buy`（`sheetRegistry.tsx:81`、`MainLayout.tsx:92`）—— 记录页与资金确认页同图标，误点风险叠加。
- `BlockOutlined` vs `QuestionCircleOutlined`：`/help` 在 `sheetRegistry.tsx:86` 用 `BlockOutlined`，`MainLayout.tsx:111` 与顶栏按钮用 `QuestionCircleOutlined` —— 同一页面两处不同图标（`BlockOutlined` 语义亦与帮助无关）。
- `AppstoreOutlined`：作为未知图标名的兜底值（`useMenuConfig.tsx:45-49` 的 iconMap 兜底），一旦 registry 写错图标名，用户看到的是无意义的九宫格且无任何告警 —— 建议出错时保留可辨识占位并在开发环境 console.warn（成本：低）。
- 建议：以 `sheetRegistry` + registry 为单一来源做一次图标盘点，规定「同一 icon 最多 2 处且必须同域」，并为撞车项改语义化图标（如 `price_dashboard` → `LineChartOutlined`、`notifications` → `NotificationOutlined`、`export` → `FileExcelOutlined`、`confirm-buy` → `PayCircleOutlined`、`vector` → `ApartmentOutlined`）（成本：低）。

#### 优先级总览（壳层）
高 ×7：菜单加载静默失败（`MainLayout.tsx:172`）、页签「保留状态」承诺落空（`SheetPreferences.tsx:119-125` vs `SheetContent.tsx:33-56`）、栈满导航锁死且零提示（`sheetStore.ts:320-336` + `sheetNotifications.tsx:25-53` + `useSheetSync.ts:40-45`）、浮动帮助按钮死链（`GuideController.tsx:167,187`）、菜单保存契约不匹配必 422（`api/menu.ts:66` vs `api_menu.py:28-39`）、隐藏菜单不可恢复（`menu_manager.py:207`）、告警轮询失败静默归零（`MainLayout.tsx:180-182`）。
中 ×13：面包屑前缀抢匹配、`g` 助记不可发现且 IME 误触、命令面板覆盖/检索不足、页签无批量管理与溢出、页签身份含 query、回收栈不可恢复、菜单缓存 5 分钟不失效、分组摊平与图标借用、移动端路径漂移与孤儿路由、`page-container` 缺失致引导永不触发等。
低 ×2 及上述图标/字段治理项。

**「首次使用」与「高频操作」哪个更痛的结论**：首次使用的痛集中在 `/onboarding`（错误命令）、`/login`（四选一 + 无出口）、`/chatbot`（发了没回复）与 `/about`（占位链接）—— 新用户第一小时内几乎必然踩到其中 2 项；高频操作的痛集中在壳层—— 页签切回丢状态、菜单改不动、告警被吞、命令面板搜不到、深链页签显示「仪表盘」。两类痛互不重叠，因此修复顺序应先是壳层的 3 个「静默失败」（P0-1/P0-3/P0-7）与登录页 2 个 高（凭证明文、无确认杀浏览器），再补引导页命令与「关于」外链，最后做四处定义源的归一化（label/icon/分组单源化）。

---

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
| G3 | 实时日志 | `LEVEL_COLOR` 键为大写、后端返回小写 → ERROR 行恒灰（同页直方图也失效（见 §8 交叉校验：`'err'.toUpperCase()='ERR'` 不在 `{ERROR,WARNING,INFO,DEBUG}` 键内，有错也显示「ERROR 0」；原写“恰好正常”已据他报 2.7-2 更正）） | `constants/logLevels.ts:3-8` vs `routes/api_logs.py:177-180,194` + `Logs.tsx:279,315` | 低 |

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

---

## 8. 与另一路已交付报告的交叉校验

> 本节由**并行的第二路评审**追加，不改动上方原回传内容。
> 第二路线：5 个并行切片做**纯源码走查**（未启动应用、未改动任何 xianyu 文件），产出 289 条（高 64 / 中 145 / 低 80）。
> 第二路交付物：`D:\code\otherProjects\20_News\_validate\ux_t02324\T02324_ux_review.md`（217,864 B / 1,220 行，含逐菜单表 + §6 四处菜单定义源完整漂移对照表 + §7 汇总优先级矩阵）。
> 比对基准：`17_xianyu/docs/requirements/2026-10-17-逐菜单UX评审与优化建议.md`（commit `28909370` + `58f42d9c`，200 条 / P0 53）。

### 8.1 两路重合度（结论一致性）

| 口径 | 数值 |
|---|---|
| 我的 64 条高 → 他报已列为 P0 | **33 条**（逐条编号可对应） |
| 我的 64 条高 → 他报列为 P1/P2（优先级分歧） | **11 条** |
| 我的 64 条高 → 他报无对应条目 | **20 条**（下表二，其中 13 条已代码复验） |
| 他报 53 条 P0 → 我的走查未覆盖 | **13 条**（下表三） |

两路对**六大系统性根因**的判断一致：静默失败、脏检查失效、确认范式三套并存、深链不消费、引导文案漂移、菜单多源漂移。他报的 §3.9/§4.14/N 系列与我的 §3 跨页共性/§4.1/§6 壳层节互为独立复现，可视为对同一批结论的双重确认。

### 8.2 仅第二路发现的缺陷（已逐条回读源码复验）

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

### 8.3 仅原报告发现的缺陷（第二路源码走查的盲区，已抽验 2 条为真）

- **2.11-1** `exportApi.buildUrl` 返回 `/api/export/<dataset>` **未加 `API_BASE`**（`api/export.ts:56`），`download` 又用 `location.href` 直跳（`:60-62`）——已复验为真；这条比我记录的 A16（无条件报"正在导出"）更根本。
- **4.5-1** 「可用策略」5 个 Tag 纯展示不可点，`anticrawlApi.setStrategy`（`api/anticrawl.ts:156`）**全仓零调用**——已复验为真（调用点只有同名局部 setter）。
- 其余 11 条属"必须跑起来才看得见"或跨字段语义类：2.4-2 未选任务对全库静默重算、2.7-2 有错仍显示「ERROR 0」、2.7-3 停止/暂停复用同一 `PauseCircleOutlined`、2.8-1 错误日志无聚合去重（真机 1,869 条多为同文重复）、4.1-2 dry-run 显示绿色「删除 0 条」、4.2-1 导入确认框写"请选择冲突处理"而 `mode` 恒 `'insert'`、4.2-2 导出忽略搜索条件、4.4-1 `running→idle` 无完成汇总、4.6-2 `handleStart` 忽略脏字段、4.10-1 保存后不失效菜单缓存、3.9-1 8 个配置页生效时机一律不明。
- 结论：**两路互补**——他报有真机截图（73 张 PNG）与运行时观测，我这条路对**前后端契约、字段级 falsy/兜底、跨页一致性**更敏感。

### 8.4 需要修正的交叉冲突（诚实记录）

`2.7-2`（他报 P0）与我的 `G3`（我判高）是**同一根因的两个症状**：后端 `events.level` 存小写缩写 `err`/`warn`/`info`（`api_logs.py:177-180` 注释 + `api_db_admin.py:620,714` 等实写值），前端两处都按大写全称查表——
- 行着色：`constants/logLevels.ts:3-8` 键为 `ERROR/WARNING/WARN/INFO/DEBUG`，`Logs.tsx:279,315` 用原始 `item.level` 查表 → ERROR 行恒灰（我的 G3，成立）；
- 级别分布：`Logs.tsx:131-141` 先 `toUpperCase()` 再查 `{ERROR,WARNING,INFO,DEBUG}`，`'err'→'ERR'` 不在键内 → 有错也显示「ERROR 0」（他报 2.7-2，成立）。

**我原先在实时日志节写的"同页直方图先 toUpperCase 恰好正常，反证是缺陷"这句推论是错的**，已据他报更正：直方图同样失效，且这条比我原来的推论更严重。修法合并为一条：在边界处统一归一化（后端返回前或前端 `normalizeLevel()`），并补 `err→ERROR`、`warn→WARNING` 别名表。

### 8.5 计数与口径差异（不影响结论）

- 他报按"优化点"计 200 条（P0 53/P1 111/P2 36），我按"可指认问题"计 289 条（高 64/中 145/低 80）——差在我把同一页面的多个字段级缺陷分条计（例如客服配置 `v && updateConfig` 我按 11 处出现点计 1 条但逐处列行号），以及我把壳层单列为 20 条。
- 他报 §7 自陈的取证盲区恰好是本次增量所在：§6-2 弹窗/抽屉内层未逐步进（→ C3、B7、A15 漏检）、§6-7 后端契约仅在矛盾点校验（→ P1、P2 漏检）。
- 两路均声明"注册菜单 26 项 + registry 外可达 6 页"，菜单口径一致。

### 8.6 建议（已建派生单 T02352）

1. 以他报为主文档（有真机取证），把上表二的 20 条并入其批次：契约类 2 条新建"后端契约全量核对"批，静默/文案类 12 条并入 T02337（P0∩XS），危害类 6 条并入 T02340（确认与危险文案）。已建派生单 T02352。
2. 排期上把 **P1（菜单保存恒 422）** 插到最前：它不是体验优化而是功能不可用，成本极低（改 1 个字段名 + 1 条集成测试断言），且能顺带暴露同类契约漂移。
3. `G3/2.7-2` 合并为一条修复，并在 §4.1 的"级别"处理上加一句边界归一化规范，避免第三处（导出/告警文案）再犯。
4. 本轮两路评审合计 489 条（去重后约 450），建议不再重复投入第三条走查路；后续以"修复 → 他报编号 + 我表二编号双引用"的验收单号制推进。

