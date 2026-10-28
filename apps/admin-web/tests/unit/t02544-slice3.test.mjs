/**
 * T02544 切片 3：功能断链 3 条（C106 / C24 / C67）
 *
 * 每条都按评审报告 §4.3 的「修订后修法」钉：
 * - C106：加入待讲书单后必须给出可点的素材去向（后端一直返回 material_id，
 *   前端只弹 toast，用户拿不到「去哪儿补齐书稿」这条线索）；
 * - C24：编辑态草稿必须在打开编辑时恢复，且恢复要可见、可放弃；
 *   原来那段恢复写在 openCreate 里，form.id 恒为 null，永远不会命中；
 * - C67：讲书稿模式对任意频道类型都生效，但改写模板只有 audiobook 注入书籍解读约束。
 *   非有声读物开启前二次确认，取消要回滚开关；后端状态必须下发 channel_type。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf-8')
const SRC = '../../src/'

const bookFinder = read(`${SRC}views/ebooks/BookFinder.vue`)
const channelMgmt = read(`${SRC}views/channel/ChannelManagement.vue`)
const bookPoolPanel = read(`${SRC}views/channel/BookPoolPanel.vue`)
const bookPoolService = repoFile('backend/app/services/book_pool_service.py')

function sliceBetween(text, startMark, endMark) {
  const start = text.indexOf(startMark)
  assert.ok(start >= 0, `缺少定位标记：${startMark}`)
  const end = text.indexOf(endMark, start + startMark.length)
  assert.ok(end > start, `缺少结束标记：${endMark}`)
  return text.slice(start, end)
}

test('C106：加入书单后把 material_id 落成可点击的素材库去向', () => {
  const onAdd = sliceBetween(bookFinder, 'async function onAddToBookList(row)', 'function applyResult(data)')
  // 断言写在取值上，不是断言注释里出现过 material_id（否则删掉取值也照样绿）
  assert.match(onAdd, /materialId: data\?\.material_id/, '必须消费接口返回的 material_id')
  assert.match(onAdd, /lastAdded\.value = \{/, '必须把上一次结果存下来才谈得上「去向」')

  // 链接要到素材库页并按 materialId 精确定位（MaterialLibrary 的深链键）
  assert.match(bookFinder, /path: '\/channels\/material-library', query: \{ materialId: lastAdded\.materialId \}/)
  // 结果表一换，旧去向失效——否则用户会以为它属于这次检索
  const applyResult = sliceBetween(bookFinder, 'function applyResult(data)', '/**')
  assert.match(applyResult, /lastAdded\.value = null/)
})

test('C24：编辑态草稿按行 id 恢复，且恢复行为可见可放弃', () => {
  // openCreate 里那段死代码必须消失：resetForm 之后 form.id 恒为 null
  const openCreate = sliceBetween(channelMgmt, 'function openCreate()', '// ===== T00730')
  assert.doesNotMatch(openCreate, /mb_channel_draft/, '新增弹窗不可能命中间草稿，别再留着假逻辑')

  // openEdit 里按 row.id 恢复，并且只套用确有差异的字段
  const openEdit = sliceBetween(channelMgmt, 'function openEdit(row)', 'async function handleSubmit()')
  assert.match(openEdit, /draft\.id === row\.id/)
  assert.match(openEdit, /JSON\.stringify\(draft\[k\]\) !== JSON\.stringify\(form\[k\]\)/)
  assert.match(openEdit, /draftRestored\.value = true/)

  // 恢复提示必须上屏，并提供放弃入口
  assert.match(channelMgmt, /v-if="draftRestored"/)
  assert.match(channelMgmt, /已恢复上次未保存的修改/)
  const discard = sliceBetween(channelMgmt, 'function discardDraft()', 'async function handleSubmit()')
  assert.match(discard, /localStorage\.removeItem\('mb_channel_draft'\)/)
  assert.match(discard, /openEdit\(row\)/, '放弃草稿要回到服务器值，而不是清空表单')
})

test('C67（前端）：非有声读物开启讲书稿模式需二次确认，取消回滚开关', () => {
  assert.match(bookPoolPanel, /import \{ CHANNEL_TYPE \}/, '确认文案要用频道类型字典的中文名')

  const onToggle = sliceBetween(bookPoolPanel, 'async function onToggleMode(val)', 'async function onScheduleChange()')
  assert.match(onToggle, /state\.channel_type !== 'audiobook'/, '只对非有声读物提示')
  assert.match(onToggle, /ElMessageBox\.confirm/)
  // 取消必须把已被 v-model 切换的开关拨回去
  assert.match(onToggle, /if \(!goOn\) \{\s*scriptMode\.value = false/)

  // 频道编辑弹窗是同一开关的第二个入口，同样要拦
  const editToggle = sliceBetween(channelMgmt, 'async function onToggleBookPool(val)', 'function openEdit(row)')
  assert.match(editToggle, /persistedType !== 'audiobook'/, '要用已保存的类型判断')
  assert.match(editToggle, /if \(!goOn\) \{\s*bookPoolOn\.value = false/)

  // 切频道先清上一条频道的类型，避免用 A 的类型判断 B 的开关
  const reset = sliceBetween(bookPoolPanel, 'function resetPoolView()', 'async function loadState(errors)')
  assert.match(reset, /channel_type: null/)
})

test('C67（后端）：状态接口下发 channel_type 供前端判断', () => {
  const getState = sliceBetween(bookPoolService, 'async def get_state', 'async def set_script_mode')
  assert.match(getState, /"channel_type": ch\.channel_type/)
})
