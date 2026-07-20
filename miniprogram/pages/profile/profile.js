/**
 * 个人中心：用户信息 + 收听统计 + 功能入口
 *
 * V1.3：
 * - 接入 /users/stats 接口获取真实收听统计（累计时长/期数/完播数/收藏数）
 * - 新增"最近播放"、"我的收藏"、"我的频道"、"意见反馈"等功能入口
 * - 接入埋点（FR-SUP-10）
 */
const { logout, getUser, login } = require('../../services/auth');
const { fetchUserStats, updateUserProfile } = require('../../services/api');
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

    if (userInfo) {
      this.loadStats();
      // 头像/昵称为空时自动拉取一次：
      // 场景：从 onLaunch 静默登录进来（user 只有 openid），头像昵称是空，
      // 此时在 profile 页直接补全，避免用户必须先退出再点"登录"才能看到资料
      if (!userInfo.avatar || !userInfo.nickname) {
        this.silentEnrichProfile();
      }
    }
  },

  /**
   * 静默补全用户资料：调 wx.getUserProfile 拿头像昵称，调 updateUserProfile 写回后端
   * 这样后续评论、收藏等所有读 User 表的接口都能用上
   *
   * 区别于 onLogin：onLogin 强调"用户主动点击登录"的成功反馈；这里无反馈静默执行
   */
  async silentEnrichProfile() {
    try {
      const profile = await this.fetchWxProfile();
      if (!profile || (!profile.avatar && !profile.nickname)) return;
      // 调后端写回 User 表（评论、收藏等接口都依赖此）
      try {
        await updateUserProfile({
          nickname: profile.nickname || undefined,
          avatar: profile.avatar || undefined,
        });
      } catch (e) {
        // 写回失败不影响本地头像显示
        console.warn('updateUserProfile 失败:', e.message || e);
      }
      const app = getApp();
      const baseUser = app.globalData.userInfo || getUser() || {};
      const enriched = { ...baseUser, ...profile };
      app.globalData.userInfo = enriched;
      this.setData({ userInfo: enriched });
    } catch (err) {
      // 静默失败：拒绝授权/接口失败都不打扰用户
      console.log('silentEnrichProfile 失败:', err.message || err);
    }
  },

  /**
   * 打开"完善资料"弹窗：用户主动选择头像和昵称
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
   * 关闭"完善资料"弹窗（点击遮罩或取消按钮）
   */
  onCloseEditProfile() {
    this.setData({ showEditProfile: false });
  },

  /**
   * 用户在 chooseAvatar 选完头像后回调
   * 临时文件路径会随小程序销毁而失效，这里用 wx.saveFile 持久化到本地
   * （存到 wxfile:// 路径，跨冷启动不丢，比原临时路径生存周期更长）
   */
  onChooseAvatar(e) {
    const tempPath = (e && e.detail && e.detail.avatarUrl) || '';
    if (!tempPath) {
      wx.showToast({ title: '未选择头像', icon: 'none' });
      return;
    }
    // 先用临时路径即时显示，避免 saveFile 异步等待时 UI 空白
    this.setData({ editAvatar: tempPath });
    // 后台持久化（不阻塞 UI）
    const fm = wx.getFileSystemManager();
    const ext = (tempPath.match(/\.(\w+)$/) || [, 'jpg'])[1];
    const savePath = `${wx.env.USER_DATA_PATH}/avatar_${Date.now()}.${ext}`;
    fm.saveFile({
      tempFilePath: tempPath,
      filePath: savePath,
      success: () => {
        // 持久化成功：用持久化路径覆盖临时路径
        this.setData({ editAvatar: savePath });
      },
      fail: (err) => {
        // 持久化失败时保留临时路径，本会话内仍可用
        console.warn('saveFile 失败，使用临时路径:', err);
      },
    });
  },

  /**
   * 昵称输入（type=nickname 唤起微信昵称键盘）
   * 同时绑定 input + blur，确保用户从原生键盘选完昵称后能拿到值
   */
  onInputNickname(e) {
    const v = (e && e.detail && e.detail.value) || '';
    this.setData({ editNickname: v });
  },

  /**
   * 确认保存资料：调后端 updateUserProfile 写回 User 表
   * 写回后评论、收藏、统计等所有读 User 表的接口都能用上最新头像昵称
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
      await updateUserProfile({
        nickname: nickname || undefined,
        avatar: editAvatar || undefined,
      });
      const app = getApp();
      const baseUser = app.globalData.userInfo || getUser() || {};
      const enriched = {
        ...baseUser,
        avatar: editAvatar || baseUser.avatar || baseUser.avatar_url,
        avatar_url: editAvatar || baseUser.avatar_url,
        nickname: nickname || baseUser.nickname,
        nickName: nickname || baseUser.nickName,
      };
      app.globalData.userInfo = enriched;
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
   */
  async loadStats() {
    try {
      const stats = await fetchUserStats();
      if (!stats) {
        // 接口失败或未登录：兜底读 globalData
        const app = getApp();
        const localStats = app.globalData.listenStats || {};
        this.applyStats({
          total_listen_seconds: localStats.totalListenDuration || 0,
          total_listen_episodes: localStats.totalListenCount || 0,
          completed_episodes: 0,
          favorite_count: 0,
        });
        return;
      }
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
   * 未登录时引导登录：先静默登录拿 token，再拉取微信头像昵称完善资料
   *
   * 头像昵称获取走 wx.getUserProfile：
   * - 旧基础库用户手动点"允许"才返回头像昵称（一次性授权）
   * - 新版基础库（2.27+）已废弃 getUserProfile，改用头像昵称填写组件（button open-type="chooseAvatar"）
   *   但 V1.3 仍兼容老路径，调用失败时静默降级为后端默认头像
   */
  async onLogin() {
    wx.showLoading({ title: '登录中...' });
    try {
      // 1. 静默登录拿 token
      const { user } = await login();
      let enriched = user;
      // 2. 尝试拉取微信头像昵称（用户可能拒绝，拒绝时 user 已含默认值）
      try {
        const profile = await this.fetchWxProfile();
        if (profile) {
          enriched = { ...user, ...profile };
          // 调后端写回 User 表：保证评论/收藏/历史等所有读 User 表的接口能用上最新头像昵称
          try {
            await updateUserProfile({
              nickname: profile.nickname || undefined,
              avatar: profile.avatar || undefined,
            });
          } catch (e) {
            // 写回失败不影响本地显示
            console.warn('updateUserProfile 失败:', e.message || e);
          }
        }
      } catch (e) {
        // 用户拒绝授权：保留静默登录返回的 user（可能 avatar/nickname 为空）
      }
      const app = getApp();
      app.globalData.userInfo = enriched;
      this.setData({ userInfo: enriched });
      this.loadStats();
      trackEvent('profile', 'login_success');
    } catch (err) {
      console.error('登录失败:', err);
      wx.showToast({ title: '登录失败，请稍后重试', icon: 'none' });
    } finally {
      wx.hideLoading();
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
        desc: '用于完善个人资料',
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
        try {
          await logout();
        } catch (err) {
          // 接口失败也继续清理本地态，避免卡在失效 token
          console.error('退出登录失败:', err);
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
