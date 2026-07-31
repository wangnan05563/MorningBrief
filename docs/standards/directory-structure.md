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
