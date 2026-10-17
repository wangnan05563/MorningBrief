复核范围是 D:\code\otherProjects\20_News；以下路径都相对于该根目录。本次全程只读，相关文件在评审后没有新的提交，未发现“已失效”。

C5 | 需修订 | ChannelManagement.vue:675-684 确实只有 `try/finally`、:78 确实会落入空态，但 api/index.js:62-67 对非 silent 请求已弹错，“既不提示”不成立 | 应降为 M，改写为“失败后落入空态，容易被误判为无数据”，保留错误态+重试
C27 | 需修订 | BookPoolPanel.vue:186-187/244-256 是无用代码且无开关，独立菜单页 BookPool.vue:36 无法开启模式（开关仅在 ChannelManagement.vue:303-310） | 独立页用 prop 显示开关，嵌套弹窗不重复；切勿按建议删外层开关，否则 :317-322 的入口链会断
C68 | 需修订 | BookPool.vue:61-67 确实不校验频道，但 book_pool.py:60-61 返回 404 会弹错，空态文案也引错（BookPoolPanel.vue:76-78） | 应降为 M；补频道存在性回落与提示，删除“静默”说法
C103 | 确认 | BookFinder.vue:212-217 不传 channel_id，ebooks.py:186 落为 null；候选按 channel_id 过滤（book_pool_service.py:351-352），实际不在书单 | —
D24 | 确认 | AdSchedule.vue:96 后写覆盖前写；ad_service.py:141-172 无重叠校验，同日同位多投放只显示一条 | —
D45 | 确认 | ChannelHealth.vue:126-129 x/y 全部 `display:false`，各卡独立自适应，跨卡斜率不可比 | —
E1 | 确认 | WorkflowList.vue:340-373 无 catch、:356 silent，sse.js:150-154 仅 console，且无独立刷新入口 | —
G2 | 需修订 | Tunnel.vue:446-448 仅 console，但拦截器已 toast；真正风险在 :521-534 以默认空值提交，tunnel_service.py:249-261 无兜底 | 删“无任何提示”，保留 H，加载失败即禁用保存
I1 | 确认 | ReviewList.vue:154 单击即 act，:246-275 仅驳回有 prompt；reviews.py:145-149 approve 即发布 | —
I42 | 确认 | ManageChannels.vue:17-23/48-57 零确认；channel_service.py:237-238 停用即取消排队任务 | —
J5 | 确认 | floating-player.js:21-37/45-58 仅 attached 刷新、无 pageLifetimes，订阅只改 isPlaying，10 处复用页浮条不现 | —
J20 | 需修订 | profile.wxml:116-140 确有内嵌+整页重复，但 profile.js:631-636 下载/偏爱仅入口卡，“五项都双份”不实 | 应降为 M；只收敛最近/收藏/频道，勿要求全组件化
J32 | 需修订 | detail.wxml:15-18 无重试属实；“无缓存兜底”是常态非缺陷 | 应降为 M；只补重试按钮
J48 | 需修订 | 订阅(channels.wxml:54-62)与偏爱(preferred-settings.wxml:19-37)确易混，但偏爱页 :5 有说明，且只影响“我的偏爱”过滤(index.js:314-322)，非“排序没变” | 应降为 M；改述概念重复，合并仅列为可选项
J66 | 需修订 | 同上；preferred-settings.wxml:5 已自述作用，“不自述”不实，合并属产品重构 | 应降为 M
J77 | 需修订 | queue.wxml:8/detail.wxml:336 仅清空，queue.js:56 无单删/排序 | 缺功能非故障，应降为 M；拖拽非必需
J98 | 确认 | privacy.js:38 称退出即删，profile.js:709-712 只清本地，routers/api 无删除接口 | —
M2 | 确认 | ParamCalculator.vue:60-61/161-162/306-314 允许 60-1800s、0.5-2.5x；AIConfig.vue:1548/1557-1558 静默夹取，toast 仍称已同步 | —
M33 | 需修订 | db_admin_service.py:66-68 仅 workflow_step，maintenance_service.py:388-396 全链级联，确不一致；但 Help.vue:309-336 是工作流监控章节，无此承诺，承诺只在 :67 标签 | 应降为 M；只加“未声明下游不删”提示，勿在 DB 后台做全链删
M54 | 需修订 | DatabaseAdmin.vue 实为 views/maintenance/，:456-487 失败置空属实，但拦截器已 toast | 应降为 M；补错误态并禁用编辑/删除
M78 | 驳回 | WorkflowDetail.vue:325-340 底部已有“从指定步骤重跑”，:903 调 /retry，Help.vue:327 并非虚指 | 不写入 PRD，仅统一“重试/重跑”措辞
M94 | 需修订 | About.vue:313-335 失败落“已是最新”属实；但 backend/.env:18 已配 REPO_URL，“根本没工作”不成立，仅 GitHub 失败降级路径为真 | 保留 H，改述为“检查失败即报最新”

统计：确认 9 / 需修订 12 / 驳回 1 / 已失效 0。

最值得注意的三点：
1. **M78 是唯一明确误报**：详情页底部“从指定步骤重跑”已完整接通后端（WorkflowDetail.vue:325-340、:903），报告只看了顶部按钮。若照建议改帮助文档，会把正确说明改错。
2. **M94 前提错误**：backend/.env:18 实际配置了 REPO_URL，“更新检查根本没工作”不成立；真实缺陷只是降级路径（未配置/GitHub 失败）一律显示“已是最新”。
3. **11 条 H 需降级或改述**：C5/C27/C68/J20/J32/J48/J66/J77/M33/M54 多为 M 级；C5/G2 的“无任何提示”与拦截器行为相反（api/index.js:62-67），J48/J66 把“偏爱”误说成影响排序，实际是首页“我的偏爱”过滤（index.js:314-322）。
