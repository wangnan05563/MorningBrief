/**
 * M3-D（FR-UX-302 / J4·J11·J16·J39·J106）：失败态与空态是两件事
 *
 * validate-error-vs-empty.mjs 静态守住模板分支与重试接线；这里锁 JS 侧行为：
 *  - 首次取数失败 → 挂 loadError（渲染失败态 + 重试），不能吞掉变成「暂无内容」；
 *  - 已有内容时翻页失败 → 只 toast，不能把整页换成失败态；
 *  - 成功回来必须清掉 loadError，否则重试成功仍挂着失败态；
 *  - J11：历史行点击只跳详情，不发声（播放按钮才 catchtap 到 onPlay）。
 *
 * 方法体从真实源码里提取（与 detail-waiting-guard.test.js 同款），改坏源码会让这里红，
 * 而不是测一份手写镜像。
 *
 * 运行：node --test apps/miniprogram/tests/error-vs-empty.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const PAGES = path.join(__dirname, '..', 'pages');
const srcOf = (rel) => fs.readFileSync(path.join(PAGES, rel), 'utf8');

/** 按方法名取方法体；找不到就抛，避免空体假绿 */
function bodyOf(src, name) {
  const start = src.search(new RegExp(`^ {2}(?:async )?${name}\\s*\\(`, 'm'));
  if (start < 0) throw new Error('找不到方法 ' + name + '（改名或删除了？）');
  const rest = src.slice(start);
  const rest2 = rest.replace(/^ {2}(?:async )?[\w$]+\s*\([^)]*\)\s*\{/, '');
  const end = rest2.search(/\n {2}\}/);
  assert.ok(end > 0, name + ' 方法体截取失败');
  return rest2.slice(0, end);
}

/** 统一按 async 编译：同步方法也能跑，调用方 await 即可 */
function compile(src, name, args) {
  const body = bodyOf(src, name);
  // eslint-disable-next-line no-new-func
  return new Function(`return async function(${args.join(',')}){${body}}`)();
}

function makePage(data) {
  const calls = { setData: [], toast: [], lc: [] };
  const page = {
    data: Object.assign({}, data),
    setData(obj) {
      calls.setData.push(obj);
      Object.assign(page.data, obj);
    },
    _lc: {
      start: () => calls.lc.push('start'),
      finish: () => calls.lc.push('finish'),
      fail: () => calls.lc.push('fail'),
    },
  };
  return { page, calls };
}

/** wx 桩：记录 showToast 文案，供断言「有没有被吞成一句提示」 */
function makeWx() {
  const calls = [];
  return { wx: { showToast: (o) => calls.push(o.title) }, calls };
}

describe('history.loadHistory：首屏失败挂错误，翻页失败只 toast', () => {
  const src = srcOf('history/history.js');
  const load = compile(src, 'loadHistory', ['first', 'fetchHistory', 'localData', 'wx', 'RENDER_STEP']);
  const base = {
    loading: false, hasMore: true, page: 1, size: 20, total: 0, sortOrder: 'desc',
    currentChannelId: null, isPreferredMode: false, preferredIds: [], list: [],
  };

  test('首屏失败：写 loadError，且不弹 toast（失败态自己带重试）', async () => {
    const { page, calls } = makePage({ ...base, list: [] });
    const { wx, calls: toast } = makeWx();
    await load.call(page, true, () => Promise.reject(new Error('接口 502')), { getPreferredChannels: () => [] }, wx, 20);
    assert.strictEqual(page.data.loadError, '接口 502');
    assert.deepEqual(toast, [], '首屏失败不该只 toast 一句');
    assert.ok(calls.lc.includes('fail'));
  });

  test('翻页失败（列表已有内容）：只 toast，不把整页换成失败态', async () => {
    const { page, calls } = makePage({ ...base, list: [{ id: 1 }], page: 2 });
    const { wx, calls: toast } = makeWx();
    await load.call(page, false, () => Promise.reject(new Error('分页超时')), { getPreferredChannels: () => [] }, wx, 20);
    assert.deepEqual(calls.setData.filter((o) => 'loadError' in o), [], '已有列表时不该挂整页失败态');
    assert.deepEqual(toast, ['分页超时']);
  });

  test('成功回来清空 loadError（重试成功后失败态要退场）', async () => {
    const { page } = makePage({ ...base, loadError: '上次失败' });
    const { wx } = makeWx();
    const fetchOk = () => Promise.resolve({ list: [{ id: 9, channel_id: 1 }], total: 1 });
    page._enrichEpisode = (ep) => ep;
    page._applyFilter = () => {};
    await load.call(page, true, fetchOk, { getPreferredChannels: () => [] }, wx, 20);
    assert.strictEqual(page.data.loadError, '');
  });
});

describe('history.onOpenDetail：行点击只跳详情，不发声（J11）', () => {
  const src = srcOf('history/history.js');
  const fn = compile(src, 'onOpenDetail', ['e', 'trackEvent', 'wx']);

  test('跳转到详情页，且方法体里没有 setQueue / playEpisode', async () => {
    const body = bodyOf(src, 'onOpenDetail');
    assert.doesNotMatch(body, /setQueue|playEpisode/, '行点击一旦发声，浏览就会打断当前播放');
    const navigated = [];
    const { page, calls } = makePage({});
    await fn.call(page, { currentTarget: { dataset: { id: 42 } } }, () => {}, {
      navigateTo: (o) => navigated.push(o.url),
    });
    assert.deepEqual(navigated, ['/pages/detail/detail?id=42']);
    assert.deepEqual(calls.setData, []);
  });

  test('无线上的模板接线：整行走 onOpenDetail，播放按钮 catchtap 到 onPlay', () => {
    const wxml = srcOf('history/history.wxml');
    assert.match(wxml, /bindtap="onOpenDetail"/);
    assert.match(wxml, /catchtap="onPlay"/);
  });
});

describe('search.doSearch：首页失败挂错误态，翻页失败只 toast', () => {
  const src = srcOf('search/search.js');
  const doSearch = compile(src, 'doSearch', ['keyword', 'page', 'searchEpisodes', 'skin', 'wx']);
  const base = { filterType: 'all', results: [], loading: false, keyword: '新闻', loadError: '' };
  const skinStub = { getChannelTypeLabel: () => '资讯' };

  test('第 1 页失败：写 loadError，不弹 toast', async () => {
    const { page } = makePage(base);
    const { wx, calls: toast } = makeWx();
    await doSearch.call(page, '新闻', 1, () => Promise.reject(new Error('搜索超时')), skinStub, wx);
    assert.strictEqual(page.data.loadError, '搜索超时');
    assert.deepEqual(toast, []);
  });

  test('第 2 页失败且已有结果：只 toast，保留结果', async () => {
    const { page } = makePage({ ...base, results: [{ id: 1 }] });
    const { wx, calls: toast } = makeWx();
    await doSearch.call(page, '新闻', 2, () => Promise.reject(new Error('分页失败')), skinStub, wx);
    assert.strictEqual(page.data.loadError, '');
    assert.deepEqual(toast, ['分页失败']);
    assert.strictEqual(page.data.results.length, 1);
  });

  test('搜索成功清空上一轮的 loadError', async () => {
    const { page } = makePage({ ...base, loadError: '上次失败' });
    page.saveHistory = () => {};
    const { wx } = makeWx();
    const ok = () => Promise.resolve({ list: [{ id: 2, channel_type: 'news' }], total: 1 });
    await doSearch.call(page, '新闻', 1, ok, skinStub, wx);
    assert.strictEqual(page.data.loadError, '');
  });

  test('onRetryLoad 用当前关键词重搜第 1 页；无关键词不发请求', async () => {
    const retry = compile(src, 'onRetryLoad', []);
    const noKeyword = makePage({ keyword: '' }).page;
    let called = 0;
    noKeyword.doSearch = () => { called += 1; };
    await retry.call(noKeyword);
    assert.strictEqual(called, 0);

    const withKeyword = makePage({ keyword: '要闻' }).page;
    const args = [];
    withKeyword.doSearch = (...a) => args.push(a);
    await retry.call(withKeyword);
    assert.deepEqual(args, [['要闻', 1]]);
  });
});

describe('channels.loadChannels：失败挂错误态，成功清空', () => {
  const src = srcOf('channels/channels.js');
  const load = compile(src, 'loadChannels', ['fetchChannels']);

  test('失败：loadError 有值，骨架被 fail() 收起（否则重试入口不可达）', async () => {
    const { page, calls } = makePage({ channels: [] });
    await load.call(page, () => Promise.reject(new Error('频道接口挂了')), undefined);
    assert.strictEqual(page.data.loadError, '频道接口挂了');
    assert.deepEqual(calls.lc, ['start', 'fail']);
  });

  test('成功：写列表并清空 loadError', async () => {
    const { page } = makePage({ channels: [], loadError: '上次失败' });
    await load.call(page, () => Promise.resolve({ list: [{ id: 1 }] }));
    assert.deepEqual(page.data.channels, [{ id: 1 }]);
    assert.strictEqual(page.data.loadError, '');
  });
});

describe('recent.loadRecent / favorites.loadFavorites：同一条判据', () => {
  test('recent 首屏失败挂错误态；翻页失败只 toast', async () => {
    const src = srcOf('recent/recent.js');
    const load = compile(src, 'loadRecent', ['first', 'localData', 'wx']);
    const base = { loading: false, hasMore: true, page: 1, list: [], loadError: '' };

    const first = makePage({ ...base });
    const { wx, calls: toast } = makeWx();
    const failGet = { getHistory: () => Promise.reject(new Error('记录读取失败')) };
    await load.call(first.page, true, failGet, wx);
    assert.strictEqual(first.page.data.loadError, '记录读取失败');
    assert.deepEqual(toast, []);

    const next = makePage({ ...base, page: 2, list: [{ id: 1 }] });
    const { wx: wx2, calls: toast2 } = makeWx();
    const failPage = { getHistory: () => Promise.reject(new Error('翻页失败')) };
    await load.call(next.page, false, failPage, wx2);
    assert.strictEqual(next.page.data.loadError, '');
    assert.deepEqual(toast2, ['翻页失败']);
  });

  test('favorites 空列表失败挂错误态；已有收藏时失败只 toast', async () => {
    const src = srcOf('favorites/favorites.js');
    const load = compile(src, 'loadFavorites', ['silent', 'localData', 'wx']);
    const base = { list: [], loading: false, loadError: '' };

    const empty = makePage({ ...base });
    const { wx } = makeWx();
    const failGet = { getFavoriteList: () => Promise.reject(new Error('收藏读取失败')) };
    await load.call(empty.page, false, failGet, wx);
    assert.strictEqual(empty.page.data.loadError, '收藏读取失败');

    const nonEmpty = makePage({ ...base, list: [{ id: 1 }] });
    const { wx: wx2, calls: toast2 } = makeWx();
    const failGet2 = { getFavoriteList: () => Promise.reject(new Error('刷新失败')) };
    await load.call(nonEmpty.page, false, failGet2, wx2);
    assert.strictEqual(nonEmpty.page.data.loadError, '');
    assert.deepEqual(toast2, ['刷新失败']);
  });
});

describe('download.refresh：索引读坏不能伪装成「还没有下载」', () => {
  const src = srcOf('download/download.js');
  const refresh = compile(src, 'refresh', ['downloadStore']);

  test('读取抛错：挂 loadError，保留可重试', async () => {
    const { page } = makePage({ loadError: '', groups: [] });
    await refresh.call(page, { listDownloads: () => { throw new Error('索引损坏'); } });
    assert.strictEqual(page.data.loadError, '索引损坏');
  });

  test('恢复后成功：清空 loadError', async () => {
    const { page } = makePage({ loadError: '索引损坏', groups: [] });
    page.formatItemTitle = () => '';
    page.formatItemSub = () => '';
    page.formatSize = () => '0 B';
    await refresh.call(page, {
      listDownloads: () => [],
      computeTotalSize: () => 0,
    });
    assert.strictEqual(page.data.loadError, '');
  });
});
