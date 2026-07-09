/**
 * 用户状态管理：token、角色、登录/登出
 *
 * 持久化策略：token/username/role 存 localStorage（刷新不丢失）
 */
import { defineStore } from 'pinia'
import api from '../api'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('admin_token') || '',
    username: localStorage.getItem('admin_username') || '',
    role: localStorage.getItem('admin_role') || '',
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.role === 'admin',
  },

  actions: {
    async login(username, password) {
      const data = await api.post('/auth/login', { username, password })
      this.token = data.token
      this.username = data.username
      this.role = data.role
      localStorage.setItem('admin_token', data.token)
      localStorage.setItem('admin_username', data.username)
      localStorage.setItem('admin_role', data.role)
    },

    async logout() {
      try {
        await api.post('/auth/logout')
      } catch {
        // 登出失败也清除本地状态，避免卡在已失效的 token
      } finally {
        this.clearToken()
      }
    },

    clearToken() {
      this.token = ''
      this.username = ''
      this.role = ''
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_username')
      localStorage.removeItem('admin_role')
    },
  },
})
