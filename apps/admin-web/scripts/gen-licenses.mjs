// 生成关于页开源清单（T02691 / FR-UX-404）。
//
// 版本取自两份真实清单（package.json 的 dependencies + devDependencies、
// backend/requirements.txt 去重后的 name==pin），许可与仓库取自已安装包的元数据：
// 前端读 node_modules/<name>/package.json，后端读 backend/.venv 里 importlib.metadata
// 暴露的字段。取不到许可时保留条目并写「未知（需人工确认）」——静默丢弃会让合规
// 清单看起来是完整的。写回只替换 About.vue 里 // <licenses> 与 // </licenses> 之间的
// 字面量，避免正则改代码；构建期仍由 scripts/validate-nav.mjs 逐条对账兜底。

import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const UNKNOWN_LICENSE = '未知（需人工确认）'
export const LICENSES_START = '// <licenses>'
export const LICENSES_END = '// </licenses>'

const HERE = dirname(fileURLToPath(import.meta.url))
const WEB_ROOT = resolve(HERE, '..')
const REPO_ROOT = resolve(WEB_ROOT, '../..')

function clean(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

/** `uvicorn[standard]==0.27.0` → `{ name: 'uvicorn', version: '0.27.0' }`；行内注释剥掉，大小写/下划线去重 */
export function parseRequirements(text) {
  const out = []
  const seen = new Set()
  for (const raw of String(text).split(/\r?\n/)) {
    const line = raw.replace(/#.*$/, '').trim()
    if (!line) continue
    const m = /^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([A-Za-z0-9][A-Za-z0-9._-]*)/.exec(line)
    if (!m) continue
    const key = m[1].toLowerCase().replace(/_/g, '-')
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ name: m[1], version: m[2] })
  }
  return out
}

// 只收「能确定」的许可写法；返回 null 表示这条字段不可用（交给下一级兜底）。
const LICENSE_RULES = [
  [/affero/i, 'AGPL-3.0'],
  [/^(?:mit|expat)(?: license)?$/i, 'MIT'],
  [/^apache(?:[-\s]+license)?(?:[-\s]+2\.0)?$/i, 'Apache-2.0'],
  [/^bsd[-\s]3[-\s]clause(?: and public-domain)?$/i, 'BSD-3-Clause'],
  [/^bsd[-\s]2[-\s]clause$/i, 'BSD-2-Clause'],
  [/^isc(?: license)?$/i, 'ISC'],
  [/^mpl[-\s]?2(?:\.0)?$/i, 'MPL-2.0'],
  [/^lgpl[-\s]?3(?:\.0)?$/i, 'LGPL-3.0'],
  [/^gpl[-\s]?3(?:\.0)?$/i, 'GPL-3.0'],
]

// SPDX 表达式（允许 AND/OR/WITH 连接）：`BSD-3-Clause AND Public-Domain`
const SPDX_EXPR = /^[A-Za-z0-9.+-]+(?:\s+(?:AND|OR|WITH)\s+[A-Za-z0-9.+-]+)*$/i

function canonicalLicense(raw) {
  const text = clean(raw)
  if (!text || /^unknown$/i.test(text)) return null
  for (const [re, value] of LICENSE_RULES) {
    if (!re.test(text)) continue
    if (/public-domain/i.test(text)) return 'BSD-3-Clause AND Public-Domain'
    return value
  }
  if (SPDX_EXPR.test(text)) {
    return text.replace(/\s+(and|or|with)\s+/gi, (_, op) => ` ${op.toUpperCase()} `)
  }
  return null
}

const CLASSIFIER_RULES = [
  [/MIT License/i, 'MIT'],
  [/Apache Software License/i, 'Apache-2.0'],
  [/GNU Affero General Public License v3/i, 'AGPL-3.0'],
  [/GNU Lesser General Public License v3/i, 'LGPL-3.0'],
  [/GNU General Public License v3/i, 'GPL-3.0'],
  [/Mozilla Public License 2\.0/i, 'MPL-2.0'],
  [/BSD License/i, 'BSD-3-Clause'],
]

/** PyPI 元数据里的 License 常是长句/旧写法，先按已知规则收敛，再退到 License 分类器 */
export function licenseFromPyMeta(meta) {
  if (!meta) return UNKNOWN_LICENSE
  const expression = canonicalLicense(meta.licenseExpression)
  if (expression) return expression
  // 具体写法（BSD-2-Clause）比分类器（BSD License）更准，先用它，避免被分类器覆盖
  const license = canonicalLicense(meta.license)
  if (license) return license
  for (const classifier of meta.classifiers ?? []) {
    for (const [re, value] of CLASSIFIER_RULES) {
      if (re.test(classifier)) return value
    }
  }
  const raw = clean(meta.license)
  return raw && !/^unknown$/i.test(raw) ? raw : UNKNOWN_LICENSE
}

export function licenseFromNpmPackage(pkg) {
  if (!pkg) return UNKNOWN_LICENSE
  const candidates = []
  if (typeof pkg.license === 'string') candidates.push(pkg.license)
  else if (pkg.license && typeof pkg.license.type === 'string') candidates.push(pkg.license.type)
  for (const item of pkg.licenses ?? []) candidates.push(typeof item === 'string' ? item : item?.type)
  const found = [...new Set(candidates.map(canonicalLicense).filter(Boolean))]
  if (found.length) return found.join(' OR ')
  const raw = clean(candidates.find(Boolean))
  return raw && !/^unknown$/i.test(raw) ? raw : UNKNOWN_LICENSE
}

/** `git+ssh://git@github.com:o/r.git` / `git://…` / `git+https://…` 统一成可点的 https 仓库地址 */
export function normalizeRepoUrl(raw) {
  let url = clean(raw)
  if (!url) return ''
  url = url.split('#')[0].split('?')[0]
  url = url.replace(/^github:/i, 'https://github.com/')
  url = url.replace(/^git\+/i, '')
  url = url.replace(/^ssh:\/\/git@([^:/]+)[:/]/i, 'https://$1/')
  url = url.replace(/^git@([^:/]+):/i, 'https://$1/')
  url = url.replace(/^git:\/\//i, 'https://')
  url = url.replace(/^http:\/\/(?:www\.)?github\.com\//i, 'https://github.com/')
  return url.replace(/\/+$/, '').replace(/\.git$/i, '')
}

const PY_REPO_LABELS = ['repository', 'source', 'source code', 'code', 'github', 'homepage']

export function repoFromPyMeta(name, meta) {
  if (meta) {
    const urls = meta.projectUrls ?? []
    for (const label of PY_REPO_LABELS) {
      const hit = urls.find((item) => clean(item?.label).toLowerCase() === label)
      if (hit) {
        const url = normalizeRepoUrl(hit.url)
        if (url) return url
      }
    }
    // 先信 Home-page，再退到任意 GitHub 链接：Changelog / Issue Tracker 也常挂在
    // github.com 下，先扫链接会把「仓库」指到 changelog 文件或 issues 列表
    const home = normalizeRepoUrl(meta.homePage)
    if (home) return home
    for (const item of urls) {
      const url = normalizeRepoUrl(item?.url)
      if (/github\.com/i.test(url)) return url
    }
  }
  return `https://pypi.org/project/${encodeURIComponent(name)}/`
}

export function repoFromNpmPackage(name, pkg) {
  const repo = pkg?.repository
  const raw = typeof repo === 'string' ? repo : repo?.url
  const url = normalizeRepoUrl(raw)
  return url || `https://www.npmjs.com/package/${encodeURIComponent(name)}`
}

/**
 * npm / PyPI 两条来源合成一张表。
 * npm: [{ name, version, pkg }]，py: [{ name, version, meta }]；pkg/meta 为 null 表示读不到元数据。
 */
export function buildEntries({ npm = [], py = [] } = {}) {
  const rows = [
    ...npm.map((dep) => ({
      name: dep.name,
      version: dep.version,
      license: licenseFromNpmPackage(dep.pkg),
      repo: repoFromNpmPackage(dep.name, dep.pkg),
    })),
    ...py.map((dep) => ({
      name: dep.name,
      version: dep.version,
      license: licenseFromPyMeta(dep.meta),
      repo: repoFromPyMeta(dep.name, dep.meta),
    })),
  ]
  return rows.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
}

function quote(value) {
  return `'${String(value).replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`
}

export function renderEntries(entries) {
  const lines = entries.map(
    (row) =>
      `  { name: ${quote(row.name)}, version: ${quote(row.version)}, license: ${quote(row.license)}, repo: ${quote(row.repo)} },`,
  )
  return [
    'const licenses = [',
    ...lines,
    "].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))",
  ].join('\n')
}

/** 只替换标记块内部；标记缺失/重复直接报错，避免把表插到错误位置 */
export function replaceLicenseBlock(source, declaration) {
  const text = String(source)
  const start = text.indexOf(LICENSES_START)
  const end = text.indexOf(LICENSES_END)
  if (start < 0 || end < 0) {
    throw new Error(`About.vue 缺少 ${LICENSES_START} / ${LICENSES_END} 标记，拒绝猜位置写入`)
  }
  if (text.indexOf(LICENSES_START, start + 1) >= 0 || text.indexOf(LICENSES_END, end + 1) >= 0) {
    throw new Error(`About.vue 的许可证标记出现多次，拒绝写入`)
  }
  if (end < start) throw new Error('About.vue 的许可证结束标记出现在开始标记之前')
  const body = declaration.trimEnd()
  const eol = text.includes('\r\n') ? '\r\n' : '\n'
  const head = text.slice(0, start + LICENSES_START.length)
  const tail = text.slice(end)
  return `${head}${eol}${body.replace(/\r?\n/g, eol)}${eol}${tail}`
}

const PY_META_SCRIPT = `
import json, sys
import importlib.metadata as md

names = json.load(sys.stdin)
out = {}
for name in names:
    try:
        dist = md.distribution(name)
    except md.PackageNotFoundError:
        out[name] = None
        continue
    meta = dist.metadata
    urls = []
    for raw in meta.get_all("Project-URL") or []:
        label, _, url = raw.partition(",")
        urls.append({"label": label.strip(), "url": url.strip()})
    out[name] = {
        "installedVersion": dist.version,
        "license": meta.get("License") or None,
        "licenseExpression": meta.get("License-Expression") or None,
        "homePage": meta.get("Home-page") or None,
        "projectUrls": urls,
        "classifiers": [c for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")],
    }
print(json.dumps(out, ensure_ascii=False))
`

function findPython() {
  const candidates = [
    resolve(REPO_ROOT, 'backend/.venv/Scripts/python.exe'),
    resolve(REPO_ROOT, 'backend/.venv/bin/python'),
  ]
  return candidates.find((p) => existsSync(p)) ?? null
}

function readPyMeta(names, python) {
  if (!python || !names.length) return { meta: {}, error: python ? null : '未找到 backend/.venv 解释器' }
  const result = spawnSync(python, ['-X', 'utf8', '-c', PY_META_SCRIPT], {
    input: JSON.stringify(names),
    encoding: 'utf8',
    maxBuffer: 8 * 1024 * 1024,
  })
  if (result.status !== 0) {
    return { meta: {}, error: (result.stderr || result.error?.message || 'python 执行失败').trim() }
  }
  try {
    return { meta: JSON.parse(result.stdout), error: null }
  } catch (e) {
    return { meta: {}, error: `元数据 JSON 解析失败：${e.message}` }
  }
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function main() {
  const npmManifest = readJson(join(WEB_ROOT, 'package.json'))
  const npmRanges = { ...npmManifest.dependencies, ...npmManifest.devDependencies }
  const npm = Object.entries(npmRanges).map(([name, version]) => {
    let pkg = null
    try {
      pkg = readJson(join(WEB_ROOT, 'node_modules', name, 'package.json'))
    } catch {
      // 未安装时保留条目：许可标未知，仓库退到 npmjs 页面
    }
    return { name, version, pkg }
  })

  const py = parseRequirements(readFileSync(join(REPO_ROOT, 'backend/requirements.txt'), 'utf8'))
  const python = findPython()
  const { meta, error } = readPyMeta(
    py.map((dep) => dep.name),
    python,
  )

  const entries = buildEntries({
    npm,
    py: py.map((dep) => ({ ...dep, meta: meta[dep.name] ?? null })),
  })
  const expected = npm.length + py.length
  if (entries.length !== expected) {
    throw new Error(`生成条数不符：实际 ${entries.length}，应为 npm ${npm.length} + pip ${py.length}`)
  }

  const aboutPath = join(WEB_ROOT, 'src/views/about/About.vue')
  const about = readFileSync(aboutPath, 'utf8')
  writeFileSync(aboutPath, replaceLicenseBlock(about, renderEntries(entries)), 'utf8')

  console.log(`[gen:licenses] npm ${npm.length} 个 + backend/requirements.txt 去重后 ${py.length} 个 = ${entries.length} 条`)
  if (error) console.warn(`[gen:licenses] 后端元数据不可用（${error}）：pip 条目的许可将标为未知`)
  const unknown = entries.filter((row) => row.license === UNKNOWN_LICENSE)
  if (unknown.length) {
    console.warn(`[gen:licenses] 许可未知（保留条目，需人工确认）：${unknown.map((row) => row.name).join(', ')}`)
  }
  console.log(`[gen:licenses] 已写入 ${aboutPath}`)
  console.log('[gen:licenses] 生成后需重跑 test:nav：npm run validate:nav && npm run test:nav')
}

const invoked = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invoked) {
  try {
    main()
  } catch (e) {
    console.error(`[gen:licenses] 失败：${e.message}`)
    process.exitCode = 1
  }
}
