# T02028 处理结果

来源：T01925（时长口径校正）→ 本单把「拼接实测时长」在链路里正规落地。
类型：派生单（不再生成新派生单，剩余工作 derivedFrom 写 T01925）。

## 根因

拼接阶段（`concat.py`）本来就把成品时长实测得很准，还会把不足下限的节目用
BGM/静音凑到 `min_allowed+2`、把超长的用 atempo 压到上限——但这条信息在
`workflow_scheduler._create_review` 处被丢弃：该步只从 context 取
`final_audio_url` / `hls_url`，`duration` 到此为止，review 表也没有承载它的列。
于是发布时只剩两条退路：T01925 临时加的「发布期 ffprobe 探测外链」，或探测失败时
回退 `script.estimated_duration`（按字数反算，与成品可差数百秒）。
更关键的是**「凑出来的秒数」全程无人可见**——运营在管理端看到 8 分钟，
无法知道内容实测只有 6 分 59 秒。

## 影响范围

- 后端：`review` / `episode` 两张表结构（新增可空列，走启动迁移）
- 链路：`concat` 返回值 → 工作流 context → `_create_review` → `publish_episode`
- 接口：`GET /admin/api/v1/reviews` 列表项新增三字段
- 前端：管理端「内容审核」列表新增「时长」列（三个 tab 共用）
- 不影响：小程序读路径（`episode.duration` 语义不变，只是取值更准）、
  历史 81 条 review / 95 条 episode（列保持 NULL，不回填）

## 修复

| 文件（绝对路径） | 改动点 |
| --- | --- |
| `D:\code\otherProjects\20_News\backend\app\models\review.py` | 新增 `measured_duration_sec` / `original_duration_sec` / `supplement_sec` 三个可空 Integer 列 |
| `D:\code\otherProjects\20_News\backend\app\models\episode.py` | 新增 `supplement_sec` / `original_duration_sec` 快照列 |
| `D:\code\otherProjects\20_News\backend\app\workflow\stitch\concat.py` | 时长改造前初始化 `original_duration=duration` / `supplement_sec=0`，补足与 atempo 分支各自更新，return 增两键；删掉 atempo 分支里一处重复赋值 |
| `D:\code\otherProjects\20_News\backend\app\services\workflow_scheduler.py` | `_create_review` 读 `context["duration"/"original_duration"/"supplement_sec"]` 落库，日志带三个值（此前 context 里的 duration 被丢弃） |
| `D:\code\otherProjects\20_News\backend\app\main.py` | 新增 `_migrate_duration_trace_columns()`（PRAGMA 判重后 `ALTER TABLE ADD COLUMN`，幂等，异常仅 warning 不阻塞启动），startup 注册在 `_migrate_review_auto_approve_columns` 之后 |
| `D:\code\otherProjects\20_News\backend\app\services\content_service.py` | 发布取时长改为 `review.measured_duration_sec or await _measure_audio_duration(...)`，并把两列快照到 episode；`_measure_audio_duration` docstring 标注为兜底路径 |
| `D:\code\otherProjects\20_News\backend\app\services\review_service.py` | `list_reviews` 返回字典新增三字段 |
| `D:\code\otherProjects\20_News\apps\admin-web\src\views\review\ReviewList.vue` | 「状态」列后新增「时长」列（width 170）：实测时长 `formatDuration` 显示，NULL 显示 `—`，`supplement_sec>0` 时追加 warning tag「凑时 Ns」+ tooltip「成品含 Ns BGM/静音凑时，内容实测 X分Y秒」 |
| `D:\code\otherProjects\20_News\backend\tests\test_duration_trace.py` | 新建 5 条用例（见下） |

## 验证

全部实测，非推断。硬约束遵守情况：**未改 `.env`、未改生产配置、未触发 LLM/TTS、
库写全部发生在 `news.db` 的副本上**。

1. **新用例** `pytest tests/test_duration_trace.py tests/test_content_service.py -q`
   → `15 passed`。新文件 5 条覆盖：
   - `_create_review` 把三个值落 review 行
   - 老 context（无键）时列为 NULL 不抛错
   - **有实测值时 `probe_calls == []`**（任务正文点名的「不再探测」断言）
   - 老 review 回退探测路径仍工作
   - 加列迁移幂等 + 存量行不被改写
2. **全量回归** `pytest tests -q` → **`1047 passed`**（基线 1042 + 本单新增 5），
   0 failed / 0 skipped，`_validate/t02028_pytest_full.txt`。
3. **迁移预演（副本库）** `_validate/t02028_migration_rehearsal.py`：把 `news.db`
   复制后连续跑 3 次迁移 → 列只加一次、每次 `新增列: []`，且断言
   「存量行 = 旧行 + 右补 NULL」逐行相等（review 81 行 / episode 95 行无变化）。
   生产库 `backend/data/news.db` 现网列已就位（`measured/original/supplement`
   三列存在、历史行 0 条非 NULL），备份 `data/news.db.bak-t01925` 仍在。
4. **真实链路冒烟（不花钱）** `_validate/t02028_realchain_smoke.py`：用已有成品
   `ep100.mp3` 切 3×140s 本地片段喂给 `concat()`（上传函数打桩，产物不落 COS），
   再依次跑 `_create_review` 与 `publish_episode`，全程在副本库上：
   ```
   [concat]   duration=482 original_duration=419 supplement_sec=63
   [review #82] measured/original/supplement = (482, 419, 63)
   [episode #101] duration=482 supplement=63 original=419   # 稿件估算值 86 已被忽略
   [ok] concat → review → episode 全链路时长留痕贯通（副本库，生产库未写）
   ```
   420s 内容 < 480s 下限，必然走补足分支，实测补足 63s → 482s，与代码约定一致。
5. **前端构建** `npm run build` → `✓ built in 37.16s`，0 error。
6. **管理端 UI 实测**（Playwright + 系统 Chrome，后端指向副本库，因为生产库历史行
   全 NULL 验不出标记）`_validate/t02028_ui_check.mjs`：
   ```
   表头: ["","日期","工作流ID","状态","时长","审核人","创建时间","操作"]
   有时长值的行数: 1        历史行显示为 — 的数量: 9 / 10
   时长单元格文本: "8 分 2 秒\n凑时 63s"
   凑时标记 tag class: el-tag el-tag--warning el-tag--small el-tag--plain el-tooltip__trigger
   tooltip: ["成品含 63s BGM/静音凑时，内容实测 6 分 59 秒"]
   异常占位: []            # 无 undefined / NaN / null
   已通过: 时长列存在=true 行数=10 全为—=true
   已打回: 时长列存在=true 行数=0
   ```
   截图 `_validate/t02028_ui_list.png`（含 tooltip 展开态）、`t02028_ui_tabs.png`。
   实测后端进程（含其自动拉起的 tailscale funnel 子进程）已 kill 并 `netstat` 确认端口释放。
7. **接口字段** `_validate/t02028_api_fields.txt`：列表项实际返回
   `measured_duration_sec=482 / original_duration_sec=419 / supplement_sec=63`，
   历史行为 `None`。

## 本次回写

- 无新增派生单（本单为派生单，剩余工作按规则挂回原单 T01925）。
- 真机侧复验由同批的 T02029 承接（小程序收听百分比/完播判定）。

## 下一步建议

1. **历史 review 不回填是有意的**，但意味着上线后新链路生效前产生的 review 仍走
   探测兜底；若希望一次性补齐，可参照 `_validate/t01925_backfill_duration.py` 的
   口径做一次回填（需逐条探测，建议低峰跑）。本单为派生单不再派生，该剩余工作随
   本次回传并入原单 T01925 正文。（仅观察不建单）
2. 审核**详情页**目前不展示时长留痕，运营在详情页 approve 时看不到「凑时」；
   列表页已可见，是否补到详情页属产品取舍。同上，并入原单 T01925，不另建单。
   （仅观察不建单）
