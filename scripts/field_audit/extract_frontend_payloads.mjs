#!/usr/bin/env node
/**
 * 抽取「前端实际提交的字段」——请求模型字段对齐登记表的数据源之一。
 *
 * 做法：先用 @babel/parser 解析 apps/admin-web/src/api/*.js，得到
 *   导出函数 → (HTTP 方法, 路径, 载荷参数位)，
 * 再解析 src/**\/*.js 与 src/**\/*.vue（取 <script setup> 块），
 *   在每个调用点把载荷参数（或它指向的局部声明）展开成字段集合。
 *
 * 之所以要用 AST 而不是正则：C56 的教训是「看不见的字段」才是缺陷。
 * 之所以要**按函数作用域**解析变量：AIConfig.vue 里有好几个不同的
 * `const payload`，按文件级同名合并会把它们的字段并成一个集合，
 * 于是凭空造出「前端提交了模型没有的字段」的假缺陷。
 * 解析不出来的（如 `...row` 展开）必须显式标 unresolved 交给门禁拦，
 * 而不是静默当成没有。
 *
 * 输出 JSON：scripts/field_audit/out/frontend_payloads.json
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(fileURLToPath(import.meta.url), '../../..')
// @babel/parser 只在 apps/admin-web 的依赖树里，从这里解析出它的绝对位置
const require = createRequire(path.join(ROOT, 'apps/admin-web/package.json'))
const { parse } = require('@babel/parser')
const SRC = path.join(ROOT, 'apps/admin-web/src')
const OUT_DIR = path.join(ROOT, 'scripts/field_audit/out')

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) walk(p, acc)
    else if (/\.(js|vue)$/.test(name)) acc.push(p)
  }
  return acc
}

function parseJs(code) {
  return parse(code, { sourceType: 'module', plugins: ['jsx'] })
}

/** .vue 只取 <script setup> 块；返回 { ast, lineOffset } 让行号对得上原文件 */
function parseVue(code) {
  const m = code.match(/<script\s+setup[^>]*>([\s\S]*?)<\/script>/)
  if (!m) return null
  const before = code.slice(0, m.index + m[0].indexOf('>') + 1)
  const lineOffset = before.split('\n').length - 1
  // 用一个空壳包起来会改变行号，所以直接解析块内容，行号靠 lineOffset 补
  return { ast: parseJs(m[1]), lineOffset }
}

const API_METHODS = new Set(['get', 'post', 'put', 'patch', 'delete', 'head', 'options'])

function normalizeUrl(raw) {
  // `${base}/materials/${id}` -> /materials/*
  let s = raw
  if (s.startsWith('`')) s = s.slice(1, -1)
  s = s.replace(/\$\{[^}]*\}/g, '*')
  s = s.replace(/^\/admin\/api\/v1/, '')
  if (!s.startsWith('/')) {
    // 拼接形式：api.post(`${BASE}/rows`) 之类，BASE 不可静态确定时保留原样
    s = '/' + s.replace(/^\/+/, '')
  }
  return s
}

function isApiCall(node) {
  const c = node.callee
  if (c.type !== 'MemberExpression') return null
  const obj = c.object.type === 'Identifier' ? c.object.name : null
  if (obj !== 'api' && obj !== 'request' && obj !== 'http' && obj !== 'client') return null
  const method = c.property.name
  return API_METHODS.has(method) ? method : null
}

/** 表达式节点里的字符串字面量/模板头部，取 URL */
function urlOfArg(node) {
  if (!node) return null
  if (node.type === 'StringLiteral') return node.value
  if (node.type === 'TemplateLiteral' && node.quasis.length) {
    // 模板各段拼接，${} 换成 *
    let out = ''
    node.quasis.forEach((q, i) => {
      out += q.value.cooked ?? q.value.raw
      if (i < node.expressions.length) out += '*'
    })
    return out
  }
  return null
}

function walkAst(root, visit, ctx = {}) {
  if (!root || typeof root.type !== 'string') return
  visit(root, ctx)
  for (const key of Object.keys(root)) {
    if (key === 'loc' || key === 'leadingComments' || key === 'trailingComments') continue
    const v = root[key]
    if (Array.isArray(v)) {
      for (const child of v) if (child && child.type) walkAst(child, visit, ctx)
    } else if (v && v.type) {
      walkAst(v, visit, ctx)
    }
  }
}

const FUNC_TYPES = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'])
const WRAPPERS = new Set(['reactive', 'ref', 'computed', 'toRaw', 'markRaw', 'toRef', 'shallowRef', 'shallowReactive'])

function unwrapInit(init) {
  // reactive({...}) / ref({...}) -> 里面的对象字面量；computed(() => ({...})) 也顺一层箭头函数
  let n = init
  for (let i = 0; i < 4 && n; i++) {
    if (n.type === 'ObjectExpression') return n
    if (n.type === 'CallExpression' && n.callee.type === 'Identifier' && WRAPPERS.has(n.callee.name)) {
      n = n.arguments[0]
      continue
    }
    if (n.type === 'ArrowFunctionExpression' || n.type === 'FunctionExpression') {
      n = n.body
      continue
    }
    if (n.type === 'BlockStatement' && n.body.length === 1) {
      const only = n.body[0]
      n = only.type === 'ReturnStatement' ? only.argument : null
      continue
    }
    if (n.type === 'ConditionalExpression') {
      return null // 分支载荷，交给 unresolved
    }
    return n
  }
  return null
}

/** 带「当前函数作用域」的遍历：walkAst 的 ctx 不会随嵌套更新，作用域必须靠这个版本 */
function traverse(node, scope, fn) {
  if (!node || typeof node.type !== 'string') return
  let next = scope
  if (FUNC_TYPES.has(node.type)) next = { start: node.start, end: node.end }
  fn(node, next)
  for (const key of Object.keys(node)) {
    if (key === 'loc' || key === 'leadingComments' || key === 'trailingComments') continue
    const v = node[key]
    if (Array.isArray(v)) {
      for (const child of v) if (child && child.type) traverse(child, next, fn)
    } else if (v && v.type) {
      traverse(v, next, fn)
    }
  }
}

/**
 * 建立「作用域内的对象字面量声明 / 成员赋值」索引。
 * 每个条目带它所处函数体的字节区间，解析时只在**同一个或外层作用域**里找同名声明，
 * 这样多个 `const payload` 不会互相污染。
 */
function buildScopeIndex(ast) {
  const decls = []
  const assigns = []

  traverse(ast.program, null, (node, scope) => {
    if (node.type === 'VariableDeclarator' && node.id.type === 'Identifier') {
      const init = unwrapInit(node.init)
      if (init && init.type === 'ObjectExpression') {
        decls.push({ name: node.id.name, line: node.loc.start.line, scope, node: init })
      } else if (init && (init.type === 'Identifier' || init.type === 'MemberExpression')) {
        decls.push({ name: node.id.name, line: node.loc.start.line, scope, node: init, alias: true })
      }
    }
    if (node.type === 'AssignmentExpression' && node.left.type === 'MemberExpression' &&
        node.left.object.type === 'Identifier') {
      const prop = node.left.property
      const propName = prop.name ?? (prop.type === 'StringLiteral' ? prop.value : null)
      if (propName && !node.left.computed) {
        assigns.push({ base: node.left.object.name, prop: propName, line: node.loc.start.line, scope })
      }
    }
  })
  return { decls, assigns }
}

function sameOrInner(candidate, caller) {
  if (!caller) return true
  if (!candidate) return false
  // 同作用域，或 candidate 在 caller 之内（嵌套函数里定义的），都允许
  return candidate.start >= caller.start && candidate.end <= caller.end
}

function resolveIdentifier(name, line, callerScope, index) {
  const cands = index.decls.filter((d) => d.name === name && d.line <= line &&
    (!callerScope || d.scope === callerScope || sameOrInner(d.scope, callerScope) || sameOrInner(callerScope, d.scope)))
  if (!cands.length) return null
  // 就近：字节起点最接近调用点的
  cands.sort((a, b) => b.line - a.line)
  return cands[0]
}

/** 把载荷表达式展开成字段名集合；返回 {fields, unresolved} */
function fieldsOf(node, prefix, seen, callerScope, index) {
  const fields = []
  const unresolved = []
  if (!node) return { fields, unresolved }
  if (node.type === 'ObjectExpression') {
    for (const p of node.properties) {
      if (p.type === 'ObjectProperty') {
        const key = p.key.name ?? (p.key.type === 'StringLiteral' ? p.key.value : null)
        if (!key) { unresolved.push(`${prefix || '?'}[计算键]`); continue }
        const dotted = prefix ? `${prefix}.${key}` : key
        if (p.value && p.value.type === 'ObjectExpression') {
          const sub = fieldsOf(p.value, dotted, seen, callerScope, index)
          fields.push(...sub.fields); unresolved.push(...sub.unresolved)
          fields.push(dotted)
        } else if (p.value && p.value.type === 'ArrayExpression') {
          fields.push(dotted)
          p.value.elements.forEach((el, i) => {
            if (el && el.type === 'ObjectExpression') {
              const sub = fieldsOf(el, `${dotted}[${i}]`, seen, callerScope, index)
              fields.push(...sub.fields)
            }
          })
        } else {
          fields.push(dotted)
        }
      } else if (p.type === 'SpreadElement') {
        if (p.argument.type === 'ObjectExpression') {
          const sub = fieldsOf(p.argument, prefix, seen, callerScope, index)
          fields.push(...sub.fields); unresolved.push(...sub.unresolved)
        } else if (p.argument.type === 'Identifier') {
          const d = resolveIdentifier(p.argument.name, p.loc.start.line, callerScope, index)
          if (d && d.node && d.node.type === 'ObjectExpression') {
            const sub = fieldsOf(d.node, prefix, seen, callerScope, index)
            fields.push(...sub.fields); unresolved.push(...sub.unresolved)
          } else {
            unresolved.push(`展开 ${prefix ? prefix + '.' : ''}${p.argument.name}（静态不可定）`)
          }
        } else {
          unresolved.push(`展开 ${prefix || ''}${p.argument.type}`)
        }
      }
    }
    return { fields, unresolved }
  }
  if (node.type === 'Identifier' || node.type === 'MemberExpression') {
    const name = node.type === 'Identifier' ? node.name :
      (node.object.type === 'Identifier' ? node.object.name : null)
    if (!name) {
      unresolved.push(`载荷属性访问 ${prefix || ''}<动态对象>`)
      return { fields, unresolved }
    }
    const startLine = node.loc.start.line
    const key = `${name}@${startLine}@${prefix}`
    if (seen.has(key)) return { fields, unresolved }
    seen.add(key)
    const d = resolveIdentifier(name, startLine, callerScope, index)
    if (!d) {
      // 参数传进来的对象（函数入参）——静态不可定，必须显式记录
      unresolved.push(`变量 ${prefix ? prefix + '.' : ''}${name} 无可解析的声明`)
      return { fields, unresolved }
    }
    if (d.node.type === 'ObjectExpression') {
      const sub = fieldsOf(d.node, prefix, seen, callerScope, index)
      // 同名变量在声明后又被 payload.x = ... 追加的键，也是实际提交出去的
      index.assigns
        .filter((a) => a.base === name && a.line <= startLine &&
          (!callerScope || a.scope === callerScope || sameOrInner(a.scope, callerScope) || sameOrInner(callerScope, a.scope)))
        .forEach((a) => sub.fields.push(prefix ? `${prefix}.${a.prop}` : a.prop))
      return sub
    }
    if (d.node.type === 'Identifier') {
      return fieldsOf(d.node, prefix, new Set([...seen, key]), callerScope, index)
    }
    unresolved.push(`变量 ${name} 指向 ${d.node.type}`)
    return { fields, unresolved }
  }
  if (node.type === 'CallExpression') {
    // 如 buildPayload(...)：函数名本身给不出字段
    const n = node.callee.name ?? node.callee.property?.name ?? node.callee.type
    unresolved.push(`载荷来自函数调用 ${n}()`)
    return { fields, unresolved }
  }
  unresolved.push(`载荷表达式 ${node.type}`)
  return { fields, unresolved }
}

/** 节点所处最近的外层具名函数（用于识别 api/*.js 里的包装函数自身） */
function buildNamedFnRanges(ast) {
  const ranges = []
  const visit = (node) => {
    let name = null
    if (node.type === 'FunctionDeclaration') name = node.id?.name
    else if (node.type === 'VariableDeclarator' && node.init &&
      (node.init.type === 'ArrowFunctionExpression' || node.init.type === 'FunctionExpression')) name = node.id?.name
    else if (node.type === 'ExportNamedDeclaration' && node.declaration) {
      const d = node.declaration
      name = d.type === 'FunctionDeclaration' ? d.id?.name : d.declarations?.[0]?.id?.name
    }
    if (name) ranges.push({ name, start: node.start, end: node.end })
  }
  walkAst(ast.program, visit, {})
  return ranges
}

/** 包住 node 的最内层具名函数名 */
function enclosingFn(node, fnRanges) {
  let best = null
  for (const r of fnRanges) {
    if (r.start <= node.start && node.end <= r.end) {
      if (!best || r.end - r.start < best.end - best.start) best = r
    }
  }
  return best ? best.name : null
}

function buildScopeOfLine(ast) {
  const ranges = []
  const visit = (node) => {
    if (FUNC_TYPES.has(node.type)) ranges.push({ start: node.start, end: node.end })
  }
  walkAst(ast.program, visit, {})
  return ranges
}

function scopeFor(node, ranges) {
  let best = null
  for (const r of ranges) {
    if (r.start <= node.start && node.end <= r.end) {
      if (!best || r.end - r.start < best.end - best.start) best = r
    }
  }
  return best
}

function collectApiDefs(apiDir) {
  /** 导出函数名 -> {method, url, argPos} */
  const defs = new Map()
  for (const file of readdirSync(apiDir)) {
    if (!file.endsWith('.js')) continue
    const code = readFileSync(path.join(apiDir, file), 'utf-8')
    let ast
    try { ast = parseJs(code) } catch { continue }
    const fileIndex = buildScopeIndex(ast)
    const visit = (node) => {
      const isFn = (node.type === 'ExportNamedDeclaration' && node.declaration &&
        (node.declaration.type === 'FunctionDeclaration' ||
          (node.declaration.type === 'VariableDeclaration' && node.declaration.declarations.length))) ||
        node.type === 'FunctionDeclaration' ||
        (node.type === 'VariableDeclarator' && node.init &&
          (node.init.type === 'ArrowFunctionExpression' || node.init.type === 'FunctionExpression'))
      if (!isFn) return
      let fnName = null
      let body = null
      let params = []
      if (node.type === 'ExportNamedDeclaration') {
        const d = node.declaration
        if (d.type === 'FunctionDeclaration') { fnName = d.id?.name; body = d.body; params = d.params }
        else {
          const v = d.declarations[0]
          fnName = v.id?.name
          const fn = v.init
          if (fn && (fn.type === 'ArrowFunctionExpression' || fn.type === 'FunctionExpression')) {
            body = fn.body; params = fn.params
          }
        }
      } else if (node.type === 'FunctionDeclaration') {
        fnName = node.id?.name; body = node.body; params = node.params
      } else {
        fnName = node.id?.name
        const fn = node.init
        body = fn.body; params = fn.params
      }
      if (!fnName || !body) return
      // 找函数体里的 api.<method>(url, payload) —— 优先非 GET（GET 一般只有 params）
      const calls = []
      const collect = (n) => {
        if (n.type === 'CallExpression') {
          const method = isApiCall(n)
          if (method) {
            const url = urlOfArg(n.arguments[0])
            if (url) calls.push({ method, url, node: n })
          }
        }
      }
      walkAst(body, collect, {})
      const nonGet = calls.find((c) => c.method !== 'get' && c.method !== 'head')
      const chosen = nonGet || calls[0]
      if (chosen) {
        defs.set(fnName, {
          fn: fnName,
          method: chosen.method,
          url: normalizeUrl(chosen.url),
          file: `api/${file}`,
          line: chosen.node.loc.start.line,
          argNames: params.map((p) => (p.type === 'Identifier' ? p.name : null)),
          // 包装函数体里真正交给后端的那个载荷表达式——字段名由它的键决定，
          // 调用点的实参只用来展开 ...spread，不能反过来把第 1 个形参当成载荷
          payloadExpr: chosen.node.arguments[1] || null,
          defIndex: fileIndex,
        })
      }
    }
    walkAst(ast.program, visit, {})
  }
  return defs
}

function main() {
  const apiDefs = collectApiDefs(path.join(SRC, 'api'))
  const files = walk(SRC)
  const sites = []

  for (const abs of files) {
    const rel = path.relative(SRC, abs).replace(/\\/g, '/')
    const code = readFileSync(abs, 'utf-8')
    let parsed
    try {
      parsed = rel.endsWith('.vue') ? parseVue(code) : { ast: parseJs(code), lineOffset: 0 }
    } catch {
      continue
    }
    if (!parsed) continue
    const { ast, lineOffset } = parsed
    const index = buildScopeIndex(ast)
    const ranges = buildScopeOfLine(ast)
    const fnRanges = buildNamedFnRanges(ast)
    const lineOf = (n) => n.loc.start.line + lineOffset

    const visit = (node, _ctx) => {
      if (node.type !== 'CallExpression') return
      let method = null, url = null, payloadNode = null, fnName = null
      const direct = isApiCall(node)
      if (direct) {
        method = direct
        url = urlOfArg(node.arguments[0])
        payloadNode = node.arguments[1]
        fnName = `api.${method}`
        // api/*.js 包装函数体里的那一次调用是「定义」，不是调用点：
        // 它带着形参名（payload/data/body），会被误报成「变量无法解析」的空字段站点
        if (url) {
          const host = enclosingFn(node, fnRanges)
          const def = host ? apiDefs.get(host) : null
          if (def && def.method === method && def.url === normalizeUrl(url)) return
        }
      } else if (node.callee.type === 'Identifier') {
        const def = apiDefs.get(node.callee.name)
        if (def) {
          method = def.method
          url = def.url
          // 把 api 包装函数的形参按位置绑定到实参，再在「包装函数体自己的作用域索引」里
          // 展开它的载荷表达式：键名来自包装函数，值/展开来自调用点
          // 只有真的出现在载荷表达式里的形参才参与解析：
          // generateChannelIcon(id, prompt) 里 id 只是路径参数，把它当载荷会把整个频道表单算进来
          const usedParams = new Set()
          if (def.payloadExpr) {
            traverse(def.payloadExpr, null, (n) => { if (n.type === 'Identifier') usedParams.add(n.name) })
          }
          const boundDecls = []
          const callerArgs = []
          def.argNames.forEach((nm, i) => {
            const argNode = node.arguments[i]
            if (!nm || !argNode || !usedParams.has(nm)) return
            if (['ObjectExpression', 'Identifier', 'MemberExpression', 'ArrayExpression'].includes(argNode.type)) {
              boundDecls.push({ name: nm, line: 0, scope: null, node: argNode })
              if (argNode.type === 'ObjectExpression' || argNode.type === 'Identifier') callerArgs.push(argNode)
            }
          })
          const merged = {
            decls: [...(def.defIndex?.decls || []), ...boundDecls],
            // 只合并 api 文件自己的成员赋值；视图里的 payload.x= 属于调用点作用域，
            // 混进来会让同文件多个同名 payload 互相污染（AIConfig 的三个 const payload）
            assigns: [...(def.defIndex?.assigns || [])],
          }
          const scope = scopeFor(node, ranges)
          const fields = new Set()
          const unresolved = new Set()
          if (def.payloadExpr) {
            const r = fieldsOf(def.payloadExpr, '', new Set(), null, merged)
            r.fields.forEach((f) => fields.add(f))
            r.unresolved.forEach((u) => unresolved.add(u))
          }
          // 调用点直接传对象（或指向对象的变量）时，它的键同样是提交字段
          for (const argNode of callerArgs) {
            const r2 = fieldsOf(argNode, '', new Set(), scope, index)
            r2.fields.forEach((f) => fields.add(f))
            r2.unresolved.forEach((u) => unresolved.add(u))
          }
          sites.push({ fn: node.callee.name, method, url, file: rel, line: lineOf(node),
            fields: [...fields], unresolved: [...unresolved], def: `${def.file}:${def.line}` })
          return
        }
      }
      if (!method || !url) return
      const scope = scopeFor(node, ranges)
      const r = fieldsOf(payloadNode, '', new Set(), scope, index)
      sites.push({ fn: fnName, method, url: normalizeUrl(url), file: rel, line: lineOf(node),
        fields: r.fields, unresolved: r.unresolved })
    }
    walkAst(ast.program, visit, {})
  }

  // 聚合到端点维度
  const byEndpoint = new Map()
  for (const s of sites) {
    const key = `${s.method.toUpperCase()} ${s.url}`
    if (!byEndpoint.has(key)) byEndpoint.set(key, { method: s.method.toUpperCase(), url: s.url, fields: new Set(), unresolved: new Set(), sites: [] })
    const e = byEndpoint.get(key)
    s.fields.forEach((f) => e.fields.add(f))
    s.unresolved.forEach((u) => e.unresolved.add(u))
    e.sites.push({ file: s.file, line: s.line, fn: s.fn, fieldCount: s.fields.length, unresolved: s.unresolved })
  }

  const endpoints = [...byEndpoint.values()]
    .sort((a, b) => a.method.localeCompare(b.method) || a.url.localeCompare(b.url))
    .map((e) => ({
      method: e.method, url: e.url,
      fields: [...e.fields].sort(),
      unresolved: [...e.unresolved].sort(),
      sites: e.sites.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line),
    }))

  mkdirSync(OUT_DIR, { recursive: true })
  writeFileSync(path.join(OUT_DIR, 'frontend_payloads.json'),
    JSON.stringify({ endpoints, apiDefs: [...apiDefs.values()], rawSites: sites.length }, null, 2) + '\n', 'utf-8')
  console.log(`endpoints=${endpoints.length} sites=${sites.length} apiDefs=${apiDefs.size}`)
}

/** api 包装函数体里真正的载荷表达式：优先第 2 个形参，其次任何对象形参 */
function payloadNodeOfDef(def, bound) {
  const candidates = []
  def.argNames.forEach((nm, i) => {
    const n = bound.get(nm)
    if (!n) return
    if (i === 0 || /payload|data|body|req|params|form|config|options/.test(nm || '')) candidates.unshift(n)
    else candidates.push(n)
  })
  return candidates[0] || null
}

main()
