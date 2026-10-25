import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { detectBrowserPlan } from './scripts/e2e-browser-plan.mjs'

/**
 * Playwright 配置
 *
 * 设计要点：
 * - webServer 自动拉起 vite dev server，CI 下不复用已有实例避免污染
 * - 仅启用 chromium 项目，运营后台为内部系统无需跨浏览器测试
 * - trace 仅在首次重试时采集，平衡调试体验与磁盘开销
 * - globalSetup 跑导航一致性门禁（T02636）：门禁原先只挂 vite build，
 *   dev 与提交前都不跑，改坏引导/菜单引用要等到下一次打包才暴露；
 *   `npx playwright test` 是本地与 CI 都会跑的命令，接这里才闭环
 * - 浏览器前置（T02595）：自带 chromium 缓存缺失/版本不匹配时，本机（非 CI）
 *   自动回退系统 Chrome/Edge，而不是让整轮 e2e 死在 "Executable doesn't exist"；
 *   判定与打印在 scripts/e2e-browser-plan.mjs，globalSetup 里同口径再跑一次（missing 直接中止）
 */
const browserPlan = detectBrowserPlan()

export default defineConfig({
  testDir: './tests',
  globalSetup: fileURLToPath(new URL('./tests/global-setup.mjs', import.meta.url)),
  // tests/unit/ 放 node:test 的纯函数用例（npm run test:unit），
  // 不能让 playwright 按 *.test.mjs 把它们当 e2e 收集——它没有浏览器夹具
  testIgnore: '**/unit/**',
  fullyParallel: true,
  // CI 环境下禁止 .only 防止误提交
  forbidOnly: !!process.env.CI,
  // 仅 CI 重试，本地失败立即可见以加快调试
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5181',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // vite 首次编译各路由组件较慢，需更长导航超时
    navigationTimeout: 60000,
  },
  // 单个测试超时：vite 编译 + 多次重试可能耗时较长
  timeout: 60000,
  projects: [
    // channel 来自浏览器前置：PW_CHANNEL 显式指定 > 自带 chromium > 系统 Chrome/Edge（仅本机）
    // CI 不自动回退，runner 上必须先 `npx playwright install chromium`（见 .github/workflows/ci.yml）
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(browserPlan.channel ? { channel: browserPlan.channel } : {}),
      },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5181',
    // 本地复用已运行的 dev server，避免每次跑测试都重启
    reuseExistingServer: !process.env.CI,
    // vite 首次冷启动 + 依赖预构建可能耗时 2-3 分钟（Windows + HDD 环境）
    timeout: 180000,
  },
})
