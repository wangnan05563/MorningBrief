import { test, expect } from '@playwright/test'
import {
  setLoginState,
  workflowListResponse,
  channelsListResponse,
} from './helpers/mock'

/**
 * 引导锚点是否真的落在按钮上（T02500 / FR-UX-401）
 *
 * 构建期校验能保证「选择器引用的 aria-label 存在于代码里」，但保证不了
 * 「那个元素在这一页真的渲染出来」——工作流页的触发按钮是 admin 才可见的，
 * 静态看得到标签、运行时选不中，就会退到 `.top-bar .el-button` 指错元素。
 * 这条用例把这个残留缺口钉住。
 */
test.describe('引导锚点', () => {
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    await setLoginState(page, 'admin')
    // SSE 与列表接口给空流/固定数据，避免后端未启动导致 flaky
    await page.route('**/admin/api/v1/events/stream**', (route) =>
      route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }))
    await page.route('**/admin/api/v1/channels**', (route) =>
      route.fulfill({ json: channelsListResponse }))
    await page.route('**/admin/api/v1/workflows**', (route) =>
      route.fulfill({ json: workflowListResponse }))
  })

  test('工作流引导第二步高亮的是「手动触发」按钮本身', async ({ page }) => {
    // useGuide 在 navigator.webdriver 下默认跳过首访弹引导（免得遮罩挡住被测按钮），
    // ?guide=demo 是它留给验收的强制入口
    await page.goto('/workflows?guide=demo')

    const bubble = page.locator('.mb-guide-bubble')
    await expect(bubble.getByText('工作流监控')).toBeVisible({ timeout: 30000 })

    await bubble.getByRole('button', { name: '下一步' }).click()

    // 修复前的表现：高亮落到工具栏第一个按钮（重新拉取列表），而不是触发按钮
    const highlighted = page.locator('.mb-guide-highlight')
    await expect(highlighted).toHaveAttribute('aria-label', '手动触发', { timeout: 30000 })
  })
})
