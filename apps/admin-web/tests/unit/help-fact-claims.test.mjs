/**
 * T02920：帮助文档 Help.vue 的量化/事实性描述必须有代码出处（M80 门禁做法的全量扩展）
 *
 * 与 help-db-claims.test.mjs 同一个原则：门禁里不抄文档里的数字，而是从源码算出来再比。
 * 文档以后加减功能，只要没同步改代码事实源，这里就红。
 *
 * 本单复核出的存量虚标（都在下面的用例里被逐条钉住）：
 * - 数据统计：把「收藏数、反馈数」写成看板指标，接口只下发 5 个指标；
 * - 广告管理：宣称「上传音频/图片素材」「素材大小限制 10MB」「按频道、时段、频次」，
 *   实际接口只登记名称/描述/URL/时长，投放维度只有广告位 + 日期区间；
 * - 工作流监控：状态写成 pending，实际枚举是 queued；步骤名与界面枚举字典不一致；
 * - 队列管理：描述成「TTS 合成队列与音频拼接队列 + 清空已完成任务」，实际是任务状态计数 + 执行模式 + 批量删除；
 * - AI 服务：TTS 只列 3 个 provider，界面有 5 个；
 * - 快速开始 / COS 部署步骤：脚本没带 scripts/ 前缀，照着敲会找不到文件。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/help-fact-claims.test.mjs
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..')
const read = (rel) => readFileSync(path.join(ROOT, rel), 'utf8').replace(/\r\n/g, '\n')

const HELP = read('apps/admin-web/src/views/help/Help.vue')
const STATS = read('backend/app/services/stats_metrics.py')
const STATS_VIEW = read('apps/admin-web/src/views/stats/StatsOverview.vue')
const QUEUE_VIEW = read('apps/admin-web/src/views/queue/QueueManagement.vue')
const WF_DETAIL = read('apps/admin-web/src/views/workflow/WorkflowDetail.vue')
const WF_MODEL = read('backend/app/models/workflow.py')
const ENUMS = read('apps/admin-web/src/constants/enums.js')
const AI_VIEW = read('apps/admin-web/src/views/ai/AIConfig.vue')
const MAINT_VIEW = read('apps/admin-web/src/views/maintenance/Maintenance.vue')
const CONFIG = read('backend/app/config.py')
const SEED = read('backend/seed_admin.py')
const ABOUT_API = read('backend/app/routers/admin/about.py')
const ABOUT_VIEW = read('apps/admin-web/src/views/about/About.vue')
const ROUTER = read('apps/admin-web/src/router/index.js')
const ADS_API = read('backend/app/routers/admin/ads.py')
const AD_MODEL = read('backend/app/models/ad_placement.py')
const AD_SERVICE = read('backend/app/services/ad_service.py')
const CALC_VIEW = read('apps/admin-web/src/views/tools/ParamCalculator.vue')
const CHANNEL_MODEL = read('backend/app/models/channel.py')

// ---------- Help.vue 章节切片 ----------

// 只取 docSections 数组字面量本身：后面的脚本注释（如 main.py、docs/xxx.md）不是文档内容
const DOC_START = HELP.indexOf('const docSections = [')
const DOC = HELP.slice(DOC_START, HELP.indexOf('\n]', DOC_START) + 2)
const SECTION_IDS = [...DOC.matchAll(/^\s{4}id: '([a-z-]+)',/gm)].map((m) => m[1])

function sectionText(id) {
  const idx = SECTION_IDS.indexOf(id)
  assert.notEqual(idx, -1, `帮助文档里没有章节 ${id}`)
  const start = DOC.indexOf(`id: '${id}',`)
  const end =
    idx + 1 < SECTION_IDS.length
      ? DOC.indexOf(`id: '${SECTION_IDS[idx + 1]}',`)
      : DOC.indexOf('\n]', start)
  return DOC.slice(start, end)
}

/** 章节绑定的路由（T02635）：文档 ↔ 页面的结构化事实源，不再从正文句式反推 */
function sectionRoutes(id) {
  const m = /^\s*routes:\s*\[([^\]]*)\]/m.exec(sectionText(id))
  assert.ok(m, `章节 ${id} 没有 routes 字段（T02635）`)
  return [...m[1].matchAll(/'([^']+)'/g)].map((r) => r[1])
}

/** 章节里的参数配置表行：[键, 示例值, 说明] */
function configRows(id) {
  return [
    ...sectionText(id).matchAll(
      /^\s*\['([A-Za-z0-9_]+)',\s*'([^']*)',\s*'([^']*)'\]/gm,
    ),
  ].map((m) => ({ key: m[1], example: m[2], desc: m[3] }))
}

// ---------- 源码事实提取 ----------

/** OVERVIEW_METRICS 的键 → METRIC_META 里的 label（顺序即渲染顺序） */
function overviewMetricLabels() {
  const at = STATS.indexOf('OVERVIEW_METRICS = [')
  assert.notEqual(at, -1, '后端概览指标清单常量改名了，这个门要先跟着改')
  const keys = (STATS.slice(at).split(']')[0].match(/"[a-z_]+"/g) || []).map((s) =>
    s.slice(1, -1),
  )
  assert.ok(keys.length > 0, '概览指标清单解析为空')
  return keys.map((k) => {
    const m = STATS.slice(STATS.indexOf(`"${k}": {`)).match(/"label":\s*"([^"]+)"/)
    assert.ok(m, `指标 ${k} 在 METRIC_META 里没有 label`)
    return m[1]
  })
}

/** enums.js 里某个枚举字典的 value → label */
function enumLabels(dictName) {
  const at = ENUMS.indexOf(`export const ${dictName} = {`)
  assert.notEqual(at, -1, `enums.js 里找不到 ${dictName}`)
  const body = ENUMS.slice(at).split('\n}')[0]
  const out = {}
  for (const m of body.matchAll(/^\s*(\w+):\s*\{\s*label:\s*'([^']+)'/gm)) out[m[1]] = m[2]
  assert.ok(Object.keys(out).length > 0, `${dictName} 没解析出 label`)
  return out
}

/** 后端 CheckConstraint 里的取值清单 */
function checkConstraintValues(source, column) {
  const m = source.match(new RegExp(`${column} IN \\(([^)]*)\\)`))
  assert.ok(m, `后端模型里没有 ${column} 的取值约束`)
  return (m[1].match(/'[^']+'/g) || []).map((s) => s.slice(1, -1))
}

function settingsKeys() {
  return new Set(
    [...CONFIG.matchAll(/^\s{4}([A-Z0-9_]+):/gm)].map((m) => m[1]),
  )
}

function channelColumns() {
  return new Set(
    [...CHANNEL_MODEL.matchAll(/^\s+(\w+):\sMapped/gm)].map((m) => m[1]),
  )
}

/** 白名单表数：与 help-db-claims.test.mjs 同一算法，文档里的「N 张」由它说了算 */
function allowedTableCount() {
  const service = read('backend/app/services/db_admin_service.py')
  const open = service.indexOf('ALLOWED_TABLES: dict[str, str] = {')
  assert.notEqual(open, -1, '后端白名单常量改名了，这个门要先跟着改')
  const body = service.slice(open).split('\n}')[0]
  return (body.match(/^\s{4}"[a-z_]+":\s"/gm) || []).length
}

/** Maintenance.vue 各清理分组的 el-option 文案（按出现顺序分组） */
function maintenanceOptions() {
  return [...MAINT_VIEW.matchAll(/<el-option label="([^"]+)"\s+value="([a-z_]+)"/g)].map(
    (m) => ({ label: m[1], value: m[2] }),
  )
}

/** QueueManagement.vue 状态计数卡片用到的状态 */
function queueStatCardKeys() {
  const m = QUEUE_VIEW.match(/const STAT_CARDS = \[([^\]]*)\]/)
  assert.ok(m, '队列页状态卡片清单改名了')
  return (m[1].match(/'[^']+'/g) || []).map((s) => s.slice(1, -1))
}

// ---------- 用例 ----------

describe('T02920 数据统计章节', () => {
  it('核心指标括号与后端下发的指标逐一对应，数量按源码算', () => {
    const labels = overviewMetricLabels()
    const sec = sectionText('stats')
    assert.match(
      sec,
      new RegExp(`核心指标看板（${labels.join('、')}）`),
      `文档必须按后端清单写：${labels.join('、')}`,
    )
    assert.match(sec, new RegExp(`查看 ${labels.length} 个核心指标卡片`))
    assert.doesNotMatch(sec, /收藏数|反馈数/, '这两个是 C 端业务表，概览接口不下发')
  })

  it('趋势图指标与时间范围取自页面单选按钮', () => {
    const sec = sectionText('stats')
    const buttons = [...STATS_VIEW.matchAll(/<el-radio-button value="([a-z_\d]+)">([^<]+)</g)]
    assert.ok(buttons.length >= 5, `趋势单选解析异常（${buttons.length}）`)
    for (const m of buttons) {
      const label = m[2].trim()
      assert.ok(
        sec.includes(label),
        `界面有单选「${label}」（${m[1]}），文档没提或写成了别的口径`,
      )
    }
  })
})

describe('T02920 广告管理章节', () => {
  it('素材字段就是接口请求模型的字段，不提供上传也不管图片', () => {
    const sec = sectionText('ads')
    const at = ADS_API.indexOf('class MaterialCreateRequest')
    assert.notEqual(at, -1, '广告素材请求模型改名了')
    const fields = [...ADS_API.slice(at).split('\n\nclass')[0].matchAll(/^\s{4}(\w+):/gm)].map(
      (m) => m[1],
    )
    assert.deepEqual(
      fields,
      ['name', 'description', 'file_url', 'duration'],
      '素材字段变了，文档要跟着改',
    )
    // 「不提供文件上传」是要正面否认的，所以只禁承诺式写法
    assert.doesNotMatch(sec, /支持上传|可上传|上传广告|上传音频|页面上传/, '页面没有上传入口')
    assert.doesNotMatch(sec, /\/图片|图片广告|图片素材/, '素材表里没有图片类型')
    assert.doesNotMatch(sec, /10\s?MB|大小限制/, '没有任何素材大小限制')
    assert.match(sec, /不提供文件上传/, '要否认到位，别让人继续找上传按钮')
    assert.match(sec, /素材 URL/, '登记方式要说清楚')
  })

  it('投放维度只有广告位与日期区间，广告位名称取自枚举字典', () => {
    const sec = sectionText('ads')
    const labels = checkConstraintValues(AD_MODEL, 'position').map(
      (v) => enumLabels('AD_POSITION')[v],
    )
    assert.ok(labels.every(Boolean), 'AD_POSITION 缺 label')
    assert.match(sec, new RegExp(`广告位（${labels.join('/')}）`))
    assert.doesNotMatch(sec, /时段|频次/, '投放规则表里没有时段/频次字段')
    // 频道维度确实存在，但它是频道表单上的开关，不是投放规则字段
    assert.match(sec, /「投放广告」开关/)
    assert.match(
      read('apps/admin-web/src/views/channel/ChannelManagement.vue'),
      /label="投放广告"/,
      '频道侧开关的名字变了，文档要同步',
    )
  })

  it('排期冲突的处理口径与后端裁决一致', () => {
    const sec = sectionText('ads')
    assert.match(sec, /拒绝保存/)
    assert.match(sec, /停用的投放不参与冲突判定/)
    assert.match(AD_SERVICE, /不允许重叠/)
  })
})

describe('T02920 工作流监控章节', () => {
  it('状态清单与后端枚举约束完全一致（pending 是错的）', () => {
    const codes = checkConstraintValues(WF_MODEL, 'status')
    const sec = sectionText('workflows')
    assert.match(
      sec,
      new RegExp(`按状态（${codes.join('/')}）`),
      `后端状态是 ${codes.join('/')}，文档不许自己拼一份`,
    )
    assert.doesNotMatch(sec, /pending\/running/, 'pending 是步骤状态，不是工作流状态')
  })

  it('步骤名用界面枚举字典的中文标签，且顺序与详情页一致', () => {
    const m = WF_DETAIL.match(/const STEP_ORDER = \[([^\]]*)\]/)
    assert.ok(m, '详情页步骤顺序常量改名了')
    const names = (m[1].match(/'[^']+'/g) || []).map((s) => s.slice(1, -1))
    const labels = enumLabels('WORKFLOW_STEP_NAME')
    const expected = names.map((n) => {
      assert.ok(labels[n], `枚举字典缺 ${n} 的 label`)
      return labels[n]
    })
    assert.match(
      sectionText('workflows'),
      new RegExp(`每个步骤（${expected.join('/')}）`),
      '文档要么照界面标签写全，要么别写——半套标签会让人找不到对应步骤',
    )
  })
})

describe('T02920 队列管理章节', () => {
  it('计数卡片的状态与标签来自页面常量 + 枚举字典', () => {
    const keys = queueStatCardKeys()
    const labels = enumLabels('WORKFLOW_STATUS')
    const sec = sectionText('queue')
    const expected = keys.map((k) => labels[k]).join('/')
    assert.match(
      sec,
      new RegExp(`计数卡片（${expected}）`),
      `队列页四张卡片是 ${expected}，文档写的「待处理/处理中/完成/失败」是编的`,
    )
    assert.doesNotMatch(sec, /TTS 合成队列与音频拼接队列/, '本页不区分这两类队列')
    assert.doesNotMatch(sec, /清空已完成任务/, '没有这个按钮')
  })

  it('并发数区间取自滑杆属性，行内动作名取自按钮', () => {
    const slider = QUEUE_VIEW.match(/v-model="config\.concurrency"[^>]*/)?.[0]
    assert.ok(slider, '并发数滑杆找不到了')
    const min = slider.match(/:min="(\d+)"/)[1]
    const max = slider.match(/:max="(\d+)"/)[1]
    assert.match(sectionText('queue'), new RegExp(`并发数 ${min}-${max}`))

    const actionLabels = [...QUEUE_VIEW.matchAll(/label="(取消|改优先级|重试|批量删除)"/g)].map(
      (m) => m[1],
    )
    assert.ok(actionLabels.length >= 4, '队列页动作按钮变了，文档要跟着改')
    for (const label of new Set(actionLabels)) {
      assert.match(sectionText('queue'), new RegExp(label), `界面有「${label}」，文档没写`)
    }
  })
})

describe('T02920 系统清理章节', () => {
  it('清理项名称逐个对应页面上的下拉选项', () => {
    const sec = sectionText('maintenance')
    const options = maintenanceOptions()
    assert.ok(options.length >= 12, `清理选项解析异常（${options.length}）`)
    for (const { value, label } of options) {
      if (value === 'all') continue
      const key = label.replace(/（[^）]*）/g, '').trim()
      assert.ok(
        sec.includes(key),
        `界面清理项「${key}」（${value}）在文档里没有，或文档写的是别的名字`,
      )
    }
    // 反向：文档里括号列出的清理项也不能是界面没有的（接错对象防护）
    const grouped = [...sec.matchAll(/（([^（）]*?\/[^（）]*?)）/g)].map((m) => m[1])
    const known = new Set(options.map((o) => o.label.replace(/（[^）]*）/g, '').trim()))
    for (const token of grouped.join('/').split('/')) {
      assert.ok(known.has(token), `文档写了界面上不存在的清理项「${token}」`)
    }
  })
})

describe('T02920 AI 服务章节', () => {
  it('限流阈值与 TTS provider 清单按源码算', () => {
    const limit = CONFIG.match(/^\s*AI_BUDGET_RATE_LIMIT_PER_MIN:\s*int\s*=\s*(\d+)/m)[1]
    assert.match(sectionText('ai-config'), new RegExp(`限流 ${limit} 次/分钟`))

    const at = AI_VIEW.indexOf('const ttsProviders = [')
    const keys = (AI_VIEW.slice(at).split(']')[0].match(/key:\s*'([a-z]+)'/g) || []).map(
      (s) => s.match(/'([a-z]+)'/)[1],
    )
    assert.ok(keys.length >= 3, 'TTS provider 选项解析为空')
    const sec = sectionText('ai-config')
    for (const k of keys) {
      assert.ok(sec.includes(k), `界面支持 TTS provider ${k}，文档漏了`)
    }
    assert.ok(
      keys.every((k) => sec.includes(k)),
      'provider 清单要与界面一致，不许只列三个',
    )
  })

  it('参数配置表的环境变量名真实存在', () => {
    const keys = settingsKeys()
    for (const row of configRows('ai-config')) {
      assert.ok(keys.has(row.key), `${row.key} 不是后端配置项`)
    }
    // 接错对象防护：模型示例值要等于后端默认值
    const modelRow = configRows('ai-config').find((r) => r.key === 'LLM_MODEL')
    const def = CONFIG.match(/^\s*LLM_MODEL:\s*str\s*=\s*"([^"]+)"/m)[1]
    assert.equal(modelRow.example, def, '默认模型示例值与后端不一致')
  })
})

describe('T02920 频道管理章节', () => {
  it('参数配置表的键都是频道表字段，示例值可落地', () => {
    const cols = channelColumns()
    const rows = configRows('channels')
    assert.ok(rows.length >= 5, '频道参数表解析为空')
    for (const row of rows) {
      assert.ok(cols.has(row.key), `频道表没有字段 ${row.key}`)
    }
    const bgm = rows.find((r) => r.key === 'bgm_path')
    assert.ok(
      existsSync(path.join(ROOT, 'backend/data/bgm', bgm.example.replace(/\//g, path.sep))),
      `BGM 示例 ${bgm.example} 在 backend/data/bgm 下不存在`,
    )
  })
})

describe('T02920 快速开始与关于章节', () => {
  it('默认账号与端口按后端源码算', () => {
    const user = SEED.match(/def seed\(db_path, username=['"](\w+)['"]/)[1]
    // T02845：口令不再写死在签名里，优先取 .env 的 ADMIN_INITIAL_PASSWORD，
    // 兜底值仍在 seed_admin.py。文档必须两截都写——只写 admin123 又是假话。
    const fallback = SEED.match(/ADMIN_INITIAL_PASSWORD or ['"]([^'"]+)['"]/)[1]
    const port = CONFIG.match(/^\s*APP_PORT:\s*int\s*=\s*(\d+)/m)[1]
    const sec = sectionText('quickstart')

    // 按条目钉，不按整节：同一节里 steps 与 note 都在讲口令，
    // 只断言「整节含某个词」时，另一条退回旧口径照样全绿（探针 G1/G2 实测过）。
    const stepLine = sec.split('\n').find((l) => l.includes('访问运营后台'))
    assert.ok(stepLine, '快速开始的步骤里没有「访问运营后台」')
    assert.match(stepLine, new RegExp(`账号 ${user}`))
    assert.match(stepLine, /ADMIN_INITIAL_PASSWORD/)
    assert.match(stepLine, new RegExp(`留空为 ${fallback}`))
    assert.match(stepLine, new RegExp(`http://127\\.0\\.0\\.1:${port}/`))

    // 「请立即修改密码」曾是空头承诺（没有改密入口）；换成能执行的建库前设置说明
    const noteLine = sec.split('\n').find((l) => l.includes('首次启动自动 seed'))
    assert.ok(noteLine, '快速开始的注意事项块不见了')
    assert.match(noteLine, /口令取 \.env 的 ADMIN_INITIAL_PASSWORD/)
    assert.match(noteLine, /没有改密入口/)
  })

  it('自动检查更新的三个时间口径都有实现兜着', () => {
    const first = ABOUT_VIEW.match(/mountDelayTimer = setTimeout\(\(\) => \{\s*\n\s*performCheck\(\)\s*\n\s*\}, (\d+)\)/)
    const every = ABOUT_VIEW.match(/autoCheckTimer = setInterval\(\(\) => \{\s*\n\s*performCheck\(\)\s*\n\s*\}, (\d+) \* (\d+) \* (\d+)\)/)
    assert.ok(first && every, '关于页自动检查的节奏变了，文档要同步')
    const firstSec = Number(first[1]) / 1000
    const hourMs = Number(every[1]) * Number(every[2]) * Number(every[3])
    const min = hourMs / 60000
    const ttl = Number(ABOUT_API.match(/_CACHE_TTL_SECONDS = (\d+)/)[1])
    const sec = sectionText('about')
    assert.match(sec, new RegExp(`进入页面 ${firstSec} 秒后首次检查`))
    assert.match(sec, new RegExp(`之后每 ${min} 分钟检查一次`))
    assert.match(sec, new RegExp(`后端 ${ttl / 60} 分钟缓存`))
  })
})

describe('T02920 音频存储（COS）章节', () => {
  it('参数表就是后端 COS 配置项，正文的「N 个」按行数算', () => {
    const rows = configRows('cos-storage')
    const keys = settingsKeys()
    for (const row of rows) {
      assert.ok(keys.has(row.key), `${row.key} 不是后端配置项`)
    }
    assert.match(
      sectionText('cos-storage'),
      new RegExp(`上述 ${rows.length} 个 COS 参数`),
      `参数表有 ${rows.length} 行，正文计数要跟着改`,
    )
    assert.match(read('backend/requirements.txt'), /cos-python-sdk-v5/, 'SDK 依赖不在了，安装步骤要删')
  })

  it('无法从代码核对的外部数字一律不写', () => {
    const sec = sectionText('cos-storage')
    assert.doesNotMatch(sec, /300-1000ms|50-200ms/, '延迟毫秒数是口头测量，代码里没有出处')
    assert.doesNotMatch(sec, /\d+-\d+ 倍/, '倍率同理')
    assert.doesNotMatch(sec, /约 \d+-\d+ 个工作日|\d+GB 内约 \d+ 元/, '备案周期与腾讯云报价不该由文档承诺')
  })
})

describe('T02920 参数计算器章节', () => {
  it('基础语速、三个区间与预设名都来自页面', () => {
    const sec = sectionText('tools')
    const base = CALC_VIEW.match(/const BASE_WORDS_PER_MIN = (\d+)/)[1]
    assert.match(sec, new RegExp(`常量 ${base} 字/分`))
    const ranges = [
      ['durationSec', '时长'],
      ['totalWords', '总字数'],
      ['rateMultiplier', '倍率'],
    ]
    for (const [model, zh] of ranges) {
      const line = CALC_VIEW.match(new RegExp(`v-model="${model}"[^\\s]*`))
      const block = CALC_VIEW.slice(CALC_VIEW.indexOf(`v-model="${model}"`), CALC_VIEW.indexOf(`v-model="${model}"`) + 400)
      const min = block.match(/:min="([\d.]+)"/)[1]
      const max = block.match(/:max="([\d.]+)"/)[1]
      assert.ok(line, `${model} 滑杆不见了`)
      assert.ok(
        sec.includes(`${min}–${max}`),
        `文档里 ${zh} 的区间要与界面上的 ${min}–${max} 一致`,
      )
    }
    const presets = [...CALC_VIEW.matchAll(/\{ key: '\w+', label: '([^']+)', icon/g)].map((m) => m[1])
    assert.ok(presets.length >= 3, '预设解析为空')
    for (const p of presets) {
      assert.ok(sec.includes(p), `界面预设「${p}」文档没提`)
    }
  })
})

describe('T02920 权限口径', () => {
  it('写了「仅 admin」的章节，其 routes 里的路由都 requireRole: admin', () => {
    for (const id of ['workflows', 'tunnel', 'db-admin', 'maintenance']) {
      assert.match(
        sectionText(id),
        /仅 admin/,
        `章节 ${id} 不再声明权限，路由那条 gating 也要一起复核`,
      )
      const routes = sectionRoutes(id)
      assert.ok(routes.length > 0, `章节 ${id} 没有绑定路由，无法核对权限口径`)
      for (const route of routes) {
        const p = route.replace(/^\//, '')
        const at = ROUTER.indexOf(`path: '${p}'`)
        assert.notEqual(at, -1, `路由里找不到 ${route}`)
        assert.match(
          ROUTER.slice(at, at + 260),
          /requireRole: 'admin'/,
          `章节 ${id} 宣称仅 admin，但路由 ${route} 不再限制角色了`,
        )
      }
    }
  })
})

describe('T02920 文档里出现的路径都能在磁盘上找到', () => {
  // 后端脚本/配置路径：照文档敲却「找不到文件」是这类文档最常见的坑。
  // 被当成命令敲的路径（双击/执行/python/copy/pip install）必须按文档原样解析——
  // 丢掉 scripts/ 前缀的写法在磁盘上根本不存在，不能因为某个目录下有同名文件就放过。
  const COMMAND_VERBS = /(双击|执行|运行|python|copy|pip install)/
  const RESOLVE_DIRS = ['', 'backend', 'scripts', 'apps/admin-web']
  const WHITELIST = {
    // 文档里用简称，实际在 crawler 源目录下
    'rss.yaml': 'backend/app/workflow/crawler/sources/rss.yaml',
  }

  function exists(rel) {
    return existsSync(path.join(ROOT, rel.replace(/\//g, path.sep)))
  }

  const tokens = [...new Set(
    DOC.match(/[\w\u4e00-\u9fff._/-]+\.(?:py|ps1|bat|md|txt|json|ya?ml|js|vue|mp3|env\.example)/g) || [],
  )]
  assert.ok(tokens.length >= 8, `路径 token 解析异常（${tokens.length}）`)

  for (const token of tokens) {
    it(token, () => {
      if (token.endsWith('.mp3')) {
        // bgm_path 相对 backend/data/bgm 解析（channels.py 的路径约定）
        assert.ok(exists(`backend/data/bgm/${token}`), 'BGM 相对 backend/data/bgm 不存在')
        return
      }
      if (WHITELIST[token]) {
        assert.ok(exists(WHITELIST[token]), `${token} 白名单指向的文件不见了`)
        return
      }
      // 命令上下文：取该 token 前面 24 个字符判断；
      // 前一个字符还是路径字符的话，它只是更长路径的尾巴，由那条路径自己负责
      const occurrences = []
      let from = 0
      for (;;) {
        const at = DOC.indexOf(token, from)
        if (at < 0) break
        from = at + token.length
        if (at > 0 && /[\w\u4e00-\u9fff._/-]/.test(DOC[at - 1])) continue
        occurrences.push(DOC.slice(Math.max(0, at - 24), at))
      }
      if (occurrences.length === 0) return
      const asCommand = occurrences.some((ctx) => COMMAND_VERBS.test(ctx))
      if (asCommand) {
        assert.ok(exists(token), `文档把 ${token} 当命令给出，但它相对仓库根不存在`)
        return
      }
      assert.ok(
        RESOLVE_DIRS.some((d) => exists(path.posix.join(d, token))),
        `文档里的 ${token} 在仓库根/backend/scripts/apps-admin-web 下都找不到（要么改路径，要么进白名单并写明真实位置）`,
      )
    })
  }
})

describe('T02920 计数词的出处登记（不接受无来源的量词）', () => {
  // 每个「数字 + 个/张/种/步/项/条/款」都要能说清算源：sourced = 本文件里按源码算出来的，
  // gated-elsewhere = 由另一个门禁文件负责，reason = 不能机器核对时给出的说明。
  // 数字本身也从源码算，门里不留任何写死的量词数字
  const metricCount = overviewMetricLabels().length
  const cosRowCount = configRows('cos-storage').length
  const SOURCED = [
    { re: new RegExp(`查看 ${metricCount} 个核心指标`), source: `overviewMetricLabels()（后端 OVERVIEW_METRICS 计数 = ${metricCount}）` },
    { re: new RegExp(`上述 ${cosRowCount} 个 COS 参数`), source: `configRows("cos-storage").length（参数表行数 = ${cosRowCount}）` },
    { re: new RegExp(`${allowedTableCount()} 张业务表`), source: 'help-db-claims.test.mjs 按 ALLOWED_TABLES 计数' },
    { re: /返回 0 条/, source: 'reason: 描述「RSS 源名不匹配时采集到 0 条」的行为，不是数量承诺' },
  ]

  it('每个量词命中都在出处表里', () => {
    // 取命中处的前后文，量词孤零零一个「5 个」没法判断出处
    const hits = [
      ...DOC.matchAll(/.{0,14}[0-9]+ ?(?:个|张|种|步|项|条|款).{0,16}/g),
    ].map((m) => m[0].replace(/\s+/g, ' ').trim())
    assert.ok(hits.length > 0, '量词正则没命中，先确认扫描范围')
    const unmatched = hits.filter((h) => !SOURCED.some((s) => s.re.test(h)))
    assert.deepEqual(
      [...new Set(unmatched)],
      [],
      `这些量词没有算源：${[...new Set(unmatched)].join(' | ')}（改文档或补门禁，别加写死的数字）`,
    )
  })

  it('量词表本身不许留空条目', () => {
    for (const s of SOURCED) assert.ok(s.source, '出处必须写清楚')
  })
})

describe('T02920 文档不许再出现的模糊量词', () => {
  it('没有「20+」「数十张」「多张」这类等于没写的表述', () => {
    assert.doesNotMatch(DOC, /20\+|数十|多张|若干个|若干项/)
  })
})
