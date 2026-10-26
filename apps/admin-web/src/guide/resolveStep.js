/**
 * 引导步骤的目标判定（T02656）
 *
 * 落空分两种，必须分开处理：
 * - **设计**：这一步本来就没有目标元素（纯文案步骤），居中展示即可；
 * - **缺陷**：这一步声明了选择器却一个都没命中——要么锚点被改名，要么它依赖的数据
 *   在空态下没有渲染。前者是 bug，后者不该让用户看一句对着空气的说明。
 *
 * 数据依赖步骤在 `guideConfig.js` 里用 `skipWhenEmpty: '<空态选择器>'` 声明：
 * 只有空态标记**确实存在**时才跳过；既没命中目标、也没有空态标记，仍按缺陷露出
 * （居中 + data-guide-missing="broken"），否则真回归会被「跳过」静默吞掉。
 */

export const GUIDE_MISSING_BROKEN = 'broken'
export const GUIDE_MISSING_TEXT = 'text'

/**
 * @param {{ s?: string[], skipWhenEmpty?: string }} step
 * @param {{ targetFound?: boolean, emptyFound?: boolean }} state
 * @returns {{ action: 'highlight' | 'skip' | 'center', reason: 'empty' | 'text' | 'broken' | '' }}
 */
export function decideGuideStep(step, { targetFound = false, emptyFound = false } = {}) {
  if (targetFound) return { action: 'highlight', reason: '' }
  if (step?.skipWhenEmpty && emptyFound) return { action: 'skip', reason: 'empty' }
  if (!(step?.s || []).length) return { action: 'center', reason: GUIDE_MISSING_TEXT }
  return { action: 'center', reason: GUIDE_MISSING_BROKEN }
}
