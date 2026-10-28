/**
 * T02597（FR-UX-202 / J60）：下载页三档清空的确认口径
 *
 * 工单要求：单章 / 整课 / 全部三档确认必须带对象名与条数，且与真实缓存一致；
 * 全部清空是最重的一档，破坏性配色不可缺。
 *
 * 本环境无微信开发者工具，弹窗的实际渲染由 T02597 保持 todo；
 * 这里从真实 download.js 提取三个 handler 执行，锁住「弹窗内容里的数字来自真实数据」——
 * 写死条数、接错 group、丢了不可恢复/破坏性配色，都会红。
 *
 * 运行：node --test apps/miniprogram/tests/download-clear-grading.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const DOWNLOAD_JS = path.join(__dirname, '..', 'pages', 'download', 'download.js');
const DOWNLOAD_WXML = path.join(__dirname, '..', 'pages', 'download', 'download.wxml');
const src = fs.readFileSync(DOWNLOAD_JS, 'utf8');
const wxml = fs.readFileSync(DOWNLOAD_WXML, 'utf8');

/** 提取真实方法体，找不到就抛，避免空体假绿 */
function bodyOf(name) {
  const m = src.match(new RegExp(name + '\\s*\\((?:[^)]*)\\)\\s*\\{([\\s\\S]*?)\\n  \\}'));
  if (!m) throw new Error('download.js 里找不到方法 ' + name + '（handler 被删除或改名？）');
  assert.ok(m[1].trim().length > 0, name + ' 方法体为空');
  return m[1];
}

/**
 * mock：showModal 记录请求并按 confirm 选项回调，downloadStore 记录调用，
 * refresh 计数用于确认「删完必须刷新列表」。
 */
function makeEnv({ confirm = true, data = {} } = {}) {
  const calls = { modal: [], remove: [], byChannel: [], clearAll: 0, refresh: 0, toast: [] };
  const page = {
    data: Object.assign({ groups: [], totalCount: 0, totalSizeLabel: '' }, data),
    refresh() { calls.refresh += 1; },
  };
  const injected = {
    wx: {
      showModal(opts) {
        calls.modal.push(opts);
        if (opts.success) opts.success({ confirm });
      },
      showToast(opts) { calls.toast.push(opts.title); },
    },
    downloadStore: {
      removeDownload(id) { calls.remove.push(id); },
      clearByChannel(ch) { calls.byChannel.push(ch); },
      clearAll() { calls.clearAll += 1; },
    },
    trackEvent: () => {},
  };
  return { page, calls, injected };
}

function compile(name) {
  // 三个 handler 的形参名都是 e；onClearAll 不读参数，多传一个无影响
  // eslint-disable-next-line no-new-func
  return new Function('e', 'wx', 'downloadStore', 'trackEvent', bodyOf(name));
}

function tap(dataset) {
  return { currentTarget: { dataset } };
}

describe('onDeleteItem：单章删除点名标题与条数', () => {
  test('确认框内容含真实标题 + 1 章 + 重新下载的后果；确认后只删这一条并刷新', () => {
    const { page, calls, injected } = makeEnv();
    compile('onDeleteItem').call(page, tap({ id: 42, title: '第三章 · 城市观察' }), injected.wx, injected.downloadStore, injected.trackEvent);
    assert.equal(calls.modal.length, 1);
    const { content } = calls.modal[0];
    assert.ok(content.includes('第三章 · 城市观察'), content);
    assert.ok(content.includes('1 章'), content);
    assert.ok(content.includes('重新联网下载'), content);
    assert.deepEqual(calls.remove, [42]);
    assert.equal(calls.refresh, 1);
    assert.deepEqual(calls.toast, ['已删除']);
  });

  test('标题缺失时用「该章节」兜底，而不是拼出「删除「undefined」」', () => {
    const { page, calls, injected } = makeEnv();
    compile('onDeleteItem').call(page, tap({ id: 7 }), injected.wx, injected.downloadStore, injected.trackEvent);
    assert.ok(calls.modal[0].content.includes('该章节'), calls.modal[0].content);
    assert.ok(!calls.modal[0].content.includes('undefined'), calls.modal[0].content);
  });

  test('取消：不删、不刷新', () => {
    const { page, calls, injected } = makeEnv({ confirm: false });
    compile('onDeleteItem').call(page, tap({ id: 42, title: 'x' }), injected.wx, injected.downloadStore, injected.trackEvent);
    assert.equal(calls.modal.length, 1);
    assert.deepEqual(calls.remove, []);
    assert.equal(calls.refresh, 0);
  });

  test('没有 id 时不弹窗（避免删错对象）', () => {
    const { page, calls, injected } = makeEnv();
    compile('onDeleteItem').call(page, tap({}), injected.wx, injected.downloadStore, injected.trackEvent);
    assert.equal(calls.modal.length, 0);
  });
});

describe('onClearChannel：整课清空按该组真实条数', () => {
  const groups = [
    { channelId: 7, channelName: '城市观察', items: [{ episodeId: 1 }, { episodeId: 2 }, { episodeId: 3 }] },
    { channelId: 8, channelName: '科技前沿', items: [{ episodeId: 9 }] },
  ];

  test('点第 1 组：文案是 3 章（不是总条数、也不是另一组），确认后只清该频道', () => {
    const { page, calls, injected } = makeEnv({ data: { groups, totalCount: 4 } });
    // dataset 拿到的是字符串 id（WXML 属性值的真实形态）；store 侧必须收到数字
    compile('onClearChannel').call(page, tap({ channelId: '7' }), injected.wx, injected.downloadStore, injected.trackEvent);
    const { content } = calls.modal[0];
    assert.ok(content.includes('3 章'), content);
    assert.ok(!content.includes('4 章'), content);
    assert.ok(content.includes('不可恢复'), content);
    assert.deepEqual(calls.byChannel, [7]);
    assert.equal(typeof calls.byChannel[0], 'number');
    assert.equal(calls.refresh, 1);
  });

  test('频道不在当前列表里：条数按 0 如实说，不炸', () => {
    const { page, calls, injected } = makeEnv({ data: { groups } });
    compile('onClearChannel').call(page, tap({ channelId: 999 }), injected.wx, injected.downloadStore, injected.trackEvent);
    assert.ok(calls.modal[0].content.includes('0 章'), calls.modal[0].content);
  });
});

describe('onClearAll：最重一档必须有条数、占用与破坏性配色', () => {
  test('文案含总章数与占用，confirmColor 为破坏性红，确认后清空并刷新', () => {
    const { page, calls, injected } = makeEnv({ data: { totalCount: 5, totalSizeLabel: '12.0 MB' } });
    compile('onClearAll').call(page, null, injected.wx, injected.downloadStore, injected.trackEvent);
    const modal = calls.modal[0];
    assert.ok(modal.content.includes('5 章'), modal.content);
    assert.ok(modal.content.includes('12.0 MB'), modal.content);
    assert.ok(modal.content.includes('不可恢复'), modal.content);
    assert.equal(modal.confirmColor, '#B0554A');
    assert.equal(calls.clearAll, 1);
    assert.equal(calls.refresh, 1);
  });

  test('占用未知时如实写「未知」，不拼出 undefined', () => {
    const { page, calls, injected } = makeEnv({ data: { totalCount: 2 } });
    compile('onClearAll').call(page, null, injected.wx, injected.downloadStore, injected.trackEvent);
    assert.ok(calls.modal[0].content.includes('未知'), calls.modal[0].content);
    assert.ok(!calls.modal[0].content.includes('undefined'), calls.modal[0].content);
  });

  test('没有下载时点清空：不弹窗、不调用清空', () => {
    const { page, calls, injected } = makeEnv({ data: { totalCount: 0 } });
    compile('onClearAll').call(page, null, injected.wx, injected.downloadStore, injected.trackEvent);
    assert.equal(calls.modal.length, 0);
    assert.equal(calls.clearAll, 0);
  });
});

describe('WXML：三档入口的可见文字必须带计数（静态锁，补真机不可验的一段）', () => {
  test('全部清空入口显示「清空全部 {{totalCount}} 章」并带可访问名', () => {
    assert.match(wxml, /class="stat-clear stat-clear--all"/);
    assert.match(wxml, /清空全部 \{\{totalCount\}\} 章/);
    assert.match(wxml, /aria-label="清空全部下载"/);
  });

  test('整课清空入口显示「清空本课程 {{group.items.length}} 章」', () => {
    assert.match(wxml, /清空本课程 \{\{group\.items\.length\}\} 章/);
    assert.match(wxml, /aria-label="清空该频道下载"/);
  });

  test('单章删除入口把标题传进 dataset，供确认框点名', () => {
    assert.match(wxml, /catchtap="onDeleteItem"/);
    assert.match(wxml, /data-title="\{\{item\.titleText\}\}"/);
  });
});
