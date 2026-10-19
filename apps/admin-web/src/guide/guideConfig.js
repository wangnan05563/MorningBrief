/**
 * 全站引导配置（T00863 → T02502 锚点契约改造）
 *
 * 结构：路由路径 -> 引导步骤数组
 * 每步：s 为目标元素选择器数组，t 为标题，d 为说明文字。
 *
 * T02502 起的选择器约定（构建期门禁 scripts/validate-nav.mjs 会校验）：
 * 1. 首选显式锚点：`[data-guide="x"]`（视图里显式打的稳定锚点）或 `[aria-label="x"]`（组件自带的可访问名）。
 * 2. **禁止位置兜底**（如 `.top-bar .el-button`）：兜底选择器在真实锚点缺失时会静默命中
 *    另一个元素，T02500 抓到的「引导指错元素」就是这么藏住的——宁可让这一步落空
 *    （浮层会带 data-guide-missing 标记，门禁与审计都能发现），也不要指错。
 * 3. 每步只写一个选择器：多选择器兜底链会把上一步的错指藏到下一步底下。
 * 4. 裸类只放行「全页唯一」的布局类（`.page-container` 等，清单见 validate-nav.mjs 的
 *    PAGE_UNIQUE_CLASSES）；`.el-table` 这类同页可能有多个实例（带弹窗表格的页面）必须打 data-guide。
 * 5. 文案必须与被锚定的元素一致：锚点是卡片列表就不要写「表格」，锚点是搜索表单就不要写「工具栏」。
 */
export const GUIDE_STEPS = {
  '/review': [
    { s: ['[data-guide="review-page"]'], t: '内容审核', d: '这里按时间列出待审核节目，先看正文再决定是否放行。' },
    { s: ['[data-guide="review-table"]'], t: '审核列表', d: '状态列显示待审核/已通过/已打回/已替换，行内按钮进入详情处理。' },
    { s: ['[data-guide="review-pagination"]'], t: '分页浏览', d: '待审核内容较多时分页查看，可调整每页条数。' },
  ],
  '/ads/materials': [
    { s: ['[data-guide="ads-materials-page"]'], t: '广告素材', d: '管理广告图文素材，支持上传、编辑与删除。' },
    { s: ['[data-guide="ads-materials-table"]'], t: '素材列表', d: '素材名称与描述过长时会悬浮显示完整内容。' },
  ],
  '/ads/placements': [
    { s: ['[data-guide="ads-placements-page"]'], t: '投放规则', d: '配置广告位与投放日期，控制广告展示窗口。' },
    { s: ['[data-guide="ads-placements-table"]'], t: '规则列表', d: '每条规则包含素材、广告位与起止日期。' },
  ],
  '/ads/schedule': [
    { s: ['[data-guide="ads-schedule-page"]'], t: '排期日历', d: '以日历视角查看各广告位的投放排期。' },
    { s: ['[data-guide="ads-schedule-calendar"]'], t: '日历视图', d: '点击日期可查看当天排期详情。' },
  ],
  '/stats': [
    { s: ['[data-guide="stats-page"]'], t: '数据统计', d: '平台核心指标总览，如节目数、播放量、素材池规模。' },
    { s: ['[data-guide="stats-metric-card"]'], t: '指标卡片', d: '关键指标以卡片形式呈现，方便一眼掌握运行状态。' },
  ],
  '/stats/channel-health': [
    { s: ['[data-guide="channel-health-page"]'], t: '频道健康度', d: '各频道抓取与生成成功率，异常频道会高亮提示。' },
    { s: ['[data-guide="channel-health-cards"]'], t: '频道卡片', d: '每个频道一张卡片，按成功率排列，便于定位需要关注的频道。' },
  ],
  '/stats/rss-health': [
    { s: ['[data-guide="rss-health-page"]'], t: 'RSS 源状态', d: '每个 RSS 源的可达性与解析状态。' },
    { s: ['[data-guide="rss-health-table"]'], t: '源列表', d: '异常源会标注失败原因，便于排查。' },
  ],
  '/stats/llm-metrics': [
    { s: ['[data-guide="llm-metrics-page"]'], t: 'LLM 重试指标', d: 'LLM 调用重试与命中率指标，评估模型服务稳定性。' },
    { s: ['[data-guide="llm-metrics-rates"]'], t: '重试率概览', d: '上方卡片是整体重试率，下方明细按模型/用途维度列出重试次数与字数。' },
  ],
  '/channels': [
    { s: ['[data-guide="channels-page"]'], t: '频道管理', d: '管理播报频道：增删改查、启停与各类开关。' },
    { s: ['[aria-label="新增频道"]'], t: '新增频道', d: '点击新增按钮，按向导创建新频道。' },
    { s: ['[data-guide="channels-table"]'], t: '频道列表', d: '每行集中了频道的类型、开关与排序等配置。' },
  ],
  '/channels/material-library': [
    { s: ['[data-guide="material-library-page"]'], t: '素材库管理', d: '统一管理讲书稿素材：搜索、筛选、增删改查。' },
    { s: ['[data-guide="material-library-table"]'], t: '素材列表', d: '标题列悬浮显示完整内容，支持按来源/分类筛选。' },
  ],
  '/channels/book-pool': [
    { s: ['[data-guide="book-pool-page"]'], t: '讲书稿素材池', d: '按频道维护书单、排序与进度，支持从素材库一键加入。' },
    { s: ['[data-guide="book-pool-channel"]'], t: '选择频道', d: '素材池、排序与进度都按所选频道独立配置，先选频道再看书单。' },
  ],
  '/materials': [
    // 该视图未打 data-guide（并发会话正在改这个文件），先用页面容器与上传组件自身的语义类锚定
    { s: ['.page-container'], t: '素材录入', d: '通过文档上传、多输入渠道快速录入素材。' },
    { s: ['.el-upload'], t: '上传入口', d: '支持上传文档自动解析，也可直接粘贴内容。' },
  ],
  '/ebooks': [
    { s: ['[data-guide="ebooks-page"]'], t: '找书工具', d: '检索电子书库，可随机抽取一批书目作为选题参考。' },
    { s: ['[data-guide="ebooks-search"]'], t: '检索与随机', d: '输入关键词点「检索」；点「随机」可随机抽取一批书目。' },
    { s: ['[data-guide="ebooks-results"]'], t: '结果列表', d: '命中书目与下载状态一目了然。' },
  ],
  '/queue': [
    { s: ['[data-guide="queue-page"]'], t: '队列管理', d: '查看各频道生成任务队列，支持调整优先级与重试。' },
    { s: ['[data-guide="queue-table"]'], t: '任务列表', d: '可勾选多行进行批量操作，状态与耗时实时刷新。' },
  ],
  '/workflows': [
    { s: ['[data-guide="workflows-page"]'], t: '工作流监控', d: '跟踪各频道工作流执行进度，可手动触发一期工作流。' },
    // 锚点必须是按钮真实的 aria-label：曾经写过 [aria-label="立即触发一期工作流"]，
    // 那是 tooltip 文案不是标签，永远选不中，于是退到 .top-bar .el-button 高亮了「刷新」（T02500 抓到）。
    { s: ['[aria-label="手动触发"]'], t: '手动触发', d: '点击触发按钮按频道生成新一期节目；跳过爬虫开关见工具提示。' },
    { s: ['[data-guide="workflows-table"]'], t: '执行列表', d: '进度条展示各阶段完成度，支持展开查看明细。' },
  ],
  '/tunnel': [
    { s: ['[data-guide="tunnel-page"]'], t: '内网穿透', d: '配置并启动隧道，将本地服务暴露到公网（Tailscale Funnel）。' },
    { s: ['[data-guide="tunnel-form"]'], t: '隧道配置', d: '填写令牌与路径后启动，页面会轮询更新公网地址与登录状态。' },
  ],
  '/ai-config': [
    { s: ['[data-guide="ai-config-page"]'], t: 'AI 服务', d: '配置 LLM 服务商、模型与语音合成参数。' },
    { s: ['[data-guide="ai-config-form"]'], t: '服务商配置', d: '支持多服务商切换，密钥类字段不会写入本地草稿。' },
  ],
  '/ai-qa': [
    { s: ['[data-guide="assistant-page"]'], t: '智能助手', d: '基于知识库问答，可切换模型并选择会话来源。' },
    { s: ['[data-guide="assistant-input"]'], t: '提问输入', d: '输入问题后 Enter 发送、Shift+Enter 换行；模型在上方选择。' },
  ],
  '/cos-config': [
    { s: ['[data-guide="cos-config-page"]'], t: '云端配置', d: '配置腾讯云 COS 访问密钥与存储桶，用于文件备份。' },
    { s: ['[data-guide="cos-config-form"]'], t: '密钥配置', d: '密钥类字段不会写入本地草稿，安全起见请手动填写。' },
  ],
  '/cos-files': [
    { s: ['[data-guide="cos-files-page"]'], t: '文件管理', d: '浏览云端存储目录，支持上传、下载与删除文件。' },
    { s: ['[data-guide="cos-files-table"]'], t: '文件列表', d: '点击文件夹进入子目录，文件名过长时悬浮显示完整信息。' },
  ],
  '/notification': [
    { s: ['[data-guide="notification-page"]'], t: '通知管理', d: '配置站内通知渠道：钉钉、企业微信、邮件等。' },
    { s: ['[data-guide="notification-form"]'], t: '渠道配置', d: '填写渠道回调地址即可在关键事件时收到推送。' },
  ],
  '/auto-review': [
    { s: ['[data-guide="auto-review-page"]'], t: '自动审批', d: '配置自动审批规则，符合条件的节目免人工审核直接发布。' },
    { s: ['[data-guide="auto-review-table"]'], t: '审批历史', d: '查看规则命中统计与执行历史，失败的记录可一键重试。' },
  ],
  '/tools/calculator': [
    { s: ['[data-guide="calculator-page"]'], t: '参数计算器', d: '计算各类业务参数，辅助运营决策。' },
    { s: ['[data-guide="calculator-inputs"]'], t: '参数输入', d: '调整时长/字数/倍率任一参数，其余参数与结果实时联动。' },
  ],
  '/db-admin': [
    { s: ['[data-guide="db-admin-page"]'], t: '数据库维护', d: '浏览表结构与数据，支持导出、导入与常用 SQL 操作。' },
    { s: ['[data-guide="db-admin-content"]'], t: '表数据区', d: '左侧选表后在右侧预览数据，可导出 CSV/JSON 便于备份迁移。' },
  ],
  '/maintenance': [
    { s: ['[data-guide="maintenance-page"]'], t: '系统清理', d: '清理过期数据与临时文件，释放磁盘空间。' },
    { s: ['[data-guide="maintenance-form"]'], t: '清理项', d: '勾选清理目标后执行，建议先用预览模式；不可恢复项会有提示。' },
  ],
  '/help': [
    { s: ['[data-guide="help-page"]'], t: '帮助文档', d: '平台使用说明与常见问题，按需查阅。' },
    { s: ['[data-guide="help-catalog"]'], t: '文档目录', d: '左侧目录点一条即跳到对应章节，也可先搜关键词。' },
    // T02502 / FR-UX-403：引导只弹一次，重放入口就在帮助页
    { s: ['[data-guide="help-replay"]'], t: '菜单引导重放', d: '想再看某个菜单的引导，点这里点对应菜单即可；也可清除全部引导记录恢复首访提示。' },
  ],
  '/about': [
    { s: ['[data-guide="about-page"]'], t: '关于', d: '版本信息、开源声明与免责说明。' },
    { s: ['[data-guide="about-brand"]'], t: '品牌信息', d: '查看当前版本与构建信息，可复制完整版本号。' },
  ],
}
