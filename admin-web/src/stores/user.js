/**
 * 用户状态管理：角色、登录/登出
 *
 * 持久化策略（NFR-M103）：鉴权 token 仅存于后端下发的 HttpOnly Cookie（JS 不可读），
 * 前端仅保留非敏感的 username/role 于 localStorage（刷新不丢失、供路由守卫/展示）。
 */
import { defineStore } from 'pinia'
import api from '../api'

export const useUserStore = defineStore('user', {
  state: () => ({
    username: localStorage.getItem('admin_username') || '',
    role: localStorage.getItem('admin_role') || '',
  }),

  getters: {
    isLoggedIn: (state) => !!state.role,
    isAdmin: (state) => state.role === 'admin',
  },

  actions: {
    async login(username, password) {
      const data = await api.post('/auth/login', { username, password })
      // NFR-M103：token 由后端写入 HttpOnly Cookie，前端不持有；仅保留非敏感态
      this.username = data.username
      this.role = data.role
      localStorage.setItem('admin_username', data.username)
      localStorage.setItem('admin_role', data.role)
    },

    async logout() {
      try {
        // 后端清除 HttpOnly Cookie（Set-Cookie max-age=0）+ 写 JWT 黑名单
        await api.post('/auth/logout')
      } catch {
        // 登出失败也清除本地状态，避免卡在已失效的会话
      } finally {
        this.clearToken()
      }
    },

    clearToken() {
      this.username = ''
      this.role = ''
      localStorage.removeItem('admin_username')
      localStorage.removeItem('admin_role')
    },
  },
})
