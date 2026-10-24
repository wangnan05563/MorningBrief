/**
 * 登录跳转目标单元测试（T02614 / T02633）
 *
 * 401 有两条落地路径（前台立即跳 / 隐藏期丢弃后恢复补跳），它们共用 loginTarget。
 * 这里锁住三件只在纯函数里才看得清的事：
 * 1) `?redirect=` 必须是 vue-router 口径（不带 /news 前缀），登录页才能直接 router.push；
 *    曾经按 vite base 推导，dev base='/' 使 redirect 带前缀，登录后落到 /news/news/...；
 * 2) PC / 移动按当前路径判定，补跳与前台跳转落到同一端；
 * 3) 「已在登录页」必须是显式信号——补跳回调据此 no-op，否则登录失败时页面会被自己刷走（FR-UX-304）。
 *
 * dev 与生产对 `resolveLoginTarget` 的输入只差地址栏是否带 /news 前缀，两种形式都在这里断。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/login-target.test.mjs
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

const { resolveLoginTarget } = await import('../../src/utils/loginTarget.js')

/** 只提供 resolveLoginTarget 真正读取的两个字段 */
const at = (pathname, search = '') => ({ pathname, search })

describe('resolveLoginTarget', () => {
  it('PC 页：跳 /news/login，redirect 是去掉前缀的应用内路径', () => {
    const t = resolveLoginTarget(at('/workflows'))
    assert.equal(t.isMobile, false)
    assert.equal(t.loginPath, '/news/login')
    assert.equal(t.onLoginPage, false)
    assert.equal(t.appPath, '/workflows')
    assert.equal(t.redirectUrl, '/news/login?redirect=%2Fworkflows')
  })

  it('地址栏已规范化（/news/...）：redirect 仍剥掉前缀，登录后不会拼成 /news/news/...', () => {
    const t = resolveLoginTarget(at('/news/workflows', '?status=success&page=2'))
    assert.equal(t.loginPath, '/news/login')
    assert.equal(t.onLoginPage, false)
    // 回归点：曾按 import.meta.env.BASE_URL 推导，dev 下这里会得到 '/news/workflows?...'
    assert.equal(t.appPath, '/workflows?status=success&page=2')
    assert.equal(t.redirectUrl, `/news/login?redirect=${encodeURIComponent('/workflows?status=success&page=2')}`)
  })

  it('前缀有无不影响跳转目标：dev 的 /x 与生产的 /news/x 必须给出同一 URL', () => {
    const raw = resolveLoginTarget(at('/stats/llm-metrics', '?range=7d'))
    const normalized = resolveLoginTarget(at('/news/stats/llm-metrics', '?range=7d'))
    assert.equal(raw.redirectUrl, normalized.redirectUrl)
  })

  it('移动页：按路径判定为移动端，跳 /news/m/login，redirect 保留 /m 路径', () => {
    const t = resolveLoginTarget(at('/news/m/message'))
    assert.equal(t.isMobile, true)
    assert.equal(t.loginPath, '/news/m/login')
    assert.equal(t.appPath, '/m/message')
    assert.equal(t.redirectUrl, '/news/m/login?redirect=%2Fm%2Fmessage')
  })

  it('已在登录页时给出显式信号（PC / 移动都要认得，/login-help 不算）', () => {
    assert.equal(resolveLoginTarget(at('/news/login')).onLoginPage, true)
    assert.equal(resolveLoginTarget(at('/login')).onLoginPage, true)
    assert.equal(resolveLoginTarget(at('/news/m/login')).onLoginPage, true)
    assert.equal(resolveLoginTarget(at('/m/login')).onLoginPage, true)
    assert.equal(resolveLoginTarget(at('/news/login-help')).onLoginPage, false)
  })

  it('根路径不能把 redirect 拼成空串', () => {
    assert.equal(resolveLoginTarget(at('/')).appPath, '/')
    assert.equal(resolveLoginTarget(at('/news/')).redirectUrl, '/news/login?redirect=%2F')
  })
})
