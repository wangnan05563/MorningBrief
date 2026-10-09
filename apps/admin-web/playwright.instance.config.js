import { defineConfig, devices } from '@playwright/test'

/**
 * 对「运行中安装实例」直跑的 e2e 配置（实例通道）
 *
 * - baseURL 带 /news 前缀（SPA 挂在该路径下），测试用例的 goto 需写 /news/... 前缀
 *   （本仓库跑实例通道时用 sed 生成带前缀的 spec 副本，见 tests/_instance/）
 * - API 全 mock：不会触达真实后端数据，可安全对生产实例直跑
 * - webServer 置 undefined：不拉起 vite dev（本机沙箱下 dev/preview 不可靠）
 */
export default defineConfig({
  testDir: './tests/_instance',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8000/news',
    trace: 'off',
    screenshot: 'only-on-failure',
    navigationTimeout: 30000,
    launchOptions: {
      executablePath: 'C:\\Users\\hspcadmin\\AppData\\Local\\ms-playwright\\chromium-1243\\chrome-win64\\chrome.exe',
    },
  },
  timeout: 60000,
  expect: { timeout: 20000 },
  outputDir: 'D:/code/otherProjects/20_News/runtime/pw-instance-output',
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // T00833 响应式：<1440px 时 .page-container 收窄为 16px，守卫断言按 24px 基线跑 1600px 桌面视口
        viewport: { width: 1600, height: 900 },
      },
    },
  ],
})
