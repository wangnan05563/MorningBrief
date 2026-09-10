/**
 * services/download.js —— buildTitleFilename（T00387）单元测试
 *
 * 使用 Node.js 内置 node:test 运行（无需额外依赖）：
 *   node --test miniprogram/tests/download-filename.test.js
 *
 * 测试策略：buildTitleFilename 为纯函数（不触碰 wx API），
 * 验证「以标题命名」的命名规则与非法字符清洗。
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');

const { buildTitleFilename } = require('../services/download');

describe('download.buildTitleFilename（T00387 以标题命名）', () => {
  test('普通标题 + 默认 .mp3', () => {
    assert.strictEqual(buildTitleFilename('2026-09-10 早间新闻'), '2026-09-10 早间新闻.mp3');
  });

  test('按 audio_url 推断扩展名（m4a/aac）', () => {
    assert.strictEqual(buildTitleFilename('早报', 'https://x.com/a/1.m4a?sign=abc'), '早报.m4a');
    assert.strictEqual(buildTitleFilename('早报', 'https://x.com/a/1.AAC'), '早报.aac');
    assert.strictEqual(buildTitleFilename('早报', 'https://x.com/a/1.wav'), '早报.wav');
  });

  test('audio_url 扩展名不在白名单时回退 .mp3', () => {
    assert.strictEqual(buildTitleFilename('早报', 'https://x.com/a/1.txt'), '早报.mp3');
    assert.strictEqual(buildTitleFilename('早报', 'https://x.com/a/noext'), '早报.mp3');
  });

  test('清洗 Windows/iOS 非法文件名字符', () => {
    assert.strictEqual(buildTitleFilename('A/B\\C:D*E?F"G<H>I|J'), 'A B C D E F G H I J.mp3');
    assert.strictEqual(buildTitleFilename('标题:第一章'), '标题 第一章.mp3');
  });

  test('清洗控制字符并压缩连续空白', () => {
    assert.strictEqual(buildTitleFilename('  早报\t\n第二版  '), '早报 第二版.mp3');
    assert.strictEqual(buildTitleFilename('a\u0000b\u001fc'), 'a b c.mp3');
  });

  test('首尾的点/空格被去除（Windows 目录项约束）', () => {
    assert.strictEqual(buildTitleFilename('...早报...'), '早报.mp3');
    assert.strictEqual(buildTitleFilename(' . 早报 . '), '早报.mp3');
  });

  test('标题为空 / 全非法字符时回退 audio_时间戳.mp3', () => {
    const empty = buildTitleFilename('');
    assert.ok(/^audio_\d+\.mp3$/.test(empty), `实际: ${empty}`);

    const illegal = buildTitleFilename('///***???');
    assert.ok(/^audio_\d+\.mp3$/.test(illegal), `实际: ${illegal}`);

    const whitespace = buildTitleFilename('   ');
    assert.ok(/^audio_\d+\.mp3$/.test(whitespace), `实际: ${whitespace}`);
  });

  test('null / undefined 标题同样回退（扩展名仍按 audio_url 推断）', () => {
    assert.ok(/^audio_\d+\.mp3$/.test(buildTitleFilename(null)));
    assert.ok(/^audio_\d+\.m4a$/.test(buildTitleFilename(undefined, 'https://x.com/a/2.m4a')));
  });

  test('超长标题截断到 80 字符（不含扩展名）', () => {
    const long = '早'.repeat(200);
    const name = buildTitleFilename(long);
    const base = name.replace(/\.mp3$/, '');
    assert.strictEqual(base.length, 80, `实际长度: ${base.length}`);
    assert.ok(name.endsWith('.mp3'));
  });

  test('同名清洗结果保持稳定（幂等，可覆盖导出同一副本）', () => {
    const once = buildTitleFilename('早报：2026-09-10');
    const twice = buildTitleFilename('早报：2026-09-10');
    assert.strictEqual(once, twice);
  });

  test('非法字符替换为空格而非删除，保留词间可读性', () => {
    assert.strictEqual(buildTitleFilename('新闻/财经'), '新闻 财经.mp3');
  });

  test('querystring 不影响扩展名推断', () => {
    assert.strictEqual(
      buildTitleFilename('早报', 'https://x.com/a/1.mp3?Expires=1&Signature=ab.cd'),
      '早报.mp3'
    );
  });
});
