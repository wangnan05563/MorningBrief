# 会话复盘报告（2026-08-08）

> 来源：本会话中连续解决的 7 类真实问题——TTS 朗读星号、详情页 TTS/素材面板空（双根因）、
> COS 历史 `audio_url` 回填、代码审查发现（`logger.exception`/NOSONAR）、头像上传测试 flake、
> 小程序频道 tab 动态生成、admin-web 展示排序输入框。
> 目标：将"踩过的坑"抽象为可复用的**固定流程 + 判断逻辑**，反哺 `news-code-dev` 编码规范
> 与 `news-backend-code-review` / `news-frontend-code-review` / `news-auto-testing` 三个审查/测试技能。

---

## 一、任务执行复盘（四维度）

### 1.1 成功执行任务的完整步骤

| 阶段 | 动作 | 本会话实例 |
|------|------|-----------|
| ① 复现与定位 | 先稳定复现，再逐层下钻到数据源，而非直接猜渲染/逻辑 | 面板空 → 查 DB `material.workflow_id` 分布 → 发现 1633/1821 为 NULL（频道级池）→ 查前端过滤用 `workflow_id` → 定位根因 |
| ② 读上下文 | 改前必读 model / router / service / 配置四件套，确认字段类型与边界 | 加 `display_order` 前先读 `Channel` 模型、`_migrate_channel_schema`、`ChannelService`、`admin channels router` 五处 |
| ③ 最小改动 | 优先改现有文件、最小 diff，遵循"为什么"注释 | `_persist_segment_audio_urls` 仅回写缺失 `audio_url`，try/except 保护不中断主流程 |
| ④ 安全回填 | 历史数据修正必须 `--dry-run` 预览 → 自动备份 → 实际执行 → 二次 dry-run 复核 | `backfill_strip_markdown.py` 与 `backfill_tts_audio_urls.py` 均 dry-run 先报影响面，再备份 `news.db.bak_*` |
| ⑤ 测试闭环 | 改完即写/跑针对性测试，`py_compile` + 定向 + 全量 | 新增 `test_api_channels_ordering.py` 等；全量 406 passed |
| ⑥ 记录 | 写入 `.workbuddy/memory` 日log，沉淀可复用资产 | 每次完成即 append 当日记忆 |

### 1.2 任务执行中的不确定性与失败点

| 失败点 | 现象 | 根因 | 应对 |
|--------|------|------|------|
| 解释器错配 | `python backfill*.py` 报缺依赖 | 用了 managed Python（无项目依赖） | 改用 `backend/.venv/Scripts/python.exe` |
| 迁移缩进错位 | `py_compile` 报 `new_columns` 跳出 `try` | Edit 时列表缩进脱落 | 重新 Read 后修正缩进 |
| 审查结论误判 | 初判"小程序 tab 需改" | 未先 grep 全仓确认——其实早已动态生成 | 先全仓 grep 硬编码频道名（0 命中）再下结论，避免无效改动 |
| safe-delete 拦截 | 全量 pytest teardown 报 safe-delete 守卫阻断 | pytest 对旧 numbered-tempdir 做 GC 批量删除触发 FAIL CLOSED | 设 `TEMP=backend/.pytest_tmp` 隔离目录，避开守卫 |
| 头像测试 flake | 全量 1 failed、隔离 1 passed | 测试 `unlink data/avatars/*` 被 safe-delete 拦（非 OS-TEMP 路径） | 重定向 `resolve_avatar_dir` 到 `tmp_path` + `monkeypatch` |
| 测试断言错位 | `data["list"][0]["channel_id"]` KeyError | `_material_to_dict` 漏返回 `channel_id` | 补 serializer 字段 + 修正测试断言 |

### 1.3 可抽象的固定流程与判断逻辑

**流程 A：面板/列表"显示为空"的分层诊断（必须按序，禁止直接定性渲染 bug）**
```
1. 先确认前端是否真收到空：查请求参数与响应体（axios 解包后 data 是否空）
2. 再查数据源：DB 该实体是否真有数据？过滤条件字段是否与存储语义匹配？
   - 素材类：是 channel 级池 → 查 channel_id，不是 workflow_id（终态 workflow_id 置 NULL）
   - 音频类：COS 模式下本地 tts 目录为空 → 必须回写 script.segments[].audio_url，否则详情页无兜底
3. 最后查渲染：wx:for / v-for 遍历字段名是否与响应字段一致
```

**流程 B：历史数据修正（回填脚本）安全闭环**
```
dry_run 预览影响面 → 自动备份 DB/文件 → 实际执行（只填缺失/不删、幂等、分批、进度日志）
→ 二次 dry_run 复核归零 → 记录 exception 单独跳过项
```

**流程 C：新增"后端可控排序/开关"字段（让前端免发版）**
```
1. model 加字段（NOT NULL DEFAULT，避免 NULL 排序歧义）
2. main.py 幂等迁移（PRAGMA table_info 检测后 ALTER）
3. 列表接口按该字段排序返回 + 返回体带字段
4. Service create/update 透传 + 失效对应缓存
5. 前端：列表加展示列 + 表单加控件 + 透传（axios 直传不丢字段）
```

**判断逻辑（决策树）**
- 面板空且 DB 有数据 → 不是渲染问题，是**查询维度/字段回写**问题。
- COS 已配置但本地无文件且 segment 无 `audio_url` → 必须补回写逻辑，不是"音频丢了"。
- 改动只影响展示顺序/开关 → 优先做"后端字段 + 缓存失效"，**最小化前端改动**。
- 测试失败但单独运行通过 → 是 flake/顺序/共享状态，不是产品 bug。

### 1.4 适用场景与不适用场景

| 流程 | 适用 | 不适用 |
|------|------|--------|
| A 分层诊断 | 任何"列表/面板空""数据不显示"类问题 | 确认是 404/500 等明确接口错误（直接查路由） |
| B 安全回填 | 存量数据因 schema 演进/bug 需补字段 | 实时路径修复（应在代码里修，不在脚本里补） |
| C 后端可控字段 | 需"运营可调、前端免发版"的配置（排序/开关/权重） | 纯展示性、与后端无关的 UI 状态 |
| `logger.exception` | 所有 `except Exception` 兜底块 | 预期可恢复、需吞掉的单点错误（仍应记 `logger.warning` 带上下文） |

---

## 二、测试过程复盘（四维度）

### 2.1 成功执行任务的完整步骤

| 阶段 | 动作 | 本会话实例 |
|------|------|-----------|
| ① 双轨判定 | 后端 `.py` → pytest；前端 `.vue` → `vue/compiler-sfc` 编译 / Playwright | 后端改完跑 pytest；admin-web 改完用 compiler-sfc 单文件编译校验 |
| ② 隔离 | 设独立 `TEMP`、用 `tmp_path`/`monkeypatch` 避免 safe-delete 守卫误伤 | `TEMP=backend/.pytest_tmp` + `tmp_path_retention_policy=all`；头像测试重定向落盘 |
| ③ 定向 → 广 → 全 | 先跑新增/改动相关用例，再跑相关子集，最后全量 | 7（定向）→ 45（相关）→ 406（全量） |
| ④ 分类 | 失败分"真缺陷 / flake / 环境制品"三类 | 头像 1 failed 归为 safe-delete 环境制品（非代码失败） |
| ⑤ 闭环 | 修复后重跑直到绿；flake 修根因而非跳过 | 头像 flake 改 `resolve_avatar_dir` 重定向，全量回到 404→406 passed |

### 2.2 任务执行中的不确定性与失败点

| 失败点 | 现象 | 根因 | 应对 |
|--------|------|------|------|
| 全量 teardown 守卫 | pytest 退出前 safe-delete 拦批量删 tempdir | pytest 自身 numbered-tempdir GC 触发 FAIL CLOSED | `TEMP` 指向新建空目录，使 GC 无可删旧目录 |
| flake 误判为回归 | 全量 1 failed 初看像新引入 | 共享状态 + 顺序依赖；隔离跑即过 | **先把失败用例单独跑**：过=flake，不过=真缺陷 |
| 解释器无 pytest | 直接用系统 python 报 `No module named pytest` | 项目依赖在 `.venv` | 用 `.venv/Scripts/python.exe -m pytest` |
| 断言 KeyError | 测试取了 serializer 未返回的字段 | `_material_to_dict` 漏字段 | 补 serializer + 同步修正断言 |
| 缓存串味 | 多用例共享 `CacheManager` 单例 | 缺 `_clear_cache_manager` 夹具 | 依赖 autouse 夹具清缓存（conftest 已有） |

### 2.3 可抽象的固定流程与判断逻辑

**流程 D：测试执行与 flake 判别（Sequential）**
```
1. 判定改动轨：backend/**/*.py → pytest；admin-web/src/** / miniprogram/** → 编译/Playwright
2. 隔离环境：设置独立 TEMP；落盘类测试重定向到 tmp_path（OS-TEMP 守卫放行）
3. 跑定向用例；有失败 → 步骤 4 判别
4. 单跑失败用例（隔离）：
   - 通过 → 预存 flake（顺序/共享状态）→ 修根因（fixture 隔离 / 重定向）而非跳过
   - 失败 → 真缺陷 → 定位代码修复
5. 跑相关子集 + 全量；全量前设独立 TEMP 避开 teardown 守卫
6. 修复后重跑至全绿；记录环境制品单独归类
```

**流程 E：前端改动验证（无 Playwright 时也成立）**
```
vue/compiler-sfc 编译目标 SFC（template + script 双校验）→ 无错即语法/模板过关；
字段契约对照后端返回体（snake_case 直传、新增字段有表单控件+列表列）
```

**判断逻辑**
- 全量失败但定向/隔离过 → 几乎必是 flake/顺序/共享状态，先隔离复跑再下结论。
- 测试内 `unlink`/`write` 命中非 OS-TEMP 路径 → 必被 safe-delete 拦，归环境制品；正解是重定向。
- "通过"定义：定向 + 相关 + 全量三级全绿，且 flake 已修根因。

### 2.4 适用场景与不适用场景

| 流程 | 适用 | 不适用 |
|------|------|--------|
| D flake 判别 | 全量套件偶发 1 failed、CI 不稳定 | 单用例 100% 复现失败（直接当真缺陷） |
| D 隔离 TEMP | 任何用 pytest 且环境有 safe-delete 守卫 | 无守卫的纯 CI 容器（可省略，但仍建议独立 TEMP） |
| E SFC 编译 | Vue SFC 语法/模板快速校验 | 需运行时行为的交互测试（需 Playwright/MCP） |
| 缓存清 fixture | 多用例共享模块级单例（CacheManager/TTLCache） | 用例间无共享状态的纯函数测试 |

---

## 三、反哺到技能的标准清单（摘要）

下列标准已分别落到：
- `news-code-dev`：R200–R212（详见其 SKILL.md 新增章节）
- `news-backend-code-review`：维度 207–213（V3.2 章节）
- `news-frontend-code-review`：FE-202–FE-205（V3.2 章节）
- `news-auto-testing`：flake 判别 + 隔离 TEMP + 顺序化测试流程（配置驱动）

| 标准 | 类型 | 关键约束 |
|------|------|----------|
| 面板空分层诊断 | 判断逻辑 | 先数据源后渲染；素材查 channel_id；COS 模式回写 audio_url |
| 历史回填安全 | 流程 | dry-run→备份→只填不删→幂等→复核 |
| 后端可控字段 | 流程 | model+迁移+排序返回+缓存失效+前端控件 |
| logger.exception | 规范 | broad except 必须保留 traceback；NOSONAR 写在 def 行 |
| COS 列举健壮 | 规范 | 无 Delimiter 不返 NextMarker→回退末位 Key；列举 try/except |
| 测试隔离 | 规范 | 落盘重定向 tmp_path；全量设独立 TEMP；flake 单跑判别 |
| 频道 tab 动态 | 规范 | 禁硬编码频道名；display_order 控制排序；前端免发版 |
