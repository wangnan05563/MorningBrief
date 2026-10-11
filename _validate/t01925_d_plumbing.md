来源：T01845（T01925 修复的后续结构性收口——本单用「发布时 ffprobe 探测外链」绕过问题，本单把实测值在链路里正规落地）

【为什么还要做】
T01925 的修法是发布时用 `ContentService._measure_audio_duration()` 探测 `review.audio_url`
（`backend/app/services/content_service.py:603-621`）。它能对齐口径，但有两个尾巴：
1. **发布多一次网络探测**：每次发布都要 ffprobe 一次 COS 外链（实测单次 ~0.9s，失败即回退估算值——
   而回退就意味着偏差重新出现，且只有 warning 日志、无告警）。
2. **拼接阶段「改造时长」这件事对运营不可见**：`concat.py:484-490` 在成品不足下限时用 BGM 尾段
   补足到 `min_allowed + 2`（目标 600s → 下限 480 → 成品 482s），`concat.py:461-477` 超上限时 atempo
   压到 720s。T01925 盘点实证：28 条成品恰为 482.064s、6 条恰为 720.0xxs，其中 DB 估算低到 86s 的
   条目内容其实只有 86s，**成品时长「达标」是靠 BGM 硬凑的**。按成品时长做「30 分钟保底」（T01657 口径）
   类核验会把这类节目误判为达标。

【要做的事】
1. 拼接阶段的实测 `duration` 随 `review` 落库并透传到 episode：
   - `backend/app/models/review.py`（现只有 `audio_url:35` / `hls_url:37`，无时长字段）加实测时长列，
     走项目既有的加列迁移方式（`backend/app/main.py` 里有 `_make_...` 列迁移清单，参考
     `min_duration_sec` / `hls_url` 的加法），不要手写裸 SQL 改生产库。
   - `backend/app/services/workflow_scheduler.py:1412-1436` `_create_review` 把
     `context["duration"]`（`concat.py:578-582` 已返回，现在被丢弃）一并写入。
   - `publish_episode` 改为**优先取 review 的实测值**，探测只作为兜底（顺序：review 实测 → 探测 → 估算）。
2. 同一处把「补足/压缩了多少秒」也带出来：`concat.py` 在 padding 分支记 `supplement_sec`、
   atempo 分支记 `original_duration`，随 context 落 review/episode（或至少落日志+可查字段），
   管理端节目列表对「被补足」的节目给出可见标记，供运营按内容时长而非成品时长核验。
3. 迁移在**已有数据**上必须安全：列可空、默认 NULL，历史行不回填（历史 90 条已由
   `_validate/t01925_backfill_duration.py` 校正完毕）。
4. 自验：
   - `cd backend && .venv/Scripts/python.exe -m pytest tests -q` 全量绿（注意
     `test_stall_alert.py::test_dedup_same_day_local` 有独立失败单，若仍在可单独说明）；
   - 补一条用例断言「context 有实测 duration 时，publish 不再发起探测」（可用 monkeypatch 计数探测调用）；
   - 真实链路冒烟：跑一次 `concat()` 级别的本地拼接（不花钱、不触发 LLM/TTS，用已有 TTS 分段缓存或
     `_validate/t01871_run` 那类既有素材），确认 review 行里带上了实测时长与补足秒数。

【硬约束】
- 不改 `.env`，用环境变量注入；不改用户生产配置。
- 频道/档位类配置改动走管理端接口，不直写库。
- 不动真实用户（dev 库 user id 1、2）的数据。
- 不在无预算确认下触发 LLM/TTS 付费链路。
- 涉及库结构变更：先在复制出来的库上验证迁移，再上真实 `backend/data/news.db`，并留备份。
