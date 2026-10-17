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
