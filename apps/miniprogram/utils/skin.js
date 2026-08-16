/**
 * 频道类型 → 皮肤 / 文案 / 合规提示 映射（FR-MC-08 / FR-MC-11）
 *
 * 设计原则（NFR-MC-05）：业务类型与 UI 皮肤解耦。
 * 新增业务类型（如未来的 audiobook）只需在此加一个分支，不触碰播放内核。
 * 未知类型一律回退 news 皮肤 + 控制台告警（FR-MC-12 防御式兜底），避免崩溃。
 *
 * 所有文案不写死「今日要闻 / 新闻」，按类型取值，避免课程场景违和。
 */

// 客户端告警上报器（FR-MC-12 后续增强）：未知 channel_type 等 best-effort 上报
const { reportClientWarn } = require('./report');

// 频道类型 → 分组展示名（用于胶囊分组标题、搜索标签等）
const TYPE_LABELS = {
  news: '资讯',
  course: '课程',
  audiobook: '有声读物',
};

// 各类型皮肤：列表标题 / 空态文案 / 胶囊角标 / 默认封面
// 封面优先复用既有图标，避免引入二进制资源
const SKINS = {
  news: {
    listTitle: '今日节目',
    listEmptyTitle: '今日节目暂未上线',
    listEmptyDesc: '节目通常每天上午更新，下拉刷新试试或稍后再来看看～',
    pillBadge: '',
    defaultCover: '/images/icons/headphones.png',
  },
  course: {
    listTitle: '课程章节',
    listEmptyTitle: '课程章节尚未生成',
    listEmptyDesc: '课程正在制作中，敬请期待下一次更新～',
    pillBadge: '课',
    defaultCover: '/images/icons/headphones.png',
  },
  audiobook: {
    listTitle: '有声书章节',
    listEmptyTitle: '有声书章节尚未生成',
    listEmptyDesc: '有声书正在制作中，敬请期待～',
    pillBadge: '听',
    defaultCover: '/images/icons/headphones.png',
  },
};

// 合规提示文案（FR-MC-11）：按 disclaimer_level 分级
// none → 不展示；normal → 通用 AI 生成提示；strong → 医疗/法律/财经强提示
const DISCLAIMER_COPY = {
  none: '',
  normal: '本内容由 AI 生成，仅供学习参考，专业问题请咨询持证专业人士。',
  strong: '重要提示：本内容为 AI 生成，不构成专业建议。医疗 / 法律 / 财经等事项请务必咨询持证专业人士，并遵医嘱、遵法律。',
};

// 回退类型：未知或缺失一律按 news 处理（向后兼容存量频道）
const FALLBACK_TYPE = 'news';

/**
 * 归一化频道类型：非法 / 未知值回退 news
 * @param {string} type
 * @returns {string}
 */
function normalizeType(type) {
  if (!type || !SKINS[type]) {
    if (type && !SKINS[type]) {
      console.warn('[skin] 未知 channel_type:', type, '，回退 news 皮肤');
      // FR-MC-12 后续增强：未知类型聚合上报，便于服务端集中发现后端误下发类型
      reportClientWarn('unknown_channel_type', '未知 channel_type: ' + String(type), {
        unknown_type: String(type),
      });
    }
    return FALLBACK_TYPE;
  }
  return type;
}

/** 取某类型的皮肤对象（已归一化） */
function getSkin(type) {
  return SKINS[normalizeType(type)];
}

/** 取分组展示名 */
function getChannelTypeLabel(type) {
  return TYPE_LABELS[normalizeType(type)] || TYPE_LABELS[FALLBACK_TYPE];
}

/** 取合规提示文案（空串表示不展示） */
function getDisclaimerText(level) {
  return DISCLAIMER_COPY[level] || '';
}

/** 归一化合规等级 */
function getDisclaimerLevel(level) {
  return level === 'normal' || level === 'strong' ? level : 'none';
}

/**
 * 是否为课程类（course / audiobook）频道
 * 用于路由判断：课程类走课程主页，news 走今日节目
 */
function isCourseType(type) {
  const t = normalizeType(type);
  return t === 'course' || t === 'audiobook';
}

module.exports = {
  TYPE_LABELS,
  SKINS,
  DISCLAIMER_COPY,
  FALLBACK_TYPE,
  normalizeType,
  getSkin,
  getChannelTypeLabel,
  getDisclaimerText,
  getDisclaimerLevel,
  isCourseType,
};
