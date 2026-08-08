import { test, expect } from '@playwright/test'
import {
  setLoginState,
  workflowListResponse,
  workflowListMultiSelectResponse,
  workflowDetailResponse,
  workflowTriggerResponse,
  workflowBatchDeleteResponse,
  channelsListResponse,
  materialsListResponse,
  workflowAudioResponse,
} from './helpers/mock'

/**
 * 工作流监控 E2E 测试
 *
 * 覆盖：
 * - 列表加载
 * - 非 admin 不显示触发按钮（RBAC）
 * - 跳转详情
 * - 详情页步骤展示
 */
test.describe('工作流监控', () => {
  // vite 首次按需编译路由组件可能耗时 15-25s，给到 30s 避免 flaky
  test.use({ expect: { timeout: 30000 } })

  test.beforeEach(async ({ page }) => {
    // mock SSE 连接：WorkflowList 会发起 SSE 连接，后端未运行时 ECONNREFUSED 导致 flaky
    await page.route('**/admin/api/v1/events/stream**', async (route) => {
      // SSE 返回空的事件流，避免连接错误
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: '',
      })
    })
    // mock channels API：WorkflowList 可能调用 channels API
    await page.route('**/admin/api/v1/channels**', async (route) => {
      await route.fulfill({ json: channelsListResponse })
    })

    // 注意：具体接口（素材 / 音频 / 详情 / 触发）必须在 workflows* catch-all
    // 之前注册——Playwright 按注册顺序匹配、先匹配先处理，否则 catch-all 会
    // 抢先拦截 /workflows/wf-001/audio 等请求并返回列表数据，导致详情/产物面板
    // 拿到错误结构。

    // 素材列表接口（工作流详情页「爬虫采集·素材」面板）
    await page.route('**/admin/api/v1/materials**', async (route) => {
      await route.fulfill({ json: materialsListResponse })
    })

    // 工作流音频接口（「语音合成·TTS 片段」「音频拼接·成品」面板）
    // 模拟打包态/COS 模式：返回 remote:true 的云端音频，验证回退逻辑
    await page.route('**/admin/api/v1/workflows/wf-001/audio', async (route) => {
      await route.fulfill({ json: workflowAudioResponse })
    })

    // 工作流详情接口
    await page.route('**/admin/api/v1/workflows/wf-001', async (route) => {
      await route.fulfill({ json: workflowDetailResponse })
    })

    // 触发接口
    await page.route('**/admin/api/v1/workflows/trigger', async (route) => {
      await route.fulfill({ json: workflowTriggerResponse })
    })

    // 工作流列表接口（catch-all，放在最后）：glob 尾部带 * 以匹配查询参数
    await page.route('**/admin/api/v1/workflows*', async (route) => {
      await route.fulfill({ json: workflowListResponse })
    })
  })

  test('工作流列表加载', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows')

    await expect(page.getByText('工作流监控').first()).toBeVisible({ timeout: 30000 })
    // 表格应展示 mock 数据
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('wf-002')).toBeVisible({ timeout: 30000 })
    // 状态标签
    await expect(page.locator('.el-tag').filter({ hasText: '成功' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.el-tag').filter({ hasText: '运行中' })).toBeVisible({ timeout: 30000 })
  })

  test('非 admin 不显示触发按钮', async ({ page }) => {
    // operator 角色访问工作流列表页
    // 注意：路由守卫对 requireRole === 'admin' 拒绝跳转，但仅作用于 /workflows 路由
    // 这里直接访问，验证 v-if="userStore.isAdmin" 不渲染按钮
    await setLoginState(page, 'operator')
    await page.goto('/workflows')

    // 由于 operator 角色无权访问工作流路由，会被守卫拦截
    // 但即便访问成功，也不应看到"手动触发"按钮
    await expect(page.getByRole('button', { name: '手动触发' })).toHaveCount(0, { timeout: 30000 })
  })

  test('admin 显示触发按钮并可触发', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows')

    // admin 应看到触发按钮
    await expect(page.getByRole('button', { name: '手动触发' })).toBeVisible({ timeout: 30000 })

    // 点击触发
    await page.getByRole('button', { name: '手动触发' }).click()
    // ElMessageBox 二次确认（项目未配置中文 locale，默认按钮文本为 OK）
    await page.getByRole('button', { name: 'OK' }).click()

    // 应显示成功提示，包含新工作流 ID
    await expect(page.locator('.el-message').getByText('已触发，工作流 ID: wf-003')).toBeVisible({ timeout: 30000 })
  })

  test('点击工作流跳转详情', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows')

    // 点击工作流 ID 链接
    // Element Plus 的 el-link 渲染为 generic 元素而非 link role，故用 .el-link 类定位
    await page.locator('.el-link').filter({ hasText: 'wf-001' }).click()

    // 应跳转到详情页
    await expect(page).toHaveURL(/\/workflows\/wf-001$/, { timeout: 30000 })
  })

  test('工作流详情显示步骤', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows/wf-001')

    await expect(page.getByText('工作流详情').first()).toBeVisible({ timeout: 30000 })

    // 基础信息
    await expect(page.getByText('wf-001').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('2026-07-08').first()).toBeVisible({ timeout: 30000 })
    // 详情页有 1 个工作流状态 tag + 5 个步骤状态 tag 都可能显示"成功"，存在 strict mode 冲突，取第一个即可
    await expect(page.locator('.el-tag').filter({ hasText: '成功' }).first()).toBeVisible({ timeout: 30000 })

    // 5 个步骤标签应出现在进度条中
    // 详情页步骤名同时出现在 el-step 标题、表格单元格、tooltip 等多处，getByText 会命中多个节点触发 strict mode，取 .first()
    await expect(page.getByText('爬虫采集').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('LLM改写').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('语音合成').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('音频拼接').first()).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('创建审核').first()).toBeVisible({ timeout: 30000 })

    // 步骤详情表格也应展示这些步骤名
    const crawlCells = page.locator('td').filter({ hasText: '爬虫采集' })
    await expect(crawlCells.first()).toBeVisible({ timeout: 30000 })
  })

  test('admin 批量删除工作流：多选+确认+请求载荷+成功提示+列表刷新', async ({ page }) => {
    // 拦截批量删除请求：校验 payload 后返回成功
    let capturedPayload = null
    let batchDeleteCallCount = 0
    let listCallCount = 0

    await page.route('**/admin/api/v1/workflows/batch-delete', async (route) => {
      batchDeleteCallCount += 1
      const body = route.request().postDataJSON()
      capturedPayload = body
      await route.fulfill({ json: workflowBatchDeleteResponse })
    })

    // 列表接口：首次加载返回 3 条，删除后刷新返回 1 条
    await page.route('**/admin/api/v1/workflows*', async (route) => {
      listCallCount += 1
      // 第 1 次加载返回 3 条可删除工作流；第 2 次（删除后刷新）返回剩余 1 条
      if (listCallCount === 1) {
        await route.fulfill({ json: workflowListMultiSelectResponse })
      } else {
        await route.fulfill({
          json: {
            code: 0,
            message: 'success',
            data: {
              total: 1,
              list: [
                {
                  id: 'wf-003',
                  episode_date: '2026-07-06',
                  source: 'cron',
                  status: 'failed',
                  started_at: '2026-07-06T05:00:00',
                  finished_at: '2026-07-06T05:10:00',
                },
              ],
            },
          },
        })
      }
    })

    await setLoginState(page, 'admin')
    await page.goto('/workflows')

    // 等待列表加载完成
    await expect(page.getByText('wf-001')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('wf-002')).toBeVisible({ timeout: 30000 })

    // admin 应看到批量删除按钮（初始禁用，因为未选中）
    const batchDeleteBtn = page.getByRole('button', { name: '批量删除' })
    await expect(batchDeleteBtn).toBeVisible({ timeout: 30000 })
    await expect(batchDeleteBtn).toBeDisabled({ timeout: 30000 })

    // 选择前两行（wf-001, wf-002）：勾选 el-table 的 selection checkbox
    // el-table 的选择框渲染为 .el-checkbox，每行第一个 cell 内
    const rowCheckboxes = page.locator('.el-table__body .el-checkbox')
    await rowCheckboxes.nth(0).click()
    await rowCheckboxes.nth(1).click()

    // 选中后按钮应启用，并显示选中数量
    await expect(batchDeleteBtn).toBeEnabled({ timeout: 30000 })
    // 选中计数提示（"已选 2 项"）
    await expect(page.getByText('已选 2 项')).toBeVisible({ timeout: 30000 })

    // 点击批量删除
    await batchDeleteBtn.click()

    // ElMessageBox 二次确认：WorkflowList.vue 中设置 confirmButtonText 为"确定删除"
    await page.getByRole('button', { name: '确定删除' }).click()

    // 验证请求载荷：workflow_ids 包含 wf-001 和 wf-002
    await expect.poll(() => batchDeleteCallCount).toBe(1)
    expect(capturedPayload).toBeTruthy()
    expect(capturedPayload.workflow_ids).toEqual(
      expect.arrayContaining(['wf-001', 'wf-002'])
    )
    expect(capturedPayload.workflow_ids).toHaveLength(2)

    // 验证成功提示
    await expect(page.locator('.el-message').getByText(/删除成功|已删除/)).toBeVisible({ timeout: 30000 })

    // 验证列表刷新：第二次 list 调用应被触发
    await expect.poll(() => listCallCount).toBeGreaterThanOrEqual(2)

    // 删除后选中状态应重置：批量删除按钮应再次禁用
    await expect(batchDeleteBtn).toBeDisabled({ timeout: 30000 })
  })

  test('非 admin 不显示批量删除按钮', async ({ page }) => {
    // operator 角色不应看到批量删除按钮（RBAC）
    await setLoginState(page, 'operator')
    await page.goto('/workflows')

    // 即使路由守卫拦截，按钮也不应渲染
    await expect(page.getByRole('button', { name: '批量删除' })).toHaveCount(0, { timeout: 30000 })
  })

  // 验证修复：打包态/COS 模式下，本地 audio_cache 为空，list_audio 回退到 DB
  // 持久化的 audio_url（remote:true），详情页三面板仍能展示内容、且远程对象不渲染删除按钮。
  test('打包态(COS)下工作流详情三面板可展示内容', async ({ page }) => {
    await setLoginState(page, 'admin')
    await page.goto('/workflows/wf-001')

    await expect(page.getByText('工作流详情').first()).toBeVisible({ timeout: 30000 })

    // 1) 爬虫采集 · 素材：展开后展示 2 条素材
    await page.locator('.el-collapse-item__header', { hasText: '爬虫采集 · 素材' }).click()
    await expect(page.getByText('测试素材一：AI 芯片突破')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('测试素材二：新能源政策')).toBeVisible({ timeout: 30000 })

    // 2) 语音合成 · TTS 片段：展开后展示 2 个远程片段（seg_1.mp3 / seg_2.mp3）
    await page.locator('.el-collapse-item__header', { hasText: '语音合成 · TTS 片段' }).click()
    await expect(page.getByText('seg_1.mp3')).toBeVisible({ timeout: 30000 })
    await expect(page.getByText('seg_2.mp3')).toBeVisible({ timeout: 30000 })
    // 远程对象不应渲染「删除」按钮（v-if="!row.remote"）
    await expect(
      page.locator('.el-collapse-item').filter({ hasText: '语音合成' }).getByRole('button', { name: '删除' }),
    ).toHaveCount(0, { timeout: 30000 })

    // 3) 音频拼接 · 成品：展开后展示「已生成」，且远程成品不渲染「删除成品」按钮
    await page.locator('.el-collapse-item__header', { hasText: '音频拼接 · 成品' }).click()
    await expect(page.getByText('已生成')).toBeVisible({ timeout: 30000 })
    await expect(page.getByRole('button', { name: '删除成品' })).toHaveCount(0, { timeout: 30000 })
  })
})
