# DEC-UX-001 决策简报：审核第 4 态 `replaced` 怎么呈现

> 目的：把「拍板」的成本降到一句话。下面三选项的代价、可行性、已验证程度全部实测过，不是纸面推演。
> 结论先行：**推荐 B（并入「已通过」加子筛选）**，且 B 的前端改动已经写完、跑通、留成补丁 `_validate/news2/dec-ux-001-optionB.patch`，批准即 `git apply`。

## 1. 实测取证（2026-10-18）

| 事实 | 证据 |
|---|---|
| 后端确实有第 4 态 | `backend/app/models/review.py:17` `ReviewStatus.replaced`，并有 `CheckConstraint` 锁死 4 值 |
| 该状态由真实动作产生，且入口一步可达 | `review_service.py:269`（`action == "replace"`）；UI 入口 `ReviewDetail.vue:112` 的 `el-radio value="replace"`（「替换段落」） |
| 当前生产库里 `replaced` 有 0 行 | 只读查询 `backend/data/news.db`：`approved 53 / pending 28`，`rejected`、`replaced` 均为 0 |
| 但列表页**完全查不到** replaced | `ReviewList.vue` 只有 3 个 tab，`loadList()` 的 `status` 恒等于当前 tab，没有第 4 个入口 → 一旦有人点「替换段落」，这条记录立刻从界面上消失 |
| 详情页会把枚举裸值当文案 | 修复前 `statusText()` 只有 3 态，走 `\|\| status` 兜底 → 显示英文 `replaced`（已在 `450d0f1` 补齐为「已替换」） |
| 后端**零改动**就能按 replaced 查询 | `routers/admin/reviews.py:43` 的 `status` 是无校验等值参数，`review_service.py:64` 直接 `Review.status == status` → `?status=replaced` 现在就能返回数据 |
| 「已通过 + 已替换」合并成一个视图**需要后端改** | 同上，等值过滤无法一次返回两个状态，必须扩成多值 `IN` |

数据补充：`replaced` 目前 0 行不代表风险为 0——它只说明「还没人用过这个按钮」。文案缺陷（英文裸值）已经修掉了；剩下的是**可见去向**，也就是本决策要拍的。

## 2. 三选项代价对比

| 选项 | 前端改动 | 后端改动 | 与 SRS 三栏的关系 | 已验证程度 |
|---|---|---|---|---|
| A. 第 4 个 tab「已替换」 | 加 1 个 `el-tab-pane` | 无 | **冲突**：SRS 定义审核页是「待审核/已通过/已打回」三栏，PRD 明确把「避免与 SRS 三栏冲突」列为约束 | 未实现（按 PRD 倾向不推荐） |
| **B. 并入「已通过」加子筛选（PRD 推荐）** | 已通过 tab 下加「仅已通过 / 仅已替换」单选组，`loadList` 用子筛选值决定 `status` | **无** | 三栏不变，第 4 态作为「已通过」组内的完结子态 | **已实现并实测通过**，见下 |
| C. 并入「已打回」 | 同 B 量级 | 无（但语义上把「替换」当打回，`rejected` 的 reason 语义与统计口径会失真） | 三栏不变 | 未实现；语义代价最高，且会污染「打回率」类统计 |

B 的一个已知取舍（拍板时请一并确认）：子筛选是**单选**，默认「仅已通过」，因此不存在「approved + replaced 合并列表」视图——那需要后端把 `status` 扩成多值 `IN`。当前补丁刻意没做合并视图，避免在未拍板时改动后端。

## 3. B 方案已验证到什么程度

- 补丁：`_validate/news2/dec-ux-001-optionB.patch`（97 行新增，含实现 + 3 条 e2e；`git apply --check` 通过，未合入主干）
- 实测：`PW_CHANNEL=chrome npx playwright test tests/review-replaced-subfilter.spec.js` → **4 passed**
  - 「已通过」tab 出现子筛选，默认仍只看 approved（不会把 replaced 混进已通过）
  - 切「仅已替换」→ `wf-005` 行可见、状态列显示「已替换」、页面无裸枚举
  - 切走 tab 子筛选复位，`status` 回到 `pending`，不会把 replaced 泄漏到其他 tab
- 实拍图（1440×900，mock 数据）：
  - `_validate/news2/dec-ux-001-optionB-approved.png`
  - `_validate/news2/dec-ux-001-optionB-replaced.png`

## 4. 拍板方式

一句话即可，例如「按 B 合入 optionB 补丁」。合入动作：

```bash
cd D:/code/otherProjects/20_News && git apply _validate/news2/dec-ux-001-optionB.patch
```

若选 A 或 C，本简报的第 2 节代价矩阵仍然适用（A 纯前端、C 需接受打回统计语义失真）；B 的补丁不浪费，`effectiveStatus()` 那层抽象可原样复用为 tab→status 映射。
