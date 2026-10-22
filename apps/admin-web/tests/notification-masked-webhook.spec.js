import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'

/**
 * 通知配置：脱敏 webhook 的可发现性（T02826）
 *
 * 后端对 webhook 的凭据参数返回「****尾4」。用户看到这串值容易误判为
 * 「没配置」或「已失效」而清空——清空是真删除。本用例锁定三件事：
 * 1. 脱敏态有说明文案、「显示/隐藏」眼睛不再出现；
 * 2. 只改开关保存时，webhook 原样回传（后端据此判定未修改）；
 * 3. 保存成功提示明确「已保留原有…机器人配置」。
 */

const MASKED_DINGTALK =
  'https://oapi.dingtalk.com/robot/send?access_token=****9999'
const MASKED_WECOM =
  'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=****abcd'

const ok = (data) => ({ json: { code: 0, message: 'ok', data } })

let savedBody = null

test.beforeEach(async ({ page }) => {
  savedBody = null
  await setLoginState(page, 'admin')

  await page.route('**/admin/api/v1/notification/config', async (route) => {
    if (route.request().method() === 'PUT') {
      savedBody = route.request().postDataJSON()
      return route.fulfill(ok({}))
    }
    return route.fulfill(
      ok({
        global_enabled: true,
        failed_enabled: true,
        review_enabled: true,
        published_enabled: false,
        dingtalk_webhook: MASKED_DINGTALK,
        wecom_webhook: MASKED_WECOM,
        email_smtp_port: 587,
      }),
    )
  })
  await page.route('**/admin/api/v1/notification/templates*', (route) =>
    route.fulfill(ok([])),
  )
  await page.route('**/admin/api/v1/notification/logs*', (route) =>
    route.fulfill(ok({ items: [], total: 0 })),
  )
})

test('脱敏值有说明、无眼睛切换，保存只改开关会原样回传并提示保留', async ({
  page,
}) => {
  await page.goto('/notification')

  await expect(
    page.getByText('当前显示为脱敏值（****尾4）').first(),
  ).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('已脱敏').first()).toBeVisible()

  // 脱敏输入框不应再有「显示/隐藏」切换（对 **** 值没有意义）
  const webhookItems = page.locator('.el-form-item', { hasText: 'Webhook 地址' })
  await expect(webhookItems).toHaveCount(2)
  await expect(
    webhookItems.first().getByRole('button', { name: /显示|隐藏/ }),
  ).toHaveCount(0)

  // 只改全局开关，webhook 保持脱敏值不动
  await page
    .locator('.el-form-item', { hasText: '全局总开关' })
    .locator('.el-switch')
    .click()
  await page.getByRole('button', { name: '保存配置' }).click()

  await expect(
    page.getByText('已保留原有钉钉/企业微信机器人配置'),
  ).toBeVisible()

  expect(savedBody.dingtalk_webhook).toBe(MASKED_DINGTALK)
  expect(savedBody.wecom_webhook).toBe(MASKED_WECOM)
})
