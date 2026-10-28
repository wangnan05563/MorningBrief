/**
 * T02536（J63 / J64 / J90）JS 侧行为用例
 *
 * 静态门禁（validate-action-labels.mjs）只保证「文字在模板里、文案与实现有联动」，
 * 这里锁真正会伤到用户的三段逻辑：
 *  - J63：未登录保存偏爱必须弹可解释、可直达登录的弹窗（不是一句 toast 后把用户卡死），
 *         且此时不得假装保存成功（不 markOnboarded、不回退页面）；
 *  - J64：「全选/全不选」的判定以 data.allSelected 为单一源，空列表不算全选；
 *  - J90：详情页取数失败时，已下载的节目必须用本机音频起播（文案「断网也能听」的依据），
 *         没下载才落到失败态。
 *
 * 方法体从真实源码提取，改坏源码会让这里红。
 *
 * 运行：node --test apps/miniprogram/tests/action-labels.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const PAGES = path.join(__dirname, '..', 'pages');
const srcOf = (rel) => fs.readFileSync(path.join(PAGES, rel), 'utf8');

function bodyOf(src, name) {
  const start = src.search(new RegExp(`^ {2}(?:async )?${name}\\s*\\(`, 'm'));
  if (start < 0) throw new Error('找不到方法 ' + name + '（改名或删除了？）');
  const rest = src.slice(start);
  const rest2 = rest.replace(/^ {2}(?:async )?[\w$]+\s*\([^)]*\)\s*\{/, '');
  const end = rest2.search(/\n {2}\}/);
  assert.ok(end > 0, name + ' 方法体截取失败');
  return rest2.slice(0, end);
}

function compile(src, name, args) {
  const body = bodyOf(src, name);
  // eslint-disable-next-line no-new-func
  return new Function(`return async function(${args.join(',')}){${body}}`)();
}

function makePage(data) {
  const page = {
    data: Object.assign({}, data),
    setData(obj) {
      Object.assign(page.data, obj);
    },
  };
  return page;
}

describe('J63 preferred-settings.onSave：未登录要给出登录路径与原因', () => {
  const src = srcOf('preferred-settings/preferred-settings.js');
  const onSave = compile(src, 'onSave', ['localData', 'trackEvent', 'wx', 'getApp', 'setTimeout']);

  function run({ saved }) {
    const rec = { modals: [], toasts: [], switches: [], onboarded: 0, backs: 0, events: [], timers: [] };
    const page = makePage({
      channels: [
        { id: 1, selected: true },
        { id: 2, selected: false },
      ],
      selectedCount: 1,
    });
    const localData = {
      setPreferredChannels: () => saved,
      markPreferredChannelsOnboarded: () => { rec.onboarded += 1; },
    };
    const wx = {
      showModal: (o) => rec.modals.push(o),
      showToast: (o) => rec.toasts.push(o.title),
      switchTab: (o) => rec.switches.push(o.url),
      navigateBack: () => { rec.backs += 1; },
    };
    const getApp = () => ({ globalData: {} });
    const timers = [];
    const setTimeoutStub = (fn, ms) => { timers.push({ fn, ms }); return 0; };
    return onSave
      .call(page, localData, (n, a) => rec.events.push([n, a]), wx, getApp, setTimeoutStub)
      .then(() => ({ rec, page, timers }));
  }

  test('未登录：弹窗解释原因，不回退、不假装已保存', async () => {
    const { rec, page } = await run({ saved: false });
    assert.strictEqual(rec.modals.length, 1, '必须弹出一个可解释的弹窗');
    assert.strictEqual(rec.modals[0].confirmText, '去登录');
    assert.match(rec.modals[0].content, /登录/);
    assert.match(rec.modals[0].content, /账号/, '要说清为什么必须登录');
    assert.deepEqual(rec.toasts, [], '不能只 toast 一句就结束');
    assert.strictEqual(rec.onboarded, 0, '未保存成功不得标记引导完成');
    assert.strictEqual(rec.backs, 0, '留在本页让用户决定');
    assert.ok(rec.switches.length === 0, '确认前不跳转');
    assert.deepEqual(page.data.channels[1].selected, false, '页面勾选态不得被改动');
  });

  test('未登录：确认后直达「我的」登录页', async () => {
    const { rec } = await run({ saved: false });
    rec.modals[0].success({ confirm: true });
    assert.deepEqual(rec.switches, ['/pages/profile/profile']);
  });

  test('未登录：取消则留在本页（不清空用户已勾选）', async () => {
    const { rec, page } = await run({ saved: false });
    rec.modals[0].success({ confirm: false });
    assert.deepEqual(rec.switches, []);
    assert.strictEqual(rec.onboarded, 0);
    assert.strictEqual(page.data.selectedCount, 1);
  });

  test('已登录：保存成功才标记完成并回退', async () => {
    const { rec, timers } = await run({ saved: true });
    assert.deepEqual(rec.modals, []);
    assert.strictEqual(rec.onboarded, 1);
    assert.deepEqual(rec.toasts, ['已保存']);
    assert.strictEqual(timers.length, 1);
    assert.strictEqual(timers[0].ms, 800);
    timers[0].fn();
    assert.strictEqual(rec.backs, 1);
  });
});

describe('J64 preferred-settings：全选态单一判定源', () => {
  const src = srcOf('preferred-settings/preferred-settings.js');
  const compute = compile(src, 'computeAllSelected', ['channels']);

  test('空列表不算全选（否则「全不选」文案会指向一个空操作）', async () => {
    assert.strictEqual(await compute([]), false);
  });

  test('全部选中才是全选', async () => {
    assert.strictEqual(await compute([{ selected: true }, { selected: true }]), true);
  });

  test('有一项未选就不是全选（此前只看第一项的写法会误判）', async () => {
    assert.strictEqual(await compute([{ selected: true }, { selected: false }]), false);
  });
});

describe('J90 detail.loadDetail：断网时已下载节目走本机音频', () => {
  const src = srcOf('detail/detail.js');
  const loadDetail = compile(src, 'loadDetail', ['id', 'fetchEpisodeDetail', 'downloadStore', 'wx']);

  function makeDetailPage() {
    const toasts = [];
    const page = makePage({ episodeId: 88, episode: null, loading: true, error: '' });
    page.syncPlayingState = () => {};
    page.refreshDownloadState = () => {};
    page.formatDuration = (d) => `${d}s`;
    // J33（T02544）给 loadDetail 加了导航标题回写；标题本身由 mini-copy-guards.test.js 单独验证
    page.applyNavTitle = () => {};
    return { page, toasts, wx: { showToast: (o) => toasts.push(o.title) } };
  }

  const rec = {
    episodeId: 88,
    title: '第 3 章',
    localPath: 'wxfile://usr/a.mp3',
    cover_url: 'https://x/c.jpg',
    duration: 300,
    channelId: 7,
    channelName: '课程',
  };

  test('取数失败 + 有下载记录：用 localPath 起播，不落失败态', async () => {
    const { page, toasts, wx } = makeDetailPage();
    const downloadStore = { getDownload: (id) => (id === 88 ? rec : null) };
    await loadDetail.call(page, 88, () => Promise.reject(new Error('网络不可用')), downloadStore, wx);
    assert.strictEqual(page.data.error, '');
    assert.strictEqual(page.data.offlinePlayback, true);
    assert.strictEqual(page.data.episode.audio_url, rec.localPath);
    assert.strictEqual(page.data.episode.title, rec.title);
    assert.strictEqual(page.data.loading, false);
    assert.ok(toasts.some((t) => t.includes('本机')), '要告知用户已切到本机音频');
  });

  test('取数失败 + 无下载记录：才落失败态（不能把「没缓存」说成「有缓存」）', async () => {
    const { page, wx } = makeDetailPage();
    const downloadStore = { getDownload: () => null };
    await loadDetail.call(page, 88, () => Promise.reject(new Error('网络不可用')), downloadStore, wx);
    assert.strictEqual(page.data.offlinePlayback, false);
    assert.strictEqual(page.data.error, '网络不可用');
  });

  test('取数成功：正常渲染，离线标记必须为 false', async () => {
    const { page, wx } = makeDetailPage();
    const downloadStore = { getDownload: () => rec };
    const episode = { id: 88, title: '第 3 章', duration: 300 };
    await loadDetail.call(page, 88, () => Promise.resolve(episode), downloadStore, wx);
    assert.strictEqual(page.data.offlinePlayback, false);
    assert.strictEqual(page.data.episode, episode);
    assert.strictEqual(page.data.error, '');
  });
});
