<template>
  <el-container class="layout">
    <!-- 左侧菜单：磨砂玻璃 + 薄荷青主题 -->
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar glass">
      <div class="logo">
        <!-- 展开时显示系统全称，收缩时显示系统 logo 图标（避免显示无意义的数字） -->
        <span v-if="!collapsed" class="logo-text">MorningBrief</span>
        <img v-else src="/favicon.svg" alt="logo" class="logo-img" />
      </div>
      <el-menu
        ref="menuRef"
        :default-active="activeMenu"
        :collapse="collapsed"
        :router="true"
        :unique-opened="true"
        class="sidebar-menu"
      >
        <template v-for="group in menuGroups" :key="group.name">
          <el-sub-menu :index="group.name">
            <template #title>
              <el-icon><component :is="group.icon" /></el-icon>
              <span>{{ group.name }}</span>
            </template>
            <el-menu-item
              v-for="item in group.items"
              :key="item.path"
              :index="'/' + item.path"
            >
              <el-icon><component :is="item.meta.icon" /></el-icon>
              <template #title>{{ item.meta.title }}</template>
            </el-menu-item>
          </el-sub-menu>
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
          <!-- 主题切换入口：调色板图标，全局可达 -->
          <el-tooltip content="主题设置" placement="bottom">
            <el-icon class="theme-btn" @click="openThemeSwitcher">
              <Brush />
            </el-icon>
          </el-tooltip>
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
  <!-- 主题切换对话框：通过 ref 暴露 open 方法 -->
  <ThemeSwitcher ref="themeSwitcherRef" />
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useThemeStore } from '../stores/theme'
import { ElMessageBox } from '../utils/message'
import ThemeSwitcher from '../components/ThemeSwitcher.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

// 主题切换器引用
const themeSwitcherRef = ref()

// 初始化主题：确保进入后台时已应用 localStorage 中的主题
onMounted(() => {
  themeStore.initTheme()
})

function openThemeSwitcher() {
  themeSwitcherRef.value?.open()
}

const collapsed = ref(false)
const username = computed(() => userStore.username || '用户')
const role = computed(() => userStore.role)

// 菜单 ref：用于路由变化时调用 open() 自动展开当前分组
const menuRef = ref()

// 菜单分组配置：顺序决定侧栏展示顺序，icon 为分组图标组件名
const groupConfig = [
  { name: '内容运营', icon: 'Document' },
  { name: '广告管理', icon: 'PictureFilled' },
  { name: '数据分析', icon: 'DataLine' },
  { name: 'AI 自动化', icon: 'Monitor' },
  { name: '系统配置', icon: 'Setting' },
  { name: '维护工具', icon: 'Tools' },
  { name: '帮助', icon: 'QuestionFilled' },
]

// 从路由配置提取菜单项并按 group 分组
// 同时根据用户角色过滤（requireRole=admin 的项仅管理员可见）
const menuGroups = computed(() => {
  const mainRoute = router.options.routes.find((r) => r.path === '/')
  const role = userStore.role
  const visible = mainRoute.children.filter((r) => {
    if (r.meta?.hidden) return false
    if (r.meta?.requireRole === 'admin' && role !== 'admin') return false
    return true
  })
  return groupConfig
    .map((g) => ({
      ...g,
      items: visible.filter((r) => r.meta?.group === g.name),
    }))
    .filter((g) => g.items.length > 0)
})

const activeMenu = computed(() => {
  // 匹配当前路径的菜单项（详情页高亮所属列表页）
  const path = route.path
  if (path.startsWith('/review/')) return '/review'
  if (path.startsWith('/workflows/')) return '/workflows'
  return path
})

// 当前激活菜单项所在的分组名（用于路由变化时自动展开）
const activeGroup = computed(() => {
  const active = activeMenu.value
  for (const g of menuGroups.value) {
    if (g.items.some((i) => '/' + i.path === active)) {
      return g.name
    }
  }
  return null
})

// 路由变化时自动展开当前分组（el-menu 的 default-openeds 仅初始化生效，需手动 open）
watch(activeGroup, (g) => {
  if (g && menuRef.value) menuRef.value.open(g)
})

onMounted(() => {
  if (activeGroup.value && menuRef.value) {
    menuRef.value.open(activeGroup.value)
  }
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

  // 收缩态 logo：复用 favicon.svg，尺寸适配 64px 侧栏
  .logo-img {
    width: 32px;
    height: 32px;
    border-radius: 8px;
  }
}

.sidebar-menu {
  border-right: none;
  background: transparent;

  // 分组标题：与菜单项一致的圆角和高度
  :deep(.el-sub-menu__title) {
    border-radius: $radius-sm;
    margin: 4px 8px;
    height: 44px;
    line-height: 44px;

    &:hover {
      background: var(--color-primary-light);
    }
  }

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
      background: var(--color-primary-light);
    }
  }

  // 折叠态：el-sub-menu 收缩为图标，popup 子菜单需保留圆角样式
  &.el-menu--collapse {
    :deep(.el-sub-menu__title) {
      margin: 4px auto;
      border-radius: $radius-sm;
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

  // 主题切换按钮：与 collapse-btn 风格统一
  .theme-btn {
    font-size: 20px;
    cursor: pointer;
    color: $color-text-secondary;
    transition: color 0.2s;
    margin-right: 16px;

    &:hover {
      color: $color-primary-dark;
    }
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
