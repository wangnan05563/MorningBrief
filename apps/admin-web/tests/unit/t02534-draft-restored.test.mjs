/**
 * T02534 · F2（配置页本地草稿恢复）· 裁决「草稿优先 + 明示」的门禁
 *
 * 两段：
 * 1) 行为段——直接跑 useDraft：apply 要返回「与服务器值不同的项数」，
 *    discard 要把表单还原成「加载时的服务器值」并清掉 localStorage，
 *    且还原动作本身不能再被 watch 反写成一份新草稿（这正是静默合并的复发形态）。
 * 2) 接线段——五个配置页都必须挂 DraftRestoredBanner，并且把「丢弃」接到
 *    当前页面自己的表单对象上；保存成功后横幅必须收掉。
 *
 * 真实渲染（横幅出现/保留/丢弃四段）由 tests/draft-restored-notice.spec.js 在浏览器里跑。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref } from 'vue'
import { useDraft, countChangedPaths } from '../../src/composables/useDraft.js'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const SRC = '../../src/views/'

class MemoryStorage {
  constructor() {
    this.map = new Map()
  }
  getItem(key) {
    return this.map.has(key) ? this.map.get(key) : null
  }
  setItem(key, value) {
    this.map.set(key, String(value))
  }
  removeItem(key) {
    this.map.delete(key)
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function freshStorage() {
  const storage = new MemoryStorage()
  globalThis.localStorage = storage
  return storage
}

test('F2：countChangedPaths 只数叶子差异，数组整体算一项', () => {
  assert.equal(countChangedPaths({ a: 1, b: { c: 2 } }, { a: 1, b: { c: 2 } }), 0)
  assert.equal(countChangedPaths({ a: 1, b: { c: 2 } }, { a: 1, b: { c: 3 } }), 1)
  assert.equal(countChangedPaths({ a: 1, b: { c: 2, d: 4 } }, { a: 9, b: { c: 3, d: 4 } }), 2)
  // 数组按整体比较：只要内容不同就算 1 项，不按元素逐个数
  assert.equal(countChangedPaths({ list: [1, 2, 3] }, { list: [1, 9, 3] }), 1)
  // 合并目标缺字段时也算差异（草稿里多出来的键被 deepMerge 丢弃前先被数到）
  assert.equal(countChangedPaths({ a: 1 }, { a: 1, b: 2 }), 1)
})

test('F2：apply 报告差异项数，discard 还原服务器值并清草稿', async () => {
  const storage = freshStorage()
  storage.setItem('mb_draft_cfg', JSON.stringify({ timeout_sec: 45 }))

  const form = ref({ timeout_sec: 30, model: 'gpt-4o' })
  const draft = useDraft('cfg')
  const applied = draft.apply(form)

  assert.equal(applied.changed, 1, 'apply 必须返回与服务器值不同的项数')
  assert.equal(form.value.timeout_sec, 45, '草稿优先：恢复后表单是草稿值')
  assert.equal(draft.hasDraft.value, true)
  assert.equal(draft.changedCount.value, 1)

  const enable = draft.track(form)
  enable()

  const restored = await draft.discard(form)
  assert.equal(restored, 1, 'discard 返回被还原的项数')
  assert.equal(form.value.timeout_sec, 30, '丢弃后表单必须是加载时的服务器值')
  assert.equal(form.value.model, 'gpt-4o')
  assert.equal(storage.getItem('mb_draft_cfg'), null, '丢弃必须清掉本机草稿')
  assert.equal(draft.hasDraft.value, false)
  assert.equal(draft.changedCount.value, 0)

  // 还原动作会改动表单，若没暂停持久化，400ms 后又会把服务器值存成新草稿
  await sleep(600)
  assert.equal(storage.getItem('mb_draft_cfg'), null, '丢弃后的还原不得被反写成新草稿')
})

test('F2：保留草稿后用户继续编辑仍会持久化，保存成功才清空', async () => {
  const storage = freshStorage()
  storage.setItem('mb_draft_keep', JSON.stringify({ a: 2 }))

  const form = ref({ a: 1 })
  const draft = useDraft('keep')
  draft.apply(form)
  const enable = draft.track(form)
  enable()

  form.value.a = 5
  await sleep(600)
  assert.equal(storage.getItem('mb_draft_keep'), JSON.stringify({ a: 5 }), '保留即继续用草稿')

  draft.commit()
  assert.equal(storage.getItem('mb_draft_keep'), null)
  assert.equal(draft.hasDraft.value, false)
})

test('F2：无草稿时 apply 返回 null，横幅计数保持 0', () => {
  freshStorage()
  const form = ref({ a: 1 })
  const draft = useDraft('empty')
  assert.equal(draft.apply(form), null)
  assert.equal(draft.changedCount.value, 0)
  assert.equal(draft.hasDraft.value, false)
})

const PAGES = [
  {
    name: 'AI 服务配置',
    file: `${SRC}ai/AIConfig.vue`,
    applyDecl: 'const llmRestored = applyDraft(llmForm)',
    noticeDecl: '(llmRestored?.changed ?? 0) + (ttsRestored?.changed ?? 0)',
    discardCall: 'discardLlMDraft(llmForm)',
  },
  {
    name: '云端配置',
    file: `${SRC}cos/CosConfig.vue`,
    applyDecl: 'const restored = applyDraft(form)',
    discardCall: 'discardDraft(form)',
  },
  {
    name: '通知管理',
    file: `${SRC}notification/NotificationConfig.vue`,
    applyDecl: 'const restored = applyDraft(configForm)',
    discardCall: 'discardDraft(configForm)',
  },
  {
    name: '自动审批配置',
    file: `${SRC}system/AutoReviewConfig.vue`,
    applyDecl: 'const restored = applyDraft(form)',
    discardCall: 'discardDraft(form)',
  },
  {
    name: '内网穿透',
    file: `${SRC}tunnel/Tunnel.vue`,
    applyDecl: 'const restored = applyDraft(form)',
    discardCall: 'discardDraft(form)',
  },
]

for (const page of PAGES) {
  test(`F2 接线：${page.name} 恢复即明示，丢弃接自己的表单`, () => {
    const src = read(page.file)

    assert.match(src, /import DraftRestoredBanner from '\.\.\/\.\.\/components\/DraftRestoredBanner\.vue'/)
    assert.match(src, /<DraftRestoredBanner[\s\S]*?:visible="draftNotice > 0"[\s\S]*?@keep="keepLocalDraft"[\s\S]*?@discard="discardLocalDraft"/)
    assert.match(src, /const draftNotice = ref\(0\)/)
    // 恢复结果必须被接住并写进横幅计数：只 apply 不报告＝静默合并复发
    assert.ok(src.includes(page.applyDecl), `恢复结果必须接住：${page.applyDecl}`)
    assert.ok(
      src.includes(page.noticeDecl || 'draftNotice.value = restored?.changed ?? 0'),
      '恢复结果必须写进横幅计数',
    )
    // 丢弃必须接当前页面自己的表单对象：接错对象=清掉别人的草稿、当前表单仍是草稿值
    const discardFn = src.slice(src.indexOf('async function discardLocalDraft'))
    const discardBody = discardFn.slice(0, discardFn.indexOf('\n}') + 2)
    assert.ok(
      discardBody.includes(page.discardCall),
      `丢弃必须调用 ${page.discardCall}（当前实现：${discardBody.trim().split('\n')[0]}）`,
    )
    // 保存 / 重置成功后横幅要收掉，不能留着一条「已恢复草稿」指向已提交的表单
    assert.match(
      src,
      /commitDraft\(\)[\s\S]{0,120}?draftNotice\.value = 0/,
      '保存成功必须收掉横幅：已提交的表单不该还挂着「已恢复草稿」',
    )

    const banner = src.indexOf('<DraftRestoredBanner')
    const err = src.indexOf('<ConfigLoadError')
    assert.ok(banner > 0 && err > banner, '横幅必须排在加载失败提示之前（同一处顶部区域）')
  })
}

test('F2 接线：AI 页三段草稿共用一条横幅，计数是三项之和', () => {
  const src = read(`${SRC}ai/AIConfig.vue`)
  assert.match(src, /llmRestored\?\.changed \?\? 0\)\s*\+\s*\(ttsRestored\?\.changed \?\? 0\)\s*\+\s*\(imageRestored\?\.changed \?\? 0\)/)
  assert.match(src, /discardLlMDraft\(llmForm\)[\s\S]{0,160}?draftTts\.discard\(ttsForm\)[\s\S]{0,160}?draftImage\.discard\(imageForm\)/)
})

test('F2 横幅：文案点名差异项数，两个出口都在，且不可随手关掉', () => {
  const src = read('../../src/components/DraftRestoredBanner.vue')
  assert.match(src, /已恢复本地未保存草稿（\{\{ count \}\} 项与服务器值不同）/)
  assert.match(src, /保留草稿/)
  assert.match(src, /丢弃草稿，载入服务器值/)
  assert.match(src, /:closable="false"/)
  assert.match(src, /@click="emit\('keep'\)"/)
  assert.match(src, /@click="emit\('discard'\)"/)
})
