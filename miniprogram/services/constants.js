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
};
