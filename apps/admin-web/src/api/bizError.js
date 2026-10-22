/**
 * 把请求错误还原成后端信封 `{ code, message, data }`（G1 / FR-UX-407）。
 *
 * 拦截器（src/api/index.js）对 **HTTP 200 但 code!==0** 的业务错误做的是
 * `reject(new Error(message))`，再把 `err.code` 与 `err.payload`（信封里的 data）挂在
 * 这个 Error 上。所以页面里写 `error?.response?.data || error` 只会拿到一个纯 Error：
 * `resp?.code === 5001` 恒为假，后端明明下发了一整块引导数据（手动放置路径、下载源、
 * 授权链接），界面却一个字都不显示，只落一句泛化 toast——这正是 G1 的形状。
 *
 * 用这个函数，页面就不需要知道拦截器的私有形状。
 */
export function readBizError(error) {
  if (!error) return {}
  if ('payload' in error) {
    return { code: error.code, message: error.message, data: error.payload }
  }
  // 真·HTTP 错误（4xx/5xx）仍走 axios 形状
  return error?.response?.data || error
}
