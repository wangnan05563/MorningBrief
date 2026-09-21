/**
 * 全站引导配置（T00863）
 *
 * 结构：路由路径 -> 引导步骤数组
 * 每步：s 为目标元素选择器数组（取第一个存在者，避免元素未加载时引导中断），
 *      t 为标题，d 为说明文字。
 * 约束遵守：仅新增引导数据，不触碰各菜单路由与页面业务逻辑。
 */
export const GUIDE_STEPS = {
  '/review': [
    { s: ['.top-bar', '.page-container'], t: '内容审核', d: '这里按时间列出待审核节目，先看正文再决定是否放行。' },
    { s: ['.el-table'], t: '审核操作', d: '行内按钮可预览详情、通过或驳回；固定操作列在表格右侧，不随横向滚动。' },
    { s: ['.el-pagination'], t: '分页浏览', d: '待审核内容较多时分页查看，可调整每页条数。' },
  ],
  '/ads/materials': [
    { s: ['.top-bar', '.page-container'], t: '广告素材', d: '管理广告图文素材，支持上传、编辑与删除。' },
    { s: ['.el-table'], t: '素材列表', d: '素材名称与描述过长时会悬浮显示完整内容。' },
  ],
  '/ads/placements': [
    { s: ['.top-bar', '.page-container'], t: '投放规则', d: '配置广告位与投放日期，控制广告展示窗口。' },
    { s: ['.el-table'], t: '规则列表', d: '每条规则包含素材、广告位与起止日期。' },
  ],
  '/ads/schedule': [
    { s: ['.top-bar', '.page-container'], t: '排期日历', d: '以日历视角查看各广告位的投放排期。' },
    { s: ['.calendar', '.el-calendar', '.page-container'], t: '日历视图', d: '点击日期可查看当天排期详情。' },
  ],
  '/stats': [
    { s: ['.top-bar', '.page-container'], t: '数据统计', d: '平台核心指标总览，如节目数、播放量、素材池规模。' },
    { s: ['.metric-card', '.el-row', '.page-container'], t: '指标卡片', d: '关键指标以卡片形式呈现，方便一眼掌握运行状态。' },
  ],
  '/stats/channel-health': [
    { s: ['.top-bar', '.page-container'], t: '频道健康度', d: '各频道抓取与生成成功率，异常频道会高亮提示。' },
    { s: ['.el-table'], t: '健康列表', d: '按成功率排序查看，可定位需要关注的频道。' },
  ],
  '/stats/rss-health': [
    { s: ['.top-bar', '.page-container'], t: 'RSS 源状态', d: '每个 RSS 源的可达性与解析状态。' },
    { s: ['.el-table'], t: '源列表', d: '异常源会标注失败原因，便于排查。' },
  ],
  '/stats/llm-metrics': [
    { s: ['.top-bar', '.page-container'], t: 'LLM 重试指标', d: 'LLM 调用重试与命中率指标，评估模型服务稳定性。' },
    { s: ['.el-table'], t: '指标明细', d: '按模型/用途维度查看重试次数与重试字数。' },
  ],
  '/channels': [
    { s: ['.top-bar', '.page-container'], t: '频道管理', d: '管理播报频道：增删改查、启停与各类开关。' },
    { s: ['[aria-label="新增频道"]', '.top-bar .el-button'], t: '新增频道', d: '点击右上角新增按钮，按向导创建新频道。' },
    { s: ['.el-table'], t: '频道列表', d: '每行集中了频道的类型、开关与排序等配置。' },
  ],
  '/channels/material-library': [
    { s: ['.top-bar', '.page-container'], t: '素材库管理', d: '统一管理讲书稿素材：搜索、筛选、增删改查。' },
    { s: ['.el-table'], t: '素材列表', d: '标题列悬浮显示完整内容，支持按来源/分类筛选。' },
  ],
  '/channels/book-pool': [
    { s: ['.top-bar', '.page-container'], t: '讲书稿素材池', d: '按频道维护书单、排序与进度，支持从素材库一键加入。' },
    { s: ['.el-table'], t: '书单列表', d: '可调整书本顺序并跟踪每本书的进度状态。' },
  ],
  '/materials': [
    { s: ['.top-bar', '.page-container'], t: '素材录入', d: '通过文档上传、多输入渠道快速录入素材。' },
    { s: ['.el-upload', '.page-container'], t: '上传入口', d: '支持上传文档自动解析，也可直接粘贴内容。' },
  ],
  '/ebooks': [
    { s: ['.top-bar', '.page-container'], t: '找书工具', d: '检索电子书库，支持随机抽取 10 本作为选题参考。' },
    { s: ['.toolbar', '.top-bar'], t: '检索与随机', d: '输入关键词检索；点「随机」可一次抽取 10 本书名。' },
    { s: ['.el-table'], t: '结果列表', d: '命中书目与下载状态一目了然。' },
  ],
  '/queue': [
    { s: ['.top-bar', '.page-container'], t: '队列管理', d: '查看各频道生成任务队列，支持调整优先级与重试。' },
    { s: ['.el-table'], t: '任务列表', d: '可勾选多行进行批量操作，状态与耗时实时刷新。' },
  ],
  '/workflows': [
    { s: ['.top-bar', '.page-container'], t: '工作流监控', d: '跟踪各频道工作流执行进度，可手动触发一期工作流。' },
    { s: ['[aria-label="立即触发一期工作流"]', '.top-bar .el-button'], t: '手动触发', d: '点击触发按钮按频道生成新一期节目；跳过爬虫开关见工具提示。' },
    { s: ['.el-table'], t: '执行列表', d: '进度条展示各阶段完成度，支持展开查看明细。' },
  ],
  '/tunnel': [
    { s: ['.top-bar', '.page-container'], t: '内网穿透', d: '配置并启动隧道，将本地服务暴露到公网（Tailscale Funnel）。' },
    { s: ['.el-form', '.page-container'], t: '隧道配置', d: '填写令牌与路径后启动，页面会轮询更新公网地址与登录状态。' },
  ],
  '/ai-config': [
    { s: ['.top-bar', '.page-container'], t: 'AI 服务', d: '配置 LLM 服务商、模型与语音合成参数。' },
    { s: ['.el-form', '.page-container'], t: '服务商配置', d: '支持多服务商切换，密钥类字段不会写入本地草稿。' },
  ],
  '/ai-qa': [
    { s: ['.top-bar', '.page-container'], t: '智能助手', d: '基于知识库问答，可切换模型并选择会话来源。' },
    { s: ['.el-input', '.page-container'], t: '提问输入', d: '输入问题回车即可得到回答，开启自动刷新可跟随最新会话。' },
  ],
  '/cos-config': [
    { s: ['.top-bar', '.page-container'], t: '云端配置', d: '配置腾讯云 COS 访问密钥与存储桶，用于文件备份。' },
    { s: ['.el-form', '.page-container'], t: '密钥配置', d: '密钥类字段不会写入本地草稿，安全起见请手动填写。' },
  ],
  '/cos-files': [
    { s: ['.top-bar', '.page-container'], t: '文件管理', d: '浏览云端存储目录，支持上传、下载与删除文件。' },
    { s: ['.el-table'], t: '文件列表', d: '点击文件夹进入子目录，文件名过长时悬浮显示完整信息。' },
  ],
  '/notification': [
    { s: ['.top-bar', '.page-container'], t: '通知管理', d: '配置站内通知渠道：钉钉、企业微信、邮件等。' },
    { s: ['.el-form', '.page-container'], t: '渠道配置', d: '填写渠道回调地址即可在关键事件时收到推送。' },
  ],
  '/auto-review': [
    { s: ['.top-bar', '.page-container'], t: '自动审批', d: '配置自动审批规则，符合条件的节目免人工审核直接发布。' },
    { s: ['.el-table'], t: '规则与历史', d: '查看规则命中统计与执行历史，失败的记录可一键重试。' },
  ],
  '/tools/calculator': [
    { s: ['.top-bar', '.page-container'], t: '参数计算器', d: '计算各类业务参数，辅助运营决策。' },
    { s: ['.el-form', '.page-container'], t: '参数输入', d: '输入目标参数后自动计算结果。' },
  ],
  '/db-admin': [
    { s: ['.top-bar', '.page-container'], t: '数据库维护', d: '浏览表结构与数据，支持导出、导入与常用 SQL 操作。' },
    { s: ['.el-table'], t: '数据预览', d: '选择数据表后可导出 CSV/JSON，便于备份迁移。' },
  ],
  '/maintenance': [
    { s: ['.top-bar', '.page-container'], t: '系统清理', d: '清理过期数据与临时文件，释放磁盘空间。' },
    { s: ['.el-form', '.page-container'], t: '清理项', d: '勾选需要清理的项目后执行，注意不可恢复项会有提示。' },
  ],
  '/help': [
    { s: ['.top-bar', '.page-container'], t: '帮助文档', d: '平台使用说明与常见问题，按需查阅。' },
    { s: ['.el-table', '.page-container'], t: '文档列表', d: '点击条目展开对应文档说明。' },
  ],
  '/about': [
    { s: ['.top-bar', '.page-container'], t: '关于', d: '版本信息、开源声明与免责说明。' },
    { s: ['.card-soft', '.page-container'], t: '品牌信息', d: '查看当前版本与构建信息，可复制完整版本号。' },
  ],
}
