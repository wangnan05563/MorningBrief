/**
 * M4「界面声称未发生的事 / 枚举与文档口径漂移」单元测试（T02536）
 *
 * 这一批缺陷的共同形状是：**界面的说法与代码/数据的真相不一致**。所以门禁分三层：
 * 1) 纯逻辑断言（强）：D15 日期区间校验、D16 关键词搜索、M20 时间戳列判定、
 *    C103 讲书稿生成排除——能直接喂输入看输出。
 * 2) 契约双向核对（中）：把「页面的说法」和「另一侧的实现」互相对齐。
 *    G1 页面读 `err.payload`，就必须有 api/index.js 真的写 `err.payload`；
 *    M84 文档写 `scripts/jmeter_test/x.py`，磁盘上就必须真的有这个文件；
 *    M77 文档写动作名，就必须和 ReviewDetail.vue 的 label 一致；
 *    H2 说「系统不会自动拼接后缀」，后端就必须真的没有拼接逻辑。
 *    「接错对象」（形状对、指向错）只有这种双向核对才拦得住。
 * 3) 反退回断言（弱但必要）：钉死旧写法不得复现——固定 size:50、`start_date >= end_date`、
 *    硬编码 `source_type: 'list'`、承诺系统自动拼 -{APPID}。
 *    真实渲染行为由 tests/m4-claims-are-true.spec.js（真实 Chrome）负责。
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'

import { MATERIAL_SOURCE_TYPE, enumLabel } from '../../src/constants/enums.js'
import { PANEL_PAGE_SIZE_OPTIONS, MAX_PAGE_SIZE } from '../../src/constants/pagination.js'

/**
 * 读源码并剥掉注释。M4 的缺陷形状是「界面/文档的说法与实现不符」，而我们修完后往往会在
 * 注释里留下旧说法作为记录。追溯门要判的是**用户看得见的话与代码行为**，所以先把注释剥掉，
 * 否则「旧文案不得复现」会被自家注释误触发。
 */
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
const REPO = '../../../../'

/** 取某函数名的源码文本：从 startMarker 起，到 endMarkers 中最早出现的一个止（行首 \n 只是「换行后」的意思，CRLF 下同样成立） */
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

/**
 * Python：取一个 def（模块级函数或类内方法皆可）的函数体。
 * 多行签名的收尾 `) -> dict:` 缩进和方法头同级，必须按括号深度跳过，否则函数体会被截空。
 */
function pyFunc(src, name) {
  const m = src.match(new RegExp(`^([ \\t]*)(?:async )?def ${name}\\(`, 'm'))
  assert.ok(m, `源码里找不到 def ${name}——追溯门失去意义`)
  const indLen = m[1].length
  const lines = src.slice(m.index).split('\n')
  const out = []
  let depth = 0
  for (const line of lines) {
    if (out.length && depth === 0 && line.trim()) {
      const lead = line.length - line.replace(/^[ \t]*/, '').length
      if (lead <= indLen) break
    }
    out.push(line)
    for (const ch of line) {
      if (ch === '(' || ch === '[' || ch === '{') depth++
      else if (ch === ')' || ch === ']' || ch === '}') depth--
    }
  }
  return out.join('\n')
}

// ============================================================ C103 枚举与落库

test('C103：book_plan 在前后端两侧枚举里都登记（只登记一侧会让构建门或筛选失效）', () => {
  const model = read(`${BACKEND}models/material.py`)
  assert.match(model, /book_plan = "book_plan"/, '后端 MaterialSourceType 未登记 book_plan')
  assert.ok(MATERIAL_SOURCE_TYPE.book_plan, '前端字典缺 book_plan → 素材库显示裸英文枚举')
  assert.equal(MATERIAL_SOURCE_TYPE.book_plan.label, '待讲书单')
  assert.equal(enumLabel(MATERIAL_SOURCE_TYPE, 'book_plan'), '待讲书单')
})

test('C103：加入待讲书单必须带归属频道，后端校验非法频道并回字段级错误', () => {
  const ebooks = read(`${BACKEND}routers/admin/ebooks.py`)
  const fn = slice(ebooks, 'async def create_draft_material', ['\n@router.', '\nasync def ', '\ndef '])
  assert.match(fn, /if req\.channel_id is not None:/, '频道未做存在性校验')
  assert.match(fn, /"field": "channel_id"/, '字段级错误未指向 channel_id')
  assert.match(fn, /source_type=MaterialSourceType\.book_plan\.value/, '占位素材类型未用枚举常量')
  assert.match(fn, /已加入待讲书单/, '回给用户的消息没说明这本书到底去了哪里')

  const finder = read(`${SRC}views/ebooks/BookFinder.vue`)
  assert.match(finder, /channel_id: planChannelId\.value/, '前端仍不传 channel_id → 落库 NULL，书「消失」')
  assert.match(finder, /if \(!planChannelId\.value\) \{/, '未选频道时前端没有拦住提交')
  assert.match(finder, /import \{ listChannels \}/, '频道列表未接真实接口')
})

test('C103：占位素材绝不进讲书稿生成链路（三处各一道，缺一处即漏）', () => {
  const svc = read(`${BACKEND}services/book_pool_service.py`)
  for (const fn of ['add_books', 'list_candidates', 'collect_book_materials']) {
    const body = pyFunc(svc, fn)
    assert.match(
      body,
      /MaterialSourceType\.book_plan\.value/,
      `${fn} 没排除 book_plan 占位素材——它没有正文，会被当成书稿改写并念出去`
    )
  }
})

// ============================================================ G1 错误负载消费

test('G1：拦截器契约与页面读取方式必须同形（payload/code，而不是 response.data）', async () => {
  const { readBizError } = await import('../../src/api/bizError.js')
  // 行为断言（强）：这就是 G1 的修复本体——业务错误的 code/data 必须读得出来
  const biz = readBizError(Object.assign(new Error('二进制下载失败'), { code: 5001, payload: { error_type: 'binary_download_failed' } }))
  assert.equal(biz.code, 5001, '业务错误码读不出来 → 引导块永不渲染（G1 原状）')
  assert.equal(biz.data.error_type, 'binary_download_failed', 'error_type 读不出来 → 无法区分失败子类型')
  assert.equal(readBizError({ response: { data: { message: '网关 502' } } }).message, '网关 502', '真 HTTP 错误仍要能读')
  assert.deepEqual(readBizError(undefined), {})

  const api = read(`${SRC}api/index.js`)
  assert.match(api, /err\.code = code/, '拦截器不再挂 code → 页面判 5001 恒假')
  assert.match(api, /err\.payload = data/, '拦截器不再挂 payload → 页面拿不到 data.error_type')

  const tunnel = read(`${SRC}views/tunnel/Tunnel.vue`)
  const start = slice(tunnel, 'async function handleStart', ['\nasync function ', '\nfunction '], 'handleStart')
  assert.match(start, /readBizError\(error\)/, 'handleStart 又开始手搓信封读法：两个引导块永不渲染')
  assert.match(start, /resp\?\.code === 5001/, '5001（二进制下载失败）分支丢失')
  assert.match(start, /resp\?\.code === 5003/, '5003（Funnel 需授权）分支丢失')
  assert.match(start, /resp\?\.data\?\.error_type/, '未读 error_type → 引导块条件写错对象')
  assert.match(start, /silent: true/, 'start 请求未静默：泛化 toast 会和引导块抢着说话')
  // 全页不得再出现旧读法（5 处 message-only 分支同样按契约读）
  assert.doesNotMatch(tunnel, /error\?\.response\?\.data/, '旧写法复现（HTTP 200 的业务错误只会得到一个纯 Error）')
  assert.equal((tunnel.match(/readBizError\(error\)/g) || []).length, 6, 'Tunnel 的 6 处错误分支必须全走同一个读法')
})

// ============================================================ C84 候选列表截断

test('C84：候选书籍可翻页，总数取后端 total 而不是本页已加载条数', () => {
  const panel = read(`${SRC}views/channel/BookPoolPanel.vue`)
  const load = slice(panel, 'async function loadCandidates', ['\nasync function ', '\nfunction '], 'loadCandidates')
  assert.match(load, /page: candidatePage\.value/, '候选仍固定 page:1')
  assert.match(load, /size: candidateSize\.value/, '候选仍固定 size:50（第 51 本起「不存在」）')
  assert.match(load, /candidateTotal\.value = data\?\.total/, '后端 total 又被丢弃')
  assert.doesNotMatch(load, /size: 50/, '硬编码 size: 50 复现')

  assert.match(panel, /:total="candidateTotal"/, '翻页控件没接总数')
  assert.doesNotMatch(panel, /:total="candidates\.length"/, '接错对象：总数取已加载条数 → 永远只有一页')
  assert.match(panel, /:page-sizes="PANEL_PAGE_SIZE_OPTIONS"/, '每页条数没走统一字典')
  assert.match(panel, /import \{ PANEL_PAGE_SIZE_OPTIONS \} from '..\/..\/constants\/pagination'/)
  assert.deepEqual(PANEL_PAGE_SIZE_OPTIONS, [20, 50, 100])
  assert.ok(PANEL_PAGE_SIZE_OPTIONS.every((n) => n <= MAX_PAGE_SIZE), '选项越过后端上限会被静默钳回')
  assert.match(panel, /本书可加入/, '界面没有把总数说给运营')
  assert.match(panel, /onCandidateSearch/, '搜索没有回到第 1 页的入口')
})

// ============================================================ M49 逐行错误明细

test('M49：导入失败必须留明细，且「未全部成功」时不得再声称导入完成', () => {
  const dba = read(`${SRC}views/maintenance/DatabaseAdmin.vue`)
  const handle = slice(dba, 'async function handleImport', ['\nasync function ', '\nfunction '], 'handleImport')
  assert.match(handle, /importResult\.value = result/, '后端 errors 又被整个丢弃')
  assert.match(handle, /导入未全部成功/, '有行没写进去仍报「导入完成」')
  assert.match(handle, /return\r?\n\s*\}\r?\n\s*ElMessage\.success/, '失败分支没 return，成功提示照发')
  assert.equal((dba.match(/导入完成：/g) || []).length, 1, '「导入完成：」出现两次说明有路径绕过判定')
  assert.match(dba, /importResult\.errors\.slice\(0, 20\)/, '界面没有渲染逐行明细')

  const open = slice(dba, 'function openImportDialog', ['\nasync function ', '\nfunction '], 'openImportDialog')
  assert.match(open, /importResult\.value = null/, '接错对象：上一次粘贴的失败明细还挂在面板上')
})

// ============================================================ T03603 导入计数去重

test('T03603：toast 的「未写入」只取 skipped，不再叠加 errors.length', () => {
  const dba = read(`${SRC}views/maintenance/DatabaseAdmin.vue`)
  const handle = slice(dba, 'async function handleImport', ['\nasync function ', '\nfunction '], 'handleImport')
  assert.match(handle, /const dropped = result\.skipped \|\| 0/, '未写入行数没走单一事实源')
  assert.doesNotMatch(
    handle,
    /skipped\s*\|\|\s*0\)\s*\+\s*\(result\.errors/,
    '同一行数被两遍：skipped 已包含错误行',
  )
  // 接错对象：改读 errors.length 会漏掉「整行无匹配列」这类只 skipped 不报错的历史分支
  assert.match(dba, /未写入 \{\{ importResult\.skipped \|\| 0 \}\} 行/, '面板口径被改成别的字段')
})

test('T03603：预览把「冲突」标成子集，不与新增/更新/错误并列相加', () => {
  const dba = read(`${SRC}views/maintenance/DatabaseAdmin.vue`)
  assert.doesNotMatch(
    dba,
    /冲突 \{\{ importPreview\.conflicts \}\}、错误/,
    '冲突仍是并列计数 → replace 下 1 行会读成 2 行',
  )
  assert.match(dba, /其中主键已存在/, '冲突子集没有在界面上说清楚')
  assert.match(dba, /importPreview\.mode === 'insert'/, '两种模式的计数拆分没有区分')
  // insert 分支只讲新增/跳过，混进更新计数等于把 replace 的口径串到另一模式
  const insertBranch = slice(dba, "v-if=\"importPreview.mode === 'insert'\"", ['<div v-else>'], 'insert 分支')
  assert.match(insertBranch, /预计跳过/, 'insert 模式没把跳过行数讲出来')
  assert.doesNotMatch(insertBranch, /\{\{ importPreview\.to_update \}\}/, 'insert 模式混入了更新计数')
})

// ============================================================ M20 系统维护列只读

test('M20：时间戳列由后端标记 auto_maintained，前端只读且不参与提交', () => {
  const svc = read(`${BACKEND}services/db_admin_service.py`)
  assert.match(svc, /"auto_maintained": _is_auto_maintained_time_column/, 'schema 不下发标记 → 前端无从判断')
  assert.ok(
    svc.includes('_AUTO_MAINTAINED_TIME_COLUMNS = {"created_at", "updated_at"'),
    '系统维护列白名单丢失'
  )

  const dba = read(`${SRC}views/maintenance/DatabaseAdmin.vue`)
  assert.match(dba, /\|\| isAutoMaintained\(col\)/, '编辑弹窗里时间戳列仍可输入')
  assert.match(dba, /c\.auto_maintained/, '非提交列集合没排除时间戳列')
  assert.match(dba, /createRow\(selectedTable\.value, buildCreateValues\(\)\)/, '新增仍提交 formData.value')
  assert.doesNotMatch(dba, /createRow\(selectedTable\.value, formData\.value\)/, '旧写法复现')
  assert.match(dba, /时间戳由系统自动写入/, '界面没有任何说明')
})

test('M20：判定按「列名 + 类型」双重收口，不误伤业务日期列', () => {
  const svc = read(`${BACKEND}services/db_admin_service.py`)
  const fn = pyFunc(svc, '_is_auto_maintained_time_column')
  assert.match(fn, /if column not in _AUTO_MAINTAINED_TIME_COLUMNS/, '列名白名单判定丢失')
  assert.match(fn, /"DATE" in t or "TIMESTAMP" in t/, '类型判定丢失 → start_date 之类也会被封只读')
})

test('M20：判定语义对照表（谁该只读、谁不该）', () => {
  const names = ['created_at', 'updated_at', 'create_time', 'update_time']
  const expect = (col, type) => names.includes(col) && /DATE|TIMESTAMP/.test(type.toUpperCase())
  assert.ok(expect('created_at', 'DATETIME'))
  assert.ok(!expect('start_date', 'DATE'), '业务日期列不该被当系统列')
  assert.ok(!expect('published_at', 'DATETIME'), '运营可编辑的发布时间不该被锁')
  assert.ok(!expect('created_at', 'VARCHAR'), '同名列但非时间类型不该被锁')
})

// ============================================================ D15 合法数据被拒

test('D15：单日投放合法（区间含首尾），只有倒序才拒，且报错说中文', () => {
  const svc = read(`${BACKEND}services/ad_service.py`)
  const fn = pyFunc(svc, 'create_placement')
  assert.match(fn, /if start_date > end_date:/, '仍是 >=：同一天被误拒')
  assert.doesNotMatch(fn, /if start_date >= end_date:/, '旧校验复现')
  assert.match(fn, /结束日期不能早于开始日期/, '用户看不到中文说明')
  assert.doesNotMatch(fn, /message="start_date 必须早于 end_date"/, '英文字段名回显复现')
  assert.match(fn, /"field": "dateRange"/, '字段级错误未指向日期区间')

  const view = read(`${SRC}views/ad/AdPlacements.vue`)
  assert.match(view, /区间含首尾/, '界面没说清同一天可投')
  assert.match(view, /dateRange: \[/, '表单没有对 dateRange 的校验规则')
})

// ============================================================ D16 可见数据被截断

test('D16：素材下拉走远端搜索并显示「已显示 N / 共 M」，后端按名称模糊过滤', () => {
  const svc = read(`${BACKEND}services/ad_service.py`)
  const fn = pyFunc(svc, 'list_materials')
  assert.match(fn, /keyword: str \| None = None/, '服务层没有关键词参数')
  assert.match(fn, /AdMaterial\.name\.like/, '关键词没有落到 LIKE')
  assert.match(
    fn,
    /select\(func\.count\(AdMaterial\.id\)\)\.where\(\*conds\)/,
    '总数没跟着筛选条件 →「已显示 1 条 / 共 102 条」这种自相矛盾的提示'
  )
  assert.match(fn, /select\(AdMaterial\)\s*\.where\(\*conds\)/, '列表查询没跟着筛选条件')

  const router = read(`${BACKEND}routers/admin/ads.py`)
  assert.match(router, /keyword: str = Query\(None/, '接口没开关键词参数，前端搜索只能在已加载的 100 条内筛')

  const view = read(`${SRC}views/ad/AdPlacements.vue`)
  assert.match(view, /:remote-method="searchMaterials"/, 'filterable 仍在本地 100 条内搜')
  assert.match(view, /素材库共 \{\{ materialTotal \}\} 条/, '界面不报总数，运营会判定「素材没上传成功」')
  assert.match(view, /materialTotal\.value = data\.total \|\| 0/)
})

// ============================================================ H2 文案承诺没有的能力

test('H2：Bucket 文案不再承诺系统会自动拼 -{APPID}，且保存前真的会校验', () => {
  const cos = read(`${SRC}views/cos/CosConfig.vue`)
  assert.doesNotMatch(cos, /不含 -\{appid\} 后缀亦可/, '虚假承诺复现')
  assert.doesNotMatch(cos, /系统按 SecretId APPID 拼接/, '全仓没有拼接逻辑，这句是凭空承诺')
  assert.match(cos, /系统不会自动拼接后缀/)
  assert.match(cos, /const BUCKET_WITH_APPID = /, '文案改对了但没人校验')
  const save = slice(cos, 'async function handleSave', ['\nasync function ', '\nfunction '], 'handleSave')
  assert.match(save, /if \(bucketSuffixError\.value\) \{/, '校验没接进保存路径')

  // 后端确实原样透传 bucket、全仓没有 appid 拼接——文案与实现双向核对
  const client = read(`${BACKEND}cos/client.py`)
  assert.match(client, /"Bucket": settings\.COS_BUCKET/, '后端不再原样透传，需同步改文案与校验')
  assert.doesNotMatch(client, /appid/i, '后端若真的开始拼后缀，前端这道拦截就成了新的谎')
})

// ============================================================ C92 来源类型口径

test('C92：分享链接复核入库真的写 qrcode，界面把来源类型显示出来', () => {
  const cm = read(`${SRC}views/channel/CourseMaterials.vue`)
  const manual = slice(cm, 'async function doManual', ['\nasync function ', '\nfunction '], 'doManual')
  assert.match(manual, /source_type: manualSourceType\.value/, '仍固定提交 list → qrcode 永不产生')
  assert.doesNotMatch(manual, /source_type: 'list',/, '硬编码复现')
  const fill = slice(cm, 'function fillManualFromShare', ['\nasync function ', '\nfunction '], 'fillManualFromShare')
  assert.match(fill, /manualSourceType\.value = 'qrcode'/, '预填时没带上来源标记')
  assert.match(cm, /MATERIAL_SOURCE_TYPE/, '标签没走统一字典（FR-UX-405）')
  assert.doesNotMatch(cm, /（source_type=qrcode）/, '把英文枚举值当用户文案')
  assert.match(cm, /来源类型标记/, '入库前界面上看不到将要写入的来源类型')
  assert.ok(MATERIAL_SOURCE_TYPE.qrcode, 'qrcode 未登记 → 素材库筛不到，界面筛选项恒为空')
})

// ============================================================ C45 术语分工

test('C45：库内补录与渠道入库分开命名', () => {
  const lib = read(`${SRC}views/channel/MaterialLibrary.vue`)
  assert.match(lib, /label="库内手工新增素材"/)
  assert.match(lib, /title="库内手工新增素材"/)
  assert.doesNotMatch(lib, /label="手动录入素材"/, '又和菜单「素材录入」撞名')
  assert.match(lib, /素材录入/, '没有指向真正的渠道入库页')
})

// ============================================================ M77 / M78 / M84 文档与界面互核

test('M77：帮助文档写的审核动作名必须真的在界面上存在', () => {
  const help = read(`${SRC}views/help/Help.vue`)
  const detail = read(`${SRC}views/review/ReviewDetail.vue`)
  const list = read(`${SRC}views/review/ReviewList.vue`)

  assert.doesNotMatch(help, /「审核通过」/, '界面上没有这个名字的按钮')
  assert.doesNotMatch(help, /点击「驳回」/, '界面动作叫「打回」')
  for (const word of ['打回', '替换段落', '提交']) {
    assert.match(help, new RegExp(word), `文档漏掉动作「${word}」`)
    assert.ok(detail.includes(word), `界面里没有「${word}」，文档不该写它`)
  }
  assert.match(list, /批量打回/, '列表侧动作名核对失败')
  assert.match(help, /replaced/, '替换段落后的状态去向没交代（与 B1 的可追溯性同源）')
})

test('M78：文档不得描述界面上不存在的「重试」按钮（复核为误报，仅修文案）', () => {
  const help = read(`${SRC}views/help/Help.vue`)
  const detail = read(`${SRC}views/workflow/WorkflowDetail.vue`)
  assert.match(help, /从指定步骤重跑/)
  assert.match(detail, /从指定步骤重跑/, '文档承诺的入口在界面上并不存在')
  assert.doesNotMatch(help, /可点击「重试」/, '旧文案复现')
})

test('M84：文档里的脚本命令必须能在磁盘上找到文件', () => {
  const help = read(`${SRC}views/help/Help.vue`)
  assert.doesNotMatch(help, /python jmeter_test\//, '仓库根没有 jmeter_test/，照抄必报文件不存在')
  const scripts = help.match(/scripts\/jmeter_test\/[\w./-]+\.py/g) || []
  assert.ok(scripts.length >= 2, `文档里没有指向 scripts/jmeter_test 的真实命令（找到 ${scripts.length} 条）`)
  for (const rel of new Set(scripts)) {
    assert.ok(existsSync(new URL(`${REPO}${rel}`, import.meta.url)), `文档指向的脚本不存在：${rel}`)
  }
})

// ============================================================ §10.1 追溯：M4 条目不得成孤儿

test('M4 全部 24 条高危都有 FR 归属或被显式判否', () => {
  const prd = read(`${REPO}docs/需求规格说明书-UX优化.md`)
  const row = prd.split('\n').find((l) => /^\| M4 \| 24 \|/.test(l))
  assert.ok(row, '§10.1 的 M4 行找不到，追溯门失去意义')
  const ids = row
    .split('|')[3]
    .split('、')
    .map((s) => s.trim())
    .filter(Boolean)
  assert.equal(ids.length, 24, `M4 条目数变了（实际 ${ids.length}），请同步追溯门`)

  const covered = new Set()
  const rejected = new Set()
  for (const fr of prd.split('\n').filter((l) => /^\| FR-UX-\d+ \|/.test(l))) {
    const cells = fr.split('|')
    ;(cells[4] || '')
      .split(/[,、]/)
      .map((s) => s.trim())
      .filter((s) => /^[A-Z]+\d+$/.test(s))
      .forEach((s) => covered.add(s))
    const desc = cells.slice(5).join('|')
    if (/不进入实施范围|复核为误报|复核驳回/.test(desc)) {
      ids.filter((id) => desc.includes(id)).forEach((id) => rejected.add(id))
    }
  }
  const orphans = ids.filter((id) => !covered.has(id) && !rejected.has(id))
  assert.deepEqual(orphans, [], `M4 条目没有落到任何 FR：${orphans.join(', ')}`)
  assert.ok(rejected.has('C66') && rejected.has('M78'), '两条复核判否条目应被显式记录，避免又被当成待办')
})

test('M4 里程碑行的 FR 数与 §4 实际 FR 行数一致', () => {
  const prd = read(`${REPO}docs/需求规格说明书-UX优化.md`)
  const milestone = prd.split('\n').find((l) => /^\| M4 \|.*一致性/.test(l))
  const declared = Number(milestone.split('|')[4].trim())
  const frRows = prd
    .split('\n')
    .filter((l) => /^\| FR-UX-4\d\d \|/.test(l))
    .map((l) => l.split('|')[1].trim())
  assert.deepEqual(
    [...new Set(frRows)].sort(),
    ['FR-UX-401', 'FR-UX-402', 'FR-UX-403', 'FR-UX-404', 'FR-UX-405', 'FR-UX-406', 'FR-UX-407', 'FR-UX-408', 'FR-UX-409'],
    'M4 的 FR 清单变了，里程碑表要同步'
  )
  assert.equal(declared, frRows.length, `里程碑表声称 ${declared} 个 FR，实际 ${frRows.length} 行`)
})
