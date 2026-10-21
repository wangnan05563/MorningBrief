/**
 * INT-UX-04 / T02527：云端存储页要把「屏上的值是从哪来的」说清楚
 *
 * 后端语义（loaded / load_error / updated_at / fallback_fields 四个字段怎么算出来）
 * 由 backend/tests/test_int04_cos_config_provenance.py 在真 HTTP 边界上断言。
 * 这里守前端接线，防的是三类回退：
 *
 * 1. 把「请求成功」当成「值是库里那份」——读表失败时不禁存，管理员点保存
 *    就会拿默认值覆盖线上配置；
 * 2. 把元数据混进 form —— 草稿与提交体里多出 loaded/updated_at，
 *    脱敏字段排除逻辑（excludePaths）也会跟着失真；
 * 3. 回落来源只写在注释里 —— 页面不渲染 fallback_fields，
 *    库里空表 + .env 有旧值时，看上去仍像「配置已保存」。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/cos-config-provenance.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const VIEW = readFileSync(
  new URL('../../src/views/cos/CosConfig.vue', import.meta.url),
  'utf8',
)

/** 取模板块（含 start 的最早一行到 end 之后的第一个结束标签）里的一段，便于按块断言 */
function block(start, end) {
  const from = VIEW.indexOf(start)
  assert.notEqual(from, -1, `页面里找不到 ${start}`)
  const to = VIEW.indexOf(end, from)
  assert.notEqual(to, -1, `页面里找不到 ${start} 之后的 ${end}`)
  return VIEW.slice(from, to + end.length)
}

/** 取包含 labelText 的那个 IconButton 标签（属性顺序不参与断言） */
function buttonContaining(labelText) {
  const at = VIEW.indexOf(labelText)
  assert.notEqual(at, -1, `页面里找不到按钮 ${labelText}`)
  const open = VIEW.lastIndexOf('<IconButton', at)
  assert.notEqual(open, -1, `${labelText} 不在 IconButton 里`)
  const close = VIEW.indexOf('/>', at)
  assert.notEqual(close, -1, `${labelText} 所在按钮没有闭合`)
  return VIEW.slice(open, close)
}

describe('INT-UX-04 读表失败必须禁存', () => {
  it('valuesNotLoaded 只认 loaded === false，不吃 truthy 兜底', () => {
    assert.match(
      VIEW,
      /const valuesNotLoaded = computed\(\(\) => provenance\.value\.loaded === false\)/,
    )
  })

  it('保存按钮的 disabled 同时看 configReady 与 valuesNotLoaded', () => {
    assert.match(
      buttonContaining('label="保存配置"'),
      /:disabled="!configReady \|\| valuesNotLoaded"/,
    )
    // 测试连接不受影响：它不落库，读表失败时正该让人先试连通性
    const test = buttonContaining('label="测试连接"')
    assert.match(test, /:disabled="!configReady"/)
    assert.doesNotMatch(test, /valuesNotLoaded/)
  })

  it('handleSave 自己也要拦一遍（按钮 disabled 不等于函数不会被调用）', () => {
    const fn = VIEW.slice(VIEW.indexOf('async function handleSave'))
    const guard = fn.slice(0, fn.indexOf('saving.value = true'))
    assert.match(guard, /if \(valuesNotLoaded\.value\) \{/)
    assert.match(guard, /已禁止保存/)
    assert.match(guard, /provenance\.value\.load_error/)
    assert.match(guard, /return/)
  })

  it('禁存原因要在页面上说清楚，不能只弹一次 toast', () => {
    const alert = block('v-if="valuesNotLoaded"', '</el-alert>')
    assert.match(alert, /data-guide="cos-config-load-error"/)
    assert.match(alert, /provenance\.load_error/)
  })
})

describe('INT-UX-04 来源信息不进表单', () => {
  it('loadConfig 把四个元数据字段从响应里剥掉后才 assign', () => {
    assert.match(
      VIEW,
      /const \{ loaded, load_error, updated_at, fallback_fields, \.\.\.values \} = cfg/,
    )
    assert.match(VIEW, /Object\.assign\(form\.value, values\)/)
    assert.doesNotMatch(VIEW, /Object\.assign\(form\.value, cfg\)/)
  })

  it('提交体仍然只发五个可编辑字段', () => {
    const body = block('await saveCosConfig({', '})')
    for (const f of ['secret_id', 'secret_key', 'region', 'bucket', 'cdn_domain']) {
      assert.match(body, new RegExp(`form\\.value\\.${f}`))
    }
    assert.doesNotMatch(body, /loaded|updated_at|fallback_fields|load_error/)
  })
})

describe('INT-UX-04 回落来源与修改时间要可见', () => {
  it('fallbackNote 逐个字段翻译，而不是只报数量', () => {
    const labels = block('const fallbackLabels = {', '}')
    for (const f of ['secret_id', 'secret_key', 'region', 'bucket', 'cdn_domain']) {
      assert.match(labels, new RegExp(`\\b${f}:`), `回落提示缺少字段 ${f} 的中文名`)
    }
    assert.match(VIEW, /以下值来自环境变量回落，库里并未保存/)
  })

  it('页面渲染 updated_at 与 fallbackNote，且只在 loaded 为真时渲染', () => {
    const line = block('class="config-provenance"', '</div>')
    assert.match(line, /data-guide="cos-config-provenance"/)
    assert.match(line, /updatedAtText/)
    assert.match(line, /fallbackNote/)
    const prov = VIEW.slice(VIEW.indexOf('class="config-provenance"') - 200, VIEW.indexOf('class="config-provenance"'))
    assert.match(prov, /v-else-if="provenance\.loaded === true"/)
  })

  it('库里无记录要说「暂无记录」，不能留白让人以为已保存', () => {
    assert.match(VIEW, /<span v-else>库里暂无记录<\/span>/)
  })
})
