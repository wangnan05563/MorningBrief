/**
 * avatar-picker 单元测试（T00593）
 *
 * 覆盖：chooseMedia 优先 / 旧基础库回退 chooseImage / 双双缺失时报错 /
 * 用户取消标记 cancelled / 响应无路径时报错。
 *
 * 运行：node --test apps/miniprogram/tests/avatar-picker.test.js
 */
const { test, describe } = require('node:test');
const assert = require('node:assert');

const { pickAvatarFromAlbum } = require('../utils/avatar-picker');

describe('pickAvatarFromAlbum（相册自选头像）', () => {
  test('优先使用 chooseMedia，并传入单图/压缩参数', async () => {
    const calls = [];
    const wxStub = {
      chooseMedia(opts) {
        calls.push(opts);
        opts.success({ tempFiles: [{ tempFilePath: 'wxfile://tmp_album_1.jpg' }] });
      },
      chooseImage() {
        throw new Error('不应回退到 chooseImage');
      },
    };
    const path = await pickAvatarFromAlbum(wxStub);
    assert.strictEqual(path, 'wxfile://tmp_album_1.jpg');
    assert.strictEqual(calls.length, 1);
    assert.strictEqual(calls[0].count, 1);
    assert.deepStrictEqual(calls[0].mediaType, ['image']);
    assert.deepStrictEqual(calls[0].sizeType, ['compressed']);
  });

  test('基础库无 chooseMedia 时回退 chooseImage', async () => {
    const wxStub = {
      chooseImage(opts) {
        opts.success({ tempFilePaths: ['wxfile://tmp_legacy.jpg'] });
      },
    };
    const path = await pickAvatarFromAlbum(wxStub);
    assert.strictEqual(path, 'wxfile://tmp_legacy.jpg');
  });

  test('两个 API 都缺失时报 NO_API（不静默失败）', async () => {
    await assert.rejects(
      () => pickAvatarFromAlbum({}),
      (e) => e.code === 'NO_API'
    );
  });

  test('用户取消标记 cancelled=true（调用方据此静默处理）', async () => {
    const wxStub = {
      chooseMedia(opts) {
        opts.fail({ errMsg: 'chooseMedia:fail cancel' });
      },
    };
    await assert.rejects(
      () => pickAvatarFromAlbum(wxStub),
      (e) => e.cancelled === true
    );
  });

  test('响应中无路径时报错', async () => {
    const wxStub = {
      chooseMedia(opts) {
        opts.success({ tempFiles: [] });
      },
    };
    await assert.rejects(() => pickAvatarFromAlbum(wxStub), /未取到图片路径/);
  });

  test('无 wx 环境时报 NO_API', async () => {
    await assert.rejects(
      () => pickAvatarFromAlbum(null),
      (e) => e.code === 'NO_API'
    );
  });
});
