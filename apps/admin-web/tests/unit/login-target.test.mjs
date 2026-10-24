/**
 * 登录跳转目标单元测试（T02614）
 *
 * 401 有两条落地路径（前台立即跳 / 隐藏期丢弃后恢复补跳），它们共用 loginTarget。
 * 这里锁住三件只在纯函数里才看得清的事：
 * 1) 生产前缀 `/news` 必须留在登录页地址上、且**不能**留在 `?redirect=` 里
 *    （登录页按 route.fullPath 口径消费 redirect，带前缀会拼成 /news/news/...）；
 * 2) PC / 移动按当前路径判定，隐藏期补跳与前台跳转落到同一端；
 * 3) 「已在登录页」必须是显式信号——补跳回调据此 no-op，否则登录失败时页面会被自己刷走（FR-UX-304）。
 *
 * e2e（tests/session-expiry-restore.spec.js）跑的是 dev base ''，覆盖不到生产前缀；
 * 两种 base 都在这里断，才不至于「dev 绿、上线跳错地址」。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/login-target.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { describe, it } from 'node:test'

const LOGIN_TARGET_URL = new URL('../../src/utils/loginTarget.js', import.meta.url).href

// 源码顶层不读 import.meta.env（只在调用时读），node 下也照常可跑；
// 但为了让用例能分别模拟 dev('')/生产('/news') 两种 base，仍按 feedback-queue 的接法替换成可控全局。
globalThis.__loginEnv__ = { BASE_URL: '/' }

registerHooks({
  load(url, context, nextLoad) {
    if (url === LOGIN_TARGET_URL) {
      const source = readFileSync(new URL(url), 'utf8').replaceAll(
        'import.meta.env',
        'globalThis.__loginEnv__',
      )
      return { url, format: 'module', source, shortCircuit: true }
    }
    return nextLoad(url, context)
  },
})

const { resolveLoginTarget } = await import(LOGIN_TARGET_URL)

/** 只提供 resolveLoginTarget 真正读取的两个字段 */
const at = (pathname, search = '') => ({ pathname, search })

describe('resolveLoginTarget', () => {
  it('dev（base ""）PC 页：跳 /login，redirect 是去掉前缀的应用内路径', () => {
    globalThis.__loginEnv__ = { BASE_URL: '/' }
    const t = resolveLoginTarget(at('/workflows'))
    assert.equal(t.isMobile, false)
    assert.equal(t.loginPath, '/login')
    assert.equal(t.onLoginPage, false)
    assert.equal(t.appPath, '/workflows')
    assert.equal(t.redirectUrl, '/login?redirect=%2Fworkflows')
  })

  it('生产（base /news）PC 页：登录页保留 /news 前缀，redirect 不带前缀', () => {
    globalThis.__loginEnv__ = { BASE_URL: '/news/' }
    const t = resolveLoginTarget(at('/news/workflows', '?status=success&page=2'))
    assert.equal(t.loginPath, '/news/login')
    assert.equal(t.onLoginPage, false)
    // 回归点：曾把整个 pathname 塞进 redirect，登录后变成 /news/news/workflows
    assert.equal(t.appPath, '/workflows?status=success&page=2')
    assert.equal(t.redirectUrl, `/news/login?redirect=${encodeURIComponent('/workflows?status=success&page=2')}`)
  })

  it('生产移动页：按路径判定为移动端，跳 /news/m/login', () => {
    globalThis.__loginEnv__ = { BASE_URL: '/news' }
    const t = resolveLoginTarget(at('/news/m/message'))
    assert.equal(t.isMobile, true)
    assert.equal(t.loginPath, '/news/m/login')
    assert.equal(t.appPath, '/m/message')
    assert.equal(t.redirectUrl, '/news/m/login?redirect=%2Fm%2Fmessage')
  })

  it('已在登录页时给出显式信号（PC / 移动两种 base 都要认得）', () => {
    globalThis.__loginEnv__ = { BASE_URL: '/news' }
    assert.equal(resolveLoginTarget(at('/news/login')).onLoginPage, true)
    assert.equal(resolveLoginTarget(at('/news/m/login')).onLoginPage, true)
    // 只认末段，避免把 /news/login-help 之类误判成登录页
    assert.equal(resolveLoginTarget(at('/news/login-help')).onLoginPage, false)
  })

  it('根路径不能把 redirect 拼成空串', () => {
    globalThis.__loginEnv__ = { BASE_URL: '/' }
    const t = resolveLoginTarget(at('/'))
    assert.equal(t.appPath, '/')
    assert.equal(t.redirectUrl, '/login?redirect=%2F')
  })
})
