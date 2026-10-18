⚠ 阻塞：DEC-UX-001（审核第 4 态 replaced 的呈现方式）尚未拍板；依赖：需求方在 A/B/C 三选项中裁决，推荐 B。

来源：T02501（FR-UX-402 审核状态口径）

## 待办内容

决策无关的文案缺陷已在 commit `450d0f1` 修掉（`ReviewList.vue` / `ReviewDetail.vue` 补齐 `replaced: '已替换'`，
与 `WorkflowDetail.vue` 的 `REVIEW_STATUS_MAP` 同口径，并配 3 例 e2e）。
本单只剩「**可见去向**」——目前审核页只有 3 个 tab，`loadList()` 的 `status` 恒等于当前 tab，
所以 `replaced` 记录一旦产生就在列表里永久查不到（详情页可直达但没人知道 id）。

## 已备好的东西（批准即合入，不必再写代码）

- 决策简报：`_validate/news2/dec-ux-001-brief.md`（实测取证表 + A/B/C 代价矩阵 + 一句话拍板方式）
- 方案 B 补丁：`_validate/news2/dec-ux-001-optionB.patch`（97 行新增，含 3 条 e2e；`git apply --check` 通过）
  合入命令：`cd D:/code/otherProjects/20_News && git apply _validate/news2/dec-ux-001-optionB.patch`
- 实拍图：`_validate/news2/dec-ux-001-optionB-approved.png` / `-replaced.png`（1440×900）
- 补丁实测记录：`PW_CHANNEL=chrome npx playwright test tests/review-replaced-subfilter.spec.js` → 4 passed（补丁已在工作树试跑并跑通后还原）

## 若选 B 的条件范围（需要时一并做）

子筛选当前是单选（仅已通过 / 仅已替换），因为后端 `status` 是无校验等值过滤
（`backend/app/routers/admin/reviews.py:43` + `review_service.py:64`），单参数无法一次返回 approved+replaced。
若产品要求「已通过（含已替换）」合并视图，需把 `status` 扩为多值 `IN`（后端改动，前端同批传数组）。

## 验证要求

合入后补跑：`tests/review-replaced-subfilter.spec.js`、`tests/review.spec.js`、`npm run build`；
人工抽查 1366×768 与 `/m/review` 下子筛选排版。
