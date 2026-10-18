# T02491 广告启停修复（FR-UX-203 / 评审行 D14）

## 根因

「停用」这条唯一的可逆干预路径在 PC 端根本不存在，且后端三处叠加缺陷让它即使存在也不可信：

1. `apps/admin-web/src/views/ad/AdPlacements.vue` 只有「删除」一列操作——D14 记录的「PC 端想停一个广告只能删规则，删了不可逆；启停只在移动端页面有」；
2. `backend/app/services/ad_service.py:get_active_placements` 的 where 条件只有日期区间，**没有 `enabled` 谓词**——`set_placement_enabled` 把 `enabled` 写成 0 之后，C 端取当期生效投放照样拿到它，停用完全无效；
3. 同函数按 `ad:placement:{date}` 缓存 **25 小时**（`ACTIVE_PLACEMENT_TTL = 25 * 3600`），而 `create/update/delete placement` 全部不失效该缓存——即使补上 enabled 过滤，停用也要等到次日缓存自然过期才生效，等于「开关按了没反应」；
4. `backend/app/routers/admin/ads.py` 只导入了 `success`，`update_placement` 的异常分支写的是 `return error(code=404, ...)` → 对不存在的 id 触发 `NameError`，移动端 PUT 直接 500（D14 后半句）；
5. 移动端 `ManageAds.vue` 的确认文案承诺「立即停止对外曝光 / 即时生效于 C 端」，而广告实际是在节目生成阶段被 ffmpeg 拼进音频的（`concat.py:401`），停用去不掉已生成节目里的广告——文案本身就是错的；且 `target` 取了列表里不存在的 `p.name`，确认框永远只显示数字 id。

## 影响范围

- 后端：`AdService.get_active_placements`（C 端唯一投放读路径）、`create_placement` / `delete_placement` / `update_placement` 三个写入点、`get_schedule` 出参；
- C 端消费方只有一处：`backend/app/workflow/stitch/concat.py:401`（生成节目时用 ffmpeg 把 head/mid/tail 拼接进音频文件），**没有独立的 C 端广告投放接口**——因此「停用」生效点是「新生成的节目」，已生成节目里已拼接的广告不会因停用而消失（见派生单 T02601）；
- 管理端 PC：`AdPlacements.vue`（新增状态列 + 停用确认）、`AdSchedule.vue`（排期日历新增停用标记）、`ManageAds.vue`（移动端确认文案纠偏）；
- e2e mock 夹具 `tests/helpers/mock.js` 补 `enabled` 字段（原先列表 mock 无该字段，状态列无从判断）。

## 修复（绝对路径与改动点）

1. `D:\code\otherProjects\20_News\backend\app\routers\admin\ads.py:10`
   `from app.core.response import error, success`——补上缺失的 `error` 导入，PUT 对不存在 id 返回业务码 404 而非 500。
2. `D:\code\otherProjects\20_News\backend\app\services\ad_service.py:26-33`
   新增 `invalidate_active_cache()`：`await self.cache.delete_pattern("ad:placement:*")`。docstring 写明「必须在数据库提交之后调用」——提交前失效会让并发读把旧结果重新写回缓存。
3. `D:\code\otherProjects\20_News\backend\app\services\ad_service.py:252`
   `get_active_placements` where 增加 `AdPlacement.enabled == 1`。列定义为 `NOT NULL DEFAULT 1`（`app/main.py:846` 迁移语句），历史行迁移时已回填 1，故不写 `coalesce` 兜 NULL 的分支。
4. `D:\code\otherProjects\20_News\backend\app\services\ad_service.py:182,196` 与 `ads.py:126-128`
   创建 / 删除在 service 提交后失效缓存；更新在路由层 `await db.commit()`（含审计日志）之后失效，保证三个写入口都不留旧缓存。
5. `D:\code\otherProjects\20_News\backend\app\services\ad_service.py:227`
   `get_schedule` 出参补 `enabled`——排期页此前无法区分「在排」与「已停用」。
6. `D:\code\otherProjects\20_News\apps\admin-web\src\views\ad\AdPlacements.vue:26-36,190-214`
   新增「状态」列（`el-switch`，`:model-value="row.enabled === 1"` 单向绑定 + `:loading` 按 id 置灰），`handleToggle()` 先走 `dangerConfirm`（动作 + 对象「广告位 · 素材名」+ 影响范围「生效区间」+ 结论「启停可随时回退，不影响已生成的节目数据」），确认后 `PUT /ads/placements/{id}`；仅在成功时写回 `row.enabled`，请求失败不写回 → 开关自动回弹，不会出现「UI 显示已停用、服务端还在播」的假成功。
7. `D:\code\otherProjects\20_News\apps\admin-web\src\views\ad\AdSchedule.vue:37-49,77-79,96,231-249`
   日历格子按 `enabled === 0` 加 `.slot-off`（灰化 + 删除线）与「已停用」标签。
8. `D:\code\otherProjects\20_News\apps\admin-web\tests\helpers\mock.js:197,207,229,235`
   投放列表与排期 mock 补 `enabled`（列表第 2 条设为 0，供 e2e 断言两种状态）。
9. `D:\code\otherProjects\20_News\apps\admin-web\src\views\mobile\ManageAds.vue:51-62`
   移动端启停确认文案此前承诺「立即停止对外曝光」「启停会即时生效于 C 端」——与真实生效边界不符（见影响范围），改为「之后新生成的节目不再插入该广告」并显式说明已生成节目里的广告去不掉；同时 `target` 用的是列表里不存在的 `p.name`，永远退化成数字 id，改为 `p.material_name`。
10. `D:\code\otherProjects\20_News\apps\admin-web\src\views\ad\AdPlacements.vue:196-201`
    PC 停用确认文案同样按真实生效边界改写（与移动端口径一致），避免本单自己引入新的过度承诺。

## 验证（实测证据）

1. 后端单测 `backend/tests/test_t02491_ad_toggle.py`（新增 6 条）+ `test_ad_service.py`（回归 12 条）+ `test_t02490_destructive_confirm.py`（5 条）+ `test_stitch_lossless_intermediates.py` → **35 passed in 5.53s**：
   - 停用位不再下发（`result["mid"] is None`），启用位仍下发；
   - 停用 → 提交 → 失效缓存后，`ad:placement:{date}` 键为空且重新查询查不到；重新启用即恢复（可逆性）；
   - `invalidate_active_cache` 清掉多日期键（`delete_pattern` 前缀匹配真实生效）；
   - `delete_placement` 后缓存被清（否则 C 端继续播已删素材）；
   - `PUT /admin/api/v1/ads/placements/999999` → HTTP 200 + body `code=404` + message 含「投放不存在」（**修复前此处 500**）；
   - `PUT {enabled:7}` → 400 且库内 `enabled` 仍为 1（校验未穿透）；
   - `PUT {enabled:0}` 走真实路由后，缓存键消失且重新查询不再返回该投放。
2. 管理端生产构建：`apps/admin-web` `npm run build` → 首次 **✓ built in 37.22s**，文案改写后复跑 **✓ built in 34.10s**。
3. 新增 e2e `apps/admin-web/tests/ad-toggle.spec.js`（系统 Chrome 无头实测）→ **6 passed (57.6s)**：
   - 状态列按 `enabled` 渲染（第 1 行 `.is-checked`、第 2 行未选中）；
   - 点停用弹出确认框，正文含「停用投放：开头位 · 品牌广告A」「生效区间 2026-07-01 ~ 2026-07-31」「停用后，之后新生成的节目不再插入该广告」与「已经生成好的节目里广告是拼在音频里的」；取消后 **零 PUT**、开关保持原状；
   - 确认停用后恰好发出 1 次 `PUT /ads/placements/1`，请求体 `{enabled:0}`，出现「已停用」提示且开关落位；
   - PUT 返回 500 时开关回弹到启用态、且不出现「已停用」提示（不报假成功）；
   - 移动端 `/m/manage/ads` 确认框显示「停用广告投放：投放「品牌广告A」」（证明 `p.name` → `material_name` 修复生效），含真实生效边界两条，确认后发出 `PUT {enabled:0}` 且 badge 变为「已停用」；
   - 排期日历对停用位显示「已停用」并对该格加 `slot-off` 类。
4. 回归 e2e：`ads.spec.js` + `destructive-confirm.spec.js` + `channels.spec.js` → **20 passed (52.6s)**（mock 加字段未影响既有用例）。
5. 提交：`3256cd1`（后端 + PC 状态列 + 日历 + 测试，7 个文件）与 `ab32c67`（PC/移动端文案纠偏，3 个文件）；`git show --stat` 确认仅含本单文件，并发会话的未提交 WIP（`api/audio.js`、`CourseMaterials.vue`、`rewriter.py` 等）未被裹挟。

## 本次回写

- T02600【AI回写待审核】广告生效投放缓存进程内失效，多 worker 下停用仍延迟 25h
- T02601【AI回写待审核】停用对已生成节目无效：广告在生成期被 ffmpeg 拼进音频，需产品裁决补救口径
- T02602【AI回写待审核】投放状态只看 enabled 不看排期区间，「投放中」与真实播放不一致

## 下一步建议

1. 缓存是进程内 `TTLCache`（`app/cache/manager.py`），`delete_pattern` 只清当前 worker；uvicorn `workers>1` 时停用请求落在 A 进程，B 进程仍会命中旧缓存最长 25h。需要跨进程失效口径（版本键 / Redis pub-sub / 或部署约束 workers=1）——已建派生单 T02600。
2. 广告是在工作流生成阶段被拼接进音频文件的（`concat.py:401` 起），停用只影响之后新生成的节目；当日已生成并分发的节目仍带广告。要不要「停用即重生成/下架当日节目」是产品决策，本单未擅自实现——已建派生单 T02601。
3. 「投放中」的判定只看 `enabled`、不看日期区间，与 C 端实际取数口径（今天是否落在区间内）不一致，是「点了停用好像没生效」这类误判的温床——已建派生单 T02602。
4. （仅观察不建单）本单未复现真实多 worker 部署与真机小程序播放链路，上述两条边界已在派生单中标注依赖环境。
