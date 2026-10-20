/**
 * 跨模块共享常量（前后端双源收敛点）。
 *
 * 课程章节「已学完」判定阈值：播放进度占比 ≥ 此值（或 completed=1）视为已学完。
 * 必须与后端 app/routers/api/courses.py 的 _COMPLETE_RATIO 保持完全一致。
 *
 * 收敛前散落于：api.js（COURSE_COMPLETE_RATIO）、course.js（COMPLETE_RATIO）、
 * local-data.js（魔法数字 0.95）。现统一收敛到此单源，杜绝多副本漂移。
 */
module.exports = {
  COURSE_COMPLETE_RATIO: 0.95,
  /**
   * 用户设置在本机 storage 里的 key（单源）。
   * T02513 / J99 起 utils/tracker.js 也要读它来判断「使用记录统计」开关，
   * 原先这个字符串只写在 pages/settings/settings.js 里，两处各写一份迟早会漂。
   */
  STORAGE_KEY_SETTINGS: 'news_settings',
};
