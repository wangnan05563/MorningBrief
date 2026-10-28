/**
 * T02544（REQ-008 中危归并）· D 组抽样修订的接线门禁
 *
 * 覆盖评审报告 §4.3 的 6 条中危：D6 / D20 / D38 / D53 / D65 / D83。
 * 这里只钉「页面确实接上了修法」，断言强度与 T02534 的委托门一致：
 * - 文本/顺序断言杀得动「改回旧写法」「把错误吞回 await」这类回退；
 * - 真实渲染行为由 isolated backend + 浏览器走查负责（result_T02544.md）。
 *
 * D65 是「修订后修法＝仅记录日志」——评审已否掉原建议的 RSS 告警配置，
 * 后端现状即符合，因此本文件只锁住「不得反过来声称已支持 RSS 告警」。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const SRC = '../../src/views/'

const adMaterials = read(`${SRC}ad/AdMaterials.vue`)
const adPlacements = read(`${SRC}ad/AdPlacements.vue`)
const adSchedule = read(`${SRC}ad/AdSchedule.vue`)
const statsOverview = read(`${SRC}stats/StatsOverview.vue`)

test('D6：素材列表接服务端关键词检索，并把条件变化重置到第 1 页', () => {
  assert.match(adMaterials, /keyword:\s*keyword\.value\.trim\(\) \|\| undefined/, '列表请求必须带 keyword')
  assert.match(adMaterials, /function onSearch\(\)\s*\{[\s\S]*?page\.value = 1/, '检索必须回到第 1 页')
  assert.match(adMaterials, /data-guide="ads-materials-search"/, '检索入口必须在页面上')
})

test('D6：补创建时间列，取接口已下发的 created_at', () => {
  assert.match(adMaterials, /label="创建时间"/)
  assert.match(adMaterials, /formatTime\(row\.created_at\)/)
})

test('D83：素材空态不再指向不存在的「右上角」按钮', () => {
  assert.match(adMaterials, /点击左上角「新增素材」/)
  assert.doesNotMatch(adMaterials, /点击右上角「新增素材」/)
})

test('D83：投放规则空态的按钮名与位置与工具栏一致', () => {
  assert.match(adPlacements, /点击左上角「新建投放」/)
  assert.doesNotMatch(adPlacements, /点击右上角「新增规则」/)
})

test('D83：排期整月为空时给出明确空态而不是满屏「—」', () => {
  assert.match(adSchedule, /hasMonthData/)
  assert.match(adSchedule, /暂无排期/)
  // 「—」在日历里的语义是「该日无排期」，空态必须由数据判断，不能按破折号数量猜
  assert.match(adSchedule, /Object\.keys\(scheduleMap\.value\)\.some/)
})

test('D20：素材下拉失败必须落在弹窗内可见、可重试，而不是让弹窗打不开', () => {
  // 失败要捕获并记录，不能把异常抛回 openCreateDialog
  assert.match(adPlacements, /materialLoadError\.value = e\?\.message \|\| '素材列表加载失败'/)
  assert.match(adPlacements, /data-guide="ads-material-load-error"/)
  assert.match(adPlacements, /@click="fetchMaterials">重试/)
  // 弹窗必须先打开：dialogVisible 出现在 fetchMaterials() 之前
  const openDialog = adPlacements.slice(adPlacements.indexOf('async function openCreateDialog'))
  const bodyEnd = openDialog.indexOf('\n}')
  const body = openDialog.slice(0, bodyEnd)
  assert.ok(body.indexOf('dialogVisible.value = true') < body.indexOf('fetchMaterials()'), '弹窗应先于素材请求打开')
  assert.doesNotMatch(body, /await fetchMaterials\(\)/, '素材请求不得阻塞弹窗打开')
})

test('D38：趋势请求有独立加载态，不再只靠整页 spinner', () => {
  assert.match(statsOverview, /const trendLoading = ref\(false\)/)
  assert.match(statsOverview, /v-loading="trendLoading && !trendError"/)
  assert.match(statsOverview, /trendLoading\.value = false/, '必须在 finally 收尾')
})

test('D53：趋势指标与区间持久化，并在读取时校验取值', () => {
  assert.match(statsOverview, /TREND_PREF_KEY/)
  assert.match(statsOverview, /localStorage\.getItem\(TREND_PREF_KEY\)/)
  assert.match(statsOverview, /localStorage\.setItem\(\s*TREND_PREF_KEY/)
  assert.match(statsOverview, /\['dau', 'play_count', 'completion_rate'\]\.includes\(trendPref\.metric\)/)
  assert.match(statsOverview, /\['7d', '30d'\]\.includes\(trendPref\.range\)/)
  // 切换即持久化：两个 radio group 都必须走同一个处理函数
  assert.equal((statsOverview.match(/@change="onTrendParamChange"/g) || []).length, 2)
})

test('D65：RSS 健康度按修订后修法只落日志，不宣称接入了通知配置', () => {
  const statsRouter = read('../../../../backend/app/routers/admin/stats.py')
  const rssDoc = statsRouter.slice(statsRouter.indexOf('def get_rss_health'))
  assert.match(rssDoc, /自动 WARNING 日志/)
  assert.doesNotMatch(rssDoc.slice(0, rssDoc.indexOf('"""', 10)), /通知/)
})
