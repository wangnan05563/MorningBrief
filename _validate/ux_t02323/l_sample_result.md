路径相对 `apps/admin-web/src`（项目根 `D:\code\otherProjects\20_News`），均逐条打开源码复核。

A20|保留|Login.vue:145 硬跳 /review，守卫:315 丢原目标|独立
A3|剔除|Layout.vue:39 无面包屑；详情页已有返回|低收益
A9|剔除|router/index.js:8 注释与 96 后分组不符|非 UX
B5|保留|ReviewList.vue:102 空态写死「待审核」|独立
B20|剔除|ReviewDetail.vue:52 重复 key；后端已去重|风险不存在
C100|合并|CourseMaterials.vue:149 与 170 页签重叠|→C92
C28|剔除|ChannelManagement.vue:311 措辞粒度差|口味
C42|合并|ChannelManagement.vue:433 试听条撑高|→C37
C65|剔除|MaterialLibrary.vue:13 success 色|颜色口味
C8|剔除|ChannelManagement.vue:19 混排|扫读无碍
D27|剔除|AdSchedule.vue:5 双入口|仅多一次请求
D52|剔除|ChannelHealth.vue:51 缺量词|微文案
D72|剔除|LlmMetrics.vue:61 缺未改善段|可视化选择
E23|剔除|WorkflowDetail.vue:258 autoplay|符按钮语义
E8|保留|WorkflowList.vue:211 ID 纯文本|独立
F15|合并|AIConfig.vue:83 与 755 两套显隐|→F4
F27|保留|api/index.js:40 已弹，KnowledgeQA:346 再弹|去重主题锚点
G18|合并|AutoReviewConfig.vue:351 同错双 toast|→F27
G7|剔除|Tunnel.vue:619 config 可能空|实际不可达
H21|保留|CosFiles.vue:5 未配置无跳转|独立
I17|剔除|Home.vue:43 恒 true 死分支|代码清理
I32|剔除|ManageHome.vue:31 无危险色|视觉口味
I41|剔除|ManageFeedback.vue:42 无筛选|M 成本、低频
I58|已失效|ManageAlert.vue:53 已有二次确认|误报，真实缺陷见 I54
J18|剔除|history.wxml:129 已降透明+角标|已区分
J96|剔除|agreement.wxml:8 无目录|法律低频
M11|合并|ParamCalculator.vue:6 名称不符|→M1
M41|合并|DatabaseAdmin.vue:204 无效透传|→M16
M67|合并|Maintenance.vue:338 重复弹错|→F27
M91|剔除|Help.vue:31 不读 hash|低收益

统计：保留 5（17%）、合并 7（23%）、剔除 17（57%）、已失效 1（3%）。L 类仅约 1/6 值得单列，连同可并入项也只有 40% 可落地。建议 PRD 不单列 L 需求，改为一个「打磨清单」附录：只收 XS/S 且有可观察验收点（文案、跳转、默认 Tab）的条目，M 成本或纯视觉判断不进 PRD。关键发现：I58 为误报（确认弹窗已存在，真正问题是 I54 的 `v` 未定义）；B20 因后端图片去重不成立；G7 分支不可达；C42 受 C37（试听 404）阻塞。