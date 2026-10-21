import { test, expect } from '@playwright/test'
import { setLoginState } from './helpers/mock'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * INT-UX-04 / T02527：`GET /admin/api/v1/cos/config` 的 loaded / updated_at /
 * fallback_fields 必须落到页面上——「请求成功」不再等于「屏上这几个值是库里存的」。
 *
 * FR-UX-104（tests/config-load-error-guard.spec.js）守的是接口**报错**那一半；
 * 这里守剩下两半：
 * - 请求成功但读表失败（loaded=false）：禁存 + 把原因说清楚；
 * - 请求成功且读表成功、但值是 .env 回落来的（库里没有这条记录）：必须点名到字段，
 *   否则管理员会以为「已经保存过」，一次保存就把 .env 旧值固化进库。
 *
 * 三态分别对应本机库的真实形态（cos_config 只存了 region/bucket/cdn_domain，
 * 两个凭证键从未入库），取证见 _validate/news2/result_T02527.md。
 */

const NAV_TIMEOUT = 30000
const BASE_DATA = {
  configured: true,
  secret_id: '****tZ5P',
  secret_key: '****kU3Q',
  region: 'ap-beijing',
  bucket: 'morningbrief-audio-1311027859',
  cdn_domain: '',
}
const ALL_FIELDS = ['secret_id', 'secret_key', 'region', 'bucket', 'cdn_domain']
const SHOTS = fileURLToPath(new URL('../../../_validate/news2/tmp_int04_shots', import.meta.url))

async function mockConfig(page, data) {
  await page.route('**/admin/api/v1/cos/config**', (route) =>
    route.fulfill({ status: 200, json: { code: 0, message: 'ok', data } }),
  )
  await page.route('**/admin/api/v1/cos/status**', (route) =>
    route.fulfill({
      status: 200,
      json: { code: 0, message: 'ok', data: { ...BASE_DATA, configured: true } },
    }),
  )
}

async function open(page) {
  await page.goto('/cos-config')
  await expect(page.locator('[data-guide="cos-config-form"]')).toBeVisible({
    timeout: NAV_TIMEOUT,
  })
}

mkdirSync(SHOTS, { recursive: true })

test.describe('INT-UX-04 云端配置页的来源信息', () => {
  test('库里存过一部分：写明最后一次修改时间，并点出哪些值是 .env 回落', async ({ page }) => {
    await mockConfig(page, {
      ...BASE_DATA,
      loaded: true,
      load_error: null,
      updated_at: '2026-08-11T02:45:46',
      fallback_fields: ['secret_id', 'secret_key'],
    })
    await setLoginState(page, 'admin')
    await open(page)

    const line = page.locator('[data-guide="cos-config-provenance"]')
    await expect(line).toBeVisible()
    await expect(line).toContainText('库里最后一次修改：2026-08-11 02:45:46')
    // 逐个字段中文名，不是「共 N 项」这种没法行动的提示
    await expect(line).toContainText('以下值来自环境变量回落，库里并未保存：SecretId、SecretKey')
    await expect(page.locator('[data-guide="cos-config-load-error"]')).toHaveCount(0)
    // 库里读到了东西 → 允许保存（本单只禁「读不到」，不禁「库里有回落」）
    await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeEnabled()
    await page.screenshot({ path: resolve(SHOTS, '1_partial_fallback.png'), fullPage: true })
  })

  test('请求成功但读表失败：横幅写明原因 + 保存禁用，测试连接不受限', async ({ page }) => {
    await mockConfig(page, {
      ...BASE_DATA,
      loaded: false,
      load_error: "RuntimeError: no such column: config_value; secret_key='<已脱敏>'",
      updated_at: null,
      fallback_fields: ALL_FIELDS,
    })
    await setLoginState(page, 'admin')
    await open(page)

    const banner = page.locator('[data-guide="cos-config-load-error"]')
    await expect(banner).toBeVisible()
    await expect(banner).toContainText('配置表读取失败，已禁止保存：RuntimeError')
    // 来源行不能同时出现：读失败时任何「上次修改时间」都不是本次读到的
    await expect(page.locator('[data-guide="cos-config-provenance"]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeDisabled()
    await expect(page.getByRole('button', { name: '测试连接' }).first()).toBeEnabled()
    await page.screenshot({ path: resolve(SHOTS, '2_load_error_gated.png'), fullPage: true })
    // handleSave 内的第二道护栏（不依赖按钮 disabled）由 tests/unit/cos-config-provenance.test.mjs
    // 守：浏览器里点不动原生 disabled 按钮，无法从 UI 侧触发那条代码路径。
  })

  test('库内无记录：写「库里暂无记录」并把五个回落字段全点出来', async ({ page }) => {
    await mockConfig(page, {
      ...BASE_DATA,
      loaded: true,
      load_error: null,
      updated_at: null,
      fallback_fields: ALL_FIELDS,
    })
    await setLoginState(page, 'admin')
    await open(page)

    const line = page.locator('[data-guide="cos-config-provenance"]')
    await expect(line).toBeVisible()
    await expect(line).toContainText('库里暂无记录')
    await expect(line).toContainText(
      '以下值来自环境变量回落，库里并未保存：SecretId、SecretKey、地域、存储桶、CDN 域名',
    )
    await page.screenshot({ path: resolve(SHOTS, '3_empty_table.png'), fullPage: true })
  })

  test('接口没给来源字段（旧版后端）：不假装「已加载」，也不误报失败', async ({ page }) => {
    // 后端回滚到修复前（没有 loaded）时，页面应退回 FR-UX-104 的口径：请求成功即可编辑，
    // 但绝不能凭空显示「库里最后一次修改」
    await mockConfig(page, BASE_DATA)
    await setLoginState(page, 'admin')
    await open(page)

    await expect(page.locator('[data-guide="cos-config-provenance"]')).toHaveCount(0)
    await expect(page.locator('[data-guide="cos-config-load-error"]')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '保存配置' }).first()).toBeEnabled()
    await page.screenshot({ path: resolve(SHOTS, '4_legacy_response.png'), fullPage: true })
  })
})
