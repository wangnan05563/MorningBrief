# T02492 交付结果 —— 2.4 FR-UX-204 自动审批护栏

需求口径：三条规则改为「默认校验、显式关闭才跳过」；开启前要求勾选风险确认；记录每次自动通过的命中规则。

## 根因

1. **零检查放行**：`AutoReviewService.try_auto_approve` 的判定是「所有启用的规则全部命中」。
   当配置为 `enabled=1` + `require_content_safe=0` + `require_steps_first_success=0` + `keyword_whitelist=[]` 时，
   三条校验一条都不会执行，`matched_rules` 与 `fail_reasons` 双双为空 → 旧逻辑视同「全部命中」，
   直接走 `approve + publish_episode`，任意稿件未经任何检查自动上线。
   根因其二是**配置层无护栏**：`update_config`（改造前 auto_review_service.py:106-121）允许保存这种组合，
   界面还写着「触发条件（全部命中才自动通过）」，看起来像有守卫。
2. **无风险确认概念**：`auto_review_config` 表没有确认位，开启总开关与改配置是同一次点击，
   管理员跳过了哪条校验、什么时候跳过的，只在审计日志里以字段值形式存在，界面上不成立即提示。
3. **命中记录不完整**：`Review.auto_trigger_reason` 只存命中的规则数组，看不出这次放行**少查了什么**；
   历史列直接把原始 JSON 甩给界面（`AutoReviewConfig.vue:formatRules` 解析数组、其余原样返回），
   移动端 `ReviewList.vue:95` 更是直接渲染 JSON 字符串。

## 影响范围

- 配置读写：`auto_review_config` 表（新增 3 列）、`AutoReviewService.update_config`、
  `GET/PUT /admin/api/v1/auto-review/config`。
- 运行期：`try_auto_approve`（工作流创建 Review 后自动审批的唯一入口）、
  `_execute_auto_approve` 的 `Review.auto_trigger_reason`、`AutoReviewStat.trigger_reason`、审计日志 detail。
- 界面：`系统配置 > 自动审批`（PC）、移动端审核详情的「自动审批」字段、执行历史「触发原因」列。
- 存量数据：启动迁移把历史行 `risk_acknowledged` 补 0；已开启但三条全关的遗留配置**继续被运行期拒绝**
  （转人工审核），这是行为变化，启动日志已点名提示。

## 修复

**后端**

- `backend/app/models/auto_review_config.py`：新增 `risk_acknowledged` / `risk_acknowledged_by` /
  `risk_acknowledged_at` 三列与 `DEFAULT_RISK_ACKNOWLEDGED=False`；两条规则字段的注释改为
  「默认校验，置为 False 才是显式跳过」。
- `backend/app/main.py:856` `_migrate_auto_review_risk_columns()`：幂等 `PRAGMA table_info` + `ALTER`，
  表不存在时直接返回；迁移后统计并告警「总开关已开但三条校验全关」的存量配置。
  在 startup 里紧跟 `_migrate_adplacement_enabled_column()` 之后调用，独立 try/except 不阻断启动。
- `backend/app/services/auto_review_service.py`
  - `parse_keywords()` / `split_rules()`：白名单容错解析 + 「生效/跳过」拆分，配置层与运行期共用同一口径。
  - `update_config(..., risk_acknowledged=False)`：开启时两条硬护栏——
    ① 三条全关 → `BizError(code=400)`「三条校验全部关闭时不能开启自动审批」；
    ② 未勾选风险确认且不可沿用 → `BizError(code=400)`「开启自动审批前需勾选风险确认：跳过的校验（…）将不再检查」。
    沿用条件：总开关本就开着 + 此前已确认 + 跳过的校验没有变多（`set(skipped) <= set(prev_skipped)`），
    因此日常加关键词不会被反复打勾，多关一条则必须重新确认；关闭总开关即清空确认位与确认人/时间。
    审计 detail 增加 `risk_acknowledged` / `risk_carried` / `enforced_rules` / `skipped_rules`。
  - `try_auto_approve`：开关检查后先算生效校验，**为空时一律拒绝自动通过并转人工**，
    写失败统计（`{"skipped_rules": [...], "guard": "no_enforced_rule"}`）+ warning 日志；
    关键词解析复用 `parse_keywords`，规则判定不再各写一遍。
  - `_execute_auto_approve`：`Review.auto_trigger_reason`、成功统计、审计日志统一改为
    `{"matched_rules": [...], "skipped_rules": [...]}`；失败分支也补上 `skipped_rules`。
- `backend/app/routers/admin/auto_review.py`：请求体新增 `risk_acknowledged`；
  GET/PUT 共用 `_config_payload()`，出参补 `risk_acknowledged[_by|_at]` 与 `enforced_rules` / `skipped_rules`
  （GET 保持 `success(data=...)` 信封不变）。

**前端**

- `apps/admin-web/src/utils/autoReviewRules.js`（新增）：规则中文名映射 + `formatTriggerReason()`，
  兼容旧数组、新对象、失败/护栏三种 JSON 形态；PC 与移动端共用一份口径。
- `apps/admin-web/src/views/system/AutoReviewConfig.vue`：分隔标题改为
  「触发条件（默认全部校验；关闭即跳过，至少保留一条）」；每个开关关闭时显示
  「已关闭：本项不再检查，命中即放行」；关键词为空显示「未配置关键词：本项不检查」；
  开启后展示「本次生效 / 跳过」标签清单；`needsAck` 为真时渲染风险确认勾选框
  （文案点名被跳过的校验并声明「不经人工审核自动发布」），跳过项增减时自动清空勾选；
  `saveConfig` 前置拦截「三条全关」「未勾选确认」，PUT 带上 `risk_acknowledged`；
  历史列改用 `formatTriggerReason`。确认位刻意放在 `form` 之外的独立 ref，避免断点续录把上次的勾选恢复出来。
- `apps/admin-web/src/views/mobile/ReviewList.vue:95`：不再直接渲染 JSON，改走同一格式化函数。

## 验证

1. **后端单测** `backend/tests/test_t02492_auto_review_guard.py`（新增 14 条）→ **14 passed in 3.46s**：
   - `split_rules` 全开/全关两种口径、`parse_keywords` 对坏 JSON / 非数组 / null 的容错；
   - `update_config`：三条全关被拒且配置未落库；未勾选确认被拒且提示里点名跳过的校验；
     确认后 `risk_acknowledged_by/at` 落库、审计 detail 的 `enforced_rules`/`skipped_rules` 正确；
     「沿用」用例——加关键词不重新打勾、再关一条必须重新确认；关闭总开关清空确认位；
   - 运行期护栏：遗留「开启+全关」配置下 `try_auto_approve` 返回 `auto_approved=False`，
     Review 仍 `pending`，统计行 `success=False` 且 `trigger_reason.guard == "no_enforced_rule"`；
   - 留痕：`content_safe` 单独生效时 `Review.auto_trigger_reason` 为
     `matched_rules=["content_safe"]`、`skipped_rules=["steps_first_success","keyword_whitelist"]`，成功统计同快照；
     失败分支同样带 `skipped_rules`；
   - 接口：`GET /admin/api/v1/auto-review/config` 出含 `code=0` 信封与新三字段；
     `PUT`（全关 / 未确认）→ HTTP 200 + `code=400` + 护栏文案，确认通过后 `code=0` 且回显生效/跳过清单。
2. **回归** `test_auto_review_content_safe.py` + `test_ebook_audiobook_guard.py` +
   `test_maintenance_cleanup_workflows_cascade.py` + `test_queue_batch_delete_autoreviewstat.py` +
   `test_review_service.py` → **39 passed in 8.14s**（含 skipped 语义、批量审批、级联删除均未受影响）。
3. **迁移实测**：复制 `backend/data/news.db` 到隔离目录，按旧 schema 建 `auto_review_config`
   并插入 `enabled=1` + 两条开关 0 + `'[]'` 的遗留行 → 跑 `_migrate_auto_review_risk_columns()`：
   三列补齐、`risk_acknowledged` 回填 0、启动告警按预期打印；**重复执行不报错、不重复加列**（幂等）。
   另注：当前开发库 `news.db` 尚无 `auto_review_config` 表，迁移函数对该情况直接返回，交由 `get_config` 首次 seed。
4. **管理端构建**：`apps/admin-web` `npm run build` → **✓ built in 33.37s**。
5. **新增 e2e** `apps/admin-web/tests/auto-review-guard.spec.js`（系统 Chrome 无头实测）→ **6 passed (35.1s)**：
   - 空白名单即显示「本项不检查」；关掉内容安全后出现「已关闭：本项不再检查」，
     生效清单只剩「步骤一次成功」，跳过清单为「内容安全检测、关键词白名单」；
   - 开启总开关后出现确认框，未勾选直接保存 → 提示「请先勾选风险确认」**且 PUT 请求数为 0**；
   - 勾选后保存 → 恰好 1 次 PUT、请求体含 `risk_acknowledged: true`、提示「配置已保存」、确认框收起；
   - 三条全关 → 前端拦截「三条校验全部关闭时不能开启自动审批」，不发请求；
   - 服务端拒绝（`code=400` 信封）→ 提示「保存失败：自动审批护栏未通过」，**不出现「配置已保存」**；
   - 历史列渲染为「命中：内容安全检测 / 跳过：步骤一次成功、关键词白名单」，失败行显示护栏原因。
6. **回归 e2e**：`review.spec.js` + `destructive-confirm.spec.js` → **18 passed (46.2s)**。
7. **提交**：`17f3a0a`（9 个本单文件）+ `688d50b`（失败留痕补齐）。`git show --stat` 复核未裹挟并发会话 WIP
   （`api/audio.js`、`CourseMaterials.vue`、`rewriter.py`、`style_library.py`、`VERSION`、perf 产物等仍在未提交状态）。

未达 `verified` 的部分：以上均为 mock 数据下的界面实测与单进程库实测；**未在生产 `enabled=1` 的实例上真跑一次
工作流自动审批链路**（需真实稿件 + 微信 msgSecCheck 凭证），人工抽查步骤：开启自动审批 → 造一条只满足内容安全
的稿件 → 看执行历史是否显示「命中：内容安全检测 / 跳过：…」。

## 本次回写

- T02603【AI回写待审核】存量自动审批配置无需补风险确认，护栏对已开启项不生效，需产品裁决
- T02604【AI回写待审核】关键词白名单为子串包含匹配，单独使用时存在误放行风险

## 下一步建议

1. 升级后遗留的 `enabled=1` 配置不会因「从未确认风险」而被拦：运行期只拒绝「三条全关」，
   确认位只约束保存动作。现网已开启的自动审批仍按旧规则放行，直到管理员下次进配置页——
   需要产品在三条口径里选一条（强制补确认 / 运行期一并拒绝 / 维持现状但横幅提示）——已建派生单 T02603。
2. 关键词白名单是大小写不敏感的**子串包含**（`_check_keyword_whitelist`），而 T02492 之后
   「只留关键词一条校验」成了合法组合，短词（如 `AI`）会命中 `air`/`maintain` 之类正文而误放行；
   改判定会让存量白名单突然不命中，须先用历史稿件比对三种口径的命中集差异再裁决——已建派生单 T02604。
