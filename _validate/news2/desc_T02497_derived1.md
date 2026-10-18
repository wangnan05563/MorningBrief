来源：T02497（FR-UX-303 提示去重）——本单跑全量 e2e 时暴露，已用 git worktree 在基线提交 0808419 复跑确认为既有缺陷，不是提示层改动引入的。

失败清单（PW_CHANNEL=chrome npx playwright test tests/page-layout-padding.spec.js tests/review.spec.js）：
1. page-layout-padding.spec.js:43「素材库管理：内容卡片不贴边」→ 左侧实测 16px，断言要求 ≥22px（.page-container 的 24px 留 2px 容差）。
2. page-layout-padding.spec.js:43「素材录入：内容卡片不贴边」→ 同样 16px。
3. page-layout-padding.spec.js:43「讲书稿素材池：内容卡片不贴边」→ 同样 16px。
4. review.spec.js:128「详情页展示采集图片并可放大预览」→ .image-grid .el-image__preview 期望 2 个，实测 0 个（el-image 未渲染出预览缩略图；基线复跑时同一条 page-layout-padding 的「不得出现空卡片 body 占位」3 条也一起失败，共 7 条）。

注意：MaterialLibrary.vue / CourseMaterials.vue 在 HEAD~3 与工作区都带 page-container 类（grep 计数一致 2 次），所以问题不在类名缺失，更可能是外层 .main-content 的 padding 被覆盖、或这些页面把卡片放在了 page-container 之外的容器里。先用/devtools 量一下实际生效样式再决定改哪层，不要盲目加 !important（见 references/pitfalls.md 的 CSS 守卫）。

验收：全站 e2e 恢复到 0 失败，可作为合并门禁。
