/**
 * T02544 切片 4：C117 —— 素材库「按当前筛选导出 CSV」+ 书单 CSV 导入
 *
 * 评审口径（T02336 §4.3）：C117 需修订——不照搬「素材库加导出」的原建议，
 * 只做两件事：
 * 1. 素材库按**当前筛选**导出 CSV（后端与列表共用同一套过滤，且不分页）；
 * 2. 书单支持 CSV 导入，但只匹配该频道素材库**已入库的 source**，未匹配的跳过。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf-8')
const SRC = '../../src/'

const materialsPy = repoFile('backend/app/routers/admin/materials.py')
const materialsApi = read(`${SRC}api/materials.js`)
const materialLib = read(`${SRC}views/channel/MaterialLibrary.vue`)
const bookPoolPanel = read(`${SRC}views/channel/BookPoolPanel.vue`)

function sliceBetween(text, startMark, endMark) {
  const start = text.indexOf(startMark)
  assert.ok(start >= 0, `缺少定位标记：${startMark}`)
  const end = text.indexOf(endMark, start + startMark.length)
  assert.ok(end > start, `缺少结束标记：${endMark}`)
  return text.slice(start, end)
}

test('C117 后端：导出端点复用列表过滤条件，且必须声明在 /{material_id} 之前', () => {
  const exportIdx = materialsPy.indexOf('async def export_materials_csv(')
  const idIdx = materialsPy.indexOf('async def get_material(')
  assert.ok(exportIdx > 0, '缺少导出端点')
  assert.ok(idIdx > exportIdx, '导出端点必须声明在 /{material_id} 之前，否则 /export 会被当作 ID')

  // 导出与列表共用同一个过滤函数（两处都调用，口径不会漂移）
  const listFn = sliceBetween(materialsPy, 'async def list_materials(', '@router.get("/export")')
  assert.match(listFn, /_filtered_material_query\(\s*select\(Material\)/)
  assert.match(listFn, /_filtered_material_query\(\s*select\(func\.count\(Material\.id\)\)/)
  const exportFn = sliceBetween(materialsPy, 'async def export_materials_csv(', 'async def aggregate_materials(')
  assert.match(exportFn, /_filtered_material_query\(/)
  // 独立确认筛选分支在共享函数里真实存在（而不是只在签名里收了参数）
  const filterFn = sliceBetween(materialsPy, 'def _filtered_material_query(', '@router.get("")')
  for (const cond of ['Material.channel_id', 'Material.status', 'Material.title.like', 'Material.source == ', 'Material.source_type', 'Material.media_type']) {
    assert.ok(filterFn.includes(cond), `共享过滤函数缺少条件：${cond}`)
  }
  assert.match(filterFn, /_ensure_source_type_supported\(source_type\)/)
  assert.match(filterFn, /_ensure_media_type_supported\(media_type\)/)
})

test('C117 后端：CSV 形态可被 Excel 直接打开（BOM + 表头 + 复数行）', () => {
  const exportFn = sliceBetween(materialsPy, 'async def export_materials_csv(', 'async def aggregate_materials(')
  assert.match(exportFn, /csv\.writer\(buf\)/)
  assert.match(exportFn, /"素材ID", "标题", "来源"/)
  assert.match(exportFn, /content="\\ufeff" \+ buf\.getvalue\(\)/)
  assert.match(exportFn, /media_type="text\/csv; charset=utf-8"/)
  assert.match(exportFn, /attachment; filename=/)
  // 不分页：不能出现 offset/limit，否则「导出全部」是假的
  assert.doesNotMatch(exportFn, /\.offset\(|\.limit\(/)
})

test('C117 前端：导出走 blob 且参数与当前视图筛选一致', () => {
  assert.match(materialsApi, /exportMaterialsCsv[\s\S]{0,160}responseType: 'blob'/)
  assert.match(materialLib, /exportMaterialsCsv,/)

  const fn = sliceBetween(materialLib, 'function currentExportParams()', 'function onReset()')
  assert.match(fn, /channel_id: filters\.channel_id/)
  assert.match(fn, /status: filters\.status/)
  assert.match(fn, /keyword: filters\.keyword/)
  assert.match(fn, /material_id: materialIdFilter\.value/)
  assert.match(fn, /source: sourceFilter\.value/)
  // 聚合视图不支持 source_type/media_type：不传，避免「筛了却没筛」
  assert.match(fn, /if \(viewMode\.value === 'list'\)/)
  assert.match(fn, /params\.source_type = filters\.source_type/)
  assert.match(fn, /params\.media_type = filters\.media_type/)

  const handler = sliceBetween(materialLib, 'async function onExportCsv()', 'function onReset()')
  assert.match(handler, /const blob = await exportMaterialsCsv\(currentExportParams\(\)\)/)
  assert.match(handler, /URL\.createObjectURL\(blob\)/)
  assert.match(handler, /a\.download = `素材库_/)
  assert.match(handler, /ElMessage\.success\('已按当前筛选导出 CSV/)
  // 按钮必须真的接上处理函数
  assert.match(materialLib, /data-guide="materials-export"[\s\S]{0,260}@click="onExportCsv"/)
})

test('C117 前端：书单 CSV 导入只取第一列、去重并交给后端按已入库 source 匹配', () => {
  assert.match(bookPoolPanel, /import \{[^}]*Upload[^}]*\} from '@element-plus\/icons-vue'/)
  assert.match(bookPoolPanel, /label="CSV 导入书单"/)
  assert.match(bookPoolPanel, /ref="csvInput" type="file" accept="\.csv,text\/csv"/)
  assert.match(bookPoolPanel, /@change="onImportCsv"/)

  const parser = sliceBetween(bookPoolPanel, 'function parseCsvFirstColumn(text)', 'async function onImportCsv')
  // 引号内逗号不能拆分列；换行/CRLF 视为行尾
  assert.match(parser, /if \(ch === '"'\)/)
  assert.match(parser, /src\[i \+ 1\] === '"'/)
  assert.match(parser, /ch === '\\n'/)
  assert.match(parser, /ch !== '\\r'/)

  const handler = sliceBetween(bookPoolPanel, 'async function onImportCsv(event)', 'async function onPreview()')
  assert.match(handler, /for \(const \[first\] of rows\)/)
  assert.match(handler, /\^\(书名\|title\|source\|book\)\$/)
  assert.match(handler, /seen\.has\(key\)/)
  assert.match(handler, /const res = await addBooksToPool\(props\.channelId, keys\)/)
  assert.match(handler, /res\?\.added/)
  assert.match(handler, /await loadAll\(\)/)
})
