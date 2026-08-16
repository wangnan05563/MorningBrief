/**
 * 带 TTL 的 storage 工具
 *
 * 为什么需要：wx.setStorageSync 写入的数据永不过期，长期使用后 storage 会膨胀。
 * 通过包装一层 TTL 机制，让缓存类数据自动过期清理，避免陈旧数据占用空间。
 *
 * 用法：
 *   const { setWithTTL, getWithTTL } = require('./storage');
 *   setWithTTL('key', value, 7 * 24 * 3600 * 1000); // 7 天后过期
 *   const v = getWithTTL('key'); // 未过期返回 data，已过期返回 null（并自动清理）
 *
 * 向后兼容：若旧数据不是 {data, expiresAt} 结构（直接存储的原始值），
 * getWithTTL 会原样返回，不会报错；下次写入时才会转为带 TTL 的结构。
 */

function setWithTTL(key, value, ttlMs) {
  const item = {
    data: value,
    expiresAt: Date.now() + ttlMs,
  };
  wx.setStorageSync(key, item);
}

function getWithTTL(key) {
  const item = wx.getStorageSync(key);
  if (!item) return null;
  // 兼容旧格式（非 {data, expiresAt} 结构）：直接返回原值，避免升级后旧数据读取报错
  if (typeof item !== 'object' || item.expiresAt === undefined) {
    return item;
  }
  // 已过期：清理后返回 null，避免陈旧数据继续占用 storage
  if (Date.now() > item.expiresAt) {
    wx.removeStorageSync(key);
    return null;
  }
  return item.data;
}

module.exports = { setWithTTL, getWithTTL };
