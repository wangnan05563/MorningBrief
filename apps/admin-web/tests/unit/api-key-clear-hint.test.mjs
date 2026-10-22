/**
 * F3：清空密钥这件事，界面必须说实话（FR-UX-101 / ACC-UX-101）
 *
 * 原缺陷的一半在文档/代码口径，另一半在界面：用户把 API Key 框清空 → 保存 →
 * 提示成功 → 重进页面脱敏值还在，界面上没有任何地方说明「留空是不修改」。
 * 三处密钥输入框（LLM / TTS / 图片）都要有这句提示，且 LLM 那处要指路
 * 「恢复初始配置」（那是唯一真的会清空 llm_api_key 的通道）。
 *
 * 顺带钉住前端的一条既有约定：提交时把脱敏值折算成空串回传。
 * 正因为这条约定存在，后端才**不能**把空串解释成「清除」——否则用户只改
 * base_url 也会把线上密钥抹掉。这个断言是给下一个想「顺手修 F3」的人看的。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/api-key-clear-hint.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const VIEW = readFileSync(
  new URL('../../src/views/ai/AIConfig.vue', import.meta.url),
  'utf8',
)
const SERVICE = readFileSync(
  new URL('../../../../backend/app/services/ai_config_service.py', import.meta.url),
  'utf8',
)

function countMatches(re, src) {
  return (src.match(re) || []).length
}

describe('F3 密钥留空语义在界面上说明白', () => {
  it('三处密钥输入框都写明「留空＝不修改」', () => {
    const hints = countMatches(/留空＝不修改/g, VIEW)
    assert.ok(hints >= 3, `只有 ${hints} 处提示，LLM/TTS/图片三处都要有`)
    assert.match(VIEW, /清空这一栏并保存不会删除已保存的/)
  })

  it('LLM 那处指路到真正会清空的入口', () => {
    assert.match(VIEW, /要清除请点右上角「恢复初始配置」/, '不给指路，用户只能反复试「清空+保存」')
    assert.match(VIEW, /label="恢复初始配置"/, '指了一个不存在的按钮')
    assert.match(VIEW, /:disabled="!configReady"\s*\n\s*style="margin-left: auto"\s*\n\s*label="恢复初始配置"/, '加载失败时这个按钮还能点，等于在未知状态下清库')
  })

  it('后端留空的语义仍是「不写入」，前端脱敏折算仍成立', () => {
    assert.match(SERVICE, /if api_key and not _is_masked\(api_key\):/, '实现被改成「空串即清除」，界面上的提示就全错了')
    assert.match(VIEW, /key\.startsWith\('\*\*\*\*'\) \? '' : key/, '脱敏值不再折算成空串，前后端口径要一起重算')
  })

  it('文档口径不许再回到「空字符串清除」（F3 的原始矛盾）', () => {
    assert.doesNotMatch(SERVICE, /空字符串(视为)?清除/, 'docstring 又在承诺实现里没有的行为')
    assert.match(SERVICE, /reset-config/, 'docstring 没指路清除通道')
  })
})

describe('F3 在 PRD 里可追溯', () => {
  const PRD = readFileSync(
    new URL('../../../../docs/需求规格说明书-UX优化.md', import.meta.url),
    'utf8',
  )

  it('FR-UX-101 仍然认领 F3', () => {
    const fr = PRD.slice(PRD.indexOf('| FR-UX-101 |'), PRD.indexOf('\n', PRD.indexOf('| FR-UX-101 |')))
    assert.match(fr, /M14, M16, M46, F3/, 'F3 从覆盖条目里掉了，M1 的 11 条就少一条有归属')
  })

  it('ACC-UX-101 第 8 条把留空语义写成可验收项', () => {
    const acc = PRD.slice(PRD.indexOf('**验收（ACC-UX-101）**'))
    assert.match(acc.slice(0, 2600), /8\. AI 服务页把 API Key 框清空/, 'F3 只有代码修了、没有验收口径，下次还会靠嘴说')
    assert.match(acc.slice(0, 2600), /reset-config/, '没写清通道是哪个接口，验收时无法确证')
  })
})
