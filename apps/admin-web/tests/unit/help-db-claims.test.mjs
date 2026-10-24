/**
 * M80：帮助文档「数据库维护」章节不许再虚标功能（随 M1 交付，主归属见 PRD §10.1）
 *
 * 原文写「提供 20+ 业务表的在线 CRUD」和「支持……SQL 查询」，而白名单实际 16 张、
 * 路由里根本没有执行任意 SQL 的入口。运维照着文档找一个不存在的查询框，只会以为
 * 是自己没找到；更糟的是「20+」这种模糊量词让人以为覆盖全库，实际只有 16 张能碰。
 *
 * 这个门不抄文档里的数字，而是从代码算出来再比——白名单以后加减，文档不改就会红。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/help-db-claims.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const HELP = readFileSync(
  new URL('../../src/views/help/Help.vue', import.meta.url),
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
// T02592 起，总开关的比较逻辑收敛到 app/core/danger_op.py（备份恢复与数据库后台共用一份）
const DANGER = readFileSync(
  new URL('../../../../backend/app/core/danger_op.py', import.meta.url),
  'utf8',
)

// 从后端源码取真实白名单表数：ALLOWED_TABLES 里的 `"name": "中文名",` 行
function allowedTableCount() {
  const open = SERVICE.indexOf('ALLOWED_TABLES: dict[str, str] = {')
  assert.notEqual(open, -1, '后端白名单常量改名了，这个门要先跟着改')
  const body = SERVICE.slice(open).split('\n}')[0]
  return (body.match(/^\s{4}"[a-z_]+":\s"/gm) || []).length
}

// 只看帮助文档里「数据库维护」那一节的正文，别拿其它章节的字眼来充数
function dbAdminSection() {
  const at = HELP.indexOf("id: 'db-admin'")
  assert.notEqual(at, -1, '帮助文档里找不到数据库维护章节')
  return HELP.slice(at, at + 2000)
}

describe('M80 数据库维护帮助文案与代码一致', () => {
  it('表白名单数量按后端源码算，文档不许写模糊量词', () => {
    const real = allowedTableCount()
    assert.ok(real > 0, '白名单解析出来是 0，多半是缩进或常量名变了')
    assert.match(
      dbAdminSection(),
      new RegExp(`白名单内 ${real} 张业务表`),
      `帮助文档没写实际的 ${real} 张（后端 ALLOWED_TABLES 说了算）`,
    )
    assert.doesNotMatch(dbAdminSection(), /20\+|数十张|多张/, '模糊量词等于没写')
  })

  it('不再宣称支持 SQL 查询，且明说不提供', () => {
    const sec = dbAdminSection()
    // 老文案的形态是「记录编辑、SQL 查询、CSV 导入导出」——列进支持清单里了
    assert.doesNotMatch(sec, /、\s*SQL/, 'SQL 又被列进功能清单')
    assert.doesNotMatch(sec, /支持[^。]{0,40}SQL/, '文档又在承诺一个不存在的入口')
    assert.match(sec, /不提供 SQL 查询/, '没有正面否认，用户还会继续找')
    assert.doesNotMatch(
      ROUTER,
      /@router\.(get|post|put|patch|delete)\(\s*"[^"]*(sql|query)/i,
      '后端真要是有 SQL 执行入口，这条门就得跟着改口径',
    )
  })

  it('确认文本写的是实际语义：删除输表名、导入输 IMPORT、服务端总开关', () => {
    const sec = dbAdminSection()
    assert.match(sec, /删除输入表名/, '删除的确认词是表名，不是固定口令')
    assert.match(sec, /导入输入 IMPORT/, '导入的确认词是 IMPORT')
    assert.match(sec, /DB_ADMIN_CONFIRM_TOKEN/, '没写服务端总开关，运维会以为是自己的拼写问题（M29 的原坑）')
    assert.match(DANGER, /if not server_token/, '后端这个开关变了，文档要同步')
    assert.match(ROUTER, /validate_danger_op\(/, '危险操作确认不再走共用实现，文档的口径要重新核')
  })

  it('脱敏与 dry-run 预览的承诺有实现兜着', () => {
    assert.match(dbAdminSection(), /dry-run 预览/, '预览是 FR-UX-102 交付的，文档不该只字不提')
    assert.match(SERVICE, /def update_row/, '编辑保存入口不在了，文档要跟着改')
    assert.match(dbAdminSection(), /不会把脱敏占位值写回真实凭据/, 'M14 的行为承诺不见了')
  })
})

describe('M80 在 PRD 里只记一次主归属', () => {
  const PRD = readFileSync(
    new URL('../../../../docs/需求规格说明书-UX优化.md', import.meta.url),
    'utf8',
  )

  it('§10.1 把 M80 留在 M1，FR-UX-401 不再重复认领', () => {
    assert.match(PRD, /\| M1 \| 11 \|[^|]*M80/, 'M80 的主归属被改走，M1 的 11 条就对不上')
    const fr401 = PRD.slice(PRD.indexOf('| FR-UX-401 |'), PRD.indexOf('\n', PRD.indexOf('| FR-UX-401 |')))
    assert.doesNotMatch(fr401, /A9, M83, M80/, '同一条在两个 FR 里各算一次，排期会重复')
    assert.match(fr401, /M80（帮助文档虚标[^）]*）主归属 M1/, '剔了编号却没说去向，下一个人会以为是漏写')
  })

  it('ACC-UX-101 第 7 条把 M80 变成可验收项', () => {
    const acc = PRD.slice(PRD.indexOf('**验收（ACC-UX-101）**'))
    assert.match(acc.slice(0, 2000), /7\. 帮助文档「数据库维护」/, '文档虚标没有验收口径，修一次就会再虚标回去')
    assert.match(acc.slice(0, 2000), /按 `ALLOWED_TABLES` 计/, '数量没有算源，又会退回拍脑袋的「20+」')
  })
})
