/**
 * e2e 浏览器前置（T02595）
 *
 * 坑长这样：`npx playwright test` 只认「与 @playwright/test 同版本号的缓存目录」。
 * 缓存里躺着 chromium-1248、而 lockfile 里的 1.61.1 找 1228 时，启动报错是
 * `Executable doesn't exist at ...\chromium_headless_shell-1228\...`——
 * 对不熟悉 playwright 缓存布局的人来说，这句话既看不出「装一下就好」，
 * 也看不出「本机 Chrome 也能跑」，于是 e2e 在这台机器上直接瘫痪。
 * 只升级依赖、不重装浏览器，或者换一台没跑过 `playwright install` 的机器，都会命中。
 *
 * 这里给出四态计划，playwright.config.js 与 tests/global-setup.mjs 共用同一份判定：
 * - bundled：自带 chromium 就绪，行为与从前一致；
 * - explicit：PW_CHANNEL 显式指定，优先于一切探测（CI 上想固定渠道也用它）；
 * - system：自带缺失但本机有 Chrome/Edge（仅限非 CI），自动回退，并打印一行提示；
 * - missing：都没有（或 CI 上没装），globalSetup 直接抛错，把两条修复命令放进报错里。
 *
 * 判定口径：以 **headless shell** 的存在与否为准——默认 headless 跑的就是它，
 * 只装了完整 chromium（chromium-<rev>\chrome-win64）而缺 headless shell 的残缺缓存
 * 依旧会启动失败，不能算「就绪」。
 *
 * CI 刻意不自动回退：runner 上没有系统浏览器，且「先装浏览器再跑 e2e」是 CI 的既有契约
 * （.github/workflows/ci.yml 的 `npx playwright install --with-deps chromium`）。
 * 在 CI 上静默回退会把「CI 契约被破坏」伪装成绿灯。
 */
import { existsSync } from 'node:fs'
import { basename, dirname, join } from 'node:path'
import { chromium } from '@playwright/test'

/** 修复命令（报错与 README 共用同一口径，测试会锁住它们同时出现） */
export const INSTALL_COMMAND = 'npm run e2e:install'
export const INSTALL_LABEL = '下载 playwright 自带 chromium（与 CI 同款）'

/** 系统浏览器候选：channel 名 → 各平台可能安装路径（按优先级） */
const SYSTEM_BROWSERS = [
  {
    channel: 'chrome',
    label: '系统 Chrome',
    paths: {
      win32: [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        '%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe',
      ],
      darwin: ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'],
      linux: ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/opt/google/chrome/chrome'],
    },
  },
  {
    channel: 'msedge',
    label: '系统 Edge',
    paths: {
      win32: [
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
      ],
      darwin: ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'],
      linux: ['/usr/bin/microsoft-edge', '/usr/bin/microsoft-edge-stable'],
    },
  },
]

/**
 * 当前平台的系统浏览器候选（含具体路径，可直接 existsSync）。
 * `%LOCALAPPDATA%` 展开失败时丢弃该条，避免拿 `\Google\...` 这种残缺路径去探测。
 */
export function systemBrowserCandidates({ platform = process.platform, env = process.env } = {}) {
  const out = []
  for (const browser of SYSTEM_BROWSERS) {
    for (const raw of browser.paths[platform] || []) {
      if (!raw.includes('%LOCALAPPDATA%')) {
        out.push({ channel: browser.channel, label: browser.label, path: raw })
      } else if (env.LOCALAPPDATA) {
        out.push({
          channel: browser.channel,
          label: browser.label,
          path: raw.replace('%LOCALAPPDATA%', env.LOCALAPPDATA),
        })
      }
    }
  }
  return out
}

/**
 * 由 `chromium.executablePath()` 推出配套的 headless shell 路径。
 * 例（win）：<reg>\chromium-1228\chrome-win64\chrome.exe
 *        → <reg>\chromium_headless_shell-1228\chrome-headless-shell-win64\chrome-headless-shell.exe
 */
export function bundledBrowserPaths({ execPath, platform = process.platform, arch = process.arch }) {
  const subDir =
    {
      win32: 'chrome-headless-shell-win64/chrome-headless-shell.exe',
      darwin: `chrome-headless-shell-mac-${arch === 'arm64' ? 'arm64' : 'x64'}/chrome-headless-shell`,
      linux: 'chrome-headless-shell-linux64/chrome-headless-shell',
    }[platform] || 'chrome-headless-shell-linux64/chrome-headless-shell'
  const chromiumDir = dirname(dirname(execPath))
  const revision = basename(chromiumDir).replace(/^chromium-/, '')
  return {
    full: execPath,
    headlessShell: join(dirname(chromiumDir), `chromium_headless_shell-${revision}`, subDir),
  }
}

/**
 * 纯判定：把探测结果折叠成四态计划（无 IO，单测直接喂输入）。
 *
 * @param {{pwChannel?: string, ci?: boolean, bundledReady?: boolean,
 *          system?: {channel: string, label: string} | null,
 *          bundledPaths?: {full: string, headlessShell: string}}} input
 */
export function resolveBrowserPlan({ pwChannel = '', ci = false, bundledReady = false, system = null, bundledPaths = null }) {
  const where = bundledPaths ? `（期望：${bundledPaths.headlessShell}）` : ''
  if (pwChannel) {
    return { mode: 'explicit', channel: pwChannel, ci, reason: `PW_CHANNEL=${pwChannel} 显式指定` }
  }
  if (bundledReady) {
    return { mode: 'bundled', channel: null, ci, reason: 'playwright 自带 chromium 就绪' }
  }
  if (ci) {
    return {
      mode: 'missing',
      channel: null,
      ci,
      reason: `CI 环境不自动回退到系统浏览器，自带 chromium 缺失${where}`,
    }
  }
  if (system) {
    return {
      mode: 'system',
      channel: system.channel,
      ci,
      reason: `自带 chromium 缺失${where}，回退 ${system.label}`,
    }
  }
  return {
    mode: 'missing',
    channel: null,
    ci,
    reason: `自带 chromium 缺失${where}，本机也未找到 Chrome / Edge`,
  }
}

/** 真实探测：读环境变量、探缓存与系统浏览器，再交给 resolveBrowserPlan 折叠 */
export function detectBrowserPlan({
  env = process.env,
  fileExists = existsSync,
  platform = process.platform,
  arch = process.arch,
  execPath = chromium.executablePath(),
  candidates = systemBrowserCandidates({ platform, env }),
} = {}) {
  const bundledPaths = bundledBrowserPaths({ execPath, platform, arch })
  return resolveBrowserPlan({
    pwChannel: env.PW_CHANNEL || '',
    ci: !!env.CI,
    bundledReady: fileExists(bundledPaths.headlessShell),
    system: candidates.find((c) => fileExists(c.path)) || null,
    bundledPaths,
  })
}

/** 计划 → 人话（globalSetup 打印/抛错都用它；修复命令原文在此，README 与测试对齐同一口径） */
export function planMessage(plan) {
  switch (plan.mode) {
    case 'bundled':
      return '[e2e] 浏览器前置：使用 playwright 自带 chromium'
    case 'explicit':
      return `[e2e] 浏览器前置：${plan.reason}（跳过自动探测）`
    case 'system':
      return `[e2e] 浏览器前置：${plan.reason}；要恢复自带浏览器：${INSTALL_COMMAND}`
    default: {
      const lines = ['[e2e 浏览器前置] 没有可用浏览器，已中止：', `  - ${plan.reason}`]
      if (plan.ci) {
        lines.push(
          '  CI 上必须先在 e2e 之前安装（.github/workflows/ci.yml 就是这一步）：',
          '    npx playwright install --with-deps chromium',
        )
      } else {
        lines.push(
          '  二选一修复后重跑（命令在 apps/admin-web 下执行）：',
          `    ${INSTALL_COMMAND}                   # ${INSTALL_LABEL}`,
          '    PW_CHANNEL=chrome npx playwright test    # 借用本机 Chrome/Edge（PowerShell 先执行 $env:PW_CHANNEL="chrome"）',
        )
      }
      lines.push('  文档：README「测试 → 管理后台 e2e（Playwright）」')
      return lines.join('\n')
    }
  }
}

/**
 * globalSetup 用：missing 直接抛错（比 playwright 那句 "Executable doesn't exist" 可执行得多），
 * 其余模式打印一行选定结果，便于排查「为什么这次用的是系统 Chrome」。
 */
export function checkBrowserPlan({ plan = detectBrowserPlan(), log = console.log } = {}) {
  const message = planMessage(plan)
  if (plan.mode === 'missing') throw new Error(message)
  log(message)
  return plan
}