/**
 * INT-UX-06（T02529）：移动端应急停服的判重与审计可追溯
 *
 * 与 backend/tests/test_int06_emergency_stop_atomicity.py 的分工：那边在真 HTTP 边界上
 * 把两个同时在飞的停服请求打出来（实测改前是「两击都 already=False、审计 2 条」）；
 * 这边守住容易被改回去的接线与跨端契约：
 *
 * 1. 判重必须发生在**一条带条件的写语句**里。写成「先 select 判断、再写」时，
 *    并发请求各自读到旧状态，判重只在串行时成立；SQLite 下读事务再升成写事务撞上
 *    并发写还会立刻 SQLITE_BUSY（busy_timeout 都不等），高危动作换来一个 500。
 *    （试过用项目的全局写锁把读+写+提交一起圈进临界区，但 asyncio.Lock 会被第一个
 *    用到它的事件循环钉死，TestClient 每个测试一个新循环 → 无关用例直接崩，
 *    所以判重必须落在数据库这一层。）
 * 2. 审计只有抢到写的那一击才写，且必须带 operator + reason + target。
 * 3. 这份审计一直有写，但唯一的老审计接口 GET /db-admin/audit-log 硬过滤
 *    category='db_admin'，停服写的是 category='mobile' → 任何界面都读不到。
 *    新增的 /m/emergency/audit 按动作白名单读，不给顺手捞别模块审计的口子。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/emergency-stop-idempotency.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf8')

const svc = () => repoFile('backend/app/services/mobile_service.py')
const router = () => repoFile('backend/app/routers/admin/mobile.py')
const apiMobile = () => repoFile('apps/admin-web/src/api/mobile.js')
const view = () => repoFile('apps/admin-web/src/views/mobile/ManageAlert.vue')

/** 取某个 async def 的函数体（到下一个顶层 def / 常量声明为止），便于按函数断言 */
function pyFn(name) {
  const src = svc()
  const from = src.indexOf(`async def ${name}(`)
  assert.notEqual(from, -1, `mobile_service.py 里找不到 ${name}`)
  const rest = src.slice(from + 1)
  const m = rest.match(/\n(?:async )?def |\n[A-Z_]+ = |\nEMERGENCY_ACTIONS/)
  return rest.slice(0, m ? m.index + 1 : undefined)
}

describe('停服判重在一条写语句里', () => {
  it('_claim_maintenance 用条件写抢状态，两个方向都有条件', () => {
    const src = svc()
    assert.match(
      src,
      /^_MAINT_ON = func\.json_extract\(SystemFlag\.value, "\$\.on"\)$/m,
      '判重条件没取 JSON 里的 on，等于没条件',
    )
    const body = pyFn('_claim_maintenance')
    assert.match(body, /update\(SystemFlag\)/, '没有走条件 UPDATE')
    assert.match(body, /_MAINT_ON\.is_\(None\), _MAINT_ON != 1/, '停服方向缺「只能从非 on 抢」的条件')
    assert.match(body, /cond = _MAINT_ON == 1/, '恢复方向缺「只能从 on 抢」的条件')
    assert.match(body, /on_conflict_do_nothing/, '行不存在时要靠主键挡回并发创建')
    assert.match(body, /return \(await db\.execute\(ins\)\)\.rowcount == 1/, 'INSERT 的 rowcount 决定输赢')
  })

  it('停服与恢复都改走 _claim_maintenance，旧的 select-then-write 已删除', () => {
    assert.match(pyFn('emergency_stop'), /_claim_maintenance\(/)
    assert.match(pyFn('resume_maintenance'), /_claim_maintenance\(/)
    assert.ok(!/_upsert_flag\(/.test(svc()), '仍留着「先读再写」的 _upsert_flag')
  })

  it('审计只在抢到写的那一击落库，already 由抢没抢到决定', () => {
    for (const fn of ['emergency_stop', 'resume_maintenance']) {
      const body = pyFn(fn)
      assert.match(
        body,
        /if claimed:\s*\n\s*db\.add\(\s*\n\s*AuditLog\(/,
        `${fn}：写审计没有被 claimed 包住`,
      )
      assert.match(body, /"already": not claimed/, `${fn}：already 不是由抢锁结果给的`)
    }
  })

  it('回给前端的状态是写完再读的那一份（判重击要如实显示赢家的原因与时间）', () => {
    for (const fn of ['emergency_stop', 'resume_maintenance']) {
      const body = pyFn(fn)
      assert.ok(
        body.indexOf('claimed = await _claim_maintenance') < body.indexOf('state = await get_maintenance'),
        `${fn}：没有在写之后再读一次状态`,
      )
    }
  })

  it('条件写真的改 value，读侧不靠「刷新补丁」兜底', () => {
    // 这条原本断的是 `populate_existing`，被探针撤掉了：把那行执行选项删掉后
    // 后端 20 条用例全绿——ORM-enabled UPDATE 本来就会让身份图里的实例过期，
    // 那个选项并无作用，留着只会让下一个人误以为「不加会读到脏的」。
    // 反过来，「条件写只盖了 updated_by、没改 value」这种错法必须有人挡。
    assert.match(
      pyFn('_claim_maintenance'),
      /\.values\(\s*value=payload, updated_by=admin_name\s*\)/,
      '抢到写的那一击没把新状态写进 value',
    )
    assert.doesNotMatch(
      pyFn('get_maintenance'),
      /\.execution_options\(/,
      '读侧又加回了刷新补丁：先证明写侧真的会脏，再来读侧兜',
    )
  })
})

describe('审计含操作者与原因，且有人能读到', () => {
  it('停服/恢复两条审计都写 operator、target，原因在 detail 里', () => {
    for (const fn of ['emergency_stop', 'resume_maintenance']) {
      const body = pyFn(fn)
      assert.match(body, /operator=admin\.username/, `${fn}：审计没有操作者`)
      assert.match(body, /target=MAINTENANCE_KEY/, `${fn}：审计没有操作目标，按对象检索不到`)
      assert.match(body, /"reason": reason/, `${fn}：审计 detail 里没有原因`)
    }
  })

  it('移动端读接口只按动作白名单取，不外捞别模块的审计', () => {
    const body = pyFn('emergency_audit')
    assert.match(body, /AuditLog\.category == "mobile"/)
    assert.match(body, /AuditLog\.action\.in_\(EMERGENCY_ACTIONS\)/)
    assert.match(svc(), /^EMERGENCY_ACTIONS = \("emergency_stop", "emergency_resume"\)$/m)
  })

  it('读接口倒序、有边界、要登录', () => {
    assert.match(pyFn('emergency_audit'), /created_at\.desc\(\), AuditLog\.id\.desc\(\)/, '不是最近优先')
    const src = router()
    assert.match(src, /@router\.get\("\/emergency\/audit"\)/)
    assert.match(src, /limit: int = Query\(20, ge=1, le=100\)/)
    const at = src.indexOf('@router.get("/emergency/audit")')
    assert.match(src.slice(at, at + 500), /Depends\(get_current_admin\)/, '读记录也要鉴权')
  })
})

describe('管理端把记录读出来', () => {
  it('api/mobile.js 请求 /m/emergency/audit 且走 silent（列表读失败不叠加 toast）', () => {
    const src = apiMobile()
    assert.match(src, /export const getEmergencyAudit = \(limit = 10\) =>/)
    // 同样是被探针纠正过的一条：整份文件裸匹配 `silent: true` 时，别的需求也能顶上，
    // 把这条请求的 silent 删掉断言仍然绿。所以断言要落在**这一段声明**里。
    const at = src.indexOf('export const getEmergencyAudit')
    const next = src.indexOf('\nexport ', at + 1)
    const stmt = src.slice(at, next === -1 ? undefined : next)
    assert.match(stmt, /api\.get\('\/m\/emergency\/audit'/, '记录列表请求打错了地址')
    assert.match(stmt, /silent: true/, '记录列表请求没走 silent：列表读失败也要弹一条 toast')
  })

  it('页面渲染「谁 / 何时 / 因为什么」三列，且有可定位的 data-guide', () => {
    const src = view()
    assert.match(src, /data-guide="emergency-audit"/)
    assert.match(src, /data-guide="emergency-audit-list"/)
    assert.match(src, /it\.operator \|\| '未知操作人'/, '列表没有操作者列')
    assert.match(src, /原因：\{\{ it\.reason \}\}/, '列表没有原因列')
    assert.match(src, /fmtDate\(it\.at\)/, '列表没有时间列')
    assert.match(src, /it\.action === 'emergency_stop' \? '停服' : '恢复'/)
  })

  it('状态刷新与两个动作之后都会重读记录（停完服当场看得到自己那条）', () => {
    const src = view()
    const calls = src.match(/await loadAudit\(\)/g) || []
    assert.equal(calls.length, 3, `loadAudit 应在 reload/stop/resume 后各调一次，实测 ${calls.length} 次`)
  })

  it('恢复也认 already：重复点恢复要说「本次未重复记录」', () => {
    const src = view()
    assert.match(src, /data\?\.already \? '系统本就是运行态，本次未重复记录' : '已恢复生产'/)
    assert.match(src, /data\?\.already \? '系统已处于停服态，本次未重复记录'/)
  })

  it('记录块不吃死底色：暗色主题下不再贴一块白（NFR-UX-04 的坑）', () => {
    const from = view().indexOf('.m-alert__audit {')
    assert.notEqual(from, -1, '找不到记录块样式')
    const css = view().slice(from, view().indexOf('}', from))
    // T02839：移动端统一走 --m-* 语义 token（--el-border-color-lighter 的浅色默认值在暗色下不吃主题）
    assert.match(css, /var\(--m-border\)/, '边框没走主题变量')
    assert.ok(!/#fff\b/.test(css), `记录块写死了浅色底：${css}`)
  })
})

describe('PRD 落档：并发判重的实测记录不能被改成「想当然」', () => {
  const prd = () => repoFile('docs/需求规格说明书-UX优化.md')

  it('§9.2 记下了改前的实测形态（两击都 already=false + 审计 2 条 + 立刻 locked）', () => {
    const src = prd()
    assert.match(src, /^### 9\.2 INT-UX-06 应急停服并发判重实测记录/m, '实测记录整节不见了')
    assert.match(src, /两次都 `code=0`、两次都 `already=false`，审计表 2 条/, '改后口径覆盖了改前实测，等于没取证')
    assert.match(src, /OperationalError: database is locked`[\s\S]{0,20}`busy_timeout` 不生效/, 'SQLITE_BUSY 立刻抛、busy_timeout 不等这个关键事实没落档')
  })

  it('记下了「为什么不用全局写锁」，否则下一个人还会去试', () => {
    assert.match(
      prd(),
      /asyncio\.Lock` 会被第一个争用到它的事件循环钉死/,
      'write_lock 的多事件循环坑没写进文档，同类改法会被重新采纳',
    )
  })

  it('记下了审计读不到是系统性缺口，且 DEC-UX-002 仍未决', () => {
    const src = prd()
    assert.match(src, /34 处审计写入分布在 13 个 `category`/, '只报了移动端这一处，别模块的缺口会被遗忘')
    assert.match(
      src,
      /另外 11 个类别（ad\/audio\/backup\/channel\/maintenance\/material\/queue\/review\/script\/user\/workflow）/,
      '读不到的类别没逐名列出，下一个人只能重新数一遍',
    )
    assert.match(src, /wc -l`\s*（34）/, '缺口没有复核命令，这两个数字下次会被重新猜')
    assert.match(src, /^\*\*仍未决\*\*：DEC-UX-002/m, '权限模型被写成已决，本单其实没碰它')
  })
})
