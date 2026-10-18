来源：T02495（FR-UX-301 可见性感知的反馈队列）

## 问题

T02495 的实现为了「不把正在看手机的人半路踢下线」，在 `apps/admin-web/src/api/index.js` 响应拦截器里把隐藏期的 401 单独收窄成直接丢弃：

```js
if (error.response?.status === 401 && document.hidden) {
  return Promise.reject(error)
}
```

后果：页面在后台标签/最小化期间 token 过期时，401 既不提示、也不跳转登录页。等用户切回前台，如果这段时间没有再发起任何请求，界面会一直停在**已经过期会话的数据页**上——用户以为看到的是实时状态，点操作才收到 401 跳转，中间是「看起来正常但已失效」的空窗。

## 期望

切回前台（`visibilitychange` 且 `!document.hidden`）时补一次会话有效性判定：
- 若在隐藏期间丢弃过 401，恢复后立即按当前端（PC `/news/login`、移动 `/news/m/login`）跳转登录页，或至少聚合提示「登录已过期，请重新登录」再跳转；
- 未丢弃过 401 则不做任何额外请求，避免恢复瞬间集中打接口。

## 落地要点

1. `src/utils/message.js` 已有 `visibilitychange` 恢复钩子（`_isRestoring` + 2s 后 `_flush`），把「隐藏期间收到过 401」记为一个模块级标记（例如 `markAuthExpired()` / `consumeAuthExpired()`），由 `src/api/index.js` 的 401 分支置位。
2. 恢复时机复用现有 `_restoreTimer` 收口点（不要在 visibilitychange 回调里立刻跳转，与 `_flush` 同一时序，避免 DOM 插入激活窗口）。
3. 跳转沿用 `src/api/index.js` 现有的 `isMobile` 端判定逻辑，抽成公共函数避免两处路径分叉。
4. 补 e2e：mock 401 → 隐藏 → 触发一次请求 → 恢复 → 断言 `location.pathname` 落到对应登录页；再加一条「隐藏期间无 401 → 恢复后不跳转」的对照组。

## 约束

- 恢复瞬间不得自动发起额外的鉴权探测请求（除非产品明确要求），只用「已经丢弃过 401」这个既有事实驱动。
- 隐藏期间仍绝对不允许插入 DOM / 跳转，这是 T02495 已建立的不可退让语义。
