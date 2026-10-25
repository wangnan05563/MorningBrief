/**
 * 本机 storage key 单源与分类（T02787 / J80 续）
 *
 * 运行：node --test apps/miniprogram/tests/storage-keys.test.js
 *
 * J80 的事故形态是「清缓存用黑名单，把 KEEP_KEYS 之外的 key 全删了」，而运行时一个异常
 * 都不会抛：界面照样绿，只是用户的收藏/进度/偏爱没了。所以这里测的不是某个函数算得对不对，
 * 而是三件容易在后续重构里悄悄散掉的事：
 *  1. key 名逐字不许动（改了老用户本机数据就读不到，界面上等价于「数据凭空消失」）；
 *  2. 分类必须穷尽且互斥（同一 key 既算缓存又算数据 = 清除策略自相矛盾；
 *     没登记的 key 必须落 unknown 而不是被当成可清除项）；
 *  3. 清除动作真的走白名单执行口，而不是在页面里重新循环一遍 storage。
 */
const { test, describe } = require('node:test')
const assert = require('node:assert')
const fs = require('node:fs')
const path = require('node:path')

const MP_ROOT = path.resolve(__dirname, '..')
const storageKeys = require('../services/storage-keys')

const read = (rel) => fs.readFileSync(path.join(MP_ROOT, rel), 'utf8')

describe('兼容红线：key 名逐字冻结', () => {
  test('固定 key 名与重构前一致（改名=老用户本机数据读不到）', () => {
    assert.deepStrictEqual(storageKeys.STATIC, {
      TOKEN: 'news_token',
      USER: 'news_user',
      SETTINGS: 'news_settings',
      PREFERRED_ONBOARDED: 'preferred_channels_onboarded',
      MANUAL_API_BASE_URL: 'manual_api_base_url',
      LAST_SUCCESS_API_BASE_URL: 'last_success_api_base_url',
      SEARCH_HISTORY: 'search_history',
      FEEDBACK_HISTORY: 'news_feedback_history',
      PENDING_REPORTS: 'pending_play_reports',
      LAST_PLAYED_EPISODE: 'lastPlayedEpisode',
    })
  })

  test('动态 key 前缀与重构前一致', () => {
    assert.deepStrictEqual(storageKeys.PREFIX, {
      PROGRESS: 'news_progress_',
      FAVORITES: 'news_favorites_',
      HISTORY: 'news_history_',
      PREFERRED_CHANNELS: 'news_preferred_channels_',
      DOWNLOADS: 'news_downloads_',
      SILENT_ENRICH_SKIP: 'skipSilentEnrich_',
    })
  })

  test('动态 key 生成函数拼出来的还是原来那几个串', () => {
    const openid = 'oABC123'
    assert.strictEqual(storageKeys.progressKey(openid), `news_progress_${openid}`)
    assert.strictEqual(storageKeys.favoritesKey(openid), `news_favorites_${openid}`)
    assert.strictEqual(storageKeys.historyKey(openid), `news_history_${openid}`)
    assert.strictEqual(storageKeys.preferredChannelsKey(openid), `news_preferred_channels_${openid}`)
    assert.strictEqual(storageKeys.downloadsKey(openid), `news_downloads_${openid}`)
    assert.strictEqual(storageKeys.silentEnrichSkipKey(openid), `skipSilentEnrich_${openid}`)
  })
})

describe('分类表：穷尽、互斥、不认的不删', () => {
  /** 把三张表拉平到同一层再比交集，前缀表和字面表分开比会漏掉「前缀正好等于某 key」这种撞名 */
  const allOf = (keys, prefixes) => keys.concat(prefixes.map((p) => `${p}openid`))

  test('KEEP / CACHE / USER_DATA 三类两两不相交', () => {
    const keep = allOf(storageKeys.KEEP_KEYS, storageKeys.KEEP_PREFIXES)
    const cache = allOf(storageKeys.CACHE_KEYS, storageKeys.CACHE_PREFIXES)
    const user = allOf(storageKeys.USER_DATA_KEYS, storageKeys.USER_DATA_PREFIXES)
    const intersection = (a, b) => a.filter((x) => b.includes(x))
    assert.deepStrictEqual(intersection(cache, user), [], 'CACHE ∩ USER_DATA 非空：同一份数据既算可清除又算用户数据')
    assert.deepStrictEqual(intersection(keep, cache), [], 'KEEP ∩ CACHE 非空：清缓存会删掉自己声明要保留的 key')
    assert.deepStrictEqual(intersection(keep, user), [], 'KEEP ∩ USER_DATA 非空：同一 key 两个口径，文案没法说实话')
  })

  test('每个 STATIC/PREFIX 都登记了类别，没有落单的 key', () => {
    for (const [name, key] of Object.entries(storageKeys.STATIC)) {
      assert.notStrictEqual(storageKeys.categoryOf(key), 'unknown', `STATIC.${name}=${key} 没进任何一张分类表`)
    }
    for (const [name, prefix] of Object.entries(storageKeys.PREFIX)) {
      assert.notStrictEqual(
        storageKeys.categoryOf(`${prefix}openid`),
        'unknown',
        `PREFIX.${name}=${prefix} 没进任何一张分类表：新加动态 key 忘了归类，清缓存就会把它当未知项绕过审计`,
      )
    }
  })

  test('工单点名的被误删项全部不是可清除项', () => {
    for (const key of [
      storageKeys.STATIC.SEARCH_HISTORY,
      storageKeys.STATIC.FEEDBACK_HISTORY,
      storageKeys.STATIC.PENDING_REPORTS,
      storageKeys.STATIC.LAST_PLAYED_EPISODE,
      storageKeys.favoritesKey('o'),
      storageKeys.progressKey('o'),
      storageKeys.historyKey('o'),
      storageKeys.preferredChannelsKey('o'),
      storageKeys.downloadsKey('o'),
    ]) {
      assert.strictEqual(storageKeys.categoryOf(key), 'user', `${key} 被归成了可清除项——J80 就是这么抹掉数据的`)
    }
  })

  test('认不出的 key 归 unknown，且绝不会被清除动作删掉', () => {
    assert.strictEqual(storageKeys.categoryOf('some_future_key'), 'unknown')
    assert.strictEqual(storageKeys.categoryOf(''), 'unknown')
    assert.strictEqual(storageKeys.categoryOf(undefined), 'unknown')
    assert.strictEqual(storageKeys.categoryOf(42), 'unknown')
    const removed = []
    storageKeys.clearCacheKeys(['some_future_key', 'news_token', 'last_success_api_base_url'], (k) => removed.push(k))
    assert.deepStrictEqual(removed, ['last_success_api_base_url'], '清除动作删了白名单之外的 key')
  })
})

describe('清除执行口：只按白名单删，并如实回报删了什么', () => {
  /** 假 storage：把真机上 getStorageInfoSync 会返回的全集摆出来，逐个核对删除结果 */
  const fakeStore = () => ({
    'news_token': 't',
    'news_user': { openid: 'o' },
    'news_settings': { usageTracking: false },
    'preferred_channels_onboarded': true,
    'manual_api_base_url': 'http://1.2.3.4:8000',
    'last_success_api_base_url': 'http://1.2.3.4:8000',
    'search_history': ['人工智能'],
    'news_feedback_history': [],
    'pending_play_reports': [{ episode_id: 1 }],
    'lastPlayedEpisode': { id: 1 },
    'news_progress_o': {},
    'news_favorites_o': [],
    'news_history_o': [],
    'news_preferred_channels_o': ['1'],
    'news_downloads_o': {},
    'skipSilentEnrich_o': true,
    'version_cache_key': 'v',
  })

  test('清缓存只删可再生技术缓存，其余一个不动', () => {
    const store = fakeStore()
    const removed = storageKeys.clearCacheKeys(Object.keys(store), (key) => {
      delete store[key]
    })
    assert.deepStrictEqual(removed, ['last_success_api_base_url'])
    assert.deepStrictEqual(Object.keys(store), Object.keys(fakeStore()).filter((k) => k !== 'last_success_api_base_url'))
  })

  test('planCacheRemoval 是纯查询：不碰 storage 也能先给 UI 算影响面', () => {
    const store = fakeStore()
    assert.deepStrictEqual(storageKeys.planCacheRemoval(Object.keys(store)), ['last_success_api_base_url'])
    assert.deepStrictEqual(Object.keys(store), Object.keys(fakeStore()), 'planCacheRemoval 不该有副作用')
    assert.deepStrictEqual(storageKeys.planCacheRemoval(undefined), [])
    assert.deepStrictEqual(storageKeys.planCacheRemoval([]), [])
  })

  test('空 storage（首次启动）清除返回空表而不是报错', () => {
    const calls = []
    assert.deepStrictEqual(storageKeys.clearCacheKeys([], (k) => calls.push(k)), [])
    assert.deepStrictEqual(calls, [])
  })
})

describe('升级兼容：老用户本机已有的 key 必须仍读得到', () => {
  /** 这些串是重构前（T02787 之前）各模块自己写死的 key 名，本用例按「老版本留下的数据」原样铺 */
  const LEGACY = {
    news_user: { openid: 'oLEGACY' },
    news_token: 'tk',
    news_settings: { usageTracking: false },
    news_favorites_oLEGACY: [{ id: 7, title: '旧收藏', audio_url: 'u', duration: 100 }],
    news_progress_oLEGACY: { 7: { position: 30, duration: 100, completed: false, updated_at: 1 } },
    news_history_oLEGACY: [{ id: 7, title: '旧收藏', played_at: 1, position: 30 }],
    news_preferred_channels_oLEGACY: [3],
    news_downloads_oLEGACY: { 7: { episodeId: 7, localPath: 'wxfile://legacy-7.mp3', size: 1024, title: '旧收藏', savedAt: 1 } },
    search_history: ['人工智能'],
    lastPlayedEpisode: { id: 7 },
  };

  let store;
  let cleanup;

  function seedAndLoad() {
    store = JSON.parse(JSON.stringify(LEGACY));
    global.wx = {
      getStorageSync: (k) => (k in store ? store[k] : ''),
      setStorageSync: (k, v) => { store[k] = v; },
      removeStorageSync: (k) => { delete store[k]; },
      getStorageInfoSync: () => ({ keys: Object.keys(store) }),
      setStorage: (o) => { store[o.key] = o.data; o.success && o.success(); },
      // 本地命中后 local-data 会「不阻塞地」同步后端；给个空成功响应，让它安静走完而不抛未处理拒绝
      request: (o) => { o.success && o.success({ statusCode: 200, data: { code: 0, data: null } }); },
      getFileSystemManager: () => ({ removeSavedFile: () => {} }),
      env: { USER_DATA_PATH: '/tmp' },
      showToast: () => {},
      showModal: () => {},
    };
    global.getApp = () => ({ globalData: { baseUrl: 'http://test.local', token: 'tk' } });
    // 真机上这些模块由页面首次 require；Node 的 require 缓存会让后续用例拿到脏的内存缓存，
    // 所以每次从缓存里删掉再 require，模拟「新启动一次小程序」
    cleanup = ['services/local-data.js', 'services/download.js', 'services/auth.js']
      .map((rel) => path.join(MP_ROOT, rel))
      .filter((abs) => require.cache[abs]);
    for (const abs of cleanup) delete require.cache[abs];
    return {
      localData: require('../services/local-data'),
      download: require('../services/download'),
    };
  }

  test('收藏/偏爱/下载索引/设置：换到单源后读的还是同一批 key', async () => {
    const { localData, download } = seedAndLoad();
    try {
      assert.deepStrictEqual((await localData.getFavoriteList()).map((i) => i.id), [7], '老用户本机收藏读不到了（key 改名）');
      assert.deepStrictEqual(localData.getPreferredChannels(), [3], '老用户本机偏爱读不到了');
      assert.strictEqual((await localData.getProgress(7)).position, 30, '老用户本机断点续播位置读不到了');
      assert.strictEqual(download.isDownloaded(7), true, '老用户本机下载索引读不到了');
      assert.strictEqual(download.getDownloadLocalPath(7), 'wxfile://legacy-7.mp3');
      assert.strictEqual(JSON.stringify(store.news_settings), JSON.stringify({ usageTracking: false }), '统计开关落到了另一个 key');
      assert.deepStrictEqual(store.search_history, ['人工智能'], '搜索历史被清缓存顺手抹掉（J80）');
      assert.deepStrictEqual(store.lastPlayedEpisode, { id: 7 }, '上次播放项被清缓存顺手抹掉（J80）');

    } finally {
      delete global.wx;
      delete global.getApp;
      for (const abs of cleanup) delete require.cache[abs];
    }
  })

  test('这份遗留数据过一遍「清除缓存」，除技术缓存外一条不少', async () => {
    const { localData } = seedAndLoad();
    try {
      const before = Object.keys(store).filter((k) => k !== 'news_token' && k !== 'news_user');
      storageKeys.clearCacheKeys(Object.keys(store), (key) => { delete store[key]; });
      const after = Object.keys(store).filter((k) => k !== 'news_token' && k !== 'news_user');
      assert.deepStrictEqual(
        before.filter((k) => !after.includes(k)),
        ['last_success_api_base_url'].filter((k) => before.includes(k)),
        '清除缓存放掉了 J80 那批 key',
      );
      assert.deepStrictEqual((await localData.getFavoriteList()).map((i) => i.id), [7]);
    } finally {
      delete global.wx;
      delete global.getApp;
      for (const abs of cleanup) delete require.cache[abs];
    }
  })
})

describe('接线：页面与读写方真的引用单源', () => {
  test('settings.js 走执行口，不再自己循环 storage 做黑名单', () => {
    const js = read('pages/settings/settings.js')
    assert.match(js, /require\('\.\.\/\.\.\/services\/storage-keys'\)/, 'settings.js 没有引用单源')
    assert.match(js, /clearCacheKeys\(/, 'settings.js 没有调用 clearCacheKeys：删哪些又回到页面自己说了算')
    assert.doesNotMatch(js, /KEEP_KEYS\.indexOf\(key\)\s*===\s*-1/, 'settings.js 回到「KEEP_KEYS 之外全删」的黑名单——J80 事故那一行')
  })

  test('工单点名的四个读写模块都从单源拿 key', () => {
    for (const rel of ['services/local-data.js', 'services/download.js', 'pages/search/search.js', 'pages/feedback/feedback.js']) {
      assert.match(read(rel), /storage-keys/, `${rel} 不再引用单源：key 名出现第二处，分类表就不再等于全集`)
    }
  })

  test('字面量 key 只许出现在 services/storage-keys.js（全仓兜底扫描）', () => {
    // ux604 规则 21 按 FILES 清单点名，清单可能漏文件；这条按目录扫，新页面写死 key 当场红
    const patterns = [
      /wx\.(?:set|get|remove)StorageSync\(\s*['"`][a-zA-Z_]+['"`]/,
      /(?:set|get)WithTTL\(\s*['"`][a-zA-Z_]+['"`]/,
      /wx\.(?:set|get)Storage\(\s*\{\s*key:\s*['"`][a-zA-Z_]+['"`]/,
    ]
    /** 只看真代码：utils/storage.js 的用法示例写在注释里，把它当违规就是误报——误报的门禁等于没有门禁 */
    const stripComments = (text) =>
      text
        .split('\n')
        .filter((line) => !/^\s*(\/\/|\*|\/\*)/.test(line))
        .join('\n')
    const hits = []
    const walk = (dir) => {
      for (const entry of fs.readdirSync(path.join(MP_ROOT, dir), { withFileTypes: true })) {
        const rel = path.posix.join(dir, entry.name)
        if (entry.isDirectory()) {
          if (entry.name === 'tests' || entry.name === 'scripts' || entry.name === 'node_modules') continue
          walk(rel)
          continue
        }
        if (!entry.name.endsWith('.js') || rel === 'services/storage-keys.js') continue
        const src = stripComments(read(rel))
        for (const re of patterns) {
          const line = src.split('\n').findIndex((l) => re.test(l))
          if (line >= 0) hits.push(`${rel}:${line + 1} ${re}`)
        }
      }
    }
    for (const dir of ['pages', 'components', 'services', 'utils']) walk(dir)
    assert.deepStrictEqual(hits, [], '这些位置还在写死 storage key，请改引 services/storage-keys.js')
  })
})
