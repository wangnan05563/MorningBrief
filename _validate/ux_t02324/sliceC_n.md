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