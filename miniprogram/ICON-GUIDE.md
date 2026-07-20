# 小程序图标使用规范

> 本文档定义 MorningBrief 小程序图标资源的选用标准、设计语言、使用场景与维护流程。所有新增/修改图标须遵循本规范。

## 一、设计语言

延续 web 端 favicon.svg 设计语言，保持品牌一致性。

| 维度 | 规范 |
|------|------|
| 整体风格 | 清新马卡龙配色 + 圆润大圆角 + 扁平化 |
| 主色 | 薄荷青 `#7ECEC1`（主色）、蜜桃粉 `#FFD3E0`（辅助） |
| 渐变 | 主色渐变 `#7DD3DD → #5BC0BE`；粉渐变 `#FFD3E0 → #FF9AA2` |
| 线条 | stroke-width: 2-3，stroke-linecap: round，stroke-linejoin: round |
| 图标库来源 | Tabler Icons (MIT License, https://tabler-icons.io) |
| 视觉层次 | 圆角方形背景烘托主体图标，主体保持白色或品牌色 |

## 二、目录结构

```
miniprogram/images/
├── icons/                    # 运行时使用的 PNG 图标（小程序原生支持）
│   ├── tab-today-active.png      # tabBar - 今日 - 选中态
│   ├── tab-today-inactive.png    # tabBar - 今日 - 未选中态
│   ├── tab-history-active.png    # tabBar - 历史 - 选中态
│   ├── tab-history-inactive.png  # tabBar - 历史 - 未选中态
│   ├── tab-profile-active.png    # tabBar - 我的 - 选中态
│   ├── tab-profile-inactive.png  # tabBar - 我的 - 未选中态
│   ├── play.png                   # 播放（实心三角）
│   ├── pause.png                  # 暂停（实心双竖条）
│   ├── skip-back.png             # 上一首
│   ├── skip-forward.png          # 下一首
│   ├── play-mini.png             # 列表项小播放图标
│   ├── favorite.png              # 收藏（线框心形）
│   ├── favorite-filled.png       # 已收藏（填充心形）
│   ├── moon.png                  # 睡眠定时器未激活
│   ├── alarm.png                 # 睡眠定时器激活
│   ├── search.png                # 搜索放大镜
│   ├── chevron-right.png         # 右箭头（列表项指示）
│   ├── alert.png                 # 错误警告
│   ├── duration.png              # 时长图标（小尺寸）
│   ├── headphones.png            # 耳机装饰（空状态/未登录/关于）
│   ├── music.png                 # 音乐装饰（队列空状态）
│   ├── newspaper.png             # 报纸装饰（历史空状态）
│   └── radio.png                 # 收音机装饰（频道空状态）
└── svg-src/                  # SVG 设计源文件（仅供维护，不参与运行）
    ├── *.svg                     # 各图标的矢量源文件
    ├── convert-icons.js          # SVG → PNG 转换脚本（Node.js + @resvg/resvg-js）
    └── generate-icons.ps1        # PowerShell 包装脚本（备选，依赖 ImageMagick）
```

## 三、尺寸规范

| 场景 | PNG 尺寸 | 用途 | 设计 viewBox |
|------|----------|------|---------------|
| tabBar 图标 | 81×81 px | 微信 tabBar 推荐 | 64×64 |
| 页面内大按钮图标 | 48×48 px | 圆形播放按钮等 | 24×24 |
| 列表项小图标 | 32×32 px | 时长前置、列表项播放小图标 | 24×24 |
| 顶部工具栏图标 | 48×48 px | 搜索、睡眠定时器入口 | 24×24 |
| 空状态装饰图标 | 96×96 px | 空状态、未登录卡片 | 64×64 |

**说明**：小程序 `<image>` 标签会用 `mode="aspectFit"` 自适应容器尺寸，PNG 实际尺寸为渲染上限。为保证 Retina 屏清晰度，PNG 尺寸应 ≥ 容器 rpx ÷ 2（设计稿 750rpx → 375px 设备）。

## 四、使用场景与选用标准

### 4.1 tabBar 图标

**选用标准**：圆角方形 + 渐变背景 + 白色线条图标。三个 tab 必须使用语义差异化图标（不可共用）。

| Tab | 选中态 | 未选中态 | 图标语义 |
|-----|--------|----------|----------|
| 今日 | `tab-today-active.png` | `tab-today-inactive.png` | 太阳（每日更新） |
| 历史 | `tab-history-active.png` | `tab-history-inactive.png` | 时钟（时间记录） |
| 我的 | `tab-profile-active.png` | `tab-profile-inactive.png` | 用户（个人中心） |

**颜色配置**（app.json）：
- 未选中文字色：`#A0AEC0`（暖灰）
- 选中文字色：`#5BA89B`（薄荷深青）

### 4.2 播放控制图标

**选用标准**：彩色背景上使用白色实心图标，禁止使用线框图标（视觉重量不足）。

| 场景 | 图标 | 尺寸 |
|------|------|------|
| 大圆形播放按钮（120rpx） | `play.png` / `pause.png` | 48×48 px |
| 上一首/下一首（72rpx 圆形） | `skip-back.png` / `skip-forward.png` | 48×48 px |
| 列表项圆形播放小图标（56rpx） | `play-mini.png` | 32×32 px |

### 4.3 状态切换图标

**选用标准**：双态设计（未激活/激活），激活态使用蜜桃粉强调色。

| 场景 | 未激活 | 激活 | 颜色 |
|------|--------|------|------|
| 收藏 | `favorite.png`（线框） | `favorite-filled.png`（填充） | `#FF6B8A`（蜜桃粉） |
| 睡眠定时器 | `moon.png` | `alarm.png` | `#5BA89B` → `#FF6B8A` |

### 4.4 顶部工具栏图标

**选用标准**：圆形浅灰背景 + 品牌色图标。

| 场景 | 图标 | 容器尺寸 | 图标尺寸 |
|------|------|----------|----------|
| 搜索入口 | `search.png` | 64rpx 圆形 | 36rpx |
| 睡眠定时器入口 | `moon.png` / `alarm.png` | 64rpx 圆形 | 36rpx |

### 4.5 列表项指示图标

**选用标准**：弱化色，不抢主信息焦点。

| 场景 | 图标 | 尺寸 | 颜色 |
|------|------|------|------|
| 时长前置 | `duration.png` | 24rpx | `#A0AEC0`（暖灰） |
| 右箭头指示 | `chevron-right.png` | 32rpx | `#A0AEC0` |

### 4.6 错误提示图标

**选用标准**：蜜桃粉警示色，配合浅粉背景。

| 场景 | 图标 | 尺寸 | 颜色 |
|------|------|------|------|
| 播放错误提示 | `alert.png` | 32rpx | `#FF6B8A` |
| 详情加载失败 | `alert.png` | 120rpx（空状态） | `#FF6B8A` |

### 4.7 空状态装饰图标

**选用标准**：品牌色线框图标，弱化视觉重量以突出文案。每个场景应使用语义匹配的图标。

| 场景 | 图标 | 语义 |
|------|------|------|
| 节目未上线 / 未登录 / 关于页 logo | `headphones.png` | 耳机（产品定位） |
| 历史节目空状态 | `newspaper.png` | 报纸（新闻内容） |
| 收藏列表空状态 | `favorite.png` | 心形（收藏主题） |
| 频道列表空状态 | `radio.png` | 收音机（频道） |
| 队列空状态 | `music.png` | 音乐（音频内容） |
| 搜索无结果 | `search.png` | 放大镜（搜索主题） |

## 五、emoji 使用边界

**禁止使用 emoji 的场景**：
- 功能性按钮（播放、暂停、收藏、搜索等）
- 状态切换图标（睡眠定时器、收藏等）
- tabBar 图标
- 列表项指示箭头
- 错误提示

**保留 emoji 的场景**（如有需要）：
- 纯装饰性内容（如静态文案中的表情符号）
- 用户生成内容（评论、反馈中的 emoji）

**替换原则**：功能性 emoji → PNG 图标；装饰性 emoji 视情况保留。原因：emoji 跨平台渲染不一致（iOS 彩色 vs Android 黑白），影响产品视觉一致性。

## 六、`<empty-state>` 组件使用规范

`components/empty-state` 组件支持两种图标类型：

```xml
<!-- 文字 emoji 模式（默认，已不推荐用于功能性场景） -->
<empty-state icon="📰" title="..." description="..." />

<!-- PNG 图标模式（推荐） -->
<empty-state
  icon="/images/icons/newspaper.png"
  icon-type="image"
  title="..."
  description="..."
/>
```

**规范**：所有新增空状态必须使用 `icon-type="image"` 模式，避免 emoji 跨平台问题。

## 七、维护流程

### 7.1 新增图标

1. 在 `svg-src/` 创建 SVG 源文件（基于 Tabler Icons 设计语言）
2. 在 `convert-icons.js` 的 `iconConfigs` 数组中添加配置项
3. 执行 `cd miniprogram/images/svg-src && npm install @resvg/resvg-js && node convert-icons.js`
4. 在 `app.wxss` 或对应页面 wxss 中添加尺寸样式
5. 在本规范文档"四、使用场景"章节补充选用标准

### 7.2 修改图标

1. 修改 SVG 源文件
2. 重新执行转换脚本
3. 检查所有引用该图标的页面，确认视觉无回归

### 7.3 删除图标

1. 确认无引用：`grep -r "icons/xxx.png" miniprogram/`
2. 删除 SVG 源文件和 PNG 文件
3. 删除 `convert-icons.js` 中的配置项
4. 更新本规范文档

## 八、合规说明

- **图标库许可**：Tabler Icons 采用 MIT License，可商用、可修改、可分发
- **设计源文件**：所有 SVG 源文件保留原始 Tabler Icons 设计风格，仅做颜色/尺寸适配
- **无 AI 生成内容**：所有图标均为开源图标库的标准化设计，不使用 AI 生成的预制图标
- **品牌一致性**：与 web 端 favicon.svg 保持设计语言一致（圆角方形 + 渐变背景 + 白色线条）

## 九、相关文件索引

- 小程序全局样式：[app.wxss](file:///d:/code/otherProjects/20_News/miniprogram/app.wxss)
- tabBar 配置：[app.json](file:///d:/code/otherProjects/20_News/miniprogram/app.json)
- 空状态组件：[components/empty-state/](file:///d:/code/otherProjects/20_News/miniprogram/components/empty-state/)
- SVG 转换脚本：[images/svg-src/convert-icons.js](file:///d:/code/otherProjects/20_News/miniprogram/images/svg-src/convert-icons.js)
- Web 端 favicon 设计参考：[admin-web/public/favicon.svg](file:///d:/code/otherProjects/20_News/admin-web/public/favicon.svg)
