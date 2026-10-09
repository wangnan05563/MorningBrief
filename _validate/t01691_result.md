# T01691 结论：跨进程写并发下缓存失效/写锁互斥/限流口径验证

> 2026-10-09 · 隔离副本（perf_gate --iso-root 设施）· 1 sched + 2 api（角色编排）· 全程隧道关闭、生产 data/ 零接触
> 复现脚本：`_validate/t01691_crossproc_probe.py`（副本用完即删，无明文 token 落盘）

## 总判定

**当前角色拆分不足以支撑读写混合的多进程部署。**
写路径本身健康（写锁互斥 + SQLite BUSY_TIMEOUT 兜底下 240 并发写 0 locked 0 5xx），
但**缓存跨进程旧值窗口 = TTL（实测 favorites 60s 内 20/20 全旧值）**，
对收藏列表这类用户可感知数据不可接受；限流口径实际放行 = N × 配额（精确验证 60 = 30×2）。

## 实验 A：缓存跨进程旧值（确定性口径）—— 不一致实锤

- 方法：GET /api/v1/favorites 预热两 worker 缓存 → sqlite 直写副本库插一条收藏
  （=「写者不通知本进程」的极端形态）→ TTL 窗口内采样 20 次 → 等 TTL 过期再读。
- 结果：**TTL 内 20/20 全部旧值**；TTL 过期后立即可见新值。
- 结论：跨进程**无失效通知**，旧值窗口 = TTL（FAVORITES_CACHE_TTL_SEC 默认 60s）。
  `cache_manager.delete_pattern` 只作用于收到写请求的进程。

## 实验 B：API 写后的采样观察

- 方法：GET 预热 40 次 → POST /favorites（随机落某 worker，只失效该 worker）→ 立即采样 40 次。
- 结果：40/40 全部新值——未观察到旧值。
- 解读：本次采样中读请求大概率由收到 POST 的同一 worker 处理（uvicorn 多进程
  accept 竞争在 Windows 回环下分布显著偏斜，LB 均匀性不可依赖）。
  与实验 A 结合判定：**不能依赖「API 写后其它进程很快看到新值」**，偏斜分布一旦改变
  即暴露 60s 旧值窗口。

## 实验 C：并发写（write_lock 互斥 + database is locked）

- 方法：240 次并发写（favorites add/delete 交替 + playlogs/progress，2 api 进程，24 线程）。
- 结果：**3.4s 完成（70 写/s），2xx 160（= add+progress 全部成功；delete 无收藏 404 属幂等预期）、
  5xx = 0、`database is locked` 增量 = 0**。
- 结论：进程内 write_gate 串行 + SQLite BUSY_TIMEOUT 兜底下，跨进程写并发健康，
  与 T01660 两轮初步观察一致（本次样本 240，较此前 100 扩大）。

## 实验 D：限流口径（N 进程合计放行）

- 方法：RATE_LIMIT_PER_MINUTE=30 重启（workers=2）→ 200 并发读。
- 结果：**放行 60、限流 140——精确等于 30 × 2**（T01660 的 240=2×120 复现）。
- 结论：多进程下实际放行 ≈ N × 配额。若需严格全局上限：改共享态存储，
  或部署文档明确「配额按进程数折算」。

## 建议（按代价从低到高）

1. **短期（无新依赖）**：用户维度可感知数据（收藏列表/进度）降 TTL 或干脆不缓存
   （fav:list 命中收益本就有限）；全局维度数据（channels/episode:today）保留 TTL 缓存可接受
   （60s 内频道名/节目列表变化用户无感）。
2. **中期**：写后失效改「带版本号缓存键」（写进程 bump DB 里的版本标记，各进程读时校验），
   或切换 MySQL+Redis 共享态（架构决策既定路线）。
3. **限流**：文档标注口径，或改共享态计数器。
