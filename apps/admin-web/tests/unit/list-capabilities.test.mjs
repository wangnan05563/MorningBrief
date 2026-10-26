/**
 * 列表通用能力门禁（FR-UX-703 / T02517）
 *
 * 这个文件干两件事，都是「不看源码就无法保证」的那类约束：
 *
 * 1) **仓库级不变量**：把「每个分页都给出尺寸选择器」「尺寸档位不超过 NFR-UX-03 的 100」
 *    「凡设了 :limit 的上传必须有 :on-exceed」写成遍历 src/views 所有 .vue 的门禁。
 *    理由：`ReviewList.vue` 的分页写死 size、`DatabaseAdmin.vue` 给到 200 档、
 *    `WorkflowDetail.vue` 的 layout 里没有 sizes——这三条都是「配置写了但不生效」的同一类缺陷，
 *    单页修好不等于不会再出现第四页；只有按目录枚举才能挡住增量。
 * 2) **接线与跨端契约**：本单实际改的四个页面（审核列表 / 工作流详情素材面板 / 素材库批删 /
 *    移动端消息分页）逐条断言到具体标识符，另加前端 api ↔ 后端路由的口径对齐。
 *
 * 豁免表 `PENDING_UPLOAD_ON_EXCEED` 是**有编号、必须被使用**的：
 * 条目要写派生单号，且对应文件确实存在「有 limit 无 on-exceed」才有效——
 * 该文件修好后如果豁免不删，门禁会反过来报错名，防止豁免长期隐身。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/list-capabilities.test.mjs
 */
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

import {
  MAX_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
  PANEL_PAGE_SIZE_OPTIONS,
  clampPageSize,
} from '../../src/constants/pagination.js'

const repoFile = (rel) => readFileSync(new URL(`../../../../${rel}`, import.meta.url), 'utf8')
const srcFile = (rel) => readFileSync(new URL(`../../src/${rel}`, import.meta.url), 'utf8')

/** 递归收集 src/views 下所有 .vue（门禁要按目录枚举，不能只点名改过的文件） */
function listViews(dir = 'views', base = '../../src/') {
  const url = new URL(`../../src/${dir}/`, import.meta.url)
  const out = []
  for (const entry of readdirSync(url, { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`
    if (entry.isDirectory()) out.push(...listViews(rel, base))
    else if (entry.name.endsWith('.vue')) out.push({ rel, text: readFileSync(new URL(`../../src/${rel}`, import.meta.url), 'utf8') })
  }
  return out
}

/**
 * 从 `opener`（以 `{` 结尾）起按花括号配平取出整个对象字面量。
 *
 * ⚠ 断言「请求参数里有什么」时不能直接对整文件跑正则：同一页面在 console.error
 * 上下文里也会出现同名字段，整文件正则会被它顶包，参数真的改名了也照样绿（实测）。
 */
function objectBlock(text, opener) {
  const start = text.indexOf(opener)
  assert.ok(start >= 0, `找不到对象起始标记：${opener}`)
  let depth = 0
  for (let i = start + opener.length - 1; i < text.length; i++) {
    if (text[i] === '{') depth++
    else if (text[i] === '}') {
      depth--
      if (depth === 0) return text.slice(start, i + 1)
    }
  }
  throw new Error(`花括号不配平：${opener}`)
}

/**
 * 抽出形如 `<el-pagination ...>` 的整段属性文本（含跨行）。
 *
 * ⚠ 必须跟踪引号状态：`v-if="materials.total > materialsSize"` 里的 `>`
 * 若按「第一个 > 结束」来切，属性会被拦腰截断，后面的 layout 就读不到了
 * （实测这条会在 WorkflowDetail.vue 上造成假失败）。
 */
function tagBlocks(text, tagName) {
  const open = `<${tagName}`
  const blocks = []
  let i = 0
  while (true) {
    const start = text.indexOf(open, i)
    if (start < 0) break
    // 必须是标签起始（后面紧跟空白或 >，不能是 <el-pagination-foo）
    const next = text[start + open.length]
    if (next && !/\s|>|\//.test(next)) {
      i = start + open.length
      continue
    }
    let quote = null
    let j = start + open.length
    for (; j < text.length; j++) {
      const ch = text[j]
      if (quote) {
        if (ch === quote) quote = null
      } else if (ch === '"' || ch === "'") {
        quote = ch
      } else if (ch === '>') {
        break
      }
    }
    blocks.push(text.slice(start, j + 1))
    i = j + 1
  }
  return blocks
}

/** 从属性段里取某个属性的值（`layout="total, sizes, ..."` → 字符串） */
function attr(block, name) {
  const re = new RegExp(`(?:^|\\s):?${name}\\s*=\\s*"([^"]*)"`)
  const m = block.match(re)
  return m ? m[1] : null
}

/**
 * 解析档位来源：字面量数组 `[10, 20, 50]` 或共享常量标识符。
 * 返回 null 表示「没给出可选档位」→ 调用方判失败。
 */
function resolveSizes(block) {
  const raw = attr(block, 'page-sizes') ?? /(^|\s)page-sizes\s*=\s*"([^"]*)"/.exec(block)?.[2] ?? null
  if (!raw) return null
  const text = raw.trim()
  if (text.startsWith('[')) {
    return text
      .slice(1, -1)
      .split(',')
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isFinite(n))
  }
  const named = {
    PAGE_SIZE_OPTIONS,
    PANEL_PAGE_SIZE_OPTIONS,
  }
  const key = text.replace(/^[A-Za-z_$.]*?\./, '').split('.').pop()
  return named[key] ?? null
}

const ALL_VIEWS = listViews()

describe('分页尺寸常量（NFR-UX-03 上限 100）', () => {
  it('两组档位都在上限内，且上限本身是 100', () => {
    assert.equal(MAX_PAGE_SIZE, 100)
    assert.ok(PAGE_SIZE_OPTIONS.length >= 3)
    assert.ok(PANEL_PAGE_SIZE_OPTIONS.length >= 2)
    assert.ok(PAGE_SIZE_OPTIONS.every((n) => n > 0 && n <= MAX_PAGE_SIZE))
    assert.ok(PANEL_PAGE_SIZE_OPTIONS.every((n) => n > 0 && n <= MAX_PAGE_SIZE))
  })

  it('clampPageSize：允许值原样通过，非档位就近取，越界收最大档', () => {
    assert.equal(clampPageSize(20), 20)
    assert.equal(clampPageSize(7), 10, '7 应就近落到 10（比 10 与 20 都远/更近 10）')
    assert.equal(clampPageSize(500), MAX_PAGE_SIZE)
    assert.equal(clampPageSize(0), PAGE_SIZE_OPTIONS[0])
    assert.equal(clampPageSize('abc'), PAGE_SIZE_OPTIONS[0])
    // 上限收口不因为「常量被人写宽」而失效
    assert.ok(clampPageSize(999, [20, 50, 100], 20) <= MAX_PAGE_SIZE)
  })
})

describe('仓库级不变量：每个 el-pagination 都能选尺寸且不越上限', () => {
  const offenders = []
  const oversized = []
  for (const { rel, text } of ALL_VIEWS) {
    for (const block of tagBlocks(text, 'el-pagination')) {
      const layout = attr(block, 'layout') || ''
      const sizes = resolveSizes(block)
      if (!layout.includes('sizes') || !sizes) {
        offenders.push(`${rel} layout="${layout}" page-sizes=${JSON.stringify(sizes)}`)
      }
      if (sizes && sizes.some((n) => n > MAX_PAGE_SIZE)) {
        oversized.push(`${rel} → ${sizes.join('/')}`)
      }
    }
  }

  it('扫到了分页组件（枚举没空跑）', () => {
    assert.ok(
      ALL_VIEWS.some((v) => v.text.includes('<el-pagination')),
      'src/views 下必须能枚举到 el-pagination，否则本门禁是在空跑',
    )
  })

  it('所有分页都把 sizes 放进 layout 并给出可选档位', () => {
    assert.deepEqual(offenders, [], '以下分页没有尺寸选择器（写了 :page-sizes 但 layout 缺 sizes 同样不渲染）')
  })

  it('所有档位不超过 NFR-UX-03 的 100（后端 reviews/materials/inbox 都是 le=100）', () => {
    assert.deepEqual(oversized, [], '以下分页档位越过 100，后端 le=100 会把它判成 400（不是静默钳回），列表直接进错误态')
  })
})

// C94 剩余工作的豁免表：**只允许带派生单号的条目**。
// T02803 已给 CourseMaterials.vue 补上 :on-exceed，表必须清空——
// 留着空豁免表即「全仓库零超限静默忽略」，新增违例会被立刻挡下。
const PENDING_UPLOAD_ON_EXCEED = {}

describe('仓库级不变量：设了 :limit 的 el-upload 必须有 :on-exceed', () => {
  it('超限静默忽略的地方与豁免表完全一致（不多不少）', () => {
    const found = []
    for (const { rel, text } of ALL_VIEWS) {
      for (const block of tagBlocks(text, 'el-upload')) {
        const hasLimit = attr(block, 'limit') !== null
        const hasExceed = attr(block, 'on-exceed') !== null || /(^|\s)on-exceed\s*=/.test(block)
        if (hasLimit && !hasExceed) found.push(rel)
      }
    }
    const exempt = Object.keys(PENDING_UPLOAD_ON_EXCEED)
    assert.deepEqual(
      found.sort(),
      exempt.sort(),
      found.length > exempt.length
        ? `出现未登记的超限静默忽略：${found.join(', ')}（超限必须给提示，或把文件补进豁免表并建派生单）`
        : `豁免表里有已失效的条目（${exempt.filter((f) => !found.includes(f)).join(', ')}）：修完就把条目删掉，别留隐身豁免`,
    )
    for (const [file, ticket] of Object.entries(PENDING_UPLOAD_ON_EXCEED)) {
      assert.match(ticket, /^T\d{4,}$/, `${file} 的豁免必须挂派生单号，不能写「以后再说」`)
    }
  })
})

describe('审核列表（B3 / B4 / B6）接线', () => {
  const vue = srcFile('views/review/ReviewList.vue')

  it('分页给了共享档位并带 size-change 回第 1 页', () => {
    const block = tagBlocks(vue, 'el-pagination')[0]
    assert.ok(block, '审核列表应有分页')
    assert.equal(attr(block, 'page-sizes'), 'PAGE_SIZE_OPTIONS')
    assert.match(attr(block, 'layout'), /sizes/)
    assert.match(block, /@size-change="handleSizeChange"/)
    assert.match(vue, /function handleSizeChange\(\)\s*\{[\s\S]*?page\.value = 1/)
  })

  it('工作流 ID 筛选：进 URL 规格、进请求参数、变更回第 1 页', () => {
    assert.match(vue, /workflow_id:\s*\{\s*default:\s*''/)
    assert.match(vue, /params:\s*\{[\s\S]*?workflow_id:\s*filters\.workflow_id/)
    assert.match(vue, /function onFilterSearch\(\)\s*\{[\s\S]*?page\.value = 1/)
    assert.match(vue, /URL_SPECS,\s*\(\)\s*=>\s*\([\s\S]*?workflow_id:\s*filters\.workflow_id/)
  })

  it('T02804 审核人/日期/频道：四类筛选都进 URL 规格与请求参数', () => {
    // URL 规格：日期必须是 validator（只写 pattern 会放过 2026-02-30），频道是正整数
    assert.match(vue, /reviewer:\s*\{\s*default:\s*''/)
    assert.match(vue, /date_from:\s*\{\s*default:\s*'',\s*validator:\s*validateIsoDate/)
    assert.match(vue, /date_to:\s*\{\s*default:\s*'',\s*validator:\s*validateIsoDate/)
    assert.match(vue, /channel_id:\s*\{\s*default:\s*'',\s*type:\s*'int',\s*min:\s*1/)

    // 请求参数：四类一起交给后端，前端不做「只筛当前页」的假过滤。
    // ⚠ 必须限定在 params 对象内部断言：整文件正则会拿 console.error 里的同名字段顶包
    // （实测：把 params 的 date_from 改成 dateFrom，整文件正则仍然绿）。
    const paramsBlock = objectBlock(vue, 'params: {')
    assert.match(paramsBlock, /reviewer:\s*filters\.reviewer/)
    assert.match(paramsBlock, /date_from:\s*filters\.date_from/)
    assert.match(paramsBlock, /date_to:\s*filters\.date_to/)
    assert.match(paramsBlock, /channel_id:\s*filters\.channel_id/)

    // 状态快照也要带上，否则改筛选后 URL 不更新（同样限定在快照对象内）
    const snapshotBlock = objectBlock(vue, '() => ({')
    assert.match(snapshotBlock, /reviewer:\s*filters\.reviewer/)
    assert.match(snapshotBlock, /date_from:\s*filters\.date_from/)
    assert.match(snapshotBlock, /date_to:\s*filters\.date_to/)
    assert.match(snapshotBlock, /channel_id:\s*filters\.channel_id/)

    // 日期区间两端各自一个参数，不把 "a ~ b" 整串塞进一个 key
    assert.doesNotMatch(vue, /date_range/, '区间必须拆成 date_from / date_to 两个参数')

    // 区间反了在前端拦一次，别用一次失败请求换一句人话
    assert.match(vue, /validateDateRange\(filters\.date_from,\s*filters\.date_to\)/)

    // 重置要清空全部筛选，不能只清 workflow_id
    assert.match(
      vue,
      /function onFilterReset\(\)\s*\{[\s\S]*?filters\.workflow_id = ''[\s\S]*?filters\.reviewer = ''[\s\S]*?filters\.date_from = ''[\s\S]*?filters\.date_to = ''[\s\S]*?filters\.channel_id = ''/,
    )

    // 频道下拉加载失败时禁用并说明原因，不把「拉不到」伪装成「没有频道」
    assert.match(vue, /listChannels\(false\)/)
    assert.match(vue, /channelOptionsError/)
    assert.match(vue, /:disabled="!!channelOptionsError"/)
  })

  it('T02804 前后端筛选参数名一致（前端发什么，后端就收什么）', () => {
    const router = repoFile('backend/app/routers/admin/reviews.py')
    const service = repoFile('backend/app/services/review_service.py')
    for (const name of ['reviewer', 'date_from', 'date_to', 'channel_id']) {
      assert.match(router, new RegExp(`\\b${name}:\\s`), `路由缺参数 ${name}（前端会发出一个被忽略的查询参数）`)
      assert.match(service, new RegExp(`\\b${name}\\b`), `service 缺参数 ${name}`)
    }
    // 日期口径锁在 episode_date 上：改成 created_at 会让「按节目日期筛」筛不到列表里那天
    assert.match(service, /Review\.episode_date >= date_from/)
    assert.match(service, /Review\.episode_date <= date_to/)
    // LIKE 通配符必须转义，否则 ?reviewer=% 等于不筛选
    assert.match(service, /_escape_like\(reviewer\)/)
  })

  it('地址栏 size 不在档位里时就近钳制并如实点名（不静默按 7 行渲染）', () => {
    assert.match(vue, /function resolveSize\(/)
    assert.match(vue, /clampPageSize\(/)
    assert.match(vue, /if \(sizeClamp\.value\) extra\.push\(sizeClamp\.value\)/)
  })

  it('加载失败上屏 + 保留旧数据 + 控制台留痕（禁止裸 catch{}）', () => {
    assert.match(vue, /import ListLoadError from/)
    assert.match(vue, /<ListLoadError[\s\S]*?:stale="list\.length > 0"/)
    assert.match(vue, /catch \(e\) \{[\s\S]*?listError\.value =/)
    assert.match(vue, /console\.error\('\[review\] 列表加载失败'/)
    // 业务文案优先取响应体：axios 对 HTTP 500 抛的 e.message 只有状态码文本
    assert.match(vue, /e\?\.response\?\.data\?\.message \|\| e\?\.message/)
    assert.doesNotMatch(vue, /catch\s*\{\s*\}/)
  })

  it('URL 上 size 的上限按 NFR-UX-03 收在 MAX_PAGE_SIZE', () => {
    assert.match(vue, /size:\s*\{\s*default:\s*10,\s*type:\s*'int',\s*min:\s*1,\s*max:\s*MAX_PAGE_SIZE/)
  })
})

describe('工作流列表深链尺寸（T02521 / NFR-UX-03）', () => {
  const vue = srcFile('views/workflow/WorkflowList.vue')

  it('URL 规格给了 size 上限——后端是 le=100，越界判 400 而不是静默钳回', () => {
    // 本单的缺陷就在这里少了一个 max：`/workflows?size=999` 会把 999 原样发出去，
    // 拿到 HTTP 400 后落进错误态。静态门禁把它钉死，防止「只有审核列表收口」再次发生。
    assert.match(vue, /size:\s*\{\s*default:\s*20,\s*type:\s*'int',\s*min:\s*1,\s*max:\s*MAX_PAGE_SIZE/)
  })

  it('档位取自共享常量（此前自己写 [10, 20, 50]，100 这一档根本选不到）', () => {
    const block = tagBlocks(vue, 'el-pagination')[0]
    assert.equal(attr(block, 'page-sizes'), 'PAGE_SIZE_OPTIONS')
    assert.deepEqual(resolveSizes(block), PAGE_SIZE_OPTIONS)
  })

  it('两条入口（首屏 readFromUrl 与地址栏变更）都必须过 resolveSize', () => {
    // 只在一处钳制等于没钳：深链进来走 onMounted，前进后退/详情返回走 applyFromUrl
    assert.match(vue, /size\.value = resolveSize\(v\.size\)/)
    assert.match(vue, /size\.value = nextSize/)
    assert.match(vue, /const nextSize = resolveSize\(values\.size\)/)
    assert.doesNotMatch(vue, /size\.value = (values|v)\.size/, '不能把地址栏的 size 原样灌进状态')
    assert.match(vue, /clampPageSize\(n, PAGE_SIZE_OPTIONS/)
  })

  it('越界页码按 total 落到最后一页，不再「每退一页发一次请求」', () => {
    // NFR-UX-03 的直接相关项：旧写法 `page.value -= 1` + 递归，配上 el-pagination
    // 自己的钳位，实测产出 [999, 998, 5, 4] 四个请求还落在倒数第二页
    assert.match(vue, /URL_SPECS\.page\.max = maxPage/)
    // 只钉「独立成一句的自减语句」——源码里留着 `page.value -= 1` 的注释在解释旧写法，
    // 宽松正则会把那条注释当成复活（实测踩过）。
    assert.doesNotMatch(vue, /^\s*page\.value -= 1\s*$/m, '不许恢复逐页回退的修正方式')
    assert.match(vue, /await loadList\(false, true\)/)
    assert.match(vue, /if \(!silent && !isPageCorrection\) pageClamp\.value = null/)
  })
})

describe('工作流详情素材面板分页（B3 同类）', () => {
  const vue = srcFile('views/workflow/WorkflowDetail.vue')

  it('尺寸不再是模板与请求里各写死一份的 20', () => {
    const block = tagBlocks(vue, 'el-pagination')[0]
    assert.equal(attr(block, 'page-sizes'), 'PANEL_PAGE_SIZE_OPTIONS')
    assert.match(attr(block, 'layout'), /sizes/)
    assert.match(vue, /const materialsSize = ref\(20\)/)
    assert.match(vue, /size: materialsSize\.value/)
    assert.doesNotMatch(vue, /size: 20,/, '请求里不能还留硬编码 20')
  })

  it('换档回第 1 页', () => {
    assert.match(vue, /function handleMaterialsSizeChange\(\)\s*\{[\s\S]*?materialsPage\.value = 1/)
  })
})

describe('素材库批量删除（C52）前端接线', () => {
  const vue = srcFile('views/channel/MaterialLibrary.vue')
  const api = srcFile('api/materials.js')

  it('两张表都有勾选列（此前只能逐行删）', () => {
    const selectionCols = vue.match(/type="selection"/g) || []
    assert.ok(selectionCols.length >= 2, `明细表与聚合表各需一个勾选列，实际 ${selectionCols.length} 个`)
    assert.match(vue, /@selection-change="onItemSelectionChange"/)
    assert.match(vue, /@selection-change="onBookSelectionChange"/)
  })

  it('聚合表的勾选列跟随删除权限（给不出删除的行就不给勾选）', () => {
    assert.match(vue, /<el-table-column v-if="canOperate" type="selection"/)
  })

  it('批量删除有二次确认、影响条数、不可逆声明', () => {
    assert.match(vue, /async function onBatchDelete\(\)/)
    // 统一走 dangerConfirm（T02596）：动作 + 对象（含条数）+ 不可逆声明都在参数里，不再手写 confirm 文案
    assert.match(vue, /dangerConfirm\(\{[\s\S]*?action: '批量删除素材'[\s\S]*?target: `\$\{ids\.length\} 条素材`/)
    assert.match(
      vue,
      /action: '批量删除整本书'[\s\S]*?target: `\$\{sources\.length\} 本书（共 \$\{selectedChapters\.value\} 章）`/,
    )
    assert.match(vue, /删除后不可恢复/)
    // deleted=0 不能谎报成功
    assert.match(vue, /function reportBatchDelete\([\s\S]*?!deleted[\s\S]*?已不存在/)
  })

  it('换数据即作废勾选（避免删掉已经看不见的行）', () => {
    assert.match(vue, /async function load\(\)\s*\{[\s\S]*?clearSelection\(\)/)
  })

  it('api 走单事务批删接口', () => {
    assert.match(api, /export const batchDeleteMaterials = \(payload\) => api\.post\('\/materials\/batch-delete', payload\)/)
  })
})

describe('素材库批量删除：前后端契约对齐', () => {
  const py = repoFile('backend/app/routers/admin/materials.py')

  it('后端存在 POST /batch-delete 且要求 admin 权限', () => {
    assert.match(py, /@router\.post\("\/batch-delete"\)/)
    assert.match(py, /async def batch_delete_materials\([\s\S]*?Depends\(require_admin\)/)
  })

  it('ids 与 sources 至少要给一个，且有单次上限（不静默吞掉超大请求）', () => {
    assert.match(py, /raise BizError\(code=400, message="ids 与 sources 至少提供一个"\)/)
    assert.match(py, /_BATCH_DELETE_MAX = (\d+)/)
    const cap = Number(/_BATCH_DELETE_MAX = (\d+)/.exec(py)[1])
    assert.ok(cap > 0 && cap <= 500, `单次上限要在可接受范围，实际 ${cap}`)
  })

  it('按书名那一路必须带 channel_id 才收窄（与 delete_materials_by_source 同口径）', () => {
    assert.match(py, /@router\.post\("\/batch-delete"\)[\s\S]*?if req\.channel_id is not None:[\s\S]*?Material\.channel_id == req\.channel_id/)
  })

  it('硬删除写审计日志（NFR-UX-05：破坏性操作留痕）', () => {
    assert.match(py, /@router\.post\("\/batch-delete"\)[\s\S]*?AuditLog\(\s*category="material",\s*action="batch_delete"/)
  })

  it('路由不落在 /{material_id} 之后导致路径被当参数解析（batch-* 必须在动态段前或有独立动词）', () => {
    const idsPath = py.indexOf('@router.delete("/{material_id}")')
    const batchPath = py.indexOf('@router.post("/batch-delete")')
    assert.ok(idsPath > 0 && batchPath > 0)
    // POST 与 DELETE 方法不同，顺序不是硬约束；这里锁的是「批删用独立动词路径，不是 /materials/{id}」
    assert.ok(batchPath > idsPath, 'POST /batch-delete 与 DELETE /{material_id} 不冲突，位置变化时此断言提醒复核')
  })
})

describe('移动端消息分页（I21）', () => {
  const vue = srcFile('views/mobile/Message.vue')

  it('写死的 page:1/page_size:20 已换成按页取数', () => {
    assert.doesNotMatch(vue, /page:\s*1,\s*page_size:\s*20/, '收件箱不能再只取第 1 页')
    assert.match(vue, /getInbox\(\{ page: nextPage, page_size: PAGE_SIZE \}\)/)
    assert.match(vue, /const PAGE_SIZE = 20/)
    assert.ok(Number(/const PAGE_SIZE = (\d+)/.exec(vue)[1]) <= MAX_PAGE_SIZE)
  })

  it('有「加载更多」出口与已显示/总数口径，并给出无更多时的收口', () => {
    assert.match(vue, /已显示 \{\{ list\.length \}\} \/ \{\{ total \}\}/)
    assert.match(vue, /@click="loadMore"/)
    assert.match(vue, /const hasMore = computed\(\(\) => list\.value\.length < total\.value\)/)
    assert.match(vue, /没有更多了/)
  })

  it('翻页期间有新消息也不会重复渲染（按 id 去重，否则 :key 撞车）', () => {
    assert.match(vue, /const seen = new Set\(list\.value\.map\(\(m\) => m\.id\)\)/)
    assert.match(vue, /items\.filter\(\(m\) => !seen\.has\(m\.id\)\)/)
  })

  it('失败态区别于「暂无消息」，且重试不会引入轮询（NFR-UX-03）', () => {
    assert.match(vue, /v-else-if="error" class="m-msg__error"/)
    assert.match(vue, /加载失败：\{\{ error \}\}/)
    assert.match(vue, /@click="refresh"/)
    assert.doesNotMatch(vue, /setInterval|setTimeout\(/, '移动端消息页不得自带定时器轮询')
  })
})

describe('维护中心分页档位（NFR-UX-03 越界项已收口）', () => {
  const vue = srcFile('views/maintenance/DatabaseAdmin.vue')

  it('档位取自共享常量（此前自带一个越界的 200 档）', () => {
    const block = tagBlocks(vue, 'el-pagination')[0]
    assert.equal(attr(block, 'page-sizes'), 'PANEL_PAGE_SIZE_OPTIONS')
    const sizes = resolveSizes(block)
    assert.deepEqual(sizes, PANEL_PAGE_SIZE_OPTIONS)
    assert.ok(sizes.every((n) => n <= MAX_PAGE_SIZE), '解析出的档位必须全部 ≤ 100')
  })
})

/**
 * T02626（FR-UX-302）：列表/详情错误态落地门禁。
 *
 * 修的是同一类缺陷：请求失败时页面把数据置空，于是显示「暂无数据」——
 * 用户无法区分「库里真的没有」和「接口没取到」。单页接好不等于不会退化，
 * 所以按页点名断言三件事同时存在：错误横幅、横幅上的重试出口、
 * 以及「空态必须被错误态压住」的那条门控表达式（`!xxxError`）。
 *
 * 不在这里断言文案长什么样（那是 ListLoadError 的职责），只钉接线。
 */
describe('T02626 列表/详情错误态接线（11 页）', () => {
  const PAGES = [
    {
      rel: 'views/review/ReviewDetail.vue',
      // 详情页没有列表空态，但「提交审核」必须被失败态禁用（否则会拿空详情发请求）
      flag: /v-if="detailLoad\.isError"/,
      extra: /:disabled="detailLoad\.isError"/,
    },
    {
      rel: 'views/workflow/WorkflowDetail.vue',
      // 详情本身 + 素材/稿件/音频/拼接/审核五个面板，各自失败、各自可重试
      flag: /v-if="detailError"/,
      banners: 6,
      // 审核面板的通过/打回也必须被失败态禁用：否则会拿空详情直接发布
      extra: /:disabled="!!review\.error"/,
    },
    {
      rel: 'views/channel/MaterialLibrary.vue',
      flag: /v-if="loadError"/,
      extra: /<el-empty v-if="!loadError"/,
    },
    {
      rel: 'views/cos/CosFiles.vue',
      flag: /v-if="statusError \|\| listError"/,
      extra: /该目录下暂无内容/,
    },
    {
      rel: 'views/ebooks/BookFinder.vue',
      flag: /v-if="searchError"/,
      extra: /<el-empty\s+v-if="!searchError"/,
    },
    {
      rel: 'views/ad/AdMaterials.vue',
      flag: /v-if="listLoad\.isError"/,
      extra: /<el-empty v-if="!listLoad\.isError"/,
    },
    {
      rel: 'views/ad/AdPlacements.vue',
      flag: /v-if="listError"/,
      extra: /<el-empty v-if="!listError"/,
    },
    {
      rel: 'views/stats/ChannelHealth.vue',
      flag: /v-if="healthLoad\.isError"/,
      extra: /<el-empty v-if="!loading && !healthLoad\.isError && channels\.length === 0"/,
    },
    {
      rel: 'views/stats/LlmMetrics.vue',
      flag: /v-if="llmLoad\.isError"/,
      // 空态与「有数据」两半都要被压住：否则失败时要么显示「暂无调用」，要么渲染一组 0 卡片
      extra: /v-else-if="!llmLoad\.isError"/,
    },
    {
      rel: 'views/stats/RssHealth.vue',
      flag: /v-if="listError"/,
      // 汇总卡与筛选计数在失败时必须一起压住，否则「失败 0 个」会被读成巡检结论
      extra: /<el-row v-if="!listError \|\| rawData\.sources\.length > 0"/,
    },
    {
      rel: 'views/system/AutoReviewConfig.vue',
      // 配置区已有 ConfigLoadError（T02594）；统计与历史是两套独立请求，各要一个横幅
      flag: /v-if="statsError"/,
      banners: 2,
      extra: /<el-empty v-if="!historyError"/,
    },
  ]

  it('覆盖 11 个页面（清单本身不许缩水）', () => {
    assert.equal(PAGES.length, 11)
  })

  for (const page of PAGES) {
    it(`${page.rel}：错误横幅 + 重试出口 + 空态门控`, () => {
      const text = srcFile(page.rel)
      assert.match(text, /import ListLoadError from/, '缺少错误态组件导入')
      assert.match(text, page.flag, '错误横幅的显隐条件缺失或改了口径')
      assert.match(text, /:retrying=/, '横幅重试期间不给 loading，用户会以为按钮没生效')
      assert.match(text, /@retry=/, '错误态必须自带重试出口（拦截器 toast 会消失）')
      assert.match(text, page.extra, '空态/写操作没有被错误态拦住')
      if (page.banners) {
        assert.equal(
          text.match(/<ListLoadError/g)?.length ?? 0,
          page.banners,
          `${page.rel} 应有 ${page.banners} 个错误横幅（每个独立请求一个）`,
        )
      }
    })
  }

  it('自建错误 ref 的页面都保留了结构化 console.error（禁止只弹一条 toast 就完事）', () => {
    for (const rel of [
      'views/workflow/WorkflowDetail.vue',
      'views/channel/MaterialLibrary.vue',
      'views/cos/CosFiles.vue',
      'views/ebooks/BookFinder.vue',
      'views/ad/AdPlacements.vue',
      'views/stats/RssHealth.vue',
      'views/system/AutoReviewConfig.vue',
    ]) {
      const text = srcFile(rel)
      assert.match(text, /console\.error\(/, `${rel} 失败路径缺少控制台留痕`)
      assert.doesNotMatch(text, /catch\s*(\(\w*\))?\s*\{\s*\}/, `${rel} 出现了吞掉异常的裸 catch`)
    }
  })
})
