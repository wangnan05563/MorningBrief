import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright 配置
 *
 * 设计要点：
 * - webServer 自动拉起 vite dev server，CI 下不复用已有实例避免污染
 * - 仅启用 chromium 项目，运营后台为内部系统无需跨浏览器测试
 * - trace 仅在首次重试时采集，平衡调试体验与磁盘开销
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  // CI 环境下禁止 .only 防止误提交
  forbidOnly: !!process.env.CI,
  // 仅 CI 重试，本地失败立即可见以加快调试
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // vite 首次编译各路由组件较慢，需更长导航超时
    navigationTimeout: 60000,
  },
  // 单个测试超时：vite 编译 + 多次重试可能耗时较长
  timeout: 60000,
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    // 本地复用已运行的 dev server，避免每次跑测试都重启
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
})
