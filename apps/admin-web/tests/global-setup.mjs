/**
 * e2e 全局前置门禁：导航一致性接到「日常开发会跑的命令」上（T02636 / 来源 T02500）
 *
 * 为什么要挪到这里：门禁原先只挂 Vite `build` 的 buildStart，dev 与提交前都不跑
 * （仓库没有 ESLint，也没有 pre-commit 钩子）。改坏引导 `aria-label` 或菜单引用的人，
 * 要等到下一次**打包**才发现——而打包往往已经在发布流程里了。
 * `npx playwright test` 是本地与 CI 都会跑的那条命令，把它变成强制点即可闭环，
 * 同时保持 dev 不被门禁拖停（vite.config.js 的取向不变）。
 *
 * 覆盖两项：validate:nav（引用一致性）+ test:nav（门禁自身的测试）。
 * 后者不能省：一个永远返回通过的门禁比没有门禁更糟。
 * 输出用 `stdio: 'inherit'` 直通子进程，失败时能直接看到「哪个引导步骤、哪个选择器」，
 * 而不是一句 exit code 1。
 */
import { spawnSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

export const NAV_GATE_STEPS = [
  {
    name: '导航引用一致性（validate:nav）',
    args: ['scripts/validate-nav.mjs'],
    stdio: 'inherit',
  },
  {
    name: '导航门禁自身的测试（test:nav）',
    args: ['--test', 'scripts/validate-nav.test.mjs'],
    stdio: 'inherit',
  },
]

/**
 * 跑完整套前置步骤，任一步非 0 即抛错（Playwright 据此中止整轮 e2e）。
 *
 * @param {{run?: (cmd: string, args: string[], opts: object) => {status: number | null},
 *          execPath?: string}} [deps] 注入执行器与 node 路径，便于单测「失败必须响」
 */
export function runNavGate({ run = spawnSync, execPath = process.execPath } = {}) {
  for (const step of NAV_GATE_STEPS) {
    const result = run(execPath, step.args, { cwd: ROOT, stdio: step.stdio })
    if (result.status !== 0) {
      throw new Error(
        `[e2e 前置门禁] ${step.name} 未通过（exit ${result.status}）。` +
          ' 上面已打印具体是哪条引导/菜单引用不一致，修好后再跑 e2e；' +
          ' 单独校验用 npm run validate:nav',
      )
    }
  }
}

export default async function globalSetup() {
  runNavGate()
}
