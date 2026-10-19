来源：T02506（FR-UX-501 指标单位元数据）。FR-UX-501 要求「同一指标全端一致」，
本单把 PC 统计页与移动端首页（`/m/home`）统一到后端下发的 meta 上，并写了 PC↔移动端
同口径的 e2e 用例；小程序端不展示 `avg_listen_duration`，本单未动它。
但小程序端的**时长格式化**是同一类问题的另一半：秒→分秒的换算在十个文件里各写一遍。

## 现状（实测）
- 秒→`X分Y秒` / `mm:ss` 的内联换算，至少 10 处，各写各的：
  `apps/miniprogram/components/audio-player/audio-player.js:156-157`、
  `apps/miniprogram/components/episode-card/episode-card.wxml:30-31`（wxml 里直接写表达式）、
  `apps/miniprogram/pages/course/course.js:402-403`、
  `apps/miniprogram/pages/detail/detail.js:996-997 / 1003-1005 / 1018-1020`（同一文件三份）、
  `apps/miniprogram/pages/index/index.js:521`、`apps/miniprogram/pages/history/history.js:386`、
  `apps/miniprogram/pages/download/download.js:80`，
  另有 `index.wxml:143-152`、`recent.wxml:46`、`search.wxml:95`、`favorites.wxml:63` 的模板侧写法。
- 累计收听的显示：`apps/miniprogram/pages/profile/profile.js:354`
  `Math.round(totalListenDuration / 60)` → `profile.wxml:34-35` 标「收听分钟」。
  这一处的**单位**（分钟）恰好与 T02506 后管理端统一后的口径一致，但它是自己算的，
  与后端 `backend/app/models/user.py:24`（秒）之间没有任何声明关联——后端一旦改口径它不会报错。

## 建议做法
1. 新增 `apps/miniprogram/utils/format.js`（小程序无 npm 依赖，写纯函数）：
   `formatDuration(sec, { style: 'mmss' | 'cn' | 'minutes' })`，把上述 10 处收敛为一次调用；
   wxml 里的表达式改为 wxs 或预先在 js 里算好，模板不做算术。
2. 单位口径与后端对齐：小程序调用的 C 端接口（`backend/app/routers/api/users.py:93-98`
   已经把字段命名为 `total_listen_seconds`——这是全仓唯一自带单位的字段）继续保留该命名，
   并考虑把 `stats_metrics.py` 的元数据同样随 C 端接口下发，`utils/format.js` 按 meta 选择 style。
3. 收敛后加一条断言（小程序侧目前无自动化测试，最低成本做法是
   在 `apps/miniprogram/utils/format.js` 旁写一个 `node --test` 可跑的用例，
   或把它并入 `scripts/` 下的静态检查）：`grep -rn "Math.floor(.*60" apps/miniprogram/pages` 应为 0 命中。

## 验收口径
- 播放页、课程页、历史、下载列表在同一条目上显示的时长完全一致（同一 sec 值）；
- 个人中心「收听分钟」与后端 `total_listen_seconds / 60` 一致（抽查 3 个用户真实数据）；
- 全仓 `apps/miniprogram` 内不再有内联的 `/ 60`、`% 60` 时长表达式（白名单：format.js 自身）。
