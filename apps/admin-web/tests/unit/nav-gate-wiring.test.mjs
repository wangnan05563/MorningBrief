/**
 * 导航门禁的开发侧强制点（T02636 / 来源 T02500）
 *
 * 门禁脚本本身早就有了，缺的是「谁会去跑它」：原先只挂 Vite build 的 buildStart，
 * dev 与提交前都不跑，改坏一条引导 `aria-label` 要等到下一次打包才暴露。
 * 本单把它接到 `npx playwright test` 的 globalSetup，于是本地 e2e 与 CI 都会挡。
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
