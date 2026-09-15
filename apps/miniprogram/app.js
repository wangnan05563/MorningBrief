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
 * 0. 隐私授权检查（同步最先注册 onNeedPrivacyAuthorization，必须先于一切隐私 API）
 * 1. 版本信息注入
 * 2. 后端地址自动发现（discoverServer，注入 globalData.baseUrl）—— 必须先完成
 * 3. 检查小程序更新（冷启动时，与下面并行无依赖）
 * 4. 静默登录 + 预加载今日节目 并行执行
 *    - login 依赖 baseUrl（已由 discoverServer 注入），不依赖 todayEpisode
 *    - fetchTodayEpisode 仅依赖 baseUrl，不依赖 token（公开接口）
 *    - 两者并行可节省 1 个 RTT，首屏更快拿到节目数据
 * 5. 初始化全局播放器（BackgroundAudioManager 单例）
 * 6. 监听网络变化（弱网时进度上报降频）
 */
const { login } = require('./services/auth');
const { initPlayer } = require('./services/audio');
const { fetchTodayEpisode, channelType } = require('./services/api');
const { discoverServer, PROD_API_BASE_URL, getEnvVersion } = require('./utils/server-discovery');
// T00609：隐私授权协调器（官方 agreePrivacyAuthorization 按钮模式，见 utils/privacy.js）
const { createPrivacyCoordinator } = require('./utils/privacy');

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
    // 0. 隐私授权检查必须最先同步注册：onNeedPrivacyAuthorization 要在任何可能的
    //    隐私 API 调用（复制链接、getUserProfile 等）之前就绪，否则框架会弹微信
    //    官方默认隐私弹窗，与自定义弹窗混合导致重复弹窗。绝不能放在 readyPromise
    //    末尾（后端发现/登录可能耗时数秒，窗口期内点链接就会触发官方弹窗）。
    this.checkPrivacy();

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
   *
   * T00575：版本判定改用 `utils/server-discovery.getEnvVersion()`（官方
   * `wx.getAccountInfoSync().miniProgram.envVersion` 优先，`__wxConfig` 回退）。
   *
   * 原实现 `if (typeof __wxConfig !== 'undefined' && __wxConfig.envVersion !== 'release') return;`
   * 与 T00571 的弹窗根因同源——依赖未公开的 `__wxConfig.envVersion`，有两个坑：
   *   ① `__wxConfig` 存在但无 `envVersion` → `undefined !== 'release'` 成立 → 直接 return，
   *      **正式版的更新检查被静默跳过**，用户拿不到新版本提示；
   *   ② `__wxConfig` 整体缺失 → 反向放行，开发版/体验版也会注册更新管理器。
   *
   * 现口径：明确判定为非 release（develop / trial）才跳过；`release` 与「版本未知（''）」
   * 都注册更新管理器——取「宁可多查、不漏更新」侧，开发版下多一次检查无副作用。
   */
  checkUpdate() {
    const env = getEnvVersion();
    if (env && env !== 'release') return;
    const updateManager = wx.getUpdateManager();
    updateManager.onCheckForUpdate((res) => {
      if (res.hasUpdate) console.warn('检测到新版本');
    });
    updateManager.onUpdateReady(() => {
      wx.showModal({
        title: '更新提示',
        content: '新版本已就绪，是否重启应用？',
        confirmColor: '#3F6C8F',
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
   * 隐私授权检查（T00609 重构：官方 agreePrivacyAuthorization 按钮模式）
   * 2026 年起微信要求所有涉及用户信息的小程序必须接入隐私协议
   * 用户未同意前，调用 wx.setClipboardData/getUserProfile 等 API 会 fail（errCode:104）
   *
   * 关键 1：onNeedPrivacyAuthorization 必须同步注册，不能放在 getPrivacySetting 的
   * 异步回调里。否则在 getPrivacySetting 返回前，clipboard 调 requirePrivacyAuthorize
   * 会因无 handler 而直接 fail，导致复制功能不可用。
   *
   * 关键 2（T00609 实测更正）：**按钮触发的隐私接口（chooseAvatar 等）必须走官方按钮授权**——
   * 自定义弹窗里须放 `<button open-type="agreePrivacyAuthorization" id="agree-btn">`，
   * 并以 `resolve({event:'agree', buttonId:'agree-btn'})` 收尾。旧实现用 wx.showModal 的
   * 「同意」+ 不带 buttonId 的 resolve，框架判定授权未完成，报：
   *   chooseAvatar:fail privacy permission is not authorized or buttonId is wrong
   * 因此授权 UI 分两条路径（见 utils/privacy.js 协调器）：
   * - 组件路径（首选）：页面挂载 privacy-modal 组件（内含官方按钮），resolve 带 buttonId；
   * - 兜底路径：wx.showModal（无法承载官方按钮），resolve 不带 buttonId——
   *   仅对剪贴板等非按钮触发的隐私 API 可靠。
   *
   * 关键 3：防重入。并发多个隐私 API 调用会同时触发本 handler，
   * 只弹一次窗，用户选择后统一 resolve 所有挂起的调用，避免弹窗叠加。
   */
  checkPrivacy() {
    // 1. 协调器：管理挂起的 resolve 队列与扇出（纯逻辑，见 utils/privacy.js）
    this._privacy = createPrivacyCoordinator();
    // 隐私授权 UI 槽位：privacy-modal 组件 attached 时注册、detached 时注销
    this._privacyUI = null;
    // T00618：授权通过后要执行的动作队列（如 setClipboardData 需在手势链内执行）
    this._postPrivacyActions = [];

    // 2. 同步注册隐私授权弹窗 handler：无论 getPrivacySetting 结果如何都必须注册
    if (typeof wx.onNeedPrivacyAuthorization === 'function') {
      wx.onNeedPrivacyAuthorization((resolve) => {
        const st = this._privacy.needPrivacy(resolve);
        if (!st.shown) return; // 已有弹窗在展示：仅排队，不重复弹（防重入）
        const ui = this._privacyUI;
        if (ui && typeof ui.show === 'function') {
          // 组件路径（首选）：内含官方 agreePrivacyAuthorization 按钮
          ui.show();
          return;
        }
        // 兜底路径：wx.showModal（无官方按钮；chooseAvatar 等按钮类接口请挂载组件）
        wx.showModal({
          title: '隐私保护提示',
          content: '为了向您提供更好的服务，我们需要您同意《用户协议》和《隐私政策》',
          confirmText: '同意',
          confirmColor: '#3F6C8F',
          cancelText: '拒绝',
          success: (modalRes) => {
            if (modalRes.confirm) {
              this.globalData.privacyAuthorized = true;
              this._privacy.agreeFallback();
              // 兜底路径（wx.showModal 无官方按钮）：同样执行登记动作
              this._runPostPrivacyActions();
            } else {
              this._privacy.reject();
              this.clearPostPrivacyActions();
            }
          },
          fail: () => {
            // showModal 失败也要释放挂起的 resolve，否则隐私 API 永久挂起
            this._privacy.reject();
            this.clearPostPrivacyActions();
          },
        });
      });
    }

    // 3. 查询当前隐私授权状态：已同意则标记 privacyAuthorized=true，
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

  /**
   * 注册/注销隐私授权 UI（privacy-modal 组件在 attached/detached 时调用）。
   * 组件须提供 show() 方法，并在用户点同意/拒绝时回调 agreePrivacyViaButton / rejectPrivacy。
   */
  registerPrivacyUI(ui) {
    this._privacyUI = ui || null;
  },

  /**
   * 注册「隐私授权通过后要执行的动作」（T00618）
   *
   * 为什么需要：`wx.setClipboardData` 等隐私写操作**必须在用户手势的同步链内发起**——
   * 在 await/setTimeout 之后调用会被微信拒绝（表现为复制失败）。而授权弹窗是异步的，
   * 用户点「同意并继续」时其按钮回调本身处于手势链内，因此把动作登记到这里，
   * 由 agreePrivacyViaButton 在那一刻同步执行。
   *
   * @param {Function} fn 返回 Promise<boolean>/boolean 的动作
   * @returns {Promise<boolean>} 动作执行结果（用户拒绝授权时 resolve(false)）
   */
  registerPostPrivacyAction(fn) {
    if (!this._postPrivacyActions) this._postPrivacyActions = [];
    return new Promise((resolve) => {
      this._postPrivacyActions.push({ fn, resolve });
    });
  },

  /** 清空登记的动作（用户拒绝授权时），全部 resolve(false) */
  clearPostPrivacyActions() {
    const acts = (this._postPrivacyActions || []).splice(0);
    acts.forEach((a) => a.resolve(false));
  },

  /** 在授权同意的手势链内执行登记的动作（内部方法） */
  _runPostPrivacyActions() {
    const acts = (this._postPrivacyActions || []).splice(0);
    acts.forEach(({ fn, resolve }) => {
      let ret;
      try {
        ret = fn();
      } catch (e) {
        console.warn('[privacy] 授权后动作抛错:', e);
        ret = false;
      }
      Promise.resolve(ret).then((ok) => resolve(!!ok));
    });
  },

  /**
   * 组件路径：用户点击官方 agreePrivacyAuthorization 按钮。
   * buttonId 必须与弹窗内该按钮的 id 一致，框架才认可授权完成（T00609 报错根因）。
   */
  agreePrivacyViaButton(buttonId) {
    this.globalData.privacyAuthorized = true;
    this._privacy.agreeViaButton(buttonId);
    // 关键：立刻在手势链内执行登记动作（如 setClipboardData），不可延后
    this._runPostPrivacyActions();
  },

  /** 组件路径：用户点击「拒绝」 */
  rejectPrivacy() {
    this._privacy.reject();
    this.clearPostPrivacyActions();
  },
});
