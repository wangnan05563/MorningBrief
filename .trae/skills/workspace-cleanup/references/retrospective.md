# 工作空间清理复盘分析（2026-07-05 更新）

> 基于对一个实际项目 5 轮工作空间清理迭代的深度复盘，提炼通用经验。
>
> 第五轮复盘（2026-07-05）新增：PowerShell 语法陷阱、后台进程持续创建文件、
> 异常文件名处理、配置缺失时的模式推断等场景。

---

## 维度一：成功执行任务的完整步骤

### 1.1 整体节奏

5 轮迭代逐步发现新问题，证明这是一个**周期性维护任务**而非一次性清理。

| 轮次 | 起始文件数 | 结束文件数 | 触发因素 |
|---|---|---|---|
| 第一轮 | ~50 | ~32 | 用户初次请求清理 |
| 第二轮 | ~32 | 18 | 启动脚本统一 |
| 第三轮 | 18 | 18（确认无新增） | 主动复查 |
| 第四轮 | 32 | 14 | 服务运行中持续产生运行产物 |
| 第五轮 | 119 | 15（14 白名单 + 1 异常重建） | 配置驱动系统化清理，引入 6 阶段闭环 |

### 1.2 每轮通用 6 步流程

1. **侦察阶段（Recon）**：用 LS/Glob 列出根目录、子目录文件清单
2. **归类阶段（Classify）**：建立"根目录允许清单"模型
3. **影响评估（Impact）**：检查服务状态（PID + 端口）决定是否停止
4. **执行阶段（Execute）**：按"删除/移动/保留"三档处理
5. **验证阶段（Verify）**：通过导入核心模块确认未破坏应用
6. **归档阶段（Archive）**：更新规范文档 + 强化 .gitignore

### 1.3 关键技术点

- **Get-FileHash 去重**：先比对同名文件 hash 避免误删唯一副本
- **停止服务前置**：服务运行中会持有文件句柄导致删除失败或生成新产物
- **批量先于精细**：先一次性删除明显垃圾，再处理边界情况
- **导入验证兜底**：`import xianyu_hunter` 作为最便宜的回归测试
- **文档同步更新**：每次清理都在 `directory-structure.md` 留变更记录

---

## 维度二：任务执行过程中的不确定性与失败点

### 2.1 不确定点

| 不确定点 | 触发场景 | 处置 |
|---|---|---|
| 根目录某文件是否该保留 | `.env` 含敏感配置 vs 误命名为 `.env` 的垃圾 | 读取前几行判断是否为真实环境变量 |
| 服务是否在运行 | 已知应用在跑，但 PID 文件可能已失效 | 双验证：PID 文件 + netstat 端口监听 |
| 文件删除后是否可恢复 | 用户未明确"清理"是否允许删除 | 优先 Move 到 scripts/，无法归类再 Delete |
| `.scannerwork/` 等大目录 | 体积 6-16 MB，但删除会影响 IDE 缓存 | 列入 gitignore，下次自动忽略 |

### 2.2 失败点

1. **重名文件被误删**：根目录与 `docs/04-系统维护/sonar-reports/` 下有同名 SonarQube 报告，第四轮才通过 Get-FileHash 比对发现冗余。
2. **服务运行中持续产生新垃圾**：清理后根目录文件数从 14 涨到 32，因为服务在跑且无 .gitignore 拦截。
3. **静默启动.vbs 找不到 launcher**：第一轮将 `静默启动.vbs` 移走，但根目录包装器硬编码了相对路径，调用失败。
4. **`.pre-commit-config.yaml` 拦截规则不全**：第三轮才补充 `sonar-results/` 规则。
5. **误重定向产物反复出现**：`<project_name>`、`<project_name>frontend` 是 PowerShell `command > filename` 错误输入产生的，每次清理完还会再生。

### 2.3 风险控制经验

- **永不大规模批量删除**：先打印清单 + 人工确认，再执行
- **删除前先备份 hash 表**：把所有"将删"文件的 path+hash+size 写入 `cleanup-YYYYMMDD.log`
- **核心模块导入作为最后一道闸**：任何清理后都跑 `python -c "import <core_module>"`
- **服务运行中只删不重要的**：服务运行时只删除重定向产物和测试输出，移动/结构变更先停服务

---

## 维度三：可抽象的固定流程与判断逻辑

### 3.1 固定 6 阶段流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Phase 1    │───▶│  Phase 2    │───▶│  Phase 3    │
│  Recon      │    │  Classify   │    │  Impact     │
│  扫描       │    │  归类       │    │  影响评估   │
└─────────────┘    └─────────────┘    └─────────────┘
       │                                    │
       │                                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Phase 6    │◀───│  Phase 5    │◀───│  Phase 4    │
│  Archive    │    │  Verify     │    │  Execute    │
│  归档       │    │  验证       │    │  执行       │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 3.2 可抽象的判断逻辑

**判断一：文件是否属于"垃圾"？**

```
文件 X 是垃圾 ⟺
  ∃ pattern ∈ garbage_patterns: match(X.name, pattern)
  OR
  X.path == workspace_root AND X.ext ∉ allowed_extensions
  OR
  X.path == workspace_root AND X.name 不在 allowed_root_files 清单
```

**判断二：文件是否属于"脚本"？**

```
文件 X 是脚本 ⟺
  X.ext ∈ { .py, .ps1, .bat, .sh, .js, .vbs }
  AND
  X.path 不是已知代码目录（src/、frontend/src/、tests/）
  AND
  X 不是配置/数据文件（按 content sniff 排除）
```

**判断三：服务是否在运行？**

```
服务在运行 ⟺
  ∃ pid_file ∈ service_indicators.pid_files: exists(pid_file)
  OR
  ∃ port ∈ service_indicators.ports: port_in_listen(port)
```

**判断四：操作是否安全？**

```
操作 O 对文件 X 安全 ⟺
  X 在 backup_log 中存在 hash 记录
  AND
  service_running == false
  AND
  (O == Delete) ⟹ X 在垃圾/重定向产物名单
  (O == Move) ⟹ 目标目录存在且可写
```

### 3.3 可参数化的配置

```yaml
# cleanup-config.yaml 示例
workspace:
  root: "."                    # 工作空间根（相对或绝对路径）
  script_dir: "scripts"        # 脚本集中目录
  docs_dir: "docs"             # 文档目录

root_allowlist:
  extensions: [".md", ".yaml", ".yml", ".toml", ".txt", ".gitignore", ".env", ".example", ".properties"]
  files:                       # 显式允许的根目录文件
    - "README.md"
    - "CHANGELOG.md"
    - "VERSIONING.md"
    - "Dockerfile"
    - "docker-compose.yml"
    - "pyproject.toml"
    - "requirements.txt"
    - ".gitignore"
    - ".dockerignore"
    - ".env.example"
    - ".pre-commit-config.yaml"

script_extensions: [".py", ".ps1", ".bat", ".sh", ".js", ".vbs"]

garbage_patterns:
  redirect_artifacts: ["/0", "/<project_name>", "/<project_name>frontend", "/_r.json"]
  tmp_suffixes: [".tmp", ".bak", ".orig", ".txtcd", ".s3358_lines.txt", ".tmp_diff.txt"]
  test_outputs: ["/pytest_output.txt", "/pytest_result.txt", "/test_result.txt", "/test_debug_output.txt"]
  cache_dirs: [".scannerwork/", ".pytest_cache/", "sonar-results/", ".ruff_cache/"]

service_indicators:
  pid_files: ["logs/web.pid", "logs/app.pid"]
  ports: [8000, 8080, 5000]
  process_names: ["python", "uvicorn", "node"]

verification:
  import_statements:
    - "import xianyu_hunter"
    - "from xianyu_hunter import config"
  command: ".venv/Scripts/python.exe -c 'import xianyu_hunter; from xianyu_hunter import config, container'"

archive:
  changelog_path: "docs/standards/directory-structure.md"
  gitignore_path: ".gitignore"
  precommit_path: ".pre-commit-config.yaml"

safety:
  require_stopped_service: true
  backup_log_format: "cleanup-{YYYYMMDD-HHmmss}.log"
  min_confidence_to_delete: 0.8
```

---

## 维度四：该流程和判断逻辑的适用场景与不适用场景

### 4.1 适用场景

| 场景 | 适用度 | 备注 |
|---|---|---|
| 长期维护的 Python/Node 项目 | ⭐⭐⭐⭐⭐ | 默认配置已覆盖主流技术栈 |
| 重定向/调试产生的根目录污染 | ⭐⭐⭐⭐⭐ | 直接套用 `garbage_patterns` |
| 脚本文件散落各子目录 | ⭐⭐⭐⭐⭐ | 按 `script_extensions` 集中即可 |
| 服务运行中持续产生运行产物 | ⭐⭐⭐⭐ | 需先停服务 |
| 周期性预防性维护 | ⭐⭐⭐⭐⭐ | 建议纳入 CI 或周维护脚本 |
| 多技术栈混合项目 | ⭐⭐⭐⭐ | 调整 `root_allowlist.extensions` 即可 |
| 含 Docker/Compose 配置的项目 | ⭐⭐⭐⭐⭐ | 已在默认清单 |

### 4.2 不适用场景

| 场景 | 不适用原因 | 替代方案 |
|---|---|---|
| 全新空仓库 | 无根目录污染，无需清理 | 跳过本 skill |
| Monorepo 单一包项目 | 硬编码根目录假设会误判 | 改为 per-package 模式 |
| 包含大量二进制资源 | 脚本扩展名规则不适用 | 增加 binary_extensions 规则 |
| 服务不能停的 7×24 业务 | Phase 3 影响评估的"先停服务"原则无法执行 | 改造为"软删除"模式（重命名加 .trash 后缀） |
| 团队规模 > 20 人的公共仓库 | 个人清理习惯可能与其他成员冲突 | 改为 PR 流程而非本地清理 |
| macOS/Linux-only 项目 | 脚本基于 PowerShell 语法 | 提供 bash 版本或用跨平台命令 |
| 大型构建产物（GB 级别） | 误删构建产物会导致重新构建 | 强制 require explicit confirmation |
| 受版本控制保护的目录（vendor/、node_modules/） | 物理删除会破坏包完整性 | 仅做 .gitignore 强化，不实际删除 |

### 4.3 边界与降级策略

- **服务不能停**：跳过 Phase 4 中的 Move，仅做 Delete（按 trash 模式）
- **配置缺失**：回退到默认 `cleanup-config.example.yaml` 并提示用户覆盖
- **核心模块导入失败**：中止归档（Phase 6），提示用户人工介入
- **根目录文件数 > 50**：先 dry-run（仅打印计划，不实际执行）

---

## 五、第五轮清理复盘（2026-07-05）

### 5.1 本轮特色

本轮首次采用 `workspace-cleanup` 技能的完整 6 阶段闭环流程，
配置驱动 + hash 备份 + 验证归档，是历轮中最规范的一次。

**清理规模：**
- 根目录：119 → 15 文件（删除 ~118 个）
- frontend：30 → 9 文件（删除 ~21 个）
- 缓存目录：3 个（`.scannerwork/` + `.pytest_cache/` + `sonar-results/`）
- 释放空间：~42 MB

### 5.2 新发现的不确定性与失败点

#### 5.2.1 工具层限制

| 失败点 | 触发场景 | 影响 | 解决方案 |
|---|---|---|---|
| LS 输出截断 | 项目文件数 > 40000 字符限制 | 无法获取完整文件清单 | 改用 PowerShell `Get-ChildItem -File` + 紧凑格式 |
| Glob `*.py` 无返回 | 工具行为与预期不符 | 浪费一轮探测 | 直接用 PowerShell 列文件，不依赖 Glob |

#### 5.2.2 PowerShell 语法陷阱（新增）

| 陷阱 | 错误代码 | 错误信息 | 修正 |
|---|---|---|---|
| 驱动器引用 | `"Port $port: not listening"` | `Variable reference is not valid. ':' was followed by a valid variable name` | 改用 `${port}: not listening` |
| 哈希表 strict mode | `$stats.Errors++` | `PropertyNotFound` | 改用简单变量 `$script:errorCount++` |
| 异常文件名 | `Join-Path $root "not enabled*"` | 路径解析失败 | 用 `Get-ChildItem + Where-Object` 匹配 |

**经验教训：** PowerShell 哈希表在 strict mode 下属性递增会报错，
应使用 `[PSCustomObject]@{}` 或简单变量。所有 `$var:` 后跟非变量名字符的场景
都需用 `${var}` 包裹。

#### 5.2.3 服务检测盲区（新增）

| 盲区 | 实际场景 | 检测结果 | 修正 |
|---|---|---|---|
| PID 文件缺失 | 服务在运行但未写 PID 文件 | 误判为"服务未运行" | 增加端口 + 进程名 + 文件占用三重检测 |
| 文件被占用 | `run.stdout.log` 被服务持有 | hash 计算失败 | 文件占用作为服务运行的间接证据 |

**经验教训：** PID 文件不可靠（可能缺失或残留），必须多重证据兜底。
配置中新增 `file_occupancy_probes` 作为第四道检测。

#### 5.2.4 后台进程持续创建文件（新增）

**现象：** 清理过程中发现新文件被持续创建：
- `compare_*.ps1` / `do_git_commit.ps1` / `integrate_*.ps1`（skill 集成脚本）
- `ubprocess; r=subprocess.run([...])`（PowerShell 误重定向产物，被重建 3 次）

**原因：** 并发的 AI 会话或后台脚本在执行 git diff 操作，产生误重定向产物。

**影响：** 清理"复发"，根目录文件数无法稳定下降。

**解决方案：**
1. 新增 `stability_check` 配置块，删除后等待 N 秒复扫
2. 匹配 `recurrence_patterns` 判断是否为已知后台进程产物
3. 按 `recurrence_action`（warn/stop/soft_delete）策略处理
4. 超过 `max_recurrence` 强制停止，提示用户排查后台进程

#### 5.2.5 配置覆盖盲区（新增）

**现象：** example 配置未覆盖以下新型调试产物：
- skill 集成脚本（`compare_*.ps1` / `do_git_commit.ps1` 等）
- git 调试脚本（`git_menu_history.py` / `git_show_output.txt` 等）
- 验证脚本（`verify_*.py` / `verify_*.txt` 等）

**解决方案：**
1. 扩展 `garbage_patterns` 新增 `skill_debug_artifacts` 类别
2. 新增 `detection` 配置块，支持基于文件名特征的模式推断
3. 推断模式自动加入 .gitignore 防止复发

### 5.3 新增的降级策略

| 场景 | 降级策略 | 配置项 |
|---|---|---|
| 配置缺失 | 回退到 example + 模式推断 | `detection.enabled: true` |
| PID 文件缺失 | 端口 + 进程名 + 文件占用三重检测 | `service_indicators.file_occupancy_probes` |
| 后台进程持续创建文件 | 稳定性检查 + 复发处理 | `stability_check.*` |
| 异常文件名 | Get-ChildItem + Where-Object 匹配 | `safety.special_filename_handling: "safe"` |
| 服务不能停 | 软删除（重命名 .trash 后缀） | `safety.soft_delete_suffix` |
| 跨平台 | 配置中的命令变体 | `platform.commands.{windows/linux/macos}` |

### 5.4 第五轮清理的关键技术点

- **配置驱动系统化**：所有规则通过 YAML 配置管理，零硬编码
- **hash 备份完整性**：125 个文件 SHA256 备份至 `logs/cleanup-20260705-000340.log`
- **服务停止前置**：检测到端口 8000 监听后停止服务（PID 33540）
- **每批删除后验证**：及时发现删除脚本失效问题
- **模式推断兜底**：识别配置未覆盖的新型调试产物
- **稳定性检查**：发现后台进程持续创建文件的问题
- **归档三件套**：.gitignore + .pre-commit + changelog 同步更新

### 5.5 适用场景更新

#### 新增不适用场景

| 场景 | 不适用原因 | 替代方案 |
|---|---|---|
| 有并发 AI 会话的项目 | 后台进程持续创建文件，清理"复发" | 先排查并停止所有后台会话，再执行清理 |
| 配置未覆盖的新型调试产物 | garbage_patterns 无法穷举所有模式 | 启用 `detection` 模式推断 |
| 文件名含特殊字符的误重定向产物 | 直接路径字符串失败 | 使用 `safe` 模式（Get-ChildItem 匹配） |

#### 新增强化适用场景

| 场景 | 强化能力 | 配置项 |
|---|---|---|
| 服务运行但无 PID 文件 | 文件占用探测兜底 | `file_occupancy_probes` |
| 跨平台项目 | 配置中的命令变体 | `platform.commands.*` |
| 新型调试产物 | 模式推断 + 自动加入 .gitignore | `detection.*` |

---

## 六、PowerShell 脚本陷阱与最佳实践（新增）

### 6.1 变量引用陷阱

```powershell
# ❌ 错误：$port: 被解析为驱动器引用
"Port $port: not listening"

# ✅ 正确：用 ${} 包裹变量名
"Port ${port}: not listening"
```

### 6.2 哈希表 strict mode 陷阱

```powershell
# ❌ 错误：strict mode 下属性递增报错 PropertyNotFound
$stats = @{ Deleted=0; Errors=0 }
$stats.Errors++  # 报错

# ✅ 正确方案 1：用简单变量
$deletedCount = 0
$errorCount = 0
$deletedCount++

# ✅ 正确方案 2：用 [PSCustomObject]
$stats = [PSCustomObject]@{ Deleted=0; Errors=0 }
$stats.Errors++  # 正常工作
```

### 6.3 异常文件名处理

```powershell
# ❌ 错误：直接路径字符串在含特殊字符时失败
$p = Join-Path $root "not enabled, try to fix it now."
Remove-Item $p  # 可能失败

# ✅ 正确：Get-ChildItem + Where-Object 匹配
$odd = Get-ChildItem -Path $root -File | Where-Object { $_.Name -like "not enabled*" }
if ($odd) { Remove-Item -LiteralPath $odd.FullName -Force }
```

### 6.4 文件占用检测

```powershell
# ✅ 检测文件是否被进程持有
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

# 用法：作为服务运行的间接证据
if (Test-FileLocked "run.stdout.log") {
  "服务可能正在运行（run.stdout.log 被占用）"
}
```

### 6.5 跨平台命令选择

```powershell
# 根据平台选择命令
$platform = if ($IsWindows) { "windows" }
            elseif ($IsLinux) { "linux" }
            elseif ($IsMacOS) { "macos" }
            else { "windows" }  # 默认 Windows

$venvPython = switch ($platform) {
  "windows" { ".venv/Scripts/python.exe" }
  "linux"   { ".venv/bin/python" }
  "macos"   { ".venv/bin/python" }
}
```

---

## 七、配置缺失时的降级策略（新增）

### 7.1 配置加载优先级

```
1. 用户 cleanup-config.yaml（优先级最高）
       │ 缺失
       ▼
2. examples/cleanup-config.example.yaml（fallback）
       │ 仍缺失
       ▼
3. STOP，要求用户提供配置
```

### 7.2 配置不完整时的降级

| 缺失配置 | 降级策略 | 影响 |
|---|---|---|
| `garbage_patterns` 部分类别 | 启用 `detection` 模式推断 | 覆盖面降低，需用户确认 |
| `service_indicators.file_occupancy_probes` | 仅用 PID + 端口 + 进程名检测 | 服务检测盲区增大 |
| `stability_check` | 跳过稳定性检查 | 无法检测后台进程复发 |
| `platform.commands` | 默认 Windows 命令 | 跨平台兼容性降低 |
| `detection` | 不进行模式推断 | 仅清理配置明确列出的垃圾 |

### 7.3 模式推断的置信度阈值

```yaml
detection:
  enabled: true
  infer_confidence_threshold: 0.7  # 低于此值仅标记，不自动删除
```

| 置信度 | 来源 | 处理 |
|---|---|---|
| 1.0 | 多源同时匹配 | 自动删除 |
| 0.9 | name_patterns 匹配 | 自动删除 |
| 0.8 | prefix_indicators 匹配 | 自动删除 |
| 0.7 | name_keywords 匹配 | 标记为"疑似垃圾"，需用户确认 |
| < 0.7 | 不匹配 | 保留 |

**经验教训：** 模式推断是配置缺失时的兜底，不能替代完整配置。
每次清理后应将推断模式补回 `garbage_patterns`，逐步完善配置。
