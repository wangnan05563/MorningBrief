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
