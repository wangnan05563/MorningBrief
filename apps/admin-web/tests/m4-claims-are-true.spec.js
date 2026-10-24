import { test, expect } from '@playwright/test'
import { setLoginState, channelsListResponse } from './helpers/mock'

/**
 * M4「界面声称未发生的事」E2E（T02536）
 *
 * 单元测试钉的是「代码不再用旧写法」，这份钉的是「用户真的看得见那句话/那个数」。
 * 每条用例都成对断言：① 界面声称的内容出现在 DOM 上；② 与之矛盾的那句谎不在了。
 *
 * 覆盖条目：C103（加入待讲书单要带频道、要说清落到哪）、G1（后端下发的引导数据要真渲染）、
 * C84（候选总数与第 51 本之后的书要可见）、M49（导入坏行的逐行原因要可见）、
 * M20（时间戳列只读、不回写）、D15（同一天可投、倒序说中文）、D16（第 101 条素材要搜得到）、
 * C92（来源类型标记要说做一致）、H2（缺后缀的桶名不许保存）。
 */

const API = '**/admin/api/v1'
const NAV = 30000
const ok = (data) => ({ code: 0, message: 'success', data })

/** 业务错误：HTTP 200 + code!==0（拦截器会 reject 成带 code/payload 的 Error） */
const bizError = (code, message, data = null) => ({ code, message, data })

async function stubEverything(page) {
  await setLoginState(page, 'admin')
  // 兜底先注册（后注册的 route 优先），未列出的接口一律给空成功
  await page.route(`${API}/**`, (route) => route.fulfill({ json: ok({}) }))
  await page.route(`${API}/channels*`, (route) => route.fulfill({ json: channelsListResponse }))
  await page.route(`${API}/events/stream**`, (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
  )
}

/** 等一小段时间，确认「没有发出某个请求」——静默失败与静默成功都得验 */
async function expectNoRequest(page, predicate, ms = 2000) {
  const hit = await page
    .waitForRequest(predicate, { timeout: ms })
    .then(() => true)
    .catch(() => false)
  expect(hit).toBe(false)
}

test.describe('M4 界面的说法必须是真的', () => {

  // ---------------------------------------------------------------- G1 隧道引导块

  test('G1 下载失败（code=5001）：手动放置路径与下载源真的渲染出来', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/tunnel/start`, (route) =>
      route.fulfill({
        json: bizError(5001, '二进制下载失败，请手动放置', {
          error_type: 'binary_download_failed',
          manual_path: 'D:/manual/place/tailscale-bin.exe',
          download_urls: ['https://mirror.example.com/tailscale.exe'],
        }),
      })
    )

    await page.goto('/tunnel')
    await page.getByRole('button', { name: '启动隧道' }).click()

    const guide = page.locator('.download-error')
    await expect(guide).toBeVisible({ timeout: NAV })
    await expect(guide.locator('code')).toContainText('D:/manual/place/tailscale-bin.exe')
    // 下载源是 IconButton（button 角色，点击才跳转），不是 <a>
    await expect(page.getByRole('button', { name: /tailscale\.exe/ })).toBeVisible()
    // 修复前这里只有一句泛化 toast，引导块永不渲染——现在两块都在
    await expect(page.getByText('请手动下载并放置到以下路径')).toBeVisible()
  })

  test('G1 Funnel 需授权（code=5003）：授权链接渲染出来', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/tunnel/start`, (route) =>
      route.fulfill({
        json: bizError(5003, 'Tailscale Funnel 需要授权', {
          error_type: 'tailscale_funnel_auth',
          auth_url: 'https://login.example.com/funnel-auth',
        }),
      })
    )

    await page.goto('/tunnel')
    await page.getByRole('button', { name: '启动隧道' }).click()

    // 修复前引导块整块不渲染；现在按钮出现且真的绑定 auth_url
    await expect(page.getByRole('button', { name: '前往授权' })).toBeVisible({ timeout: NAV })
  })

  // ---------------------------------------------------------------- C103 加入待讲书单

  test('C103 未选频道时不许提交；选了就把频道一起写进去', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/ebooks/random*`, (route) =>
      route.fulfill({
        json: ok({ hits: [{ title: '书名甲', author: '作者乙', category: '技术', url: 'https://e/a.epub' }] }),
      })
    )
    await page.route(`${API}/ebooks/draft-material`, (route) =>
      route.fulfill({
        json: ok({
          created: true,
          material_id: 88,
          channel_id: 1,
          message: '《书名甲》已加入待讲书单（「科技频道」频道，素材库第 88 条）；书稿需在「素材录入」上传后才会进入讲书稿书单',
        }),
      })
    )

    await page.goto('/ebooks')
    await page.getByRole('button', { name: /随机/ }).click()
    const row = page.locator('.el-table__row').first()
    await expect(row.getByText('书名甲')).toBeVisible({ timeout: NAV })

    // ① 没选频道：不落库，且要说清为什么
    await row.getByRole('button', { name: '加入书单' }).click()
    await expect(page.locator('.el-message').filter({ hasText: /请先在结果表上方选择归属频道/ })).toBeVisible({ timeout: NAV })
    await expectNoRequest(page, (req) => req.url().includes('draft-material'))

    // ② 选了频道：请求体必须带 channel_id（此前恒为 null，书「消失」在所有书单之外）
    await page.locator('.result-meta .el-select').click()
    await page.locator('.el-select-dropdown__item').filter({ hasText: '科技频道' }).first().click()

    const reqPromise = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('draft-material'), {
      timeout: NAV,
    })
    await row.getByRole('button', { name: '加入书单' }).click()
    const req = await reqPromise
    const body = JSON.parse(req.postData())
    expect(body.channel_id).toBe(1)

    // ③ 落点要说人话：哪本书、哪个频道、第几条、下一步干什么
    await expect(page.locator('.el-message').filter({ hasText: '素材库第 88 条' })).toBeVisible({ timeout: NAV })
    await expect(page.getByText(/book_plan/)).toHaveCount(0)
  })

  // ---------------------------------------------------------------- C84 候选总数与翻页

  test('C84 候选书籍：总数要说出来，第 21 本之后的书要翻得到', async ({ page }) => {
    await stubEverything(page)
    const books = (i) => ({
      id: i,
      title: `《书${i}》`,
      chapters: 10,
      pending_chapters: 3,
      category: '技术',
      in_pool: false,
    })
    await page.route(`${API}/channels/*/book-pool/candidates*`, (route) => {
      const url = new URL(route.request().url())
      const p = Number(url.searchParams.get('page') || 1)
      const size = Number(url.searchParams.get('size') || 20)
      const all = Array.from({ length: 137 }, (_, i) => books(i + 1))
      return route.fulfill({ json: ok({ items: all.slice((p - 1) * size, p * size), total: 137 }) })
    })

    await page.goto('/channels/book-pool')
    await page.locator('.el-select').first().click()
    await page.locator('.el-select-dropdown__item').first().click()
    await page.getByRole('button', { name: '从素材库加入' }).click()

    const pager = page.locator('.candidate-pager')
    await expect(pager).toBeVisible({ timeout: NAV })
    await expect(pager.getByText('本频道共 137 本书可加入')).toBeVisible()
    await expect(page.locator('.el-table__row').first().getByText('《书1》')).toBeVisible()

    // 修复前：固定 page:1/size:50，第 51 本起在界面上不存在，也不显示总数
    await pager.locator('.btn-next').click()
    await expect(page.locator('.el-table__row').first().getByText('《书21》')).toBeVisible({ timeout: NAV })
  })

  // ---------------------------------------------------------------- M49 / M20 数据库后台

  const tablesResponse = ok([{ name: 'ad_material', label: '广告素材', rows: 12 }])
  const schemaResponse = ok({
    columns: [
      { name: 'id', type: 'INTEGER', primary_key: true, sensitive: false, auto_maintained: false },
      { name: 'name', type: 'VARCHAR(256)', primary_key: false, sensitive: false, auto_maintained: false },
      { name: 'created_at', type: 'DATETIME', primary_key: false, sensitive: false, auto_maintained: true },
    ],
  })

  async function stubDbAdmin(page) {
    await stubEverything(page)
    await page.route(`${API}/db-admin/tables`, (route) => route.fulfill({ json: tablesResponse }))
    await page.route(`${API}/db-admin/tables/ad_material/schema`, (route) => route.fulfill({ json: schemaResponse }))
    await page.route(`${API}/db-admin/tables/ad_material/rows*`, (route) =>
      route.fulfill({
        json: ok({
          rows: [{ id: 1, name: '素材A', created_at: '2026-10-17 22:01:00' }],
          total: 1,
        }),
      })
    )
    await page.route(`${API}/db-admin/audit-log*`, (route) => route.fulfill({ json: ok({ items: [], total: 0 }) }))
  }

  test('M49 导入坏行：逐行原因要看得见，且不许再说「导入完成」', async ({ page }) => {
    await stubDbAdmin(page)
    await page.route(`${API}/db-admin/tables/ad_material/import/preview`, (route) =>
      route.fulfill({
        json: ok({ total: 3, to_insert: 3, to_update: 0, conflicts: 0, error_rows: 0, errors: [], notices: [] }),
      })
    )
    await page.route(`${API}/db-admin/tables/ad_material/import`, (route) =>
      route.fulfill({
        json: ok({
          inserted: 1,
          updated: 0,
          skipped: 2,
          errors: [
            { row: 3, error: '列 not_exist 不在表 ad_material 中' },
            { row: 5, error: '字段类型不匹配：duration 需要数字' },
          ],
        }),
      })
    )

    await page.goto('/db-admin')
    await page.locator('.table-item').filter({ hasText: '广告素材' }).click({ timeout: NAV })
    await page.getByRole('button', { name: '导入' }).click()
    await page.getByPlaceholder('粘贴 CSV 内容（首行为列名，支持引号内逗号与换行）').fill('id,name\n1,素材A\n2,素材B')

    const dlg = page.locator('.el-dialog').filter({ hasText: '导入数据' })
    // 后端要求先 dry-run 预览，确认写入行数后才允许真导
    await dlg.getByRole('button', { name: '预览' }).click()
    await expect(dlg.locator('.import-preview').first()).toBeVisible({ timeout: NAV })
    await dlg.getByRole('button', { name: '确认导入' }).click()

    await expect(page.locator('.el-message').filter({ hasText: '导入未全部成功' })).toBeVisible({ timeout: NAV })
    const detail = dlg.locator('.import-preview')
    await expect(detail.getByText('列 not_exist 不在表 ad_material 中')).toBeVisible()
    await expect(detail.getByText('字段类型不匹配：duration 需要数字')).toBeVisible()
    // 矛盾的谎不得再出现
    await expect(page.locator('.el-message').filter({ hasText: '导入完成' })).toHaveCount(0)
  })

  test('M20 时间戳列：界面只读，编辑与新增都不把它写回去', async ({ page }) => {
    await stubDbAdmin(page)
    await page.goto('/db-admin')
    await page.locator('.table-item').filter({ hasText: '广告素材' }).click({ timeout: NAV })

    await page.locator('.data-table .el-table__row').first().getByRole('button', { name: '编辑' }).click()
    const dlg = page.locator('.el-dialog').filter({ hasText: '编辑行' })
    await expect(dlg).toBeVisible({ timeout: NAV })
    const tsInput = dlg.locator('.el-form-item').filter({ hasText: 'created_at' }).locator('input')
    await expect(tsInput).toBeDisabled()
    await expect(dlg.getByText('时间戳由系统自动写入')).toBeVisible()

    const patchPromise = page.waitForRequest(
      (r) => r.method() === 'PATCH' && r.url().includes('db-admin/tables/ad_material/rows'),
      { timeout: NAV }
    )
    await dlg.locator('.el-form-item').filter({ hasText: /^name/ }).locator('input').fill('素材A-改名')
    await dlg.getByRole('button', { name: '确认' }).click()
    const patch = await patchPromise
    const values = JSON.parse(patch.postData()).values
    expect(values.name).toBe('素材A-改名')
    // 修复前：把后端 isoformat 的 `2026-10-17T22:01:00` 原样回写，破坏按空格分隔格式比较的清理与排序
    expect(values).not.toHaveProperty('created_at')
  })

  // ---------------------------------------------------------------- D15 / D16 投放表单

  async function stubAds(page, { total = 102, placements = [] } = {}) {
    await stubEverything(page)
    await page.route(`${API}/ads/placements*`, (route) =>
      route.fulfill({ json: ok({ total: placements.length, list: placements }) })
    )
    await page.route(`${API}/ads/materials*`, (route) =>
      route.fulfill({ json: ok({ total, list: [{ id: 7, name: '素材G' }] }) })
    )
  }

  test('D16 素材下拉：说清「共 102 条」，并按关键词去服务端搜第 101 条之后的素材', async ({ page }) => {
    await stubAds(page)
    await page.goto('/ads/placements')
    await page.getByRole('button', { name: '新建投放' }).click()
    const dlg = page.locator('.el-dialog').filter({ hasText: '新建投放' })
    await expect(dlg.getByText('素材库共 102 条')).toBeVisible({ timeout: NAV })

    const reqPromise = page.waitForRequest(
      (r) => r.url().includes('ads/materials') && new URL(r.url()).searchParams.get('keyword') === '素材Z',
      { timeout: NAV }
    )
    // el-select 的占位文字是 span，不是 input 的 placeholder；点开后 filterable 输入框才出现
    await dlg.locator('.el-select').first().click()
    await dlg.locator('.el-select__input').first().fill('素材Z')
    await reqPromise // 只有服务端搜索才能触达第 101 条起的素材
  })

  test('D15 同一天可以投：表单不许拦，闭区间口径写在提交之前', async ({ page }) => {
    await stubAds(page)
    await page.goto('/ads/placements')
    await page.getByRole('button', { name: '新建投放' }).click()
    const dlg = page.locator('.el-dialog').filter({ hasText: '新建投放' })
    await expect(dlg.getByText('区间含首尾')).toBeVisible({ timeout: NAV })

    // 单日投放：两个日期相同 → 必须能提交（修复前 start>=end 直接被拒，用户只能猜）
    await dlg.locator('.el-select').first().click()
    await dlg.locator('.el-select__input').first().fill('素材G')
    await page.locator('.el-select-dropdown__item').filter({ hasText: '素材G' }).first().click()
    await dlg.locator('.el-select').nth(1).click()
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await dlg.getByPlaceholder('开始日期').fill('2026-07-15')
    await dlg.getByPlaceholder('结束日期').fill('2026-07-15')
    await page.keyboard.press('Enter')

    const postPromise = page.waitForRequest(
      (r) => r.method() === 'POST' && r.url().includes('ads/placements'),
      { timeout: NAV }
    )
    await dlg.getByRole('button', { name: '确定' }).click()
    const post = await postPromise
    const body = JSON.parse(post.postData())
    expect(body.start_date).toBe('2026-07-15')
    expect(body.end_date).toBe('2026-07-15')

    // 提交成功后弹窗关闭，倒序用例要重新打开（同一次会话里的下一条规则）
    await page.getByRole('button', { name: '新建投放' }).click()
    await expect(dlg.getByText('区间含首尾')).toBeVisible({ timeout: NAV })

    // el-date-picker 的 daterange 会把两端自动排序，倒序状态在界面上不可达；
    // 倒序拦截由前端规则（中文 message）+ 后端 BizError 各自兜底，见单测与后端用例。
    // 界面上必须成立的是：闭区间与「只投一天」的口径写在用户点提交之前。
    await expect(dlg.getByText('只投一天可让两个日期相同')).toBeVisible({ timeout: NAV })
    await expect(dlg.getByText(/start_date 必须早于 end_date/)).toHaveCount(0)
  })

  // ---------------------------------------------------------------- C92 / H2 口径一致

  test('C92 分享链接转手动录入：来源类型标记看得见，也确实按 qrcode 入库', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/materials/share`, (route) =>
      route.fulfill({ json: ok({ available: true, title: '分享稿', content: '正文若干', url: 'https://s/1' }) })
    )

    await page.goto('/materials')
    await page.locator('.el-select').first().click()
    await page.locator('.el-select-dropdown__item').first().click()
    await page.getByRole('tab', { name: '二维码 / 链接分享' }).click()
    await page.locator('#pane-share').getByPlaceholder('https://...').fill('https://s/1')
    await page.getByRole('button', { name: '获取预览' }).click()
    await page.getByRole('button', { name: '转为手动录入' }).click()

    // 预填后来源类型就摆在表单上，而不是只写在提示语里
    await expect(page.getByText('二维码 / 链接分享').first()).toBeVisible({ timeout: NAV })
    const reqPromise = page.waitForRequest((r) => r.method() === 'POST' && r.url().endsWith('/materials'), {
      timeout: NAV,
    })
    await page.getByRole('button', { name: '保存到素材池' }).click()
    const req = await reqPromise
    expect(JSON.parse(req.postData()).source_type).toBe('qrcode')
    // 界面上不再出现英文枚举手手
    await expect(page.getByText('（source_type=qrcode）')).toHaveCount(0)
  })

  test('H2 桶名缺 -{APPID} 后缀：保存前就拦住并说明原因，不发请求', async ({ page }) => {
    await stubEverything(page)
    await page.route(`${API}/cos/config`, (route) =>
      route.fulfill({
        method: 'GET',
        json: ok({ loaded: true, load_error: null, updated_at: null, fallback_fields: [], region: 'ap-guangzhou', bucket: 'news-bucket', secret_id: '****', secret_key: '****', cdn_domain: '' }),
      })
    )

    await page.goto('/cos-config')
    const bucket = page.getByPlaceholder('如 news-1250000000（完整桶名，必须带 -{APPID} 数字后缀）')
    await expect(bucket).toBeVisible({ timeout: NAV })
    // 页面说明与校验错误都在说同一件事：系统不替你拼后缀
    await expect(page.locator('.field-tip').filter({ hasText: '系统不会自动拼接后缀' })).toBeVisible()

    await bucket.fill('news-bucket')
    await expect(page.locator('.bucket-suffix-alert')).toContainText('缺少 -{APPID} 数字后缀', { timeout: NAV })
    await page.getByRole('button', { name: '保存配置' }).click()
    await expectNoRequest(page, (r) => r.method() === 'PUT' && r.url().includes('cos/config'))

    // 补上后缀就能存（不是把用户堵死，而是给出可达的路径）
    await bucket.fill('news-1250000000')
    await expect(page.locator('.bucket-suffix-alert')).toHaveCount(0)
    const putPromise = page.waitForRequest((r) => r.method() === 'PUT' && r.url().includes('cos/config'), {
      timeout: NAV,
    })
    await page.getByRole('button', { name: '保存配置' }).click()
    await putPromise
  })
})
