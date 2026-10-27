/**
 * T03319（C91）：整本上传「跳过已存在章节」的说法必须与后端一致。
 *
 * 缺陷形状是「界面声称未发生的事」：整本改为单事务 + 断点续传后，重复上传整本会返回
 * `count=0, skipped=N`。若前端沿用 `ElMessage.success('上传成功')` + 「新增 0 条」，
 * 运营看到的是一句什么都没发生的成功提示，无从判断是「书早就在库里」还是「解析失败」。
 *
 * 门禁两层：
 * 1) 契约双向核对：页面读 `res.skipped`，后端两个批量入口就必须真的回 `skipped`；
 * 2) 反退回断言：只有 `count>0` 才许说「上传成功 / COS 导入成功」，全跳过时走 warning。
 * 真实渲染由 tests/course-materials-upload-skip.spec.js（真实 Chrome）负责。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')

const PAGE = read('../../src/views/channel/CourseMaterials.vue')
const BACKEND = read('../../../../backend/app/routers/admin/materials.py')

function handlerBody(source, fnName) {
  const start = source.indexOf(`async function ${fnName}()`)
  assert.ok(start >= 0, `未找到 ${fnName}()——用例已失效，请同步更新`)
  const end = source.indexOf('\nasync function ', start + 1)
  return source.slice(start, end < 0 ? undefined : end)
}

test('后端两个批量入口都回报 skipped / skipped_titles', () => {
  const occurrences = BACKEND.match(/"skipped": len\(skipped\)/g) || []
  assert.equal(occurrences.length, 2, `upload 与 import-cos 都要回报 skipped，实际 ${occurrences.length} 处`)
  assert.equal((BACKEND.match(/"skipped_titles": skipped\[:SKIPPED_PREVIEW_LIMIT\]/g) || []).length, 2)
})

test('文档上传：读取 skipped，且只有新增才说「上传成功」', () => {
  const body = handlerBody(PAGE, 'doUpload')
  assert.match(body, /const skipped = res\.skipped \|\| 0/, '没有读取后端回报的 skipped')
  assert.match(body, /if \(res\.count\) \{\s*ElMessage\.success\('上传成功'\)/, '全跳过时也会说「上传成功」')
  assert.match(body, /else if \(skipped\) \{\s*ElMessage\.warning\(`整本已存在/, '全跳过缺少如实提示')
  assert.match(body, /跳过 \$\{skipped\} 章/, '提示里没有说明跳过了几章')
})

test('COS 导入：读取 skipped，且只有新增才说「COS 导入成功」', () => {
  const body = handlerBody(PAGE, 'doCos')
  assert.match(body, /const skipped = res\.skipped \|\| 0/, '没有读取后端回报的 skipped')
  assert.match(body, /if \(res\.count\) \{\s*ElMessage\.success\('COS 导入成功'\)/, '全跳过时也会说「导入成功」')
  assert.match(body, /else if \(skipped\) \{\s*ElMessage\.warning\(`整本已存在/, '全跳过缺少如实提示')
  assert.match(body, /跳过 \$\{skipped\} 章/, '提示里没有说明跳过了几章')
})

test('反退回：不得出现无条件「上传成功」', () => {
  const body = handlerBody(PAGE, 'doUpload')
  const unconditional = /uploadResult\.value = `解析完成，新增 \$\{res\.count\} 条素材`\s*\n\s*ElMessage\.success/
  assert.ok(!unconditional.test(body), '无条件成功提示又回来了（重复上传整本会假报成功）')
})
