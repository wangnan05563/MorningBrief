# T02501 回传文档（FR-UX-402 审核状态口径：4 态含 replaced 有可见去向）

> **本单未完结，保持待办可见**：需求的「可见去向」部分绑在待拍板的 DEC-UX-001（三选项 A/B/C）上，
> 未获批准前不改 tab/筛选结构（避免与 SRS 三栏口径冲突并返工）。
> 决策无关的缺陷已修复合入（`450d0f1`），推荐方案的**已验证补丁**已备好，拍板只需一句话——见 `_validate/news2/dec-ux-001-brief.md`。

## 根因

1. **前端只映射 3 态，第 4 态被当成未知值裸显示。** 后端 `ReviewStatus` 有 4 值（`backend/app/models/review.py:17`，并有 CheckConstraint 锁死），
   但 `ReviewList.vue` 与 `ReviewDetail.vue` 的 `statusText()` 只有 `pending/approved/rejected` 三项，
   兜底分支是 `|| status` → `replaced` 记录直接把英文枚举当文案渲染。同仓库的 `WorkflowDetail.vue:853` 早已有完整 4 态 `REVIEW_STATUS_MAP`
   （`replaced: { label: '已替换', type: 'info' }`），即**正确口径在同一项目内已存在，只是审核页没跟上**——这是典型的枚举多点复制而非单一字典（该结构性问题由 T02504 / FR-UX-405 承担）。
2. **列表页没有任何入口能查到 `replaced`。** `ReviewList.vue` 的 `loadList()` 把 `status` 恒等于当前 tab，而 tab 只有三个 →
   一旦产生 replaced 记录，它在列表里永久不可见（详情页可直达，但没人知道 id）。
3. **产生入口是活的。** 「替换段落」是待审核详情页一步可达的 `el-radio value="replace"`（`ReviewDetail.vue:112`），
   后端 `review_service.py:269` 会把状态写成 replaced。所以这不是理论风险，是「谁点了按钮谁的数据就消失」。

## 影响范围

- 已合入（决策无关）：`apps/admin-web/src/views/review/ReviewList.vue`、`ReviewDetail.vue` 的状态文案与标签色；
  任何以 API 返回 `replaced` 的列表/详情渲染点。
- 未合入（绑 DEC-UX-001）：审核页 tab / 子筛选结构，即 replaced 的「可见去向」。
- 实测确认**不受影响**（仅观察，无需建单）：
  - 统计口径无误判风险——全仓只有 `mobile_service.py:275` 按 `Review.status == pending` 计数，不存在「非 approved 即打回」的排除式聚合，
    因此 replaced 不会污染打回率/待处理数。
  - `maintenance_service.py:509` 已把 replaced 列入「已完结状态」参与清理，后端生命周期完整。
- 数据现状（只读查询 `backend/data/news.db`）：`approved 53 / pending 28 / rejected 0 / replaced 0`。
  即当前还没有存量记录需要找回，修复窗口是干净的。

## 修复（绝对路径 + 改动点）

### 已合入 commit `450d0f1`（决策无关部分）

1. `D:\code\otherProjects\20_News\apps\admin-web\src\views\review\ReviewList.vue`
   `statusText()` / `statusTagType()` 各补 `replaced: '已替换'` / `replaced: 'info'`，并注明与 `WorkflowDetail.vue` 的 `REVIEW_STATUS_MAP` 同口径。
2. `D:\code\otherProjects\20_News\apps\admin-web\src\views\review\ReviewDetail.vue` 同上两处。
3. `D:\code\otherProjects\20_News\apps\admin-web\tests\helpers\mock.js`
   新增 `reviewReplacedListResponse` / `reviewReplacedDetailResponse` 两个第 4 态夹具。
4. `D:\code\otherProjects\20_News\apps\admin-web\tests\review-replaced-status.spec.js`（新增 3 例）
   锁一条决策无关的不变量：**渲染器绝不把枚举裸值当文案**（详情页直达 + 列表注入 replaced 行 + 既有 3 态不被破坏）。

### 备好待批（未合入，绑 DEC-UX-001）

5. `D:\code\otherProjects\20_News\_validate\news2\dec-ux-001-optionB.patch`（97 行新增，`git apply --check` 通过）
   方案 B 的完整实现 + 3 条 e2e：`ReviewList.vue` 增 `approvedSub` 子筛选（仅已通过 / 仅已替换）、
   `effectiveStatus()` 决定真正请求的 `status`、切 tab 时复位；**后端零改动**（`reviews.py:43` 的 status 是无校验等值过滤，`?status=replaced` 现在即可查）。
6. `D:\code\otherProjects\20_News\_validate\news2\dec-ux-001-brief.md` 决策简报：实测取证表、A/B/C 代价矩阵、B 的验证程度、一句话拍板方式。
7. 实拍图：`_validate/news2/dec-ux-001-optionB-approved.png`、`_validate/news2/dec-ux-001-optionB-replaced.png`（1440×900，子筛选已展开、行内显示「已替换」）。

## 验证（实测证据）

1. 新增 spec 通过：`PW_CHANNEL=chrome npx playwright test tests/review-replaced-status.spec.js` → **3 passed**。
2. **反向证明**（测试确实能抓到缺陷）：临时把 `ReviewList.vue` 的 `replaced: '已替换'` 撤掉 →
   `列表收到 replaced 行时状态列显示「已替换」` **1 failed**（`expect(locator).toBeVisible() failed`），随后已还原（`grep -c` 确认为 1）。
3. 提案补丁实测：`npx playwright test tests/review-replaced-subfilter.spec.js` → **4 passed**
   （默认不混入 replaced / 切「仅已替换」可见且中文 / 切走 tab 复位不外泄）。截图即该轮实拍。
4. 回归：`tests/review.spec.js + review-replaced-status + auto-review-guard + workflow.spec.js` → 28 passed / 1 failed，
   唯一失败 `review.spec.js:128 详情页展示采集图片并可放大预览` 是**既有失败**（同一断言在 T02500 全量跑的 4 条已知失败里，日志 `_validate/news2/t02500_e2e_full.log:1167`，由 T02628 跟踪），与本单改动无关（本单只改状态文案，不碰图片区）。
5. 构建：`npm run build` → ✓ built（含 T02500 的导航一致性门禁）。
6. 补丁可干净应用：`git apply --check --verbose _validate/news2/dec-ux-001-optionB.patch` 无错误后，工作树已还原（`git status` 对 review 相关文件为空）。

### 留待人工抽查（因此本单不标 verified）

- 子筛选在 1366×768 与移动端 `/m/review` 下的排版（本单只在 1440×900 实拍）。
- 「已替换」标签色 `info`（灰）与既有 `已打回`（红）的可辨识度是否符合运营预期。

## 本次回写

- 建派生单 **T02643**「【缺环境】【AI回写待审核】DEC-UX-001 拍板后实施 replaced 可见去向（推荐 B：合入 optionB 补丁）」，
  描述首行写明阻塞原因与依赖，含「若要求 approved+replaced 合并视图则需后端把 `status` 扩为多值 IN」这一条件范围。
- 本单标题加 **【缺环境】** 前缀、description 首行写 `⚠ 阻塞：DEC-UX-001 未拍板；依赖：A/B/C 三选一裁决`，
  保持 `status=todo, archived=false`——任务在待办列表可见但一眼可辨是等决策，不是漏做。
- 决策无关部分已以 commit `450d0f1` 独立合入，不随决策返工。

## 下一步建议

1. 拍板 DEC-UX-001（推荐 B），一句话即可；批准后 `git apply _validate/news2/dec-ux-001-optionB.patch` 并补跑回归（已建派生单 T02643）。
2. 若选 B 且要求「已通过 + 已替换」合并视图，需后端把 `status` 等值过滤扩为多值 `IN`（已并入 T02643 的条件范围，不另建单）。
3. 把审核状态字典收敛为单一来源（前端 3 处 `statusText` 复制是本次缺陷的土壤）——**不新建单**，属既有待办 **T02504**（FR-UX-405 枚举统一字典）范围。
4. 统计口径与清理链路经核对无 replaced 误判（仅观察不建单）。
