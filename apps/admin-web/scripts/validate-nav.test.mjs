/**
 * 校验脚本自身的测试（node --test scripts/）
 *
 * 重点是「它能不能失败」：一个永远返回通过的门禁比没有门禁更糟——
 * 它会让后面的人以为这项检查已经做过了。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { collectFacts, checkFacts, checkEnums, collectEnumDuplicates } from './validate-nav.mjs'

/** 最小可用事实集：只写用到字段，其余留空 */
function facts(over = {}) {
  return {
    routes: [
      { path: '/', meta: { requiresAuth: true } },
      { path: '/review', meta: { title: '内容审核', icon: 'Document', group: '内容运营' } },
      // 例外登记表（BARE_CLASS_EXCEPTIONS）里的路由，测试用得到，否则先撞上「路由不存在」
      { path: '/materials', meta: { title: '素材录入', icon: 'Files', group: '内容运营' } },
      { path: '/m/home', meta: { title: '首页' } },
    ],
    guideSteps: { '/review': [{ s: ['[data-guide="review-table"]'], t: '审核', d: '' }] },
    groups: [{ name: '内容运营', icon: 'Document' }],
    ariaLabels: new Set(['新增频道']),
    dataGuides: new Set(['review-table']),
    helpIds: ['review'],
    menuRefs: ['内容审核'],
    mobileTargets: [{ from: 'layouts/MobileLayout.vue', to: '/m/home' }],
    aboutHrefs: [],
    commentGroups: ['内容运营'],
    ...over,
  }
}

test('真实仓库通过校验（且抽取到的是真数据，不是空集合）', async () => {
  const f = await collectFacts()
  assert.ok(f.routes.length > 30, `路由数异常：${f.routes.length}`)
  assert.ok(f.ariaLabels.size > 50, `aria-label 数异常：${f.ariaLabels.size}`)
  assert.ok(f.menuRefs.length > 5, '帮助文档菜单引用没抽到，检查项等于没跑')
  assert.ok(f.routes.some((r) => r.path === '/review'), '路由相对路径未正确展开')
  assert.ok(f.routes.some((r) => r.path === '/m/manage/users'), '移动端嵌套路径未正确展开')
  assert.deepEqual(checkFacts(f).errors, [])
})

test('真实仓库的开源清单与外链都是实况（T02503）', async () => {
  const f = await collectFacts()
  // 抽取本身要非空，否则「对账通过」只是因为什么都没对
  assert.ok(f.dependencyTable.length > 30, `开源清单条目异常：${f.dependencyTable.length}`)
  assert.ok(Object.keys(f.npmManifest).length >= 15, 'package.json 依赖没读到')
  assert.ok(f.pyManifest && f.pyManifest.size >= 20, 'requirements.txt 没读到，pip 侧对账等于没跑')
  // 占位外链必须为 0：视图里仍有合法的 example.com 示例值（placeholder、正文说明），
  // 因此这里断言的是「链接位置为 0」而不是「全文查不到 example.com」
  assert.deepEqual(f.placeholderLinks, [])
})

test('引导指向不存在的路由时报错', () => {
  const r = checkFacts(
    facts({ guideSteps: { '/nope': [{ s: ['[data-guide="review-table"]'], t: 'x', d: '' }] } }),
  )
  assert.match(r.errors.join('\n'), /引导配置的路由不存在：GUIDE_STEPS\['\/nope'\]/)
})

test('引导选择器命中不存在的 aria-label 时报错（T02500 抓到的真实缺陷形态）', () => {
  const r = checkFacts(
    facts({ guideSteps: { '/review': [{ s: ['[aria-label="不存在的按钮"]'], t: '触发', d: '' }] } }),
  )
  assert.equal(r.errors.length, 1)
  assert.match(r.errors[0], /不存在的 aria-label/)
})

test('锚点契约：多选择器兜底链报错（T02502）', () => {
  const r = checkFacts(
    facts({ guideSteps: { '/review': [{ s: ['[data-guide="review-table"]', '.page-container'], t: '列表', d: '' }] } }),
  )
  assert.match(r.errors.join('\n'), /一步只允许一个选择器/)
})

test('锚点契约：视图里不存在的 data-guide 报错（T02502）', () => {
  const r = checkFacts(
    facts({ guideSteps: { '/review': [{ s: ['[data-guide="被改名删掉的锚点"]'], t: '列表', d: '' }] } }),
  )
  assert.match(r.errors.join('\n'), /不存在的锚点：\/review → \[data-guide="被改名删掉的锚点"\]/)
})

test('锚点契约：组合选择器与可能多实例的裸类报错（T02502）', () => {
  const r = checkFacts(
    facts({
      guideSteps: {
        '/review': [
          { s: ['.top-bar .el-button'], t: '工具栏', d: '' },
          { s: ['.el-table'], t: '表格', d: '' },
        ],
      },
    }),
  )
  const text = r.errors.join('\n')
  assert.match(text, /禁止位置兜底：\/review → \.top-bar \.el-button/)
  assert.match(text, /禁止未打显式锚点的裸类：\/review → \.el-table/)
})

test('锚点契约：只放行全页唯一的布局类，同页多个的类不放行（T02502）', () => {
  const pageLevel = checkFacts(
    facts({ guideSteps: { '/review': [{ s: ['.page-container'], t: '整页', d: '' }] } }),
  )
  assert.deepEqual(pageLevel.errors, [])
  // `.el-table` 在带弹窗表格的页面上会有两个实例，querySelector 取到的可能是弹窗那个
  const ambiguous = checkFacts(
    facts({ guideSteps: { '/ads/materials': [{ s: ['.el-table'], t: '列表', d: '' }] } }),
  )
  assert.match(ambiguous.errors.join('\n'), /禁止未打显式锚点的裸类：\/ads\/materials → \.el-table/)
})

test('真实仓库的锚点契约事实非空（检查项等于真跑了）', async () => {
  const f = await collectFacts()
  assert.ok(f.dataGuides.size > 40, `data-guide 锚点数异常：${f.dataGuides.size}`)
  const selectors = Object.values(f.guideSteps).flat().flatMap((s) => s.s)
  assert.equal(
    selectors.filter((s) => s.includes(' ')).length,
    0,
    '存在位置兜底选择器（含空格的组合器），会静默指错元素',
  )
})

test('帮助文档指向不存在的菜单时报错', () => {
  const r = checkFacts(facts({ menuRefs: ['不存在的菜单'] }))
  assert.match(r.errors.join('\n'), /帮助文档指向不存在的菜单：「不存在的菜单」/)
})

test('分组漂移（路由有组无配置 / 配置有组无菜单）双向报错', () => {
  const orphanGroup = checkFacts(
    facts({ routes: [{ path: '/review', meta: { title: '内容审核', icon: 'Document', group: '陌生分组' } }] }),
  )
  assert.match(orphanGroup.errors.join('\n'), /没有对应分组配置/)
  const emptyGroup = checkFacts(facts({ groups: [{ name: '空分组', icon: 'Coin' }] }))
  assert.match(emptyGroup.errors.join('\n'), /下没有任何可见菜单项/)
})

test('移动端手写入口与分组注释漂移同样报错', () => {
  const badTo = checkFacts(facts({ mobileTargets: [{ from: 'x.vue', to: '/m/nope' }] }))
  assert.match(badTo.errors.join('\n'), /移动端入口指向不存在的路由/)
  const staleComment = checkFacts(facts({ commentGroups: ['内容运营', '已删除分组'] }))
  assert.match(staleComment.errors.join('\n'), /列出不存在的分组/)
})

/** 依赖对账夹具：导航项全空，只留下对账需要的字段 */
function depFacts(over = {}) {
  return {
    routes: [],
    guideSteps: {},
    groups: [],
    ariaLabels: new Set(),
    dataGuides: new Set(),
    helpIds: [],
    menuRefs: [],
    mobileTargets: [],
    aboutHrefs: [],
    commentGroups: [],
    placeholderLinks: [],
    dependencyTable: [
      { name: 'vue', version: '^3.4.0' },
      { name: 'fastapi', version: '0.110.0' },
    ],
    npmManifest: { vue: '^3.4.0' },
    pyManifest: new Map([['fastapi', { name: 'fastapi', version: '0.110.0' }]]),
    ...over,
  }
}

test('依赖对账：两边一致时不报错', () => {
  assert.deepEqual(checkFacts(depFacts()).errors, [])
})

test('依赖对账：表里的幽灵依赖、漏声明、版本漂移三个方向都报错（T02503）', () => {
  const ghost = checkFacts(
    depFacts({ dependencyTable: [{ name: 'vue', version: '^3.4.0' }, { name: 'gone-lib', version: '1.0.0' }] }),
  )
  assert.match(ghost.errors.join('\n'), /列了 gone-lib（1\.0\.0）/)

  const unlisted = checkFacts(depFacts({ npmManifest: { vue: '^3.4.0', axios: '^1.6.0' } }))
  assert.match(unlisted.errors.join('\n'), /package\.json 依赖 axios（\^1\.6\.0）没有列入/)

  const drifted = checkFacts(
    depFacts({ dependencyTable: [{ name: 'vue', version: '^3.3.0' }, { name: 'fastapi', version: '0.110.0' }] }),
  )
  assert.match(drifted.errors.join('\n'), /vue 版本是 \^3\.3\.0，但 package\.json 里是 \^3\.4\.0/)

  const pyDrift = checkFacts(
    depFacts({ dependencyTable: [{ name: 'vue', version: '^3.4.0' }, { name: 'fastapi', version: '0.100.0' }] }),
  )
  assert.match(pyDrift.errors.join('\n'), /fastapi 版本是 0\.100\.0，但 backend\/requirements\.txt 里是 0\.110\.0/)
})

test('依赖对账：Python 包名大小写与连字符等价（PyMuPDF ↔ pymupdf）不误报', () => {
  const r = checkFacts(
    depFacts({
      dependencyTable: [{ name: 'vue', version: '^3.4.0' }, { name: 'PyMuPDF', version: '1.28.2' }],
      pyManifest: new Map([['pymupdf', { name: 'PyMuPDF', version: '1.28.2' }]]),
    }),
  )
  assert.deepEqual(r.errors, [])
})

test('依赖对账：后端清单读不到时只跳过，不谎报「依赖已移除」（前端单独构建场景）', () => {
  const r = checkFacts(
    depFacts({
      dependencyTable: [{ name: 'vue', version: '^3.4.0' }, { name: 'fastapi', version: '0.110.0' }],
      pyManifest: null,
    }),
  )
  assert.deepEqual(r.errors, [])
})

test('依赖对账：重复条目与解析不出条目都会报错，不会静默通过', () => {
  const dup = checkFacts(
    depFacts({
      dependencyTable: [
        { name: 'vue', version: '^3.4.0' },
        { name: 'vue', version: '^3.4.0' },
        { name: 'fastapi', version: '0.110.0' },
      ],
    }),
  )
  assert.match(dup.errors.join('\n'), /重复列出 vue/)

  const empty = checkFacts(depFacts({ dependencyTable: [] }))
  assert.match(empty.errors.join('\n'), /解析为空/)
})

test('占位外链：链接位置出现 example.com 即报错（ACC-UX-401）', () => {
  const r = checkFacts(
    depFacts({
      placeholderLinks: [{ from: 'views/about/About.vue', text: `href: 'https://example.com/terms'` }],
    }),
  )
  assert.match(r.errors.join('\n'), /占位外链残留在链接位置：views\/about\/About\.vue/)
})

test('占位外链抽取只认链接位置：placeholder 与正文示例不算（避免误报）', async () => {
  // collectPlaceholderLinks 的判据来自视图实况——真实仓库里 CosConfig / Tunnel /
  // Notification / Help 都有 example.com 的示例值，但都不在链接位置，故必须抽到 0 条。
  const f = await collectFacts()
  assert.equal(f.placeholderLinks.length, 0)
})

/** 枚举对账用的最小事实集（T02504）：默认给一份「字典与后端完全一致」的事实 */
function enumFacts(over = {}) {
  const {
    dictValues = ['queued', 'running', 'success', 'failed', 'cancelled'],
    backendValues = ['queued', 'running', 'success', 'failed', 'cancelled'],
    backendEnums = new Map([['WorkflowStatus', backendValues]]),
    dictionary = {
      dicts: new Map([['WORKFLOW_STATUS', dictValues]]),
      backendOf: new Map([['WORKFLOW_STATUS', 'WorkflowStatus']]),
    },
    dupes = [],
    phantoms = [],
  } = over
  return { enumDictionary: dictionary, backendEnums, enumDuplicates: { dupes, phantoms } }
}

test('枚举对账：字典与后端逐值一致时不报错', () => {
  assert.deepEqual(checkEnums(enumFacts()).errors, [])
})

test('枚举对账：字典缺值（漏英文原值）与多值（永不命中）两个方向都报错', () => {
  const missing = checkEnums(enumFacts({ dictValues: ['queued', 'running', 'success', 'failed'] }))
  assert.match(missing.errors.join('\n'), /缺少后端 WorkflowStatus 的值：cancelled/)
  assert.match(missing.errors.join('\n'), /漏出英文原值/)

  const extra = checkEnums(enumFacts({ dictValues: ['queued', 'finished'] }))
  assert.match(extra.errors.join('\n'), /列了后端 WorkflowStatus 没有的值：finished/)

  const renamed = checkEnums(
    enumFacts({
      dictionary: {
        dicts: new Map([['WORKFLOW_STATUS', ['queued']]]),
        backendOf: new Map([['WORKFLOW_STATUS', 'WorkflowStatusV2']]),
      },
    }),
  )
  assert.match(renamed.errors.join('\n'), /找不到该定义：枚举已改名/)
})

test('枚举对账：后端模型读不到时只跳过值集比对，重复映射照抓（前端单独构建）', () => {
  const r = checkEnums(
    enumFacts({
      backendEnums: null,
      dupes: [{ name: 'WORKFLOW_STATUS', where: 'views/x.vue:9', keys: ['queued', 'success'] }],
    }),
  )
  assert.equal(r.backendSkipped, true)
  assert.match(r.errors.join('\n'), /重复声明了 WORKFLOW_STATUS/)
})

test('枚举对账：没有字典文件时整项跳过，不谎报「已对上」', () => {
  const r = checkEnums({})
  assert.equal(r.skipped, true)
  assert.deepEqual(r.errors, [])
})

test('枚举对账：重复映射与幻影值经 checkFacts 冒出来（T02504）', () => {
  const r = checkFacts(
    facts(
      enumFacts({
        phantoms: [{ name: 'WORKFLOW_STATUS', where: 'views/mobile/ManageQueue.vue:40', keys: ['finished'] }],
      }),
    ),
  )
  assert.match(r.errors.join('\n'), /含 WORKFLOW_STATUS 里不存在的值：finished/)
  assert.match(r.errors.join('\n'), /永远走不到/)
})

/** 在临时目录里造一份 src 树，验证扫描器「能失败」也「不误报」 */
function enumFixtureTree(files) {
  const dir = mkdtempSync(join(tmpdir(), 'enum-gate-'))
  for (const [rel, content] of Object.entries(files)) {
    const p = join(dir, rel)
    mkdirSync(dirname(p), { recursive: true })
    writeFileSync(p, content, 'utf8')
  }
  return dir
}

const FIXTURE_DICT = new Map([['WORKFLOW_STATUS', ['queued', 'running', 'success', 'failed', 'cancelled']]])

test('重复映射扫描：抓到页面手抄的第二份，也抓到后端不存在的幻影值', () => {
  const dir = enumFixtureTree({
    'views/Dupe.vue':
      '<template><div>{ queued: \'插值不算\' }</div></template>\n<script setup>\n' +
      "const STATUS_LABEL = { queued: '排队中', running: '执行中', success: '成功', failed: '失败', cancelled: '已取消' }\n" +
      '</script>\n',
    'views/Phantom.vue':
      '<script setup>\nconst M = {\n' +
      "  queued: '排队中', running: '运行中', success: '已完成', finished: '已完成',\n}\n</script>\n",
    // 「值 → 对象」的写法（字典自己的形状）同样算重复声明——T02504 里 WorkflowDetail
    // 就是这样抄了第二份素材状态，与素材库页面上「待消费/已选题」漂成「待处理/已选中」
    'views/ObjectMap.vue':
      '<script setup>\nconst MAP = {\n' +
      "  queued: { label: '排队中', el: 'wait' },\n  success: { label: '成功', el: 'finish' },\n}\n</script>\n",
    'constants/enums.js': "export const WORKFLOW_STATUS = { queued: { label: '排队中' } }\n",
  })
  const r = collectEnumDuplicates(FIXTURE_DICT, dir)
  assert.equal(r.dupes.length, 2, `重复声明没抓到：${JSON.stringify(r)}`)
  assert.equal(r.dupes[0].name, 'WORKFLOW_STATUS')
  // 行号要落在 .vue 的物理行（<script> 之前的行数已补回），否则报错没法跳
  assert.match(r.dupes[0].where, /^views[/\\]Dupe\.vue:3$/)
  assert.match(r.dupes[1].where, /^views[/\\]ObjectMap\.vue:2$/)
  assert.deepEqual(r.dupes[1].keys, ['queued', 'success'])
  assert.equal(r.phantoms.length, 1, `幻影值没抓到：${JSON.stringify(r)}`)
  assert.deepEqual(r.phantoms[0].keys, ['finished'])
  rmSync(dir, { recursive: true, force: true })
})

test('重复映射扫描不误报：计数对象、非枚举文案表、字典自身被排除（真映射照抓）', () => {
  const dir = enumFixtureTree({
    'views/Counter.vue':
      '<script setup>\n' +
      'const summary = reactive({ success: 3, failed: 1, cancelled: 0 })\n' +
      "const LOCALE = { zh: '中文', en: 'English' }\n" +
      "const ok = computed(() => ({ success: '成功', failed: '失败', cancelled: '已取消', queued: '排队中', running: '执行中' }))\n" +
      '</script>\n',
    'constants/enums.js':
      '<script setup>\nconst WORKFLOW_STATUS = { queued: { label: \'排队中\' }, success: { label: \'成功\' } }\n</script>\n',
  })
  const r = collectEnumDuplicates(FIXTURE_DICT, dir)
  // summary 的值是数字 → 不是映射；LOCALE 的键与枚举无关 → 不算；
  // ok 是「全部键命中」的映射，确实属于要抓的重复声明，所以这里断言它被抓到、summary/LOCALE 没被抓到
  assert.equal(r.dupes.length, 1)
  assert.match(r.dupes[0].where, /Counter\.vue:4$/)
  assert.equal(r.phantoms.length, 0)
  rmSync(dir, { recursive: true, force: true })
})

test('真实仓库的枚举字典与后端逐值对上（T02504）', async () => {
  const f = await collectFacts()
  // 抽取本身要非空，否则「对账通过」只是因为什么都没对
  assert.ok(f.enumDictionary, 'src/constants/enums.js 没解析出来')
  assert.ok(f.enumDictionary.dicts.size >= 10, `枚举字典份数异常：${f.enumDictionary.dicts.size}`)
  assert.ok(f.backendEnums?.get('WorkflowStatus')?.includes('queued'), '后端 WorkflowStatus 没读到')
  assert.ok(f.enumDictionary.dicts.get('WORKFLOW_STATUS').includes('cancelled'), '前端字典没解析出成员')
  // 迁移完成后，视图里不该再有任何一份同族映射（这一条是「迁移真做了」的证据）
  assert.deepEqual(f.enumDuplicates, { dupes: [], phantoms: [] })
  assert.deepEqual(checkEnums(f).errors, [])
})

