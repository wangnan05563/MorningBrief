来源：T02489（FR-UX-201 应急停服可用性与状态可信）

问题：应急停服入口目前**只存在于移动端路由**。

- `git grep emergencyStop apps/admin-web/src` 仅命中 `src/api/mobile.js` 与 `src/views/mobile/ManageAlert.vue`；
- 路由挂载点唯一：`src/router/index.js:287` 的 `/m/manage/alert`（`MobileManageAlert`，`requireRole:'admin'`，`hidden:true`）；
- PC 端「系统维护」页 `src/views/maintenance/Maintenance.vue` 通篇不涉及维护态/停服（grep 无命中），只有一组数据库/缓存维护动作。

后果：超级管理员日常在 PC 后台作业，线上出故障时必须切到 `/m/` 移动布局（或掏手机）才能停服——高危动作的操作路径反而最长。

建议：
1. 把 ManageAlert.vue 已改好的三态卡片（未知/停服/正常 + 原因必填 + 提交守卫 + 已停服时长计时）抽成可复用组件，例如 `apps/admin-web/src/components/EmergencyStopCard.vue`；
2. PC 端入口位置需产品确认（系统维护页新增小节 vs 总览页顶部横幅）；
3. 复用同一 `api/mobile.js` 的三个接口即可，无需后端改动；补一条 E2E 覆盖 PC 入口。

前置：入口位置与是否需要「PC 端二次确认更严格（如输入确认词）」的产品结论。
