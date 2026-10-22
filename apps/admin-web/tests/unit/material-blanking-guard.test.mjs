/**
 * C56（M2 / FR-UX-202）：素材编辑不得把正文/标题/来源清成空白，也不得静默丢弃来源。
 *
 * 缺陷原文：「编辑弹窗不校验正文与来源：onSaveEdit 只挡空标题，正文/来源可被清空后
 * 照样提示『已保存』；而来源=书名正是讲书稿聚合键，清空即打断整本书聚合」。
 *
 * 实测中还量出**第二条**（原文没写）：`MaterialUpdateRequest` 压根没有 `source` 字段，
 * pydantic 默认 `extra='ignore'` 把前端提交的书名直接丢掉 → 提示成功但从未改动。
 * 同一种「成功而库里没动」的形状，与 M16 同类，所以这里也一起钉住。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

import { BLANK_CRITICAL_FIELDS, blankedFieldMessage, findBlankedCriticalField } from '../../src/utils/blankGuard.js'

// 与同目录其他门禁一致：相对本文件解析，不依赖 npm run 的工作目录
const read = (relUrl) => readFileSync(new URL(relUrl, import.meta.url), 'utf8')

const vueSrc = read('../../src/views/channel/MaterialLibrary.vue')
const pySrc = read('../../../../backend/app/routers/admin/materials.py')
const prd = read('../../../../docs/需求规格说明书-UX优化.md')

// 只取编辑这段函数体，避免整份文件里别的 trim() 误判成「已有校验」
function slice(src, startMarker, endMarker) {
  const s = src.indexOf(startMarker)
  assert.notEqual(s, -1, `找不到起点 ${startMarker}`)
  const e = src.indexOf(endMarker, s)
  assert.notEqual(e, -1, `找不到终点 ${endMarker}`)
  return src.slice(s, e)
}

const onSaveEdit = slice(vueSrc, 'async function onSaveEdit(', '\nfunction openCreate(')

test('C56 前端预检：原本非空、提交空白 → 点名被清的列', () => {
  const original = { content: '第一章正文', source: '被讨厌的勇气' }
  assert.equal(findBlankedCriticalField(original, { ...original, content: '' }).field, 'content')
  assert.equal(findBlankedCriticalField(original, { ...original, source: '' }).field, 'source')
  // 只剩空白字符同样是清空
  assert.equal(findBlankedCriticalField(original, { ...original, content: '   \n ' }).field, 'content')
})

test('C56 前端预检：只拦「转变」，不拦本就为空的行', () => {
  // 历史导入的空正文素材必须还能编辑——否则防护做成了新 bug
  assert.equal(findBlankedCriticalField({ content: '', source: '' }, { content: '', source: '' }), null)
  assert.equal(findBlankedCriticalField({ content: '正文', source: '书' }, { content: '新正文', source: '书' }), null)
  // 表单缺字段（未提交）不该被当成清空
  assert.equal(findBlankedCriticalField({ content: '正文', source: '书' }, { category: 'x' }), null)
})

test('C56 前端预检：拒绝文案说清后果，且字段名与后端一致', () => {
  const hit = findBlankedCriticalField({ content: '正文', source: '书' }, { content: '', source: '书' })
  assert.match(blankedFieldMessage(hit), /^正文不能清空：/, '提示要以被清的列名开头')
  assert.match(blankedFieldMessage(hit), /改写流程/, '提示要说明清空后果')
  const sourceHit = findBlankedCriticalField({ content: '正文', source: '书' }, { content: '正文', source: '' })
  assert.match(blankedFieldMessage(sourceHit), /聚合/, '来源的提示必须点出「讲书稿聚合键」')

  // 前后端不许各说各话：前端登记的每一列，后端护栏都得拦
  const reasons = slice(pySrc, '_BLANK_CRITICAL_REASONS = {', '\n\n\ndef _reject_blanking_critical_field')
  for (const col of Object.keys(BLANK_CRITICAL_FIELDS)) {
    assert.match(reasons, new RegExp(`"${col}"`), `前端拦 ${col} 但后端护栏没登记，刷新页面就能绕过`)
  }
})

test('C56 视图委托给 blankGuard，不再自带第二份判定', () => {
  // 判定留在 .vue 里时，变异探针「把 const 定义改名、引用不动」实测存活：
  // 字符串门禁认不出标识符断链，纯函数 + import 才咬得住。
  assert.match(vueSrc,
    /import \{ blankedFieldMessage, findBlankedCriticalField \} from '\.\.\/\.\.\/utils\/blankGuard'/,
    '视图没有引用共享预检模块')
  assert.doesNotMatch(vueSrc, /const BLANK_CRITICAL = \{/, '视图里又实现了一份，前后端口径会分叉')
  assert.match(onSaveEdit, /blankedCriticalField\(\)/, 'onSaveEdit 没走清空预检')
  assert.match(onSaveEdit, /blankedFieldMessage\(blanked\)/, '提示文案没有复用同一份说明')
})

test('C56 前端：区分「没填」与「删光了」——必须拿打开弹窗时的原值比', () => {
  assert.match(vueSrc, /const editOriginal/, '没有记录原值，无法区分清空与留空')
  assert.match(vueSrc, /editOriginal\.value = \{ content: editForm\.content, source: editForm\.source \}/,
    'openEdit 未把原值存进 editOriginal')
  assert.match(vueSrc, /findBlankedCriticalField\(editOriginal\.value, editForm\)/,
    '预检没有拿原值快照与当前表单比')
})

test('C56 后端：护栏在写库之前，且按 INT-UX-01 契约点名被拒字段', () => {
  const updateRow = slice(pySrc, '@router.put("/{material_id}")', '@router.delete("")')
  assert.match(updateRow, /_reject_blanking_critical_field\(m, updates\)/, 'PUT 没调护栏')
  assert.match(updateRow, /raise BizError\(\s*code=400/, '护栏不是业务拒绝')
  assert.match(updateRow, /data=\{"errors": errors\}/, '没按 data.errors[].field 契约回字段')
  // 只拦转变，不拦本就为空的行（否则历史数据无法编辑，把防护做成新 bug）
  const guard = slice(pySrc, 'def _reject_blanking_critical_field', '\n\n@router.delete("")')
  assert.match(guard, /if not str\(getattr\(m, field, ""\) or ""\)\.strip\(\):\s*\n\s*continue/,
    '护栏没有放行「原值本就为空」的行')
})

test('C56 后端：source 必须是真能写的字段，不能再静默丢弃', () => {
  const model = slice(pySrc, 'class MaterialUpdateRequest', '\ndef _material_to_dict')
  assert.match(model, /source: Optional\[str\] = None/, '请求模型仍没有 source（前端提交的书名会被 pydantic 丢掉）')
  assert.doesNotMatch(model, /model_config = ConfigDict\(extra="ignore"\)/, '不该再声明忽略多余字段')
})

test('C56：三列都在不许清空的登记里', () => {
  const reasons = slice(pySrc, '_BLANK_CRITICAL_REASONS = {', '\n\n\ndef _reject_blanking_critical_field')
  for (const col of ['title', 'content', 'source']) {
    assert.match(reasons, new RegExp(`"${col}"`), `${col} 未登记为不许清空`)
  }
})

test('C56 在 PRD 里可追溯（覆盖条目 + 验收项）', () => {
  assert.match(prd, /\| M2 \| 19 \|[^|]*C56/, '§10.1 的 M2 行仍包含 C56')
  assert.match(prd, /FR-UX-202 \|[^|]*\|[^|]*\|[^|]*C56/, 'FR-UX-202 的覆盖条目里没有 C56')
  assert.match(prd, /9\.[^\n]*清空[^\n]*素材|素材[^\n]*清空[^\n]*M2|（C56）/, 'ACC-UX-201 没有把 C56 变成可验收项')
})
