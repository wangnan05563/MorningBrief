来源：T02506（FR-UX-501 指标单位元数据）。本单把「单位口径」改成了后端唯一真源 +
展示端按 meta 渲染，但没有任何机制阻止下一个页面重新写死一份 `(分钟)` / `*100`——
这正是本次漂移的成因，和 T02504 之前「枚举文案各抄一份」是同一类问题。
T02504 已给枚举建了构建期门禁，本单给「单位」补同一条。

## 现状（实测）
- 门禁 `apps/admin-web/scripts/validate-nav.mjs` 现有能力：路由/引导/图标/依赖/枚举字典对账
  （`checkEnums` + `collectEnumDuplicates`，T02504 落地），完全不认识「单位」这件事。
- 本单改完后仍然存在的硬编码点（未被本单覆盖，见派生单「其余统计接口纳入单位元数据表」）：
  `apps/admin-web/src/views/system/AutoReviewConfig.vue:547`（`(rate*100).toFixed(1)+'%'`）、
  `:552-553`（自写秒/分换算）、`apps/admin-web/src/views/stats/LlmMetrics.vue:42`（`{{ r.value }}%`）、
  `apps/admin-web/src/views/mobile/ManageUsers.vue:28`（`次`/`秒` 后缀）。
- 参照对照：`apps/admin-web/src/views/stats/StatsOverview.vue` 与 `views/mobile/Home.vue`
  已不含任何单位字面量，全部走 `utils/format.js` 的 `metricLabel / metricValue`。

## 建议做法
1. 在 `validate-nav.mjs` 增加 `checkMetricUnits(f)`：扫描 `src/views/**`（排除
   `src/utils/format.js`），命中以下模式即报错并给出 `文件:行`：
   - 模板/脚本里出现 `(分钟)`、`(分)`、`(%)`、`(秒)`、`(次)` 形式、且同一文件里没有
     `metricLabel/metricValue` 调用（说明是硬编码而非渲染 meta）；
   - `* 100` 与 `%` 拼接出现在同一表达式（`(x*100)+'%'` 一类）；
   - `Math.floor(... / 60)`、`... % 60` 出现在 admin-web 视图里（时长换算应集中）。
2. 报错文案要给出修法指向：「改用 utils/format.js 的 metricValue + 接口 meta」。
3. 与枚举检查同样保留 skip 语义：字典/接口元数据文件读不到时打印跳过说明，不假装通过。
4. 存量违规先清（见另一张派生单）再接门禁，否则门禁上线即红灯；
   可以在实现时用 `--force`/白名单常量临时豁免，但白名单必须逐条写文件:行并注明原因。

## 验收口径
- `npm run validate:nav` 通过；
- 反证一：临时在某个视图写 `label: '平均收听(分钟)'` 且不 import format → 门禁报错 exit=1；
- 反证二：写 `(v * 100).toFixed(1) + '%'` → 门禁报错 exit=1；
- 反证删掉探测文件后 `node --test apps/admin-web/scripts/validate-nav.test.mjs` 全绿，
  并新增 ≥3 条 fixture 用例覆盖上述两类命中与「已走 meta 不误报」。
