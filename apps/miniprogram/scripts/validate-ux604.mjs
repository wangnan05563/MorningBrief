/**
 * FR-UX-604（小程序页面职责与文案）构建期一致性校验 —— T02513
 *
 * 这一类缺陷的共同点：错的是「界面上的话」和「代码里做的事」之间的关系，
 * 运行时一个异常都不会抛。所以只能构建期静态比对，且比对必须是双向的：
 *  1. J45/J48 页名与职责说明：channels 页标题不得再写「我的频道」（内容其实是全部频道 + 订阅态）；
 *     channels.wxml 必须同时出现「订阅」与「偏爱」两个词并给出跨页入口，
 *     preferred-settings.wxml 必须反向出现「订阅」（两页卡片几乎同形，只说明一边等于没说清）。
 *  2. J46 跨页切换契约：写侧（pages/channels/channels.js 或 app.js）给 globalData.pendingChannelId
 *     赋值 ↔ 读侧 pages/index/index.js 定义 _consumePendingChannel 且被 onShow / loadChannels 调用。
 *     这条最容易在后续重构里单边丢失：删掉读侧代码，页面照样跑得起来，只是「点了没反应」回来了。
 *     另含 index.wxml 的胶囊定位（scroll-into-view）必须绑到 index.js 的 scrollIntoViewId。
 *  3. J72 取消收藏入口：favorites.wxml 必须有非长按手势的可见入口（catchtap/bindtap 到取消收藏方法），
 *     且该方法在 favorites.js 里存在并落到 removeFavorite。只有 bind/catch 名对上还不算，
 *     方法名里必须含 unFavorite/unfavorite/removeFavorite/cancelFavorite 之一，防止绑到别处。
 *  4. J80 清除缓存文案 ↔ KEEP_KEYS 同源：确认文案必须逐类点名「收藏 / 进度 / 偏爱」这些
 *     真会被抹掉的类别（KEEP_KEYS 之外的那些），并且不得再出现「保留登录信息与设置」这种
 *     没列举后果的裸承诺；KEEP_KEYS 必须含设置 key（单源 services/constants）。
 *  5. J99 隐私承诺 ↔ 实现：隐私第七条不得再写「退出登录即可」删除个人信息，
 *     必须给出可走的通道（意见反馈）与真开关的位置（设置 → 数据与统计）；
 *     第五条不得写「不会上传服务器」（收藏与进度确实双写）。
 *     同时开关必须三处齐：settings.wxml 的 switch 绑 usageTracking + bindchange、
 *     settings.js 的 handler 调 setTrackingEnabled、utils/tracker.js 的 track() 先判 isEnabled()。
 *  6. J5 浮条纠偏：floating-player.js 必须既有 pageLifetimes.show，又在播放状态回调里调 this._refresh()
 *     （只留订阅回调 = tab 页常驻组件错过事件后浮条永远不出现；只留 show = 播放中状态不刷新）。
 *  7. 通用防「绑了个不存在的方法」：本轮涉及的 wxml 里字面量写法的 bind / catch 事件处理器名，
 *     必须能在同页 js 里找到定义（`bindtap="{{ x ? 'a' : 'b' }}"` 这类动态值跳过，与 validate-tabbar 同口径）。
 *
 * 局限（如实声明，不假装查过）：只做文本抽取与配对，不解析 WXML/JS 语法树；
 * 动态方法名、运行时拼出的 storage key、跨页 getCurrentPages() 跳转不在能力范围内。
 *
 * 运行：node apps/miniprogram/scripts/validate-ux604.mjs
 * 自测（证伪样本，门禁会不会红）：node --test apps/miniprogram/tests/validate-ux604.test.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/** 需要交叉比对的文件（相对 apps/miniprogram） */
const FILES = [
  'app.js',
  'pages/channels/channels.js',
  'pages/channels/channels.json',
  'pages/channels/channels.wxml',
  'pages/preferred-settings/preferred-settings.wxml',
  'pages/preferred-settings/preferred-settings.js',
  'pages/index/index.js',
  'pages/index/index.wxml',
  'pages/favorites/favorites.js',
  'pages/favorites/favorites.wxml',
  'pages/settings/settings.js',
  'pages/settings/settings.wxml',
  'pages/privacy/privacy.js',
  'utils/tracker.js',
  'components/floating-player/floating-player.js',
  'services/constants.js',
]

/** wxml 里绑定 → 同页 js 方法必须存在（跳过动态绑定值） */
const BIND_RE = /\b(?:bind|catch)[:]?([a-z]+)="([A-Za-z0-9_]+)"/g

function collectFacts(overrides = {}) {
  const files = {}
  for (const rel of FILES) {
    const fromOverride = overrides[rel]
    if (typeof fromOverride === 'string') {
      files[rel] = fromOverride
      continue
    }
    try {
      files[rel] = readFileSync(join(ROOT, rel), 'utf8')
    } catch (err) {
      files[rel] = null
    }
  }
  return { files, missing: FILES.filter((rel) => files[rel] === null) }
}

/** 剔除整行注释（考古用的旧句子写在注释里，不能当成违规复发） */
const stripComments = (text) =>
  text
    .split('\n')
    .filter((line) => !/^\s*(\/\/|\*|\/\*)/.test(line))
    .join('\n')

/**
 * wxml 注释同理：本单在 wxml 顶部留了「为什么改」的说明，里面就带着「订阅」「偏爱」这些词。
 * 不剥离的话，文案规则只检查到注释就会永远绿——注释越详细，门禁越没用。
 */
const stripWxmlComments = (text) => text.replace(/<!--[\s\S]*?-->/g, '')

/** 只取某个 Page 方法的函数体（两空格缩进的定义 → 下一个同缩进定义之前） */
function methodBody(src, name) {
  const start = src.search(new RegExp(`^ {2}(?:async )?${name}\\s*\\(`, 'm'))
  if (start < 0) return ''
  const rest = src.slice(start)
  const next = rest.slice(1).search(/^ {2}(?:async )?[A-Za-z_]\w*\s*\(/m)
  return next < 0 ? rest : rest.slice(0, next + 1)
}

/**
 * 找到源码里每一处 `this.<name>()` 调用所处的方法名。
 * 为什么不用「onShow … 调用 …」这种顺序正则：`onShow` 与 `loadChannels` 两个词在文件里
 * 会以注释、被调用点的形式反复出现，顺序正则能跨过半个文件匹配上，
 * 于是「删掉 loadChannels 里那次调用」照样绿（本文件第一版就被这样骗过一次）。
 */
function callSites(src, name) {
  const sites = []
  // 逐行判定时用非全局正则：带 /g 的 test() 会保留 lastIndex，跨行漏判
  const hit = new RegExp(`this\\.${name}\\(`)
  const headerRe = /^ {2}(?:async )?([A-Za-z_]\w*)\s*\(/
  const lines = src.split('\n')
  let current = ''
  for (let i = 0; i < lines.length; i += 1) {
    const m = headerRe.exec(lines[i])
    if (m) current = m[1]
    if (hit.test(lines[i])) sites.push({ line: i + 1, method: current })
  }
  return sites
}

/**
 * 取隐私政策里某一节的文本（按 title 关键词定位到下一节之前）。
 * 先剔除整行注释：本单修文案时会在注释里引用被修掉的旧句子（「退出登录即可」之类），
 * 不剔的话门禁会把自家留下的考古注释当成违规复发——误报的门禁等于没有门禁。
 */
function privacySection(src, keyword) {
  const i = src.indexOf(keyword)
  if (i < 0) return ''
  const next = src.indexOf('title:', i + keyword.length)
  return stripComments(src.slice(i, next > i ? next : src.length))
}

export function checkFacts(facts) {
  const errors = []
  const { files } = facts
  if (facts.missing.length) {
    errors.push(`缺失待校验文件：${facts.missing.join(', ')}（本单涉及的页面被改名/删除时，门禁必须红而不是静默跳过）`)
  }
  const f = (rel) => files[rel] || ''
  /** wxml 的文案断言一律先看掉注释后的文本（见 stripWxmlComments 的说明） */
  const wf = (rel) => stripWxmlComments(f(rel))

  // —— 1. J45 / J48：页名与两页职责说明 ——
  if (/"navigationBarTitleText":\s*"我的频道"/.test(f('pages/channels/channels.json'))) {
    errors.push('channels.json: 页名仍写「我的频道」，列出的却是全部频道 + 订阅态（T02323 J45）')
  }
  const channelsWxml = wf('pages/channels/channels.wxml')
  for (const word of ['订阅', '偏爱']) {
    if (!channelsWxml.includes(word)) {
      errors.push(`channels.wxml: 页面文案缺少「${word}」——两页卡片几乎同形，不在本页说明区别，用户就会把订阅当成偏爱（J48）`)
    }
  }
  if (!/onGoPreferred/.test(channelsWxml) || !/onGoPreferred\s*\(/.test(f('pages/channels/channels.js'))) {
    errors.push('channels 页没有可用的「去偏爱设置」入口（wxml 未绑定或 js 未实现 onGoPreferred）（J48）')
  }
  if (!/onGoChannels/.test(wf('pages/preferred-settings/preferred-settings.wxml')) ||
      !/onGoChannels\s*\(/.test(f('pages/preferred-settings/preferred-settings.js'))) {
    errors.push('preferred-settings 页没有反向入口 onGoChannels（J48 要求两页对称说明，只写一边等于没写）')
  }
  if (!/订阅/.test(wf('pages/preferred-settings/preferred-settings.wxml'))) {
    errors.push('preferred-settings.wxml 的说明未提到「订阅」——本页与频道页的区别必须双向说清（J48）')
  }

  // —— 2. J46：跨页切换契约的两端 + 胶囊定位 ——
  const writeSide = f('pages/channels/channels.js') + f('app.js')
  if (!/pendingChannelId\s*=/.test(writeSide)) {
    errors.push('写侧（channels.js / app.js）不再给 globalData.pendingChannelId 赋值——J46 的「点了频道没反应」回来了')
  }
  const indexJs = f('pages/index/index.js')
  if (!/_consumePendingChannel\s*\(/.test(indexJs)) {
    errors.push('index.js 没有 _consumePendingChannel 定义：读侧丢失，pendingChannelId 永远没人消费（J46）')
  }
  const consumers = [...new Set(callSites(indexJs, '_consumePendingChannel').map((s) => s.method))]
  for (const host of ['onShow', 'loadChannels']) {
    if (!consumers.includes(host)) {
      errors.push(`index.js 的 ${host} 里没有 this._consumePendingChannel() 调用（现有调用点：${consumers.join('/') || '无'}）。` +
        '两处都要在：首屏 fetch 未完成时列表是空的，只有 loadChannels 之后那次能兜住（J46）')
    }
  }
  if (!/scroll-into-view="{{scrollIntoViewId}}"/.test(wf('pages/index/index.wxml')) ||
      !/scrollIntoViewId/.test(indexJs)) {
    errors.push('index 频道条缺少 scroll-into-view ↔ scrollIntoViewId：选中胶囊落在屏幕外时用户读不到「已切换」（J46）')
  }
  if (!/id="pill-\{\{index\}\}"/.test(wf('pages/index/index.wxml'))) {
    errors.push('index.wxml 胶囊没有 id="pill-{{index}}"，scroll-into-view 无锚点可用（J46）')
  }

  // —— 3. J72：取消收藏要有非长按的可见入口 ——
  const favWxml = wf('pages/favorites/favorites.wxml')
  const bindNames = [...favWxml.matchAll(/(?:bind|catch)tap="([A-Za-z0-9_]+)"/g)].map((m) => m[1])
  const unfav = bindNames.find((n) => /unfavor|cancelFav|removeFav/i.test(n))
  if (!unfav) {
    errors.push('favorites.wxml 没有指向取消收藏的 tap 入口（只有 bindlongpress 不算，长按是唯一手势正是 J72 的缺陷）')
  } else if (!new RegExp(`${unfav}\\s*\\(`).test(f('pages/favorites/favorites.js'))) {
    errors.push(`favorites.js 缺少 ${unfav} 实现：入口绑到了不存在的动作`)
  }
  if (!/removeFavorite\s*\(/.test(f('pages/favorites/favorites.js'))) {
    errors.push('favorites.js 不再调用 removeFavorite：取消收藏链路被切断')
  }

  // —— 4. J80：清除缓存文案 ↔ KEEP_KEYS 同源 ——
  const settingsJs = f('pages/settings/settings.js')
  const keep = /KEEP_KEYS\s*=\s*\[([^\]]*)\]/.exec(settingsJs)
  if (!keep) {
    errors.push('settings.js 找不到 KEEP_KEYS 定义：清除范围失去唯一事实源')
  } else if (!/STORAGE_KEY_SETTINGS/.test(keep[1])) {
    errors.push('settings.js 的 KEEP_KEYS 未包含 STORAGE_KEY_SETTINGS——清除缓存会把用户设置一起抹掉（J80）')
  } else if (!/STORAGE_KEY_SETTINGS\s*[:=]/.test(f('services/constants.js'))) {
    errors.push('services/constants.js 未导出 STORAGE_KEY_SETTINGS 单源（settings 与 tracker 会各写一份字面量）（J99）')
  }
  const modal = /onClearCache\(\)[\s\S]*?showModal\(\{([\s\S]*?)\n  \}/.exec(settingsJs)
  const modalText = modal ? stripComments(modal[1]) : ''
  for (const word of ['收藏', '进度', '偏爱']) {
    if (!modalText.includes(word)) {
      errors.push(`清除缓存确认文案没有点名「${word}」——它确实在 KEEP_KEYS 之外会被抹掉，` +
        `原先那句「保留登录信息与设置」正是 J80 的撒谎点`)
    }
  }
  if (/保留登录信息与设置）/.test(modalText) || !/服务器|本机/.test(modalText)) {
    errors.push('清除缓存确认文案回到了「只保留登录信息与设置」式的未列举写法，或未说明只影响本机（J80）')
  }

  // —— 5. J99：隐私开关三处齐 + 隐私文案不再撒谎 ——
  const settingsWxml = wf('pages/settings/settings.wxml')
  if (!/checked="{{usageTracking}}"/.test(settingsWxml) || !/bindchange="onTrackingChange"/.test(settingsWxml)) {
    errors.push('settings.wxml 没有绑到 usageTracking/onTrackingChange 的开关——隐私政策第 4 条又指向了不存在的控件（J99）')
  }
  const trackingBody = methodBody(settingsJs, 'onTrackingChange')
  if (!trackingBody) {
    errors.push('settings.js 缺少 onTrackingChange：开关的 bindchange 指向了一个不存在的处理器（J99）')
  } else {
    if (!/setTrackingEnabled\(/.test(trackingBody)) {
      errors.push('settings.js 的 onTrackingChange 没有调 setTrackingEnabled：UI 与 tracker 各自为政，关掉开关事件照记（J99）')
    }
    if (!/saveSettings\(\{\s*usageTracking:\s*value\s*\}\)/.test(trackingBody)) {
      errors.push('settings.js 的 onTrackingChange 没把 usageTracking 落盘：重启后开关回到默认值，承诺只活一次（J99）')
    }
  }
  const trackerJs = f('utils/tracker.js')
  if (!/function track\([\s\S]{0,200}isEnabled\(\)/.test(trackerJs)) {
    errors.push('utils/tracker.js 的 track() 未在写事件前判 isEnabled()：开关关掉后事件照记（J99）')
  }
  const right = privacySection(f('pages/privacy/privacy.js'), '您的权利')
  if (!right) {
    errors.push('privacy.js 找不到「您的权利」条款，后续文案断言无法定位范围（J98）')
  } else {
    if (right.includes('退出登录即可')) {
      errors.push('隐私政策第七条仍写「要求删除个人信息（退出登录即可）」：退出登录只清本机，服务端数据一条不删（J98）')
    }
    if (!/意见反馈/.test(right)) errors.push('隐私政策第七条没有可走的删除请求通道（意见反馈）（J98）')
    if (!/数据与统计/.test(right)) errors.push('隐私政策第七条没把「关闭使用统计」指到设置页的真实分组（J99）')
  }
  const cache = privacySection(f('pages/privacy/privacy.js'), 'Cookie')
  if (cache && /不会上传服务器/.test(cache)) {
    errors.push('隐私政策第五条仍写「不会上传服务器」：收藏与播放进度是双写的（J98）')
  }

  // —— 6. J5：浮条纠偏的两个时机都要在 ——
  const player = f('components/floating-player/floating-player.js')
  if (!/pageLifetimes:\s*\{[\s\S]{0,200}show\s*\(\)[\s\S]{0,120}_refresh\(\)/.test(player)) {
    errors.push('floating-player 缺少 pageLifetimes.show → _refresh()：tab 页组件常驻，错过订阅事件后浮条永不出现（J5）')
  }
  if (!/onPlaybackChange\(\(\)\s*=>\s*\{[\s\S]{0,120}this\._refresh\(\)/.test(player)) {
    errors.push('floating-player 的播放状态回调不再走 _refresh()：visible/episode 与 isPlaying 分成两套口径（J5）')
  }

  // —— 7. wxml 字面量绑定 ↔ 同页 js 方法 ——
  for (const rel of FILES.filter((r) => r.endsWith('.wxml'))) {
    const jsRel = rel.replace(/\.wxml$/, '.js')
    const js = f(jsRel)
    if (!js) continue
    const seen = new Set()
    for (const m of wf(rel).matchAll(BIND_RE)) {
      const handler = m[2]
      if (/^(navigator|picker|swiper|scroll)/.test(handler)) continue
      if (seen.has(handler)) continue
      seen.add(handler)
      if (!new RegExp(`(^|[^.\\w])${handler}\\s*[(=]`).test(js) && !new RegExp(`"${handler}"`).test(js)) {
        errors.push(`${rel}: 绑定了 ${handler}，但 ${jsRel} 里没有这个方法定义——运行时静默「点了没反应」（与 validate-tabbar 的死入口互为反向）`)
      }
    }
  }

  return { errors, facts }
}

export async function validate(overrides = {}) {
  return checkFacts(collectFacts(overrides))
}

const isCli = process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href
if (isCli) {
  const { errors } = await validate()
  if (errors.length) {
    for (const e of errors) console.error(`  ✗ ${e}`)
    console.error(`[validate-ux604] ${errors.length} 项不一致`)
    process.exit(1)
  }
  console.log(`[validate-ux604] 通过（交叉比对 ${FILES.length} 个文件：职责说明/切换契约/入口/文案同源/开关接线/纠偏时机）`)
}
