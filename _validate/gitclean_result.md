# 工作空间 Git 卫生治理（2026-10-13）

## 1. 扫描范围与方法

- 全库枚举：`find`（排除 `.git`）共 45280 个路径 → `git check-ignore -v --stdin` 逐路径归因，
  得到「实际生效规则 → 命中数」矩阵（45 条规则在生效，43966 个路径被忽略）。
- 索引违规：`git ls-files -i -c --exclude-standard`（已跟踪但命中忽略规则）。
- 历史违规：`git log --all --pretty=format: --name-only` 全量路径去重后按敏感形态过滤
  （`\.env|\.db|token|secret|credential|\.pem|\.key|bak|malformed`）。
- 内容级：对全部 3417 个历史 blob 解压扫描 JWT / GitHub PAT / 钉钉 secret 形态串。
- 大对象与二进制：`git count-objects -vH`、`git ls-files | grep exe|dll`。

## 2. 判定与处置（用户确认口径）

| 类别 | 处置 |
| --- | --- |
| 构建产物 / 依赖目录（node_modules、dist、dist_*、.venv、.venv-build、__pycache__、pytest_cache、playwright-report、test-results、release、runtime/{data,cache,ai_images}、tests/_instance、backend/ffmpeg） | 补齐/修正忽略规则；已入库的移出索引，物理文件保留 |
| 第三方可执行体（exe/dll） | 移出索引，本地保留，历史保留 |
| `_validate/` 取证目录 | 文本证据与截图入库；音频/视频与大转储忽略（`_validate/**/*.mp3` 等 + 转储目录内容级忽略，目录内手写 `*.md` 用反选保留） |
| 库备份 + 明文 JWT 令牌（11 个路径） | 从**全部历史**清除 |
| `.git/config` 明文 PAT | remote URL 改为不含凭据形式 |

移出索引的 46 个违规文件在 commit `2b457d3` 处理；`9857e8c` 修正我引入的回归
（`_validate/*_pack/` 整目录忽略误吞已入库的 `README-真机测试说明.md`，改内容级忽略 + `!.../*.md` 反选）。

## 3. `.gitignore` 规则修订

锚定缺陷修复（含斜杠规则被锚定到仓库根、从未命中真实层级）：

- `admin-web/playwright-report/`、`admin-web/test-results/`、`admin-web/vite.config.js.timestamp-*.mjs`、
  `admin-web/dist_*/` → 改为无斜杠基名规则 `playwright-report/`、`test-results/`、
  `vite.config.js.timestamp-*.mjs`、`dist_*/`（对 `apps/admin-web` 层级生效）。

冗余清理（12 条被更宽规则完全覆盖，逐条就地注明取代关系）：

`debug.log`、`*.test.log`、`backend/pytest*.log`、`/build_output.log`、`/sonar-*.log`、
`/pytest-output.log`、回归日志块 8 条 → 由全局 `*.log` 覆盖；
`*.db.malformed.bak`、`*.spec.bak`、`sonar-project.properties.bak`、`serverless.yml.bak` → 由 `*.bak` 覆盖；
`scf/__pycache__/` → 由 `__pycache__/` 覆盖；第二处 `*.egg-info/` → 重复声明；
`release/MorningBrief/`、`release/MorningBrief-Setup-*.exe` → 由后置 `release/` 覆盖。

新增补充：`/runtime/data/`、`/runtime/ai_images/`、`/runtime/cache/`、`/tests/_instance/`、
`*.list.txt`、`_validate/**/{mp3,m4a,wav,aac,mp4}`、`_validate/perf_results_*/*`、
`_validate/*_samples/*`、`_validate/*_pack/*` 及三条 `!.../*.md` 反选。

结果：292 行 → 274 行，重复规则 0；**忽略集合逐路径比对 delta = 0 行**
（43966 个被忽略路径完全一致，dedup 未损失任何覆盖）。

## 4. 历史清理（敏感内容）

清除的 11 个路径（此前分别在 2~10 个提交中出现）：

```
backend/data/news.db.bak_20260808_013028   backend/data/news.db.bak_20260808_020033
backend/data/news.db.malformed.bak         backend/data/news.db-shm   backend/data/news.db-wal
.run/test_token.txt                        jmeter_test/test_token.txt
scripts/jmeter_test/test_token.txt         scripts/jmeter_test/test_user_info.json
jmeter_test/test_user_info.json            backend/.token.tmp
```

执行方式（关键：不动主仓工作树）：

1. `git filter-repo` 对**非 bare 仓**收尾会执行 `git reset --hard`
   （源码 `git_filter_repo.py:4942 reset = not is_bare`），会摧毁并发会话的未提交改动
   （`apps/admin-web/src/api/audio.js`、`backend/app/workflow/llm/rewriter.py` 等 12 个已跟踪改动）。
   故改为：`git clone --bare --no-local` → 在 bare 副本里 `git filter-repo --invert-paths --force`
   （bare 跳过 `reset --hard`，`--force` 跳过 fresh-clone 前置检查）。
2. 主仓 `git fetch file://…/news.git '+refs/heads/*:refs/histclean/*' '+refs/tags/*:…'`，
   先验证 `git diff --stat main refs/histclean/main` **为空**（HEAD 树逐字节相同，
   因 11 个路径早已不在 HEAD），再 `update-ref` 平移 `refs/heads/main` 与 tag。
3. 删除 `refs/remotes/origin/main`（旧历史指针，否则敏感对象仍可达、gc 无法回收）。
4. `git reflog expire --expire=now --expire-unreachable=now --all && git gc --prune=now`。

## 5. 验证

```
历史残留   git log --all --name-only | grep 敏感形态        → 0 命中（exit 1）
           git rev-list --objects --all | grep 敏感形态      → 0 命中
           逐路径 git log --all -- <path>                    → 全部 0 commits
内容扫描   3417 个历史 blob 解包 grep eyJhbGciOi|ghp_|github_pat_|SEC<32hex> → 0 命中
完整性     git fsck --full                                   → 无输出（无损坏/无悬空）
对象       before: 7040 松散 539.92 MiB + 2 pack 252.14 MiB + 5 garbage tmp_obj + prune-packable 5395
           after : 0 松散 / 1 pack / 5831 in-pack / 252.04 MiB / garbage 0
           .git 目录 554 MB → 253 MB
提交       211 → 211（main 9857e8c → dcd47b4，tag MorningBrief-Setup 1f13903 → a800b3a）
索引       git ls-files -i -c --exclude-standard → 0（已跟踪但违规 = 0）
           git ls-files | grep exe|dll|so|dylib  → 0（无跟踪二进制）
工作区     改写前后 `git status --porcelain -uall` 集合一致，并发 WIP 未受影响
远端       origin → https://github.com/wangnan05563/MorningBrief.git（已去凭据）
           全仓 grep 原 PAT 字符串 → .git / .github / *.md 中 0 处残留
```

## 6. 收尾与遗留事项

已执行（用户确认后）：

- **强推完成**：`git push --force-with-lease=refs/heads/main:8fac0c0…  --atomic`，
  main `8fac0c0 → 874178b`、tag `1f13903 → a800b3a` 均为 forced update；
  远端复核 `git ls-remote` 两个 ref 已等于本地改写后的 SHA。
  注意 tag 需 `+refs/tags/...` 前缀，否则 `--atomic` 会因「tag already exists」把整批推回退。
- **磁盘令牌产物已删**：`scripts/jmeter_test/test_token.txt`、`test_user_info.json`
  （压测脚本每轮自动重签，删除无损失）。
- **保留** `backend/data/news.db-shm`(32K) / `news.db-wal`(0K)：正在使用的库伴生文件，
  后端进程持有时误删有 WAL 损坏风险；两者已被 `*.db-shm` / `*.db-wal` 忽略。
- **备份包已删除**（用户指示，2026-10-13）：`20_News_history_backup_20261013.bundle`（272,381,207 B ≈ 260 MiB，
  heads = `refs/heads/main 3b99f015` / `refs/remotes/origin/main 8fac0c0` / `tag 1f13903`）。
  删除前复核仓库自洽：213 个提交、`git fsck --full` 无告警、main == origin/main == `502f133`，
  即删除不影响任何现存 ref 的可达性。删除后本机不再持有被清除对象的任何副本，
  旧库备份内容**不可回溯**。
- 用户判定：项目单人使用，钉钉 webhook / SMTP 等凭据不做轮换；
  仅保留一条与协作无关的提醒——该 PAT 对本仓有写权限且曾明文躺在公开历史里，
  值得确认它的 scope 与 Expiration（仓库产出分发给终端用户的桌面安装包，属供应链面）。

仍需人工动作：

1. **GitHub 侧旧对象**：强推只让旧提交失去 ref 引用，服务端那份历史（含库备份与明文 JWT）
   在 GitHub 完成 GC 前仍可能按 SHA 直接访问（实测按旧 SHA fetch，服务器持续回传 pack）；
   若需彻底清除，按官方「removing sensitive data」流程提 Support 请求（或删库重建）。
   仓库实测为 **public**（API `private: false`），建议先改私有再决定是否提请求。
2. **fork 自查**：若存在 fork，旧历史在别人仓库里永久留存，Support 与删库均不可达，
   此时应按「数据已泄露」处置（本环境抓取 forks 页失败，需人工打开确认）。
3. 推送时 GitHub 提示两个 >50MB 大文件（`backend/ffmpeg/bin/avcodec-63.dll` 94MB、
   `runtime/data/cloudflared.exe` 52MB）仍在历史中——本轮按既定口径保留，
   如后续要瘦身可改走 Git LFS 或一并做历史清除。
4. `backend/app/_build_info.py` 为构建期生成文件但**有意入库**（开发态缺省值 + About 页兜底，
   见 `backend/app/routers/admin/about.py:65`），故保留跟踪、不加忽略规则。
