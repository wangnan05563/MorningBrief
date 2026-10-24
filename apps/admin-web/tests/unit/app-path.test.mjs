/**
 * 应用路径前缀单一来源（T02633 / FR-UX-304）
 *
 * 两件事：
 * 1) 纯函数行为：前后端入口、登录页判定、redirect 取值都只从 APP_PREFIX 派生；
 * 2) 门禁：`src` 下除了 utils/appPath.js，任何业务代码都不许再出现 `'/news…'` 字面量。
 *    前缀分散时的代价已经实测过两次（T02498 登录失败横幅被整页刷新、T02614 redirect
 *    在 dev 下多带一层前缀），靠人工 grep 守不住，所以放进单测——改回硬编码即红。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/app-path.test.mjs
 */
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it } from 'node:test'

const SRC = fileURLToPath(new URL('../../src/', import.meta.url))
const ALLOWED = join('utils', 'appPath.js')

const {
  APP_PREFIX,
  APP_BASE,
  withAppPrefix,
  stripAppPrefix,
  appPathOf,
  isLoginPath,
  API_BASE_URL,
  SSE_ENDPOINT,
  READY_PATH,
  API_DOCS_PATH,
} = await import('../../src/utils/appPath.js')

describe('前缀常量', () => {
  it('应用前缀固定为 /news，与 vite base 无关', () => {
    assert.equal(APP_PREFIX, '/news')
    assert.equal(APP_BASE, '/news/')
  })

  it('后端入口都由前缀派生，值不变', () => {
    // vite.config.js 的代理键与后端挂载点都按这些值对齐
    assert.equal(API_BASE_URL, '/news/admin/api/v1')
    assert.equal(SSE_ENDPOINT, '/news/admin/api/v1/events/stream')
    assert.equal(READY_PATH, '/news/api/health/ready')
    assert.equal(API_DOCS_PATH, '/news/docs')
  })
})

describe('withAppPrefix / stripAppPrefix', () => {
  it('补前缀且幂等（DB 里的旧值可能已带前缀）', () => {
    assert.equal(withAppPrefix('/channel-assets/a.png'), '/news/channel-assets/a.png')
    assert.equal(withAppPrefix('/news/channel-assets/a.png'), '/news/channel-assets/a.png')
    assert.equal(withAppPrefix('channel-assets/a.png'), '/news/channel-assets/a.png')
    assert.equal(withAppPrefix('/'), '/news/')
  })

  it('剥前缀回到 vue-router 口径', () => {
    assert.equal(stripAppPrefix('/news/review'), '/review')
    assert.equal(stripAppPrefix('/news/m/message'), '/m/message')
    assert.equal(stripAppPrefix('/news'), '/')
    assert.equal(stripAppPrefix('/news/'), '/')
    // 未带前缀时原样返回：dev 首次导航可能还没被 router 规范化
    assert.equal(stripAppPrefix('/review'), '/review')
    // 不能误吞前缀相同开头的别的路径
    assert.equal(stripAppPrefix('/newsroom'), '/newsroom')
  })

  it('appPathOf 保留 query，供 ?redirect= / ?from= 使用', () => {
    assert.equal(appPathOf('/news/review', '?tab=approved&page=3'), '/review?tab=approved&page=3')
    assert.equal(appPathOf('/news/'), '/')
  })
})

describe('isLoginPath', () => {
  it('只认 PC / 移动登录页，前缀有无都算', () => {
    for (const p of ['/login', '/news/login', '/m/login', '/news/m/login']) {
      assert.equal(isLoginPath(p), true, p)
    }
  })

  it('同前缀开头的其它页面不算登录页', () => {
    for (const p of ['/login-help', '/news/login-help', '/review', '/news/m/message', '/news']) {
      assert.equal(isLoginPath(p), false, p)
    }
  })
})

describe('门禁：业务代码不得再硬编码 /news 前缀', () => {
  const files = []
  const walk = (dir, rel = '') => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const relPath = join(rel, entry.name)
      if (entry.isDirectory()) walk(join(dir, entry.name), relPath)
      else if (/\.(js|vue)$/.test(entry.name)) files.push(relPath)
    }
  }
  walk(SRC)

  it('扫描面覆盖到主要代码目录（防止 walk 失效后空转判绿）', () => {
    assert.ok(files.length > 100, `只扫到 ${files.length} 个文件，扫描器可能坏了`)
    assert.ok(files.some((f) => f.endsWith(join('api', 'index.js'))))
    assert.ok(files.some((f) => f.endsWith(join('router', 'index.js'))))
  })

  it('除 utils/appPath.js 外无前缀字面量（注释除外）', () => {
    const offenders = []
    for (const rel of files) {
      if (rel === ALLOWED) continue
      const lines = readFileSync(join(SRC, rel), 'utf8').split('\n')
      lines.forEach((line, i) => {
        if (!/['"`]\/news(?:['"`/])/.test(line)) return
        const t = line.trim()
        // 注释里说明历史原因/代理约定是允许的，代码里拼接则不行
        if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*') || t.startsWith('<!--')) return
        offenders.push(`${rel}:${i + 1}: ${t}`)
      })
    }
    assert.deepEqual(offenders, [], `前缀请改用 utils/appPath 派生：\n${offenders.join('\n')}`)
  })

  it('路由 history base 也来自同一来源', () => {
    const router = readFileSync(join(SRC, 'router', 'index.js'), 'utf8')
    assert.match(router, /createWebHistory\(APP_BASE\)/)
  })
})
