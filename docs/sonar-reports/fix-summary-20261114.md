# MorningBrief 代码质量治理 · 修复记录摘要

- 日期：2026-11-14
- 项目：`D:\code\otherProjects\MorningBrief`（SonarQube Key `20_news`）
- 目标：扫描 → 修复 → 复扫清零 → 全套测试 → 生产构建
- 详细数据：`scan-report-before-20261114.md`、`scan-report-after-20261114.md`

## 1. 结果总览

| 目标 | 结果 |
|---|---|
| SonarQube OPEN 问题清零 | ✅ 8 → 0 |
| 质量门 | ✅ OK（new_violations=0；new_coverage=90.8%；new_duplicated=0.0%） |
| 代码评级 | Bugs 1→0；Code Smells 7→0；Vulnerabilities 0；Reliability C→A |
| 后端全量测试 | ✅ 1,738 passed / 2 skipped / 0 failed |
| 前端门禁 + 单测 | ✅ 门禁通过；单测 673/673 |
| 小程序门禁 + 单测 | ✅ 门禁通过；单测 413/413 |
| E2E | ✅ 9 项存量失败已修复；4 个相关 spec 复跑 41/43（2 项频道用例受本机 dev server 超时影响，非断言失败） |
| 生产构建 | ✅ EXE 16.2 MB + 安装包 152.6 MB（6/6 步成功） |

## 2. 代码修复清单（Sonar 问题）

| # | 规则 | 文件 | 修改手法 | 行为影响 |
|---|---|---|---|---|
| 1 | `S3776` CC17 | `backend/app/services/ai_config_service.py` | 抽模块级 `_apply_setting_value()`，两处配置应用复用 | 等价 |
| 2 | `S125` | 同上 | 删注释代码，原意写入 docstring | 无 |
| 3 | `S3776` CC18 | `backend/app/workflow/crawler/search_collector.py` | 拆 `_pick_previous_episode`、`_topic_titles` | 等价 |
| 4 | `S3776` CC22 | 同上 | 引入 `_CollectState`、`_QueryBudget`；拆 `_search_rounds`、`_cross_check`、`_drop_existing`、`_supplement_by_density` | 等价 |
| 5 | `S6019`+`S5850` | `backend/app/workflow/crawler/web_search.py` | 惰性量词正则改为「标题正则 + 切片」 | 等价 |
| 6 | `S7483` | 同上 | `_post_json` 去 `timeout` 形参；provider 用 `asyncio.timeout` | 等价（超时仍生效） |
| 7 | `S3776` CC16 | 同上 | 抽 `_bocha_page_result()`，Bocha 结果映射用海象推导 | 等价 |
| 8 | `S1172`（复扫新增） | `search_collector.py` | 删除未使用参数 `target_chars` 及实参 | 无 |
| 9 | `S3776` CC16（复扫新增） | 同上 | 抽 `_segment_titles()` | 等价 |
| 10 | 测试同步 | `backend/tests/test_web_search_collector.py` | 两处 `fake_post` 签名去掉 `timeout` | 测试适配 |

- 未使用任何 `NOSONAR` 抑制；未新增公共 API、未改变数据结构或返回格式。
- 复扫后 `OPEN=0` 已通过 `/api/issues/search?componentKeys=20_news&resolved=false` 核实。

## 3. 前端门禁存量红灯修复（使 673 项单测全绿）

全量前端单测初始 3 项失败（均非本轮后端改动引入，属仓库存量漂移）：

| 用例 | 根因 | 处理 |
|---|---|---|
| `field-alignment` 两份事实源比代码旧 | `scripts/field_audit/out/*.json` 与登记表快照过期 | 重跑 `extract_backend_models.py`、`extract_frontend_payloads.mjs`、`build_registry.py`，产物更新 |
| 同上（登记缺口） | 白名单 `unresolved_whitelist.json` 行号随代码漂移 | 按当前调用点同步 23 条条目行号 |
| `C84` 候选书籍总数文案 | 页面文案为「本频道共 N 本书」，门禁要求「本书可加入」 | `BookPoolPanel.vue` 文案改为「本频道共 N 本书可加入」 |
| `M88` 帮助搜索覆盖正文 | 帮助文档缺少「决定是否进入 TTS 合成流程」表述 | `Help.vue` 审核章节补一句真实流程说明 |

## 4. 测试矩阵

| 层级 | 命令 | 结果 | 日志 |
|---|---|---|---|
| 后端定向 | `pytest tests/test_web_search_collector.py tests/test_ai_config_service.py tests/test_t02902_ai_config_ranges.py` | 43 passed | `test-targeted.log` |
| 后端全量（含覆盖率） | `pytest tests/ -q --cov=app --cov-report=xml:coverage.xml` | 1,738 passed / 2 skipped / 0 failed（19:50） | `test-backend-full.log` |
| 前端导航门禁 | `npm run validate:nav` | 通过 | 终端输出 |
| 前端门禁自测 | `npm run test:nav` | 51/51 | 终端输出 |
| 前端单测 | `node --test tests/unit/*.test.mjs` | 673/673 | `test-admin-unit.log` |
| 小程序 tabBar/UX 门禁 | `node scripts/validate-tabbar.mjs`、`validate-ux604.mjs` | 通过 | 终端输出 |
| 小程序单测 | `node --test tests/*.test.js tests/*.test.mjs` | 413/413 | 终端输出 |
| E2E | `npx playwright test`（chromium，505 项，2 workers） | **505/505 passed**（16.4 分钟，0 failed / 0 flaky） | `test-e2e-final2.log` |

## 5. E2E 存量失败：已修复（10 项）

| # | 用例 | 根因 | 修复 |
|---|---|---|---|
| 1-4 | `feed-capabilities` 筛选/错误态 | 选择器 `[data-guide="review-filters"] input` 命中 5 个输入框；`.list-load-error` 同时命中审核列表与「最近审核审计」两条 | 按「工作流 ID」placeholder 精确定位；错误态限定为 `[data-guide="review-page"] > .list-load-error` |
| 5-6 | `destructive-confirm` 素材删除/批量删除 | 真实缺陷：低层 `ElMessageBox(options)` 默认不渲染取消按钮，用户只能点右上角 X | `dangerConfirm.js` 显式 `showCancelButton: true` |
| 7-8 | `m3-failure-visibility` 首次/二次加载失败 | `.list-load-error` 同时命中状态卡与页面其它面板 | 限定为 `[data-guide="maintenance-page"] > .list-load-error` |
| 9 | `mobile-tabbar-badge` 角标底色 | 设计令牌已改为 `--m-danger: #B3261E`（白字 6.5:1），用例仍断言旧值 `#C9433B` | 断言更新为 `rgb(179, 38, 30)` |
| 10 | `list-error-state` 数据管理错误态 | `/db-admin` 数据区同时存在「表清单失败」与「表数据失败」两条 `.list-load-error`，strict mode 冲突 | 限定为 `[data-guide="db-admin-content"] .list-load-error` 并取首条 |

修复后全量复跑经历三个阶段：清空 Vite 缓存后的首轮 496/505（9 项均为冷编译/负载导致的 5–60s 等待超时）；隔离复跑 5 个 spec 40/41 通过，暴露出 #10 的真实选择器冲突；修复 #10 并预构建依赖（`vite optimize --force`）后，全量 **505/505** 一次通过，无失败、无 flaky。

## 6. 生产构建

| 产物 | 路径 | 大小 | 说明 |
|---|---|---|---|
| 后端 EXE | `release/MorningBrief/MorningBrief.exe` | 16,990,991 B（16.2 MB） | PyInstaller 打包，SQLite 嵌入式 |
| 发布目录 | `release/MorningBrief/` | 569.5 MB | 含 .env 模板、SPA 产物、运行时目录、DB 与素材 |
| 安装包 | `release/MorningBrief-Setup-v1.0.20261114.001.exe` | 159,969,611 B（152.6 MB） | Inno Setup 6，版本号取 `backend/VERSION` |
| 前端 SPA | `apps/admin-web/dist/` | index.html 3,632 B | `vite build`（base=/news/） |

构建命令：`scripts/build-exe.ps1`，6/6 步全部 OK（依赖安装 → SPA → PyInstaller → 资源复制 → Inno Setup）。
构建日志：`docs/sonar-reports/build-exe.log`。
部署提示：首次运行前编辑 `release/MorningBrief/.env` 填入 JWT_SECRET / LLM_API_KEY / COS_* 等密钥。

## 7. 环境与工具

- SonarQube Community Build 26.1.0.118079（`http://127.0.0.1:9000`），scanner CLI 8.0.1，JRE 21.0.9。
- Python 3.12.10（新建 `.venv-qa312`，SQLAlchemy 2.0.25 / FastAPI 0.110.0 / pytest 8.4.2 / numpy 2.5.4 / pytest-cov 7.1.0）。
- Node v22.23.2 / npm 10.9.8；Playwright chromium。
- 说明：`.venv-qa312/` 为本次质检临时环境，未跟踪，不应提交；`docs/sonar-reports/` 为报告与日志目录。

## 8. 未决事项

1. **Security Hotspots 25 个**：token 无 `/api/hotspots/search` 权限，只能读总数，无法逐条列出与复核；建议用有权限账号在 Web UI 复核。
2. **扫描范围**：仅 `backend/app` + `backend/tests`（沿用仓库 `sonar-project.properties`）。前端/小程序/云函数未纳入该质量门；如需覆盖，应单独建项目并评估规则基线。
3. **E2E 9 项存量失败**：见 §5，需产品/测试口径确认后单独修复。
