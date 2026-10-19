/**
 * 后端枚举 → 展示文案的唯一字典（FR-UX-405 / T02504）
 *
 * 约定：
 * 1. 键集合必须与 `backend/app/models/*.py` 里对应的 `class X(str, Enum)` 逐字一致。
 *    构建期门禁 `scripts/validate-nav.mjs` 会解析后端模型做双向比对（后端新增/字典漏配都 fail）。
 * 2. 页面不得再自建同族映射。门禁同时按「对象字面量的键 ⊂ 某枚举值集」拦截重复声明。
 *    —— 这正是「填了不显示」「列表与详情文案不一致」两个 bug 的机械成因。
 * 3. `channel_type` 不是模型 Enum（`Channel.channel_type` 是自由字符串列），无法由门禁比对模型，
 *    因此它的值集在本文件单点声明，页面一律走 `enumLabel(CHANNEL_TYPE, …)`。
 *
 * 字段：
 * - label 中文文案（列表 / 详情 / 下拉共用）
 * - type  el-tag 的 type
 * - badge 移动端 `.m-badge--*` 状态类（仅跨端展示的枚举提供）
 * - el    el-steps 的 status（仅工作流步骤）
 */

export const WORKFLOW_STATUS = {
  queued: { label: '排队中', type: 'info', badge: 'm-badge--info' },
  running: { label: '运行中', type: 'warning', badge: 'm-badge--warn' },
  success: { label: '成功', type: 'success', badge: 'm-badge--on' },
  failed: { label: '失败', type: 'danger', badge: 'm-badge--off' },
  cancelled: { label: '已取消', type: 'info', badge: 'm-badge--off' },
}

export const WORKFLOW_STEP_NAME = {
  crawl: { label: '爬虫采集' },
  rewrite: { label: 'LLM改写' },
  quality_check: { label: '质量审核' },
  tts: { label: '语音合成' },
  stitch: { label: '音频拼接' },
  review: { label: '创建审核' },
  publish: { label: '发布上线' },
}

export const WORKFLOW_STEP_STATUS = {
  pending: { label: '等待中', type: 'info', el: 'wait' },
  running: { label: '运行中', type: 'warning', el: 'process' },
  success: { label: '成功', type: 'success', el: 'success' },
  retrying: { label: '重试中', type: 'warning', el: 'process' },
  failed: { label: '失败', type: 'danger', el: 'error' },
}

export const WORKFLOW_SOURCE = {
  cron: { label: '定时', type: 'info' },
  manual: { label: '手动', type: 'warning' },
}

export const REVIEW_STATUS = {
  pending: { label: '待审核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已打回', type: 'danger' },
  replaced: { label: '已替换', type: 'info' },
}

export const MATERIAL_STATUS = {
  pending: { label: '待消费', type: 'info' },
  selected: { label: '已选题', type: 'success' },
  skipped: { label: '已跳过', type: 'warning' },
}

export const MATERIAL_MEDIA_TYPE = {
  text: { label: '文本', type: 'info' },
  image: { label: '图片', type: 'success' },
  video: { label: '视频', type: 'warning' },
}

export const MATERIAL_SOURCE_TYPE = {
  // 与录入渠道一一对应；下拉里需要完整说明，列表徽标用短标签
  list: { label: '书稿文档', long: '书稿文档（上传/手动录入）', type: 'primary' },
  cos: { label: '云端存储', long: '云端存储导入', type: 'info' },
  rss: { label: '资讯 RSS', type: 'info' },
  book_rss: { label: '书籍 RSS', long: '书籍 RSS 预制源', type: 'success' },
  api: { label: 'URL / API', long: 'URL / API 拉取', type: 'warning' },
  qrcode: { label: '二维码 / 链接', long: '二维码 / 链接分享', type: 'warning' },
}

export const AD_POSITION = {
  head: { label: '开头', type: 'success' },
  mid: { label: '中间', type: 'danger' },
  tail: { label: '结尾', type: 'info' },
}

export const CHANNEL_TYPE = {
  news: { label: '资讯', long: '资讯（默认）', type: 'info' },
  course: { label: '课程', type: 'success' },
  audiobook: { label: '有声读物', type: 'warning' },
}

export const ADMIN_ROLE = {
  admin: { label: '管理员', type: 'success' },
  operator: { label: '运营', type: 'info' },
}

/** 供构建期门禁比对：字典名 → 后端模型枚举类名（None = 非模型枚举，跳过比对） */
export const BACKEND_ENUM_OF = {
  WORKFLOW_STATUS: 'WorkflowStatus',
  WORKFLOW_STEP_NAME: 'WorkflowStepName',
  WORKFLOW_STEP_STATUS: 'WorkflowStepStatus',
  WORKFLOW_SOURCE: 'WorkflowSource',
  REVIEW_STATUS: 'ReviewStatus',
  MATERIAL_STATUS: 'MaterialStatus',
  MATERIAL_MEDIA_TYPE: 'MaterialMediaType',
  MATERIAL_SOURCE_TYPE: 'MaterialSourceType',
  AD_POSITION: 'AdPosition',
  ADMIN_ROLE: 'AdminRole',
  CHANNEL_TYPE: null,
}

export function enumLabel(dict, value, fallback = value) {
  if (value == null || value === '') return '-'
  return dict[value]?.label ?? fallback
}

/** 下拉/筛选用的完整文案（有 `long` 用 long，否则 label） */
export function enumOptionLabel(dict, value) {
  return dict[value]?.long ?? dict[value]?.label ?? value
}

export function enumTagType(dict, value, fallback = 'info') {
  return dict[value]?.type ?? fallback
}

export function enumBadge(dict, value, fallback = 'm-badge--info') {
  return dict[value]?.badge ?? fallback
}

export function enumStepStatus(dict, value, fallback = 'wait') {
  return dict[value]?.el ?? fallback
}

/** 枚举选项列表，顺序即字典声明顺序（与后端枚举定义顺序一致） */
export function enumOptions(dict) {
  return Object.keys(dict).map((value) => ({ value, label: enumOptionLabel(dict, value) }))
}
