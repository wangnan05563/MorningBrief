/**
 * M16：清空字段这件事，前后端两本账必须一致
 *
 * 缺陷长这样：输入框是 `clearable`，清空后交上来的是空串；后端 `update_row` 又把
 * 「空串」当成「没填」直接丢掉，于是 SET 子句少一列、接口返回成功，库里还是旧值。
 * 修好之后两端各剩一半责任，任何一端改回去都会把这个「改了没生效但说成功」找回来：
 * - 前端：脏字段提交里，被清空的列要带着空串出发（不能自己也丢一轮）；
 * - 后端：出现在 payload 里的键就是要写的键，只有「列不存在/是主键」才丢。
 *
 * 真正的行为断言在 backend/tests/test_m16_clear_field_submission.py（直接看库里的值），
 * 这里守的是两端别再各说一套。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/db-admin-clear-field.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const VIEW = readFileSync(
  new URL('../../src/views/maintenance/DatabaseAdmin.vue', import.meta.url),
  'utf8',
)
const SERVICE = readFileSync(
  new URL('../../../../backend/app/services/db_admin_service.py', import.meta.url),
  'utf8',
)

function slice(src, startMarker, endMarker) {
  const at = src.indexOf(startMarker)
  assert.notEqual(at, -1, `源码里找不到 ${startMarker}`)
  const rest = src.slice(at)
  const end = endMarker ? rest.indexOf(endMarker) : -1
  return end > 0 ? rest.slice(0, end) : rest
}

const dirty = slice(VIEW, 'function buildDirtyValues(', '\nasync function')
const updateRow = slice(SERVICE, 'async def update_row(', '\n    async def delete_row')

describe('M16 清空字段的跨端契约', () => {
  it('前端脏字段提交：只按「未变更/主键/敏感列/脱敏哨兵」跳过，不按值是否为空跳过', () => {
    assert.match(dirty, /skip\.has\(name\)\) continue/, '主键与敏感列的跳过逻辑不见了')
    assert.match(dirty, /MASK_SENTINEL_RE\.test/, '脱敏哨兵不再被拦，等于把 *** 写回凭据列')
    assert.doesNotMatch(
      dirty,
      /if\s*\(\s*!value\s*\)\s*continue|value\s*!==\s*''\s*\)?\s*continue|if\s*\(\s*value\s*===\s*''\s*\)\s*continue/,
      '前端自己把空串丢掉，清空就又做不到了',
    )
    assert.match(
      dirty,
      /String\(originalForm\.value\[name\] \?\? ''\) === String\(value \?\? ''\)/,
      '未变更判据不见了：整行回传会把没动过的列一起提交',
    )
  })

  it('后端 update_row 不再按值过滤，只按列有效性过滤', () => {
    assert.doesNotMatch(
      updateRow,
      /v is not None and v !==? ""|v !==? ""|if v is not None and/,
      '空串又被当成「没填」丢掉了，M16 复发',
    )
    assert.match(updateRow, /\{k: v for k, v in values\.items\(\) if k in valid_cols\}/, '列有效性过滤是唯一的丢键理由')
  })

  it('后端仍然拒绝「一个有效列都没有」的请求，而不是静默成功', () => {
    assert.match(updateRow, /raise ParamError\("无有效更新字段"\)/, '放开空串后这条兜底不能一起消失')
  })

  it('前端「没有需要保存的修改」只在确实没有脏列时提示', () => {
    const submit = slice(VIEW, 'async function submitForm(', '\nfunction ')
    assert.match(submit, /Object\.keys\(values\)\.length/, '空提交要先问用户，再发请求')
    assert.match(submit, /await updateRow\(selectedTable\.value, editingPkValue\.value, values\)/, '编辑走脏字段，不许整行回传')
  })

  it('输入框可清空这件事仍然是用户能做到的动作', () => {
    assert.match(VIEW, /clearable/, '去掉 clearable 等于用「不给清空」来掩盖「清空不生效」')
  })
})

describe('M16 在 PRD 里可追溯', () => {
  const PRD = readFileSync(
    new URL('../../../../docs/需求规格说明书-UX优化.md', import.meta.url),
    'utf8',
  )
  const fr = slice(PRD, '| FR-UX-101 |', '\n')

  it('FR-UX-101 的覆盖条目补上了 M16', () => {
    assert.match(fr, /M14, M16, M46, F3/, 'M16 只出现在 §10.1 的里程碑计数里，没有任何 FR 承接——那等于没人负责')
    assert.match(fr, /空串\/None|不得再把空串/, 'FR 正文没写清空的语义，验收时无从对照')
  })

  it('ACC-UX-101 有对应的验收条', () => {
    const acc = slice(PRD, '**验收（ACC-UX-101）**', '\n\n')
    assert.match(acc, /6\. 清空一个可空文本列/, '没有第 6 条，M16 就没有验收口径')
    assert.match(acc, /不得返回「成功而库里没动」/, '第 6 条要否掉的就是这个假成功形态')
  })

  it('原验收第 1 条的 remark 列不存在，已按真实表结构订正', () => {
    const acc = slice(PRD, '**验收（ACC-UX-101）**', '\n\n')
    assert.match(acc, /只改 `nickname` 保存/, '验收写的是表里没有的列，执行的人只能自己猜一个')
    assert.match(acc, /admin_user` 无该列/, '没留下订正痕迹，下次又会照抄 remark')
  })
})
