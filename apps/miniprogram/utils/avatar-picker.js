/**
 * 头像选择器（T00593）：从相册/相机选择一张图片作为自定义头像。
 *
 * 为什么需要：`<button open-type="chooseAvatar">` 是微信官方推荐的「使用微信头像」入口，
 * 但它属于隐私接口——小程序未在 mp 后台《用户隐私保护指引》声明「收集你的昵称、头像」时，
 * 点击会被渲染层直接拦截（控制台报 chooseAvatar:fail api scope is not declared in the
 * privacy agreement），用户侧表现为「点了没反应」。相册自选是本项目的降级路径。
 *
 * 注意：wx.chooseMedia（相册/相机）同样属隐私接口，后台需声明「选中的照片或视频信息」；
 * 但两条路径的声明项彼此独立，补齐其一即可先恢复部分能力，故两条入口都保留。
 *
 * 基础库兼容：chooseMedia 需 2.10.0+，旧版本回退 chooseImage（本项目其余页面同款回退策略）。
 */

/** 统一取 wx 对象（允许注入便于单测） */
function _wx(injected) {
  if (injected) return injected;
  // eslint-disable-next-line no-undef
  return typeof wx !== 'undefined' ? wx : null;
}

/**
 * 选择一张图片，返回本地临时文件路径。
 *
 * @param {object} [injectedWx] 注入的 wx 对象（单测用；不传则用全局 wx）
 * @returns {Promise<string>} 图片临时路径（wxfile:// 开头）
 * @throws {Error} 用户取消时 err.cancelled=true；无可用 API 时 err.code='NO_API'
 */
function pickAvatarFromAlbum(injectedWx) {
  const api = _wx(injectedWx);
  if (!api) {
    const e = new Error('当前环境不支持选择图片');
    e.code = 'NO_API';
    return Promise.reject(e);
  }

  return new Promise((resolve, reject) => {
    const onSuccess = (res) => {
      const path =
        (res && res.tempFiles && res.tempFiles[0] && res.tempFiles[0].tempFilePath) ||
        (res && res.tempFilePaths && res.tempFilePaths[0]) ||
        '';
      if (!path) {
        reject(new Error('未取到图片路径'));
        return;
      }
      resolve(path);
    };
    const onFail = (err) => {
      const msg = (err && err.errMsg) || '';
      // 用户主动取消不是错误，单独标记，调用方静默处理（不弹错误提示）
      if (/cancel/i.test(msg)) {
        const e = new Error('已取消选择');
        e.cancelled = true;
        reject(e);
        return;
      }
      reject(new Error(msg || '选择图片失败'));
    };

    if (typeof api.chooseMedia === 'function') {
      api.chooseMedia({
        count: 1,
        mediaType: ['image'],
        sourceType: ['album', 'camera'],
        sizeType: ['compressed'], // 压缩图：头像展示无需原图，省流量与上传时间
        success: onSuccess,
        fail: onFail,
      });
      return;
    }
    if (typeof api.chooseImage === 'function') {
      api.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['album', 'camera'],
        success: onSuccess,
        fail: onFail,
      });
      return;
    }
    const e = new Error('当前微信版本过低，请升级后再试');
    e.code = 'NO_API';
    reject(e);
  });
}

module.exports = { pickAvatarFromAlbum };
