# 生产 COS 影响范围审计（只读，逐对象核对）

审计时间：2026-11-03 11:40—11:50（北京时间），方法：`runtime/cos_audit.py`、`runtime/cos_write_scope.py`
用生产凭据对桶做 `list_objects` 全量分页遍历，只读不写，按 `LastModified` 归因。

## 桶基线

| 项 | 值 |
|---|---|
| Bucket | 生产桶（`backend/.env` 中 `COS_BUCKET`，本文件不记录名称以外的凭据信息） |
| 对象总数 | 51,012 |
| 顶层前缀 | `episodes/` 45,106、`tts/` 4,270、`play_progress/` 1,624、`jwt_blacklist/` 12 |

## 结论一：11-03 批次对生产 COS 零写入

- 沙箱构建日志（`runtime/rerun_all.log:2`）：`已清空沙箱外部凭据 10 项`；
  `sandbox/backend/.env` 中 `COS_SECRET_ID`、`COS_SECRET_KEY`、`COS_BUCKET` 等 10 个键实测为空串。
- 全桶扫描阈值取沙箱启动时刻 2026-11-03 09:36（北京时间）：
  **`LastModified` 晚于该时刻的对象数 = 0**。
- 沙箱服务日志中 `scheduler` 关键字出现 0 次，`APP_ROLE=api` 已关闭 APScheduler，
  故 `episodes/`、`tts/` 的日常增量不来自压测实例（它们由生产定时任务在 05:00 档写入）。

## 结论二：10-31 批次仅留下 1 个对象，且落在测试账号目录

| 对象 | 大小 | LastModified | 归属 |
|---|---:|---|---|
| `play_progress/950020/100.json` | 130 B | 2026-10-31T08:30:44Z（16:30:44 北京时间） | `sub=950020`，即 `runtime/tokens.json` 中 C 端压测令牌自身 |

同期其余前缀均无新增/改动：

- `play_progress/` 前缀按天统计，2026-10-31 全天 **仅 1 个**对象，就是上表这一条；
  `950020/` 目录下其余 394 个对象的写入时间为 2026-10-09（功能测试造数，早于性能批次）。
- `jwt_blacklist/` 共 12 个对象，最晚一条为 2026-09-15，10-31 与 11-03 均无新增（登出类端点未被真实执行）。
- `perf/` 前缀对象数 0（夹具里的 `perf/*.txt`、`perf/backup-none.zip` 只作为不存在的 key 触发 404/校验分支）。

影响判定：单个 130 字节的播放进度文件覆写，位于压测自建账号目录，不涉及真实用户数据，
不构成生产数据污染；10-31 报告「测试策略不影响生产数据」的声明在本项上误差为 1 个测试账号对象。

## 排除项：`play_progress/1/` 的近期写入与压测无关

`uid=1`（作者本人账号）在 2026-11-02 09:49 及 11-03 08:03—08:34（北京时间）写入 9 个对象，
间隔约 6 分钟、键号为连续递增的条目 id，与真实收听行为一致；
该时段早于沙箱启动（09:36），且当时压测实例尚无凭据，故不计入压测影响。

## 复现命令

```bash
# 只读遍历，前缀可选
backend/.venv/Scripts/python.exe scripts/jmeter_test/full_api/runtime/cos_audit.py \
    play_progress/950020/ perf/ jwt_blacklist/
backend/.venv/Scripts/python.exe scripts/jmeter_test/full_api/runtime/cos_write_scope.py
```
