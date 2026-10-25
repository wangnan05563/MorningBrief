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
  // T02787 起，本机 storage 的 key 名与分类挪到 services/storage-keys.js 单源：
  // 「清除缓存」要按类别做正向白名单，前提是 key 名能被静态列全，散在各模块里就列不全。
};
