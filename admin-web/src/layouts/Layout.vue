<template>
  <el-container class="layout">
    <!-- 左侧菜单：磨砂玻璃 + 薄荷青主题 -->
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar glass">
      <div class="logo">
        <span v-if="!collapsed" class="logo-text">20_News</span>
        <span v-else class="logo-mini">20</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :router="true"
        class="sidebar-menu"
      >
        <template v-for="route in menuRoutes" :key="route.path">
          <el-menu-item :index="'/' + route.path">
            <el-icon><component :is="route.meta.icon" /></el-icon>
            <template #title>{{ route.meta.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部导航：磨砂玻璃 -->
      <el-header class="header glass">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="collapsed = !collapsed">
            <Fold v-if="!collapsed" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" class="user-avatar">
                {{ username.charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="username">{{ username }}</span>
              <el-tag size="small" :type="role === 'admin' ? 'success' : 'info'">
                {{ role === 'admin' ? '管理员' : '运营' }}
              </el-tag>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const collapsed = ref(false)
const username = computed(() => userStore.username || '用户')
const role = computed(() => userStore.role)

// 从路由配置提取菜单项（过滤 hidden 的路由如详情页）
const menuRoutes = computed(() => {
  const mainRoute = router.options.routes.find((r) => r.path === '/')
  return mainRoute.children.filter((r) => !r.meta?.hidden)
})

const activeMenu = computed(() => {
  // 匹配当前路径的菜单项（详情页高亮所属列表页）
  const path = route.path
  if (path.startsWith('/review/')) return '/review'
  if (path.startsWith('/workflows/')) return '/workflows'
  return path
})

const currentTitle = computed(() => route.meta.title || '')

async function handleCommand(command) {
  if (command === 'logout') {
    await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
    await userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped lang="scss">
@use '../styles/variables.scss' as *;

.layout {
  height: 100vh;
}

.sidebar {
  transition: width 0.3s ease;
  border-right: 1px solid $color-border;
  overflow-x: hidden;

  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid $color-border;
  }

  .logo-text {
    font-size: 20px;
    font-weight: 700;
    color: $color-primary-dark;
    letter-spacing: 1px;
  }

  .logo-mini {
    font-size: 18px;
    font-weight: 700;
    color: $color-primary-dark;
  }
}

.sidebar-menu {
  border-right: none;
  background: transparent;

  :deep(.el-menu-item) {
    border-radius: $radius-sm;
    margin: 4px 8px;
    height: 44px;
    line-height: 44px;

    &.is-active {
      background: $color-primary-light;
      color: $color-primary-dark;
      font-weight: 600;
    }

    &:hover {
      background: rgba(181, 234, 215, 0.4);
    }
  }
}

.header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid $color-border;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .collapse-btn {
    font-size: 20px;
    cursor: pointer;
    color: $color-text-secondary;
    transition: color 0.2s;

    &:hover {
      color: $color-primary-dark;
    }
  }

  .page-title {
    font-size: 16px;
    font-weight: 600;
    color: $color-text-primary;
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  .user-avatar {
    background: $color-primary;
    color: white;
    font-weight: 600;
  }

  .username {
    font-size: 14px;
    color: $color-text-primary;
  }
}

.main-content {
  background: $color-bg;
  padding: 0;
  overflow-y: auto;
}
</style>
