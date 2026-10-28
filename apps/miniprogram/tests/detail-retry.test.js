/**
 * T02627（FR-UX-302 / J32）：详情加载失败必须能原地重试
 *
 * 工单的 5 条验收点里，只有「渲染与点击」需要微信开发者工具/真机；
 * 状态迁移（错误文案是否残留、缺 id 是否还发请求、重复点是否还受理、
 * 离线兜底是否抢占错误态）全部能在本机用真实方法体跑通。这里锁这部分，
 * 避免「按钮在但点了没用」与「重试后错误文案挂着」两类退化。
 *
 * 策略与 detail-waiting-guard.test.js 一致：从真实源码提取函数体，
 * new Function 注入依赖，在 mock this 上执行——不测手写镜像逻辑。
 *
 * 运行：node --test apps/miniprogram/tests/detail-retry.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const DETAIL_JS = path.join(ROOT, 'pages', 'detail', 'detail.js');
const DETAIL_WXML = path.join(ROOT, 'pages', 'detail', 'detail.wxml');
const DETAIL_WXSS = path.join(ROOT, 'pages', 'detail', 'detail.wxss');
const APP_WXSS = path.join(ROOT, 'app.wxss');

const src = fs.readFileSync(DETAIL_JS, 'utf8');
const wxml = fs.readFileSync(DETAIL_WXML, 'utf8');

/** 提取真实方法体（去掉 `onXxx(args) {` 与收尾 `  }`），找不到就抛，避免空体假绿 */
function bodyOf(name) {
  const m = src.match(new RegExp(name + '\\s*\\((?:[^)]*)\\)\\s*\\{([\\s\\S]*?)\\n  \\}'));
  if (!m) throw new Error('detail.js 里找不到方法 ' + name + '（重试链路被整段删除或改名？）');
  assert.ok(m[1].trim().length > 0, name + ' 方法体为空');
  return m[1];
}

const EPISODE = {
  id: '42',
  title: '测试节目',
  duration: 300,
  cover_url: 'https://cdn/cover.jpg',
  channel_id: 7,
  channel_name: '测试频道',
};

function makePage(data) {
  const calls = { setData: [], navTitle: [], toast: [], sync: 0, refresh: 0, loadDetail: [] };
  const page = {
    calls,
    data: Object.assign({}, data),
    formatDuration: (sec) => 'D' + sec,
    syncPlayingState: () => { calls.sync += 1; },
    refreshDownloadState: () => { calls.refresh += 1; },
    applyNavTitle: (ep) => calls.navTitle.push(ep && ep.title),
    setData(obj) {
      calls.setData.push(obj);
      Object.assign(page.data, obj);
    },
  };
  page.wx = { showToast: (o) => calls.toast.push(o.title) };
  page.store = { getDownload: () => null };
  return page;
}

/** 用真实方法体编译；依赖以形参注入，this 由调用方给（mock page） */
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

function compile(name, page, extra = {}) {
  const body = bodyOf(name);
  // 方法体是自己声明的 id（onRetryLoad 读 this.data）还是形参 id（loadDetail 收参）
  const paramId = !/\b(?:const|let|var)\s+id\b/.test(body);
  const Ctor = new RegExp('async\\s+' + name + '\\s*\\(').test(src) ? AsyncFunction : Function;
  // eslint-disable-next-line no-new-func
  const fn = new Ctor(
    ...['wx', 'downloadStore', 'fetchEpisodeDetail'].concat(paramId ? ['id'] : []),
    body,
  );
  const fetchEpisodeDetail = extra.fetchEpisodeDetail || (() => Promise.reject(new Error('未注入')));
  return (id) => fn.call(page, page.wx, page.store, fetchEpisodeDetail, ...(paramId ? [id] : []));
}

describe('onRetryLoad：重试入口自身', () => {
  test('缺 id 时不改状态、不发请求（按钮虽被 wx:if 隐藏，JS 侧也不许空转）', () => {
    const page = makePage({ episodeId: '', loading: false, error: '网络异常' });
    let called = 0;
    page.loadDetail = () => { called += 1; };
    compile('onRetryLoad', page)({});
    assert.strictEqual(page.calls.setData.length, 0);
    assert.strictEqual(called, 0);
  });

  test('有 id 时先置 loading、清空 error，再用同一 id 重载', () => {
    const page = makePage({ episodeId: '42', loading: false, error: '网络异常' });
    page.loadDetail = (id) => page.calls.loadDetail.push(id);
    compile('onRetryLoad', page)({});
    assert.deepStrictEqual(page.calls.setData[0], { loading: true, error: '' });
    assert.deepStrictEqual(page.calls.loadDetail, ['42']);
  });

  test('弱网连点：每次点击都重置状态并重新发起，不因上一次未返回而卡住', () => {
    const page = makePage({ episodeId: '42', error: '网络异常' });
    page.loadDetail = (id) => page.calls.loadDetail.push(id);
    const retry = compile('onRetryLoad', page);
    retry({});
    page.data.error = '网络异常';
    retry({});
    retry({});
    assert.deepStrictEqual(page.calls.loadDetail, ['42', '42', '42']);
    assert.strictEqual(page.calls.setData.length, 3);
    assert.strictEqual(page.data.error, '');
  });
});

describe('loadDetail：错误态与成功态的迁移', () => {
  test('成功：error 清空、loading 归 false、offlinePlayback 归 false、标题随内容', async () => {
    const page = makePage({ episodeId: '42', loading: true, error: '网络异常', offlinePlayback: true });
    const load = compile('loadDetail', page, { fetchEpisodeDetail: () => Promise.resolve(EPISODE) });
    await load('42');
    assert.strictEqual(page.data.error, '');
    assert.strictEqual(page.data.loading, false);
    assert.strictEqual(page.data.offlinePlayback, false);
    assert.strictEqual(page.data.episode.id, '42');
    assert.strictEqual(page.data.durationLabel, 'D300');
    assert.deepStrictEqual(page.calls.navTitle, ['测试节目']);
    assert.strictEqual(page.calls.sync, 1);
  });

  test('失败且无本地下载：错误文案落到 error，loading 归 false，不进离线态', async () => {
    const page = makePage({ episodeId: '42', loading: true, error: '' });
    const load = compile('loadDetail', page, { fetchEpisodeDetail: () => Promise.reject(new Error('网络异常')) });
    await load('42');
    assert.strictEqual(page.data.error, '网络异常');
    assert.strictEqual(page.data.loading, false);
    assert.strictEqual(page.data.offlinePlayback, false);
  });

  test('失败且 message 为空：回落「加载失败」，不显示空白错误页', async () => {
    const page = makePage({ episodeId: '42', loading: true, error: '' });
    const load = compile('loadDetail', page, { fetchEpisodeDetail: () => Promise.reject(new Error('')) });
    await load('42');
    assert.strictEqual(page.data.error, '加载失败');
  });

  test('失败但有本地下载：走离线兜底，error 同样清空且提示已切换', async () => {
    const page = makePage({ episodeId: '42', loading: true, error: '网络异常' });
    page.store = {
      getDownload: () => ({
        episodeId: '42',
        title: '离线节目',
        localPath: 'wxfile://local.mp3',
        cover_url: '',
        duration: 60,
        channelId: 7,
        channelName: '测试频道',
      }),
    };
    const load = compile('loadDetail', page, { fetchEpisodeDetail: () => Promise.reject(new Error('网络异常')) });
    await load('42');
    assert.strictEqual(page.data.error, '');
    assert.strictEqual(page.data.loading, false);
    assert.strictEqual(page.data.offlinePlayback, true);
    assert.strictEqual(page.data.episode.audio_url, 'wxfile://local.mp3');
    assert.deepStrictEqual(page.calls.navTitle, ['离线节目']);
    assert.ok(page.calls.toast.includes('网络不可用，已切换本机下载'), '离线兜底没有可见提示');
  });
});

describe('重试闭环：失败态点重试后回到正常界面', () => {
  test('先失败留下错误文案，再点重试成功——error 不残留、loading 不悬挂', async () => {
    const page = makePage({ episodeId: '42', loading: true, error: '' });
    let fail = true;
    const fetchEpisodeDetail = () => (fail
      ? Promise.reject(new Error('网络异常'))
      : Promise.resolve(EPISODE));
    page.loadDetail = compile('loadDetail', page, { fetchEpisodeDetail });

    await page.loadDetail('42');
    assert.strictEqual(page.data.error, '网络异常', '前置条件：先要真的进入错误态');

    fail = false;
    compile('onRetryLoad', page)({});
    assert.strictEqual(page.data.error, '', '重试发出前就应清掉旧错误文案');
    await new Promise((resolve) => setImmediate(resolve));
    assert.strictEqual(page.data.error, '');
    assert.strictEqual(page.data.loading, false);
    assert.strictEqual(page.data.episode.id, '42');
  });
});

describe('WXML 静态：重试入口只在错误态、且缺 id 不渲染', () => {
  test('按钮必须落在 wx:elif="{{error}}" 分支内、wx:else 之前', () => {
    const errorBranch = wxml.indexOf('wx:elif="{{error}}"');
    const retry = wxml.indexOf('bindtap="onRetryLoad"');
    const elseBranch = wxml.indexOf('<block wx:else>');
    assert.ok(errorBranch > -1, 'detail.wxml 找不到错误态分支');
    assert.ok(retry > -1, 'detail.wxml 找不到重试按钮绑定');
    assert.ok(elseBranch > -1, 'detail.wxml 找不到正常态分支');
    assert.ok(errorBranch < retry && retry < elseBranch, '重试按钮不在错误态分支内（正常播放界面也会出现）');
  });

  test('重试按钮带 episodeId 守卫与可访问名', () => {
    const wrapStart = wxml.indexOf('class="load-retry-wrap"');
    const btnEnd = wxml.indexOf('</button>', wrapStart);
    const block = wxml.slice(wrapStart, btnEnd + '</button>'.length);
    assert.ok(/wx:if="\{\{episodeId\}\}"/.test(block), '缺 id 时仍会渲染重试按钮');
    assert.ok(/aria-label="重新加载该节目"/.test(block), '重试按钮缺可访问名');
    assert.ok(/>重试</.test(block), '按钮可见文字不是「重试」');
  });

  test('复用 app.wxss 的 .load-retry-btn（T00599），detail.wxss 不另造一套', () => {
    assert.ok(fs.readFileSync(APP_WXSS, 'utf8').includes('.load-retry-btn'), 'app.wxss 里的共享重试样式被删');
    const detailWxss = fs.readFileSync(DETAIL_WXSS, 'utf8');
    assert.ok(!detailWxss.includes('load-retry-btn'), 'detail.wxss 又造了一套重试按钮样式，与列表页会漂移');
  });
});
