/**
 * 定时触发的全局默认时刻（C7 / T02544 切片 6）
 *
 * 为什么存在：频道列表的「定时触发」列对空值只写「默认」，弹窗里才写「05:00」，
 * 做「今天为什么没生成」排障时从列表上根本看不出实际触发时刻。两个位置各写一份
 * 字面量既对不上也容易漂——这里收成一处，页面统一显示「默认 05:00」。
 *
 * ⚠ 数值必须与后端 `settings.WORKFLOW_CRON_HOUR` 的默认值一致
 * （backend/app/config.py）。后端目前不通过接口下发该项，改后端默认值时要同步这里；
 * 门禁 `tests/unit/t02544-slice6.test.mjs` 会比对两处。
 */
export const DEFAULT_CRON_HOUR = 5

/** 展示用「时:分」文案，如 05:00 */
export const DEFAULT_CRON_LABEL = `${String(DEFAULT_CRON_HOUR).padStart(2, '0')}:00`
