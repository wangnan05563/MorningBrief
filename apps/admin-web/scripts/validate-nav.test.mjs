/**
 * 校验脚本自身的测试（node --test scripts/）
 *
 * 重点是「它能不能失败」：一个永远返回通过的门禁比没有门禁更糟——
 * 它会让后面的人以为这项检查已经做过了。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { collectFacts, checkFacts } from './validate-nav.mjs'

/** 最小可用事实集：只写用到字段，其余留空 */
function facts(over = {}) {
  return {
    routes: [
      { path: '/', meta: { requiresAuth: true } },
      { path: '/review', meta: { title: '内容审核', icon: 'Document', group: '内容运营' } },
      { path: '/m/home', meta: { title: '首页' } },
    ],
    guideSteps: { '/review': [{ s: ['.top-bar'], t: '审核', d: '' }] },
    groups: [{ name: '内容运营', icon: 'Document' }],
    ariaLabels: new Set(['新增频道']),
    helpIds: ['review'],
    menuRefs: ['内容审核'],
    mobileTargets: [{ from: 'layouts/MobileLayout.vue', to: '/m/home' }],
    aboutHrefs: [],
    commentGroups: ['内容运营'],
    ...over,
  }
}

test('真实仓库通过校验（且抽取到的是真数据，不是空集合）', async () => {
  const f = await collectFacts()
  assert.ok(f.routes.length > 30, `路由数异常：${f.routes.length}`)
  assert.ok(f.ariaLabels.size > 50, `aria-label 数异常：${f.ariaLabels.size}`)
  assert.ok(f.menuRefs.length > 5, '帮助文档菜单引用没抽到，检查项等于没跑')
  assert.ok(f.routes.some((r) => r.path === '/review'), '路由相对路径未正确展开')
  assert.ok(f.routes.some((r) => r.path === '/m/manage/users'), '移动端嵌套路径未正确展开')
  assert.deepEqual(checkFacts(f).errors, [])
})

test('引导指向不存在的路由时报错', () => {
  const r = checkFacts(facts({ guideSteps: { '/nope': [{ s: ['.top-bar'], t: 'x', d: '' }] } }))
  assert.match(r.errors.join('\n'), /引导配置的路由不存在：GUIDE_STEPS\['\/nope'\]/)
})

test('引导选择器命中不存在的 aria-label 时报错（T02500 抓到的真实缺陷形态）', () => {
  const r = checkFacts(
    facts({ guideSteps: { '/review': [{ s: ['[aria-label="不存在的按钮"]', '.top-bar'], t: '触发', d: '' }] } }),
  )
  assert.equal(r.errors.length, 1)
  assert.match(r.errors[0], /不存在的 aria-label/)
})

test('帮助文档指向不存在的菜单时报错', () => {
  const r = checkFacts(facts({ menuRefs: ['不存在的菜单'] }))
  assert.match(r.errors.join('\n'), /帮助文档指向不存在的菜单：「不存在的菜单」/)
})

test('分组漂移（路由有组无配置 / 配置有组无菜单）双向报错', () => {
  const orphanGroup = checkFacts(
    facts({ routes: [{ path: '/review', meta: { title: '内容审核', icon: 'Document', group: '陌生分组' } }] }),
  )
  assert.match(orphanGroup.errors.join('\n'), /没有对应分组配置/)
  const emptyGroup = checkFacts(facts({ groups: [{ name: '空分组', icon: 'Coin' }] }))
  assert.match(emptyGroup.errors.join('\n'), /下没有任何可见菜单项/)
})

test('移动端手写入口与分组注释漂移同样报错', () => {
  const badTo = checkFacts(facts({ mobileTargets: [{ from: 'x.vue', to: '/m/nope' }] }))
  assert.match(badTo.errors.join('\n'), /移动端入口指向不存在的路由/)
  const staleComment = checkFacts(facts({ commentGroups: ['内容运营', '已删除分组'] }))
  assert.match(staleComment.errors.join('\n'), /列出不存在的分组/)
})
