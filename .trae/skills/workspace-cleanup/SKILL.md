---
name: workspace-cleanup
description: Use when cleaning up project workspaces, removing garbage files, organizing scattered scripts, or establishing file classification standards. Triggers on requests like "clean up the workspace", "organize the project structure", "centralize scripts into scripts/ directory", "remove junk files", or "建立文件分类标准". Config-driven, parameterized, no hardcoded paths.
---

# Workspace Cleanup

## Overview

工作空间清理是一项**周期性维护任务**，不是一次性清理。同一项目可能需要 3-5 轮迭代才能稳定下来。

**核心原则：**
- **配置驱动**：所有规则（路径、后缀、白名单）通过 YAML 配置管理，零硬编码
- **安全优先**：删除前必须先备份 hash，清理后必须验证应用完整性
- **6 阶段闭环**：Recon → Classify → Impact → Execute → Verify → Archive

**Violating the letter of this process is violating the spirit of cleanup.**

## The Iron Law

```
NO DELETION WITHOUT CONFIG-DRIVEN CLASSIFICATION FIRST
NO ARCHIVE WITHOUT POST-CLEANUP VERIFICATION
```

## When to Use

**Use for:**
- 长期维护的项目根目录污染（重定向产物、调试脚本、测试输出、缓存目录）
- 脚本文件散落在各子目录（应统一到 `scripts/`）
- 周期性预防性维护（每周/每月跑一次）
- 初次接手项目时的结构梳理
- 重构后批量重新分类

**Use this ESPECIALLY when:**
- 服务运行中持续产生新垃圾（必须先停服务）
- 根目录文件数 > 30（含可疑）
- 团队成员多次反馈"项目结构混乱"
- 准备做大型重构或迁移前的整理

**Don't skip when:**
- 看似"只删几个文件"（删除决策应可追溯）
- 用户说"就快速清一下"（快速 = 误删风险高）
- 已经做过清理了（周期性维护，每轮都可能发现新问题）

## Configuration

**Required:** Read the user's `cleanup-config.yaml` first. If not provided, fall back to [examples/cleanup-config.example.yaml](file:///d:/code/otherProjects/17_xianyu/.trae/skills/workspace-cleanup/examples/cleanup-config.example.yaml).

**Configuration has 10 sections:**

1. `workspace` — 根目录、脚本目录、文档目录、日志目录、前端目录
2. `root_allowlist` — 根目录允许的文件（按扩展名 + 文件名 + 允许的根脚本）
3. `script_extensions` — 脚本文件后缀（.py/.ps1/.bat 等）+ 排除目录
4. `garbage_patterns` — 垃圾文件模式（重定向产物、临时后缀、缓存目录、运行时日志、skill 调试产物、前端调试产物等）
5. `detection` — 模式推断配置（配置缺失时基于文件名特征自动识别垃圾）
6. `service_indicators` — 服务状态检测（PID 文件 + 端口 + 进程名 + 文件占用探测）
7. `stability_check` — 稳定性检查（检测后台进程持续创建文件）
8. `platform` — 跨平台命令配置（Windows/Linux/macOS 命令变体）
9. `verification` — 清理后验证（核心模块导入 + 失败回滚建议）
10. `archive` + `safety` — 归档配置（.gitignore + pre-commit + changelog）+ 安全配置

**配置加载优先级：**
1. 用户 `cleanup-config.yaml`（优先级最高）
2. `examples/cleanup-config.example.yaml`（fallback）
3. 都缺失则 STOP，要求用户提供

详见 [references/decisions.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/workspace-cleanup/references/decisions.md) 中的 7 个判断逻辑。

---

## The Six Phases

You MUST complete each phase before proceeding to the next. Output a phase report at the end of each.

### Phase 1: Recon（侦察）

**Goal:** Collect ground truth. NO deletions in this phase.

1. **List root directory files** with sizes:
   - Tool: `Get-ChildItem -File` (Windows) 或 `ls -la` (Linux/macOS)
   - **注意**：LS 工具有 40000 字符截断限制，文件数多时改用 PowerShell/Bash 命令
   - Record: filename, size (KB), extension, mtime

2. **List subdirectories** at depth 1-2 for orphan script detection:
   - Exclude: `node_modules/`, `.venv/`, `.git/`, `__pycache__/`
   - 同时扫描 `workspace.frontend_dir`（若配置非空）

3. **Identify all `.gitignore` rules** that should already cover garbage:
   - Read `.gitignore`
   - Compare with what's actually present
   - 记录 gaps（已有规则未覆盖的垃圾文件）

4. **Apply Decision 7（模式推断，若 `detection.enabled: true`）**:
   - 对未匹配 `garbage_patterns` 的根目录文件
   - 检查 `detection.prefix_indicators`（如 `_` / `.tmp_` 前缀）
   - 检查 `detection.name_keywords`（如 debug/diag/trace/verify）
   - 检查 `detection.name_patterns`（如 `test_*.py` / `run_*.py`）
   - 计算置信度，低于 `infer_confidence_threshold` 仅标记为"疑似垃圾"

5. **Output:** A complete file inventory table + 疑似垃圾清单.

**Phase 1 Report:**
```
=== Phase 1: Recon ===
Root files: N (含 K 个配置已覆盖 + L 个模式推断)
Subdir scripts: M
Frontend files: F (若 frontend_dir 配置非空)
Gitignore gaps: G
Inferred garbage: I (置信度分布: high/medium/low)
```

### Phase 2: Classify（归类）

**Goal:** For each file in root, decide its category using config.

1. **Apply Decision 1** (is it garbage?):
   - Match against `garbage_patterns.redirect_artifacts`
   - Match against `garbage_patterns.tmp_suffixes`
   - Match against `garbage_patterns.test_outputs`
   - Match against `garbage_patterns.cache_dirs`
   - If in root and NOT in `root_allowlist` → marked as "scattered"

2. **Apply Decision 2** (is it a script?):
   - For files NOT in `root_allowlist` and in root or scattered subdirs
   - Check `script_extensions` and `script_exclude_dirs`

3. **Compute hash for any file marked Delete or Move**:
   - Tool: `Get-FileHash` (Windows) or `sha256sum` (Linux)
   - Write to `logs/cleanup-{YYYYMMDD-HHmmss}.log`

4. **Output:** Classification table with 3 columns: Action (Delete/Move/Keep), Reason, Target.

**Phase 2 Report:**
```
=== Phase 2: Classify ===
Delete: X files
Move:   Y files
Keep:   Z files
Backup log: logs/cleanup-...log
```

### Phase 3: Impact（影响评估）

**Goal:** Verify it's safe to delete/move. Check service state.

1. **Apply Decision 3** (四重服务检测):
   - **检测 1: PID 文件** — Check `service_indicators.pid_files` for PID file existence
     - 若有 PID 文件 → 读取 PID → 验证进程存在
     - PID 文件存在但进程已死 → 记录 "stale PID file" 警告
   - **检测 2: 端口监听** — Check `service_indicators.ports` via `netstat` / `lsof` / `ss`
   - **检测 3: 进程名** — Check `service_indicators.process_names` / `process_name_patterns`
   - **检测 4: 文件占用探测** — Check `service_indicators.file_occupancy_probes`
     - 这些文件被占用则视为服务运行（作为 PID 文件缺失的兜底）
     - 用 `platform.commands.file_occupancy_check` 检测

2. **If service running** AND `safety.require_stopped_service: true`:
   - **STOP and ask user** whether to:
     a. Stop service first (recommended)
        - 用 `platform.commands.stop_process` 停止进程
        - 停止后重新检测端口释放 + 文件解锁
        - 补算被占用文件的 hash
     b. Soft-delete (rename to `safety.soft_delete_delete_suffix` instead of hard delete)
     c. Skip Move operations, only do safe Delete
     d. Cancel cleanup

3. **异常文件名检测**（Apply Decision 6）:
   - 扫描待删除文件中是否有含特殊字符的文件名
   - 若有且 `safety.special_filename_handling: "safe"`，标记需用 Get-ChildItem 匹配

4. **Output:** Service state + decision request + 异常文件名清单.

**Phase 3 Report:**
```
=== Phase 3: Impact ===
Service running: yes/no (检测来源: PID/端口/进程名/文件占用)
Stale PID files: list
Locked files: list (file_occupancy_probes 检测结果)
Special filenames: list (需 safe 模式处理的文件)
Action: [proceed / wait for user / soft-delete mode]
```

### Phase 4: Execute（执行）

**Goal:** Apply the classification. Atomic per category.

**Execution order** (lowest risk first):

1. **Cache directories** (lowest risk, easily regenerated):
   - 用 `platform.commands.remove_dir` 删除每个 `cache_dirs` 条目

2. **Redirect artifacts & tmp files** (next, low value):
   - 用 `platform.commands.remove_file` 删除每个匹配
   - **异常文件名处理**（Apply Decision 6）:
     - 若 `safety.special_filename_handling: "safe"`
     - 用 `Get-ChildItem -File | Where-Object { $_.Name -like "<pattern>" }` 匹配
     - 删除时用 `Remove-Item -LiteralPath $file.FullName -Force`

3. **Test outputs** (low value, debug only):
   - 用 `platform.commands.remove_file` 删除每个匹配

4. **Move scripts to `script_dir`**:
   - For each scattered script: `Move-Item` to `{script_dir}/`
   - Handle name conflicts: prompt user or auto-rename with suffix

5. **Last: Delete high-confidence root files**:
   - Only files matching explicit `garbage_patterns` 或 `detection` 推断（置信度 ≥ threshold）
   - If `min_confidence_to_delete` < 1.0, prompt user
   - 大文件（> `safety.large_file_threshold_mb`）需二次确认

**Batching:** Respect `safety.max_files_per_batch`. If exceeded, batch and confirm between batches.

**每批删除后验证**（若 `safety.verify_after_each_batch: true`）:
   - 立即检查删除结果是否匹配预期
   - 用 `Test-Path` 验证文件已被删除
   - 记录精确的删除清单（哪些文件在哪个批次被删除）

**PowerShell 脚本注意事项：**
- 使用简单变量而非哈希表（`$script:deletedCount++` 而非 `$stats.Deleted++`）
- 变量后跟 `:` 时用 `${var}` 包裹（如 `"Port ${port}: not listening"`）
- 用 `-LiteralPath` 而非 `-Path` 防止通配符被二次解析

**稳定性检查**（Apply Decision 5，若 `stability_check.enabled: true`）:
   - 删除完成后记录文件快照 `snapshot_after`
   - 等待 `stability_check.wait_seconds` 秒
   - 复扫根目录 `snapshot_now`
   - 比较 `snapshot_now - snapshot_after`，检测新创建的文件
   - 匹配 `recurrence_patterns` 判断是否为已知后台进程产物
   - 按 `recurrence_action`（warn/stop/soft_delete）策略处理
   - 超过 `max_recurrence` 强制停止，提示用户排查后台进程

**Phase 4 Report:**
```
=== Phase 4: Execute ===
Deleted: X files (freed NN MB)
Moved:   Y files
Errors:  Z (with reason)
Batch details:
  Batch 1 (cache dirs): N deleted
  Batch 2 (redirect+tmp): N deleted
  Batch 3 (test+sonar): N deleted
  Batch 4 (runtime+frontend): N deleted
Stability check:
  New files after wait: K (matched recurrence_patterns: Y/N)
  Action: [proceed / warn / stop]
```

### Phase 5: Verify（验证）

**Goal:** Confirm cleanup didn't break the application.

1. **Run the verification command** from config:
   - 用 `platform.venv_python` 选择对应平台的 Python 路径
   - PowerShell: `& {venv_python} -c "<python_imports joined>"`
   - Bash: `{venv_python} -c "<python_imports joined>"`

2. **Read the output and exit code**:
   - Exit 0 + no error output = pass
   - Exit non-zero or error = STOP and report

3. **If verification fails:**
   - DO NOT proceed to Phase 6
   - Output the failure details
   - 按 `verification.on_failure` 建议回滚:
     - 检查 `logs/cleanup-*.log` 中的 hash 记录
     - 从 git 历史恢复误删文件：`git checkout HEAD -- <file>`
     - 重新生成缓存目录：`pytest --cache-clear` / `sonar-scanner`

4. **完整性检查清单**（Apply Decision 4）:
   - [ ] 核心模块导入成功（退出码 0）
   - [ ] 根目录文件数符合预期（before → after）
   - [ ] scripts/ 目录文件数符合预期（若执行了 Move）
   - [ ] frontend 目录文件数符合预期（若扫描了 frontend）
   - [ ] 无文件被意外删除（对比 backup_log 中的 hash 记录）

5. **Optional but recommended: run tests** (if `tests/` exists):
   - `pytest` for Python projects
   - `npm test` for Node projects

**Phase 5 Report:**
```
=== Phase 5: Verify ===
Import check: PASS/FAIL (output: ...)
Test run:    PASS/FAIL/SKIP
Integrity checklist:
  [✓] Core module import
  [✓] Root file count: A → B
  [✓] scripts/ count: C → D
  [✓] frontend count: E → F
  [✓] No accidental deletion
Rollback suggestions: (if FAIL)
```

### Phase 6: Archive（归档）

**Goal:** Make cleanup durable. Prevent recurrence.

1. **Update `.gitignore`** if `archive.auto_update_gitignore: true`:
   - For each new pattern in `garbage_patterns` that wasn't already ignored
   - Group by category with comments

2. **Update `.pre-commit-config.yaml`** if `archive.auto_update_precommit: true`:
   - Add or update hook to detect forbidden files
   - Match the new `.gitignore` rules

3. **Update changelog** at `archive.changelog_path`:
   - Add a "Round N" section with:
     - Date
     - Background
     - Cleanup actions table
     - Verification results
     - Files added (config, new scripts)

4. **Output final report** with:
   - Total files cleaned
   - Space freed
   - Root file count (before → after)
   - Scripts count (before → after)
   - Verification status
   - Recurrence prevention (new gitignore rules)

**Phase 6 Report:**
```
=== Phase 6: Archive ===
Gitignore rules added: N
Pre-commit hooks updated: yes/no
Changelog updated: path
Total freed: NN MB
Root files: A → B
```

---

## Red Flags - STOP

- Starting Phase 4 without finishing Phase 1-3 reports
- Deleting files without writing hash to backup log
- Skipping Phase 5 because "it should be fine"
- Hardcoding paths instead of using config
- Adding files to `.gitignore` without also updating pre-commit
- Service running but proceeding to Phase 4 anyway
- One-shot bulk delete of > 20 files without batching
- "User said clean it up" interpreted as "delete everything I didn't write"
- **Using PowerShell `$var:` without `${var}` wrapping**（驱动器引用陷阱）
- **Using hashtable `$stats.Errors++` in strict mode**（PropertyNotFound 陷阱）
- **Using direct path strings for special filenames**（应用 safe 模式）
- **Ignoring stability check warnings**（后台进程持续创建文件）
- **Skipping file occupancy check when PID files missing**（服务检测盲区）

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "I know what's garbage" | Run Phase 1-2 anyway, evidence > intuition |
| "It's only temp files" | Hash them first, logs prove you did |
| "Service probably stopped" | CHECK with PID + port, don't guess |
| "Verification is overkill" | One import line is cheaper than debugging a broken app |
| "Just this once, no config" | Future-you will re-clean without knowing patterns |
| "User is in a hurry" | Dry-run is faster than redoing because of mistakes |
| ".gitignore can wait" | Recurrence happens within 24 hours without it |

## When NOT to Use

| Scenario | Reason | Alternative |
|---|---|---|
| Empty repo | Nothing to clean | Skip this skill |
| Monorepo single package | Root-only assumption breaks | Per-package cleanup |
| 24/7 production service | Can't stop | Soft-delete mode (rename `.trash`) |
| Team > 20 people | Conflicts with others' cleanup | PR-based cleanup |
| Large binaries in root | Delete = redownload | Force explicit confirmation |
| macOS/Linux only (no Windows) | Path syntax differs | Use `platform.commands` 配置 |
| **Concurrent AI sessions** | 后台进程持续创建文件，清理"复发" | 先排查并停止所有后台会话 |
| **Config 未覆盖的新型调试产物** | garbage_patterns 无法穷举 | 启用 `detection` 模式推断 |
| **Special character filenames** | 直接路径字符串失败 | 使用 `safe` 模式（Get-ChildItem 匹配） |

See [references/retrospective.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/workspace-cleanup/references/retrospective.md) Sections 4-5 for full applicability analysis.

---

## Key Patterns

**Config-driven scan:**
```
✅ Read cleanup-config.yaml → Apply patterns → Report
❌ "I see <project_name> is junk, delete it" (without checking config)
```

**Backup before delete:**
```
✅ Get-FileHash X | Tee-Object cleanup.log → Remove-Item X
❌ "Remove-Item X" (no backup)
```

**Service check:**
```
✅ Test-Path logs/web.pid; netstat -aon | Select-String ":8000.*LISTENING"
❌ "Service probably not running"
```

**Verification:**
```
✅ Run `import xianyu_hunter` → See exit 0 → Report PASS
❌ "Code looks fine, should work"
```

**Recurrence prevention:**
```
✅ Update .gitignore + pre-commit + changelog (all three)
❌ "Cleaned up, done" (without gitignore)
```

---

## Quick Reference

**Most common cleanup actions** (top 80% cases):

| Pattern | Action | Reason |
|---|---|---|
| `<project_name>`, `<project_name>frontend`, `0`, `_r.json` | Delete | PowerShell 误重定向 |
| `*.tmp`, `*.bak`, `*.txtcd`, `*.orig` | Delete | 异常命名后缀 |
| `pytest_output.txt`, `test_result.txt` | Delete | 测试输出散落根目录 |
| `check-scan*.ps1`, `query-*.ps1` | Delete | SonarQube 一次性调试脚本 |
| `.scannerwork/`, `sonar-results/`, `.pytest_cache/` | Delete | 缓存目录（可重建） |
| `scripts/` 外的 `.py`/`.ps1`/`.bat` | Move to `scripts/` | 脚本集中化 |
| `docs/` 副本与根目录重名 | Delete root copy | 哈希去重后保留 docs/ 版本 |
| `test_*.py`, `run_*.py/js` (根目录) | Delete | 临时调试脚本（detection 推断） |
| `_*.log`, `_*.txt` (根目录) | Delete | _ 前缀调试输出（detection 推断） |
| `git_*.py/txt`, `verify_*.py/txt` | Delete | git/验证调试产物（detection 推断） |
| `run.stdout.log`, `run.stdout.*.log` | Delete | 运行时日志（服务持续写入） |
| `compare_*.ps1`, `do_git_commit.ps1` | Delete | skill 集成调试产物 |

---

## PowerShell 脚本陷阱与最佳实践

### 1. 变量引用陷阱

```powershell
# ❌ 错误：$port: 被解析为驱动器引用
"Port $port: not listening"

# ✅ 正确：用 ${} 包裹变量名
"Port ${port}: not listening"
```

### 2. 哈希表 strict mode 陷阱

```powershell
# ❌ 错误：strict mode 下属性递增报错 PropertyNotFound
$stats = @{ Deleted=0; Errors=0 }
$stats.Errors++  # 报错

# ✅ 正确方案 1：用简单变量
$script:deletedCount = 0
$script:errorCount = 0
$script:deletedCount++

# ✅ 正确方案 2：用 [PSCustomObject]
$stats = [PSCustomObject]@{ Deleted=0; Errors=0 }
$stats.Errors++  # 正常工作
```

### 3. 异常文件名处理

```powershell
# ❌ 错误：直接路径字符串在含特殊字符时失败
$p = Join-Path $root "not enabled, try to fix it now."
Remove-Item $p  # 可能失败

# ✅ 正确：Get-ChildItem + Where-Object 匹配
$odd = Get-ChildItem -Path $root -File | Where-Object { $_.Name -like "not enabled*" }
if ($odd) { Remove-Item -LiteralPath $odd.FullName -Force }
```

### 4. 文件占用检测

```powershell
# ✅ 检测文件是否被进程持有（作为服务运行的间接证据）
function Test-FileLocked {
  param([string]$Path)
  try {
    $stream = [System.IO.File]::Open($Path, 'Open', 'Read', 'None')
    $stream.Close()
    return $false  # 未被锁定
  } catch {
    return $true   # 被锁定
  }
}
```

### 5. 跨平台命令选择

根据 `platform.current` 配置选择命令变体：
- `windows`: `Get-ChildItem`, `Get-FileHash`, `netstat`, `Stop-Process`
- `linux`/`macos`: `ls`, `sha256sum`/`shasum`, `ss`/`lsof`, `kill`

---

## 配置缺失时的降级策略

### 配置加载优先级

1. 用户 `cleanup-config.yaml`（优先级最高）
2. `examples/cleanup-config.example.yaml`（fallback）
3. 都缺失则 STOP，要求用户提供

### 配置不完整时的降级

| 缺失配置 | 降级策略 | 影响 |
|---|---|---|
| `garbage_patterns` 部分类别 | 启用 `detection` 模式推断 | 覆盖面降低，需用户确认 |
| `service_indicators.file_occupancy_probes` | 仅用 PID + 端口 + 进程名检测 | 服务检测盲区增大 |
| `stability_check` | 跳过稳定性检查 | 无法检测后台进程复发 |
| `platform.commands` | 默认 Windows 命令 | 跨平台兼容性降低 |
| `detection` | 不进行模式推断 | 仅清理配置明确列出的垃圾 |

### 模式推断的置信度阈值

| 置信度 | 来源 | 处理 |
|---|---|---|
| 1.0 | 多源同时匹配 | 自动删除 |
| 0.9 | name_patterns 匹配 | 自动删除 |
| 0.8 | prefix_indicators 匹配 | 自动删除 |
| 0.7 | name_keywords 匹配 | 标记为"疑似垃圾"，需用户确认 |
| < 0.7 | 不匹配 | 保留 |

详见 [references/retrospective.md](file:///d:/code/otherProjects/17_xianyu/.trae/skills/workspace-cleanup/references/retrospective.md) Section 7。

---

## The Bottom Line

**No cleanup without config, no delete without backup, no archive without verification.**

Read config → Run 6 phases → Output report. This is non-negotiable.

If config is missing, STOP and ask the user to provide `cleanup-config.yaml` or copy from `examples/cleanup-config.example.yaml`.

**配置驱动 + 模式推断 + 四重服务检测 + 稳定性检查 + 异常文件名处理 = 健壮的清理流程。**
