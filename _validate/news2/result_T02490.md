# T02490 破坏性操作确认规范（FR-UX-202）

## 根因

管理端与小程序的破坏性动作各自写 `ElMessageBox.confirm('确认删除？')`，没有统一口径：

1. 缺「影响条数」与「不可逆声明」——用户看不到删一行会连带多少行（C9/I42/I45）；
2. 高危动作单击即执行（`ReviewList.vue:154` 通过=立即发布、`ManageChannels.vue:17-23` 停用即取消排队任务、`About.vue` 升级、`CosFiles.vue` 同名覆盖）；
3. 预览失败被 `catch` 吞掉后仍打开确认框，退化成「零信息确认」（`DatabaseAdmin.vue:583-609`、`ChannelManagement.vue:1071`）；
4. 删除结果按前端 `deleteIds.length` 报数，与服务端实际影响行数可能不符（M37）；
5. 级联预览只覆盖 `TABLE_RELATIONS` 已声明的表，未声明的下游（script/review/episode/play_log）静默不删（M33）；
6. 小程序下载页三个「清空」按钮视觉同权重、确认文案无对象无条数（J60）。

PRD §6.3 要求：`动作 + 对象 + 影响条数 + 不可逆声明`，高风险再要求输入确认词，预览失败禁止提交。

## 影响范围

- 管理端 8 个视图：频道管理、数据库维护、系统清理、关于/升级、云端文件、移动审批、移动频道、移动广告；
- 新增公共组件 `src/utils/dangerConfirm.js`（全部确认框的唯一实现）；
- 后端新增 1 个只读接口 `GET /admin/api/v1/channels/{id}/delete-preview`；`db-admin` 级联预览响应新增 `undeclared_downstream` 字段（向后兼容，前端按需展示）；
- 小程序下载页 3 处清空/删除入口的文案与视觉权重；
- 既有 e2e：`tests/channels.spec.js` 的删除用例断言文案随新口径更新。

未纳入本单的其余 15 处 `ElMessageBox.confirm` 站点见「下一步建议」。

## 修复（绝对路径与改动点）

1. `D:\code\otherProjects\20_News\apps\admin-web\src\utils\dangerConfirm.js`（新增）
   - `buildDangerText()` 拼「动作：对象 / 影响范围（可多行）/ 明细 / 红色不可逆声明」；
   - 所有插值经 `escapeHtml()` 转义——对象名来自抓取内容（RSS 标题、素材名），确认框走 `dangerouslyUseHTMLString`，不转义即成 XSS 注入口；
   - `dangerConfirm(opts)`：传 `confirmWord` 走 `prompt` + `inputValidator` 逐字比对，否则 `confirm`；取消与遮罩关闭一律返回 `false`。
2. `D:\code\otherProjects\20_News\apps\admin-web\src\views\channel\ChannelManagement.vue:1071-1105`
   - `handleDelete` 先 `deleteChannelPreview(row.id)`，失败即 `ElMessage.error('无法获取删除影响面预览，已禁止删除：…')` 并 return（C10）；
   - 确认正文用预览返回的真实条数 + 三条连带说明（书单 CASCADE / 素材无外键变无主 / 工作流仅置空），确认词＝频道名（C9）。
3. `D:\code\otherProjects\20_News\backend\app\services\channel_service.py:284-309` 新增 `delete_preview()`，计数口径与 `delete_channel` 真实行为逐条对齐。
4. `D:\code\otherProjects\20_News\backend\app\routers\admin\channels.py:522-535` 新增只读路由（require_admin，频道不存在返回 404）。
5. `D:\code\otherProjects\20_News\apps\admin-web\src\api\channels.js` 新增 `deleteChannelPreview`。
6. `D:\code\otherProjects\20_News\apps\admin-web\src\views\maintenance\DatabaseAdmin.vue`
   - `:337-378` 弹窗标题补中文表名（M32）、新增「合计受影响 N 行（主表 + 级联）」、`undeclared_downstream` 告警条、常驻不可逆声明（M31/M33）；
   - `:602-641` 单条与批量删除的级联预览失败 → 报错并拒绝打开弹窗（M31）；
   - `:646-674` 以服务端 `affected/cascade` 为准报数，`affected < requested` 时改为 warning 提示核对剩余数据（M37）。
7. `D:\code\otherProjects\20_News\backend\app\services\db_admin_service.py:84-94,485-490` 新增 `UNDECLARED_DOWNSTREAM` 并在 `cascade_preview` 透出。
8. `D:\code\otherProjects\20_News\apps\admin-web\src\views\maintenance\Maintenance.vue:327-358` 真实删除前用 `dangerConfirm` 写清「删什么 / 保留多久 / 上次预览命中 N 项（前 5 条）/ 不可恢复」，无预览时提示先 dry-run（M58/M59）。
9. `D:\code\otherProjects\20_News\apps\admin-web\src\views\about\About.vue:378` 立即更新加确认（重启中断工作流 + 不支持管理端回滚 + 确认词 `UPDATE`）（M95）。
10. `D:\code\otherProjects\20_News\apps\admin-web\src\views\cos\CosFiles.vue:299` 同名对象覆盖上传需输入「覆盖」（H9）。
11. `D:\code\otherProjects\20_News\apps\admin-web\src\views\mobile\ReviewList.vue:249-258,301-326` 单条通过补确认（I1）、一键全部通过按频道列分布且未限定频道时要求输入「全部通过」（I2）。
12. `D:\code\otherProjects\20_News\apps\admin-web\src\views\mobile\ManageChannels.vue:53` 停用前告知「该频道排队中的工作流任务会被取消」（I42）；`ManageAds.vue:54` 启用/停用都确认（I45）。
13. `D:\code\otherProjects\20_News\apps\miniprogram\pages\download\download.{js,wxml,wxss}` 三档清空/删除按权重分层（单章删除最低、整课居中、全部清空最高并显示总章数与占用），确认文案带对象名与条数（J60）。

## 验证（实测证据）

1. `apps/admin-web` 生产构建：`npm run build` → `✓ 346 modules transformed / ✓ built in 21.41s`。
   （期间发现并修掉一处我自己引入的回归：补丁脚本把 `api/channels.js` 整体覆盖成 2 个导出，已 `git checkout` 还原后重新追加，`export const` 恢复 16 条。）
2. 后端单测 `backend/tests/test_t02490_destructive_confirm.py`：5 passed。
   - 预览计数与真实行数一致（书单 1 / 素材 1 / 工作流 1）；
   - `delete_channel` 后工作流保留且 `channel_id` 置空、`book_pool_item.channel_id` 外键确为 `ON DELETE CASCADE`、生产引擎连接事件仍下发 `PRAGMA foreign_keys=ON`（测试库另建内存引擎不带该 PRAGMA，故不直接断言级联生效，改断言 schema + PRAGMA 开关两道前提）；
   - `cascade_preview` 对 workflow 暴露未声明下游提示、对 episode 为 `None`；
   - 预览接口对不存在频道返回业务码 404。
3. 后端回归：`test_db_admin_audit_mask.py test_db_admin_import_upsert.py test_db_admin_sensitive_guard.py test_api_channels_ordering.py test_audiobook_channel_schedule.py test_channel_asset_seed.py test_channel_bgm_gap_mode.py test_channel_icon.py test_channel_material_lookback.py test_channel_prompt_json.py` → 107 passed。
4. 新增 e2e `apps/admin-web/tests/destructive-confirm.spec.js`（系统 Chrome 无头实测）→ 6 passed：
   - 频道删除确认框四要素齐全、正文条数来自 mock 预览（12/340/5）、不输入频道名点确认被 `请逐字输入 科技频道` 拦下、输入后才发出 `DELETE`；
   - 取消后不发 `DELETE`；
   - 预览返回 500 时不出现确认框、无 `DELETE` 请求；
   - 数据库后台删除弹窗显示中文表名、「合计受影响 4 行（主表 1 + 级联 3）」、未声明下游告警、不可逆声明；
   - 级联预览失败时不打开删除弹窗；
   - 移动审批一键通过显示「本页 3 条待审内容（覆盖 2 个频道）」与逐频道分布，并要求确认词。
5. 全量 e2e：88 条 → 84 passed / 4 failed。4 条失败为并发会话未提交 WIP 所致，与本单无关：3 条 `page-layout-padding`（`views/channel/CourseMaterials.vue` 未提交改动把内边距改成 `10px 12px`）、1 条 `review.spec.js:128` 图片预览（`src/api/audio.js` 未提交的 axios→fetch 重写）。本单提交 `3457e5a` 未含这两个文件。

## 本次回写

- T02596【AI回写待审核】剩余 15 处 `ElMessageBox.confirm` 站点统一接入 dangerConfirm
- T02597【AI回写待审核】小程序下载页清空分级需微信开发者工具真机复验（缺环境）
- T02598【AI回写待审核】素材表 `channel_id` 缺外键约束，删除频道留下无主数据
- T02599【AI回写待审核】系统清理页补「按全链路清理工作流」能力（DB 后台不做全链删）

## 下一步建议

1. 剩余破坏性入口尚未接入统一确认（`AdMaterials.vue`、`AdPlacements.vue`、`AIConfig.vue`、`BookPoolPanel.vue`、`MaterialLibrary.vue`、`CosFiles.vue` 其余动作、`ManageAlert.vue`、`ManageUsers.vue`、`QueueManagement.vue`、`ReviewDetail.vue`、`review/ReviewList.vue`、`AutoReviewConfig.vue`、`WorkflowDetail.vue`、`WorkflowList.vue`）——已建派生单 T02596。
2. 小程序改动只能由微信开发者工具/真机验证，本环境无法执行——已建派生单 T02597（缺环境）。
3. `material.channel_id` 无外键，删除频道后素材成无主数据，预览只能如实告知、不能修——需 DB 迁移补约束或清理策略，已建派生单 T02598。
4. M33 的裁决是「DB 后台不做全链删」，但全链清理能力目前在系统清理页缺失——已建派生单 T02599。
