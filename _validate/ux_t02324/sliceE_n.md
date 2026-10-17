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

### 全局壳层与共性问题

#### 现状描述
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