/**
 * T02544 切片 6：C7 / F22 / I39 / I59 / H11 / I6 / M66
 *
 * 评审口径（T02336 §4.3）：
 * - C7  需修订：列表「默认」看不出触发时刻，收成常量并显示「默认 05:00」；
 * - F22 确认：引导文案写「会话来源」，实际是每 90 秒刷新模型列表；
 * - I39 需修订：只增高移动端反馈队列 tab（34px → 44px），不改宽度；
 * - I59 需修订：跨端重定向本身正确，改为「提示 + 带 mode 的回原页面链接」；
 * - H11 确认：COS 上传只收单文件且只弹一条 toast，要批量 + 成功/失败汇总 + 失败清单；
 * - I6  确认：处理完一条后整批重建，展开态/详情/滚动位置丢失；
 * - M66 需修订：日志清理预览未排除活动分片，修法是预览与执行都跳过它。
 *
 * 这里既跑纯函数（通知存取、列表合并），也钉住接线（组件挂载/守卫顺序/UI 文案），
 * 因为这几处「逻辑对但没接上」恰恰是复核最容易漏的形态。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { DEFAULT_CRON_HOUR, DEFAULT_CRON_LABEL } from '../../src/constants/schedule.js'
import {
  CROSS_END_NOTICE_KEY,
  buildCrossEndNotice,
  clearCrossEndNotice,
  crossEndNoticeLink,
  parseCrossEndNotice,
  readCrossEndNotice,
  saveCrossEndNotice,
  shouldClearCrossEndNotice,
} from '../../src/utils/crossEndNotice.js'
import { decorateReviewRow, mergeReviewRows } from '../../src/utils/reviewListState.js'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf-8')
const SRC = '../../src/'

const channelVue = read(`${SRC}views/channel/ChannelManagement.vue`)
const guideConfig = read(`${SRC}guide/guideConfig.js`)
const knowledgeQa = read(`${SRC}views/ai/KnowledgeQA.vue`)
const manageFeedback = read(`${SRC}views/mobile/ManageFeedback.vue`)
const routerJs = read(`${SRC}router/index.js`)
const noticeVue = read(`${SRC}components/CrossEndNotice.vue`)
const layoutVue = read(`${SRC}layouts/Layout.vue`)
const mobileLayout = read(`${SRC}layouts/MobileLayout.vue`)
const cosFiles = read(`${SRC}views/cos/CosFiles.vue`)
const reviewList = read(`${SRC}views/mobile/ReviewList.vue`)
const maintenanceVue = read(`${SRC}views/maintenance/Maintenance.vue`)
const maintenancePy = repoFile('backend/app/services/maintenance_service.py')

/** 最小 sessionStorage 替身（含「不可用」形态） */
function memoryStorage(initial = {}) {
  const map = new Map(Object.entries(initial))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    keys: () => [...map.keys()],
  }
}

test('C7：默认触发时刻只有一份常量，且与后端 WORKFLOW_CRON_HOUR 默认值一致', () => {
  assert.equal(DEFAULT_CRON_HOUR, 5)
  assert.equal(DEFAULT_CRON_LABEL, '05:00')

  const configPy = repoFile('backend/app/config.py')
  const m = /WORKFLOW_CRON_HOUR:\s*int\s*=\s*(\d+)/.exec(configPy)
  assert.ok(m, '后端 config.py 必须仍以字面量给出 WORKFLOW_CRON_HOUR 默认值')
  assert.equal(Number(m[1]), DEFAULT_CRON_HOUR, '前端常量与后端默认值已漂移')

  // 两处展示都必须走常量；列表也要显示时刻，不能只剩「默认」两个字
  assert.match(channelVue, /import \{ DEFAULT_CRON_LABEL \} from '\.\.\/\.\.\/constants\/schedule'/)
  assert.match(channelVue, /默认 \{\{ DEFAULT_CRON_LABEL \}\}/)
  assert.match(channelVue, /全局 cron（\{\{ DEFAULT_CRON_LABEL \}\}）/)
  assert.doesNotMatch(channelVue, /全局 cron（05:00）/)
})

test('F22：智能助手引导描述与真实行为一致（90 秒刷模型，没有「会话来源」）', () => {
  assert.match(guideConfig, /每 90 秒重新拉取模型列表/)
  // 注释里可以解释旧文案，但步骤描述（d:）里不许再出现
  assert.doesNotMatch(guideConfig, /d: '[^']*会话来源/)
  // 描述里的数字来自真实实现，不是另写一份
  assert.match(knowledgeQa, /const AUTO_REFRESH_MS = 90_000/)
  assert.match(knowledgeQa, /fetchModels\(\{ silent: true \}\), AUTO_REFRESH_MS/)
  assert.match(knowledgeQa, /data-guide="assistant-page"/)
})

test('I39：移动端反馈队列 tab 触控高度 44px', () => {
  const block = /\.m-fb__tab \{[\s\S]*?\}/.exec(manageFeedback)
  assert.ok(block, '找不到 .m-fb__tab 规则')
  const m = /height:\s*(\d+)px/.exec(block[0])
  assert.ok(m, '.m-fb__tab 必须声明固定高度')
  assert.equal(Number(m[1]), 44)
})

test('I59：跨端提示只接受站内路径，回链显式带原页面所属端', () => {
  const toMobile = buildCrossEndNotice('/review', { tab: 'approved' }, '/m/review')
  assert.deepEqual(toMobile, {
    fromPath: '/review',
    fromQuery: { tab: 'approved' },
    landedPath: '/m/review',
    mode: 'desktop',
  })
  assert.deepEqual(crossEndNoticeLink(toMobile), {
    path: '/review',
    query: { tab: 'approved', mode: 'desktop' },
  })

  const toDesktop = buildCrossEndNotice('/m/manage/queue', { status: 'failed' }, '/queue')
  assert.equal(toDesktop.mode, 'mobile')
  assert.deepEqual(crossEndNoticeLink(toDesktop).query, { status: 'failed', mode: 'mobile' })

  // 开放重定向入口：协议相对/带 scheme 的地址一律不生成提示
  assert.equal(buildCrossEndNotice('//evil.com', {}, '/review'), null)
  assert.equal(buildCrossEndNotice('https://evil.com', {}, '/review'), null)
  assert.equal(buildCrossEndNotice('', {}, '/review'), null)
})

test('I59：存储内容损坏不报错、不复活；导航离开落点即失效', () => {
  const storage = memoryStorage()
  const notice = buildCrossEndNotice('/review', { tab: 'approved' }, '/m/review')
  saveCrossEndNotice(storage, notice)
  assert.deepEqual(storage.keys(), [CROSS_END_NOTICE_KEY])
  assert.deepEqual(readCrossEndNotice(storage), notice)

  storage.setItem(CROSS_END_NOTICE_KEY, '{not json')
  assert.equal(readCrossEndNotice(storage), null)
  storage.setItem(CROSS_END_NOTICE_KEY, JSON.stringify({ fromPath: '//evil.com' }))
  assert.equal(readCrossEndNotice(storage), null)
  storage.setItem(CROSS_END_NOTICE_KEY, JSON.stringify({ fromPath: '/review' }))
  assert.equal(parseCrossEndNotice(storage.getItem(CROSS_END_NOTICE_KEY)).mode, 'desktop')

  // sessionStorage 不可用（隐私模式）时 set/get/clear 都不抛
  const broken = { getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') }, removeItem() { throw new Error('denied') } }
  assert.doesNotThrow(() => saveCrossEndNotice(broken, notice))
  assert.equal(readCrossEndNotice(broken), null)
  assert.doesNotThrow(() => clearCrossEndNotice(broken))

  assert.equal(shouldClearCrossEndNotice(notice, '/m/review'), false, '落点页自己换 query 不该清掉提示')
  assert.equal(shouldClearCrossEndNotice(notice, '/review'), true)
  assert.equal(shouldClearCrossEndNotice(null, '/review'), false)

  clearCrossEndNotice(storage)
  assert.equal(readCrossEndNotice(storage), null)
})

test('I59：守卫先落 mode 再判端（否则回链会被再切回去），两边布局都挂提示', () => {
  // 顺序即行为：先 setForcedMode 后 resolveMode
  assert.ok(routerJs.includes('const qMode = to.query.mode'))
  const setIdx = routerJs.indexOf('setForcedMode(qMode)')
  const resolveIdx = routerJs.indexOf('const wantMobile = resolveMode()')
  assert.ok(setIdx > -1 && resolveIdx > setIdx, 'guard 必须先应用 mode= 再解析端归属')

  assert.match(
    routerJs,
    /saveCrossEndNotice\(\s*sessionStorage,\s*buildCrossEndNotice\(to\.path, to\.query, target\.path\),?\s*\)/,
  )
  // 离开落点清掉陈旧提示（点「仍要查看原页面」也走这条）
  assert.match(routerJs, /const staleNotice = readCrossEndNotice\(sessionStorage\)/)
  assert.match(routerJs, /shouldClearCrossEndNotice\(staleNotice, to\.path\)\) clearCrossEndNotice\(sessionStorage\)/)

  assert.match(noticeVue, /crossEndNoticeLink\(notice\.value\)/)
  assert.match(noticeVue, /data-testid="cross-end-notice-link"/)
  assert.match(noticeVue, /readCrossEndNotice\(sessionStorage\)/)
  for (const layout of [layoutVue, mobileLayout]) {
    assert.match(layout, /import CrossEndNotice from '\.\.\/components\/CrossEndNotice\.vue'/)
    assert.match(layout, /<CrossEndNotice \/>/)
  }
})

test('H11：COS 上传支持多选，批量给出成功/失败汇总与失败清单', () => {
  assert.match(cosFiles, /type="file"\s*\n\s*multiple/)
  assert.match(cosFiles, /Array\.from\(e\.target\.files \|\| \[\]\)/)
  assert.match(cosFiles, /async function uploadOne\(file, \{ notify = false \} = \{\}\)/)
  // 单文件仍走逐条提示（cos-upload-rollback e2e 依赖这些文案）
  assert.match(cosFiles, /if \(picked\.length === 1\) \{\s*\n\s*const r = await uploadOne\(picked\[0\], \{ notify: true \}\)/)
  assert.match(cosFiles, /已上传 \$\{file\.name\}/)
  assert.match(cosFiles, /旧文件已备份至 \$\{result\.backup_key\}/)
  // 批量：汇总数据 + 页内清单，不靠连续 toast
  assert.match(cosFiles, /uploadReport\.value = \{ ok: okCount, failed, canceled \}/)
  assert.match(cosFiles, /本次上传：成功 \$\{uploadReport\.ok\} 个，失败 \$\{uploadReport\.failed\.length\} 个/)
  assert.match(cosFiles, /v-for="f in uploadReport\.failed"/)
  assert.match(cosFiles, /data-guide="cos-upload-report"/)
})

test('I6：重载按 id 复用旧行对象，展开态/详情/音频就地保留', () => {
  const prev = [
    {
      id: 1,
      title: '旧标题',
      expanded: true,
      detail: { script: '长文' },
      audioSrc: 'blob:item-1',
      audioToken: 3,
      busy: false,
    },
  ]
  const prevRef = prev[0]
  const merged = mergeReviewRows(prev, [{ id: 1, title: '新标题' }, { id: 2, title: '新条目' }])

  assert.equal(merged[0], prevRef, '命中的行必须是旧对象本身（v-for 才不重挂载）')
  assert.equal(merged[0].title, '新标题', '服务端字段要覆盖上去')
  assert.equal(merged[0].expanded, true)
  assert.equal(merged[0].detail.script, '长文')
  assert.equal(merged[0].audioSrc, 'blob:item-1')
  assert.equal(merged[0].audioToken, 3)

  assert.deepEqual(merged[1], decorateReviewRow({ id: 2, title: '新条目' }))
  assert.equal(merged[1].expanded, false)
  assert.equal(merged[1].detail, null)

  // id 类型不一致（字符串/数字）也要认成同一行，否则 JSON 边界一变就全量重置
  const [sameId] = mergeReviewRows([{ id: '7', expanded: true }], [{ id: 7 }])
  assert.equal(sameId.expanded, true)

  // 接线：处理完一条后保留状态 + 滚回原来的位置
  assert.match(reviewList, /const scroller = keepState \? document\.querySelector\('\.m-content'\) : null/)
  assert.match(reviewList, /scroller\.scrollTop = scrollTop/)
  assert.match(reviewList, /const items = mergeReviewRows\(prevRows, data\.list \|\| \[\]\)/)
  assert.equal(
    reviewList.match(/await load\(\{ keepState: true \}\)/g)?.length,
    2,
    '通过/驳回与一键审批后的重载都要保留状态',
  )
  assert.doesNotMatch(reviewList, /const items = \(data\.list \|\| \[\]\)\.map\(/)
  assert.match(mobileLayout, /\.m-content \{[^}]*overflow-y: auto/)
})

test('M66：日志清理在预览与执行两侧都跳过活动分片，界面把规则写明', () => {
  assert.match(maintenancePy, /ACTIVE_LOG_GLOB = "MorningBrief_\*\.log"/)
  assert.match(maintenancePy, /active_log = self\._active_log_file\(log_dir\)/)
  assert.match(maintenancePy, /if entry\.name == active_name:\s*\n\s*continue/)
  // 判定与 logging_setup 的「保留最新那个」同口径：mtime 最新 + 名字稳定排序
  assert.match(maintenancePy, /return max\(shards, key=_key\)/)
  assert.match(maintenanceVue, /正在写入的最新日志文件（MorningBrief_\*\.log）不会被清理/)
})
