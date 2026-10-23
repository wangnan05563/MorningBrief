/**
 * T02898：AI / 通知配置页也要把「屏上的值是从哪来的」说清楚
 *
 * 后端语义（loaded / load_error / updated_at / fallback_fields）由
 * backend/tests/test_t02898_ai_notify_config_provenance.py 在真 HTTP 边界上断言。
 * 这里守前端接线，防的是 T02527 同款三类回退：
 *
 * 1. 把「请求成功」当成「值是库里那份」——读表失败时不禁存；
 * 2. 把元数据混进 form/草稿/提交体；
 * 3. 回落来源只写在注释里——页面不渲染 fallback_fields。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/config-provenance-ai-notify.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const AI = readFileSync(
  new URL('../../src/views/ai/AIConfig.vue', import.meta.url),
  'utf8',
)
const NOTIFY = readFileSync(
  new URL('../../src/views/notification/NotificationConfig.vue', import.meta.url),
  'utf8',
)

function block(source, start, end) {
  const from = source.indexOf(start)
  assert.notEqual(from, -1, `页面里找不到 ${start}`)
  const to = source.indexOf(end, from)
  assert.notEqual(to, -1, `页面里找不到 ${start} 之后的 ${end}`)
  return source.slice(from, to + end.length)
}

/** 取包含 labelText 的那个 IconButton 标签 */
function buttonContaining(source, labelText) {
  const at = source.indexOf(labelText)
  assert.notEqual(at, -1, `页面里找不到按钮 ${labelText}`)
  const open = source.lastIndexOf('<IconButton', at)
  assert.notEqual(open, -1, `${labelText} 不在 IconButton 里`)
  const close = source.indexOf('/>', at)
  assert.notEqual(close, -1, `${labelText} 所在按钮没有闭合`)
  return source.slice(open, close)
}

function guardBefore(source, fnStart, nextLine) {
  const fn = source.slice(source.indexOf(fnStart))
  return fn.slice(0, fn.indexOf(nextLine))
}

describe('T02898 读表失败必须禁存（AI 配置页）', () => {
  it('valuesNotLoaded 只认 loaded === false', () => {
    assert.match(
      AI,
      /const valuesNotLoaded = computed\(\(\) => provenance\.value\.loaded === false\)/,
    )
  })

  it('保存按钮 disabled 同时看 configReady 与 valuesNotLoaded', () => {
    assert.match(
      buttonContaining(AI, 'label="保存配置"'),
      /:disabled="!configReady \|\| valuesNotLoaded"/,
    )
  })

  it('handleSave 自己也要拦一遍', () => {
    const guard = guardBefore(AI, 'async function handleSave', 'saving.value = true')
    assert.match(guard, /if \(valuesNotLoaded\.value\) \{/)
    assert.match(guard, /已禁止保存/)
    assert.match(guard, /provenance\.value\.load_error/)
    assert.match(guard, /return/)
  })

  it('禁存原因在页面上说清楚，而不是只弹 toast', () => {
    const alert = block(AI, 'v-if="valuesNotLoaded"', '/>')
    assert.match(alert, /data-guide="ai-config-load-error"/)
    assert.match(alert, /provenance\.load_error/)
  })
})

describe('T02898 来源信息不进表单（AI 配置页）', () => {
  it('loadConfig 把四个元数据字段剥掉后才 assign', () => {
    assert.match(
      AI,
      /const \{ loaded, load_error, updated_at, fallback_fields, \.\.\.configValues \} = configData \|\| \{\}/,
    )
    assert.match(AI, /Object\.assign\(llmForm\.value, configValues\.llm\)/)
    assert.match(AI, /Object\.assign\(ttsForm\.value, configValues\.tts\)/)
    assert.match(AI, /Object\.assign\(imageForm\.value, configValues\.image\)/)
    assert.doesNotMatch(AI, /Object\.assign\(llmForm\.value, configData\.llm\)/)
    assert.doesNotMatch(AI, /Object\.assign\(ttsForm\.value, configData\.tts\)/)
  })

  it('提交体仍然只发 llm/tts/image 三段', () => {
    const body = block(AI, "await api.put('/ai/config', {", '})')
    for (const f of ['llm: llmForm.value', 'tts: ttsForm.value', 'image: imageForm.value']) {
      assert.ok(body.includes(f), `提交体缺少 ${f}`)
    }
    assert.doesNotMatch(body, /loaded|updated_at|fallback_fields|load_error/)
  })
})

describe('T02898 回落来源与修改时间要可见（AI 配置页）', () => {
  it('fallback_fields 按 llm./tts./image. 路径逐个点名', () => {
    assert.match(AI, /fallback_fields: fallback_fields \|\| \[\]/)
    assert.match(AI, /fields\.map\(fallbackLabel\)\.join\('、'\)/)
    assert.match(AI, /const sectionLabels = \{ llm: 'LLM', tts: 'TTS', image: '图片生成' \}/)
    assert.match(AI, /以下字段的值来自环境变量回落，库里并未保存/)
  })

  it('渲染 updated_at 与 fallbackNote，只在 loaded 为真时渲染', () => {
    const line = block(AI, 'class="config-provenance"', '</div>')
    assert.match(line, /data-guide="ai-config-provenance"/)
    assert.match(line, /updatedAtText/)
    assert.match(line, /fallbackNote/)
    const prov = AI.slice(
      AI.indexOf('class="config-provenance"') - 220,
      AI.indexOf('class="config-provenance"'),
    )
    assert.match(prov, /v-else-if="provenance\.loaded === true"/)
    assert.match(AI, /<span v-else>库里暂无记录<\/span>/)
  })
})

describe('T02898 读表失败必须禁存（通知配置页）', () => {
  it('valuesNotLoaded 只认 loaded === false', () => {
    assert.match(
      NOTIFY,
      /const valuesNotLoaded = computed\(\(\) => provenance\.value\.loaded === false\)/,
    )
  })

  it('保存与测试发送按钮都看 valuesNotLoaded（测试前会先保存）', () => {
    assert.match(
      buttonContaining(NOTIFY, 'label="保存配置"'),
      /:disabled="!configReady \|\| valuesNotLoaded"/,
    )
    assert.match(
      buttonContaining(NOTIFY, 'label="测试发送"'),
      /:disabled="!configReady \|\| valuesNotLoaded"/,
    )
  })

  it('handleSaveConfig 与 handleTestSend 各自再拦一遍', () => {
    for (const fn of ['async function handleSaveConfig', 'async function handleTestSend']) {
      const end = fn.includes('Save') ? 'saving.value = true' : 'testing.value = true'
      const guard = guardBefore(NOTIFY, fn, end)
      assert.match(guard, /if \(valuesNotLoaded\.value\) \{/, `${fn} 缺少读失败护栏`)
      assert.match(guard, /provenance\.value\.load_error/)
      assert.match(guard, /return/)
    }
  })

  it('禁存原因在页面上说清楚', () => {
    const alert = block(NOTIFY, 'v-if="valuesNotLoaded"', '/>')
    assert.match(alert, /data-guide="notification-load-error"/)
    assert.match(alert, /provenance\.load_error/)
  })
})

describe('T02898 来源信息不进表单（通知配置页）', () => {
  it('loadConfig 把四个元数据字段剥掉后才 assign', () => {
    assert.match(
      NOTIFY,
      /const \{ loaded, load_error, updated_at, fallback_fields, \.\.\.values \} = data \|\| \{\}/,
    )
    assert.match(NOTIFY, /Object\.assign\(configForm, \{/)
    assert.doesNotMatch(NOTIFY, /values\.loaded|values\.updated_at/)
    assert.match(NOTIFY, /email_smtp_port: values\.email_smtp_port \?\? 587/)
  })

  it('提交体仍然只发 configForm', () => {
    assert.match(NOTIFY, /saveNotificationConfig\(\{ \.\.\.configForm \}\)/)
  })
})

describe('T02898 回落来源与修改时间要可见（通知配置页）', () => {
  it('回落文案按「默认值」口径，不能照抄 .env', () => {
    assert.match(NOTIFY, /以下字段库里未保存，当前使用的是默认值/)
    assert.doesNotMatch(NOTIFY, /以下值来自环境变量回落/)
  })

  it('13 个通知字段都有可读名，逐个翻译而不是只报数量', () => {
    const labels = block(NOTIFY, 'const fallbackLabels = {', '}')
    for (const f of [
      'global_enabled',
      'failed_enabled',
      'review_enabled',
      'published_enabled',
      'dingtalk_webhook',
      'dingtalk_secret',
      'wecom_webhook',
      'email_smtp_host',
      'email_smtp_port',
      'email_smtp_user',
      'email_smtp_password',
      'email_to',
      'admin_base_url',
    ]) {
      assert.match(labels, new RegExp(`\\b${f}:`), `回落提示缺少字段 ${f} 的中文名`)
    }
    assert.match(NOTIFY, /fields\s*\.map\(\(f\) => fallbackLabels\[f\] \|\| f\)/)
  })

  it('渲染 updated_at 与 fallbackNote，只在 loaded 为真时渲染', () => {
    const line = block(NOTIFY, 'class="config-provenance"', '</div>')
    assert.match(line, /data-guide="notification-provenance"/)
    assert.match(line, /updatedAtText/)
    assert.match(line, /fallbackNote/)
    const prov = NOTIFY.slice(
      NOTIFY.indexOf('class="config-provenance"') - 220,
      NOTIFY.indexOf('class="config-provenance"'),
    )
    assert.match(prov, /v-else-if="provenance\.loaded === true"/)
    assert.match(NOTIFY, /<span v-else>库里暂无记录<\/span>/)
  })
})
