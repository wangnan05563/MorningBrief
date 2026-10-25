/**
 * T02595：e2e 浏览器前置的判定与接线
 *
 * 缺缓存时 playwright 只会说 "Executable doesn't exist"，既不告诉人「装一下就好」，
 * 也不提「本机 Chrome 也能跑」。这组用例锁四件事：
 * 1. 四态优先级：PW_CHANNEL 显式 > 自带 chromium > 系统浏览器（仅本机）> 报错；
 * 2. 判定以 headless shell 为准——残缺缓存（只有完整 chromium）不算就绪；
 * 3. 报错必须自带两条修复命令，且与 README 口径一致（否则文档与报错各说各话）；
 * 4. config / globalSetup / package.json / CI 真的接上了，而不是只写了个没人调的函数。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/e2e-browser-plan.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  bundledBrowserPaths,
  checkBrowserPlan,
  detectBrowserPlan,
  planMessage,
  resolveBrowserPlan,
  systemBrowserCandidates,
} from '../../scripts/e2e-browser-plan.mjs'

const read = (rel) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
const CONFIG_SRC = read('../../playwright.config.js')
const SETUP_SRC = read('../global-setup.mjs')
const README_SRC = read('../../../../README.md')
const CI_SRC = read('../../../../.github/workflows/ci.yml')
const PKG = JSON.parse(read('../../package.json'))

const EXEC = '/pw/chromium-1228/chrome-win64/chrome.exe'

describe('缓存路径推导', () => {
  it('由 chromium-<rev> 推出同版本号的 headless shell（win/linux/darwin 子目录各不同）', () => {
    const win = bundledBrowserPaths({ execPath: EXEC, platform: 'win32', arch: 'x64' })
    assert.equal(win.full, EXEC)
    assert.ok(win.headlessShell.includes('chromium_headless_shell-1228'), win.headlessShell)
    assert.ok(win.headlessShell.includes('chrome-headless-shell-win64'))
    assert.ok(win.headlessShell.endsWith('.exe'))

    const linux = bundledBrowserPaths({ execPath: EXEC, platform: 'linux', arch: 'x64' })
    assert.ok(linux.headlessShell.includes('chromium_headless_shell-1228'))
    assert.ok(linux.headlessShell.includes('chrome-headless-shell-linux64'))

    const macArm = bundledBrowserPaths({ execPath: EXEC, platform: 'darwin', arch: 'arm64' })
    assert.ok(macArm.headlessShell.includes('chrome-headless-shell-mac-arm64'))
    const macX64 = bundledBrowserPaths({ execPath: EXEC, platform: 'darwin', arch: 'x64' })
    assert.ok(macX64.headlessShell.includes('chrome-headless-shell-mac-x64'))
  })

  it('win32 的 LOCALAPPDATA 候选按环境变量展开；变量缺失时不留占位符', () => {
    const expanded = systemBrowserCandidates({
      platform: 'win32',
      env: { LOCALAPPDATA: 'C:/Users/demo/AppData/Local' },
    })
    assert.ok(
      expanded.some((c) => c.path.includes('C:/Users/demo/AppData/Local') && c.path.includes('chrome.exe')),
      'LOCALAPPDATA 下的 Chrome 是常见的用户级安装位置',
    )
    const bare = systemBrowserCandidates({ platform: 'win32', env: {} })
    assert.ok(bare.length > 0)
    assert.ok(bare.every((c) => !c.path.includes('%LOCALAPPDATA%')), '展开失败必须丢弃，不能拿残缺路径去探测')
  })
})

describe('四态判定优先级', () => {
  it('PW_CHANNEL 显式指定优先于一切（含 CI 与自带就绪）', () => {
    const plan = resolveBrowserPlan({
      pwChannel: 'msedge',
      ci: true,
      bundledReady: true,
      system: { channel: 'chrome', label: '系统 Chrome' },
    })
    assert.equal(plan.mode, 'explicit')
    assert.equal(plan.channel, 'msedge')
  })

  it('自带 chromium 就绪时不再探测系统浏览器（channel 必须为空）', () => {
    const plan = resolveBrowserPlan({
      bundledReady: true,
      system: { channel: 'chrome', label: '系统 Chrome' },
    })
    assert.equal(plan.mode, 'bundled')
    assert.equal(plan.channel, null, 'bundled 模式不能顺手塞 channel，否则等于换浏览器跑')
  })

  it('非 CI 且自带缺失：回退系统浏览器（chrome 优先于 edge 由候选顺序保证）', () => {
    const plan = resolveBrowserPlan({
      bundledReady: false,
      system: { channel: 'chrome', label: '系统 Chrome' },
    })
    assert.equal(plan.mode, 'system')
    assert.equal(plan.channel, 'chrome')
  })

  it('CI 不自动回退：runner 上即使碰巧有系统浏览器也算缺失', () => {
    const plan = resolveBrowserPlan({
      ci: true,
      bundledReady: false,
      system: { channel: 'chrome', label: '系统 Chrome' },
    })
    assert.equal(plan.mode, 'missing')
    assert.equal(plan.channel, null)
    const msg = planMessage(plan)
    assert.match(msg, /CI/)
    assert.match(msg, /playwright install --with-deps chromium/)
    assert.match(msg, /ci\.yml/)
    assert.doesNotMatch(msg, /PW_CHANNEL/, 'CI 上不该建议借系统浏览器：runner 上没有，按这条路走只会白试')
  })

  it('一个都没有：缺失且报错里同时给出「装缓存」与「借系统浏览器」两条路', () => {
    const plan = resolveBrowserPlan({ bundledReady: false, system: null })
    assert.equal(plan.mode, 'missing')
    const msg = planMessage(plan)
    assert.match(msg, /npm run e2e:install/)
    assert.match(msg, /PW_CHANNEL=chrome/)
    assert.match(msg, /README/, '报错要指到文档，免得用户只看到一句命令')
  })
})

describe('真实探测（注入 IO，不依赖本机装没装浏览器）', () => {
  const linuxCandidates = systemBrowserCandidates({ platform: 'linux', env: {} })

  it('headless shell 存在 → bundled', () => {
    const plan = detectBrowserPlan({
      env: {},
      platform: 'linux',
      execPath: EXEC,
      fileExists: (p) => p.includes('chromium_headless_shell-1228'),
    })
    assert.equal(plan.mode, 'bundled')
  })

  it('只有完整 chromium、没有 headless shell：残缺缓存不算就绪', () => {
    // 默认 headless 跑的是 headless shell；只看 chrome.exe 会把启动失败误判成「已就绪」
    const plan = detectBrowserPlan({
      env: {},
      platform: 'linux',
      execPath: EXEC,
      candidates: linuxCandidates,
      fileExists: (p) => p === EXEC,
    })
    assert.equal(plan.mode, 'missing')
  })

  it('残缺缓存 + 系统 Chrome → 回退 chrome', () => {
    const plan = detectBrowserPlan({
      env: {},
      platform: 'linux',
      execPath: EXEC,
      candidates: linuxCandidates,
      fileExists: (p) => p === EXEC || p === '/usr/bin/google-chrome',
    })
    assert.equal(plan.mode, 'system')
    assert.equal(plan.channel, 'chrome')
  })

  it('只有 Edge 时回退 msedge；两者都在时 Chrome 优先', () => {
    const onlyEdge = detectBrowserPlan({
      env: {},
      platform: 'linux',
      execPath: EXEC,
      candidates: linuxCandidates,
      fileExists: (p) => p === '/usr/bin/microsoft-edge',
    })
    assert.equal(onlyEdge.channel, 'msedge')

    const both = detectBrowserPlan({
      env: {},
      platform: 'linux',
      execPath: EXEC,
      candidates: linuxCandidates,
      fileExists: (p) => p === '/usr/bin/microsoft-edge' || p === '/usr/bin/google-chrome',
    })
    assert.equal(both.channel, 'chrome')
  })

  it('PW_CHANNEL 从环境变量透传，且不被探测结果覆盖', () => {
    const plan = detectBrowserPlan({
      env: { PW_CHANNEL: 'msedge' },
      platform: 'linux',
      execPath: EXEC,
      fileExists: () => true,
    })
    assert.equal(plan.mode, 'explicit')
    assert.equal(plan.channel, 'msedge')
  })

  it('CI 环境变量同样透传：缺失时不拿系统浏览器兜底', () => {
    const plan = detectBrowserPlan({
      env: { CI: 'true' },
      platform: 'linux',
      execPath: EXEC,
      candidates: linuxCandidates,
      fileExists: (p) => p === '/usr/bin/google-chrome',
    })
    assert.equal(plan.mode, 'missing')
  })
})

describe('globalSetup 的打印与中止', () => {
  it('system/bundled/explicit 打印一行并放行，不抛错', () => {
    for (const plan of [
      { mode: 'bundled', channel: null, reason: 'ok' },
      { mode: 'explicit', channel: 'chrome', reason: 'PW_CHANNEL=chrome' },
      { mode: 'system', channel: 'chrome', reason: '回退 系统 Chrome' },
    ]) {
      const logs = []
      const result = checkBrowserPlan({ plan, log: (m) => logs.push(m) })
      assert.equal(result.mode, plan.mode)
      assert.equal(logs.length, 1, `${plan.mode} 模式应打印且只打印一行`)
    }
  })

  it('system 模式提示可以恢复自带浏览器', () => {
    const logs = []
    checkBrowserPlan({ plan: { mode: 'system', channel: 'chrome', reason: '回退 系统 Chrome' }, log: (m) => logs.push(m) })
    assert.match(logs[0], /npm run e2e:install/)
  })

  it('missing 才抛错（不是 system），且错误信息可直接照做', () => {
    assert.throws(
      () => checkBrowserPlan({ plan: { mode: 'missing', reason: '没浏览器' }, log: () => {} }),
      (err) => {
        assert.match(err.message, /npm run e2e:install/)
        assert.match(err.message, /PW_CHANNEL=chrome/)
        return true
      },
      'missing 必须中止整轮 e2e，否则每条用例都会各自报一遍同样的启动错误',
    )
  })
})

describe('接线：配置、门禁、脚本、文档与 CI 口径一致', () => {
  it('playwright.config.js 用浏览器前置的 channel，而不是自己读 PW_CHANNEL', () => {
    assert.match(CONFIG_SRC, /import\s*\{\s*detectBrowserPlan\s*\}\s*from\s*'\.\/scripts\/e2e-browser-plan\.mjs'/)
    assert.match(CONFIG_SRC, /browserPlan\.channel\s*\?\s*\{\s*channel:\s*browserPlan\.channel\s*\}/)
    assert.doesNotMatch(CONFIG_SRC, /process\.env\.PW_CHANNEL/, '两处各判一次就会漂移：显式覆盖只在前置里做')
  })

  it('globalSetup 在导航门禁之后跑浏览器前置', () => {
    assert.match(SETUP_SRC, /import\s*\{\s*checkBrowserPlan\s*\}\s*from\s*'\.\.\/scripts\/e2e-browser-plan\.mjs'/)
    const body = SETUP_SRC.slice(SETUP_SRC.indexOf('export default async function globalSetup'))
    assert.match(body, /runNavGate\(\)[\s\S]*checkBrowserPlan\(\)/, '先跑导航门禁，再验浏览器')
  })

  it('package.json 提供 e2e:install，且单测列表包含本文件', () => {
    assert.equal(PKG.scripts['e2e:install'], 'playwright install chromium')
    assert.ok(PKG.scripts['test:unit'].includes('tests/unit/e2e-browser-plan.test.mjs'))
  })

  it('README 写清两条路径（装缓存 / 借系统浏览器），且提到版本不匹配这一常见坑', () => {
    assert.match(README_SRC, /npm run e2e:install/)
    assert.match(README_SRC, /PW_CHANNEL=chrome/)
    assert.match(README_SRC, /管理后台 e2e/)
    assert.match(README_SRC, /版本不匹配|chromium-1248/, '只升级依赖不重装浏览器是这次的真实场景，文档要点明')
  })

  it('CI 先装 playwright 浏览器再跑 e2e（自动回退不适用于 CI）', () => {
    const install = CI_SRC.indexOf('npx playwright install --with-deps chromium')
    const e2e = CI_SRC.indexOf('npx playwright test')
    assert.ok(install >= 0, 'CI 必须保留浏览器安装步骤')
    assert.ok(e2e >= 0, 'CI 的 e2e 入口要在')
    assert.ok(install < e2e, '安装必须排在 e2e 之前，否则 runner 上直接 missing')
  })
})