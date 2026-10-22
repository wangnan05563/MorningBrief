/**
 * M6「信息架构与深链」Claims（T02540）
 *
 * 这一类缺陷的共同点：运行时不抛异常，界面却把「没做的事」说成做了，或者把
 * 「能不能点」藏在图标/隐含约定里。所以这里既钉源码写法，也直接调工具函数验证
 * 容错行为（D69 的 null / 字符串回退、E12 的无历史栈返回目标）。
 *
 * 覆盖：B12 试听代理 / D13 投放状态筛选 / D69 率值容错 / E12 返回目标 /
 *      I19 消息深链 / I48 队列 workflow_id / M88 正文搜索 / C68 非法频道 / I27 移动端角标
 *
 * 运行：cd apps/admin-web && node --test tests/unit/m6-ia-claims.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import { metricText, metricValue } from '../../src/utils/format.js'
import { returnTarget } from '../../src/utils/urlState.js'

const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')

const REVIEW_DETAIL = read('../../src/views/review/ReviewDetail.vue')
const AD_PLACEMENTS = read('../../src/views/ad/AdPlacements.vue')
const LLM_METRICS = read('../../src/views/stats/LlmMetrics.vue')
const WORKFLOW_DETAIL = read('../../src/views/workflow/WorkflowDetail.vue')
const MESSAGE = read('../../src/views/mobile/Message.vue')
const MANAGE_QUEUE = read('../../src/views/mobile/ManageQueue.vue')
const HELP = read('../../src/views/help/Help.vue')
const BOOK_POOL = read('../../src/views/channel/BookPool.vue')
const MOBILE_LAYOUT = read('../../src/layouts/MobileLayout.vue')
const AD_SERVICE = read('../../../../backend/app/services/ad_service.py')
const AD_ROUTER = read('../../../../backend/app/routers/admin/ads.py')
const QUEUE_SERVICE = read('../../../../backend/app/services/queue_service.py')

describe('B12 审核详情试听必须走代理并给出失败态', () => {
  it('audio 不再直连 detail.audio_url（私有桶/COS 会 403/CORS）', () => {
    assert.doesNotMatch(REVIEW_DETAIL, /:src="detail\.audio_url"/)
    assert.doesNotMatch(REVIEW_DETAIL, /src="\{\{\s*detail\.audio_url/)
  })

  it('改走 getEpisodeAudioUrl，并有加载态、错误说明与重试', () => {
    // 只匹配函数名会被 import 行蒙混过关，必须钉住「调用」与「调用结果真的进入 src」
    assert.match(REVIEW_DETAIL, /await getEpisodeAudioUrl\(\s*workflowId,\s*remoteUrl\s*\)/)
    assert.match(REVIEW_DETAIL, /audioSrc\.value = blobUrl/)
    assert.match(REVIEW_DETAIL, /v-if="audioLoading"/)
    assert.match(REVIEW_DETAIL, /data-guide="review-audio-error"/)
    assert.match(REVIEW_DETAIL, /@error="onAudioElementError"/)
    assert.match(REVIEW_DETAIL, /label="重试加载"/)
  })

  it('成功后显示时长与「重听」，审核员能确认听到的是这一期', () => {
    assert.match(REVIEW_DETAIL, /时长 \{\{ audioDuration \}\}/)
    assert.match(REVIEW_DETAIL, /label="重听"/)
  })
})

describe('D13 投放规则：状态可见 + 可按启用/停用筛选', () => {
  it('PC 列表现状可读（开关 + 已启用/已停用文字）', () => {
    assert.match(AD_PLACEMENTS, /data-guide="ads-enabled-filter"/)
    assert.match(AD_PLACEMENTS, /已启用/)
    assert.match(AD_PLACEMENTS, /已停用/)
    assert.match(AD_PLACEMENTS, /@update:model-value="\(v\) => handleToggle\(row, v\)"/)
  })

  it('筛选值真的进入请求参数（不是只有下拉框）', () => {
    assert.match(AD_PLACEMENTS, /enabledFilter/)
    assert.match(AD_PLACEMENTS, /enabled:\s*enabledFilter\.value === ''\s*\?\s*undefined\s*:\s*enabledFilter\.value/)
  })

  it('后端 total 与 list 使用同一组 enabled 条件', () => {
    assert.match(AD_SERVICE, /enabled:\s*Optional\[int\] = None/)
    assert.match(AD_SERVICE, /AdPlacement\.enabled == enabled/)
    // 条件必须同时挂在 count_stmt 与 list_stmt 上，否则 total 与列表口径漂移
    const body = AD_SERVICE.slice(AD_SERVICE.indexOf('def list_placements'))
    assert.ok((body.match(/for cond in conditions/g) || []).length >= 2, 'count/list 至少各应用一次条件')
  })

  it('路由层把 enabled 透传给服务（0/1 边界）', () => {
    assert.match(AD_ROUTER, /enabled:\s*Optional\[int\] = Query\(None,\s*ge=0,\s*le=1/)
    assert.match(AD_ROUTER, /list_placements\([^)]*enabled=enabled/s)
  })
})

describe('D69 LLM 指标：null / 字符串不能让整页白屏', () => {
  it('metricValue/metricText 对 null、空串、非数都返回「-」而不是抛错', () => {
    const meta = { display: { unit: '%', factor: 1, precision: 1 } }
    for (const bad of [null, undefined, '', 'abc']) {
      assert.equal(metricValue(bad, meta), '-', `metricValue(${String(bad)}) 应回退为 -`)
      assert.equal(metricText(bad, meta), '-', `metricText(${String(bad)}) 应回退为 -`)
    }
  })

  it('后端把率值给成字符串数字时仍能格式化（不调 toFixed 崩在字符串上）', () => {
    const meta = { display: { unit: '%', factor: 1, precision: 1 } }
    assert.equal(metricValue('42.123', meta), '42.1')
    assert.equal(metricText('42.123', meta), '42.1%')
  })

  it('页面不再直接对 metrics 字段调 toFixed', () => {
    assert.doesNotMatch(LLM_METRICS, /metrics\.value\.\w+\.toFixed\(/)
    assert.match(LLM_METRICS, /metricText\(/)
    assert.match(LLM_METRICS, /metricValue\(/)
  })
})

describe('E12 工作流详情深链返回', () => {
  it('返回目标来自 query/fallback，不再用 router.back()', () => {
    // 文件里保留了「为什么不用 router.back()」的考古注释，判定前先剥注释
    const code = WORKFLOW_DETAIL
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')
    assert.doesNotMatch(code, /router\.back\(/)
    assert.match(WORKFLOW_DETAIL, /returnTarget\(route\.query/)
  })

  it('没有历史栈信息时回落到工作流列表（不是空操作）', () => {
    assert.deepEqual(returnTarget({}, '/workflows'), { path: '/workflows', query: {} })
  })
})

describe('I19 消息可跳转', () => {
  it('明确契约：payload.path 优先，workflow_id 进作用域审核页', () => {
    assert.match(MESSAGE, /payload\.path\.startsWith\('\/'\)/)
    assert.match(MESSAGE, /path: '\/m\/review', query: \{ workflow_id: String\(workflowId\) \}/)
  })

  it('open() 在标记已读后仍会跳转（不再直接 return）', () => {
    const at = MESSAGE.indexOf('async function open(m)')
    assert.notEqual(at, -1)
    const body = MESSAGE.slice(at, MESSAGE.indexOf('\n}', at))
    assert.match(body, /router\.push\(target\)/)
    assert.doesNotMatch(body, /if \(m\.read\) \{\s*\/\/[^\n]*\n\s*return/)
  })
})

describe('I48 队列项显式携带 workflow_id', () => {
  it('后端下发 workflow_id，前端消费它而不是猜测 id 语义', () => {
    assert.match(QUEUE_SERVICE, /"workflow_id": wf\.id/)
    assert.match(MANAGE_QUEUE, /workflow_id:\s*t\.workflow_id \?\? t\.id/)
  })
})

describe('M88 帮助搜索覆盖正文', () => {
  it('搜索 haystack 包含 blocks（正文），不只是标题与简介', () => {
    assert.match(HELP, /function collectSectionText/)
    assert.match(HELP, /collectSectionText\(\[s\.title, s\.intro, s\.blocks\]\)/)
  })
})

describe('C68 非法 channelId 不再静默降级', () => {
  it('地址参数查无此频道时显式说明，并回写真正生效的频道', () => {
    assert.match(BOOK_POOL, /data-guide="book-pool-dead-channel"/)
    assert.match(BOOK_POOL, /deadChannelId/)
    // 不允许把 query 直接当成有效频道
    assert.doesNotMatch(BOOK_POOL, /channelId\.value\s*=\s*route\.query\.channelId/)
  })
})

describe('I27 移动端 tab 未读角标', () => {
  it('审批/消息 tab 有角标挂载点，计数来自 dashboard-summary', () => {
    assert.match(MOBILE_LAYOUT, /mobile-tab-badge-\$\{tab\.name\}/)
    assert.match(MOBILE_LAYOUT, /pending_review/)
    assert.match(MOBILE_LAYOUT, /unread_message/)
  })
})
