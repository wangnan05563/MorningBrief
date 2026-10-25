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
import { filterHelpSections } from '../../src/utils/helpSearch.js'

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
  // 直接从 SFC 里取出 messageTarget 求值：这是纯函数，行为必须可跑，不能只断言源码里
  // 有那两行——优先级写反、startsWith 取反这类错误，正则一条都抓不到。
  const messageTarget = (() => {
    const at = MESSAGE.indexOf('function messageTarget(m)')
    assert.notEqual(at, -1, 'Message.vue 里找不到 messageTarget')
    let depth = 0
    let quote = ''
    for (let i = at; i < MESSAGE.length; i += 1) {
      const ch = MESSAGE[i]
      if (quote) {
        if (ch === '\\') i += 1
        else if (ch === quote) quote = ''
        continue
      }
      if (ch === '/' && MESSAGE[i + 1] === '/') {
        const nl = MESSAGE.indexOf('\n', i)
        i = nl === -1 ? MESSAGE.length : nl
        continue
      }
      if (ch === "'" || ch === '"' || ch === '`') {
        quote = ch
        continue
      }
      if (ch === '{') depth += 1
      else if (ch === '}') {
        depth -= 1
        if (depth === 0) return new Function('return (' + MESSAGE.slice(at, i + 1) + ')')()
      }
    }
    throw new Error('messageTarget 未闭合')
  })()

  it('显式 payload.path 优先于 workflow_id，且原样带 query', () => {
    assert.equal(messageTarget({ payload: { path: '/m/review?tab=all', workflow_id: 7 } }), '/m/review?tab=all')
  })

  it('只有 workflow_id 时进作用域审核页，id 一律转成字符串', () => {
    assert.deepEqual(messageTarget({ payload: { workflow_id: 42 } }), {
      path: '/m/review',
      query: { workflow_id: '42' },
    })
    assert.deepEqual(messageTarget({ payload: { workflow_id: 'wf-9' } }).query.workflow_id, 'wf-9')
  })

  it('相对地址不算深链：path 不以 / 开头时丢弃', () => {
    assert.equal(messageTarget({ payload: { path: 'review' } }), '')
    assert.equal(messageTarget({ payload: { path: 'https://evil.example/x' } }), '')
  })

  it('空 workflow_id 不生成链接（0/空串/null/undefined 都不算目标）', () => {
    assert.equal(messageTarget({ payload: { workflow_id: '' } }), '')
    assert.equal(messageTarget({ payload: { workflow_id: null } }), '')
    assert.equal(messageTarget({ payload: {} }), '')
  })

  it('payload 缺失或不是对象时不跳转、不抛错', () => {
    assert.equal(messageTarget({}), '')
    assert.equal(messageTarget({ payload: 'x' }), '')
    assert.equal(messageTarget(null), '')
    assert.equal(messageTarget({ payload: [] }), '')
  })

  it('不按 msg_type/标题猜地址：没有显式契约就不跳', () => {
    assert.equal(messageTarget({ msg_type: 'review', title: '有新的审核任务' }), '')
    assert.equal(messageTarget({ msg_type: 'alert', title: '工作流失败' }), '')
  })

  it('open() 在标记已读后仍会跳转（不再直接 return）', () => {
    const at = MESSAGE.indexOf('async function open(m)')
    assert.notEqual(at, -1)
    const body = MESSAGE.slice(at, MESSAGE.indexOf('\n}', at))
    assert.match(body, /router\.push\(target\)/)
    assert.doesNotMatch(body, /if \(m\.read\) \{\s*\/\/[^\n]*\n\s*return/)
  })

  it('可跳转的消息在列表上有明确入口（chevron + link 类）', () => {
    assert.match(MESSAGE, /'m-msg__item--link': !!messageTarget\(m\)/)
    assert.match(MESSAGE, /<span v-if="messageTarget\(m\)" class="m-msg__go" aria-label="查看详情">/)
  })
})

describe('I48 队列项显式携带 workflow_id', () => {
  it('后端下发 workflow_id，前端消费它而不是猜测 id 语义', () => {
    assert.match(QUEUE_SERVICE, /"workflow_id": wf\.id/)
    assert.match(MANAGE_QUEUE, /workflow_id:\s*t\.workflow_id \?\? t\.id/)
  })
})

describe('M88 帮助搜索覆盖正文', () => {
  // 从 SFC 里取出真实 docSections：搜索口径的用例必须跑在真实文档上，否则改了文案/加块类型
  // 用例还在原地绿。数组字面量按括号配对截取（跳过字符串与注释），再用 markRaw 注入求值。
  const literal = (() => {
    const at = HELP.indexOf('const docSections =')
    assert.notEqual(at, -1, 'Help.vue 里找不到 docSections')
    const open = HELP.indexOf('[', at)
    let depth = 0
    let quote = ''
    for (let i = open; i < HELP.length; i += 1) {
      const ch = HELP[i]
      if (quote) {
        if (ch === '\\') i += 1
        else if (ch === quote) quote = ''
        continue
      }
      if (ch === '/' && HELP[i + 1] === '/') {
        const nl = HELP.indexOf('\n', i)
        i = nl === -1 ? HELP.length : nl
        continue
      }
      if (ch === '/' && HELP[i + 1] === '*') {
        const end = HELP.indexOf('*/', i + 2)
        i = end === -1 ? HELP.length : end + 1
        continue
      }
      if (ch === "'" || ch === '"' || ch === '`') {
        quote = ch
        continue
      }
      if (ch === '[') depth += 1
      else if (ch === ']') {
        depth -= 1
        if (depth === 0) return HELP.slice(open, i + 1)
      }
    }
    throw new Error('docSections 数组未闭合')
  })()
  const DOC = (() => {
    const icons = [...new Set([...literal.matchAll(/markRaw\(([A-Za-z_$][\w$]*)\)/g)].map((m) => m[1]))]
    // 文档数据只依赖 markRaw(图标)；把图标名注入成同名标识符即可原样求值
    return new Function('markRaw', ...icons, 'return (' + literal + ')')((v) => v, ...icons.map((n) => n))
  })()
  const hits = (kw) => filterHelpSections(DOC, kw)
  const bodyOnly = (kw) => {
    const found = hits(kw)
    assert.ok(found.length > 0, `「${kw}」应至少命中一章`)
    return found.filter((s) => !`${s.title}\n${s.intro}`.toLowerCase().includes(kw.toLowerCase()))
  }

  it('真实文档的块类型齐全，正文类用例才有意义', () => {
    const types = [...new Set(DOC.flatMap((s) => s.blocks.map((b) => b.type)))].sort()
    assert.deepEqual(types, ['config', 'feature', 'note', 'scenario', 'steps'])
  })

  it('只在标题/简介命中的词仍能搜到（不因改造丢掉原有能力）', () => {
    assert.ok(hits('广告管理').some((s) => s.title === '广告管理'))
    assert.ok(hits('决定是否进入 TTS 合成流程').length === 1)
  })

  it('步骤数组可搜到，且确认命中位置在正文', () => {
    const found = bodyOnly('访问运营后台')
    assert.deepEqual(found.map((s) => s.id), ['quickstart'])
  })

  it('配置表格的参数列与说明列都可搜到', () => {
    assert.deepEqual(bodyOnly('COS_SECRET_ID').map((s) => s.id), ['cos-storage'])
    assert.ok(bodyOnly('通义千问').length >= 1)
  })

  it('注意事项块可搜到', () => {
    assert.ok(bodyOnly('生产环境请立即修改密码').some((s) => s.id === 'quickstart'))
  })

  it('关键词按大小写不敏感与首尾空白归一匹配', () => {
    assert.deepEqual(hits('cos_secret_id').map((s) => s.id), hits('COS_SECRET_ID').map((s) => s.id))
    assert.deepEqual(hits('  COS_SECRET_ID  ').map((s) => s.id), ['cos-storage'])
  })

  it('跨章节命中返回全部相关章节而不是只取第一个', () => {
    assert.ok(hits('COS').length >= 2)
  })

  it('块的 type / noteType 等展示枚举不算文档内容', () => {
    assert.deepEqual(hits('warning'), [])
    assert.deepEqual(hits('feature'), [])
  })

  it('空关键词与纯空白返回全部章节且保持原顺序，无命中返回空数组', () => {
    assert.deepEqual(hits('').map((s) => s.id), DOC.map((s) => s.id))
    assert.deepEqual(hits('   ').map((s) => s.id), DOC.map((s) => s.id))
    assert.deepEqual(hits('不存在的词zzz'), [])
  })

  it('组件只保留一份实现：引用 utils/helpSearch，正文/空态都渲染过滤结果', () => {
    assert.match(HELP, /import \{ filterHelpSections \} from '\.\.\/\.\.\/utils\/helpSearch'/)
    assert.match(HELP, /filterHelpSections\(docSections, search\.value\)/)
    assert.doesNotMatch(HELP, /function collectSectionText/)
    assert.match(HELP, /v-for="s in filteredSections"/)
    assert.match(HELP, /v-for="section in filteredSections"/)
    assert.match(HELP, /未找到匹配的章节/)
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
