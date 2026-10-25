/**
 * T02610：ESLint 门禁的接线与牙齿
 *
 * 事故形态：`CosFiles.vue` 调了 `dangerConfirm(...)` 却没 import。Vue 模板/组合式 API
 * 这种「用了没导入」编译期不报错，运行时 ReferenceError 被全局 Promise 守卫吞掉，
 * 界面表现成「点了没反应」，直到 e2e 断言确认框存在才暴露。
 *
 * 一个「永远返回通过」的 lint 配置比没有更糟，所以这里锁四件事：
 * 1. 关键规则真的开着：`no-undef`（<script setup> 同样生效）与 `import/no-unresolved`；
 * 2. 它被接在日常会跑的命令上（`npm run build` 前置），不是只能手动想起来；
 * 3. README 里有它，否则这条强制点对新人不可见；
 * 4. **有牙齿**：用 ESLint 的 Node API 对一份虚拟 SFC 喂「未导入 util + 坏路径」，
 *    必须同时命中两条规则。用 lintText + 虚拟 filePath 而不是在 src/ 里写临时文件：
 *    node --test 是并行跑文件的，落在 src/ 的残片会被别的用例（字段对齐/导航门禁）看见。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'

const WEB = fileURLToPath(new URL('../..', import.meta.url))
const CONFIG_SRC = readFileSync(new URL('../../eslint.config.js', import.meta.url), 'utf8')
const PKG = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'))

const PROBE = `<script setup>
import Missing from './definitely-not-here'
const value = ref(0)
dangerConfirm({ title: 't', message: 'm' })
</script>
<template><div>{{ value }}</div></template>
`

describe('ESLint 接线', () => {
  it('开着 no-undef 与 import/no-unresolved，且 .vue 走 vue-eslint-parser', () => {
    assert.match(CONFIG_SRC, /'no-undef':\s*'error'/)
    assert.match(CONFIG_SRC, /'import\/no-unresolved':\s*\['error'/)
    assert.match(CONFIG_SRC, /parser:\s*vueParser/)
    assert.match(CONFIG_SRC, /defineProps:\s*'readonly'/, '<script setup> 宏不是运行时全局，不声明会满屏误报')
  })

  it('npm run lint 存在，且 build 先跑 lint（不能只靠手动想起来）', () => {
    assert.equal(PKG.scripts.lint, 'eslint "src/**/*.{vue,js}"')
    assert.match(PKG.scripts.build, /^npm run lint && /, '构建前置是 tickets 要求的强制点；CI 跑的就是 npm run build')
  })

  it('README 把 lint 写进开发命令（门禁不写文档等于没人知道有它）', () => {
    const readme = readFileSync(new URL('../../../../README.md', import.meta.url), 'utf8')
    const start = readme.indexOf('### 管理后台（Node.js）')
    assert.ok(start >= 0, 'README 的管理后台命令块标题不能改名为无人认领')
    const block = readme.slice(start, readme.indexOf('### 微信小程序', start))
    assert.ok(block.includes('npm run lint'), '管理后台命令块里要出现 `npm run lint`')
    assert.match(block, /npm run build[^\n]*lint/, 'build 那行要点明它前置了 lint')
  })
})

describe('ESLint 牙齿（Node API，不留临时文件）', () => {
  it('未导入的 util 与坏 import 路径必须同时报红', async () => {
    const eslint = new ESLint({ cwd: WEB })
    // 虚拟路径落在 src/ 下，让 flat config 的 files 匹配生效；文件本身不需要存在
    const [result] = await eslint.lintText(PROBE, {
      filePath: join(WEB, 'src', '__lint_gate_probe__.vue'),
    })
    const ruleIds = new Set(result.messages.map((m) => m.ruleId))
    assert.ok(ruleIds.has('no-undef'), `dangerConfirm 未定义必须被拦下，实际：${[...ruleIds].join(', ')}`)
    assert.ok(ruleIds.has('import/no-unresolved'), `坏路径必须被拦下，实际：${[...ruleIds].join(', ')}`)
    assert.ok(result.errorCount >= 2, '两条都是 error 级，不能降成 warning')
  })

  it('正常的 SFC 不误报（规则收窄后不应拦合法代码）', async () => {
    const eslint = new ESLint({ cwd: WEB })
    const [result] = await eslint.lintText(
      `<script setup>
import { ref } from 'vue'
const value = ref(0)
</script>
<template><div>{{ value }}</div></template>
`,
      { filePath: join(WEB, 'src', '__lint_gate_probe_ok__.vue') },
    )
    assert.deepEqual(result.messages, [])
  })
})