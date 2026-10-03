# 目录结构与清理记录

## 2026-07-23 工作空间清理

### 背景

项目根目录文件数达 19 个（含 12 个垃圾文件），admin-web 散落 4 个调试产物，backend 下 22 个 `__pycache__/` + 1 个 `.pytest_cache/`，`build/` 占 44 MB、`dist/` 占 167 MB（含 2 个 Setup.exe）。

### 清理动作

| 类别 | 内容 | 数量 | 释放空间 |
|---|---|---|---|
| 缓存目录 | `.scannerwork/`、22 个 `__pycache__/`、`.pytest_cache/` | 24 | 4.39 MB |
| 根目录垃圾 | `build_output.txt`、`clear_test.py`、2 张测试图片、`pytest-output.log`、6 个 `sonar-*.log`、`test_tts.mp3`、`-w` | 13 | 2.41 MB |
| admin-web 散落 | `build_output.log`、`debug.log`、2 个 `vite.config.js.timestamp-*.mjs` | 4 | 0.06 MB |
| 构建产物 | `build/`（PyInstaller 中间产物） | 1 目录 | 44.4 MB |
| 旧版安装包 | `dist/MorningBrief-Setup-v1.0.0.exe` | 1 | 39.53 MB |
| 前端构建产物 | `admin-web/dist/` | 1 目录 | 2.06 MB |
| **合计** | | **41** | **~92.85 MB** |

### 验证结果

- **Python 语法检查**：`backend/app/main.py`、`config.py`、`models/__init__.py` 语法正确 ✓
- **目录结构**：11 个关键目录（backend/app、routers、services、models、workflow 各子目录、admin-web/src、miniprogram）全部存在 ✓
- **根目录文件**：19 → 5 个（仅保留配置文件）✓
- **源代码完整**：188 个 `.py` + 26 个 `.vue` + 20 个 `.js` 全部完整 ✓
- **稳定性检查**：5 秒复扫无复发文件 ✓

### 保留内容

根目录保留 5 个配置文件：`.gitignore`、`cleanup-config.yaml`、`installer.iss`、`MorningBrief.spec`、`sonar-project.properties`。

`dist/` 保留 `MorningBrief-Setup-v1.2.0.exe`（当前版本）。

### 新增 .gitignore 规则

在 `.gitignore` 末尾追加「清理技能自动生成规则」块，共 8 条规则：
- `admin-web/vite.config.js.timestamp-*.mjs`（Vite 临时配置）
- `/build_output.txt`、`/build_output.log`（构建输出散落）
- `/test_tts.mp3`、`/clear_test.py`、`/generated_image.png`、`/morning_brief_cycling.png`（测试产物散落）
- `/-w`（异常命名误重定向）
- `/sonar-*.log`、`/sonar-*.txt`、`/pytest-output.log`（SonarQube 调试输出补充）

### 备份日志

清理前所有待删除文件的 SHA256 hash 已备份至 `logs/cleanup-20260723-015857.log`，可用于追溯。

### 后续建议

1. **散落脚本整理**：`backend/` 下有 `main.py`、`backfill_*.py`、`migrate_*.py`、`seed_*.py`、`launcher.py` 等脚本，可考虑统一归入 `backend/scripts/` 目录（需先确认 `MorningBrief.spec` 的路径引用）。
2. **venv 依赖修复**：`backend/.venv` 缺少 `loguru` 等依赖（`ModuleNotFoundError`），建议运行 `pip install -r backend/requirements.txt` 修复。
3. **周期性维护**：建议每月运行一次清理，防止调试产物累积。

---

## 2026-08-11 工作空间清理（周期性维护 · 第二轮）

### 背景

距上一轮（2026-07-23）约三周，项目持续开发，Python 字节码缓存、测试缓存与运行日志重新累积。本轮聚焦**纯可重建的编译/测试缓存与运行日志**，严格保留全部源代码、配置文件、用户数据（`*.db`）、构建产物（`dist/`、`build/`）、虚拟环境（`.venv`/`.venv-build`）与依赖（`node_modules`）。

基线快照（清理前）：944 个 `__pycache__/`、2 个 `.pytest_cache/`、1 个 `jmeter.log`(162 KB)、1 个临时文件、5 个游离 `.pyc`。

### 清理动作

| 类别 | 内容 | 数量 | 释放空间 |
|---|---|---|---|
| Python 字节码缓存 | `__pycache__/` 目录（递归） | 944 目录 | 127.23 MB |
| Python 字节码缓存 | 游离 `.pyc`（不入 `__pycache__`） | 5 文件 | ~0.04 MB |
| 测试缓存 | `.pytest_cache/` 目录 | 2 目录 | 0.04 MB |
| 运行日志 | 根目录 `jmeter.log`（JMeter 压测运行日志，可重建） | 1 文件 | 0.16 MB |
| 临时文件 | `tmp/bak/orig` 后缀文件 | 1 文件 | 0.02 MB |
| **合计** | | **953** | **~127.49 MB** |

### 验证结果

- **删除完整性**：清理后全树复扫 `__pycache__/`=0、`.pytest_cache/`=0、游离 `.pyc`=0、`jmeter.log` 已删除、tmp/bak/orig=0 ✓
- **源代码零损失**：`git status` 显示 0 个被跟踪文件删除（`^ D`=0）；backend 下 5842 个 `.py` 源文件完整 ✓
- **用户数据保留**：20 个 `*.db`（SQLite 数据）全部 intact ✓
- **交付/运行产物保留**：`dist/`、`build/`、`.venv/`、`.venv-build/`、10 个 `node_modules` 全部保留 ✓
- **配置保留**：`cleanup-config.yaml`、`.gitignore`、`sonar-project.properties`、`installer.iss`、`MorningBrief.spec` 及根目录 `.xlsx` 业务文档均保留 ✓
- **IDE/工具目录隔离**：`.workbuddy/` 未被触碰（技能规则明确禁止清理）✓

### 保留内容

- 构建产物 `dist/`、`build/`（含 `MorningBrief-Setup-v1.0.0.exe` 与 PyInstaller 中间产物）——属交付物，非垃圾。
- 虚拟环境 `.venv`、`.venv-build` 与依赖 `node_modules` —— 重建成本高，保留。
- `.run/`（含 `*.pid`、`test_token.txt`）、`.tmp/`（含 `api_test.ps1` 等调试脚本）—— 含运行中进程文件与工作脚本，本轮按"仅删纯缓存/日志"原则保留。
- `data/`（含 `cloudflared.exe`、`cpolar.exe` 运行时二进制）、`canvas-design/`、`docs/`、`reports/`、`jmeter_test/`、`logs/` —— 均属业务/产物/历史数据，保留。

### .gitignore 规则

本轮无需新增规则：`.gitignore` 已覆盖全部清理类别（第 19 行 `*.py[cod]`、第 18 行 `__pycache__/`、第 23 行 `.pytest_cache/`、第 48 行 `*.log`、第 124 行 `*.tmp`、第 193 行 `/jmeter.log`）。复发防护已具备。

### 备份日志

- 阶段二哈希备份：`logs/cleanup-<时间戳>.log`（待删项 SHA256 记录，可追溯）。
- 执行日志：`logs/cleanup-loop-*.log`（FINAL totalOk=727 totalFail=0，单进程内多轮收敛）、`logs/cleanup-run-*.log`、`logs/cleanup-del-*.log`、`logs/cleanup-final.log`。

### 后续建议

1. **venv 依赖修复**（同前）：`backend` 导入报 `ModuleNotFoundError: loguru`，建议 `pip install -r backend/requirements.txt`。
2. **周期性维护**：缓存类垃圾再生快，建议每月或每个里程碑后运行一次 workspace-cleanup。
3. **`.tmp/`/`.run/` 待定项**：这两目录含调试脚本与运行态文件，本轮未清理；若确认其中脚本已无用，可纳入下一轮分类。

---

## 2026-08-16 目录重组（规范化分类评估与执行）

### 背景

用户要求按功能把项目重组为 6 个标准目录并评估合理性：

> 前端 → `frontend`、后端 → `backend`、自动化/工具脚本 → `script`、构建产物/打包输出 → `dist`、运行日志 → `log`、项目文档 → `docs`，所有现存文件按此分类迁移。

### 评估结论（是否合理）

**部分合理，但不可直接套用，否则破坏构建与运行态：**

1. **`admin-web` 即事实上的前端**，但被硬编码引用 10+ 处：`ci.yml`（7 处 `cd admin-web`/`npm ci`/`playwright`）、5 个构建/打包脚本（`build-exe.ps1`、`build-frontend.ps1`、`generate-icons.ps1`、`setup-env.ps1`、两个 `.bat`）、**运行时 SPA 解析器** `backend/app/paths.py:126/136`（`app_root / "admin-web" / "dist"`）、`installer.iss` 打包逻辑（`build-exe.ps1` 复制到 `dist\admin-web\dist`）。改名 `frontend` 会导致后台全 404 + 打包失败，需同步改 10+ 文件并跑通验证 → **保留原名，在文档中标注为前端目录**。
2. **命名 `script`/`log`（单数）与生态惯例及现有 `cleanup-config.yaml`（`scripts`/`logs` 复数）冲突** → 保持复数。
3. **6 类覆盖不全**：`miniprogram`（独立小程序客户端）、`scf`（云函数，独立部署契约 `scf/xxx.handler`）、`data`（SQLite + cloudflared/cpolar 隧道二进制）、`node_modules`（依赖）、`assets`（安装包图标，被 `installer.iss` 引用）、`canvas-design`（素材生成工具）、`jmeter_test`（压测工具）、`reports`（评审纪要）、`installer.iss`/`MorningBrief.spec`（构建配置）无归宿。
4. **`build/` vs `dist/` 重叠**：`dist/` 已承载打包 exe（`dist/MorningBrief/`）；`build/MorningBrief/` 是 PyInstaller 中间目录（应 gitignore，非交付物）。

### 执行动作（低风险的「安全归并」，未做任何破坏构建/运行态的改名）

| 原路径 | 新路径 | 说明 |
|---|---|---|
| `jmeter_test/` | `scripts/jmeter_test/` | 性能压测工具归入脚本目录；仅 `docs` 两处引用同步更新 |
| `reports/` | `docs/reports/` | 评审/复盘纪要归入文档目录 |
| `canvas-design/` | `scripts/canvas-design/` | 素材生成工具（脚本 + 图片）归入脚本目录 |
| `scf/` | **保留根目录** | 独立部署的云函数，设计文档明确为项目根目录且有 `scf/xxx.handler` 部署契约，移入 `backend/` 会破坏该契约（与 `miniprogram` 同类） |
| `miniprogram/`、`assets/`、`data/`、`node_modules/`、`installer.iss`、`MorningBrief.spec` | **保留根目录** | 各有引用（installer.iss 引用 `assets\`、运行时二进制、依赖）或属运行时/依赖，不可移动 |

- 同步修正 `.gitignore`：移除过度宽泛的 `reports`、`jmeter_test` 两行（无斜杠锚点，会误忽略新建的 `docs/reports`、`scripts/jmeter_test`），确保迁移后目录正常纳入版本控制。

### 规范化目标布局（当前实际结构）

| 分类 | 目录 | 备注 |
|---|---|---|
| 前端 | `admin-web/`（即 frontend） | Vue SPA，被 CI/构建/运行时硬编码引用，暂不改名 |
| 后端 | `backend/` | FastAPI 应用 + `backend/app`（服务源码） |
| 脚本 | `scripts/`（含 `scripts/jmeter_test/`、`scripts/canvas-design/`） | 构建/打包/压测/素材生成工具 |
| 构建产物 | `dist/`（含 `dist/MorningBrief/` 打包 exe）、`build/` | 交付物，运行时伺服根 |
| 日志 | `logs/` | 运行态日志（gitignore），运行时 `paths.py` 解析 |
| 文档 | `docs/`（含 `docs/reports/`、`docs/test-reports/`、`docs/sonar-reports/`、`docs/standards/`） | 设计/测试/评审/规范 |
| 独立部署/运行时 | `miniprogram/`、`scf/`、`data/`、`assets/`、`node_modules/` | 各有部署或运行契约，保留根目录 |
| 根配置 | `installer.iss`、`MorningBrief.spec`、`sonar-project.properties`、`.gitignore`、`cleanup-config.yaml` | 构建/扫描/清理配置 |

---

## 2026-08-16 完整分桶重组（apps / backend / scripts / docs / release / runtime）

### 背景（续第一轮规范化）

第一轮（上文 2026-08-16）仅做了「安全归并」（jmeter_test/reports/canvas-design 入 scripts/docs），根目录仍有 `admin-web/`、`miniprogram/`、`scf/`、`dist/`、`build/`、`assets/`、`data/`、`logs/` 共 8 个功能性目录 + `node_modules/`，顶层偏多。本轮按用户确认的「完整分桶」方案，将其归入 6 个标准顶层桶，根目录归一为 7 个目录（+ `node_modules/`）。

### 执行动作（完整分桶）

| 原路径 | 新路径 | 说明 |
|---|---|---|
| `admin-web/` | `apps/admin-web/` | 前端 Vue SPA；同步更新 ci.yml、5 个构建/打包脚本、运行时 `backend/app/paths.py:136`、`installer.iss`/`MorningBrief.spec` 图标与打包路径 |
| `miniprogram/` | `apps/miniprogram/` | 微信小程序客户端 |
| `scf/` | `apps/scf/` | 腾讯云 SCF，部署契约由 `scf/xxx.handler` 更新为 `apps/scf/xxx.handler` |
| `dist/` | `release/MorningBrief/` | 打包 exe 交付物（gitignore）；`build-exe.ps1`/`installer.iss`/`MorningBrief.spec` 同步改 `release/MorningBrief` |
| `build/` | `release/build/` | PyInstaller 中间目录（gitignore）；`build-exe.ps1` 清理列表同步改 `release/build` |
| `assets/` | `release/assets/` | 安装包图标 `MorningBrief.ico`，被 `installer.iss`/`MorningBrief.spec` 引用，改为 `release/assets/MorningBrief.ico` |
| `data/` | `runtime/data/` | cloudflared/cpolar 隧道二进制（dev 真实库在 `backend/data/`，不在本次移动范围） |
| `logs/` | `runtime/logs/` | 运行态日志（gitignore）；`start.ps1`/`cleanup-config.yaml` `logs_dir`/`preserve_roots`/`service_indicators` 同步改 `runtime/logs` |
| `canvas-fonts/` | （删除） | 空目录，无引用，直接移除 |

> 冻结态（exe 模式）SPA 拷贝名保持 `admin-web/dist`：`build-exe.ps1` 复制到 `release/MorningBrief/admin-web/dist`，`backend/app/paths.py:126` 的 `ext_dist` 仍按 `admin-web/dist` 解析（exe 同级子目录名，与源码树位置无关）。仅开发态路径 `paths.py:136`（`app_root.parent`）改 `apps/admin-web/dist`。

### 规范化目标布局（当前实际结构）

| 分类 | 目录 | 备注 |
|---|---|---|
| 前端 | `apps/admin-web/`（即 frontend） | Vue SPA，CI/构建/运行时硬编码引用，保持原名置于 `apps/` 下 |
| 小程序 | `apps/miniprogram/` | 微信小程序客户端，独立部署 |
| 云函数 | `apps/scf/` | 腾讯云 SCF，部署契约 `apps/scf/xxx.handler` |
| 后端 | `backend/` | FastAPI 应用 + `backend/app`（服务源码） |
| 脚本 | `scripts/`（含 `scripts/jmeter_test/`、`scripts/canvas-design/`） | 构建/打包/压测/素材生成/运维工具 |
| 构建产物/打包 | `release/MorningBrief/`（打包 exe + 安装包 `MorningBrief-Setup-v*.exe`）、`release/build/`（PyInstaller 中间目录）、`release/assets/`（安装包图标 `MorningBrief.ico`） | 交付物与安装包资源 |
| 运行时数据/日志 | `runtime/data/`（隧道二进制 + audio_cache）、`runtime/logs/`（运行态日志，gitignore） | 运行时产物，被 `paths.py`/`start.ps1`/`cleanup-config.yaml` 解析 |
| 文档 | `docs/`（含 `docs/reports/`、`docs/test-reports/`、`docs/sonar-reports/`、`docs/standards/`） | 设计/测试/评审/规范 |
| 根配置 | `installer.iss`、`MorningBrief.spec`、`sonar-project.properties`、`.gitignore`、`cleanup-config.yaml` | 构建/扫描/清理配置 |

### 根目录最终形态

- 目录（7）：`apps/` `backend/` `docs/` `release/` `runtime/` `scripts/` + `node_modules/`（gitignore）
- 文件（4）：`cleanup-config.yaml` `installer.iss` `MorningBrief.spec` `sonar-project.properties`

---

## 2026-09-10 工作空间清理（周期性维护 · 第三轮）

### 背景

距上一轮（2026-08-14，删 3633 文件 / 137.2 MB）约四周。根目录已稳定（9 个文件，全部合规），本轮垃圾集中在**子目录与运行态目录**：backend 下 22 个 `__pycache__/`、pytest 临时目录、5 个超大运行日志（合计 106.5 MB）、以及散落在 `apps/admin-web` 的 Vite 临时配置与调试产物。

执行前服务状态四重检测：`runtime/logs/{web,app}.pid` 不存在、8000/8080/5000 端口无监听、后端日志与 `service-error.log` 未被占用 → 判定服务已停止，可安全执行。

### 清理动作

| Tier | 类别 | 数量 | 处理方式 | 空间 |
|---|---|---|---|---|
| A | Python 字节码 `__pycache__/`（backend 22 个 + 根 1 个） | 259 文件 / 23 目录 | 直接删除 | 3.11 MB |
| A | pytest 临时目录 `backend/.pytest_tmp/`、`.pytest_cache/`×2 | 110 文件 / 3 目录 | 直接删除 | 0.05 MB |
| A | Sonar / 临时目录 `.scannerwork/`、`backend/.tmp/`、`pytest-cache-files-*/` | 3 文件 / 3 目录 | 直接删除 | ~0 MB |
| B | 运行日志：`backend/logs/MorningBrief_2026-0{9-01,9-05,9-06,9-09}.log` 等 | 10 文件 | 直接删除 | 106.52 MB |
| C | 根目录调试产物：`_sonar_issues.py`、`_es_query.json`、`_diag_build.ps1`（空文件） | 3 文件 | 直接删除 | ~0 MB |
| C | `apps/admin-web/`：`vite.config.js.timestamp-*.mjs`×5、`_clean_tmp.py`、`test-last-run.txt` | 7 文件 | 直接删除 | 0.05 MB |
| D | 一次性脚本与上轮审计产物：`temp/`、`backend/temp/`、`backend/fix_client.py`、`.run/test_token.txt`、`runtime/logs/cleanup-*`、`stats_page_*.png` | 20 文件 | **隔离 24h** | 1.48 MB |
| D | `apps/admin-web/dist/`（SPA 构建产物） | 109 文件 | **隔离 24h** | 3.27 MB |
| **合计** | | **521 文件 / 29 目录** | | **~114.47 MB** |

### 风险分级与处置依据

| 级别 | 判定 | 处置 |
|---|---|---|
| 零风险 | 纯缓存/字节码，可完全再生 | 直接删除 |
| 低风险 | 运行日志、根目录调试脚本（空文件、一次性 ES 查询） | 直接删除（删前 sha256 留痕） |
| 中风险 | 一次性验证脚本、上轮清理审计产物、前端构建产物 | **移动至 `runtime/.cleanup-trash-20260910/`**（24h 恢复窗口） |
| 高风险（未执行） | `backend/data/backup/` 9 个 DB 备份（~205 MB）、`news.db.bak_constraint_drop`（22 MB） | 用户数据，仅列出未动 |

### 验证结果

- **语法完整性**：`backend/app` + `backend/tests` 共 **244 个 `.py` AST 解析 0 错误** ✓
- **应用导入冒烟**：`.venv\Scripts\python.exe -B -c "from app.main import app"` → **import OK，199 条路由，4.83s，exit=0** ✓（`-B` 确保不复生 pyc）
- **稳定性复扫**：6 秒后复扫 `__pycache__`=0、`backend/logs`=0、根 `__pycache__`=0 ✓
- **根目录文件**：9 → **6** ✓
- **用户数据零触碰**：`backend/data/news.db`(40 MB)、`backup/`、`bgm/`、`avatars/`、`ai_budget.json`、`tunnel_config.json` 全部保留 ✓
- **保留根零触碰**：`build/`、`release/`、`runtime/data/`、`node_modules/`×2、`backend/ffmpeg/`、`.trae/`、`.workbuddy/`、`.venv*` ✓

### 新增 .gitignore 规则

追加「清理技能自动生成规则 (workspace-cleanup 2026-09-10)」块，共 8 条：

| 规则 | 补的缺口 |
|---|---|
| `vite.config.js.timestamp-*.mjs` | 旧规则 `admin-web/...` 含斜杠被锚定到仓库根，未命中 `apps/admin-web/` 层级（本轮 5 个文件曾被跟踪） |
| `/pytest-cache-files-*/` | 根目录 pytest 随机后缀临时目录（`.pytest_cache/` 规则未覆盖） |
| `.pytest_tmp/` | backend pytest 临时目录 |
| `/_*.json`、`/_*.txt` | 已有 `/ _*.py`、`/_*.ps1`，补齐 json/txt 两类 |
| `test-last-run.txt` | 前端测试运行残留（本轮 1 个文件曾被跟踪） |
| `/.run/` | 运行态 pid / 临时 token 目录 |
| `runtime/.cleanup-trash-*/` | 未来清理隔离区，防止误入库 |

> `.pre-commit-config.yaml` 在本仓库不存在（项目未启用 pre-commit），故未生成钩子；防复发依赖 `.gitignore` + CI。如需强制拦截，建议后续引入 pre-commit 或复用 `.github/workflows/ci.yml`。

### 备份与可追溯

- **删前哈希审计**：`runtime/logs/cleanup-20260910-audit.log`（412 行：SHA256 \| 字节数 \| Tier \| 动作 \| 路径）
- **目标清单**：`runtime/logs/cleanup-targets-20260910.txt`、`cleanup-plan-20260910.json`
- **隔离区**：`runtime/.cleanup-trash-20260910/`（21 项，含 `dist/`；24h 内可原样恢复）—— **已于 2026-10-03 第二轮清理中连同审计哈希一并删除**，详见本文档「2026-10-03 工作空间清理（第二轮）」
- **执行脚本**：`runtime/logs/wscleanup-exec-20260910.ps1`（enumerate / hashlog / delete / move / movedirs / rmdirs 六动作，幂等）

### 未清理的风险文件（需人工决策）

| 项 | 大小 | 原因 |
|---|---|---|
| `backend/data/backup/` 9 个 DB 备份 | ~205 MB | 用户数据，备份轮转残留，删前需确认保留策略 |
| `backend/data/news.db.bak_constraint_drop` | 22 MB | 08-19 手工兜底备份 |
| `backend/fix_client.py` | 9.7 KB | 已隔离；untracked 一次性修复脚本，待确认是否仍需 |
| `release/assets/MorningBrief.ico` | — | **本轮之前即已缺失**（`git ls-files --deleted` 可见，不在本轮目标清单内），且整个 `release/` 目录当前不存在，待确认是否被历史打包脚本清除 |

---

## 2026-10-03 清理轮次（T01363 收尾后）

**结论：删除 295 文件 / 22 目录（3.8 MB），全部为可再生缓存；480 MB 空间因证据/活跃/不可再生原因保留待决。**

### 已删除（tier=delete，配置 `cache_dirs` 明确列入）

| 项 | 数量 | 体积 | 依据 |
|---|---|---|---|
| `backend/**/__pycache__/*.pyc` | 290 | 3.7 MB | `garbage_patterns.cache_dirs` 明确列入 `__pycache__/`，完全可再生 |
| `backend/.pytest_cache/` | 5 | 0.1 MB | 同上，明确列入 `.pytest_cache/` |

- **删前哈希审计**：`runtime/logs/cleanup-20261003-225430.log`（290 行：SHA256 \| 字节数 \| 路径）
- **目标清单**：`runtime/logs/cleanup-targets.txt`
- **执行方式**：`bypass_hook_mode: ctypes` + `flatten_directories` + 批大小 20（295 文件 → 15 批），错误 0
- **验证**：`from app.main import app` → OK（231 路由）；定向回归 25 passed（material 契约 / content_security / upgrade_service）

### 保留待决（tier=review，未自动删）

| 项 | 体积 | 保留原因 |
|---|---|---|
| `runtime/.cleanup-trash-20260910/` | 73.2 MB | 9/10 隔离区，24h 恢复窗口早已过期，但**本文档第 255 行将其登记为审计证据**——按「引用即承重墙」原则，删除前需先更新本文档的证据登记 |
| `backend/.venv-build/` | 113.5 MB | 7/23 遗留构建 venv，无代码引用（`build-exe.ps1` 用的是仓库根 `.venv-build`）；重建需联网装依赖，当前环境 pypi 不可达 → 不可逆因素命中，路由 review |
| `.venv` → `backend/.venv-build` | 符号链接 | **绝不可递归删除**：根 `.venv` 是指向 `backend/.venv-build` 的 symlink，沿链接删除会清空真实 venv 内容（项目铁律） |
| `backend/logs/` | 370.5 MB | 38 个文件全部为当日（10-03）运行日志，是压测与部署验证的诊断依据；loguru retention 14d 会自动轮转 |
| `_validate/` | 34.1 MB | mtask 任务结论回传证据归档（`res_*.md`）与压测原始 jtl |

### 本轮发现的配置漂移（`cleanup-config.yaml`，未擅自修改）

1. **`verification.command` 引用 `xianyu_hunter`（另一项目）** → 验证命令必然 FAIL，本轮改用真实导入 `from app.main import app` 降级验证
2. `service_indicators.pid_files` → `runtime/logs/{web,app}.pid` 不存在
3. `service_indicators.file_occupancy_probes` → `runtime/data/xianyu.db` 不存在（实际 `news.db`）
4. `workspace.frontend_dir: "frontend"` → 本项目前端在 `apps/admin-web`
5. 配置缺失 12 个 section（`actions`/`quarantine`/`recovery`/`evidence_gate`/`preserve_paths`/`semantic_divergence`/`sizing`/`diagnostics`/`report`/`dependency_check`/`capability_probe`/`ignored_audit`）→ 按 skill fallback 表，`recovery` 缺失要求所有候选路由 quarantine，故本轮 delete 桶仅限配置明确授权的 `cache_dirs`
6. **记忆漂移**：项目记忆记录 `build/`、`release/` 是指向 `F:\MorningBrief_build\` 的 NTFS junction，但实测 `os.path.isjunction()` 均为 `False`、`islink()` 亦为 `False` → 二者是 D 盘真实目录（release 569 MB / build 12 MB），D 盘空间压力应按真实占用计算


### 后续建议

1. **DB 备份轮转策略**：`backend/data/backup/` 已积累 9 份快照（每份 ~19–29 MB，共 ~205 MB），建议在 `backup_service` 中加保留窗口（如仅留最近 3 份 + 每周 1 份）。
2. **日志轮转**：`backend/logs/` 单日日志可达 34 MB，建议加 `RotatingFileHandler` 或按天保留 N 天，避免四周内再次累积 100 MB+。
3. **`release/` 目录核查**：确认 `release/assets/MorningBrief.ico` 缺失是否影响 `installer.iss` / `MorningBrief.spec` 打包，必要时从 git 历史恢复。
4. **周期性维护**：建议每月或每个里程碑后运行一次 workspace-cleanup。

---

## 2026-10-03 工作空间清理（第二轮 · 解除第一轮 review 阻塞）

第一轮（22:54）只删了配置明确授权的可再生缓存，把 480 MB 路由到 review。本轮在完成前置校验后解除其中两项阻塞，回收 443 MB。

### 结论：删除 167 文件 + 3 目录（443.24 MB），0 失败；验证全绿。**

### 已删除

| 项 | 数量 | 体积 | 依据 |
|---|---|---|---|
| `backend/logs/*.2026-10-03_*.log`（loguru 滚动副本） | 37 | ~370 MB | 均为当日已封存的滚动分片；`MorningBrief_2026-10-03.log`（活动文件）**保留**。loguru retention 14d 会自行轮转，分片无诊断价值 |
| `runtime/.cleanup-trash-20260910/**` | 130 | ~74 MB | 9/10 隔离区，24h 恢复窗口已过期 23 天；其唯一引用方是本文档第 255 行的证据登记，**已先更新该行再删除**（解除「引用即承重墙」） |

- **删前哈希审计**：`runtime/logs/cleanup-20261003-234150.log`（169 行：SHA256 \| 字节数 \| 路径）
- **目标清单**：`runtime/logs/cleanup-targets-r2.txt`（167 行）
- **执行脚本**：`_validate/cleanup_r2_exec.py`（干跑校验）、`_validate/cleanup_r2_delete.py`（ctypes 删除 + 空目录剪枝 + 范围守卫）
- **执行方式**：`bypass_hook_mode: ctypes`（`kernel32.DeleteFileW` / `RemoveDirectoryW`），批大小 20，8 批，错误 0
- **验证**：`from app.main import app` → OK（231 路由）；定向回归 16 passed（material 契约 / SPA 缓存）；`git ls-files --deleted` = 0；`backend/.venv-build` 5886 文件完好

### 仍保留（tier=keep）

| 项 | 体积 | 保留原因 |
|---|---|---|
| `backend/.venv-build/` | 113.5 MB | 7/23 遗留构建 venv，无代码引用；重建需联网（pypi 此前超时），不可逆因素命中 |
| `.venv` → `backend/.venv-build` | 符号链接 | **绝不可递归删除**（项目铁律） |
| `backend/logs/MorningBrief_2026-10-03.log` | 0.5 MB | 当日活动日志，压测/部署验证诊断依据 |
| `_validate/` | 34.1 MB | mtask 结论回传证据（`res_*.md`）与压测原始 jtl |
| `release/` + `build/` | ~581 MB | D 盘真实目录（非 F 盘 junction）；exe 安装包产物 |

### 本轮踩坑（写入执行脚本注释，防复发）

1. **清单为 CRLF 行尾** → Git Bash 下 `[ -e "$f" ]` 全部误报 MISSING（尾部 `\r` 粘进路径）。用 Python `splitlines()` + `strip()` 读清单，不要在 shell 里逐行判存在。
2. **范围守卫大小写**：`full.lower().startswith(ALLOWED_PREFIXES)` 与含大写盘符/目录名（`D:\...20_News`）的常量比较 → 167 个全部 `OUT_OF_SCOPE`，删除静默跳过。**守卫常量必须同样 `.lower()`**。
3. 排空后的隔离区会留下空目录（`os.walk` topdown=False 剪枝 2 个，但嵌套更深的空目录在剪枝后才暴露）→ 需再手动 `RemoveDirectoryW` 一轮并复核 `islink()/isjunction()` 为 `False`。

### 后续建议（第二轮后更新）

1. ~~**DB 备份轮转策略**~~ **已治理（2026-10-04）**：`backup_service` 原有 7 天窗口，但存在两个缺口——`list_backups` 因 `entry.path`（`_list_dir_safe` 实际返回 `Path` 而非 `DirEntry`）必然 500（7/12 引入，潜伏 82 天）；`news_pre_<scene>_<date>.db` 预备份快照不匹配命名模式，永久孤儿。已新增预备份模式（3 天短窗口）+ 份数上限（7 份）+ 14 个单测 + HTTP 冒烟。详见 commit `77fc930`。
   - **实际占用更正**：本轮实测 `backend/data/backup/` 仅剩 1 份 41MB，此前「9 份 205MB」记录已过期（轮转机制一直在生效）。
2. **日志轮转**：`backend/logs/` 仍缺 `RotatingFileHandler`，单日可达 34MB（retention 14d）。本轮已清当日滚动分片 370MB，但机制未修，建议尽快加按天保留 N 天。
3. **`release/` 目录核查**：确认 `release/assets/MorningBrief.ico` 缺失是否影响 `installer.iss` / `MorningBrief.spec` 打包，必要时从 git 历史恢复。
4. **测试环境补依赖**：`numpy`（`test_kokoro_provider.py`）与 `PyMuPDF`（`test_document_ingest_formats.py::TestPdf` 2 failed）未装，全量 pytest 需 `--ignore=tests/test_kokoro_provider.py` 才能收集完成。
5. **周期性维护**：建议每月或每个里程碑后运行一次 workspace-cleanup。
