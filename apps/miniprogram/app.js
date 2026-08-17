/**
 * 全局入口：登录、全局播放器初始化、预加载今日节目
 *
 * V1.3 增强：
 * - 注入 version/buildDate（构建脚本可覆盖，about 页读取展示）
 * - 隐私授权检查（__usePrivacyCheck__: true 开启后需主动引导用户同意）
 * - 小程序版本更新检测（wx.getUpdateManager）
 * - 后端地址自动发现（utils/server-discovery.js，零配置真机调试）
 *
 * onLaunch 执行顺序（V1.4 性能优化：串行 → 并行）：
 * 1. 版本信息注入
 * 2. 后端地址自动发现（discoverServer，注入 globalData.baseUrl）—— 必须先完成
 * 3. 检查小程序更新（冷启动时，与下面并行无依赖）
 * 4. 静默登录 + 预加载今日节目 并行执行
 *    - login 依赖 baseUrl（已由 discoverServer 注入），不依赖 todayEpisode
 *    - fetchTodayEpisode 仅依赖 baseUrl，不依赖 token（公开接口）
 *    - 两者并行可节省 1 个 RTT，首屏更快拿到节目数据
 * 5. 初始化全局播放器（BackgroundAudioManager 单例）
 * 6. 监听网络变化（弱网时进度上报降频）
 * 7. 隐私授权检查（涉及用户信息接口前需先同意）
 */
const { login } = require('./services/auth');
const { initPlayer } = require('./services/audio');
const { fetchTodayEpisode, channelType } = require('./services/api');
const { discoverServer, PROD_API_BASE_URL } = require('./utils/server-discovery');

// 构建脚本可在编译期注入 VERSION / BUILD_DATE 全局变量覆盖默认值
const VERSION = (typeof __VERSION__ !== 'undefined' && __VERSION__) || '1.3.0';
const BUILD_DATE = (typeof __BUILD_DATE__ !== 'undefined' && __BUILD_DATE__) || '';

App({
  globalData: {
    userInfo: null,
    token: null,
    player: null,           // 全局音频播放器单例
    todayEpisode: null,     // 预加载的今日节目
    networkType: 'wifi',    // 网络类型（弱网降频用）
    listenStats: null,      // 收听统计（profile 页兜底读取，后续接入 stats 接口）
    version: VERSION,       // 应用版本（about 页展示）
    buildDate: BUILD_DATE,  // 构建日期（about 页展示）
    privacyAuthorized: false, // 隐私协议是否已授权
    currentChannelId: null,   // 当前选中的频道 ID（多频道切换用，null 表示全部）
    baseUrl: null,           // 自动发现的后端 API 基础地址（含 /api/v1 前缀）
    channelsMeta: {},         // 频道元信息缓存（id → 归一化频道对象，含 channel_type 等）
    // 偏爱频道首次引导标志：登录成功且未引导过时置 true，由首页 onShow 弹窗引导
    // 为什么放 globalData 而非直接弹窗：onLaunch 期间页面尚未加载，弹窗会失效；
    // 改为标志位让首个可见页面（index）在 onShow 中触发，时机最稳
    needsPreferredOnboarding: false,
    // 偏爱频道变更时间戳：preferred-settings 保存后更新，今日/历史页 onShow 检测变化后刷新筛选
    preferredChannelsChanged: 0,
  },

  /**
   * 启动就绪 Promise：onLaunch 内完成后端发现、登录与预加载后 resolve
   *
   * 为什么需要这个：
   * 小程序框架不会 await App.onLaunch，页面 onLoad 可能在登录完成前执行，
   * 导致需鉴权的请求（如 /playlogs/recent）拿到空 token 触发 401。
   * 页面 onLoad 中 await getApp().readyPromise 可确保登录完成后才发请求。
   */
  readyPromise: null,

  async onLaunch() {
    this.readyPromise = (async () => {
      // 1. 后端地址自动发现：注入 globalData.baseUrl，后续 api.js getBaseUrl() 读取
      // 必须先完成：login 和 fetchTodayEpisode 都通过 request() 间接依赖 baseUrl，
      // 否则请求会走兜底 localhost 在真机上必然失败
      try {
        this.globalData.baseUrl = await discoverServer();
      } catch (err) {
        console.warn('[app] 后端地址发现失败，使用公网兜底:', err.message);
        // 异常时优先使用公网域名，避免后续请求打到 localhost 在真机上必然失败
        this.globalData.baseUrl = PROD_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';
      }

      // 2. 检查小程序更新（冷启动时，仅 release 模式生效）
      // 与 login/fetchTodayEpisode 无依赖，但因是同步注册回调，放在并行前执行不影响并行收益
      this.checkUpdate();

      // 3. login 与 fetchTodayEpisode 并行：
      // - login 通过 request() 调 /auth/login，依赖 baseUrl（已就绪），不依赖 todayEpisode
      // - fetchTodayEpisode 通过 request() 调 /episodes/today，仅依赖 baseUrl，不需 token
      // - 串行执行会浪费 1 个 RTT，并行后首屏可更快拿到今日节目供页面预渲染
      const loginTask = (async () => {
        try {
          const { token, user } = await login();
          this.globalData.token = token;
          this.globalData.userInfo = user;
          console.warn('登录成功');
          // 登录成功后检查是否需要首次偏爱频道引导
          // 放在这里而不是 onLaunch 末尾：未登录场景下 getOpenid() 返回空，
          // isPreferredChannelsOnboarded 仍能读取全局 ONBOARDED_KEY，但语义上希望引导绑定到登录态，
          // 避免未登录用户被引导后选了频道却因 openid 为空无法保存
          const localData = require('./services/local-data');
          if (!localData.isPreferredChannelsOnboarded()) {
            this.globalData.needsPreferredOnboarding = true;
          }
        } catch (err) {
          // 输出 baseUrl 辅助诊断：真机调试时最常见的失败原因是手机与电脑不在同一网段
          console.warn('登录未执行（可忽略，不影响播放）:', err.message, '| baseUrl:', this.globalData.baseUrl);
        }
      })();

      const preloadTask = (async () => {
        // 预加载今日节目元数据（不含稿件，首屏加速）
        // 结果存入 globalData.todayEpisode 供首页 onLoad 立即取用，避免等待 readyPromise
        try {
          this.globalData.todayEpisode = await fetchTodayEpisode();
          console.warn('预加载今日节目成功:', this.globalData.todayEpisode?.title);
        } catch (err) {
          // 输出 baseUrl 辅助诊断：真机调试时最常见的失败原因是手机与电脑不在同一网段
          console.warn('预加载今日节目失败:', err.message, '| baseUrl:', this.globalData.baseUrl);
        }
      })();

      // 等两者都完成（任一失败已被各自 catch 吞掉，不会让 Promise.all 抛错）
      await Promise.all([loginTask, preloadTask]);

      // 4. 初始化全局播放器（单例，所有页面共享）
      // 放在并行任务之后：player 初始化不依赖网络，但页面 onLoad 可能取 player，故仍需在 readyPromise 内
      this.globalData.player = initPlayer();

      // 5. 监听网络变化（弱网时进度上报降频）
      wx.onNetworkStatusChange((res) => {
        this.globalData.networkType = res.networkType;
      });

      // 6. 隐私授权检查：__usePrivacyCheck__ 开启后，调用涉及用户信息的 API 前需先同意
      this.checkPrivacy();
    })();
    return this.readyPromise;
  },

  /**
   * 订阅消息通知进入（FR-MC-06）
   * scene === 1014 表示从小程序订阅消息卡片点击进入。
   * 后端发送时已在模板 page 字段携带目标路径（课程主页 / 资讯频道），为主要跳转机制；
   * 此处为兜底路由：处理未带 page 或默认落到首页的场景，确保点击通知跳到正确频道。
   *
   * 后端可在通知 page query 中附带 ct（channel_type）以加速兜底判定；
   * 缺省时按缓存 / 频道列表判定类型。
   */
  onShow(options) {
    if (!options || options.scene !== 1014) return;
    const q = options.query || {};
    const channelId = q.channelId;
    if (!channelId) return;

    const routeToCourse = () => {
      const pages = getCurrentPages();
      const top = pages[pages.length - 1];
      // 已在目标课程页则跳过，避免重复跳转
      if (top && top.route === 'pages/course/course' && String((top.options || {}).channelId) === String(channelId)) {
        return;
      }
      wx.navigateTo({ url: '/pages/course/course?channelId=' + channelId });
    };
    const routeToNews = () => {
      this.globalData.currentChannelId = channelId;
      wx.switchTab({ url: '/pages/index/index' });
    };

    const t = q.ct; // 后端附带 channel_type 时优先使用
    if (t === 'course' || t === 'audiobook') {
      routeToCourse();
    } else if (t === 'news') {
      routeToNews();
    } else {
      // 类型未知：先查缓存，缓存无则拉取频道列表后判定（一次性兜底）
      const cached = channelType(channelId);
      if (cached && cached !== 'news') routeToCourse();
      else if (cached === 'news') routeToNews();
      else {
        const { fetchChannels } = require('./services/api');
        fetchChannels()
          .then(() => {
            const ct = channelType(channelId);
            if (ct && ct !== 'news') routeToCourse();
            else routeToNews();
          })
          .catch(() => routeToNews());
      }
    }
  },

  /**
   * 检查小程序版本更新
   * 仅 release 模式生效（开发版不需要弹窗提示）
   */
  checkUpdate() {
    if (typeof __wxConfig !== 'undefined' && __wxConfig.envVersion !== 'release') return;
    const updateManager = wx.getUpdateManager();
    updateManager.onCheckForUpdate((res) => {
      if (res.hasUpdate) console.warn('检测到新版本');
    });
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已就绪，是否重启应用？',
        confirmColor: '#FF6B8A',
        success: (res) => {
          if (res.confirm) updateManager.applyUpdate();
        },
      });
    });
    updateManager.onUpdateFailed(() => {
      wx.showToast({ title: '更新失败，请稍后重试', icon: 'none' });
    });
  },

  /**
   * 隐私授权检查
   * 2026 年起微信要求所有涉及用户信息的小程序必须接入隐私协议
   * 用户未同意前，调用 wx.setClipboardData/getUserProfile 等 API 会 fail（errCode:104）
   *
   * 关键：onNeedPrivacyAuthorization 必须同步注册，不能放在 getPrivacySetting 的
   * 异步回调里。否则在 getPrivacySetting 返回前，clipboard 调 requirePrivacyAuthorize
   * 会因无 handler 而直接 fail，导致复制功能不可用。
   */
  checkPrivacy() {
    // 1. 同步注册隐私授权弹窗 handler：无论 getPrivacySetting 结果如何都必须注册
    //    requirePrivacyAuthorize 触发时依赖此 handler 弹窗引导用户同意
    if (typeof wx.onNeedPrivacyAuthorization === 'function') {
      wx.onNeedPrivacyAuthorization((resolve) => {
        wx.showModal({
          title: '隐私保护提示',
          content: '为了向您提供更好的服务，我们需要您同意《用户协议》和《隐私政策》',
          confirmText: '同意',
          confirmColor: '#FF6B8A',
          cancelText: '拒绝',
          success: (modalRes) => {
            if (modalRes.confirm) {
              this.globalData.privacyAuthorized = true;
              resolve({ event: 'agree', buttonId: 'agree' });
            } else {
              resolve({ event: 'disagree' });
            }
          },
        });
      });
    }

    // 2. 查询当前隐私授权状态：已同意则标记 privacyAuthorized=true，
    //    跳过后续 requirePrivacyAuthorize 弹窗
    if (typeof wx.getPrivacySetting === 'undefined') {
      this.globalData.privacyAuthorized = true;
      return;
    }
    wx.getPrivacySetting({
      success: (res) => {
        if (!res.needAuthorization) {
          this.globalData.privacyAuthorized = true;
        }
      },
      fail: () => {
        this.globalData.privacyAuthorized = true;
      },
    });
  },
});
