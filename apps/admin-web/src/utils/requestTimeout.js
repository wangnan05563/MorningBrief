/**
 * 请求超时判定与长任务超时常量（FR-UX-702 / M62 / T02516）
 *
 * 为什么要单独成文件：VACUUM、批量 DELETE 这类分钟级操作与 CRUD 共用全局 15s 超时
 * （src/api/index.js 的 `timeout: 15000`），到点后 axios 报的是「timeout of 15000ms
 * exceeded」——用户读到的信息是「失败了」，而真相是「后端还在跑，而且 VACUUM 期间锁库」。
 * 于是常见后果是再点一次执行：两个 VACUUM 排队，前面那个还占着写锁。
 *
 * 所以这里同时提供两件事：
 * 1) LONG_TASK_TIMEOUT_MS——把长任务从 15s 里摘出来（与调用点成对，见 api/maintenance.js）；
 * 2) isRequestTimeout——把「超时」从所有失败里可判定地分出来，让页面能说「后端仍在执行」。
 *
 * 与问答链路的分工（api/aiChat.js 的 _isTimeoutError）：两边都排除「用户主动取消」，
 * 但问答还要区分后端自己返回的业务超时（success=false/timeout=true，走响应体而非异常），
 * 判定口径并不相同，因此不合并成一个函数——合并只会让两条链路互相迁就。
 */

/** 分钟级维护/清理类操作的显式超时：5 分钟（VACUUM 在数百 MB 库上的常见耗时上界） */
export const LONG_TASK_TIMEOUT_MS = 300_000

/**
 * 是否为「客户端等不到响应」的超时（区别于用户主动中止与业务错误）
 * @param {unknown} error axios 抛出的错误
 * @returns {boolean}
 */
export function isRequestTimeout(error) {
  if (!error) return false
  // 主动 abort() 也带 name==='CanceledError'，但那是用户自己停的，不能报「后端仍在执行」
  if (error.__CANCEL__ === true || error?.name === 'CanceledError') return false
  if (error.code === 'ECONNABORTED') return true
  if (error.name === 'TimeoutError') return true
  return typeof error.message === 'string' && /timeout of\s+\d+\s*ms exceeded/i.test(error.message)
}

/** 超时后必须传达的事实：请求断了，任务没断 */
export function longTaskTimeoutText(ms = LONG_TASK_TIMEOUT_MS) {
  return (
    `等待超过 ${Math.round(ms / 1000)} 秒，请求已断开，但后端仍在继续执行。` +
    '请勿重复提交：VACUUM 与批量删除期间会占用数据库写锁，重复执行只会让后续操作排队更久。' +
    '可稍后回到本页看「存储状态」刷新结果。'
  )
}
