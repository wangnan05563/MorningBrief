# MorningBrief 运营后台全站 UI 一致性审计与优化报告

> 日期：2026-10-10 · 范围：admin-web 全部 31 个桌面路由页（移动端 /m 与登录页按既有约定不在桌面规范内）
> 方式：3 路并行静态审计（设计基线校准）→ 分级修复 → vite build 验证 → 实例通道 e2e 全量回归
> 结论提交：`368cc7b`（24 文件，+163/−79）

## 一、设计基线（判定依据）

- 桌面卡片页根容器必须带 `.page-container`（24px 内边距，<1440px 收窄 16px）；全屏分栏页（数据库维护）为白名单例外
- 列表/表格空态必须 `<el-empty>`；初始加载用 `v-loading`
- 图标+文字动作用共享 `IconButton`（Tooltip/aria 统一）
- 6 套主题经 CSS 变量切换，`showcase` 为暗黑主题 —— 硬编码浅色 = 主题断裂
- `.toolbar`/`.top-bar` 均为 global.scss 认可的操作栏令牌（窄屏自动换行）

## 二、审计总览

全部 31 页均已有 `.page-container`（贴边类问题为零）；无重复大标题；表格普遍 stripe + `fixed="right"`。
问题集中在四类：**主题断裂（P1）×4 页、空态缺失 ×11 表、加载态缺失 ×3 页、按钮规范 ×1 页**。

## 三、本次已修复（commit 368cc7b）

### P1 主题断裂 / 对比度（showcase 暗黑主题不可用级别）
| 位置 | 问题 | 修复 |
|---|---|---|
| LlmMetrics 漏斗条 | `color:#fff` 压浅薄荷/霓虹底，对比度 ~1.5:1 | 新增 `--on-primary` 主题变量（6 主题各配），文字改 `var(--on-primary)` |
| KnowledgeQA 聊天界面 | `.as-body/.as-msg-content/.as-input-bar` 等 13 处 `#fff/#f7f8fa/#ebeef5` 硬编码 | 全部改 `var(--el-bg-color)/var(--el-fill-color-light)/var(--color-border)`；用户气泡改 `--el-color-primary-light-9` 随主题 |
| ChannelManagement 图标/封面编辑器 | `#303133/#909399/#f5f7fa/#dcdfe6/#409eff` 深灰字在深色弹窗近乎不可见 | 改 `var(--color-text-primary)/var(--el-text-color-secondary)/var(--el-fill-color-light)/var(--color-border)`；hover/选中态 EP 蓝 → `var(--color-primary)` + 主题阴影 |
| CourseMaterials `.hint` | 浅底提示框暗黑下断裂 | 同上主题化 |
| Tunnel 具名隧道向导 | `rgba(255,255,255,.6)` 浮层暗黑下刺眼 | 改 `var(--glass-bg)` |

### P1 交互规范
- About 版本卡：复制按钮 + 升级流程 6 处裸 `el-button`/`el-icon` → 统一 `IconButton`（补 Tooltip 与 aria-label）

### P2 空态统一（11 处表格补 `<el-empty>`）
ReviewList / ChannelManagement / QueueManagement / AdMaterials / AdPlacements / RssHealth / WorkflowList（主表）/ WorkflowDetail（素材子表）/ NotificationConfig（发送日志）/ AutoReviewConfig（审批历史）/ AIConfig（用量趋势）

### P2 加载态补齐
- AIConfig：`loading` ref 已存在但从未绑定 → 绑定到页面根
- StatsOverview：新增 `loading` ref 包裹概览加载
- DatabaseAdmin：主数据表新增 `rowsLoading`

### e2e 守卫与修复
- 布局守卫扩至「素材录入」（随功能合入），空卡片 body 守卫泛化到全部受守卫页
- 修正两条**过期断言**（UI 演进后测试未同步）：
  - login：token 已迁 HttpOnly Cookie（NFR-M103）→ 改断言 `admin_role/admin_username`
  - review 图片计数提示随 45bc938 简化为「共 M 张」
- 新增 `playwright.instance.config.js`：对运行实例直跑的 e2e 通道配置

## 四、验证

- `vite build` 通过（21.5s）
- 实例通道全量 74 用例通过（channels 1 例环境性 flaky，复跑 9/9 通过）
- 前端已原子部署至安装实例（`F:\Program Files\MorningBrief\admin-web\dist`，备份 `dist.bak-5-0057`），实例运行中
- ⚠️ 部署产物包含工作区当时全部前端改动（含另一会话未合入的素材录入功能 WIP）

## 五、遗留建议（未修，按价值排序）

1. **指标卡类名割裂**：ChannelHealth `.summary-card` / RssHealth `.count-card` / LlmMetrics `.rate-card` vs StatsOverview `.metric-card` —— 建议统一复用 `.metric-card`
2. **图表/日历硬编码品牌色**：AdSchedule 图例与日期格（马卡龙 rgba）、StatsOverview chart.js `#7ECEC1`、ChannelHealth mini 折线 —— 建议读 CSS 变量或按主题映射
3. **卡片间距节奏**：BookFinder 12px / QueueManagement 16px / BookPool 12px / MaterialLibrary 4px，与 24px 基线不一
4. **响应式栅格**：QueueManagement 统计卡固定 `:span="6"`、Maintenance 固定 `:span="8"`、ReviewDetail 固定 14/10 两栏、AIConfig 多处固定宽度 select —— 窄窗挤压风险
5. **死 CSS 清理**：ad/stats 多页 `.toolbar .page-title` 残留（T00811 移除标题后未删）
6. WorkflowProgressIndicator 状态色硬编码（`#4CAF50/#FFC107/#F44336`）
7. `global.scss` `.el-card box-shadow !important` 覆盖了部分页 `shadow="never"` 意图，需定夺全站是否统一软阴影
8. RssHealth `.top-bar` 单子元素时内容靠左（若需右对齐改 `justify-content:flex-end`）
9. AIConfig TTS 预设 hex（原注释为规避粉彩主题对比度而保留，记为已知例外）

## 六、实例通道 e2e 使用方法（新增能力）

```bash
# 1) 进程级解除实例限流（429 会打断静态资源加载 → 页面不渲染、e2e 假失败）
#    停实例后以 RATE_LIMIT_PER_MINUTE=999999 环境变量重启，跑完恢复正常重启
# 2) 生成 /news 前缀的 spec 副本（goto 与数据驱动 path 均需前缀）
sed -e "s#page.goto('/#page.goto('/news/#g" -e "s#path: '/#path: '/news/#g" \
    -e "s#from './helpers/mock#from '../helpers/mock#g" \
    tests/xxx.spec.js > tests/_instance/xxx.spec.js
# 3) 运行（API 全 mock，不触真实数据）
node node_modules/@playwright/test/cli.js test --config=playwright.instance.config.js
# 4) 跑完恢复实例（不带环境变量重启）
```

要点：`executablePath` 必须放在 `use.launchOptions` 下；1600×900 视口必须放进 `projects[].use`（否则被 `devices['Desktop Chrome']` 的 1280 覆盖 → <1440 触发响应式 16px 内边距，守卫假失败）。
