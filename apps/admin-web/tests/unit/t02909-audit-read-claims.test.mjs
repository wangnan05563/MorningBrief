/**
 * T02909（B 端审计「查得到」）：前端读取审计的说法必须与后端一致。
 *
 * 缺陷形状是「写了一直有，读没有」：仓库里 30+ 处 `AuditLog(...)` 写入覆盖 15 类操作，
 * 但统一读口只放行 db_admin 与移动端停服两类，出事以后回答「刚才那次是谁做的」得手工捞表。
 * 本单的修法是：后端一个通用只读接口 + 类别登记表，前端一个挂在页面动作旁边的组件。
 *
 * 门禁三层：
 * 1) 契约双向核对：前端调 `/audit-logs`，后端就必须真的注册这个前缀与两个读点；
 * 2) 登记表核对：页面里写死的 category 必须是后端登记过（且有写入）的类别，防止读一个不存在的桶；
 * 3) 反「失败说成没数据」（T02496 口径）：读取失败渲染 ListLoadError，
 *    「该模块暂无审计记录」只能在 !error 分支出现。
 * 真实渲染由 tests/audit-trail.spec.js（真实 Chrome）负责。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')

const API = read('../../src/api/audit.js')
const COMPONENT = read('../../src/components/AuditTrail.vue')
const BACKEND_ROUTER = read('../../../../backend/app/routers/admin/audit.py')
const BACKEND_SERVICE = read('../../../../backend/app/services/audit_service.py')
const MAINTENANCE = read('../../src/views/maintenance/Maintenance.vue')
const DB_ADMIN = read('../../src/views/maintenance/DatabaseAdmin.vue')
const REVIEW = read('../../src/views/review/ReviewList.vue')
const MANAGE_USERS = read('../../src/views/mobile/ManageUsers.vue')
const ADMIN_USERS = read('../../src/views/system/AdminUsers.vue')

/** 后端 AUDIT_CATEGORIES 元组里的字面量，作为前端可请求类别的唯一来源 */
function registeredCategories() {
  const block = BACKEND_SERVICE.match(/AUDIT_CATEGORIES:\s*tuple\[str,\s*\.\.\.\]\s*=\s*\(([^)]*)\)/)
  assert.ok(block, '未在 audit_service.py 找到 AUDIT_CATEGORIES 登记表——用例已失效，请同步更新')
  return [...block[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1])
}

function mountedCategory(source) {
  const tag = source.match(/<AuditTrail\b[^>]*>/)
  assert.ok(tag, '页面里没有挂载 AuditTrail 组件')
  const category = tag[0].match(/category="([a-z_]+)"/)
  assert.ok(category, 'AuditTrail 挂载时没写 category')
  return { category: category[1], tag: tag[0] }
}

test('api/audit.js：走 /audit-logs 且两个读点都 silent', () => {
  assert.match(API, /api\.get\('\/audit-logs'/, '没有调用统一审计读口')
  assert.match(API, /api\.get\('\/audit-logs\/categories'/, '缺少类别清单读口')
  const calls = API.match(/api\.get\([^)]*\)/g) || []
  assert.equal(calls.length, 2, '审计读口应只有两处调用')
  for (const call of calls) {
    assert.match(call, /silent:\s*true/, '审计请求未 silent：失败时会抢一条全局 toast 打断操作')
  }
})

test('后端确实注册了这两个读点（契约双向）', () => {
  assert.match(BACKEND_ROUTER, /prefix="\/admin\/api\/v1\/audit-logs"/, '后端前缀与前端路径不一致')
  assert.match(BACKEND_ROUTER, /@router\.get\(""\)/, '列表读点丢失')
  assert.match(BACKEND_ROUTER, /@router\.get\("\/categories"\)/, '类别读点丢失')
  assert.match(BACKEND_ROUTER, /Depends\(get_current_admin\)/, '读点未挂管理员鉴权')
})

test('未知类别后端拒绝，而不是静默返回空列表', () => {
  assert.match(BACKEND_ROUTER, /category not in audit_service\.AUDIT_CATEGORIES/, '读口没有拦截未登记的 category')
  assert.match(BACKEND_ROUTER, /ParamError\(f"未知审计类别/, '未登记类别应报错而不是静默返回空')
})

test('读侧脱敏：明细里的凭据形状字段被替换', () => {
  assert.match(BACKEND_SERVICE, /_mask_audit_detail\(/, '读口未复用脱敏函数')
  assert.match(BACKEND_ROUTER, /list_logs/, '列表读点未走服务层')
})

test('分页与倒序：最近一条在最前', () => {
  assert.match(BACKEND_SERVICE, /AuditLog\.created_at\.desc\(\)/, '未按时间倒序')
  assert.match(BACKEND_SERVICE, /max\(1, min\(/, '服务层 page_size 未夹上下界')
  assert.match(BACKEND_ROUTER, /page_size: int = Query\(20, ge=1, le=100\)/, '接口层 page_size 未限幅')
})

test('各页面挂载的 category 都在后端登记表内', () => {
  const registry = registeredCategories()
  assert.ok(registry.length >= 15, `登记表类别数异常（${registry.length}）`)
  const mounts = [
    ['Maintenance.vue', MAINTENANCE],
    ['DatabaseAdmin.vue', DB_ADMIN],
    ['ReviewList.vue', REVIEW],
    ['ManageUsers.vue', MANAGE_USERS],
    ['AdminUsers.vue', ADMIN_USERS],
  ]
  const used = []
  for (const [name, source] of mounts) {
    const { category, tag } = mountedCategory(source)
    assert.ok(registry.includes(category), `${name} 请求了未登记类别：${category}`)
    assert.match(tag, /guide="[a-z-]+"/, `${name} 的审计块缺少 data-guide 锚点`)
    assert.match(source, /import AuditTrail from .*AuditTrail\.vue/, `${name} 未引入组件`)
    used.push(category)
  }
  assert.equal(new Set(used).size, used.length, '各页面应各自读取本模块类别，不能共用一个')
})

test('失败不能说成「暂无记录」：ListLoadError 分支先于空态', () => {
  assert.match(COMPONENT, /import ListLoadError from '\.\/ListLoadError\.vue'/)
  const errIdx = COMPONENT.indexOf('<ListLoadError')
  const emptyIdx = COMPONENT.indexOf('该模块暂无审计记录')
  assert.ok(errIdx > 0 && emptyIdx > 0, '组件里既没有失败态也没有空态')
  assert.ok(errIdx < emptyIdx, '空态排在失败态之前，渲染顺序与 v-else-if 语义不符')
  const emptyLine = COMPONENT.slice(COMPONENT.lastIndexOf('<', emptyIdx), emptyIdx)
  assert.match(emptyLine, /v-else-if/, '「暂无审计记录」未走 v-else-if：失败时也会显示成没数据')
  assert.match(COMPONENT, /:stale="items\.length > 0"/, '已有旧数据时失败应标记为 stale，而不是清空')
  assert.match(COMPONENT, /@retry="load"/, '失败态没有重试入口')
})

test('反退回：不得把 audit-logs 挂到 db-admin 专用读口上', () => {
  assert.doesNotMatch(API, /db-admin/, '通用审计读口又退回模块私有接口')
})
