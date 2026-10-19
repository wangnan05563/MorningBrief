## 根因

T02503（[PRD] 4.4 关于页链接与版本修正 / FR-UX-404）下面其实是五个不同性质的缺陷，共同点是「**界面说的是事实，但事实源不成立**」：

1. **占位外链当成官方入口出厂**：`About.vue` 的 8 条链接里有 5 条是
   `https://example.com/...`（用户协议、隐私条款、联系我们、官方社区，外加一个写死的「API 文档」）。
   它们不是「以后会填」——从 V1 起没人填过，而门禁和测试都只查「站内路由是否存在」，
   对指向外部的字符串完全无感。
2. **`/docs` 是条件性存在的东西被当成恒在**：后端 `main.py:1371` 是
   `docs_url="/docs" if settings.is_dev else None`，生产环境根本没有这个路径；
   前端却在关于页和帮助页各写了一个无条件入口。
3. **检查更新的降级被渲染成成功**（M94）：后端 `_fetch_latest_release()` 只返回 `dict | None`，
   失败原因（未配仓库 / 无 release / 限流 / 网络 / 响应异常）在函数里就地丢弃，
   `_build_local_response()` 一律给 `has_update=false, source='local'`；
   前端 `performCheck()` 看到 `!has_update` 就显示绿色「已是最新」。
   于是「没查成」和「确实最新」在 UI 上不可区分，用户据此决定要不要升级。
4. **依赖版本清单是手抄的**（M101）：`About.vue` 的 `licenses` 数组手抄了 npm + pip 两份清单，
   升级只改 `package.json` / `requirements.txt`，没人回头改表——实测抄出来的 43 条里已经有 3 条是旧的
   （`edge-tts 6.1.10`、`pytest 8.0.0`、`pytest-asyncio 0.23.0`），另有 3 个真实依赖根本没抄进去
   （`python-multipart`、`slowapi`、`PyMuPDF`）。
5. **升级二次确认没有回归防线**：`dangerConfirm({confirmWord:'UPDATE'})` 代码在（M95 期落的），
   但没有任何用例证明「不输入确认词就不会发 POST /about/upgrade」——这类防线一旦回归就是
   误点一下直接替换程序并重启服务。

## 影响范围

- 关于页（`/about`）：链接区、检查更新按钮六态、开源声明 Modal；
- 帮助页（`/help`）：API 文档按钮与 `openApiDocs`、`id: 'about'` 章节文案；
- 后端 `/admin/api/v1/about`、`/about/check-update`：响应新增字段与降级语义；
- 构建门禁 `validate-nav.mjs`：新增两类检查，`npm run build` 口径变严；
- dev 代理：`/docs`、`/openapi.json` 与 `/news/*` 前缀两条链路都要打通，否则开发环境也看不到文档。

不影响：升级下载/替换的实际流程（`upgrade.py` 未改）、其他视图。

## 修复

**后端 —— 降级带原因，事实由服务端下发**

- [backend/app/routers/admin/about.py](file:///D:/code/otherProjects/20_News/backend/app/routers/admin/about.py)
  - `_fetch_latest_release()` 返回从 `dict | None` 改为 `tuple[dict | None, str]`，
    失败原因不再就地丢弃：404→`no_release`、403→`rate_limited`、非 200 / 缺 `tag_name`→`bad_response`、
    超时与 `HTTPError`→`network`，成功为 `(release, "")`；
  - 新增 `_UPDATE_REASON_TEXT`（4 个 reason → 用户可读文案），
    `_build_local_response(current, *, error=None, reason=None)` 同时下发 `reason`（机器判定）
    与 `error`（人读的一句话）；
  - 仓库未配置时显式 `_build_local_response(current, reason="repo_not_configured")`，
    不再靠「返回空」让前端猜；
  - `/about` 响应新增 `repo_url`（来自 settings.REPO_URL）与 `docs_enabled`（= `settings.is_dev`）
    ——把「这个链接该不该存在」从前端硬编码改成服务端事实。
- [backend/tests/test_about.py](file:///D:/code/otherProjects/20_News/backend/tests/test_about.py)
  7 处 `AsyncMock(return_value={...})` 改为 `({...}, "")` 元组；降级用例改
  `(None, "network")` 并断言 `data["reason"] == "network"`、`data["error"]`；
  新增 `test_check_update_repo_not_configured_reason`（`_REPO_URL=""` 时不发请求、reason 正确）、
  `test_get_about_exposes_link_source`（`repo_url` / `docs_enabled` 与 settings 一致）；
  5 个直连 `_fetch_latest_release` 的单测改为解包并逐模式断言 reason。

**前端 —— 链接由仓库派生、入口按实况显隐**

- [apps/admin-web/src/utils/links.js](file:///D:/code/otherProjects/20_News/apps/admin-web/src/utils/links.js)（新增）
  `API_DOCS_PATH = '/news/docs'` 与 `buildRepoLinks(repoUrl)`：
  非法/空地址返回 `[]`（宁可不显示也不给死链），三条派生链接为
  项目主页 = `base`、版本发布 = `base/releases`、报告问题 = `base/issues`
  （指向 issue 列表而非 `/issues/new`：后者需要登录，未登录会停在登录页）。
- [apps/admin-web/src/views/about/About.vue](file:///D:/code/otherProjects/20_News/apps/admin-web/src/views/about/About.vue)
  - 5 条占位外链**删除**（不是改名），`menuItems` 改为 `computed`：
    帮助文档 + 开源软件声明 + `buildRepoLinks(info.repo_url)` + 仅当 `docs_enabled` 才有的 API 文档；
  - `performCheck()` 先判 `res.source !== 'remote'` → 新终态 `unavailable`，
    显示 `res.error` 与重试按钮，**不再**把降级当「已是最新」；`_showLatest()` 抽出原重复的
    「3s 回 idle」计时器逻辑；模板新增 `.unavailable-row`（warning 色按钮 + 原因文案）与 scss；
  - `licenses` 表：3 条旧版本改对、补 3 个漏掉的依赖，头注释说明「版本号在构建期与两份清单比对」。
- [apps/admin-web/src/api/about.js](file:///D:/code/otherProjects/20_News/apps/admin-web/src/api/about.js)
  typedef 补 `repo_url` / `docs_enabled`，`UpdateCheckResult` 写清
  `source: local = 未能确认（不等于无更新）` 与 reason 枚举。
- [apps/admin-web/src/views/help/Help.vue](file:///D:/code/otherProjects/20_News/apps/admin-web/src/views/help/Help.vue)
  - API 文档按钮 `v-if="userStore.role === 'admin'"`（`/about` 是 admin 专属接口，运营点了只会得到权限错误）；
  - `openApiDocs()` 改为先 `getAbout()` 取 `docs_enabled`：未开放时 `ElMessage.info` 说明
    「仅开发环境挂载，接口清单见 docs/详细设计说明书.md」，取不到事实时
    `notifyErrorOnce` 而不是静默打开死链；
  - `id: 'about'` 章节的「核心功能/操作步骤」按现在的真实链接集合重写（旧文案还在说「8 项外部资源链接」）。
- [apps/admin-web/vite.config.js](file:///D:/code/otherProjects/20_News/apps/admin-web/vite.config.js)
  代理加 `/news/docs`、`/news/openapi.json`（剥 `/news` 前缀）与裸 `/docs`、`/openapi.json`
  （Swagger UI 按绝对路径取 spec，不剥前缀）。

**构建门禁 —— 两类新检查**

- [apps/admin-web/scripts/validate-nav.mjs](file:///D:/code/otherProjects/20_News/apps/admin-web/scripts/validate-nav.mjs)
  - `collectPlaceholderLinks()`：扫 `src/**/*.{vue,js}`，**只认链接位置**
    （`href="…"` / `href: '…'` / `window.open('…'`）里的 `example.com`。
    不做全文 grep 是有原因的：`CosConfig`、`Tunnel`、`NotificationConfig`、`Help` 里有
    4 处合法的示例域名（`placeholder="https://cdn.example.com"` 等），
    全文匹配会把门禁变成误报制造机，而误报的门禁等于没有门禁；
  - `checkDependencies()`：`readLicenseTable(About.vue)` ↔ `readNpmManifest()` ↔ `readPyManifest()`
    三向对账（幽灵依赖 / 漏声明 / 版本漂移），Python 包名按 PEP 503 归一
    （`PyMuPDF` ↔ `pymupdf`），`requirements.txt` 读不到时**只跳过**后端判定不失败
    （前端单独构建的环境里「无法对账」不是错误，谎报「依赖已移除」才是错误）；
  - `walk()` 支持扩展名参数，CLI 输出行增加「开源清单 43 项（npm 15 + pip 28）」，
    让「跑过」和「跑空」在日志上可区分。

## 验证

全部为实测证据，不是推断。

- `node scripts/validate-nav.mjs` → `路由 45 · 引导 27 · aria-label 117 · 分组 8 · 帮助章节 15 · 开源清单 43 项（npm 15 + pip 28）` → **通过**；
- `npm run test:nav` → **19 passed / 0 failed**（原 11 条 + 新增 8 条：对账一致不报错、
  幽灵依赖/漏声明/版本漂移三向报错、PyMuPDF 大小写不误报、后端清单缺失只跳过、
  重复条目与解析为空报错、占位外链报错、真实仓库 `placeholderLinks` 为空）；
- **门禁负向实测（它能失败）**：
  - 占位外链：临时放 `src/__gate_probe__/Probe.vue`（含 `href="https://example.com/terms"`、
    `href: 'https://example.com/privacy'`、`window.open('https://example.com/community'`）
    → 报 **3 条**，而同文件里的 `const placeholder = 'https://cdn.example.com'` **未**被误报；探针已删除；
  - 依赖对账：把 axios 改成 `^0.99.0` 并删掉 jieba 行 → 报 2 条
    （`axios 版本是 ^0.99.0，但 package.json 里是 ^1.6.0` / `requirements.txt 依赖 jieba（0.42.1）没有列入`），
    **exit=1**；从备份恢复后门禁重新通过，`git diff` 确认 About.vue 未被探针污染；
- `npm run build` → **✓ built in 3m 39s**（门禁以 `apply:'build'` 在 buildStart 真实生效）；
- 后端 `backend/.venv/Scripts/python.exe -m pytest tests/test_about.py -q` → **44 passed**（提交后复跑一次）；
- 新增 [apps/admin-web/tests/about-links.spec.js](file:///D:/code/otherProjects/20_News/apps/admin-web/tests/about-links.spec.js)
  → **9 passed**（`PW_CHANNEL=chrome npx playwright test tests/about-links.spec.js`）：
  1. 仓库已配置：三条派生外链出现，拦 `window.open` 记账断言 URL 恰为 `REPO` / `REPO/releases` / `REPO/issues`，
     整页文本不含 `example.com`，未开放文档时不提供 API 文档入口；
  2. 仓库未配置：三条整组隐藏（`toHaveCount(0)`）；
  3. `docs_enabled=true` 才出现入口且打开 `/news/docs`；
  4. **降级不谎报（M94）**：`source=local, reason=rate_limited` → 出现「无法确认，点击重试」
     与 `.update-hint` 原因文案，且「已是最新」按钮 `toHaveCount(0)`；
  5. `source=remote` 才显示「已是最新」；
  6. 升级二次确认：加载后 2s 内 `POST /about/upgrade` **未发出**；弹框含
     「当前版本 v1.0.20260921.003 → v9.9.9」「重启会中断进行中的工作流」「不支持在管理端内回滚」，
     不输入直接点「开始更新」提示「请逐字输入 UPDATE」且仍不发请求，填入 UPDATE 后请求才发出；
  7. 帮助页：运营角色无 API 文档按钮；`docs_enabled=false` 时点击只出提示、`window.open` 调用数为 0；
     `docs_enabled=true` 时才真的打开 `/news/docs`。
- 全量 e2e `PW_CHANNEL=chrome npx playwright test` → **152 passed / 3 failed（10.8m）**。
  3 条失败全部是 `page-layout-padding.spec.js:43` 的三个素材页内边距（讲书稿素材池 / 素材库管理 / 素材录入），
  与 T02628 记录的存量失败同一批（该单还记了第 4 条 `review.spec.js:128` 采集图片预览，本轮已通过）。
  本单**零新增失败**：改动面在关于页/帮助页/门禁/dev 代理，与素材页样式无交集。
- 外链存在性用 `api.github.com` 核对（本环境 `github.com` 页面 HTML 与 `raw.githubusercontent.com` 不可达）：
  `full_name=wangnan05563/MorningBrief`、`has_issues=true`、`default_branch=main`、
  `releases/latest` 有正式 release；`README.md` 远端与本地**逐字节相同**（8839 字节、含「风险免责」小节），
  故页脚 tooltip 的指向成立——上一轮「远端 README 是 55 字节截断桩」的判断是被沙箱网络误导的**误报**，
  本轮已用 contents API 证伪，不为此建单。

**验证缺口（诚实标注）**：三条外链的真实 HTTP 200 探活在本环境做不了（只证到了 API 元数据层面），
已建 T02689 交给能访问外网页面 HTML 的环境；GitHub 页面打开后的视觉与登录态跳转未实测。

## 本次回写

- [T02689] 【缺环境】关于页三条外链需在有外网的环境做 HTTP 200 探活 —— 门禁与 e2e 只能证明
  「URL 派生正确、无占位符」，200 探活需要外网可达的执行环境；
- [T02690] 【缺环境】用户协议/隐私条款正文缺失，关于页政策类入口待产品决定 ——
  占位外链删除后暴露的真实缺口，是否要政策文本、放站内还是配置下发属产品决策，不由前端代答；
- [T02691] 开源许可清单改为脚本自动生成，去掉 `About.vue` 手抄表 —— 本轮只做到「手抄 + 机器对账」，
  自动生成才能消除手抄本身。

提交：`9a7c75d`（前后端 + 门禁 10 files changed, +786/-128）；
测试与留痕文档随本单第二次提交。并发会话的 WIP（`api/audio.js`、
`CourseMaterials.vue`、根 `package.json`、`backend/VERSION`、`_build_info.py`、`workflow/llm/*`）
用 path-limited commit 排除在外，提交后 `git status` 复核仍在工作区。

## 下一步建议

- T02689 / T02690 / T02691 已建单（见上），分别对应外链探活、政策文本决策、清单自动生成三条后续动作；
- 门禁的下一步是把 `checkDependencies` 与占位外链检查接进 `guide-anchor-audit` 那类「强制检查点」，
  与既有 T02636（引导锚点审计接入强制卡点）同一口径推进，不另建单；
- 关于页 `unavailable` 态的文案是否要按 reason 分支给不同动作（限流→「稍后自动重试」，
  未配仓库→给 REPO_URL 配置入口），属文案与交互取舍，本轮保持「原因 + 重试」最小实现（仅观察不建单）。

**人工抽查步骤（本单 verified=false 的原因）**：

1. 在能访问 GitHub 页面的机器上，从管理端关于页依次点开「项目主页 / 版本发布 / 报告问题」，
   确认三条都是 200 且落在预期页面（`/issues` 应是列表而非新建 issue 的登录墙）；
2. 把 `backend/.env` 的 `REPO_URL` 临时置空重启一次：三条外链应整组消失，
   检查更新显示「未配置代码仓库地址（REPO_URL），已跳过更新检查」，且**不显示**「已是最新」；
3. 在 `APP_ENV=production` 下打开帮助页点「API 文档」：应显示「当前环境未开放交互式 API 文档…」的提示，
   浏览器不该新开一个 404 标签页。
