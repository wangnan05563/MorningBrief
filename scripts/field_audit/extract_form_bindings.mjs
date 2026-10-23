#!/usr/bin/env node
/**
 * 抽取「界面上有输入控件、但保存时没提交」的字段——登记表里的第四类差集 (v)−(b)。
 *
 * 判据：同一视图里 `v-model="form.x"` 的 x 集合，与该视图写接口调用点提交的字段集合做差。
 * 命中即「用户填了、点了保存、库里没有」——PUT/POST 返回 200 而列不变，正是 M16/C56 的体质。
 * 白名单：纯本地开关（xxxEnabled）、拼接文本列（*_text）与另单入口，登记在 reason 里。
 */
import { readFileSync, readdirSync, statSync, writeFileSync, mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(fileURLToPath(import.meta.url), '../../..')
const SRC = path.join(ROOT, 'apps/admin-web/src')
const OUT_DIR = path.join(ROOT, 'scripts/field_audit/out')
const payloads = JSON.parse(readFileSync(path.join(OUT_DIR, 'frontend_payloads.json'), 'utf-8'))

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) walk(p, acc)
    else if (name.endsWith('.vue')) acc.push(p)
  }
  return acc
}

const rows = []
for (const abs of walk(SRC)) {
  const rel = path.relative(SRC, abs).replace(/\\/g, '/')
  const code = readFileSync(abs, 'utf-8')
  // v-model="obj.key" / v-model="obj.deep.key"
  const bound = new Map()
  for (const m of code.matchAll(/v-model="([A-Za-z_$][\w$]*)\.([\w.$]+)"/g)) {
    if (!bound.has(m[1])) bound.set(m[1], new Set())
    bound.get(m[1]).add(m[2])
  }
  if (!bound.size) continue
  // 该视图里的写调用点（POST/PUT/PATCH），按端点聚合提交字段
  const writes = payloads.endpoints.filter((e) =>
    ['POST', 'PUT', 'PATCH'].includes(e.method) &&
    e.sites.some((s) => s.file === rel))
  for (const [obj, keys] of bound) {
    const submitted = new Set(writes.flatMap((e) => e.fields))
    const missing = [...keys].filter((k) => {
      const top = k.split('.')[0]
      return !submitted.has(top) && !submitted.has(k)
    })
    if (missing.length) {
      rows.push({ file: rel, object: obj, endpoints: writes.map((e) => `${e.method} ${e.url}`),
        boundCount: keys.size, missing: missing.sort() })
    }
  }
}

mkdirSync(OUT_DIR, { recursive: true })
writeFileSync(path.join(OUT_DIR, 'form_bindings.json'),
  JSON.stringify({ rows }, null, 2) + '\n', 'utf-8')
console.log(`viewsWithBindings=${new Set(rows.map((r) => r.file)).size} rows=${rows.length}`)
for (const r of rows.filter((x) => /Material|Channel|Ad/.test(x.file))) {
  console.log(`${r.file} [${r.object}] -> ${(r.endpoints || []).join(', ') || '无写调用点'}\n    未提交: ${r.missing.join(', ')}`)
}
