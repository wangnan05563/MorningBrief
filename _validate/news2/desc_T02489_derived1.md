来源：T02489（FR-UX-201 应急停服可用性与状态可信）

⚠ 阻塞：需产品裁决「倒计时」语义，不宜由实现侧选边

PRD 原文（docs/需求规格说明书-UX优化.md FR-UX-201）写的是「停服后提供恢复入口与倒计时」，这句话有两种解读：

- 解读 A（T02489 已实现）：显示**已停服时长**，每秒递增，并明示「停服不会自动到期恢复，必须手动解除」。
- 解读 B：显示**距自动恢复还剩多久**——即停服时可选填时长（如 30 分钟），到期由后端自动 `resume_maintenance` 并写审计。

需要裁决的点：
1. 是否允许「自动恢复」？应急停服通常因上游故障触发，自动恢复可能在故障未消除时放行新任务，风险方向与停服意图相反。
2. 若允许，默认时长/上限、是否允许「永久停服」（不填时长）？
3. 自动恢复是否算高危动作需要二次审计与通知（通知管理模块已有模板通道）。

落地前置：裁决结论。裁决为 A 则本单可直接关闭（现状已实现）；裁决为 B 需要动 `mobile_service.emergency_stop` 增加 `until` 字段、`workflow_scheduler` 守卫增加到期判定或引入到期任务，并补 `resume` 审计与通知。

涉及文件（现状参考）：
- D:\code\otherProjects\20_News\apps\admin-web\src\views\mobile\ManageAlert.vue（已停服时长计时已在此实现）
- D:\code\otherProjects\20_News\backend\app\services\mobile_service.py:349 emergency_stop / :384 resume_maintenance
