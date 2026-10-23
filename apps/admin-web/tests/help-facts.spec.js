/**
 * T02920：帮助文档在浏览器里渲染出来的正文，必须与代码事实一致
 *
 * 单测（help-fact-claims.test.mjs）拿的是源码字面量，证明的是「文案与代码同源」；
 * 这里补的是运行时那一段：Help.vue 真的编译进页面、订正后的文案真的出现在章节里、
 * 虚标字样（收藏数/10MB/TTS 合成队列/pending 状态/毫秒延迟）在整页上确实消失。
 * 文档类改动最容易「改了半天没渲染」，所以这条要真打开页面看。
 *
 * 运行：cd apps/admin-web && npx playwright test tests/help-facts.spec.js --workers=1
 */
import { expect, test } from '@playwright/test'
import { setLoginState } from './helpers/mock'

const section = (page, id) => page.locator(`#${id}`)

test.describe('帮助文档事实性渲染', () => {
  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/help', { waitUntil: 'load' })
    await expect(page.locator('#quickstart')).toBeVisible({ timeout: 30000 })
  })

  test('整页不再有接口不下发的指标名', async ({ page }) => {
    await expect(page.locator('.help-page')).not.toContainText('收藏数')
    await expect(page.locator('.help-page')).not.toContainText('反馈数')
    await expect(section(page, 'stats')).toContainText(
      'DAU、播放量、完播率、平均收听、推算广告曝光',
    )
  })

  test('广告章节否认上传，也不再承诺大小限制', async ({ page }) => {
    const ads = section(page, 'ads')
    await expect(ads).toContainText('不提供文件上传')
    await expect(ads).toContainText('素材 URL')
    await expect(ads).toContainText('开头/中间/结尾')
    await expect(ads).not.toContainText('10MB')
    await expect(ads).not.toContainText('上传图片')
  })

  test('队列章节按界面枚举写状态，不再编两个队列', async ({ page }) => {
    const queue = section(page, 'queue')
    await expect(queue).toBeVisible()
    await expect(queue).toContainText('排队中/运行中/成功/失败')
    await expect(queue).not.toContainText('TTS 合成队列与音频拼接队列')
    await expect(queue).not.toContainText('清空已完成任务')
  })

  test('工作流章节用 queued 而不是 pending', async ({ page }) => {
    const wf = section(page, 'workflows')
    await expect(wf).toContainText('queued/running/success/failed/cancelled')
    await expect(wf).not.toContainText('pending/running')
    await expect(wf).toContainText('爬虫采集/LLM改写/质量审核/语音合成/音频拼接/创建审核')
  })

  test('脚本路径带 scripts/ 前缀，照抄能落地', async ({ page }) => {
    await expect(section(page, 'quickstart')).toContainText('scripts/启动服务.bat')
    await expect(section(page, 'cos-storage')).toContainText('scripts/stop.ps1')
    await expect(section(page, 'cos-storage')).toContainText(
      'scripts/jmeter_test/verify_cos.py',
    )
  })

  test('无法核对的外部数字已从文档里撤下', async ({ page }) => {
    const cos = section(page, 'cos-storage')
    await expect(cos).not.toContainText('300-1000ms')
    await expect(cos).not.toContainText('50-200ms')
    await expect(cos).not.toContainText('7-20 个工作日')
    await expect(cos).not.toContainText('10GB 内约 1 元/月')
  })
})
