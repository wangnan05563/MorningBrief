/**
 * 本机 storage key 的唯一生成处与分类表（T02787 / J80 续）
 *
 * 为什么要单源：J80 的缺陷不是某个 key 写错，而是「清除缓存」用黑名单实现——
 * `KEEP_KEYS` 只写了 3 个，循环却删掉 storage 里剩下的所有 key。于是收藏、播放进度、
 * 播放历史、偏爱频道、下载索引、上次播放项、搜索历史、反馈历史被一起抹掉，
 * 而确认文案只说「保留登录信息与设置」。黑名单之所以危险，正是因为 key 名散落在
 * 各模块里、运行时按 openid 拼，静态列不全（T02513 当时只能先把文案改成说实话）。
 *
 * 现在所有 key 在这一处生成并归类，清除动作改成**正向白名单**：
 * 只删 CACHE_KEYS；认不出的 key（后来别人新加的、或旧版本残留的）一律不动。
 * 分类规则只有一条判据——「删掉之后用户会不会觉得自己少了东西」：
 * 拿不准的进 USER_DATA_KEYS，宁可让「清除缓存」少清，也不能再多抹。
 *
 * ⚠ 兼容红线：这里的字符串值就是老用户本机已存的 key 名。改名等于让升级后的用户
 * 「收藏/进度/偏爱凭空消失」（数据还在，只是读不到了），所以逐字不许动，
 * tests/storage-keys.test.js 用冻结快照锁住这一点。
 */

/** 固定名（不带 openid 的 key） */
const STATIC = {
  /** 登录态 */
  TOKEN: 'news_token',
  USER: 'news_user',
  /** 播放与通知设置（含「使用记录统计」开关） */
  SETTINGS: 'news_settings',
  /** 偏爱频道引导是否看过：删掉会重弹引导，属于用户已经做过的选择 */
  PREFERRED_ONBOARDED: 'preferred_channels_onboarded',
  /** 用户手动填的服务地址：删掉会把人指回默认地址 */
  MANUAL_API_BASE_URL: 'manual_api_base_url',
  /** 上次发现成功的服务地址：只用于二次启动加速，丢了走完整发现流程 */
  LAST_SUCCESS_API_BASE_URL: 'last_success_api_base_url',
  /** 搜索历史（工单点名的被误删项） */
  SEARCH_HISTORY: 'search_history',
  /** 反馈提交历史（工单点名的被误删项） */
  FEEDBACK_HISTORY: 'news_feedback_history',
  /** 还没上报成功的收听计数队列：删了就是真丢，服务端永远补不回来 */
  PENDING_REPORTS: 'pending_play_reports',
  /** 上次收听的节目与断点：承担「继续收听」卡片（写入带 7 天 TTL，但内容是用户痕迹） */
  LAST_PLAYED_EPISODE: 'lastPlayedEpisode',
};

/** 动态 key 的前缀（后面接 openid） */
const PREFIX = {
  PROGRESS: 'news_progress_',
  FAVORITES: 'news_favorites_',
  HISTORY: 'news_history_',
  PREFERRED_CHANNELS: 'news_preferred_channels_',
  DOWNLOADS: 'news_downloads_',
  SILENT_ENRICH_SKIP: 'skipSilentEnrich_',
};

/** 清缓存保留：登录态、设置、以及用户已经做过的选择 */
const KEEP_KEYS = [
  STATIC.TOKEN,
  STATIC.USER,
  STATIC.SETTINGS,
  STATIC.PREFERRED_ONBOARDED,
  STATIC.MANUAL_API_BASE_URL,
];
const KEEP_PREFIXES = [PREFIX.SILENT_ENRICH_SKIP];

/** 清缓存可删：只有可再生的技术态。删完不影响用户任何一条数据或设置 */
const CACHE_KEYS = [STATIC.LAST_SUCCESS_API_BASE_URL];
const CACHE_PREFIXES = [];

/**
 * 用户数据：清缓存一律不动。
 * 偏爱频道只有本机一份（收藏与进度服务端有双写备份，偏爱没有），一旦抹掉不可恢复；
 * 待上报队列删了就是永久少计数。
 */
const USER_DATA_KEYS = [
  STATIC.SEARCH_HISTORY,
  STATIC.FEEDBACK_HISTORY,
  STATIC.PENDING_REPORTS,
  STATIC.LAST_PLAYED_EPISODE,
];
const USER_DATA_PREFIXES = [
  PREFIX.PROGRESS,
  PREFIX.FAVORITES,
  PREFIX.HISTORY,
  PREFIX.PREFERRED_CHANNELS,
  PREFIX.DOWNLOADS,
];

const byPrefix = (prefixes, key) => prefixes.find((p) => key.indexOf(p) === 0);

/** 归哪一类：'keep' | 'cache' | 'user' | 'unknown'（unknown 一律不当作可清除） */
function categoryOf(key) {
  if (typeof key !== 'string' || !key) return 'unknown';
  if (KEEP_KEYS.indexOf(key) >= 0 || byPrefix(KEEP_PREFIXES, key)) return 'keep';
  if (CACHE_KEYS.indexOf(key) >= 0 || byPrefix(CACHE_PREFIXES, key)) return 'cache';
  if (USER_DATA_KEYS.indexOf(key) >= 0 || byPrefix(USER_DATA_PREFIXES, key)) return 'user';
  return 'unknown';
}

/** 从「storage 里当前存在的 key」挑出这次清除该删的：正向白名单，认不出的一律不删 */
function planCacheRemoval(existingKeys) {
  return (existingKeys || []).filter((key) => categoryOf(key) === 'cache');
}

/**
 * 执行清除并把「真正删掉的 key」还回去，供 UI 如实播报。
 * remove 做成入参：页面只负责交互，删哪些由这里的白名单决定，测试可以用假 storage 验证策略。
 */
function clearCacheKeys(existingKeys, remove) {
  const removed = planCacheRemoval(existingKeys);
  removed.forEach((key) => remove(key));
  return removed;
}

module.exports = {
  STATIC,
  PREFIX,
  KEEP_KEYS,
  KEEP_PREFIXES,
  CACHE_KEYS,
  CACHE_PREFIXES,
  USER_DATA_KEYS,
  USER_DATA_PREFIXES,
  categoryOf,
  planCacheRemoval,
  clearCacheKeys,
  progressKey: (openid) => PREFIX.PROGRESS + openid,
  favoritesKey: (openid) => PREFIX.FAVORITES + openid,
  historyKey: (openid) => PREFIX.HISTORY + openid,
  preferredChannelsKey: (openid) => PREFIX.PREFERRED_CHANNELS + openid,
  downloadsKey: (openid) => PREFIX.DOWNLOADS + openid,
  silentEnrichSkipKey: (openid) => PREFIX.SILENT_ENRICH_SKIP + openid,
};
