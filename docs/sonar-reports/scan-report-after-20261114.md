# MorningBrief SonarQube 扫描报告（修复后复扫）

- 生成时间：2026-11-14 19:37（UTC+8）
- 项目：MorningBrief（`20 News`）· Key `20_news`
- 服务：SonarQube Community Build 26.1.0.118079
- 复扫 CE 任务：`a2e6b246-5f0e-4270-b677-33858fba67e4`（SUCCESS）
- 日志：`docs/sonar-reports/scan-after-fix.log`（第 1 次复扫）、`docs/sonar-reports/scan-after-fix2.log`（最终复扫，含覆盖率）
- 覆盖率报告：`backend/coverage.xml`（Cobertura，pytest-cov 生成，1,738 用例）

## 1. 复扫结论

| 校验项 | 结果 |
|---|---|
| `/api/issues/search?componentKeys=20_news&resolved=false` | **total = 0** |
| Bugs | **0**（基线 1） |
| Code Smells | **0**（基线 7） |
| Vulnerabilities | **0** |
| 质量门 | **OK**（`new_violations=0`、`new_coverage=90.8% ≥ 80%`、`new_duplicated_lines_density=0.0% ≤ 3%`） |
| 可靠性评级 | 3.0(C) → **1.0(A)** |
| 安全评级 | 1.0(A)（保持） |
| 可维护性评级 | 1.0(A)（保持） |
| 技术债 | 53min → **0min** |
| 认知复杂度合计 | 5,789 → **5,766** |
| ncloc | 32,979 → 33,039（拆分函数带来的 docstring/结构行） |
| 覆盖率 | 0.0% → **67.5%**（新代码 90.8%） |
| 重复行密度 | 0.6%（未变化） |
| Security Hotspots | 25（未变化；明细仍因权限不足无法读取） |

## 2. 修复过程（两轮复扫）

| 轮次 | OPEN 数 | 说明 |
|---|---|---|
| 基线 | 8 | 4 CRITICAL + 4 MAJOR（含 1 BUG） |
| 第 1 次复扫 | 2 | 原 8 项全部消失；拆分后新暴露 2 项：`S3776`（`_topic_titles` CC 16）、`S1172`（`_supplement_by_density` 未使用参数 `target_chars`） |
| 最终复扫 | **0** | 上述 2 项修复，质量门 OK |

> 第 1 次复扫暴露的 2 项不是「新引入违规」，而是拆分出的函数仍超阈值 / 拆分后遗留参数；均按代码修复处理，未使用任何 `NOSONAR` 抑制。

## 3. 逐项修复明细

| # | 规则 | 文件:基线行 | 处理 |
|---|---|---|---|
| 1 | `S3776` | `ai_config_service.py:1033`（CC 17） | 抽模块级 `_apply_setting_value(settings, key, value)`，`apply_config_to_settings` 复用，CC 降至约 3 |
| 2 | `S125` | `ai_config_service.py:1049` | 删除注释代码；原意（`llm_base_url` 存量值削平）写进方法 docstring |
| 3 | `S3776` | `search_collector.py:103`（CC 18） | 拆 `_pick_previous_episode` / `_topic_titles`，`_load_previous_topics` CC 约 2 |
| 4 | `S3776` | `search_collector.py:305`（CC 22） | 引入 `_CollectState`、`_QueryBudget`，拆 `_search_rounds` / `_cross_check` / `_drop_existing` / `_supplement_by_density`，主函数 CC 降至约 12–14 |
| 5 | `S6019` + `S5850` | `web_search.py:78` | 用 `_SUBSECTION_HEADING_RE` + `_NEXT_H2_HEADING_RE` + 字符串切片替代惰性量词与歧义分组正则 |
| 6 | `S7483` | `web_search.py:224` | `_post_json` 去掉 `timeout` 形参（`httpx.AsyncClient(timeout=None)`），provider 内用 `async with asyncio.timeout(self._timeout)` |
| 7 | `S3776` | `web_search.py:250`（CC 16） | 抽 `_bocha_page_result(page)`，`BochaProvider.search` 改为海象表达式列表推导，CC 约 3 |
| 8 | `S1172`（复扫新增） | `search_collector.py:411` | 删除未使用参数 `target_chars` 及调用实参 |
| 9 | `S3776`（复扫新增） | `search_collector.py:147`（CC 16） | 抽 `_segment_titles(segments)`，`_topic_titles` CC 约 2 |

改动文件（4 个）：

- `backend/app/services/ai_config_service.py`
- `backend/app/workflow/crawler/search_collector.py`
- `backend/app/workflow/crawler/web_search.py`
- `backend/tests/test_web_search_collector.py`（两处 `fake_post` 签名随 `_post_json` 变更同步）

所有改动保持行为等价：仅函数拆分、正则等价改写、超时控制方式替换；未新增公共 API、未改变返回结构。

## 4. 复核证据

### 4.1 问题清零

```
GET /api/issues/search?componentKeys=20_news&resolved=false&ps=100
total = 0
```

### 4.2 质量门

```
GET /api/qualitygates/project_status?projectKey=20_news
status = OK
new_coverage                    90.8  (LT 80 → OK)
new_duplicated_lines_density     0.0  (GT 3  → OK)
new_violations                   0    (GT 0  → OK)
```

### 4.3 覆盖率口径说明

- 复扫通过 `-Dsonar.python.coverage.reportPaths=backend/coverage.xml` 引入覆盖率，未改动受版本控制的 `sonar-project.properties`。
- 全量 1,738 个后端用例产生的总体行覆盖率 67.5%；本次改动新增/修改行覆盖率 90.8%，满足 Sonar way 的 80% 新代码门槛。

## 5. 测试与构建（同一代码快照）

| 环节 | 命令 | 结果 |
|---|---|---|
| 后端全量单测/集成 | `backend: .venv-qa312\Scripts\python -m pytest tests/ -q --cov=app` | **1,738 passed，2 skipped，0 failed**（19m50s） |
| 后端定向回归 | `pytest tests/test_web_search_collector.py tests/test_ai_config_service.py tests/test_t02902_ai_config_ranges.py` | 43 passed（修复后再次 27 passed） |
| 前端门禁 | `npm run validate:nav` / `npm run test:nav` | 通过（46 路由 / 27 页 / 133 aria-label）；51/51 |
| 前端单测 | `node --test tests/unit/*.test.mjs` | **673 passed，0 failed** |
| 小程序门禁 | `node scripts/validate-tabbar.mjs` / `validate-ux604.mjs` | 通过（tabBar 3 项 / 交叉比对 41 文件） |
| 小程序单测 | `node --test tests/*.test.js tests/*.test.mjs` | **413 passed，0 failed** |
| E2E | `npx playwright test` | 见 §6 |

## 6. E2E 与生产构建

### 6.1 E2E

- 最终全量：**505/505 passed**（2 workers，16.4 分钟，0 failed / 0 flaky）。
- 修复对象：9 项存量失败 + 1 项全量复跑中暴露的选择器冲突（`/db-admin` 两条 `.list-load-error`），其中 1 项为真实缺陷（低层 `ElMessageBox(options)` 不渲染「取消」按钮），其余为用例选择器/颜色断言过期。
- 过程：清空 Vite 缓存后的首轮 496/505（9 项均为冷编译/负载超时）；隔离复跑 40/41；修复 `/db-admin` 用例并执行 `vite optimize --force` 预构建后，全量一次通过。

### 6.2 生产构建

命令：`scripts/build-exe.ps1`，6/6 步全部 OK（依赖 → SPA → PyInstaller → 资源 → Inno Setup）。

| 产物 | 路径 | 大小 | 时间 |
|---|---|---|---|
| 前端 SPA | `apps/admin-web/dist/` | — | 19:46 |
| 后端 EXE | `release/MorningBrief/MorningBrief.exe` | 16,990,991 B | 19:51 |
| 发布目录 | `release/MorningBrief/` | 569.5 MB | 19:52 |
| 安装包 | `release/MorningBrief-Setup-v1.0.20261114.001.exe` | 159,969,611 B | 19:54 |

构建日志：`docs/sonar-reports/build-exe.log`。

## 7. 范围与残留

1. **扫描范围仅后端**：沿用仓库 `sonar-project.properties`（`sonar.sources=backend/app`）。前端 `apps/admin-web`、小程序 `apps/miniprogram`、云函数 `apps/scf` 未纳入该质量门，故其代码问题不计入本次 OPEN 数。
2. **Security Hotspots 25 个未逐条列出**：当前 token 对 `/api/hotspots/search` 返回 `Insufficient privileges`，仅有总数。这些是需人工复核的安全敏感点，不是已确认漏洞（Vulnerabilities=0）。
3. **SCM blame 缺失告警**：5 个本轮改动文件无 blame（未提交），不影响问题判定与质量门。
4. 前端门禁在本次全量测试中另有 3 项存量红灯（字段登记表陈旧、候选总数文案、帮助正文关键词），已按生成器口径修复并使 673 项全绿；详见 `fix-summary-20261114.md`。
