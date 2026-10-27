/**
 * T03321：审计 reason 前端接线。
 *
 * 后端已经把 reason 收进 detail，但前端不填就等于永远空串——
 * 这里守住三件事：确认框里有原因输入、原因真的随请求发出去、预览请求不乱带。
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const read = (p) => readFileSync(resolve(ROOT, p), 'utf8')

test('dangerConfirmWithReason 沿用统一的正文规范并返回原因', () => {
  const src = read('src/utils/dangerConfirm.js')
  assert.match(src, /export async function dangerConfirmWithReason/)
  assert.match(src, /buildDangerText\(rest\)/, '必须复用 buildDangerText，否则文案规范会分叉')
  assert.match(src, /return \{ confirmed: true, reason: state\.reason\.trim\(\) \}/)
  assert.match(src, /return \{ confirmed: false, reason: '' \}/)
  assert.match(src, /beforeClose/, '逐字确认词要在提交前校验')
  assert.match(src, /maxlength: 200/, '原因长度要与后端 Query(max_length=200) 对齐')
})

test('素材删除三入口都把原因带到请求里', () => {
  const vue = read('src/views/channel/MaterialLibrary.vue')
  assert.match(vue, /dangerConfirmWithReason/)
  assert.match(vue, /deleteMaterial\(row\.id, reason\)/)
  assert.match(vue, /deleteMaterialsBySource\(row\.source, filters\.channel_id \|\| undefined, reason\)/)
  assert.match(vue, /batchDeleteMaterials\(\{ ids, reason \}\)/)
  assert.match(vue, /batchDeleteMaterials\(\{\s*sources,/)

  const api = read('src/api/materials.js')
  assert.match(api, /export const deleteMaterial = \(id, reason = ''\)/)
  assert.match(api, /export const deleteMaterialsBySource = \(source, channelId, reason = ''\)/)
})

test('系统清理只在真正执行时带原因', () => {
  const vue = read('src/views/maintenance/Maintenance.vue')
  assert.match(vue, /dangerConfirmWithReason/)
  assert.match(vue, /cleanupReason = reason/)
  assert.match(vue, /if \(cleanupReason\) payload\.reason = cleanupReason/)
})
