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
 *     另含 index.wxml 的胶囊定位（scroll-into-view）必须绑到 index.js 的 scrollIntoViewId，
 *     以及读侧必须自己挡掉非 news 频道（app.js 深链兜底会把课程/有声书 id 也交给首页）。
 *  3. J72 取消收藏入口：favorites.wxml 必须有非长按手势的可见入口（catchtap/bindtap 到取消收藏方法），
 *     且该方法在 favorites.js 里存在并落到 removeFavorite。只有 bind/catch 名对上还不算，
 *     方法名里必须含 unFavorite/unfavorite/removeFavorite/cancelFavorite 之一，防止绑到别处。
 *  4. J80 / T02787 清除缓存 ↔ 分类表 ↔ 文案 三处同源：删哪些由 services/storage-keys.js
 *     的 CACHE_KEYS 正向白名单决定（黑名单写法会被点名），确认文案必须逐类点名
 *     「收藏 / 进度 / 偏爱」这些**不再被清除**的类别，并说明只影响本机；
 *     设置 key 必须留在 KEEP_KEYS 里，且 constants 不得再导出第二份字面量。
 *     行下说明（进页就看到的那句）与弹窗同口径：实现改成不毁数据后，
 *     旧说明还在承诺「清除收藏/进度」同样算撒谎（按分句判，「只清除…」不算违规）。
 *  5. J99 隐私承诺 ↔ 实现：隐私第七条不得再写「退出登录即可」删除个人信息，
 *     必须给出可走的通道（意见反馈）与真开关的位置（设置 → 数据与统计）；
 *     第五条不得写「不会上传服务器」（收藏与进度确实双写）。
 *     同时开关必须三处齐：settings.wxml 的 switch 绑 usageTracking + bindchange、
 *     settings.js 的 handler 调 setTrackingEnabled、utils/tracker.js 的 track() 先判 isEnabled()。
 *     T02788 起第七条还必须指向自助入口「删除我的数据」，且备份保留期数字要与服务端
 *     常量（backup_service._DEFAULT_KEEP_DAYS / config.COS_BACKUP_KEEP_COUNT）逐字一致。
 *  6. J5 浮条纠偏：floating-player.js 必须既有 pageLifetimes.show，又在播放状态回调里调 this._refresh()
 *     （只留订阅回调 = tab 页常驻组件错过事件后浮条永远不出现；只留 show = 播放中状态不刷新）。
 *  7. 通用防「绑了个不存在的方法」：本轮涉及的 wxml 里字面量写法的 bind / catch 事件处理器名，
 *     必须能在同页 js 里找到定义（`bindtap="{{ x ? 'a' : 'b' }}"` 这类动态值跳过，与 validate-tabbar 同口径）。
 *
 *  T02540（M6 信息架构与深链）追加：
 *  8. J21 退出登录文案 ↔ 真实行为：弹窗必须说明「只清本机、云端收藏/进度/记录仍在」，
 *     并给出删除服务端数据的真实通道（意见反馈）；不得回到「确定要退出登录吗？」。
 *  9. J24 登录与编辑资料按钮必须有可见文字，不得再是 btn-icon-only（仅 aria-label）。
 * 10. J66 偏爱设置自述作用面：说明必须点名「首页」「历史」「我的偏爱」，
 *     并注明与频道页「订阅」互不同步（两页同形卡片，不说清就会互相误解）。
 * 11. J105 webview 失败兜底：两个按钮必须有「复制链接」「返回」可见文字，
 *     URL 展示区必须有高度上限 + 滚动（超长链接不挤走按钮、也不截断到无法核对）。
 * 12. J69 最近播放 onShow 只能首次加载：无保护地重载会重置分页与滚动位置。
 * 13. J77 队列单项管理单源：services/audio.js 提供 removeQueueAt/moveQueueItem，
 *     队列页与详情页 modal 各自绑定移出/上移下移（此前两处都只能整表清空）。
 * 14. J14/J12 历史的两个出口：页内分段入口直达「我的播放记录」，队列 chip 带可见「队列」文字。
 * 15. J20 个人中心第二层只做入口：不得再出现 secondList 内嵌列表（与整页重复取数/渲染）。
 *
 * 16-20. J27/J28/J32/J59/J73/J81：详情页缓冲态与课程语境、失败可重试、离线兜底、
 *     已下架标签、检查更新等实现与文案的接线（逐条见下方代码注释）。
 * 21. T02787：字面量 storage key 只许出现在 services/storage-keys.js ——
 *     黑名单清缓存会抹数据，根因就是 key 散在各模块、静态列不全；这条堵住新增散 key。
 * 22. T02788：「删除我的数据」必须入口、确认口径、拆除顺序三处齐：
 *     wxml 入口在「数据与统计」分组内；handler 先取预览条数、破坏性配色、写明不可恢复、
 *     只 clearToken 不调 logout（后者 401 自动重登会把刚删的账号注册回来）；
 *     api.js 的 DELETE 带 confirm:true 且关掉 401/网络两类自动重试。
 *
 * 局限（如实声明，不假装查过）：只做文本抽取与配对，不解析 WXML/JS 语法树；
 * 动态方法名、跨页 getCurrentPages() 跳转不在能力范围内。
 * （原先「运行时拼出的 storage key 无法静态列全」这一条已由 T02787 的
 *  services/storage-keys.js 单源消除：拼法收成一处后，门禁与测试都能枚举全集。）
 *
 * 运行：node apps/miniprogram/scripts/validate-ux604.mjs
 * 自测（证伪样本，门禁会不会红）：node --test apps/miniprogram/tests/validate-ux604.test.mjs
 */
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/**
 * 读服务端备份保留常量（T02788）。隐私政策是静态文案，保留期必须与后端配置逐字一致：
 * 只断言「文案里有个数字」证明不了「数字还对」，而配置一改，静态文案就成了第二处谎言。
 */
const BACKEND = resolve(ROOT, '../../backend/app')
function backendConst(rel, name) {
  try {
    const src = readFileSync(join(BACKEND, rel), 'utf8')
    const m = new RegExp(`^\\s*${name}\\s*(?::\\s*[A-Za-z_][\\w[\\], ]*)?=\\s*(\\d+)`, 'm').exec(src)
    return m ? Number(m[1]) : null
  } catch (err) {
    return null
  }
}

/** 需要交叉比对的文件（相对 apps/miniprogram） */
const FILES = [
  'app.js',
  // T02735：第二层入口路由必须在 app.json.pages 注册过，否则 navigateTo 静默失败
  'app.json',
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
  // T02540 / M6
  'pages/profile/profile.js',
  'pages/profile/profile.wxml',
  'pages/webview/webview.wxml',
  'pages/webview/webview.wxss',
  'pages/history/history.js',
  'pages/history/history.wxml',
  'pages/recent/recent.js',
  'pages/queue/queue.js',
  'pages/queue/queue.wxml',
  'pages/detail/detail.js',
  'pages/detail/detail.wxml',
  'services/audio.js',
  // T02542 / M7
  'services/download.js',
  // T02787：持有 storage key 的模块都要进门禁，字面量 key 禁令才覆盖得到
  'services/storage-keys.js',
  'services/local-data.js',
  'services/auth.js',
  'services/api.js',
  'utils/server-discovery.js',
  'utils/storage.js',
  'pages/search/search.js',
  'pages/feedback/feedback.js',
]

/** app.json.pages 与 navigateTo url 的前导斜杠归一（T02735） */
const normPage = (p) => String(p || '').replace(/^\/+/, '').replace(/\/+$/, '')

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
  // 深链兜底会把课程/有声书频道 id 也交给首页消费端（app.js 判不出类型时 routeToNews()），
  // 所以读侧必须自己挡一次。删掉这段不会报错，只会让课程频道被塞进今日列表里空跑一次 fetch。
  const consumeBody = methodBody(stripComments(indexJs), '_consumePendingChannel')
  if (!/normalizeType\s*\(/.test(consumeBody) || !/pages\/course\/course/.test(consumeBody)) {
    errors.push('index.js 的 _consumePendingChannel 不再拦截非 news 频道：深链把课程/有声书频道交给今日列表，'
      + '切过去只会空列表（J46 的跨类型兜底丢失）')
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

  // —— 4. J80 / T02787：清除缓存的白名单 ↔ 分类表 ↔ 文案 三处同源 ——
  const settingsJs = f('pages/settings/settings.js')
  const keysJs = f('services/storage-keys.js')
  for (const name of ['KEEP_KEYS', 'CACHE_KEYS', 'USER_DATA_KEYS']) {
    if (!new RegExp(`const ${name} = \\[`).test(keysJs)) {
      errors.push(`services/storage-keys.js 缺少 ${name} 分类表：清除范围失去唯一事实源（T02787）`)
    }
  }
  const keepBlock = /const KEEP_KEYS = \[([\s\S]*?)\]/.exec(keysJs)
  if (keepBlock && !/STATIC\.SETTINGS/.test(keepBlock[1])) {
    errors.push('services/storage-keys.js 的 KEEP_KEYS 未包含设置 key——清除缓存会把用户设置一起抹掉（J80）')
  }
  if (!/require\('\.\.\/\.\.\/services\/storage-keys'\)/.test(settingsJs)) {
    errors.push('settings.js 不再引用 services/storage-keys：清除缓存改回自行判断，白名单形同虚设（T02787）')
  }
  if (!/clearCacheKeys\(/.test(settingsJs)) {
    errors.push('settings.js 的清除缓存没走 storage-keys 的执行口 clearCacheKeys：删哪些又回到页面自己说了算（T02787）')
  }
  if (/KEEP_KEYS\.indexOf\(key\)\s*===\s*-1/.test(settingsJs)) {
    errors.push('settings.js 回到「KEEP_KEYS 之外全删」的黑名单写法——那一行正是 J80 抹掉收藏/进度/偏爱的事故点（T02787）')
  }
  if (/STORAGE_KEY_SETTINGS/.test(f('services/constants.js'))) {
    errors.push('services/constants.js 仍在导出 STORAGE_KEY_SETTINGS：key 名出现第二处，分类表就不再是全集（T02787）')
  }
  // 只看真 require：写成「提到 storage-keys 这个词就行」会被上一行的考古注释喂饱，
  // 把 require 改回字面量后门禁照样绿（第一版就是这样，证伪样本当场戳穿了它）。
  if (!/require\('\.\.\/services\/storage-keys'\)\.STATIC\.SETTINGS/.test(stripComments(f('utils/tracker.js')))) {
    errors.push('utils/tracker.js 不再从 storage-keys 读设置 key：统计开关会去读一个没人写的 key（J99 / T02787）')
  }
  const modal = /onClearCache\(\)[\s\S]*?showModal\(\{([\s\S]*?)\n  \}/.exec(settingsJs)
  const modalText = modal ? stripComments(modal[1]) : ''
  for (const word of ['收藏', '进度', '偏爱']) {
    if (!modalText.includes(word)) {
      errors.push(`清除缓存确认文案没有点名「${word}」——用户无法确认它现在不会被抹掉，` +
        `原先那句「保留登录信息与设置」正是 J80 的撒谎点`)
    }
  }
  if (/保留登录信息与设置）/.test(modalText) || !/服务器|本机/.test(modalText)) {
    errors.push('清除缓存确认文案回到了「只保留登录信息与设置」式的未列举写法，或未说明只影响本机（J80）')
  }
  if (/仍要清除/.test(modalText)) {
    errors.push('清除缓存仍是警告级确认：现在它只删可再生项，却用红色「仍要清除」暗示会毁掉数据（T02787 文案与实现脱钩）')
  }
  // 行下说明（进页面就看到的那句）和弹窗必须同口径。T02787 把实现改成「不毁数据」后，
  // 旧说明还写着「清除本机存的收藏、进度」——说多做少也是撒谎，而且它就在按钮底下，比弹窗更容易被当真。
  const caption = /清除缓存[\s\S]{0,600}?list-caption">\s*<text>([\s\S]*?)<\/text>/.exec(wf('pages/settings/settings.wxml'))
  if (!caption) {
    errors.push('settings.wxml 的「清除缓存」行下没有说明文案：影响面必须进页就能看到，而不是等弹窗（J80 / T02787）')
  } else {
    // 逐分句判定：老句子是「清除本机存的收藏、进度…」，新句子是「只清除可再生的技术缓存…，
    // 收藏/进度都会保留」。整串正则分不开这两种（「清除」和「收藏」之间没有标点），
    // 所以按分句切：一个分句里「清除」没被否定词修饰，却又点名了用户数据，就是承诺删数据。
    const NEGATED = /不会清除|不清除|只清除|无需清除|不必清除|已保留|都会保留|都会|不删除/
    for (const clause of caption[1].split(/[；;]/)) {
      if (/清除/.test(clause) && !NEGATED.test(clause) && /(收藏|进度|偏爱|历史|下载|搜索|反馈)/.test(clause)) {
        errors.push('settings.wxml 的行下说明有一个分句在承诺「清除收藏/进度/偏爱」，而 T02787 后实现已经不碰它们了——' +
          `文案与实现脱钩（说多做少同样是撒谎）：${clause.trim().slice(0, 60)}（T02787）`)
        break
      }
    }
    for (const word of ['保留', '本机']) {
      if (!caption[1].includes(word)) {
        errors.push(`settings.wxml 的行下说明没点明「${word}」：与弹窗口径不一致，用户会按旧说明预期后果（T02787）`)
      }
    }
  }

  // —— 21. T02787：字面量 storage key 只许出现在 services/storage-keys.js ——
  // 黑名单之所以会抹数据，根因是 key 名散在各模块、按 openid 动态拼，静态列不全。
  // 这条规则堵住的就是「新页面顺手写死一个 key」：它不会立刻出错，但会让白名单永远漏一项。
  for (const rel of FILES.filter((r) => r.endsWith('.js') && r !== 'services/storage-keys.js')) {
    const src = stripComments(f(rel))
    const hits = []
    if (/wx\.(?:set|get|remove)StorageSync\(\s*['"`]/.test(src)) hits.push('wx.*StorageSync(字面量)')
    if (/(?:set|get)WithTTL\(\s*['"`]/.test(src)) hits.push('set/getWithTTL(字面量)')
    if (/const\s+[A-Z][A-Z0-9_]*KEYS?\s*=\s*['"][a-z_]+['"]/.test(src)) hits.push('本地 const *KEY = 字面量')
    if (hits.length) {
      errors.push(`${rel}: 直接写死 storage key（${hits.join(' / ')}）——请引用 services/storage-keys.js，` +
        '否则「清除缓存」的白名单列不全它，用户数据就会再次被顺手抹掉（T02787）')
    }
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
    if (!/意见反馈/.test(right)) {
      errors.push('隐私政策第七条没有留「意见反馈」人工通道：意见反馈记录被排除在自助删除之外，这类数据只能人工处理（J98 / T02788）')
    }
    if (!/数据与统计/.test(right)) errors.push('隐私政策第七条没把「关闭使用统计」指到设置页的真实分组（J99）')
    // T02788：自助删除接口上线后，政策必须指向它；备份保留期必须与服务端常量一致
    if (!/删除我的数据/.test(right)) {
      errors.push('隐私政策第七条没有指向「设置 → 数据与统计 → 删除我的数据」：自助接口已上线，政策还停在人工通道（T02788）')
    }
    const keepDays = backendConst('services/backup_service.py', '_DEFAULT_KEEP_DAYS')
    const cosKeep = backendConst('config.py', 'COS_BACKUP_KEEP_COUNT')
    if (keepDays === null || cosKeep === null) {
      // 读不到就报错而不是跳过：跨仓比对静默失效，等于保留期没人校验
      errors.push('无法读取服务端备份保留常量（backend/app/services/backup_service.py / config.py）：' +
        '隐私第七条的保留期失去同源校验（T02788）')
    }
    if (keepDays !== null && !right.includes(`${keepDays} 天`)) {
      errors.push(`隐私政策第七条的数据库备份保留期与服务端 _DEFAULT_KEEP_DAYS=${keepDays} 不一致：` +
        '文案写死数字，配置一改就成了第二处谎（T02788）')
    }
    if (cosKeep !== null && !right.includes(`${cosKeep} 份`)) {
      errors.push(`隐私政策第七条的云端备份保留份数与服务端 COS_BACKUP_KEEP_COUNT=${cosKeep} 不一致（T02788）`)
    }
  }
  const cache = privacySection(f('pages/privacy/privacy.js'), 'Cookie')
  if (cache && /不会上传服务器/.test(cache)) {
    errors.push('隐私政策第五条仍写「不会上传服务器」：收藏与播放进度是双写的（J98）')
  }
  // T02787 把「清除缓存」改成只删技术缓存后，第五条旧句「清除缓存只清除本机这一份」反过来撒了谎：
  // 用户按它预期「点了会丢本机收藏」，实际一项不丢；隐私页是全仓对「清缓存后果」的第二处承诺，必须同口径。
  if (cache) {
    if (/清除缓存」只清除本机这一份/.test(cache)) {
      errors.push('隐私政策第五条仍写「清除缓存只清除本机这一份」：实现已经不碰本机用户数据了（T02787）')
    }
    if (!/技术缓存/.test(cache) || !/不会删除服务器/.test(cache)) {
      errors.push('隐私政策第五条没有如实描述「清除缓存」现在的后果（只清可再生技术缓存、不动本机数据、不删服务端）（T02787）')
    }
  }

  // —— 22. T02788：删除我的数据——入口 / 确认口径 / 拆除顺序 ——
  const statsStart = settingsWxml.indexOf('数据与统计')
  const storageStart = settingsWxml.indexOf('存储管理')
  const statsCard = statsStart >= 0
    ? settingsWxml.slice(statsStart, storageStart > statsStart ? storageStart : undefined)
    : ''
  if (!/bindtap="onPurgeMyData"/.test(statsCard)) {
    errors.push('settings.wxml 的「数据与统计」分组没有「删除我的数据」入口：隐私政策第七条又会指向一个不存在的地方（T02788）')
  }
  const purgeBody = methodBody(stripComments(settingsJs), 'onPurgeMyData')
  if (!purgeBody) {
    errors.push('settings.js 缺少 onPurgeMyData：入口绑到了不存在的处理器（T02788）')
  } else {
    if (!/fetchMyDataSummary\s*\(/.test(purgeBody)) {
      errors.push('onPurgeMyData 没有先取预览条数：确认框只能说「确定删除？」，说不出会删掉多少（T02788）')
    }
    if (!/purgeMyData\s*\(/.test(purgeBody)) {
      errors.push('onPurgeMyData 没有调用 purgeMyData：入口点了什么都不会删（T02788）')
    }
    if (!/confirmColor:\s*'#B0554A'/.test(purgeBody)) {
      errors.push('删除我的数据没有用破坏性配色 #B0554A：不可逆动作与普通确认长得一样（T02788）')
    }
    if (!/不可恢复/.test(purgeBody)) {
      errors.push('删除我的数据确认框没有写明不可恢复：用户无法判断这是不可逆操作（T02788）')
    }
    if (!/clearToken\s*\(/.test(purgeBody)) {
      errors.push('删号后没有 clearToken()：本机还留着已被服务端拉黑的登录态（T02788）')
    }
    if (/\blogout\s*\(/.test(purgeBody)) {
      errors.push('onPurgeMyData 用了 logout()：token 已被拉黑，401 自动重登会把刚删掉的账号重新注册出来（T02788）')
    }
  }
  const apiJs = stripComments(f('services/api.js'))
  if (!/const purgeMyData\s*=[\s\S]{0,400}?url:\s*'\/account\/data'[\s\S]{0,200}?method:\s*'DELETE'[\s\S]{0,200}?confirm:\s*true/.test(apiJs)) {
    errors.push('services/api.js 的 purgeMyData 没落到 DELETE /account/data + confirm:true：后端会以缺少二次确认为由拒绝（T02788）')
  }
  if (!/const purgeMyData[\s\S]{0,600}?_allowRetry:\s*false[\s\S]{0,100}?_netRetry:\s*false/.test(apiJs)) {
    errors.push('purgeMyData 没同时关掉两类自动重试：账号删掉后 401 会自动重登注册回来，网络抖动还会二次执行删除（T02788）')
  }
  if (!/if\s*\(!_netRetried\s*&&\s*options\._netRetry\s*!==\s*false\)/.test(apiJs)) {
    errors.push('api.js 的网络重试分支不认 _netRetry：不可逆写操作照样会被自动重发（T02788）')
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

  // —— 8. J21：退出登录文案 ↔ 真实行为 ——
  const logoutBody = methodBody(stripComments(f('pages/profile/profile.js')), 'onLogout')
  if (!logoutBody) {
    errors.push('profile.js 找不到 onLogout：退出登录文案无法定位（J21）')
  } else {
    if (/确定要退出登录吗/.test(logoutBody)) {
      errors.push('profile.js 的退出登录弹窗仍是「确定要退出登录吗？」——用户会以为退出即删除云端数据（J21）')
    }
    for (const word of ['本机', '保留', '意见反馈']) {
      if (!logoutBody.includes(word)) {
        errors.push(`退出登录弹窗没有点明「${word}」：只清本机、云端收藏/进度/记录仍保留，删除需走意见反馈（J21/J98）`)
      }
    }
  }

  // —— 9. J24：登录与编辑资料按钮必须有可见文字 ——
  const profileWxml = wf('pages/profile/profile.wxml')
  if (/btn-icon-only[^>]*login-btn|login-btn[^>]*btn-icon-only/.test(profileWxml)) {
    errors.push('profile 登录按钮仍是纯图标 btn-icon-only：登录是唯一转化动作却没有文字（J24）')
  }
  if (!/<view class="[^"]*login-btn[^"]*"[\s\S]{0,400}?<text[^>]*>\s*[^<\s][^<]*<\/text>/.test(profileWxml)) {
    errors.push('profile 登录按钮内没有可见文案（J24）')
  }
  for (const [cls, label] of [
    ['edit-btn-cancel', '取消'],
    ['edit-btn-confirm', '保存'],
  ]) {
    const re = new RegExp(`class="[^"]*${cls}[^"]*"[\\s\\S]{0,400}?<text[^>]*>\\s*${label}\\s*</text>`)
    if (!re.test(profileWxml)) {
      errors.push(`编辑资料弹窗的「${label}」按钮没有可见文案——两颗纯图标按钮，用户分不清哪颗是保存（J24）`)
    }
  }

  // —— 10. J66：偏爱设置要自述作用面与同步关系 ——
  const prefWxml = wf('pages/preferred-settings/preferred-settings.wxml')
  for (const word of ['首页', '历史', '我的偏爱', '不同步']) {
    if (!prefWxml.includes(word)) {
      errors.push(`preferred-settings.wxml 的说明没有点明「${word}」：偏爱作用于首页/历史的筛选入口，` +
        '且与频道页「订阅」两处勾选各自独立（J66）')
    }
  }

  // —— 11. J105：webview 失败兜底的可见指令与 URL 可核对 ——
  const webWxml = wf('pages/webview/webview.wxml')
  for (const label of ['复制链接', '返回']) {
    if (!webWxml.includes(label)) {
      errors.push(`webview 兜底按钮缺少可见文案「${label}」：失败场景最需要明确指令（J105）`)
    }
  }
  if (/btn-icon-only/.test(webWxml)) {
    errors.push('webview 兜底按钮退回纯图标（btn-icon-only）：用户在两颗无字按钮前无从选择（J105）')
  }
  const urlBlock = /\.fallback-url\s*\{([\s\S]*?)\}/.exec(f('pages/webview/webview.wxss'))
  if (!urlBlock || !/max-height/.test(urlBlock[1]) || !/overflow-y/.test(urlBlock[1])) {
    errors.push('webview 的 .fallback-url 没有高度上限 + 滚动：超长链接会把按钮挤出屏幕，或截断后无法核对（J105）')
  }

  // —— 12. J69：最近播放只首次加载 ——
  const recentShow = methodBody(stripComments(f('pages/recent/recent.js')), 'onShow')
  if (!recentShow || !/_loaded/.test(recentShow) || !/return/.test(recentShow)) {
    errors.push('recent.js 的 onShow 没有首次加载保护：每次从详情返回都会重置分页与滚动位置（J69）')
  }

  // —— 13. J77：队列单项管理单源 + 两个出口都接线 ——
  const audioSvc = f('services/audio.js')
  for (const fn of ['removeQueueAt', 'moveQueueItem']) {
    if (!new RegExp(`function ${fn}\\s*\\(`).test(audioSvc)) {
      errors.push(`services/audio.js 缺少 ${fn}：队列单项管理没有单源实现（J77）`)
    }
    if (!new RegExp(`module\\.exports[\\s\\S]*\\b${fn}\\b`).test(audioSvc)) {
      errors.push(`services/audio.js 未导出 ${fn}：队列页与详情页只能各写一套（J77）`)
    }
  }
  for (const [rel, names] of [
    ['pages/queue/queue.wxml', ['onMoveItem', 'onRemoveItem']],
    ['pages/detail/detail.wxml', ['onQueueMove', 'onQueueRemove']],
  ]) {
    for (const name of names) {
      if (!new RegExp(`catchtap="${name}"`).test(wf(rel))) {
        errors.push(`${rel} 的队列项没有 ${name} 入口：单项移出/排序仍然只能整表清空（J77）`)
      }
    }
  }
  // 角标口径（验收第 4 项）：删除中间项与把当前项上移都会改「当前条之后还剩几条」，
  // 所以队列变更必须实时驱动角标；只靠 tab 页 onShow 补挂会出现「列表变了、角标还是旧数字」。
  if (!/onQueueChange\(\(\)\s*=>\s*refreshTabBadge\(\)\)/.test(stripComments(f('app.js')))) {
    errors.push('app.js 没把 onQueueChange 接到 refreshTabBadge：队列删除/重排后「历史」tab 角标停在旧数字（J77）')
  }

  // —— 14. J14/J12：历史的两个出口 ——
  const historyWxml = wf('pages/history/history.wxml')
  if (!/我的播放记录/.test(historyWxml) || !/bindtap="onOpenRecent"/.test(historyWxml)) {
    errors.push('history.wxml 没有直达「我的播放记录」的可见入口：两份"过去"数据仍然分不清（J14）')
  }
  if (!/pages\/recent\/recent/.test(f('pages/history/history.js'))) {
    errors.push('history.js 的「我的播放记录」入口没有指向 recent 页（J14）')
  }
  if (!/class="[^"]*queue-chip[^"]*"[\s\S]{0,300}?<text[^>]*>\s*队列\s*<\/text>/.test(historyWxml)) {
    errors.push('history.wxml 的队列入口仍是纯图标 chip：全站唯一队列整页入口没有文字（J12）')
  }
  if (!/pages\/queue\/queue/.test(f('pages/history/history.js'))) {
    errors.push('history.js 的队列入口没有指向 queue 页（J12）')
  }

  // —— 15. J20：个人中心第二层只做入口 ——
  const profileJs = f('pages/profile/profile.js')
  if (!/second-entry-card/.test(profileWxml) || !/bindtap="goSecondPage"/.test(profileWxml)) {
    errors.push('profile 第二层没有收敛为单入口 second-entry-card → goSecondPage（J20）')
  }
  if (/secondList/.test(profileWxml) || /secondList/.test(profileJs)) {
    errors.push('profile 仍保留 secondList 内嵌列表：与 recent/favorites/channels/download/preferred 整页形成第二套取数与渲染（J20）')
  }
  // T02735：上面两条挡不住「换个变量名把列表搬回来」和「页签与入口对不上」。
  // 入口卡内部再出现 wx:for 即视为列表回流；第二层五枚页签必须与 SECOND_PAGES 一一对应，
  // 每条路由要真的注册在 app.json、且落到该页签自己的整页（否则点了跳不动或跳错页）。
  const panelStart = profileWxml.indexOf('second-panel')
  const panelEnd = panelStart < 0 ? -1 : profileWxml.indexOf('course-card', panelStart)
  const panelBody = panelEnd > panelStart ? profileWxml.slice(panelStart, panelEnd) : ''
  if (!panelBody) {
    errors.push('profile 第二层入口卡（second-panel）定位失败：结构被改名后无法校验是否退回内嵌列表（J20/T02735）')
  } else if (/wx:for/.test(panelBody)) {
    errors.push('profile 第二层入口卡里又出现 wx:for：列表渲染搬回了「我的」页（J20/T02735）')
  }
  const subBarStart = profileWxml.indexOf('tab-bar-sub')
  const subBar = subBarStart < 0 ? '' : profileWxml.slice(subBarStart, panelStart > subBarStart ? panelStart : undefined)
  const tabKeys = [...subBar.matchAll(/data-tab="([A-Za-z0-9_]+)"/g)].map((m) => m[1])
  const pagesBlock = (profileJs.match(/const SECOND_PAGES = \{[\s\S]*?\n {2}\}/) || [''])[0]
  const entries = [...pagesBlock.matchAll(/^\s{4,8}([A-Za-z0-9_]+):\s*\{\s*url:\s*"([^"]+)"/gm)]
    .map((m) => ({ key: m[1], url: m[2] }))
  if (!tabKeys.length || !entries.length) {
    errors.push('profile 第二层页签或 SECOND_PAGES 解析不到：tab↔入口一致性没有被校验（J20/T02735）')
  } else {
    const entryKeys = entries.map((e) => e.key)
    for (const key of tabKeys.filter((k) => !entryKeys.includes(k))) {
      errors.push(`profile 第二层页签 ${key} 没有对应入口：点进去是一张空白卡片（J20/T02735）`)
    }
    for (const key of entryKeys.filter((k) => !tabKeys.includes(k))) {
      errors.push(`SECOND_PAGES 里的 ${key} 没有对应页签：这段入口永远点不到（J20/T02735）`)
    }
    const pageRoutes = (() => {
      try {
        return (JSON.parse(f('app.json')).pages || []).map(normPage)
      } catch (err) {
        return []
      }
    })()
    for (const { key, url } of entries) {
      const target = normPage(url)
      if (!pageRoutes.includes(target)) {
        errors.push(`SECOND_PAGES.${key} 指向未注册页面 ${url}：goSecondPage 的 navigateTo 必然失败（J20/T02735）`)
      }
      // 接错对象：入口必须落到该页签自己的整页，而不是「随便哪个已注册页面」
      // downloads → download 这类单复数差异用去 s 的词干兜住
      const stems = key.endsWith('s') ? [key, key.slice(0, -1)] : [key]
      if (!stems.some((stem) => target.includes(stem))) {
        errors.push(`SECOND_PAGES.${key} 指向 ${url}，与该页签不对应：入口把用户带到了别的页（J20/T02735）`)
      }
    }
  }
  if (/\bsecondPage\b/.test(profileJs)) {
    errors.push('profile.js 又把第二层跳转拆成 secondPage 与 secondEntry.url 两份状态（J20/T02735）')
  }

  // —— 16. J27：缓冲态必须真的呈现 ——
  const detailWxml = wf('pages/detail/detail.wxml')
  if (!/wx:if="\{\{isWaiting\}\}"/.test(detailWxml) || !/缓冲中/.test(detailWxml)) {
    errors.push('detail.wxml 没有绑定 isWaiting 的「缓冲中」节点：弱网起播与正常播放同貌（J27）')
  }
  // J27/T02798 的第二半：缓冲态不得「伪装成可播放」。只显示菊花而入口照旧可点，
  // 用户拖完进度条位置又被 onTimeUpdate 拉回去，观感等于「界面骗人」。
  if (!/disabled="\{\{isWaiting\}\}"/.test(detailWxml)) {
    errors.push('detail.wxml 的进度 slider 没在缓冲时 disabled：缓冲态仍伪装成可拖动（J27）')
  }
  const rateChipMatch = /bindtap="onCycleRate"[\s\S]{0,120}?aria-label="([^"]*)"/.exec(detailWxml)
  if (!rateChipMatch || !/isWaiting/.test(rateChipMatch[1])) {
    errors.push('倍速入口在缓冲时仍报「切换播放倍速」：可访问性与可见性都说不出「现在点了没用」（J27）')
  }
  const detailJsForWaiting = stripComments(f('pages/detail/detail.js'))
  for (const gated of ['onSeekInput', 'onSeek', 'onCycleRate']) {
    if (!/isWaiting/.test(methodBody(detailJsForWaiting, gated))) {
      errors.push(`detail.js ${gated} 没有 isWaiting 护栏：WXML 的 disabled 之外还得有 JS 侧兜底（J27）`)
    }
  }

  // —— 17. J28：课程语境字段必须显示 ——
  if (!/wx:if="\{\{isCourse\}\}"/.test(detailWxml) || !/courseName/.test(detailWxml) || !/chapterLabel/.test(detailWxml)) {
    errors.push('detail.wxml 不显示课程名/章节坐标：从课程页进入后用户失去位置感（J28）')
  }

  // —— 18. J32/J59：失败可重试，已下载条目断网可播 ——
  if (!/bindtap="onRetryLoad"/.test(detailWxml) || !/onRetryLoad\s*\(/.test(f('pages/detail/detail.js'))) {
    errors.push('detail 失败态缺「重试」入口或 onRetryLoad 实现：断网进页只能退回去（J32）')
  }
  const loadDetailBody = methodBody(stripComments(f('pages/detail/detail.js')), 'loadDetail')
  if (!/downloadStore\.getDownload\(/.test(loadDetailBody) ||
      !/audio_url:\s*rec\.localPath/.test(loadDetailBody) ||
      !/offlinePlayback:\s*true/.test(loadDetailBody)) {
    errors.push('detail.loadDetail 失败时不再用下载记录的 localPath 兜底：已下载条目断网仍落到失败页（J59）')
  }
  if (!/data-guide="detail-offline-note"/.test(detailWxml) || !/本机已下载/.test(detailWxml)) {
    errors.push('离线兜底没有可见说明：用户分不清播的是网络数据还是本机下载（J59）')
  }
  if (!/function getDownload\s*\(/.test(f('services/download.js'))) {
    errors.push('services/download.js 缺少 getDownload：详情页拿不到 localPath 做离线兜底（J59）')
  }

  // —— 19. J73：已下架要有文字标签，点击行为要说清 ——
  if (!/已下架/.test(wf('pages/favorites/favorites.wxml')) || !/data-available="\{\{item\.available\}\}"/.test(wf('pages/favorites/favorites.wxml'))) {
    errors.push('favorites.wxml 的已下架条目没有「已下架」文字标签或未把 available 传给点击逻辑（J73）')
  }
  if (!/available === false/.test(f('pages/favorites/favorites.js')) ||
      !/isDownloaded\(/.test(f('pages/favorites/favorites.js'))) {
    errors.push('favorites.js 未区分「下架且本机无下载」：点击要么静默失败，要么把已下载条目也挡掉（J73）')
  }

  // —— 20. J81：检查更新必须等真实回调 ——
  const checkUpdateBody = methodBody(stripComments(settingsJs), 'onCheckUpdate')
  if (!/onCheckForUpdate\(\(res\)/.test(checkUpdateBody)) {
    errors.push('settings.js 的检查更新不再读 onCheckForUpdate 回调结果（J81）')
  }
  if (!/if\s*\(res\.hasUpdate\)[\s\S]{0,400}else\s*\{[\s\S]{0,120}已是最新版本/.test(checkUpdateBody)) {
    errors.push('「已是最新版本」不在 res.hasUpdate 的 else 分支里：仍会在真有更新时先报最新（J81）')
  }
  if (!/检查超时/.test(checkUpdateBody) || /\},\s*2000\)/.test(checkUpdateBody)) {
    errors.push('检查更新仍用 2s 固定兜底并冒充「已是最新」：应等回调，超时如实说「检查超时」（J81）')
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
