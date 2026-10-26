/**
 * 导航门禁的开发侧强制点（T02636 / 来源 T02500）
 *
 * 门禁脚本本身早就有了，缺的是「谁会去跑它」：原先只挂 Vite build 的 buildStart，
 * dev 与提交前都不跑，改坏一条引导 `aria-label` 要等到下一次打包才暴露。
 * T02636 把它接到 `npx playwright test` 的 globalSetup，于是本地 e2e 与 CI 都会挡；
 * T02737 再把它显式接进 CI 的 frontend job（构建之前，红了不必等几分钟构建）。
 *
 * 这里锁四件事（真实子进程的行为留给验收与探针，见 _validate/news2/result_T02636.md）：
 * 1. playwright 配置确实指向 globalSetup 文件——没接线的门禁等于没有门禁；
 * 2. 两步都在（validate:nav + test:nav）且输出直通（stdio: 'inherit'），
 *    否则失败时只剩一句 exit code 1，没人知道改坏了哪一步；
 * 3. 任一步非 0 必须抛错中止：一个「永远返回通过」的前置比没有前置更糟；
 * 4. CI 走的仍是经过 globalSetup 的 `npx playwright test`。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { before, describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

const CFG_URL = new URL('../../playwright.config.js', import.meta.url)
const CI_URL = new URL('../../../../.github/workflows/ci.yml', import.meta.url)
const SETUP_URL = new URL('../global-setup.mjs', import.meta.url)

let setup
let configSource

before(async () => {
  configSource = readFileSync(fileURLToPath(CFG_URL), 'utf8')
  setup = await import(SETUP_URL)
})

describe('导航门禁接入 e2e 全局前置', () => {
  it('playwright.config.js 把 globalSetup 指向 tests/global-setup.mjs', () => {
    assert.match(
      configSource,
      /globalSetup:\s*fileURLToPath\(new URL\('\.\/tests\/global-setup\.mjs'/,
      '配置里必须真的接线，而不是只写了个没人 import 的文件',
    )
  })

  it('前置覆盖 validate:nav 与 test:nav 两步，且输出直通', () => {
    const { NAV_GATE_STEPS } = setup
    assert.deepEqual(
      NAV_GATE_STEPS.map((s) => s.args),
      [['scripts/validate-nav.mjs'], ['--test', 'scripts/validate-nav.test.mjs']],
      '门禁自身测试（test:nav）不能省：永远通过的门禁比没有门禁更糟',
    )
    for (const step of NAV_GATE_STEPS) {
      assert.equal(step.stdio, 'inherit', `${step.name} 的输出必须直通终端`)
      assert.ok(step.name.includes('nav'), '步骤名要能看出跑的是哪道门禁')
    }
  })

  it('任一步非 0：抛出可读错误并中止，绝不静默放行', () => {
    const seen = []
    const ok = (cmd, args, opts) => {
      seen.push({ cmd, args, opts })
      return { status: 0 }
    }
    setup.runNavGate({ run: ok, execPath: 'node' })
    assert.equal(seen.length, 2, '两步都要真的执行')
    assert.equal(seen[0].cmd, 'node', '要用 node 直接跑脚本，而不是 npm（多一层进程且输出更难归因）')
    assert.equal(seen[0].args[0], 'scripts/validate-nav.mjs')
    assert.ok(seen[0].opts.cwd.endsWith('admin-web'), '子进程要在 admin-web 里跑')
    assert.equal(seen[0].opts.stdio, 'inherit')

    assert.throws(
      () => setup.runNavGate({ run: () => ({ status: 1 }), execPath: 'node' }),
      /validate:nav/,
      '第一步失败即中止，并点名是哪道门禁',
    )

    assert.throws(
      () =>
        setup.runNavGate({
          run: (cmd, args) => (args[0] === '--test' ? { status: 1 } : { status: 0 }),
          execPath: 'node',
        }),
      /test:nav/,
      '门禁自身测试失败同样要拦住 e2e',
    )
  })

  it('真实跑一遍前置：当前代码树必须通过（否则门禁自己就是红的）', () => {
    // 注入缺省执行器：真的 spawn node 跑 validate:nav + test:nav。
    // 这一条把上面所有「假执行器」断言钉回现实——否则测的只是我编的返回值。
    setup.runNavGate()
  })

  it('CI 走的是带前置门禁的 playwright 入口', () => {
    const ci = readFileSync(fileURLToPath(CI_URL), 'utf8')
    assert.match(ci, /npx playwright test/, 'CI 必须经过 playwright（含 globalSetup）')
  })
})

/**
 * T02737：同一道门禁在 CI 里的位置与可跑性。
 *
 * 为什么单独立一组而不是并进上面：上面锁的是「开发侧（本地 e2e）跑不跑」，这里锁的是
 * 「CI 跑不跑、什么时候跑」。两者是不同的失效面——globalSetup 被删，本地和 CI 一起失效；
 * 而 CI 少了这两步时，本地开发者照样绿，只有别人机器上的构建才漏。
 */
describe('导航门禁接入 CI', () => {
  /** 取出 frontend-build-test 这个 job 的原文（按 job 名切，避免全文件匹配到小程序 job 的步骤） */
  const frontendJob = () => {
    const ci = readFileSync(fileURLToPath(CI_URL), 'utf8')
    const start = ci.indexOf('  frontend-build-test:')
    assert.ok(start >= 0, 'CI 里得存在 frontend-build-test job')
    const rest = ci.slice(start + 2)
    const next = rest.search(/^ {2}\S/m)
    return rest.slice(0, next < 0 ? undefined : next)
  }

  /** 按出现顺序收集 `- name: ...` 对应的 run 命令（逐行扫，注释/if/uses 行都不算步骤） */
  const runSteps = (jobText) => {
    const steps = []
    let pending = null
    for (const raw of jobText.split(/\r?\n/)) {
      const name = /^\s*- name:\s*(.+)$/.exec(raw)
      if (name) {
        pending = name[1].trim()
        continue
      }
      const run = /^\s*run:\s*(.+)$/.exec(raw)
      if (run && pending) {
        steps.push({ name: pending, run: run[1].trim() })
        pending = null
      }
    }
    return steps
  }

  it('CI 显式跑 validate:nav 与 test:nav，且都在构建之前', () => {
    const steps = runSteps(frontendJob())
    const idxOf = (needle) =>
      steps.findIndex((s) => s.run.includes(needle))
    const install = idxOf('npm ci')
    const build = idxOf('npm run build')
    const nav = idxOf('npm run validate:nav')
    const selfTest = idxOf('npm run test:nav')

    assert.ok(nav >= 0, 'CI 必须有 `npm run validate:nav` 这一步')
    assert.ok(selfTest >= 0, 'CI 必须也跑门禁自身测试 `npm run test:nav`')
    assert.ok(build >= 0, '对照基准（构建步骤）要在')
    // 顺序而非存在性：放在构建后面，红一次要白等几分钟构建，等于没人愿意修
    assert.ok(install < nav && nav < build, 'validate:nav 要夹在 npm ci 与 npm run build 之间')
    assert.ok(install < selfTest && selfTest < build, 'test:nav 同样要前置')
    assert.ok(nav < selfTest, '门禁先跑、门禁的测试随后（与 e2e 前置的顺序一致）')
  })

  it('这两步都在 apps/admin-web 里执行，且步骤名能看出跑的是什么', () => {
    const steps = runSteps(frontendJob())
    for (const s of steps) {
      if (!/npm run (validate:nav|test:nav)/.test(s.run)) continue
      assert.match(s.run, /cd apps\/admin-web &&/, `${s.name}：仓库根目录下没有这两个 script`)
      assert.match(s.name, /导航/, `${s.name}：步骤名要能一眼看出是导航门禁，不能只写 npm 脚本名`)
    }
  })

  it('门禁脚本只依赖 node 内置模块且无平台分支（ubuntu runner 上可跑）', () => {
    // 票据要求「确认两个脚本在 ubuntu runner + Node 20 下可跑」。这里能静态锁死的是依赖面：
    // 只要门禁 import 了三方包，CI 里它的可跑性就取决于 npm ci 是否成功、镜像是否可用；
    // 只要它按平台分支，本地（win）绿就推不出 CI（linux）绿。这两点必须被断言，而不是写在注释里。
    for (const rel of ['../../scripts/validate-nav.mjs', '../../scripts/validate-nav.test.mjs']) {
      const src = readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
      const imports = [...src.matchAll(/from\s+['"]([^'"]+)['"]/g)].map((m) => m[1])
      for (const spec of imports) {
        if (spec.startsWith('node:')) continue
        // 相对 import 只允许在 scripts/ 目录内部（门禁自测引门禁本体）；
        // 一旦越出去引到 src/**，就会把 vue/element-plus 这条依赖链拽进门禁，CI 上它就不再是秒级检查
        assert.match(
          spec,
          /^\.\.?\/(?!.*\/)/,
          `门禁脚本不应引入三方包或跨目录依赖（CI 上等于把可跑性押在 npm ci 上）：${rel} import 了 ${spec}`,
        )
      }
      assert.doesNotMatch(
        src,
        /process\.platform|os\.platform\(\)/,
        `门禁不应按平台分支，否则 win 上绿不等于 ubuntu 上绿：${rel}`,
      )
      assert.doesNotMatch(
        src,
        /\b[A-Za-z]:[\\/]/,
        `门禁里不能出现盘符路径（linux 无此路径）：${rel}`,
      )
    }
  })
})

/**
 * T02656：引导步骤的「空态跳过」判据。
 *
 * 引导的落空有两种：数据为空导致的「这一步此刻不该出现」（应跳过）与锚点被改名
 * 导致的「指不到该指的东西」（应报缺陷）。把两者混在一起，空态实例上用户会看到
 * 一句对着空气的说明，而真回归又会被「跳过」静默吞掉。这里锁纯函数判据、配置声明、
 * 浮层接线与审计分级四层。
 */
const OVERLAY_SRC = readFileSync(
  fileURLToPath(new URL('../../src/components/GuideOverlay.vue', import.meta.url)),
  'utf8',
)
const AUDIT_SRC = readFileSync(
  fileURLToPath(new URL('../../scripts/guide-anchor-audit.mjs', import.meta.url)),
  'utf8',
)
const LLM_METRICS_SRC = readFileSync(
  fileURLToPath(new URL('../../src/views/stats/LlmMetrics.vue', import.meta.url)),
  'utf8',
)
const CHANNEL_HEALTH_SRC = readFileSync(
  fileURLToPath(new URL('../../src/views/stats/ChannelHealth.vue', import.meta.url)),
  'utf8',
)
const { GUIDE_STEPS } = await import('../../src/guide/guideConfig.js')
const { decideGuideStep, GUIDE_MISSING_BROKEN, GUIDE_MISSING_TEXT } =
  await import('../../src/guide/resolveStep.js')

describe('引导空态步骤判据（T02656）', () => {
  it('命中目标就高亮，空态标记不应抢走优先级', () => {
    const r = decideGuideStep(
      { s: ['[data-guide="x"]'], skipWhenEmpty: '[data-guide="x-empty"]' },
      { targetFound: true, emptyFound: true },
    )
    assert.deepEqual(r, { action: 'highlight', reason: '' })
  })

  it('目标缺席且空态标记确实存在：跳过，而不是居中念一句空话', () => {
    const r = decideGuideStep(
      { s: ['[data-guide="x"]'], skipWhenEmpty: '[data-guide="x-empty"]' },
      { targetFound: false, emptyFound: true },
    )
    assert.deepEqual(r, { action: 'skip', reason: 'empty' })
  })

  it('声明了空态但空态标记也不存在：仍按缺陷露出（锚点被改名不能被静默吞掉）', () => {
    const r = decideGuideStep(
      { s: ['[data-guide="x"]'], skipWhenEmpty: '[data-guide="x-empty"]' },
      { targetFound: false, emptyFound: false },
    )
    assert.deepEqual(r, { action: 'center', reason: GUIDE_MISSING_BROKEN })
    assert.equal(GUIDE_MISSING_BROKEN, 'broken')
  })

  it('没有选择器的纯文案步骤：设计性居中', () => {
    const r = decideGuideStep({ t: '说明', d: '……' }, {})
    assert.deepEqual(r, { action: 'center', reason: GUIDE_MISSING_TEXT })
    assert.equal(GUIDE_MISSING_TEXT, 'text')
  })

  it('有选择器却没命中、也没声明空态：缺陷', () => {
    const r = decideGuideStep({ s: ['[data-guide="gone"]'] }, {})
    assert.deepEqual(r, { action: 'center', reason: GUIDE_MISSING_BROKEN })
  })

  it('两个数据依赖步骤都声明了空态选择器，且选择器在视图空态分支里真实存在', () => {
    const rates = GUIDE_STEPS['/stats/llm-metrics'].find((s) => s.t === '重试率概览')
    const cards = GUIDE_STEPS['/stats/channel-health'].find((s) => s.t === '频道卡片')
    assert.equal(rates.skipWhenEmpty, '[data-guide="llm-metrics-empty"]')
    assert.equal(cards.skipWhenEmpty, '[data-guide="channel-health-empty"]')
    // 空态锚点必须挂在 el-empty 上（v-if 空态分支），否则跳过条件永远不成立
    assert.match(LLM_METRICS_SRC, /<el-empty[\s\S]{0,220}data-guide="llm-metrics-empty"/)
    assert.match(CHANNEL_HEALTH_SRC, /<el-empty[^>]*data-guide="channel-health-empty"/)
  })

  it('浮层按判据分流：skip 直接下一步，居中时把原因写进 data-guide-missing', () => {
    assert.match(OVERLAY_SRC, /decideGuideStep\(step,/)
    assert.match(OVERLAY_SRC, /decision\.action === 'skip'[\s\S]{0,200}guide\.next\(\)/)
    assert.match(OVERLAY_SRC, /dataset\.guideMissing = decision\.reason/)
    assert.doesNotMatch(OVERLAY_SRC, /dataset\.guideMissing = currentStep\.value\.s/)
  })

  it('审计只把 broken 计入未命中，跳过与设计性居中分开统计', () => {
    assert.match(AUDIT_SRC, /s\.missing === 'broken'/)
    assert.match(AUDIT_SRC, /s\.skipped/)
    assert.match(AUDIT_SRC, /argv\.includes\('--empty'\)/)
    assert.match(AUDIT_SRC, /skippedSteps/)
  })
})
