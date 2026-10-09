## 根因

任务主体（第 1、3 条）要求「在 system CPU < 15% 的专用空闲执行机上复跑并把分解表回填 T01659」，
本环境**不具备该前置**：2026-10-09 07:33 实测 `typeperf '\Processor(_Total)\% Processor Time'`
= **60.3 / 61.1 / 61.8（跑前）→ 69.8 / 69.8 / 68.2（跑后）**（样本已入库
`_validate/t01661_cpu_before.txt`、`_validate/t01661_cpu_after.txt`）。
T01617 的教训正是同一台机在 82–93% 负载下绝对值放大 ≈9 倍，所以在忙机上出「分解表绝对值」
等于制造第二份不可引用数据。

因此本单按「**工具与口径就绪 + 结构性结论先出，绝对值留给空闲机**」落地：
把任务第 2 条要求的临时分段计时做成**可一键应用/回滚的补丁**，用隔离副本真跑一遍验证口径可用，
并借这轮忙机数据完成对三条待验证假设的**方向性判定**（判定看的是占比与「是否为 0」，
不依赖绝对值大小）。

## 影响范围

- 代码影响：**无**（探针没有进 main）。`git status --short backend/app` 只剩并发会话的
  `_build_info.py`；`grep -rn "_t01661_probe" backend/app` 无命中 —— 硬约束「临时探针不得合入 main」已守住。
- 交付物（全部在 `_validate/`，commit `9791060`）：
  - `_validate/t01661_probe.patch` —— 5 处 perf_counter 分段计时（新增 `app/core/_t01661_probe.py`
    探针模块；`core/auth.py:get_current_user` 的 token_extract/jwt_decode/blacklist；
    `database.py:_set_sqlite_pragma` 的建连 PRAGMA 累加；`core/write_gate.py` 新增
    `write_lock_probed()` 拆 lock_wait/lock_hold；`routers/api/comments.py:create_comment`
    的 profile_query/episode_check/commit + flush）。
    **已用 `git apply --check` 验证可干净应用**（含 new file 头），空闲机上照 runbook 直接打。
  - `_validate/t01661_comment_probe.py` —— 顺序 + 并发两组写请求驱动，解析探针行输出占比表，
    `--out` 落原始 JSON。
  - `_validate/t01661_runbook.md` —— 前置判据、隔离副本步骤、打补丁/起实例/跑探针/回滚、
    结果口径模板（含回填 T01659 的阈值判定规则）、基线重标定要求、残留限制。
  - `_validate/t01661_probe_data.json` —— 忙机预跑原始探针行（标注绝对值不可引用）。
- 对外部无副作用：全程隔离副本（`%TEMP%/t01661_iso`，已删除），
  **未复制 `data/tunnel_config.json`** → 默认 `auto_start=False`，不会再建 Funnel、不发通知；
  副本库 12 个定时频道中和（is_active=0 / schedule_time=NULL）；
  探针用户 id=950020~950023 写在副本库，**未触碰 dev 库真实用户（id 1、2）**；
  限流与 cron 用环境变量注入，未改 `.env`。

## 修复（本次交付的实现要点，绝对路径）

- `D:\code\otherProjects\20_News\_validate\t01661_probe.patch`（补丁正文）
- `D:\code\otherProjects\20_News\_validate\t01661_comment_probe.py`
- `D:\code\otherProjects\20_News\_validate\t01661_runbook.md`
- 探针实现取舍（写给下一个读的人）：
  1. 用 `ContextVar` 存分段标记 → 依赖 `get_current_user` 与 handler 在同一请求上下文，
     天然按请求隔离，无需传参改造函数签名；
  2. `write_lock()` 只返回锁、无法自测等待时长 → 新增 `write_lock_probed()` 上下文管理器，
     在**获取锁前后**各打一个标记，才拆得出 `lock_wait` 与 `lock_hold`；
  3. 建连 PRAGMA 发生在 SQLAlchemy connect 事件里（不在请求协程上下文）→ 用模块级累加器
     `CONN{n,ms}` + 请求入口快照做差，得到「本请求新建了几条连接 / PRAGMA 花了多久」；
  4. loguru sink 自耗时无法在同一条日志里自测 → 报 `sink_prev`（滞后一条，只看量级）。

## 验证（实测证据）

1. **补丁可用**：`git apply --check _validate/t01661_probe.patch` 通过；
   打补丁后的副本 5 个文件 `py_compile` 全部通过；实例冷启动就绪（`/api/v1/channels` = 200）。
2. **探针口径真跑通**（忙机，`POST /api/v1/comments`）：
   - 顺序写 n=14（间隔 300ms，无并发）：服务端 total 中位 **201.4ms**；
     profile_query **62.2ms(31%)**、lock_hold **63.6ms(32%)**（其中 commit 38.0）、
     episode_check **32.4ms(16%)**、lock_wait 0.1ms、blacklist 0.0ms、
     conn_new **0 条 / conn_pragma 0.0ms**、sink_prev 3.0ms；客户端往返 229.5ms。
   - 并发写 n=24（8 线程）：total 692.9ms；**lock_wait 252.9ms(36%)** 跃居第一大段，
     其余段全部降到 3~6%；客户端往返 748.3ms。另一轮样本 lock_wait **619ms(48%)**、往返 1322ms。
   - 两轮写请求状态码全 200，未出现 `database is locked`。
3. **三条待验证假设的判定**（这是本单真正拿到的结论）：
   - H1「`Depends(get_db)` 每请求新建连接触发 PRAGMA」→ **已被 T01662 消除**
     （连接池开启后 conn_new=0、conn_pragma=0.0ms；NullPool 时代该项 ≈41ms/请求）。
   - H2「loguru 同步 sink 在 Defender 实时防护下写盘放大」→ **不是主因但不可忽略**：
     单条 0.9~3.2ms，写请求路径约 6~10 条 → 折算 5~30ms/请求（忙机 total 的 3~15%）。
   - H3「全局写锁在无并发下的 await 开销」→ **不成立**（0.1ms）；
     真正代价是**争用排队**：并发下 lock_wait 36~48%。
     → 归因方向应从「锁原语开销」改写为「持锁段长度 × 并发数」，这直接改写 T01659 的削减优先级。
4. **对 T01617「≈75% 每请求耗时无法解释」的收敛**：分段已覆盖服务端 201.4ms 中的 ≈158ms
   （profile_query + episode_check + lock_hold），残差 ≈40ms 归框架（依赖注入/响应序列化/中间件），
   runbook §4 给了空闲机进一步夹逼的对照组设计。
5. **未达 verified 的原因（诚实标注）**：任务第 1、3 条要求的「空闲机正式复跑 +
   分解表绝对值回填 T01659 阈值」在本环境**未完成**（前置 CPU 60~70% ≠ <15%）。
   本轮只交付工具、口径与方向性判定，绝对值须由空闲机复跑产出 → `done` 不带 `verified:true`。

## 本次回写

- 建派生子单 2 张（来源均挂最初原单 **T01518**，标题带`【AI回写待审核】`，建单前按同项目标题
  查重含归档单，无重复）：
  - **T01693** 空闲执行机上正式复跑写路径每请求归因并重录 perf_gate 基线（本单工具已就绪）
  - **T01694** 按归因结果缩短写锁持锁段并前置查询（并发 lock_wait 占比 36%~48%）
- 携带上游结论：**T01659 的 R1/R2/R3 对照**表明同机跨日离散 ±48%/38% 已**大于门禁阈值本身**；
  T01662（连接池）与 T01660（角色编排）又改变了每请求路径构成（建连成本归零、多进程限流 N×）
  → **T01623 标定的基线已失效**，空闲机复跑必须同时重录 S0/S1/S2 并把
  pool/role/worker 写进基线元数据（perf_gate 侧的隔离与安全启动改造在 **T01692**）。
- 与并发会话的隔离：本单未改 `backend/app/**` 任何生产代码，提交只 stage 本单 `_validate` 文件。
- 临时产物清理：隔离副本 `%TEMP%/t01661_iso`（含 .env 副本与探针用户数据）已整目录删除；
  本轮未产生含明文 token 的日志入库（token 只在进程内签发，脚本不落盘）。
  ⚠ 历史遗留 `scripts/jmeter_test/test_token.txt` / `test_user_info.json` / `admin_token.txt`
  仍未入库但仍在磁盘上，**建议轮换压测 token**。

## 下一步建议

1. 空闲机正式复跑（含 pool on/off 与 role 编排两组对照 + 重录门禁基线），
   填 runbook §5 口径表并回填 T01659 阈值。已建派生单 **T01693**。
2. 依据并发段 `lock_wait` 36%~48% 的结论，缩短持锁范围（`db.refresh` 出锁）并前置
   profile/episode 查询，同口径复测验收。已建派生单 **T01694**。
3. perf_gate 隔离副本 + 角色编排改造（否则第 1 条每跑一次都会重复外发隧道通知）。
   已建派生单 **T01692**（T01660 回写时建）。
4. （仅观察不建单）多进程下缓存互不失效/限流 N× 的残留限制验证已在 **T01691**，不重复建单。
