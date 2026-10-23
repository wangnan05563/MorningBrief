/**
 * T02926 门禁：请求模型字段对齐登记表必须与两份「事实源」一致。
 *
 * 和 help-fact-claims 同一套做法——门禁里不写死任何字段名或端点数：
 *   (a) 模型声明字段 ← scripts/field_audit/out/backend_models.json（pydantic 运行时反射）
 *   (b) 前端提交字段 ← scripts/field_audit/out/frontend_payloads.json（AST 解析调用点）
 *   (c) ORM 可写列   ← backend_models.json 的 ormModels
 *   登记表            ← scripts/field_audit/out/field_registry.json + docs/请求字段对齐登记表.md
 * 任何一份重跑后与登记表脱节 → 红。这样「文档说做了、代码没做」（M80 那一类）就过不了关。
 */
import { readFileSync, existsSync, statSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const ROOT = path.resolve(import.meta.dirname, '../../../..')
const OUT = path.join(ROOT, 'scripts/field_audit/out')
const read = (p) => JSON.parse(readFileSync(p, 'utf-8'))

const be = read(path.join(OUT, 'backend_models.json'))
const fe = read(path.join(OUT, 'frontend_payloads.json'))
const reg = read(path.join(OUT, 'field_registry.json'))
const rows = reg.rows
const byEndpoint = new Map(rows.map((r) => [r.endpoint, r]))

// 工单点名的三个域：素材 / 频道 / 广告
const GUARD_DOMAINS = [/\/materials/, /\/channels/, /\/ads\//]
// 解析缺口的理由类型：只允许这三类，防止写成「应该没事」
const REASON_KEYS = new Set(['dynamic-columns', 'value-scalar', 'spread-manually-verified'])

test('三份事实源都在（缺文件说明生成器没跑，不是「没有问题」）', () => {
  for (const f of ['backend_models.json', 'frontend_payloads.json', 'field_registry.json']) {
    assert.ok(existsSync(path.join(OUT, f)), `缺少 ${f}，请先跑 scripts/field_audit/ 下的生成命令`)
  }
})

test('登记表行数与运行时反射到的「有 body 模型的管理端点」数一致', () => {
  const derived = Object.values(be.endpoints).filter((e) => e.model).length
  assert.equal(rows.length, derived,
    `登记表 ${rows.length} 行 ≠ 运行时 ${derived} 个端点：登记表过期或后端加了端点`)
})

for (const domain of GUARD_DOMAINS) {
  test(`域 ${domain}：前端提交的每个字段都能在对应模型里找到`, () => {
    const hit = rows.filter((r) => domain.test(r.endpoint))
    assert.ok(hit.length > 0, `${domain} 一个端点都没匹配上——域名正则失效（接错对象）`)
    const noSite = new Set(read(path.join(ROOT, 'scripts/field_audit/no_callsite_whitelist.json')).entries.map((e) => e.endpoint))
    let compared = 0
    for (const r of hit) {
      const extra = r.diffs.frontendNotInModel
      assert.deepEqual(extra, [],
        `${r.endpoint} 前端提交了模型未声明的字段 ${extra.join(', ')}（模型 ${r.model} @ ${r.modelSource}）`)
      if (!r.frontend.hasCallSite) {
        // 没有调用点就没法比对「⊂」，必须要么登记为断链、要么红
        assert.ok(noSite.has(r.endpoint), `${r.endpoint} 在域内、无前端调用点、又没登记理由`)
        continue
      }
      compared += 1
      assert.ok(r.frontend.fields.length > 0, `${r.endpoint} 有调用点却提不出任何字段，比对不成立`)
    }
    assert.ok(compared > 0, `${domain} 域内一个可比对的端点都没有（抽取器或域名正则坏了）`)
  })
}

for (const [label, re, colName] of [
  ['素材 source（讲书稿按书聚合键）', /material/i, 'source'],
  ['频道 channel_type（选稿与改写策略入口）', /channel/i, 'channel_type'],
  ['频道 disclaimer_level（免责声明档位）', /channel/i, 'disclaimer_level'],
]) {
  test(`安全相关列 ${label}：字段名 ⊂ 模型字段名（漂移即红）`, () => {
    const candidates = rows.filter((r) => re.test(r.model) && r.declared.includes(colName))
    assert.ok(candidates.length > 0, `没有任何模型声明 ${colName}——列改名了，门禁必须知道`)
    let compared = 0
    for (const r of candidates) {
      if (!r.frontend.hasCallSite || r.frontend.fields.length === 0) continue
      compared += 1
      for (const f of r.frontend.fields) {
        assert.ok(r.declared.includes(f), `${r.endpoint} 提交的 ${f} 不在 ${r.model} 声明里`)
      }
      // 光「⊂ 模型」还不够：这一列必须真的在 ORM 表里，否则写了也不落库
      assert.ok(r.ormColumns.includes(colName), `${r.endpoint} 的 ${r.ormTable} 表里没有 ${colName} 列`)
    }
    assert.ok(compared > 0, `${colName} 相关端点一个可比对的前端载荷都没有，门禁形同虚设`)
  })
}

test('登记表的汇总数字是从明细现算的，不是抄的', () => {
  const t = reg.totals
  assert.equal(t.endpointsWithBodyModel, rows.length)
  assert.equal(t.forbidCount, rows.filter((r) => r.modelExtra === 'forbid').length)
  assert.equal(t.withFrontendCallSite, rows.filter((r) => r.frontend.hasCallSite).length)
  assert.deepEqual(t.noFrontendCallSite, rows.filter((r) => !r.frontend.hasCallSite).map((r) => r.endpoint))
  assert.deepEqual(t.frontendNotInModel, rows.filter((r) => r.diffs.frontendNotInModel.length).map((r) => r.endpoint))
})

test('已 forbid 的端点数：登记表说的 = 反射出来的 = 本文件断言到的', () => {
  const reflected = Object.entries(be.endpoints)
    .filter(([, e]) => e.model && e.model.extra === 'forbid').map(([k]) => k).sort()
  const inRegistry = rows.filter((r) => r.modelExtra === 'forbid').map((r) => r.endpoint).sort()
  assert.deepEqual(inRegistry, reflected,
    '登记表记录的 forbid 端点与模型实际 extra=forbid 不一致（M80 口径：说做了就必须真做了）')
  // 灰度推进时这里必须被同步修改：断言清单与 forbid 集合同集合
  const graylist = read(path.join(ROOT, 'scripts/field_audit/forbid_endpoints.json')).endpoints.map((e) => e.key).sort()
  assert.deepEqual(graylist, reflected,
    'forbid_endpoints.json 的灰度清单与运行时 extra=forbid 的端点集合不一致')
  assert.ok(graylist.length >= 1, '灰度清单为空——「分步引入 forbid」一步都没走')
  // 灰度清单每一条都要有可执行的探针字段，且该字段确实不在模型声明里（否则探针是假的）
  for (const e of read(path.join(ROOT, 'scripts/field_audit/forbid_endpoints.json')).endpoints) {
    const row = byEndpoint.get(e.key)
    assert.ok(row, `灰度清单里的 ${e.key} 在登记表中不存在（接错对象）`)
    assert.equal(row.model, e.model, `${e.key} 登记的模型名与反射结果 ${row.model} 不符`)
    assert.ok(!row.declared.includes(e.probe_field),
      `${e.key} 的探针字段 ${e.probe_field} 其实是模型声明过的字段，拒不到它`)
    assert.match(e.evidence, /[\w./-]+:\d+/, `${e.key} 缺 文件:行 证据`)
  }
})

test('每条判定都带 文件:行 证据，且证据文件真实存在', () => {
  const verdictsPath = path.join(ROOT, 'scripts/field_audit/verdicts.json')
  if (!existsSync(verdictsPath)) return // 还没开始判定阶段（无差集命中时允许）
  const verdicts = read(verdictsPath)
  for (const v of verdicts) {
    assert.match(v.evidence, /[\w./-]+:\d+/, `${v.endpoint} 的判定缺 文件:行 证据`)
    for (const token of v.evidence.split(/[\s、，]+/)) {
      const m = token.match(/^([\w./-]+):(\d+)$/)
      if (!m || !m[1].includes('/')) continue
      assert.ok(existsSync(path.join(ROOT, m[1])), `${v.endpoint} 证据指向不存在的文件 ${m[1]}`)
    }
    assert.ok(byEndpoint.has(v.endpoint), `verdicts.json 里有登记表不认识的端点 ${v.endpoint}`)
  }
})

test('差集命中与「无前端调用点」端点全部有判定或白名单理由', () => {
  const whitelistPath = path.join(ROOT, 'scripts/field_audit/no_callsite_whitelist.json')
  const whitelist = existsSync(whitelistPath) ? read(whitelistPath) : { entries: [] }
  const reasons = new Map(whitelist.entries.map((e) => [e.endpoint, e.reason]))
  for (const r of rows) {
    if (r.frontend.hasCallSite) continue
    assert.ok(reasons.has(r.endpoint),
      `${r.endpoint} 找不到前端调用点却没登记理由——要么是断链，要么是抽取器漏了，不能默默放过`)
    assert.ok(reasons.get(r.endpoint).length >= 12, `${r.endpoint} 的理由太短，不具备可复核性`)
  }
  for (const w of whitelist.entries) {
    assert.ok(byEndpoint.has(w.endpoint), `白名单里的 ${w.endpoint} 在登记表中不存在（接错对象）`)
  }
})

test('载荷静态不可定的调用点必须逐条列出，不许折叠成「没问题」', () => {
  const listed = new Map()
  for (const r of rows) {
    for (const s of r.frontend.callSites) {
      for (const u of s.unresolved) listed.set(`${r.endpoint}|${s.file}:${s.line}`, u)
    }
  }
  const wl = read(path.join(ROOT, 'scripts/field_audit/unresolved_whitelist.json'))
  const covered = new Map(wl.entries.map((e) => [`${e.endpoint}|${e.site}`, e]))
  for (const key of listed.keys()) {
    assert.ok(covered.has(key), `未登记解析缺口：${key}（${listed.get(key)}）`)
    const e = covered.get(key)
    assert.ok(REASON_KEYS.has(e.reason_key), `${key} 的理由类型不在口径内：${e.reason_key}`)
    assert.ok((e.note || '').length >= 12, `${key} 的理由太短，不具备可复核性`)
  }
  for (const e of wl.entries) {
    assert.ok(listed.has(`${e.endpoint}|${e.site}`),
      `白名单里的 ${e.endpoint} ${e.site} 已经不是解析缺口了（抽取器修好了就该删条目）`)
  }
  assert.ok(listed.size > 0, '一个解析缺口都没有——抽取器多半是坏掉了，而不是真的全都静态可定')
})

test('登记表 Markdown 里出现的每个端点都在明细里（防止文档与数据两张皮）', () => {
  const md = readFileSync(path.join(ROOT, 'docs/请求字段对齐登记表.md'), 'utf-8')
  const mentioned = [...md.matchAll(/`((?:GET|POST|PUT|PATCH|DELETE) [^`]+)`/g)].map((m) => m[1])
  assert.ok(mentioned.length >= rows.length, '文档里一个端点都没提到')
  for (const ep of new Set(mentioned)) {
    if (!byEndpoint.has(ep)) assert.fail(`文档提到 ${ep}，但登记表里没有这一行`)
  }
})

test('判定覆盖：三个域内每个「连到了表却仍有差集」的端点都有一条带证据的判定', () => {  const verdicts = new Map(read(path.join(ROOT, 'scripts/field_audit/verdicts.json')).map((v) => [v.endpoint, v]))
  const need = rows.filter((r) => GUARD_DOMAINS.some((d) => d.test(r.endpoint))
    && r.ormTable
    && Object.values(r.diffs).some((v) => v.length > 0))
  assert.ok(need.length >= 8, `域内需判定的端点只剩 ${need.length} 个——差集抽取器大概坏了，不是「全都对齐了」`)
  for (const r of need) {
    const v = verdicts.get(r.endpoint)
    assert.ok(v, `${r.endpoint} 有差集（${Object.entries(r.diffs).filter(([, x]) => x.length).map(([k]) => k).join('/')}）但没有判定`)
    assert.ok(['真缺陷（已修）', '真缺陷（登记，未修）', '设计如此', '列不可达'].includes(v.kind),
      `${r.endpoint} 的判定类型不在口径内：${v.kind}`)
    assert.ok(r.verdict, `${r.endpoint} 判定没回填进登记表行（生成器没重跑）`)
  }
  // declaredButNotHandled 是最危险的一类（PUT 200 而 DB 未变），全仓都要有说法
  for (const ep of Object.keys(reg.totals.declaredButNotHandled)) {
    assert.ok(verdicts.has(ep), `${ep} 声明了处理函数没引用的字段，却没有判定`)
  }
})

test('两份事实源不比代码旧：改了模型/视图却忘了重跑生成器 → 红', () => {
  // 门禁读的是生成产物。产物比代码旧时，「全绿」只代表旧快照自洽，不代表代码没问题
  const srcMtime = (rel) => {
    const abs = rel.startsWith('apps/admin-web') ? path.join(ROOT, rel) : path.join(ROOT, 'apps/admin-web/src', rel)
    return existsSync(abs) ? statSync(abs).mtimeMs : null
  }
  const stale = []
  const beMtime = statSync(path.join(OUT, 'backend_models.json')).mtimeMs
  const beSources = new Set()
  for (const e of Object.values(be.endpoints)) {
    if (e.model?.source?.includes(':')) beSources.add(e.model.source.split(':')[0])
    if (e.handler?.source?.includes(':')) beSources.add(e.handler.source.split(':')[0])
  }
  for (const m of Object.values(be.ormModels)) {
    if (m.source?.includes(':')) beSources.add(m.source.split(':')[0])
  }
  assert.ok(beSources.size > 20, `后端事实源只提到 ${beSources.size} 个文件，抽取器可能坏了`)
  for (const rel of beSources) {
    const abs = path.join(ROOT, rel)
    if (existsSync(abs) && statSync(abs).mtimeMs > beMtime) stale.push(rel)
  }
  const feMtime = statSync(path.join(OUT, 'frontend_payloads.json')).mtimeMs
  const feSources = new Set([
    ...fe.endpoints.flatMap((e) => e.sites.map((s) => s.file)),
    ...fe.apiDefs.map((d) => d.file),
  ])
  assert.ok(feSources.size > 20, `前端事实源只提到 ${feSources.size} 个文件，抽取器可能坏了`)
  for (const rel of feSources) {
    const ms = srcMtime(rel)
    if (ms !== null && ms > feMtime) stale.push(`apps/admin-web/src/${rel}`)
  }
  assert.deepEqual(stale, [],
    `这些源文件比生成产物新，请先跑 scripts/field_audit/ 下的三条抽取命令再判绿：\n${stale.join('\n')}`)
})
