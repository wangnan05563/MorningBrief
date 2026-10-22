/**
 * M5「指标单位与口径说错话」追溯门禁（T02538）
 *
 * 11 条里 5 条（D33/D34/D35/D68/D23）已由 T02506~T02508、T02491 先行修掉，
 * 这里不再重写实现，只钉住「修好的口径不许退回」；其余 4 条是本单新修的：
 * - D39 广告曝光是推算值（play_count × 3），页面必须自证，不能只写在注释里；
 * - D46 两个页面的「RSS 源数量」是两种口径，标签必须写归属；
 * - M81 帮助文档必须与 ParamCalculator 的真实输入范围/基线一一对应；
 * - C114 同一素材在素材库与工作流详情里必须同名、同字段、同状态字典。
 *
 * 门禁分三类：
 * 1) 双向核对（强）：文档里的数字从组件源码解析后回比，两边各写一份时必被抓；
 * 2) 契约核对（中）：后端取值来源（channel.rss_sources / enabled 字段）与页面说法互证；
 * 3) 反退回（弱）：旧说法（330 WPM、必填 URL、hardcode 状态选项）不得复现。
 *
 * 真实渲染由 tests/m5-claims-are-true.spec.js（真实 Chrome）负责。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { statsMetricMeta } from '../helpers/statsMeta.js'
import { MATERIAL_STATUS, enumLabel } from '../../src/constants/enums.js'

function stripComments(text) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((line) => !/^\s*(\/\/|#)/.test(line))
    .join('\n')
}

const read = (rel) => stripComments(readFileSync(new URL(rel, import.meta.url), 'utf-8'))
const SRC = '../../src/'
const BACKEND = '../../../../backend/app/'

const STATS_VIEW = read(`${SRC}views/stats/StatsOverview.vue`)
const CHANNEL_VIEW = read(`${SRC}views/stats/ChannelHealth.vue`)
const RSS_VIEW = read(`${SRC}views/stats/RssHealth.vue`)
const HELP_VIEW = read(`${SRC}views/help/Help.vue`)
const CALC_VIEW = read(`${SRC}views/tools/ParamCalculator.vue`)
const LIBRARY_VIEW = read(`${SRC}views/channel/MaterialLibrary.vue`)
const WORKFLOW_VIEW = read(`${SRC}views/workflow/WorkflowDetail.vue`)
const STATS_SERVICE = read(`${BACKEND}services/stats_service.py`)
const AD_SERVICE = read(`${BACKEND}services/ad_service.py`)
const AD_SCHEDULE_VIEW = read(`${SRC}views/ad/AdSchedule.vue`)
const LLM_VIEW = read(`${SRC}views/stats/LlmMetrics.vue`)

function slice(src, startMarker, endMarkers, label = startMarker) {
  const start = src.indexOf(startMarker)
  assert.notEqual(start, -1, `找不到 ${label} 的起点：${startMarker}`)
  let end = src.length
  for (const raw of endMarkers) {
    const marker = raw.replace(/^\r?\n/, '')
    const idx = src.indexOf(marker, start + startMarker.length)
    if (idx !== -1 && idx < end) end = idx
  }
  return src.slice(start, end)
}

test('D39：广告曝光必须自证为推算值，且脚注随卡片渲染', () => {
  const meta = statsMetricMeta.ad_impression
  assert.match(meta.label, /推算/, '标签不带「推算」时，截图里就是真实曝光')
  assert.match(meta.note || '', /播放数\s*×\s*3/, '脚注要写明算法')
  assert.match(meta.note || '', /不是真实曝光/, '脚注要写明不是埋点')

  // 页面从 meta 取 note，不能按 key 写死：后端改口径时页面会跟着变
  assert.match(STATS_VIEW, /note:\s*meta\?\.note\s*\|\|\s*''/)
  assert.match(STATS_VIEW, /v-if="m\.note"[^>]*class="metric-note"/)
  assert.doesNotMatch(STATS_VIEW, /key === 'ad_impression'/, '按 key 写死口径＝第二份事实来源')
})

test('D33：平均收听按秒入库、按分钟展示，换算只发生在 meta', () => {
  const meta = statsMetricMeta.avg_listen_duration
  assert.equal(meta.unit, 'second', '原始值单位必须是秒（PlayLog.duration）')
  assert.equal(meta.display.unit, '分钟')
  assert.ok(Math.abs(meta.display.factor - 1 / 60) < 1e-9, '秒→分钟的因子必须是 1/60')

  // 后端取 AVG(duration)，模型注释与元数据说的必须是同一件事
  assert.match(STATS_SERVICE, /func\.avg\(PlayLog\.duration\)/)
  assert.doesNotMatch(STATS_VIEW, /平均收听/, '页面自己写指标名就会与 meta 漂移')
  assert.doesNotMatch(STATS_VIEW, /\(分钟\)/, '页面写死「(分钟)」＝D33 回退')
})

test('D34：卡片与趋势图同一刻度，换算只走 metricNumber', () => {
  assert.match(STATS_VIEW, /metricNumber\(v,\s*trendMeta\.value\)/, '趋势点必须按 meta 换算')
  assert.match(STATS_VIEW, /axisTitle\s*=\s*computed\(\(\)\s*=>\s*metricLabel\(trendMeta\.value\)\)/)
  // 页面里出现裸 *100 就是把 ratio 换算复制了一份
  assert.doesNotMatch(STATS_VIEW, /\*\s*100\b/)
  assert.equal(statsMetricMeta.completion_rate.display.factor, 100)
})

test('D35：无数据的日子是 null 断点，不是 0 折线', () => {
  const trend = slice(
    STATS_SERVICE,
    'async def get_trend(',
    ['    async def get_channel_health('],
    'StatsService.get_trend',
  )
  assert.match(trend, /db_map\.get\(d\.isoformat\(\)\)/, '缺日必须保留 null')
  assert.doesNotMatch(trend, /db_map\.get\([^)]*\)\s*or\s*0/, '缺日补 0 就是「断崖归零」回退')
  assert.match(STATS_VIEW, /v !== null && v !== undefined/, '空态判定要看数据点而不是 dates 长度')
  assert.match(STATS_VIEW, /暂无趋势数据/)
})

test('D68：LLM 指标页标明「进程内累计、重启清零」的起点', () => {
  // 口径文案收敛在 utils/scope.js：页面只负责把 started_at / pid 交给它
  const scope = read(`${SRC}utils/scope.js`)
  assert.match(scope, /累计/)
  assert.match(scope, /重启/)
  assert.match(LLM_VIEW, /cumulativeScopeText\(/)
  assert.match(LLM_VIEW, /startedAt:\s*metrics\.value\.started_at/)
  assert.match(LLM_VIEW, /pid:\s*metrics\.value\.pid/)
  // 后端必须真的回传起点，否则页面只能拿当前时间冒充
  const router = read(`${BACKEND}routers/admin/stats.py`)
  assert.match(router, /runtime_fields\(\)/)
})

test('D23：停用的投放仍会出现在日历上，但必须标明「已停用」', () => {
  const schedule = slice(
    AD_SERVICE,
    'async def get_schedule(',
    ['    async def get_active_placements('],
    'AdService.get_schedule',
  )
  // 排期视图不过滤 enabled：停用规则也要可见（否则运营以为它被删了/照播了）
  assert.doesNotMatch(schedule, /AdPlacement\.enabled/, '排期按 enabled 过滤会让停用规则凭空消失')
  assert.match(schedule, /"enabled":\s*p\.enabled/, '必须下发 enabled，前端才能标灰')
  // T02602 起状态改由服务端派生，四态文案收敛在 utils/placementStatus.js；
  // 日历仍须对非生效态加标签，「已停用」不能只剩一个灰色格子
  assert.match(AD_SCHEDULE_VIEW, /slotStatusTag/)
  assert.match(read(`${SRC}utils/placementStatus.js`), /disabled: \{ label: '已停用'/)
})

test('D46：频道卡片数的是本频道配置，RSS 页数的是全局清单', () => {
  // 取值来源：频道自己的 rss_sources 列，而非 rss.yaml 全局清单。
  // 直接读整个 stats_service，比截函数更严：这个文件根本不该出现 rss.yaml。
  assert.match(STATS_SERVICE, /ch\.rss_sources/)
  assert.doesNotMatch(STATS_SERVICE, /rss\.yaml|global_sources/, '频道卡片不能改数全局清单')

  assert.match(CHANNEL_VIEW, /本频道已配源（个）/, '标签必须写清「本频道」')
  assert.match(CHANNEL_VIEW, /RSS 源状态/, 'tooltip 要把「看全局去哪儿」指出来')
  assert.match(RSS_VIEW, /全局源清单总数/, 'RSS 页的同名卡片要写清是全局')
  assert.match(RSS_VIEW, /rss\.yaml/)
})

test('M81：帮助文档的每个数字都能在 ParamCalculator 里找到出处', () => {
  const helpCalc = slice(HELP_VIEW, "title: '参数计算器'", ["id: 'db-admin'"], 'Help 参数计算器章节')

  // 反退回：旧文档的三处硬伤
  assert.doesNotMatch(helpCalc, /330/, '330 WPM 是旧基线')
  assert.doesNotMatch(helpCalc, /WPM/)
  assert.doesNotMatch(helpCalc, /±10%/)
  assert.doesNotMatch(helpCalc, /输入目标时长（分钟）/, '界面单位是秒，不是分钟')
  assert.doesNotMatch(helpCalc, /语速调节建议/, '界面没有这种输出')

  // 基线：从组件常量回比
  const base = CALC_VIEW.match(/BASE_WORDS_PER_MIN\s*=\s*(\d+)/)?.[1]
  assert.equal(base, '210', '组件基线变了，文档必须同步')
  assert.match(helpCalc, /210\s*字\/分/)

  // 范围：从组件模板的真实 min/max 回比，文档写死的区间必须与之相同
  const ranges = [...CALC_VIEW.matchAll(/:min="([\d.]+)"[\s\S]{0,80}?:max="([\d.]+)"/g)]
  assert.ok(ranges.length >= 3, `应能解析出三组范围，实际 ${ranges.length}`)
  const [duration, words, rate] = ranges.map(([, min, max]) => `${min}–${max}`)
  assert.match(helpCalc, new RegExp(`${duration}\\s*秒`), `时长范围文档与组件不一致（组件 ${duration}）`)
  assert.match(helpCalc, new RegExp(`${words}\\s*字`), `字数范围文档与组件不一致（组件 ${words}）`)
  assert.match(helpCalc, new RegExp(`${rate}`), `倍率范围文档与组件不一致（组件 ${rate}）`)

  assert.match(helpCalc, /应用到 AI 配置/, '真实出口是「应用到 AI 配置」')
})

test('C114：素材库与工作流详情是同一实体、同一套字段与状态字典', () => {
  // 1) 状态字典只有一份：两页都走 MATERIAL_STATUS，页面不再自带中文映射
  assert.equal(enumLabel(MATERIAL_STATUS, 'pending'), '待消费')
  assert.match(LIBRARY_VIEW, /statusOptions\s*=\s*enumOptions\(MATERIAL_STATUS\)/)
  assert.match(WORKFLOW_VIEW, /enumOptions\(MATERIAL_STATUS\)/)
  assert.doesNotMatch(LIBRARY_VIEW, /label="待消费"\s+value="pending"/, '页面自带的第二份映射回退了')
  assert.doesNotMatch(WORKFLOW_VIEW, /label="待处理"/, '「待处理」是已淘汰的叫法')

  // 2) 同一字段同名词：category 两页都叫「分类」
  assert.match(LIBRARY_VIEW, /label="分类"/)
  assert.match(WORKFLOW_VIEW, /label="分类"/)
  assert.doesNotMatch(WORKFLOW_VIEW, /label="品类"/, '品类/分类两套叫法会让同一字段像两个概念')

  // 3) 同一实体同一名：工作流面板不再自称「爬虫采集 · 素材」
  assert.match(WORKFLOW_VIEW, /爬虫采集 · 素材库/)
  assert.match(WORKFLOW_VIEW, /与菜单「素材库管理」同一份数据/)

  // 4) URL 不再假装必填：list 录入的 URL 由后端 content_hash 合成，
  //    前端强制填写＝收一个必定被丢弃的字段（素材库页则完全不提供）
  assert.doesNotMatch(WORKFLOW_VIEW, /label="URL" required/, '假必填 URL 回退了')
  assert.doesNotMatch(WORKFLOW_VIEW, /!f\.url/, '前端仍在校验一个不会保存的字段')
  assert.match(WORKFLOW_VIEW, /URL 是去重键，仅展示，不可修改/)
  assert.doesNotMatch(LIBRARY_VIEW, /label="URL"/, '素材库页不编辑去重键，保持一致')

  // 5) 跨页写操作后各自都能刷新
  assert.match(LIBRARY_VIEW, /label="刷新"/)
  assert.match(WORKFLOW_VIEW, /label="刷新"/)
})
