# 20_News 工作空间清理报告

- **执行时间**：2026-09-10 12:34 – 16:10 (GMT+8)
- **轮次**：周期性维护 · 第三轮（前两轮 2026-07-23 / 2026-08-14）
- **执行规范**：workspace-cleanup skill（Recon → Classify → Impact → Execute → Verify → Archive）
- **配置**：`cleanup-config.yaml`
- **提交**：`68c73b4` chore(cleanup): 工作空间清理第三轮 + .gitignore 防复发规则

---

## 1. 总览

| 指标 | 数值 |
|---|---|
| 直接删除文件 | **392** |
| 删除目录 | **29** |
| 隔离（移动）文件 | **129**（含 `dist/` 109 个） |
| 释放空间 | **114.47 MB** |
| 根目录文件数 | 9 → **6** |
| 被跟踪文件删除 | 10（已 `git rm --cached`） |
| 验证结果 | **PASS**（语法 0 错误 / 应用导入 OK） |

---

## 2. 按类型分类的已清理统计

| 类型 | 文件数 | 大小 (MB) | 占比 |
|---|---:|---:|---:|
| `.log`（运行日志） | 8 | 107.21 | 93.7% |
| `.pyc`（Python 字节码） | 259 | 3.10 | 2.7% |
| `.txt`（pytest 临时/调试输出） | 37 | 0.52 | 0.5% |
| `.json`（pytest 临时/上轮审计） | 29 | 0.11 | 0.1% |
| `.png`（调试截图） | 2 | 0.10 | 0.1% |
| `.py`（一次性脚本/缓存） | 21 | 0.05 | <0.1% |
| `.mjs`（Vite 临时配置） | 5 | 0.05 | <0.1% |
| 无扩展名（pytest 临时 fixture） | 7 | 0.04 | <0.1% |
| 其他（`.ps1` `.err` `.out` `.lock` `.TAG` `.gitignore` `.env` `.exe` `.dll` `.zip` `.yaml` `.md` 等） | 56 | <0.05 | <0.1% |
| **合计** | **412 + 109** | **~114.47** | 100% |

> 说明：`.env`(12) / `.exe`(8) / `.dll`(4) / `.zip`(4) 等零字节项均位于 `backend/.pytest_tmp/` 内的测试 fixture 沙盒中，非真实凭据或二进制。

### 按 Tier 分类

| Tier | 风险级别 | 文件数 | 大小 (MB) | 处置方式 |
|---|---|---:|---:|---|
| A | 零风险（可完全再生缓存） | 372 | 3.15 | 直接删除 |
| B | 低风险（运行日志） | 10 | 106.52 | 直接删除 |
| C | 低风险（调试产物） | 10 | 0.05 | 直接删除 |
| D | 中风险（一次性脚本/审计产物/构建产物） | 129 | 4.75 | **隔离 24h** |
| **合计** | | **521** | **114.47** | |

---

## 3. 按目录分类的存储空间释放

| 目录 | 文件数 | 释放 (MB) | 主要内容 |
|---|---:|---:|---|
| `backend/` | 376 | 109.64 | 22 个 `__pycache__/`、`.pytest_tmp/`、5 个运行日志、`fix_client.py`、`backend/temp/` |
| `apps/` | 116 | 3.32 | `admin-web/dist/`（109）、Vite 临时配置 ×5、`_clean_tmp.py`、`test-last-run.txt` |
| `runtime/` | 17 | 1.50 | 上轮清理审计产物 ×9、`stats_page_*.png` ×2、`service-error.log` 等 |
| 根目录文件 | 3 | <0.01 | `_sonar_issues.py`、`_es_query.json`、`_diag_build.ps1`（空） |
| `__pycache__/`（根） | 1 | 0.01 | 根级 `MorningBrief.cpython-313.pyc` |
| `temp/` | 1 | 0.01 | `test_bgm_overlay_e2e.py` |
| `.pytest_cache/` | 4 | <0.01 | 根 pytest 缓存 |
| `.run/` | 1 | <0.01 | `test_token.txt` |
| `.scannerwork/` | 2 | <0.01 | Sonar 扫描残留 |
| `pytest-cache-files-bdlg3fu2/` | 0 | 0 | 空目录 |
| **合计** | **521** | **114.47** | |

### 目录删除清单（29 个）

- `backend/` 下 22 个 `__pycache__/`
- 根 `__pycache__/`、`.pytest_cache/`、`.scannerwork/`、`pytest-cache-files-bdlg3fu2/`
- `backend/.pytest_cache/`、`backend/.pytest_tmp/`、`backend/.tmp/`
- `temp/`、`backend/temp/`

---

## 4. 清理前后工作空间占用对比

| 指标 | 清理前 | 清理后 | 变化 |
|---|---:|---:|---:|
| 工作空间总占用（排除 `.git`） | ≈ 1458.6 MB | ≈ 1344.1 MB | **−114.47 MB（−7.8%）** |
| 根目录文件数 | 9 | 6 | −3 |
| 全仓 `.pyc` 文件数 | 259 | 0 | −259 |
| `__pycache__/` 目录数（排除 venv） | 23 | 0 | −23 |
| `backend/logs/` 日志文件数 | 5 | 0 | −5 |
| `apps/admin-web/dist/` | 存在（3.27 MB） | 已隔离 | — |

---

## 5. 未清理的风险文件列表及原因

| 路径 | 大小 | 原因 | 建议 |
|---|---:|---|---|
| `backend/data/backup/`（9 个 DB 快照） | ~205 MB | **用户数据**。`backup_service` 自动轮转产物，无保留策略，删除不可逆 | 确认保留窗口后由用户在 `backup_service` 中加轮转策略，或单独授权清理 |
| `backend/data/news.db.bak_constraint_drop` | 22 MB | **用户数据**。2026-08-19 手工兜底备份，可能仍有回滚价值 | 确认约束变更已稳定后可删 |
| `backend/fix_client.py` | 9.7 KB | untracked 一次性修复脚本（2026-08-17），功能归属不明 | 已隔离至 `runtime/.cleanup-trash-20260910/`，24h 内可恢复；请确认是否仍需 |
| `backend/run_test.py`、`build_info.py`、`seed_*.py`、`launcher.py` | ~15 KB | 已纳入版本控制的根级工具脚本，属源码而非垃圾 | 保留 |
| `release/assets/MorningBrief.ico` | — | **本轮之前即已缺失**（`git ls-files --deleted` 可见，不在本轮目标清单内），且整个 `release/` 目录当前不存在 | **需人工核查**：确认是否影响 `installer.iss` / `MorningBrief.spec` 打包 |
| `backend/data/`（`news.db` 40 MB、`bgm/`、`avatars/`、`ai_budget.json`、`tunnel_config.json`） | ~140 MB | 运行时用户数据与素材 | 保留（preserve_roots） |
| `backend/ffmpeg/` | 175 MB | 运行时依赖（音频处理二进制） | 保留（preserve_roots） |
| `build/` | 52.8 MB | PyInstaller 中间产物，**今日 09:51 刚构建** | 保留（preserve_roots，活跃构建中） |
| `runtime/data/`（cloudflared/cpolar 二进制） | 72 MB | 内网穿透运行时二进制 | 保留（preserve_roots） |
| `.trae/`、`.workbuddy/`、`.github/`、`.venv*`、`node_modules/`×2 | ~270 MB | 活跃 skill 源 / 规则目录 / 依赖 | 保留（禁止清理） |

---

## 6. 服务状态（Phase 3 · 四重检测）

| 检测项 | 结果 |
|---|---|
| PID 文件 | `runtime/logs/web.pid`、`app.pid` 均不存在；`.run/20-news.pid` 内容 `17140` → 进程不存在（陈旧残留） |
| 端口监听 | 8000 / 8080 / 5000 **均无 LISTENING** |
| 进程名 | 存在大量 `node` / `python` 进程，经核实属 IDE 与工具链自身，非本项目后端服务 |
| 文件占用 | `backend/logs/*.log`、`runtime/logs/service-error.log` 均 `not locked` |
| 特殊文件名 | 无 |
| **结论** | 服务已停止，可安全执行；`.run/20-news.pid` 被非服务句柄持有，本轮跳过 |

---

## 7. 验证结果（Phase 5）

| 项 | 结果 |
|---|---|
| 语法完整性 | `backend/app` + `backend/tests` 共 **244 个 `.py` AST 解析 0 错误**（`utf-8-sig` 处理 BOM）✓ |
| 应用导入冒烟 | `.venv\Scripts\python.exe -B -c "from app.main import app"` → **import OK，199 条路由，4.83s，exit=0** ✓ |
| pyc 未复生 | 导入后 `__pycache__` 计数 = **0**（`-B` 生效）✓ |
| 稳定性复扫 | 6s 后复扫：`__pycache__`=0、`backend/logs`=0、根 `__pycache__`=0 ✓ |
| 根目录文件 | 9 → 6 ✓ |
| 源码零损失 | 244 个后端 `.py` + 前端/小程序源码未触碰 ✓ |
| 用户数据零触碰 | `backend/data/` 全部 intact ✓ |
| 保留根零触碰 | `build/`、`release/`、`runtime/data/`、`node_modules/`×2、`backend/ffmpeg/`、`.trae/`、`.workbuddy/`、`.venv*` ✓ |

> 回滚参考：`on_failure` → 检查 `runtime/logs/cleanup-20260910-audit.log` 的 hash 记录；隔离项从 `runtime/.cleanup-trash-20260910/` 原样移回；已跟踪文件用 `git checkout 68c73b4^ -- <file>` 恢复。

---

## 8. 防复发归档（Phase 6）

### 8.1 `.gitignore` 新增规则（8 条）

| 规则 | 补齐的缺口 |
|---|---|
| `vite.config.js.timestamp-*.mjs` | **修正旧规则缺陷**：原 `admin-web/vite.config.js.timestamp-*.mjs` 含斜杠被锚定到仓库根，未命中 `apps/admin-web/` 层级 → 本轮 5 个文件曾被跟踪 |
| `/pytest-cache-files-*/` | 根目录 pytest 随机后缀临时目录（`.pytest_cache/` 规则不覆盖） |
| `.pytest_tmp/` | backend pytest 临时目录 |
| `/_*.json`、`/_*.txt` | 已有 `/_*.py`、`/_*.ps1`，补齐 json / txt |
| `test-last-run.txt` | 前端测试运行残留（本轮 1 个文件曾被跟踪） |
| `/.run/` | 运行态 pid / 临时 token 目录 |
| `runtime/.cleanup-trash-*/` | 未来清理隔离区，防止误入库 |

### 8.2 pre-commit

`.pre-commit-config.yaml` 在本仓库**不存在**（项目未启用 pre-commit），故未生成钩子。防复发当前依赖 `.gitignore` + `.github/workflows/ci.yml`。如需强制拦截，建议后续引入 `pre-commit` 或复用现有 CI。

### 8.3 变更记录

已追加至 `docs/standards/directory-structure.md`（「2026-09-10 工作空间清理（周期性维护 · 第三轮）」章节）。

### 8.4 版本库历史垃圾处理

本轮清理的 10 个曾被跟踪文件已通过 `git rm --cached` 从索引移除并随本次提交生效。其中 5 个 Vite 临时配置历史体积很小（各 ~9.5 KB），无需 `export-ignore`；如后续出现大体积历史垃圾，建议用 `.gitattributes` + `export-ignore` 或 `git filter-repo` 处理。

### 8.5 提交

```
68c73b4  chore(cleanup): 工作空间清理第三轮 + .gitignore 防复发规则
         12 files changed, 106 insertions(+), 776 deletions(-)
```

> 附带修复：清除了 `.git/index.lock`（2026-08-22 遗留的 19 天陈旧空锁，0 字节，无 git 进程持有），该锁此前一直阻塞所有 git 写操作。

---

## 9. 可追溯性产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 删前哈希审计 | `runtime/logs/cleanup-20260910-audit.log` | 412 行：`SHA256 \| BYTES \| TIER \| ACTION \| PATH` |
| 目标清单 | `runtime/logs/cleanup-targets-20260910.txt` | 全部去重路径 |
| 执行计划 | `runtime/logs/cleanup-plan-20260910.json` | 含 Tier/Action 结构 |
| 隔离区 | `runtime/.cleanup-trash-20260910/` | 21 项，24h 恢复窗口 |
| 执行脚本 | `runtime/logs/wscleanup-exec-20260910.ps1` | 6 个幂等动作 |
| JSON 报告 | `reports/workspace-cleanup-20260910.json` | 机器可读 |

---

## 10. 后续建议

1. **DB 备份轮转策略**：`backend/data/backup/` 已积累 9 份快照（~205 MB），建议在 `backup_service` 中加保留窗口（如最近 3 份 + 每周 1 份）。
2. **日志轮转**：`backend/logs/` 单日日志可达 34 MB，建议加 `RotatingFileHandler` 或按天保留 N 天。
3. **`release/` 目录核查**：确认 `release/assets/MorningBrief.ico` 缺失是否影响打包链路。
4. **周期性维护**：建议每月或每个里程碑后运行一次 workspace-cleanup。
