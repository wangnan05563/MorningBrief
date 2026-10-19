/**
 * 底部导航角标（T02510 / FR-UX-601 需求项②的小程序侧）
 *
 * 背景（T02323 I27 同源问题的 C 端形态）：底部三个 tab 只有图形，用户停在别的 tab 时
 * 无法感知「队列里还压着几条没播」。管理端（H5）有服务端未读/待办计数可用，
 * 小程序是 C 端收听应用，**后端没有任何 C 端未读/待办计数接口**，
 * 因此这里的角标口径明确定为**本地播放队列的待播条数**（不新增请求、不引入轮询）。
 *
 * 口径（写清楚，避免被当成「消息未读数」误读）：
 * - 计数 = `queue.length - (queueIndex + 1)`，即当前条之后还剩几条；队列空 → 0 → 撤角标；
 * - 挂在「历史」tab 上：队列页的入口就在历史页工具条（history.wxml 队列 chip），
 *   用户在历史页找队列最自然；索引由 `HISTORY_TAB_INDEX` 固定，
 *   与 app.json 的 `tabBar.list` 顺序绑定，由 `scripts/validate-tabbar.mjs` 门禁守住——
 *   有人往 tabBar 前面插一个 tab，门禁会红，而不是角标静默挂错位置；
 * - `wx.setTabBarBadge` 只在 tabBar 页面可调用（非 tab 页调用会 fail），
 *   所以每次刷新先判定当前栈顶是不是 tab 页；不是就跳过，等下一个 tab 页 onShow 再补挂。
 *
 * 依赖注入：计数来源走构造参数（默认延迟 require services/audio），纯逻辑可单测，
 * 不需要把整个 audio service（会碰 wx.createInnerAudioContext）拉进测试环境。
 */

/** 「历史」tab 在 app.json tabBar.list 中的下标（门禁校验该项 pagePath 确实是 history） */
const HISTORY_TAB_INDEX = 1;

/** tab 页路由 → 下标（与 app.json tabBar.list 顺序一致） */
const TAB_ROUTES = {
  'pages/index/index': 0,
  'pages/history/history': 1,
  'pages/profile/profile': 2,
};

/** 角标最多显示 3 个字符（微信建议不超过 4 个），超过 99 折叠 */
const BADGE_FOLD_AT = 99;

/**
 * 待播条数：当前条（含）之后的队列不计。
 * index 为 -1（未定位）时，整个队列都算待播。
 */
function pendingCountOf(queue, index) {
  const total = Array.isArray(queue) ? queue.length : 0;
  if (total === 0) return 0;
  const consumed = Number.isFinite(index) && index >= 0 ? index + 1 : 0;
  return Math.max(0, total - consumed);
}

/** 角标文案；0 表示「不显示」，由调用方撤角标 */
function badgeText(count) {
  if (!count || count <= 0) return '';
  return count > BADGE_FOLD_AT ? `${BADGE_FOLD_AT}+` : String(count);
}

/** 当前栈顶页面对应的 tab 下标；不在 tab 页返回 -1 */
function currentTabIndex() {
  if (typeof getCurrentPages !== 'function') return -1;
  const pages = getCurrentPages() || [];
  const top = pages[pages.length - 1];
  const route = (top && (top.route || (top.$page && top.$page.route))) || '';
  return Object.prototype.hasOwnProperty.call(TAB_ROUTES, route) ? TAB_ROUTES[route] : -1;
}

/**
 * 创建角标刷新器。
 * @param {object} deps
 * @param {() => Array} deps.getQueue 队列快照
 * @param {() => number} deps.getQueueIndex 当前播放索引
 */
function createTabBadge({ getQueue, getQueueIndex }) {
  // 上一次真正下发的文案：相同的重复调用直接短路，避免每次 onShow 都打一次 API
  let lastText = null;

  function refresh() {
    if (currentTabIndex() < 0) return { applied: false, reason: 'not-tab-page' };

    let count = 0;
    try {
      count = pendingCountOf(getQueue(), getQueueIndex());
    } catch (e) {
      // 取数失败不应影响页面：撤角标而不是留一个来路不明的数字
      console.warn('[tab-badge] 读取队列失败，跳过角标刷新:', e && e.message);
      return { applied: false, reason: 'read-failed' };
    }

    const text = badgeText(count);
    if (lastText === text) return { applied: false, reason: 'unchanged', count };
    lastText = text;

    const fail = () => {
      // 失败（多为「非 tabBar 页面」时序竞争）时清缓存，下次 onShow 重试
      lastText = null;
    };
    if (count > 0) {
      wx.setTabBarBadge({ index: HISTORY_TAB_INDEX, text, fail });
    } else {
      wx.removeTabBarBadge({ index: HISTORY_TAB_INDEX, fail });
    }
    return { applied: true, count, text };
  }

  /** 仅测试/诊断用：清掉去重缓存 */
  function reset() {
    lastText = null;
  }

  return { refresh, reset };
}

let _instance = null;

/** 默认实例：计数来源为全局音频服务的播放队列（services/audio.js 单例） */
function getTabBadge() {
  if (!_instance) {
    const { getQueue, getQueueIndex } = require('../services/audio');
    _instance = createTabBadge({ getQueue, getQueueIndex });
  }
  return _instance;
}

/** 页面 onShow / 队列变更时调这个 */
function refreshTabBadge() {
  return getTabBadge().refresh();
}

module.exports = {
  HISTORY_TAB_INDEX,
  TAB_ROUTES,
  BADGE_FOLD_AT,
  pendingCountOf,
  badgeText,
  currentTabIndex,
  createTabBadge,
  getTabBadge,
  refreshTabBadge,
};
