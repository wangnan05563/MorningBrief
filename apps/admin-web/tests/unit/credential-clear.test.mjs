/**
 * T02919：凭据「能不能真的清掉」是可核对的契约，不是文案。
 *
 * F3 那一轮把口径统一成「留空＝不修改」，代价是除 LLM 之外
 * （tts_api_key / tts_appkey / tencent_tts_secret_id / tencent_tts_secret_key /
 * image_api_key / cos_secret_id / cos_secret_key）根本没有清除通道，
 * 而界面文案还在指「点右上角『恢复初始配置』」——那句话对 TTS/图片/COS 是假的。
 *
 * 所以这里的重点不是「有没有按钮」，而是：
 * 1. 文案指向的入口在本页真实存在（逐条反查，防「指到一个不存在的清除入口」）；
 * 2. 清除走显式 scope，而不是把空串当删除；
 * 3. 四类凭据各有对应的后端 key 组，COS 也不再是空白。
 *
 * 运行：cd apps/admin-web && node --test tests/unit/credential-clear.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe, it } from 'node:test'

const AI_VIEW = readFileSync(
  new URL('../../src/views/ai/AIConfig.vue', import.meta.url),
  'utf8',
)
const COS_VIEW = readFileSync(
  new URL('../../src/views/cos/CosConfig.vue', import.meta.url),
  'utf8',
)
const COS_API = readFileSync(new URL('../../src/api/cos.js', import.meta.url), 'utf8')
const AI_SERVICE = readFileSync(
  new URL('../../../../backend/app/services/ai_config_service.py', import.meta.url),
  'utf8',
)
const COS_SERVICE = readFileSync(
  new URL('../../../../backend/app/services/cos_config_service.py', import.meta.url),
  'utf8',
)
const AI_ROUTER = readFileSync(
  new URL('../../../../backend/app/routers/admin/ai_config.py', import.meta.url),
  'utf8',
)
const COS_ROUTER = readFileSync(
  new URL('../../../../backend/app/routers/admin/cos.py', import.meta.url),
  'utf8',
)

/**
 * 收集「请点 X」式指引里的 X，并核对页面上真有叫这个名字的按钮。
 * 只扫带「清除 / 作废 / 留空」字样的提示行，避免把普通说明也当成承诺。
 */
function referencedClearTargets(source) {
  const targets = []
  for (const line of source.split('\n')) {
    if (!/field-tip|留空|清除|作废/.test(line)) continue
    for (const m of line.matchAll(/[「『]([^」』]{2,20})[」』]/g)) {
      const text = m[1]
      if (/清除|恢复初始|作废/.test(text)) targets.push(text)
    }
  }
  return targets
}

function hasButtonLabeled(source, label) {
  return new RegExp(`label="${label}"`).test(source)
}

/** 从按钮的 label 往后找它绑定的 handleResetConfig('scope')，找不到返回 null */
function clickScopeOf(source, label) {
  const at = source.indexOf(`label="${label}"`)
  if (at < 0) return null
  const m = source.slice(at, at + 300).match(/handleResetConfig\('(\w+)'\)/)
  return m ? m[1] : null
}

describe('T02919 界面提示只允许指向真实存在的清除入口', () => {
  it('AI 页文案点名的清除入口都真的在页面上', () => {
    const refs = referencedClearTargets(AI_VIEW)
    assert.ok(refs.length >= 3, `只找到 ${refs.length} 条指路文案，LLM/TTS/图片三处都要有`)
    for (const label of refs) {
      assert.ok(
        hasButtonLabeled(AI_VIEW, label),
        `文案让用户点「${label}」，但 AIConfig.vue 里没有这个按钮`,
      )
    }
  })

  it('COS 页文案点名的「清除凭证」按钮真的在页面上', () => {
    assert.match(COS_VIEW, /要\*\*作废\*\*凭证请点右上角「清除凭证」/)
    assert.ok(hasButtonLabeled(COS_VIEW, '清除凭证'), 'COS 页面没有清除凭证按钮，文案是指空的')
  })

  it('TTS/图片两处的留空提示不再指错入口', () => {
    assert.match(AI_VIEW, /要作废请点下方「清除 TTS 凭证」/)
    assert.match(AI_VIEW, /要作废请点下方「清除图片 Key」/)
    assert.match(AI_VIEW, /label="清除 TTS 凭证"/)
    assert.match(AI_VIEW, /label="清除图片 Key"/)
  })
})

describe('T02919 前端把清除做成显式 scope 调用', () => {
  it('按 scope 调 reset-config，而不是留空提交', () => {
    assert.match(AI_VIEW, /api\.post\(`\/ai\/reset-config\?scope=\$\{scope\}`\)/)
    assert.match(AI_VIEW, /const CLEAR_META = \{/, '清除动作没有集中的文案/范围定义，三处会各写一套')
    assert.match(AI_VIEW, /dangerConfirm\(/, '清凭据是不可逆动作，必须走统一确认规范')
    // 提交时仍把脱敏值折算成空串＝不修改（这条一旦改反，只改 base_url 就会抹掉密钥）
    assert.match(AI_VIEW, /key\.startsWith\('\*\*\*\*'\) \? '' : key/)
  })

  it('COS 侧有对应的 api 封装与调用', () => {
    assert.match(COS_API, /resetCosConfig = \(\) => api\.post\('\/cos\/reset-config'\)/)
    assert.match(COS_VIEW, /await resetCosConfig\(\)/)
  })

  it('每个清除按钮绑定的 scope 与它的名字一致（接错对象防护）', () => {
    // 「清除 TTS 凭证」按钮实际打 scope=llm 时，界面看着像成功了、TTS 密钥却还在
    for (const [label, scope] of [
      ['恢复初始配置', 'llm'],
      ['清除 TTS 凭证', 'tts'],
      ['清除图片 Key', 'image'],
    ]) {
      assert.equal(
        clickScopeOf(AI_VIEW, label),
        scope,
        `按钮「${label}」没有绑定 scope=${scope}，清了别的凭据族`,
      )
    }
  })
})

describe('T02919 后端四类凭据都有对应清除范围', () => {
  it('RESET_SCOPES 覆盖 llm/tts/image/all 且 key 组完整', () => {
    for (const scope of ['"llm"', '"tts"', '"image"', '"all"']) {
      assert.ok(AI_SERVICE.includes(scope), `RESET_SCOPES 缺 ${scope}`)
    }
    for (const key of ['tts_api_key', 'tts_appkey', 'tencent_tts_secret_id', 'tencent_tts_secret_key']) {
      assert.match(AI_SERVICE, new RegExp(`"${key}"`), `${key} 不在清除范围内`)
    }
    assert.match(AI_SERVICE, /IMAGE_RESET_KEYS = \["image_api_key"\]/)
  })

  it('清除是删行 + 回写 Settings，而不是写空串', () => {
    assert.match(AI_SERVICE, /delete\(AIConfig\)\.where\(AIConfig\.config_key == key\)/)
    assert.match(AI_SERVICE, /setattr\(settings, attr, getattr\(defaults, attr, ""\)\)/)
    // 「留空＝不修改」的守卫不能被改成「空串即删除」
    assert.match(AI_SERVICE, /if api_key and not _is_masked\(api_key\):/)
  })

  it('COS 只清凭证、保留地域/桶/CDN', () => {
    assert.match(COS_SERVICE, /CREDENTIAL_KEYS = \["cos_secret_id", "cos_secret_key"\]/)
    assert.match(COS_SERVICE, /async def reset_credentials/)
    assert.match(COS_SERVICE, /delete\(CosConfig\)\.where\(CosConfig\.config_key == key\)/)
    assert.doesNotMatch(COS_SERVICE, /当前没有「一键清除已存凭证」的接口/, 'docstring 还在说没有通道')
  })

  it('两个清除端点都落审计，且 scope 由接口层枚举', () => {
    assert.match(AI_ROUTER, /Literal\["llm", "tts", "image", "all"\]/)
    assert.match(AI_ROUTER, /category="ai",\s*\n\s*action="reset_config"/)
    assert.match(COS_ROUTER, /@router\.post\("\/reset-config"\)/)
    assert.match(COS_ROUTER, /category="cos",\s*\n\s*action="reset_config"/)
  })
})

describe('T02919 在 PRD 里可追溯', () => {
  const PRD = readFileSync(
    new URL('../../../../docs/需求规格说明书-UX优化.md', import.meta.url),
    'utf8',
  )

  it('ACC-UX-101 有第 9 条覆盖四类凭据的清除', () => {
    const acc = PRD.slice(PRD.indexOf('**验收（ACC-UX-101）**'))
    assert.match(acc, /9\. 对 ?LLM\/TTS\/图片\/COS ?四类凭据/, '清除通道只有代码、没有验收口径')
    assert.match(acc, /库里该行确实没了/)
  })

  it('F3 的缺口注释改成「已闭环」口径，不再挂着 T02919 当未做', () => {
    assert.match(PRD, /T02919（已闭环/, '注释还写着缺口未跟踪，下期会重复排同一件事')
  })
})
