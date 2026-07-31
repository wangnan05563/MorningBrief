/**
 * 个人中心：用户信息 + 收听统计 + 功能入口
 *
 * V1.3：
 * - 接入 /users/stats 接口获取真实收听统计（累计时长/期数/完播数/收藏数）
 * - 新增"最近播放"、"我的收藏"、"我的频道"、"意见反馈"等功能入口
 * - 接入埋点（FR-SUP-10）
 */
const { logout, getUser, login, getToken, setToken, isLoginCoolingDown } = require('../../services/auth');
const { fetchUserStats, updateUserProfile, uploadAvatar } = require('../../services/api');
const { trackPageView, trackEvent } = require('../../utils/tracker');

Page({
  data: {
    userInfo: null,
    totalListenDuration: 0,   // 累计收听秒数
    totalListenCount: 0,      // 累计收听期数
    completedCount: 0,        // 完播期数
    favoriteCount: 0,         // 收藏数
    durationLabel: '0分钟',   // 格式化后的收听时长
  },

  onShow() {
    trackPageView('pages/profile/profile');
    // 每次展示都刷新，确保登录态/统计为最新
    const app = getApp();
    const userInfo = app.globalData.userInfo || getUser();
    this.setData({ userInfo });

    // 总是调 loadStats：即使未登录也尝试请求，触发 refreshToken 自动恢复登录态
    // 为什么移除 if (userInfo) 检查：login 失败时 globalData.userInfo 为 null，
    // 旧逻辑会跳过 loadStats 导致统计永远显示 0；移除后 fetchUserStats 会触发 401→refreshToken
    this.loadStats();

    if (userInfo) {
      // 头像/昵称为空时自动拉取一次：
      // 场景：从 onLaunch 静默登录进来（user 只有 openid），头像昵称是空，
      // 此时在 profile 页直接补全，避免用户必须先退出再点"登录"才能看到资料
      // 为什么加 storage 节流：onShow 每次切 tab 都触发，用户点"以后再说"后下次再弹会骚扰
      // 用 openid 隔离标志位，用户拒绝后当次会话不再弹（与 maybeShowOnboarding 同款套路）
      if (!userInfo.avatar || !userInfo.nickname) {
        const skipKey = 'skipSilentEnrich_' + (userInfo.openid || '');
        if (!wx.getStorageSync(skipKey)) {
          this.silentEnrichProfile();
        }
      }
    }
  },

  /**
   * 静默补全用户资料：调 wx.getUserProfile 拿头像昵称，调 updateUserProfile 写回后端
   * 这样后续评论、收藏等所有读 User 表的接口都能用上
   *
   * 新基础库（2.27+）下 wx.getUserProfile 已废弃，会返回 null。
   * 此时不再静默吞掉，而是引导用户走"使用微信资料"弹窗（chooseAvatar + nickname），
   * 因为这是新版基础库下唯一能拿到真实头像昵称的方式。
   *
   * 区别于 onLogin：onLogin 是用户主动点击的强反馈；此处仅给一次温和提示，
   * 避免用户每次进入 profile 页都被打扰。提示后用户不操作则下次 onShow 再提示一次。
   */
  async silentEnrichProfile() {
    let profile = null;
    try {
      profile = await this.fetchWxProfile();
    } catch (err) {
      // 旧版 API 报错：profile 保持 null，走下方"使用微信资料"分支
      console.log('silentEnrichProfile fetchWxProfile 失败:', err.message || err);
    }
    if (profile && (profile.avatar || profile.nickname)) {
      // 旧基础库路径：getUserProfile 成功，写回后端 + 更新本地
      try {
        await updateUserProfile({
          nickname: profile.nickname || undefined,
          avatar: profile.avatar || undefined,
        });
      } catch (e) {
        console.warn('updateUserProfile 失败:', e.message || e);
      }
      const app = getApp();
      const baseUser = app.globalData.userInfo || getUser() || {};
      const enriched = { ...baseUser, ...profile };
      app.globalData.userInfo = enriched;
      // 同步 localStorage：与 onConfirmEditProfile 同理，避免重启后 login() 失败回退读旧缓存
      const tk = getToken();
      if (tk) setToken(tk, enriched);
      this.setData({ userInfo: enriched });
      return;
    }
    // 新基础库路径：getUserProfile 已废弃或被拒，提示用户去使用微信资料
    // 用 showModal 而非自动弹"使用微信资料"弹窗：避免 onShow 频繁自动弹出骚扰用户
    wx.showModal({
      title: '使用微信资料',
      content: '为了在评论、收藏等场景展示你的头像和昵称，建议使用微信资料。',
      confirmText: '使用微信资料',
      cancelText: '以后再说',
      confirmColor: '#5BA89B',
      success: (res) => {
        if (res.confirm) {
          // 用户同意：打开"使用微信资料"弹窗（复用 onTapEditProfile 的 UI）
          this.onTapEditProfile();
        } else {
          // 用户拒绝：写标志避免下次 onShow 再弹（与 onShow 中的节流逻辑配合）
          const u = this.data.userInfo || {};
          const skipKey = 'skipSilentEnrich_' + (u.openid || '');
          wx.setStorageSync(skipKey, Date.now());
        }
      },
    });
  },

  /**
   * 打开"使用微信资料"弹窗：用户主动选择微信头像和昵称
   * 解决微信 2.27+ 后 getUserProfile 不再返回真实头像的问题
   */
  onTapEditProfile() {
    const ui = this.data.userInfo || {};
    this.setData({
      showEditProfile: true,
      editAvatar: ui.avatar || ui.avatar_url || ui.avatarUrl || '',
      editNickname: ui.nickname || ui.nickName || '',
    });
  },

  /**
   * 关闭"使用微信资料"弹窗（点击遮罩或取消按钮）
   */
  onCloseEditProfile() {
    this.setData({ showEditProfile: false });
  },

  /**
   * 阻止事件冒泡（与详情页弹窗同款：catchtap 需要绑定一个 handler 才能稳定工作）
   * 为什么需要：catchtap="" 空字符串在部分真机上会被解析为无效 handler，
   * 导致点击弹窗内部时事件冒泡到遮罩层触发 onCloseEditProfile，弹窗误关闭
   */
  stopPropagation() {
    // 空方法，仅用于 catchtap 阻止冒泡
  },

  /**
   * 用户在 chooseAvatar 选完头像后回调
   * 返回的是微信临时文件路径（wxfile://tmp_xxx），小程序关闭后失效
   *
   * 临时路径仅用于本会话内 UI 预览，保存时由 onConfirmEditProfile 上传到后端
   * 持久化为 /avatars/{user_id}_{ts}.jpg，下次拉取 User.avatar 即可正常加载
   */
  onChooseAvatar(e) {
    const tempPath = (e && e.detail && e.detail.avatarUrl) || '';
    if (!tempPath) {
      wx.showToast({ title: '未选择头像', icon: 'none' });
      return;
    }
    // 仅用临时路径做 UI 预览，本会话内有效
    this.setData({ editAvatar: tempPath });
  },

  /**
   * 昵称输入（type=nickname 唤起微信昵称键盘上方的"使用微信昵称"按钮）
   * 为什么拆分 input 和 blur 两个 handler：
   * 旧代码 bindinput 和 bindblur 都绑 onInputNickname，
   * 部分机型上 blur 事件的 e.detail.value 是空字符串，会覆盖 input 拿到的最新值，
   * 导致用户点"使用微信昵称"后 editNickname 被清空
   */
  onInputNickname(e) {
    const v = (e && e.detail && e.detail.value) || '';
    this.setData({ editNickname: v });
  },

  /**
   * 昵称失焦：仅在 input 未拿到值时兜底
   * 不直接覆盖，避免 blur 空值清空 input 已拿到的最新值
   */
  onBlurNickname(e) {
    const v = (e && e.detail && e.detail.value) || '';
    if (v && (!this.data.editNickname || v.length > this.data.editNickname.length)) {
      this.setData({ editNickname: v });
    }
  },

  /**
   * 确认保存资料：头像先上传后端拿 URL，再调 updateUserProfile 写回 User 表
   *
   * 流程：
   * 1. editAvatar 是 wxfile:// 临时路径（chooseAvatar 返回）→ 先 uploadAvatar 上传后端拿持久 URL
   *    editAvatar 已是 http/https URL（旧基础库 getUserProfile 返回的微信 CDN URL）→ 直接用
   * 2. 拿到 avatar URL 后调 updateUserProfile 写回 User 表，评论/收藏/统计等所有读 User 表的接口都能用上
   */
  async onConfirmEditProfile() {
    const { editAvatar, editNickname } = this.data;
    const nickname = (editNickname || '').trim();
    if (!nickname && !editAvatar) {
      wx.showToast({ title: '请选择头像或输入昵称', icon: 'none' });
      return;
    }
    wx.showLoading({ title: '保存中...' });
    try {
      // 头像处理：临时路径需先上传后端，已是 URL（旧版 getUserProfile 返回的微信 CDN）则直接用
      // 为什么用 startsWith('http') 判断：chooseAvatar 返回的临时路径以 wxfile:// 开头，
      // 旧版 getUserProfile 返回的是 https://thirdqq.qlogo.cn/...，二者前缀差异可作为判定依据
      let avatarUrl = editAvatar;
      if (editAvatar && !/^https?:\/\//.test(editAvatar)) {
        try {
          avatarUrl = await uploadAvatar(editAvatar);
        } catch (err) {
          // 上传失败不让整个保存流程崩：仅 nickname 写回后端，头像仅更新本会话 globalData
          // 与旧版"头像不传后端"行为对齐，避免用户因网络抖动无法保存昵称
          console.warn('头像上传失败，仅保存昵称:', err.message || err);
          avatarUrl = null;
        }
      }

      // 昵称 + 头像 URL（上传成功时）写回后端持久化
      // avatarUrl 为 null 时不下发 avatar 字段，避免覆盖 User 表中已有的旧头像 URL
      const profileData = { nickname: nickname || undefined };
      if (avatarUrl) profileData.avatar = avatarUrl;
      await updateUserProfile(profileData);

      const app = getApp();
      const baseUser = app.globalData.userInfo || getUser() || {};
      const enriched = {
        ...baseUser,
        // 头像优先用上传后的 URL（持久化），上传失败时回退到临时路径（仅本会话有效）
        avatar: avatarUrl || editAvatar || baseUser.avatar || baseUser.avatar_url,
        avatar_url: avatarUrl || editAvatar || baseUser.avatar_url,
        nickname: nickname || baseUser.nickname,
        nickName: nickname || baseUser.nickName,
      };
      app.globalData.userInfo = enriched;
      // 同步 localStorage 缓存：globalData 在小程序重启后丢失，
      // 若不同步 news_user，重启时若 login() 失败（网络/invalid code）会回退读 getUser() 拿到旧空资料，
      // 导致"保存了头像昵称但下次进来又没了"
      const tk = getToken();
      if (tk) setToken(tk, enriched);
      this.setData({ userInfo: enriched, showEditProfile: false });
      wx.showToast({ title: '保存成功', icon: 'success' });
      trackEvent('profile', 'edit_profile_success');
    } catch (err) {
      console.error('保存资料失败:', err);
      wx.showToast({ title: err.message || '保存失败', icon: 'none' });
    } finally {
      wx.hideLoading();
    }
  },

  /**
   * 从后端加载用户统计
   * 接口失败时回退到 globalData 兜底，避免页面空白
   *
   * 缓存策略：成功时写入 globalData.listenStats，失败时用缓存值兜底
   * 为什么：之前 listenStats 从未赋值，失败时兜底永远是 0；
   * 缓存后弱网/token 失效场景下能显示上次成功获取的数据，而非 0
   */
  async loadStats() {
    try {
      const stats = await fetchUserStats();
      if (!stats) {
        // 接口失败或未登录：兜底读 globalData 缓存
        const app = getApp();
        const localStats = app.globalData.listenStats || {};
        this.applyStats({
          total_listen_seconds: localStats.total_listen_seconds || 0,
          total_listen_episodes: localStats.total_listen_episodes || 0,
          completed_episodes: localStats.completed_episodes || 0,
          favorite_count: localStats.favorite_count || 0,
        });
        return;
      }
      // 成功时缓存到 globalData，下次失败时用此值兜底
      getApp().globalData.listenStats = stats;
      this.applyStats(stats);
    } catch (err) {
      console.error('加载用户统计失败:', err);
    }
  },

  applyStats(stats) {
    const totalListenDuration = stats.total_listen_seconds || 0;
    const totalListenCount = stats.total_listen_episodes || 0;
    const completedCount = stats.completed_episodes || 0;
    const favoriteCount = stats.favorite_count || 0;
    this.setData({
      totalListenDuration,
      totalListenCount,
      completedCount,
      favoriteCount,
      durationLabel: this.formatDuration(totalListenDuration),
    });
  },

  /**
   * 未登录时引导登录：先静默登录拿 token，再拉取微信头像昵称
   *
   * 头像昵称获取策略（按基础库版本自适应）：
   * - 旧基础库（<2.27）：wx.getUserProfile 弹窗授权，用户点"允许"返回头像昵称
   * - 新基础库（>=2.27）：wx.getUserProfile 已废弃，返回 null；
   *   此时自动弹出"使用微信资料"弹窗，引导用户通过 chooseAvatar + nickname 选择微信头像和昵称
   *
   * 新版方案优势：用户主动选择，不受基础库限制，且资料会写回后端 User 表，
   * 评论/收藏等所有读 User 表的接口都能用上。
   */
  async onLogin() {
    // 冷却期内直接提示，避免触发无效 wx.login 浪费 code
    if (isLoginCoolingDown()) {
      wx.showToast({ title: '登录冷却中，请 30 秒后重试', icon: 'none', duration: 2000 });
      return;
    }
    wx.showLoading({ title: '登录中...' });
    try {
      // 优先复用已有 token：避免短时间内重复 wx.login 拿到相同 code 导致 invalid code
      // app.js onLaunch 已自动登录，多数情况下 token 已就绪，点击登录只需拉取头像昵称
      let user = getUser();
      if (!getToken()) {
        // 无 token 才真正调用 wx.login 换 token
        const result = await login();
        user = result.user;
      }
      let enriched = user;
      // 尝试旧版 wx.getUserProfile 拉取头像昵称（旧基础库可用）
      let profileFromGetUserProfile = null;
      try {
        profileFromGetUserProfile = await this.fetchWxProfile();
      } catch (e) {
        // 旧版 API 报错或用户拒绝：profileFromGetUserProfile 保持 null
      }
      if (profileFromGetUserProfile) {
        // 旧基础库路径：getUserProfile 成功，直接用其返回值
        enriched = { ...user, ...profileFromGetUserProfile };
        try {
          await updateUserProfile({
            nickname: profileFromGetUserProfile.nickname || undefined,
            avatar: profileFromGetUserProfile.avatar || undefined,
          });
        } catch (e) {
          console.warn('updateUserProfile 失败:', e.message || e);
        }
        const app = getApp();
        app.globalData.userInfo = enriched;
        // 同步 localStorage：onLogin 可能复用已有 token（未走 login()），需手动同步缓存
        const tk = getToken();
        if (tk) setToken(tk, enriched);
        this.setData({ userInfo: enriched });
        this.loadStats();
        trackEvent('profile', 'login_success');
      } else {
        // 新基础库路径：getUserProfile 已废弃/被拒绝/返回空，
        // 自动弹出"使用微信资料"弹窗引导用户选择微信头像昵称
        const app = getApp();
        app.globalData.userInfo = enriched;
        this.setData({
          userInfo: enriched,
          // 自动展开"使用微信资料"弹窗：用户选择微信头像昵称后完成登录闭环
          showEditProfile: true,
          editAvatar: '',
          editNickname: '',
        });
        trackEvent('profile', 'login_need_profile');
      }
    } catch (err) {
      console.error('登录失败:', err);
      // 先 hideLoading 再 showToast：showToast 会自动关闭 showLoading，
      // 但显式 hideLoading 可避免"showLoading 与 hideLoading 必须配对使用"警告
      wx.hideLoading();
      // invalid code 是微信 API 返回的错误，提示用户稍后重试
      const msg = err.message && err.message.includes('invalid code')
        ? '登录已过期，请 30 秒后重试'
        : '登录失败，请稍后重试';
      wx.showToast({ title: msg, icon: 'none' });
      return;
    }
    // 成功路径：hideLoading 在最后，避免与下方可能的 showToast 冲突
    wx.hideLoading();
    // 弹窗路径下给出引导提示，避免用户困惑为何没"登录成功"toast
    if (this.data.showEditProfile) {
      wx.showToast({ title: '请选择微信头像和昵称', icon: 'none', duration: 2000 });
    }
  },

  /**
   * 拉取微信用户信息（头像/昵称）。
   * 使用 Promise 包装 wx.getUserProfile，便于 async/await 链式调用。
   * 用户拒绝或 API 不存在时返回 null（不阻断主流程）。
   */
  fetchWxProfile() {
    return new Promise((resolve) => {
      if (typeof wx.getUserProfile !== 'function') {
        resolve(null);
        return;
      }
      wx.getUserProfile({
        desc: '用于展示你的微信头像和昵称',
        success: (res) => {
          const u = res.userInfo || {};
          resolve({
            avatar: u.avatarUrl,
            nickname: u.nickName,
            gender: u.gender,
            country: u.country,
            province: u.province,
            city: u.city,
          });
        },
        fail: () => resolve(null),
      });
    });
  },

  /**
   * 秒 → "X小时Y分钟"，用于收听时长展示
   */
  formatDuration(sec) {
    if (!sec || sec < 0 || Number.isNaN(sec)) return '0分钟';
    const m = Math.floor(sec / 60);
    if (m < 60) return `${m}分钟`;
    const h = Math.floor(m / 60);
    const rest = m % 60;
    return rest ? `${h}小时${rest}分钟` : `${h}小时`;
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      confirmColor: '#FF6B8A',
      success: async (res) => {
        if (!res.confirm) return;
        // 在 logout 清除 news_user 前先取 openid，用于清理该用户的本地数据
        // 否则 logout 后 getOpenid() 返回空字符串，无法定位要清理的 key
        const localData = require('../../services/local-data');
        const user = getUser();
        const openid = (user && user.openid) || '';
        try {
          await logout();
        } catch (err) {
          // 接口失败也继续清理本地态，避免卡在失效 token
          console.error('退出登录失败:', err);
        }
        // 清理当前用户的本地数据（进度/收藏/历史），避免下一个登录账号看到上一个账号的数据
        if (openid) {
          localData.clearByOpenid(openid);
        }
        const app = getApp();
        app.globalData.userInfo = null;
        app.globalData.token = null;
        trackEvent('profile', 'logout');
        // reLaunch 清空页面栈后回到首页 tab
        wx.reLaunch({ url: '/pages/index/index' });
      },
    });
  },

  /**
   * 点击列表项跳转
   * 各功能页统一通过 navigateTo 进入（非 tab 页）
   * 失败时降级为 reLaunch：避免页面栈满 10 层或 navigateTo 静默失败导致"无反应"
   */
  onTapSetting(e) {
    const key = e.currentTarget.dataset.key;
    if (key === 'logout') {
      this.onLogout();
      return;
    }
    trackEvent('profile', 'tap_menu', key);

    const routeMap = {
      favorites: '/pages/favorites/favorites',
      recent: '/pages/recent/recent',
      channels: '/pages/channels/channels',
      preferred: '/pages/preferred-settings/preferred-settings',
      feedback: '/pages/feedback/feedback',
      settings: '/pages/settings/settings',
      about: '/pages/about/about',
      agreement: '/pages/agreement/agreement',
      privacy: '/pages/privacy/privacy',
    };
    const url = routeMap[key];
    if (!url) return;

    // navigateTo 失败（页面栈满/页面未注册等）时降级为 reLaunch，确保用户能进入目标页
    wx.navigateTo({
      url,
      fail: (err) => {
        console.warn('navigateTo 失败，降级为 reLaunch:', err);
        wx.reLaunch({ url });
      },
    });
  },
});
