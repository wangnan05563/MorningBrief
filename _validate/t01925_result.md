# T01925 回传：已发布成品实测时长与 DB episode.duration 系统性偏差

来源：T01845（经 T01871 → T01922 取证顺带发现转出）。本单结论同时回填 T01845。

## 根因

**不是「拼接后测量」与「上传产物」不一致，而是实测值从未走到发布这一步——发布一直写稿件估算值。**

- 拼接阶段确实按成品实测：`backend/app/workflow/stitch/concat.py:455`
  `duration = await get_audio_duration(final_path)`，并把该值随 `{"final_audio_url", "hls_url", "duration"}`
  返回进 workflow context（`concat.py:578-582`）。
- 断点在下一跳：`workflow_scheduler._create_review`（`backend/app/services/workflow_scheduler.py:1412-1436`）
  只把 `final_audio_url` / `hls_url` 写入 `review`，**context 里的 `duration` 被丢弃**（`Review` 表根本没有时长字段，
  `backend/app/models/review.py:35-37`）。
- 发布时 `ContentService.publish_episode` 取的是 `script.estimated_duration`
  （改前 `backend/app/services/content_service.py:569`），而该字段是**按字数反算的文本估算**：
  `int(total_words / words_per_min * 60)`（`backend/app/workflow/llm/rewriter.py:1583`、
  `backend/app/routers/admin/scripts.py:145`）。
- 估算与成品的差主要来自拼接阶段对时长的**强制改造**，这两种情形偏差最大：
  - 不足下限被补足：`concat.py:484-490` `shortfall = (min_allowed - duration) + 2`，
    全局目标 600s 的允许区间是 `[480, 720]`（`backend/app/workflow/duration.py:19-20,48-56`
    `DURATION_LOW_RATIO=0.80 / DURATION_HIGH_RATIO=1.20`）→ 成品被精确凑到 **482s**；
  - 超上限被 atempo 压到上限（`concat.py:461-477`）→ 成品落在 **720.0s**。
  实测证据：本次盘点里 **28 条**成品时长恰为 482.064s、**6 条**恰为 720.005~720.013s。
  同批文件字节数也完全一致（482s 组全部 7,713,061B、720s 组全部 11,521,087B），但首尾 256KB
  md5 互不相同 → 是「不同内容被凑到同一时长」，不是「同一文件被发到多个 key」。

**判据：属「现行链路仍在发生」，不是历史批次独有。**
`git log -S"duration=script.estimated_duration" -- backend/app/services/content_service.py` 只有两笔：
`9709034`（2026-07-08 初始化）与本次修复 `96237b9`——发布写估算值自项目初始化起从未改过；
`_create_review` 相关 `final_audio_url` 同样只有初始化一笔，即实测值从未被透传。
最新批次（2026-07-29 建单、64kbps standard 档，ep87~ep91）偏差 10/15/30/45/62s 依旧存在，
证明到本单开工时仍在发生。

## 影响范围

- 小程序进度与完播：`apps/miniprogram/services/audio.js` 用 `audioManager.duration`（真实文件时长）算
  `finalPos` / 已听秒数，后端下发的 DB 值偏小 → 收听百分比与「听完」判定偏移（最大 396s，约 82% 的节目时长）。
- 「30 分钟保底」（T01657 口径）的运营核验：以 DB duration 判断是否达标会**低估**成品时长，
  反向也可能把被补足到 482s 的短节目误判为达标——本次盘点里 482s 组对应的 DB 估算值低至 86s（ep58）。
  注意这类节目的**真实内容长度并非 86s**：`concat.py:496-501` 有「原时长 < 下限 50% 直接判失败」的守卫
  （下限 480 → 门槛 240s），能补足成功说明拼接前实测已在 240s 以上，即估算值 86s 本身就低估了 3 倍；
  但补足段确实在凑时长，按成品时长做保底核验仍会把「内容不够」的节目判为达标，需要按内容而非时长判定。
- 缓存/统计：`episode.duration` 经 `publish_service`、`content_service` 直出到列表与详情接口，无二次计算，
  校正后各读路径自动受益，无需改动。
- 不影响音频本身：成品文件、COS 对象、HLS 均正常（COS Content-Range 与本地下载字节数一致，T01922 已验）。

## 修复

1. `backend/app/services/content_service.py:565-572`——发布时改为**以上传产物实测时长为准**：
   ```python
   measured_duration = await self._measure_audio_duration(review.audio_url)
   ...
   duration=measured_duration or (script.estimated_duration if script else 600),
   ```
   估算值降级为「探测不可用时的回退」，不改默认行为之外的任何逻辑。
2. `backend/app/services/content_service.py:603-621`——新增 `_measure_audio_duration()`：
   仅对 `http(s)` 外链用 `get_audio_duration_f`（复用 `ffmpeg_wrapper`，内部 `to_thread` + ffprobe）探测并
   `round` 取整；本地 `/audio/...` 相对路径与 `None` 直接返回 `None`；任何异常（超时/网络/文件缺失）
   记 warning 后返回 `None`，**绝不阻塞发布**。
3. 历史数据重算：`_validate/t01925_backfill_duration.py`（默认 dry-run，`--apply` 前强制要求备份文件存在，
   否则拒绝写库）。
4. 取证脚本与产物（全部只读，不改配置、不直写库）：
   - `_validate/t01925_duration_audit.py` / `t01925_duration_audit.json`（修复前全量对照）
   - `_validate/t01925_duration_audit_after.json` / `t01925_audit_after.txt`（修复+重算后复核）
   - `_validate/t01925_audit_out.txt`（修复前逐条控制台输出）
   - `_validate/t01925_fingerprint.py` / `t01925_fingerprint.json`（首尾 256KB md5 + 字节数取证）
   - `_validate/t01925_dupgroups.txt` / `t01925_originals.txt` / `t01925_index.txt`
     （共享 audio_url 分组、逐条偏差表、修复前 DB 值索引）
   - commit `96237b9`

## 验证

**全量盘点（95 条含 audio_url 的 episode，90 条可探测 + 5 条本地产物已清理无法探测，探测失败 0）**

修复前 `ffprobe 实测 − DB duration`：

| 口径 | 值 |
|---|---|
| 偏差中位 / P25 / P75 | **+30.0s / +11.0s / +58.0s** |
| 偏差最小 / 最大 | **−12.0s / +396.0s** |
| 偏短（real>db）/ 偏长 / \|偏差\|≤1s | **86 / 4 / 1**（共 90） |
| 成品码率档 | 64kbps、128kbps 两档均有偏差 |
| 按创建日期批次（avg 偏差） | 07-18 −1.0 / 07-20 +16.0 / 07-21 +15.6 / 07-22 +51.6 / 07-24 +87.0 / 07-25 +65.8 / 07-27 +98.0 / 07-28 +103.0 / **07-29 +77.6**（n=14，含 64kbps standard 新档）→ **除 07-18 单条外每个批次都在偏**，排除「某次历史改动独有」 |

典型条目：ep100 586→597、ep99 452→482、ep58 86→482（被补足到 480+2）、ep46 709→720（被 atempo 压到上限）。

**时长口径自检**：这些 MP3 均无 Xing/Info 头（T01922 帧头取证），ffprobe 对纯 CBR 会按 size/bitrate 推算，
故额外用逐帧计数交叉校验本地副本：`_validate/t01845_samples/ep99.mp3` = 18,454 帧 × 1152/44100 = **482.064s**、
`ep100.mp3` = 22,856 帧 = **597.055s**，与 ffprobe 的 482.0 / 597.0 一致 → 盘点口径可信，偏差不是探测假象。

**修复后复核（已执行）**：

1. 备份：`cp backend/data/news.db backend/data/news.db.bak-t01925`（30,539,776B，两侧一致），
   `PRAGMA integrity_check = ok`；写库前确认无后端进程监听（`netstat` 无 8000x 端口）。
2. `_validate/t01925_backfill_duration.py --apply` → **需校正 90 条 / 共 95 条，跳过本地路径 5，探测失败 0**，
   逐条 `old→new` 落 `_validate/t01925_backfill.json`。
3. 重跑全量盘点：`delta_min 0.0 / delta_median 0.0 / delta_max 0.01`，`count_zeroish=90`，
   偏短/偏长计数归零 → DB 与成品时长一致（残余 0.01s 是整数取整 vs 帧计数）。
4. 代码层：`backend/tests/test_content_service.py` 新增 2 例（实测值覆盖估算值：估算 86 + 实测 482.064 → 落库 482；
   本地路径 / None / 探测异常三种情形回退 None 不抛错），并把原发布用例改为 monkeypatch 探测函数避免真发网络请求。
   `pytest backend/tests/test_content_service.py -q` → **10 passed**。
5. 真实链路冒烟（只读，不写库）：直接调用新 helper 打真实 COS 对象——
   `ep100 → 597`、`ep58 → 482`、`/audio/... 本地路径 → None`、`None → None`。
6. 全量回归：`cd backend && pytest tests -q` → **1040 passed, 1 failed**。
   唯一失败 `tests/test_stall_alert.py::test_dedup_same_day_local`（断言 `status=="skipped"` 实为 `"success"`，
   属停留告警同日去重逻辑，与本次改动无关：该文件与 content_service 无依赖关系，单独复跑亦失败）。

**未覆盖项（诚实标注）**：
- 修复只影响**此后新发布**的节目；历史 90 条已用重算脚本校正，5 条（ep2/70/71/72/73）因本地音频文件已被清理、
  audio_url 又非外链而无法实测，仍保留估算值，无法验证。
- 小程序端「进度条/完播」的实际观感改善需真机复听（本环境无设备）——不标 verified。

## 本次回写

- 建派生单 3 张（本单是 T01845 的派生单，按「派生单不再派生」规则全部挂到最初原单 **T01845** 下，
  建单前按 REST（未归档 62 条 + 归档 37 条）全量查重，无同题单）：
  - **T02027**【AI回写待审核】test_stall_alert 同日去重失效：当日已有成功告警仍重复发送
    （修复验证跑全量回归时发现的既有缺陷，与本单主题无关）。
  - **T02028**【AI回写待审核】review 落库拼接实测时长与补足/压缩秒数：发布去掉网络探测，
    让「被凑出来的时长」对运营可见（本单用发布期探测绕过，这条是结构性收口）。
  - **T02029**【AI回写待审核】真机复核 duration 校正后的小程序收听百分比与完播判定
    （执行表已就地追加到 `_validate/t01922_pack/README-真机测试说明.md` 的「三之二」节，
    与 T01922 的三端播放矩阵同批跑，不重复占用人力）。
- 代码与取证产物已提交：commit `96237b9`（fix(publish): episode.duration 改取成品实测时长）。
- 生产数据变更：**已执行**历史重算（90 条 `episode.duration` 校正），库备份留在
  `backend/data/news.db.bak-t01925`，回滚命令见「下一步建议」第 1 条。

## 下一步建议

1. **备份的处置**（仅观察不建单——复核无误后由用户决定，勿在确认前删除）：
   回滚 `cp backend/data/news.db.bak-t01925 backend/data/news.db`；确认后
   `rm backend/data/news.db.bak-t01925`。
   缓存在进程内 TTLCache（列表 600s / 详情 1800s），后端重启或 TTL 到期后自然读到新值，无需清缓存动作。
2. 真机收听百分比/完播复核 → **已建派生单 T02029**（见上，与 T01922 播放矩阵同批执行）。
3. 发布期 ffprobe 探测的结构性替代（review 落实测时长 + 补足秒数可见）→ **已建派生单 T02028**。
4. `test_stall_alert::test_dedup_same_day_local` 既有失败 → **已建派生单 T02027**。
