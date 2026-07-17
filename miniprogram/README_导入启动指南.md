# 微信小程序项目导入与启动指南

## 项目概述
本项目是一个名为"今日要闻"的语音新闻播报小程序，采用马卡龙配色风格，主要功能包括：
- 今日节目展示与播放
- 历史节目浏览
- 用户个人中心
- 音频断点续播
- 播放进度上报

## 一、环境准备

### 1. 必需软件
- 微信开发者工具（最新版）
- 后端服务已部署并运行

### 2. 项目结构
```
miniprogram/
├── app.js                  # 全局入口：登录、播放器初始化
├── app.json                # 全局配置
├── app.wxss                # 全局样式
├── project.config.json     # 项目配置
├── sitemap.json            # 站点地图
├── pages/                  # 页面目录
│   ├── index/             # 首页/播放页
│   ├── history/           # 历史记录
│   ├── profile/           # 个人中心
│   ├── detail/            # 节目详情
│   ├── favorites/         # 收藏夹
│   ├── feedback/          # 意见反馈
│   ├── settings/          # 设置
│   └── about/             # 关于
├── components/            # 自定义组件
│   ├── audio-player/      # 音频播放器
│   ├── episode-card/      # 节目卡片
│   └── empty-state/       # 空状态
├── services/              # 服务层
│   ├── api.js             # API封装
│   ├── audio.js           # 音频服务
│   └── auth.js            # 认证服务
└── utils/                 # 工具函数
    ├── config.js          # 全局配置
    └── tracker.js         # 埋点追踪
```

## 二、导入项目步骤

### 方法一：通过微信开发者工具导入

1. **打开微信开发者工具**
   - 启动微信开发者工具
   - 选择"导入项目"

2. **填写项目信息**
   ```
   项目路径：D:\code\otherProjects\20_News\miniprogram
   AppID：wx0000000000000000（测试号）
   项目名称：MorningBrief
   本地目录：保持默认
   ```

3. **配置检查**
   - 确保 `project.config.json` 中的配置正确
   - 检查 `app.json` 中的页面注册

4. **编译运行**
   - 点击"编译"按钮
   - 等待编译完成
   - 在模拟器中查看效果

### 方法二：通过命令行导入

```bash
# 进入项目目录
cd D:\code\otherProjects\20_News\miniprogram

# 使用微信开发者工具CLI导入
wechat devtools import --path . --appid wx0000000000000000
```

## 三、关键配置说明

### 1. 项目配置 (project.config.json)
```json
{
  "description": "MorningBrief 语音新闻播报小程序",
  "miniprogramRoot": "./",
  "compileType": "miniprogram",
  "setting": {
    "urlCheck": false,
    "es6": true,
    "enhance": true,
    "postcss": true,
    "minified": true
  },
  "appid": "wx0000000000000000",
  "projectname": "MorningBrief",
  "libVersion": "3.3.4"
}
```

### 2. 应用配置 (app.json)
```json
{
  "pages": [
    "pages/index/index",
    "pages/history/history", 
    "pages/profile/profile",
    "pages/detail/detail"
  ],
  "tabBar": {
    "list": [
      {"pagePath": "pages/index/index", "text": "今日"},
      {"pagePath": "pages/history/history", "text": "历史"},
      {"pagePath": "pages/profile/profile", "text": "我的"}
    ]
  },
  "requiredBackgroundModes": ["audio"]
}
```

### 3. API配置
开发环境：`http://localhost:8000/api/v1`
生产环境：`https://api.example.com/api/v1`

## 四、启动与调试

### 1. 基础启动
- 确保后端服务正常运行
- 在微信开发者工具中点击"编译"
- 观察控制台日志输出

### 2. 常见问题排查

#### 接口请求失败
```javascript
// 检查网络配置
// 开发者工具 -> 详情 -> 本地设置
// ✓ 不校验合法域名、web-view（业务域名）
```

#### 音频播放问题
- 确认 `requiredBackgroundModes` 包含 `audio`
- 检查音频URL是否可访问
- 验证音频格式兼容性

#### 登录认证失败
- 检查 `auth.js` 中的登录流程
- 确认后端 `/auth/login` 接口可用
- 验证 `wx.login` 返回值

### 3. 调试技巧

#### 数据流监控
```javascript
// 在控制台查看全局数据
console.log(getApp().globalData);

// 监听组件生命周期
// 开发者工具 -> 调试器 -> Component
```

#### 性能优化
- 使用开发者工具的Performance面板
- 检查图片资源大小
- 优化API请求频率

## 五、部署上线

### 1. 代码上传
- 在开发者工具中点击"上传"
- 填写版本号和项目备注
- 提交到微信公众平台

### 2. 配置修改
```javascript
// 修改 utils/config.js 中的API地址
const IS_RELEASE = true; // 启用生产环境
const CONFIG = {
  apiBaseUrl: 'https://api.example.com/api/v1', // 生产域名
  // ...
};
```

### 3. 审核准备
- 完善隐私政策说明
- 准备应用截图
- 填写服务类目

## 六、开发规范

### 1. 代码风格
- 使用ES6+语法
- 遵循微信小程序开发规范
- 统一命名约定

### 2. 组件化开发
- 公共组件放在 `components/` 目录
- 页面组件放在对应 `pages/` 子目录
- 合理拆分组件职责

### 3. 状态管理
- 全局状态使用 `App.globalData`
- 页面状态使用 `Page.data`
- 避免过度依赖全局状态

## 七、扩展建议

### 1. 功能增强
- 添加推送通知功能
- 实现离线缓存机制
- 增加多语言支持

### 2. 性能优化
- 图片懒加载
- 接口请求合并
- 虚拟列表优化

### 3. 用户体验
- 添加骨架屏
- 优化加载动画
- 改进错误提示

---
*最后更新：2026-07-15*
