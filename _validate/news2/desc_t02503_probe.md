来源：T02503（关于页外链与更新态可信 / FR-UX-404 / ACC-UX-401）

⚠ 阻塞：本环境无法访问 GitHub 页面 HTML（`api.github.com` 返回 200，`github.com`/`raw.githubusercontent.com` 全部不可达）；依赖：一台可以正常打开外网页面的执行环境。

## 为什么要这一单

ACC-UX-401 的口径是「关于页所有外链可达（HTTP 200 或站内路由存在），无 `example.com`」。
T02503 已经做到的部分：

- 占位外链归零：`apps/admin-web/scripts/validate-nav.mjs` 新增「链接位置占位外链」门禁，
  视图里 `href="…"` / `href: '…'` / `window.open('…')` 出现 `example.com` 直接构建失败；
  负向实测：临时塞一个 `Probe.vue` 即报 3 条（模板属性 / 对象字面量 / window.open），
  而 `placeholder="https://cdn.example.com"` 与帮助正文里的示例域名不误报。
- URL 派生正确：`apps/admin-web/tests/about-links.spec.js` 拦 `window.open` 记账，
  断言三条外链是 `REPO` / `REPO/releases` / `REPO/issues`。
- 元数据存在性：用 `api.github.com` 核对过仓库存在（`full_name=wangnan05563/MorningBrief`、
  `has_issues=true`、`default_branch=main`）、`releases/latest` 有正式 release。

**没有做到的部分（本单要补的）**：真实 HTTP 200 探活。
「仓库有 issues 开关」不等于「`/issues` 页面能打开」，「有 latest release」也不等于
「`/releases` 页面 200」。这类偏差只有能访问页面 HTML 的环境能证。

## 要做什么

1. 在有外网的环境跑一次三条外链探活（命令示意）：
   ```
   for u in "https://github.com/wangnan05563/MorningBrief" \
            "https://github.com/wangnan05563/MorningBrief/releases" \
            "https://github.com/wangnan05563/MorningBrief/issues"; do
     printf "%s -> %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' -L "$u")"
   done
   ```
   三条都应是 200；出现 404/451 说明仓库可见性或功能开关与假设不符，需要回头改
   `apps/admin-web/src/utils/links.js` 的派生规则（而不是改断言）。
2. 顺手点开帮助页 `/help` 的「API 文档」按钮：在开发环境（`APP_ENV=development`）应真的打开
   `/news/docs` 并渲染 Swagger UI；在生产环境应显示「当前环境未开放交互式 API 文档」的提示。
3. 结论写回本单 result，附探活输出。

## 验收

- 三条外链 200 的实测记录（或修复派生规则的提交号）；
- 帮助页 API 文档入口在开发/生产两种 `APP_ENV` 下的行为各一张截图或一段文本证据。
