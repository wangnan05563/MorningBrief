/**
 * T02544 剩余小程序条目（J33 / J92）的行为用例
 *
 * 静态门禁只能看「有没有写」，这里跑真实代码路径：
 *  - J33：applyNavTitle 取的是当前集/章节而不是固定串；课程与资讯两条分支都要对；
 *  - J92：版本号连点只在 develop/trial 打开后端地址编辑，release 与「取不到版本」都无反应。
 *
 * 运行：node --test apps/miniprogram/tests/mini-copy-guards.test.js
 */
const { test, describe, before, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const MP_ROOT = path.resolve(__dirname, '..');
const DETAIL_JS = fs.readFileSync(path.join(MP_ROOT, 'pages/detail/detail.js'), 'utf8');

/** 从详情页源码里取出真实的 applyNavTitle 方法体，不在测试里重抄一份 */
function applyNavTitle(episode, data) {
  const m = /applyNavTitle\(episode\) \{([\s\S]*?)\n {2}\},/.exec(DETAIL_JS);
  assert.ok(m, 'detail.js 里定位不到 applyNavTitle 方法');
  const calls = [];
  global.wx = {
    setNavigationBarTitle: (opts) => calls.push(opts.title),
  };
  const ctx = { data };
  // 编译仓库内源码（非外部输入），与 tests/action-labels.test.js 同一种做法
  new Function('episode', m[1]).call(ctx, episode);
  return calls;
}

describe('J33 详情页导航标题取当前集', () => {
  test('资讯集：标题用节目标题', () => {
    assert.deepEqual(applyNavTitle({ title: '美联储宣布降息' }, { isCourse: false }), ['美联储宣布降息']);
  });

  test('课程集：优先章节信息', () => {
    assert.deepEqual(
      applyNavTitle({ title: '第三章 内容' }, { isCourse: true, chapterLabel: '第 3 章 / 共 10 章', courseName: '三体精读' }),
      ['第 3 章 / 共 10 章'],
    );
  });

  test('课程集缺章节信息：退回课程名', () => {
    assert.deepEqual(
      applyNavTitle({ title: '第三章 内容' }, { isCourse: true, chapterLabel: '', courseName: '三体精读' }),
      ['三体精读'],
    );
  });

  test('集没有标题：保留「节目详情」而不是空标题', () => {
    assert.deepEqual(applyNavTitle({}, { isCourse: false }), ['节目详情']);
  });

  test('没有集数据（例如加载失败）：不改动标题', () => {
    assert.deepEqual(applyNavTitle(null, { isCourse: false }), []);
  });
});

describe('J92 服务器地址编辑入口的环境守卫', () => {
  let aboutConfig;
  let modalLog;

  function makeWx(envVersion, { throws } = {}) {
    const wx = {
      showModal: (opts) => modalLog.push(opts),
      showToast: () => {},
      setClipboardData: (opts) => { if (opts && opts.success) opts.success(); },
      getStorageSync: () => '',
      setStorage: () => {},
      getSystemInfoSync: () => ({ platform: 'ios' }),
    };
    if (envVersion) {
      wx.getAccountInfoSync = throws
        ? () => { throw new Error('getAccountInfoSync not supported'); }
        : () => ({ miniProgram: { envVersion } });
    }
    global.wx = wx;
    delete global.__wxConfig;
    return wx;
  }

  function freshPage() {
    delete require.cache[require.resolve(path.join(MP_ROOT, 'pages/about/about.js'))];
    delete require.cache[require.resolve(path.join(MP_ROOT, 'utils/server-discovery.js'))];
    delete require.cache[require.resolve(path.join(MP_ROOT, 'utils/tracker.js'))];
    let captured;
    global.Page = (o) => { captured = o; };
    try {
      require(path.join(MP_ROOT, 'pages/about/about.js'));
    } finally {
      delete global.Page;
    }
    assert.ok(captured, 'about.js 没把配置交给 Page()');
    const page = Object.assign({ setData: (patch) => Object.assign(page.data, patch) }, captured);
    page.data = Object.assign({}, captured.data);
    return page;
  }

  function tapTimes(page, n) {
    for (let i = 0; i < n; i += 1) page.onVersionTap();
    if (page._versionTapTimer) clearTimeout(page._versionTapTimer);
  }

  before(() => {
    global.getApp = () => ({
      globalData: { version: '1.0.0', buildDate: '2026-10-29', baseUrl: 'http://127.0.0.1:8000/api/v1' },
    });
  });

  beforeEach(() => {
    modalLog = [];
  });

  afterEach(() => {
    delete global.__wxConfig;
  });

  test('正式版：连点 5 次无反应', () => {
    makeWx('release');
    const page = freshPage();
    tapTimes(page, 5);
    assert.equal(modalLog.length, 0);
  });

  test('开发版：连点 5 次打开配置弹窗', () => {
    makeWx('develop');
    const page = freshPage();
    tapTimes(page, 4);
    assert.equal(modalLog.length, 0, '4 次不该触发');
    page.onVersionTap();
    if (page._versionTapTimer) clearTimeout(page._versionTapTimer);
    assert.equal(modalLog.length, 1);
    assert.equal(modalLog[0].title, '配置后端地址');
  });

  test('体验版：同样可打开（排障需要）', () => {
    makeWx('trial');
    const page = freshPage();
    tapTimes(page, 5);
    assert.equal(modalLog.length, 1);
  });

  test('版本号取不到（API 抛错且无 __wxConfig）：按正式版处理，不暴露入口', () => {
    makeWx('develop', { throws: true });
    const page = freshPage();
    tapTimes(page, 5);
    assert.equal(modalLog.length, 0);
  });
});
