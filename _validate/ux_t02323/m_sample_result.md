A18 | 确认 | VoiceSyncButton.vue:93-96 在请求失败时会马上把 meta 重置为内置状态，导致请求失败被误判为尚未同步。

B10 | 确认 | ReviewList.vue:218/255 的确认文案没有说明操作不可撤销；review_service.py:250 会拒绝重复处理。

B25 | 确认 | QueueManagement.vue:282-289 的筛选条件和分页只保存在组件内部，整个文件没有读取 route.query，刷新页面后就会丢失。

C106 | 确认 | BookFinder.vue:221 只弹出提示；ebooks.py:193 已返回 material_id，但前端未使用，所以无法跳转到对应素材。

C117 | 需修订 | 素材库确实没有导出功能（MaterialLibrary.vue:73-150），但建议与 C94 的多文件上传重复；应只做素材库按当前筛选导出 CSV、书单按 CSV 导入书名，并注明只匹配已入库的 source（book_pool_service.py:151）。

C24 | 确认 | resetForm 会把 form.id 设为 null（:714），于是 openCreate 中的 draft.id===form.id 永远为假（:760）；openEdit 也不会读取草稿。

C40 | 需修订 | tip 写「留空/0.15」，与 slider 的 0-1 范围冲突（:445-454）属实；但后端只在值非 None 时才写入（channel_service.py:191），所以勾选「继承全局」发送 null 不会生效，应增加 inherit 布尔字段并区分未提供与显式 null。

C52 | 确认 | MaterialLibrary.vue:73-150 两张表都没有 selection 列，只能逐行删除。

C67 | 需修订 | BookPool.vue:25 的下拉确实没有按类型过滤，但 script_mode 对任意频道都生效（crawler/runner.py:105-113），并非只对有声读物生效；应改为对非有声读物二次确认，并说明会按资讯风格改写（rewriter.py:53）。

C7 | 需修订 | 列表列显示「默认」，弹窗却写 05:00（:25-30/:193），这属实，但并没有全局配置接口，05:00 由 workflow_scheduler.py:394 硬编码；应共用常量并显示「默认 05:00」。

C81 | 确认 | BookPoolPanel.vue:9/50-51/64-66 混用了素材池、素材库和书单，以及素材 ID 等名称。

C94 | 确认 | CourseMaterials.vue:53 只设置了 limit=1，全文件没有 on-exceed 处理，第二次选择文件会被静默忽略。

D20 | 需修订 | fetchMaterials 没有 catch（:171-176），而 openCreateDialog 是等它执行完才打开弹窗（:178-182）；所以请求失败时弹窗根本不会打开，不是「下拉空白」。应把打开弹窗放进 finally，并在下拉框内显示「加载失败」和「重试」。

D38 | 需修订 | 页面级 v-loading 属实（:2），但 loadTrend（:156-158）没有 loading 状态，「两个请求共用 spinner」并不成立；应拆成两个 loading，并给趋势请求补 catch。

D53 | 需修订 | rangeDays 不持久化属实（:105/:169），但请求失败已有全局 ElMessage 提示（api/index.js:87-95），「无提示」不成立；只需保留持久化和局部 loading 重试。

D6 | 确认 | AdMaterials.vue:17-30 没有创建时间列，而 ad_service.py:52 已返回 created_at；列表也没有搜索功能。

D65 | 需修订 | stats.py:70-72 只写 WARNING 日志属实，但通知只支持 workflow 事件（sender.py:36-48），无法按建议「去通知管理配置 RSS 告警」；应改为仅记录日志，或者先补上该事件类型。

D83 | 需修订 | AdPlacements.vue:38 写「右上角新增规则」，但实际按钮在左上且名为「新建投放」（:4-10），AdMaterials.vue:52 也有同样问题，且报告对此没有给出建议；应只修改文案并补充日历空月引导。

E15 | 确认 | WorkflowDetail.vue:692-694/866-868 将异常一律置为 null，模板 :191/:318 因而显示「暂无」；script、review、stitch 面板没有刷新按钮。

F22 | 确认 | guideConfig.js:83-84 写的是「会话来源/跟随最新会话」，但实际页面每 90 秒刷新模型（KnowledgeQA.vue:278/474），且描述中的 .top-bar 不存在，真实页面是 .as-header。

F5 | 确认 | AIConfig.vue:1247-1263 应用预设、:1266-1280 保存后才配置都没有清空 llmTestResult，导致测试标签残留。

G9 | 确认 | config_service.py:100-102 只脱敏 secret 和 password，带 access_token 的 webhook 仍明文返回，而 NotificationConfig.vue:552 的注释却称已脱敏。

H11 | 确认 | CosFiles.vue:54-59 的 input 没有 multiple，:289 只取 files[0]，所以只弹一条 toast。

I21 | 确认 | Message.vue:49 固定 page:1/page_size:20，而后端已支持分页（mobile.py:52-57）。

I39 | 需修订 | tab 高 34px（:113）低于 44px，属实；但 375px 宽下每个 tab 约 80px，不会小于 60px或被截断；只保留增高，优先级从 M 降到 L。

I59 | 需修订 | 重定向属实（App.vue:44-50），但 ?mode=mobile 已实现并持久化（App.vue:20-29），原建议等同于现状；应改为提示一句并给出带 mode=mobile 的链接。

I6 | 确认 | ReviewList.vue:269 在 await load() 后重建列表（:200 将 expanded 置为 false），导致展开状态和滚动位置丢失。

J111 | 驳回 | 受保护 API 只在 about.js:110、detail.js:36、profile.js:19 使用，而这三个页面都已挂载 privacy-modal（about.json:3 等）；首页和搜索页没有此类调用，小程序也没有 app 级 WXML 容器。

J13 | 需修订 | history.wxml:34-38 的排序 chip 没有可见文字，属实；但已有动态 aria-label 和 88rpx 的触控区（wxss:399）；应降为 L，只在图标旁加「最新/最早」两个字。

J33 | 确认 | detail.json:2 固定为「节目详情」，detail.js 没有 setNavigationBarTitle，而 course.js:145 会动态设置标题。

J44 | 确认 | search.wxml:50-52 只有一句「未找到相关节目」，而类型筛选就在上方，另有 channels 页可以引导。

J58 | 确认 | download.wxml:49 的文本节点含字面 \n，而 WXML 不转义。

J75 | 驳回 | 两处排序实际一致：本地 unshift 让最新数据在前（local-data.js:180），后端 created_at desc（favorites.py:81）；按类型过滤是设计，而不是口径冲突。

J92 | 确认 | about.js:61-71 连续点 5 次版本号会打开服务器地址编辑，没有 envVersion 守卫。

M101 | 确认 | About.vue:252 列 edge-tts 6.1.10，与 requirements.txt:22 的 7.2.8 不符（清单实为 40 条）。

M13 | 需修订 | 顺序问题属实（AIConfig.vue:1578-1585），但 commitDraft 会清掉此前所有未保存编辑；应改为 toast「已带入，未保存保留为草稿」或提供恢复，优先级从 M 降到 L。

M30 | 需修订 | DatabaseAdmin.vue:334-335 将令牌直写在题面，属实；但让前端自动取用的一次性 nonce 构不成确认；应改为在界面固定输入 DELETE 或表名作为摩擦，后端令牌只由服务端配置。

M50 | 需修订 | 两个 Tab 共用 importContent 属实（:272-296），CSV 分支按逗号拆分（:608-615）会产生垃圾行；应拆成两个 v-model，或者切换 Tab 时清空并确认，删掉无关的 5000 行校验。

M66 | 需修订 | maintenance_service.py:769-771 预览没有排除活动日志，属实；但文件名是 MorningBrief_日期.log（logging_setup.py:226），不是 app.log，而且按 10MB 滚动使活动文件通常小于 10MB，所以「必然失败」不成立；应降为 L。

M86 | 确认 | Help.vue:304 写「清空已完成任务」，但队列页只有批量删除（QueueManagement.vue:95），也没有提到执行模式和并发配置。

统计：确认 22（A18、B10、B25、C106、C24、C52、C81、C94、D6、E15、F22、F5、G9、H11、I21、I6、J33、J44、J58、J92、M101、M86），需修订 16（C117、C40、C67、C7、D20、D38、D53、D65、D83、I39、I59、J13、M13、M30、M50、M66），驳回 2（J111、J75），已失效 0；报告中的目标文件都没有晚于报告提交 0bff87e 的修复。

三条最值得注意的判断：C67 建议「只列有声读物」与 crawler/runner.py:105-113 的既有设计相悖，照做会关掉受支持的通路；C40 的「继承全局」如果按原建议发 null，会被 channel_service.py:191 忽略，使勾选框变成死控件；D65 指向的通知管理没有 RSS 事件类型（sender.py:36-48），会引导用户走到死路。另外，J111 是典型误报：隐私弹窗覆盖已完整，问题无法在小程序架构内实现。