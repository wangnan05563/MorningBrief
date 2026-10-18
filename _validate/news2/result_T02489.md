## 根因

T02323 逐菜单评审里，「应急停服」页（`/m/manage/alert`）被记了两条 P0 级失效，本单两条都实测复现并修复：

1. **I54 高危动作功能从未生效**：`stop()` 里 `const { value } = await ElMessageBox.prompt(...)` 之后写了 `reason = v.trim()`，而 `v` 只存在于 `inputValidator` 箭头函数的形参作用域，外层根本不存在 → 抛 `ReferenceError: v is not defined` → 被同一 `try` 的 `catch { return }` 吞掉，与「用户点取消」无法区分。结果：用户填完原因点「确认停服」，页面静默无反应，`POST /m/emergency/stop` 从未发出，应急停服能力实际不可用。
2. **I55 状态误导**：`reload()` 用 `getMaintenanceStatus().catch(() => ({ enabled: false }))` 兜底，把「接口读不到」当成「未处于维护态」，横幅渲染成绿色的「生产运行正常」。后端宕机/网络失败时，值班人看到的是一枚「一切正常」的绿标，且此时点「应急停服」还会基于未知状态执行高危动作。
3. **停服动作不幂等**：`mobile_service.emergency_stop()` 无条件 `_upsert_flag` + `db.add(AuditLog)`。重复调用（连点、移动端脚本重放）会覆盖首次停服的时间与原因，并往审计里堆一串同名条目——倒计时/追责起点随之漂移。
4. **停服后无可信的时间语境**：页面只显示 `操作人 · at`（分钟精度），没有「已经停了多久」，也没有「不会自动恢复」的说明；恢复入口虽有（`v-else` 的「解除应急停服」），但很容易被误认为停服会自己到期。

## 影响范围

- `apps/admin-web/src/views/mobile/ManageAlert.vue`：全站唯一的应急停服入口页（PC 端无同功能页面，`views/maintenance/Maintenance.vue` 不涉及停服），本次整页重写状态机为三态。
- `apps/admin-web/src/api/mobile.js`：`getMaintenanceStatus` 加 `silent: true`（该函数仅 ManageAlert 一处调用，无其他消费方受影响）。
- `backend/app/services/mobile_service.py:349 emergency_stop`：新增幂等分支与 `already` 字段。返回值多一个键，消费方只有 `routers/admin/mobile.py:138`（原样 `success(data=...)` 透传）与前端 `normalize()`，不破坏既有契约。
- `backend/app/services/workflow_scheduler.py:616` 读的 `is_maintenance_enabled()` 未改动：停服标志与进程内缓存刷新逻辑保持原样，幂等分支同样会刷新缓存为 True。
- 数据：`system_flag(maintenance_mode)` 与 `audit_log(category='mobile', action='emergency_stop')`，无表结构变更。

## 修复

- `D:\code\otherProjects\20_News\backend\app\services\mobile_service.py`
  - `emergency_stop()` 头部加幂等短路：`current = await get_maintenance(db)`，`current["enabled"]` 为真时只刷新进程内缓存并返回 `{**current, "already": True}`，不再写标志、不再写审计；首次停服分支返回 `{**await get_maintenance(db), "already": False}`。
- `D:\code\otherProjects\20_News\apps\admin-web\src\views\mobile\ManageAlert.vue`
  - 状态改为三态：`m = ref(null)`（null = 未知）+ `state` computed 映射 `unknown | on | off`；横幅按状态加 `m-alert__banner--unknown`（琥珀警示色），未知态标题为「维护态未知」并显示失败原因与「请重试确认状态后再执行停服/恢复操作」。
  - 未知态下只渲染「重新读取状态」按钮，停服/恢复按钮一律不出现（`getByRole` 断言计数为 0）；`stop()`/`resume()` 入口各加一道 `state.value === 'unknown'` 兜底。
  - `reload()` 的 `catch` 不再伪造 `{ enabled: false }`，改为 `m.value = null` + `loadError = e.message`。
  - **I54 修复**：`reason = (value || '').trim()`（取 prompt 解构出来的 `value`），并去掉「校验通过但仍为空」时继续提交的可能。
  - 新增 `submitting` 守卫（提交中禁用按钮，避免连点），新增 `normalize()` 统一响应结构。
  - 新增已停服时长计时：`startedAt` 解析后端本地 naive ISO，`now` 由 `setInterval(1000)` 驱动，仅在 `state === 'on'` 时启动、`watch` 切换与 `onUnmounted` 都会 `clearInterval`（正常态不留定时器）；`at` 缺失时显示「时长未知（停服记录缺少时间戳）」而不是 NaN。
  - 提示文案补「**停服不会自动到期恢复**，必须在这里手动解除」；停服态 toast 区分 `already`（「系统已处于停服态，本次未重复记录」）。
- `D:\code\otherProjects\20_News\apps\admin-web\src\api\mobile.js`
  - `getMaintenanceStatus` 加 `{ silent: true }`：读失败由页内横幅承载，避免同一错误弹两条 toast。
- `D:\code\otherProjects\20_News\backend\tests\test_t02489_emergency_stop.py`（新增，8 条）
  - 首次停服写标志+1 条审计；重复停服审计仍 1 条且 `at`/`reason` 保持首次值、`already=True`；重复停服后守卫仍判定为维护态；恢复后再停服算新一轮（审计 2 条）；路由层强制原因、第二次调用返回 `already`、`/m/maintenance-status` 结构含 `at`（前端倒计时依赖）、无 token 拒绝。
  - 用 `autouse` fixture 重置模块级 `_maint_cache`，避免 TTL 5s 缓存跨用例串味。
- `D:\code\otherProjects\20_News\apps\admin-web\tests\emergency-stop-state.spec.js`（新增，6 条）
  - 状态接口 500 → 未知态可见、无「生产运行正常」文本、停服/恢复按钮计数为 0、有重试按钮；重试成功后出现正常态与停服按钮；填原因点确认 → 断言 `POST /m/emergency/stop` 真的发出且 body 为 `{reason:"上游 TTS 全部超时"}`（去首尾空格）→ 横幅转停服态 + toast；纯空格原因不提交；停服态无重复停服入口且 `已停服：1 分 xx 秒` 2.1s 后文本变化；恢复调用 `/m/emergency/resume` 后回到正常态。
  - `localIso()` 按本地时钟生成 `at`（后端存 naive 本地 ISO，用 `toISOString()` 会整体偏一个时区、倒计时读数失真）。

## 验证

- `backend/.venv/Scripts/python.exe -m pytest tests/test_t02489_emergency_stop.py -q -p no:warnings` → **8 passed in 2.67s**。
- `PW_CHANNEL=chrome npx playwright test tests/emergency-stop-state.spec.js --reporter=line` → **6 passed (24.7s)**（本机 vite dev @5181，Playwright webServer 复用）。
- `npm run build`（apps/admin-web）→ **✓ built in 56.17s**，无编译告警。
- 修复前证据：`git show HEAD~1:apps/admin-web/src/views/mobile/ManageAlert.vue` 第 59 行仍是 `reason = v.trim()`、第 44 行仍是 `.catch(() => ({ enabled: false }))`；`v` 在该作用域未定义，故 I54 用例的三个断言（请求发出 / body 内容 / 横幅转停服态）在修复前必然失败。
- 提交：`f536735 fix(mobile): 应急停服可用性与状态可信 (T02489 / FR-UX-201)`，path-limited 只含上述 5 个文件（453 insertions / 24 deletions），未裹挟工作区内其他并发会话的 WIP（`rewriter.py`、`CourseMaterials.vue`、`audio.js` 等）。
- 未实测项（如实标注）：
  - 真机/真实后端链路未跑（本轮全程用 Playwright route mock）；停服后 `workflow_scheduler` 实际返回 409 的行为属 FR-M902，不在本单验收范围。
  - 「状态未知」的视觉配色（琥珀）与文案未经产品确认，只保证不再是绿色「运行正常」。
  - ACC-UX-201 第 2 条要求「非超级管理员看不到入口」由路由 `requireRole:'admin'` 与后端 `require_admin` 双重保证，本单只实测了后端 401 分支，未实测 operator 角色下的入口隐藏。

## 本次回写

- 更新任务 T02489 状态为 done（`verified:false`：UI 交互已实测，但 ACC-UX-201 的角色隐藏项与真实后端链路未覆盖）。
- 新建派生子任务 3 张（详见「下一步建议」，均带 `derivedFrom=T02489`）。
- 留痕文档：`D:\code\otherProjects\20_News\_validate\news2\result_T02489.md`。

## 下一步建议

1. **停服到期自动恢复需产品裁决**（已建派生单 T02611）：本单按「已停服时长实时计时 + 明示不会自动恢复」落地，而 PRD 原文「停服后提供恢复入口与倒计时」存在另一种解读——倒计时指「距自动恢复还剩多久」。若采后者需要停服时可选填时长、到期自动 resume 并写审计，属产品语义决策，不宜由实现侧擅自选边。
2. **`is_maintenance_enabled()` 是 fail-open，与停服意图相反**（已建派生单 T02612）：`mobile_service.py:340` 捕获任何异常后 `on = False` 并注释「保证安全默认」，但这里的「安全」方向是反的——数据库抖动/超时期间，值班人已下的应急停服指令会被绕过、新任务照常触发。应改为 fail-closed（读不到即拒绝触发新任务）或至少用缓存最后一次已知值 + 告警。
3. **PC 端缺应急停服入口**（已建派生单 T02613）：全站只有移动端路由 `/m/manage/alert` 提供该操作（`grep emergencyStop` 仅命中 `api/mobile.js` 与 `ManageAlert.vue`），而超级管理员日常在 PC 后台作业；出故障时要切到移动布局才能停服。建议把已修好的三态卡片抽成组件复用到 PC「系统维护」页，涉及入口摆放与权限提示，需产品确认。
