import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 配置页「来源提示」行（provenance）在回落字段多时把整页撑出横向滚动。
 *
 * 形状：`.config-provenance` 是 flex，右侧 `el-tag` 默认 `white-space: nowrap`，
 * 于是长提示的 min-content 宽度就是整条文案宽度，既不肯换行也压不下去，
 * 结果三处一起坏：
 * - 提示条冲出容器右边界（用户看到的是文字被裁掉）；
 * - 左侧「库里最后一次修改：…」被挤成一列竖排；
 * - 整页出现横向滚动，右上角固定在容器右缘的保存按钮被推出可视区。
 *
 * 三个配置面（AI 服务 / 通知 / 云端存储）是同一段布局写法，一起守。
 * 断言只量版面，不比像素字体：溢出量、冲出容器的距离、左侧标签行数。
 */

const ok = (data) => ({ status: 200, json: { code: 0, message: 'ok', data } })

const NAV_TIMEOUT = 60000

const AI_FIELDS = [
  'llm.chat_timeout_sec',
  'llm.llm_max_script_segments',
  'tts.api_key',
  'tts.appkey',
  'tts.tencent_secret_id',
  'tts.tencent_secret_key',
  'image.api_key',
  'image.base_url',
  'image.model',
]

const NOTIFY_FIELDS = [
  'global_enabled',
  'failed_enabled',
  'review_enabled',
  'published_enabled',
  'dingtalk_webhook',
  'dingtalk_secret',
  'wecom_webhook',
  'email_smtp_host',
  'email_smtp_port',
  'email_smtp_user',
  'email_smtp_password',
  'email_to',
  'admin_base_url',
]

const COS_FIELDS = ['secret_id', 'secret_key', 'region', 'bucket', 'cdn_domain']

// flex 子项会被块化，getClientRects() 对多行块只返回一个矩形（照它数行数会永远得 1，
// 断言就成了空跑）；这里按逐字符矩形分组数真实的行盒。
// 定义在 measure 内部：page.evaluate 只序列化这一个函数，外层helper带不进页面。
function measure(el) {
  const lineCount = (node) => {
    const text = [...node.childNodes].find((n) => n.nodeType === 3 && n.data.trim())
    if (!text) return 0
    const range = document.createRange()
    const tops = new Set()
    for (let i = 0; i < text.data.length; i += 1) {
      if (/\s/.test(text.data[i])) continue
      range.setStart(text, i)
      range.setEnd(text, i + 1)
      const r = range.getBoundingClientRect()
      if (r.width === 0 && r.height === 0) continue
      tops.add(Math.round(r.top))
    }
    return tops.size
  }
  const box = el.getBoundingClientRect()
  const kids = [...el.children]
  const tag = kids.find((k) => k.classList.contains('el-tag'))
  const label = kids.find((k) => !k.classList.contains('el-tag'))
  const content = tag ? tag.querySelector('.el-tag__content') || tag : null
  const cs = content ? getComputedStyle(content) : null
  // 最后一个非空白字符的矩形：标签被固定高度裁掉时，几何尺寸照样「正常」，
  // 只有落到字形上才看得出末字已经不在标签框内（或被 ellipsis 吞掉）
  let lastGlyph = null
  if (content) {
    const node = [...content.childNodes].find((n) => n.nodeType === 3 && n.data.trim())
    if (node) {
      const range = document.createRange()
      for (let i = node.data.length - 1; i >= 0; i -= 1) {
        if (!/\s/.test(node.data[i])) {
          range.setStart(node, i)
          range.setEnd(node, i + 1)
          lastGlyph = range.getBoundingClientRect()
          break
        }
      }
    }
  }
  const tagBox = tag ? tag.getBoundingClientRect() : null
  return {
    // 整页横向溢出（保存按钮被推出可视区的直接成因）
    pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    // 提示条自身溢出容器
    boxOverflow: el.scrollWidth - el.clientWidth,
    // 标签右缘冲出容器的距离
    tagEscape: tag ? tagBox.right - box.right : 0,
    // 左侧时间标签被挤成几行（1 = 正常单行）
    labelLines: label ? lineCount(label) : 0,
    // 提示文字自己的行数：窄屏必须真的换行，否则说明它是靠被压扁「挤」进去的
    tagLines: content ? lineCount(content) : 0,
    // 标签文字自身被裁掉的宽度（overflow: hidden + ellipsis 的情形）
    tagClipped: content ? content.scrollWidth - content.clientWidth : 0,
    whiteSpace: cs ? cs.whiteSpace : 'n/a',
    // 末字是否完整落在标签框内
    lastGlyphOutside: lastGlyph && tagBox
      ? Math.max(0, lastGlyph.right - tagBox.right) + Math.max(0, lastGlyph.bottom - tagBox.bottom)
      : 0,
  }
}

async function mockAi(page) {
  await page.route('**/admin/api/v1/ai/**', (route) => route.fulfill(ok({})))
  await page.route('**/admin/api/v1/ai/config', (route) =>
    route.fulfill(
      ok({
        llm: { api_key: '****wxyz', base_url: 'https://llm.example/v1', model: 'qwen-max', preset_configs: {} },
        tts: { provider: 'aliyun', api_key: '****abcd' },
        image: { api_key: '', base_url: '', model: '' },
        loaded: true,
        load_error: null,
        updated_at: '2026-09-08T01:02:12',
        fallback_fields: AI_FIELDS,
      }),
    ),
  )
  await page.route('**/admin/api/v1/ai/presets', (route) => route.fulfill(ok([])))
  await page.route('**/admin/api/v1/ai/audio-profile', (route) => route.fulfill(ok({})))
  await page.route('**/admin/api/v1/ai/voices*', (route) => route.fulfill(ok([])))
}

async function mockNotify(page) {
  await page.route('**/admin/api/v1/notification/**', (route) => route.fulfill(ok({})))
  await page.route('**/admin/api/v1/notification/config', (route) =>
    route.fulfill(
      ok({
        global_enabled: true,
        failed_enabled: true,
        review_enabled: true,
        published_enabled: false,
        loaded: true,
        load_error: null,
        updated_at: '2026-09-08T01:02:12',
        fallback_fields: NOTIFY_FIELDS,
      }),
    ),
  )
  await page.route('**/admin/api/v1/notification/templates*', (route) => route.fulfill(ok([])))
  await page.route('**/admin/api/v1/notification/logs*', (route) => route.fulfill(ok({ items: [], total: 0 })))
}

async function mockCos(page) {
  await page.route('**/admin/api/v1/cos/config**', (route) =>
    route.fulfill(
      ok({
        configured: true,
        secret_id: '****tZ5P',
        secret_key: '****kU3Q',
        region: 'ap-beijing',
        bucket: 'morningbrief-audio',
        cdn_domain: '',
        loaded: true,
        load_error: null,
        updated_at: '2026-09-08T01:02:12',
        fallback_fields: COS_FIELDS,
      }),
    ),
  )
  await page.route('**/admin/api/v1/cos/status**', (route) => route.fulfill(ok({ configured: true })))
}

const CASES = [
  { name: 'AI 服务', guide: 'ai-config-provenance', form: 'ai-config-form', mock: mockAi, path: '/ai-config' },
  { name: '通知配置', guide: 'notification-provenance', form: 'notification-form', mock: mockNotify, path: '/notification' },
  { name: '云端存储', guide: 'cos-config-provenance', form: 'cos-config-form', mock: mockCos, path: '/cos-config' },
]

for (const c of CASES) {
  test(`${c.name}：回落字段再多也不撑破版面`, async ({ page }) => {
    await setLoginState(page, 'admin')
    await c.mock(page)
    await page.goto(c.path)
    const line = page.locator(`[data-guide="${c.guide}"]`)
    await expect(line).toBeVisible({ timeout: NAV_TIMEOUT })
    // 提示条要真的承载长文案，否则断言是空跑
    await expect(line.locator('.el-tag')).toContainText('、')

    for (const width of [1600, 1280, 1024, 800]) {
      await page.setViewportSize({ width, height: 900 })
      const m = await line.evaluate(measure)
      expect(m.pageOverflow, `@${width}px 整页出现横向滚动（保存按钮会被推出可视区）：${JSON.stringify(m)}`).toBeLessThanOrEqual(0)
      expect(m.boxOverflow, `@${width}px 提示条溢出容器：${JSON.stringify(m)}`).toBeLessThanOrEqual(0)
      expect(m.tagEscape, `@${width}px 提示条冲出容器右缘 ${m.tagEscape}px`).toBeLessThanOrEqual(0.5)
      expect(m.whiteSpace, `@${width}px 提示文字仍是 nowrap（换行声明没落到元素上）`).toBe('normal')
      expect(m.tagClipped, `@${width}px 提示文字被裁切 ${m.tagClipped}px`).toBeLessThanOrEqual(0)
      expect(m.lastGlyphOutside, `@${width}px 提示文字末字落在标签框外 ${m.lastGlyphOutside}px（被固定高度裁掉）`).toBeLessThanOrEqual(0.5)
      expect(m.labelLines, `@${width}px 左侧时间标签被挤成 ${m.labelLines} 行`).toBe(1)
      if (width <= 800) {
        // 窄屏下提示条要靠换行消化，不是靠压扁：行数必须 >1
        expect(m.tagLines, `@${width}px 提示文字仍是 ${m.tagLines} 行（没换行就是被挤扁了）`).toBeGreaterThan(1)
      }
    }
  })
}
