# T02029 处理结果

来源：T01845（本单 derived_from），承接 T01925 的 duration 校正真机复核项。
本单正文自身已写明处置方式：**并入 T01922 的人工执行矩阵，不新建单**。

## 根因

这一项被写成「只能真机看」，但拆开看它其实包含三个互相独立的命题，其中两个在本环境
就有确定性证据，不需要设备：

1. **「DB duration 偏短 → 进度条没到底就被判听完」**——这条因果链在代码里根本不成立。
   小程序所有进度/完播计算取的是 `audioManager.duration`（真机播放器实测文件时长），
   `episode.duration` 在客户端只有 4 个消费点，全部是展示标签。DB 值偏短错的是
   「显示 586s 实为 597s」这类口径，不是进度条。
2. **下发值与真机实测值是否一致**——`play_log.duration` 存的就是客户端上报的
   `audioManager.duration`，与后端下发值来自两条独立路径，等价于一次已经发生过的真机复核。
   库里 8 条上报直接可查，不必再听一遍。
3. **ep58 结尾那段补足的听感**——这条确实要人耳，但「尾段是不是语音、有多响」可量化，
   量化完再把人耳那一格交回去，比让人从零开始听 8 分钟有效。

## 影响范围

- 无代码改动（硬约束：只读播放、不改小程序代码；本单连后端代码都没动）。
- 产物：`_validate/t01922_pack/README-真机测试说明.md` 新增「三之二·补」节 +
  3 个取证脚本与其输出。
- 数据库：全程 `mode=ro` 打开 `backend/data/news.db`，0 写入；未新增用户、未碰真实用户
  id 1/2 的数据。COS 只做了 2 次 GET。

## 修复

本单是复核单，「修复」即把结论写回任务正文指定的文件：

| 文件（绝对路径） | 改动点 |
| --- | --- |
| `D:\code\otherProjects\20_News\_validate\t01922_pack\README-真机测试说明.md` | 「三之二」表后追加「三之二·补」：①进度/完播来源逐行核对结论（含 `audio.js:122/1311/1378`、4 个展示消费点、`play_service.py:65`）②play_log 真机上报对账表（8 行）③ep58 尾段声学取证表 ④仍需人耳的那一格与听感重点 |
| `D:\code\otherProjects\20_News\_validate\t02029_playlog_crosscheck.py` | 新建：只读连库，把 `play_log.duration`（真机上报）与 `episode.duration` 校正前/后逐条对账，并统计「已听秒数超下发时长」「completed 时 position 与真机 duration 之差」 |
| `D:\code\otherProjects\20_News\_validate\t02029_tail_profile.py` | 新建：成品 mp3 逐 30s RMS 能量剖面（ep58 vs 对照 ep100） |
| `D:\code\otherProjects\20_News\_validate\t02029_tail_acoustic.py` | 新建：过零率 / 包络自相关 / 低能量秒占比，用于区分「语音」与「循环 BGM 铺底」 |

## 验证

1. **进度/完播不读 DB 值**（代码逐行核对，非推测）：
   `services/audio.js:122` `finalPos = Math.floor(audioManager.duration || 0)`；
   `:1311` 周期上报 `Math.floor(audioManager.duration)`；`:1378` seek 上限保护同样用真机
   duration；`pages/course/course.js:173` 的 `ratio = p.position / p.duration` 里
   `p.duration` 也是 play_log 中客户端上报值。
   消费 `episode.duration` 的只有 `index.js:468`、`detail.js:244`、`history.js:364`、
   `course.js:184` 四处，全是 `duration_label` 类展示。
2. **真机上报对账**（`_validate/t02029_playlog_crosscheck.txt`）：
   ```
   ep100  真机上报 597 | DB 校正前 586（差 11s）| DB 现值 597（差 0s）
   ep99   真机上报 482 | 校正前 452（差 30s）  | 现值 482（差 0s）
   ep3/4/5/50/91/96 同样：校正前偏差 1~65s，现值全部 0s
   偏差 >1s 的条数：校正前 7/8 → 现值 0/8
   「已听秒数 > 下发时长」：0 条
   completed=1 的 2 条：position - 真机 duration = 0s / 0s（完播判在真实结尾，无提前）
   ```
3. **全库下发值 vs 成品实测**（T01925 校正后复点，`t01925_duration_audit_after.json`）：
   90/95 条可探测，`|DB-实测|` min=0.0 / 中位=0.0 / **max=0.01s**，>1s 的 0 条；
   5 条（id 2、70~73）外链不可探测，跳过原因已知。
4. **ep58 尾段量化**（`t02029_tail_profile.txt` / `t02029_tail_acoustic.txt`）：
   稿件 `full_text` 仅 481 字（`estimated_duration=86`）而成品 482s → 约 396s 非语音。
   声学特征（对照 ep100：3242 字/597s 正常一期）：
   ```
   ep58 语音段 0-86s    -27.3 dBFS  std 1.9  ZCR 1251/s  包络自相关 0.25@6s
   ep58 尾段 400-482s   -27.9 dBFS  std 1.9  ZCR  821/s  包络自相关 0.46@5s   ← 器乐特征
   ep100 语音段 0-86s   -26.9 dBFS  std 1.8  ZCR 1314/s  包络自相关 0.16@18s
   ep100 尾段 515-597s  -27.3 dBFS  std 2.1  ZCR 1269/s  包络自相关 0.17@7s
   ```
   尾段过零率比语音段低 34%、自相关峰 0.46（语音仅 0.16~0.25）→ 周期性器乐；
   但平均能量与语音段几乎相同（-27.9 vs -27.3）→ **补足用的 BGM 是满响度铺在结尾的**，
   不是低音量垫底。「低于 -45dBFS 秒占比」四段均 0%（成品整期响度归一，该指标无区分度，
   列出备查不作判据）。
5. 物料保留：`_validate/t02029_ep58.mp3`（从 COS GET 的成品，供人耳复核那一格直接听）；
   对照用的 ep100 下载件已删除，其数据留在两份 txt 里。

## 本次回写

- 无新建单（本单正文即要求「并入 T01922 的人工执行矩阵，不新建单」，已照此执行）。
- 复核结论已写回 `_validate/t01922_pack/README-真机测试说明.md` 三之二·补。
- 提交：`fd4b016`（结论与取证脚本）、`965fc26`/`1aa3697`（同批 T02028）。

## 下一步建议

1. **本单三个命题里两个已离线闭环，真机矩阵里 ep100/ep58 两行可以只保留「听感」一列**，
   进度条/完播两列按 2) 的证据直接判「通过（离线等价）」，不必再占一次设备。
   （仅观察不建单，随回传并入原单 T01845）
2. **ep58 类「满响度 BGM 铺 6 分钟」是可感知的质量问题**：内容 86s 被补到 482s，
   且补足段与语音同响度，听众很可能当成播放故障。处理方向是缩短补足上限
   （`concat.py` 的 `min_allowed + 2` 策略）或把 `generate_bgm_tail` 的音量降到
   垫底量级，属产品决策。本单为派生单不再派生，该剩余工作随本次回传并入原单 T01845，
   由其决定是否派生。（仅观察不建单）
3. T02028 已把 `supplement_sec` 落到 review/episode 并让「凑时」在管理端可见，
   上线后新产生的节目可直接按该字段筛出同类样本，不必再从字数与成品时长反推。
   （仅观察不建单）
