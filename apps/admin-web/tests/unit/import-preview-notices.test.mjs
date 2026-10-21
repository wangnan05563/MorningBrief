/**
 * INT-UX-02：导入预览的两本账必须对上
 *
 * 这一单修的是「预览说 1 行错误，导入实际 1 行成功」这类分叉：
 * - 多余的列（`not_a_column`）不该记成 error_rows——那一行照样会写进去；
 * - 缺 NOT NULL 无默认值的新行必须提前拦住——实测真实导入会 IntegrityError；
 * - `/import/preview` 老端点借道 `dry_run=true`，两个入口不能各长一套字段。
 *
 * 页面那三条是跨端约定（前端不渲染 notices，后端把警告挪出 errors 就等于把提示弄丢），
 * 后端那两条是接口口径。真正的行为断言在 backend/tests/test_int02_import_dry_run.py，
 * 这里守的是「两端别再各说一套」。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/import-preview-notices.test.mjs
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
const ROUTER = readFileSync(
  new URL('../../../../backend/app/routers/admin/db_admin.py', import.meta.url),
  'utf8',
)

describe('INT-UX-02 预览计数与真实导入同一本账', () => {
  it('多余的列是提示，不进 error_rows', () => {
    assert.match(SERVICE, /notices\.append\(\s*\{[\s\S]*?列不在表结构内，导入时将忽略/)
    assert.doesNotMatch(
      SERVICE,
      /errors\.append\(\s*\{\s*"row": i \+ 1, "error": f"列不在表结构内/,
      '多余的列一旦被记成错误行，预览的 error_rows 就又比实际多算了',
    )
  })

  it('缺必填列的新行在预览阶段就被拦下', () => {
    assert.match(SERVICE, /if not is_update:\s*[\s\S]*?缺少必填列（NOT NULL 且无默认值）/)
  })

  it('页面渲染 notices，警告不因挪出 error_rows 而消失', () => {
    assert.match(VIEW, /v-if="importPreview\.notices\?\.length"/)
    assert.match(VIEW, /importPreview\.notices\.slice\(0, 10\)/)
  })

  it('老预览端点借道 dry_run，不再自己算一套', () => {
    assert.match(ROUTER, /await import_rows\(\s*table,[\s\S]*?dry_run=True,\s*\)/)
    assert.match(ROUTER, /items\(\)\s*if k != "dry_run"/)
  })
})
