<template>
  <div class="page-container about-page">
    <!-- 品牌卡：版本号 + 检查更新 -->
    <div class="card-soft brand-card">
      <div class="brand-row">
        <!-- Logo：薄荷青渐变 + 首字母 M -->
        <div class="brand-logo" aria-hidden="true">M</div>
        <div class="brand-info">
          <div class="version-row">
            <span class="version-label">版本：{{ info.version }}</span>
            <el-tooltip content="复制完整版本号" placement="top">
              <el-icon class="copy-btn" @click="copyVersion"><CopyDocument /></el-icon>
            </el-tooltip>
          </div>
          <div class="meta-row">
            <span>发布于 {{ info.build_date }}</span>
            <span v-if="showSha" class="git-sha">@{{ info.git_sha }}</span>
          </div>
        </div>
        <div class="update-btn-wrap">
          <!-- 五态按钮：idle / loading / latest / newer / error -->
          <el-button
            v-if="updateState.kind === 'idle'"
            type="primary"
            :icon="Refresh"
            @click="runCheckUpdate"
          >
            检查更新
          </el-button>
          <el-button v-else-if="updateState.kind === 'loading'" loading>检查中…</el-button>
          <el-button
            v-else-if="updateState.kind === 'latest'"
            type="success"
            :icon="CircleCheckFilled"
            plain
          >
            已是最新
          </el-button>
          <el-button
            v-else-if="updateState.kind === 'newer'"
            type="primary"
            :icon="Top"
            @click="openRelease"
          >
            有新版本 ({{ updateState.latest }})
          </el-button>
          <el-button
            v-else
            type="danger"
            :icon="WarningFilled"
            plain
            @click="runCheckUpdate"
          >
            {{ updateState.reason === 'network' ? '网络异常' : '服务异常' }} · 重试
          </el-button>
        </div>
      </div>
    </div>

    <!-- 系统元信息卡：Python 版本 + 平台 + 产品名 -->
    <div class="card-soft meta-card">
      <div class="meta-grid">
        <div class="meta-item">
          <span class="meta-label">产品</span>
          <span class="meta-value">{{ info.product }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Python</span>
          <span class="meta-value">{{ info.python }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">平台</span>
          <span class="meta-value">{{ info.platform }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Git SHA</span>
          <span class="meta-value mono">{{ info.git_sha }}</span>
        </div>
      </div>
    </div>

    <!-- 外部链接列表 -->
    <div class="card-soft menu-card">
      <div
        v-for="(item, idx) in menuItems"
        :key="item.key"
        class="menu-item"
        :class="{ 'no-border': idx === menuItems.length - 1 }"
        @click="handleMenuClick(item)"
      >
        <span class="menu-label">{{ item.label }}</span>
        <el-icon class="menu-arrow"><TopRight /></el-icon>
      </div>
    </div>

    <!-- 页脚 -->
    <div class="footer">
      <el-tooltip content="本工具仅供个人研究学习，详见 README 中的「风险免责」" placement="top">
        <span class="footer-text">© {{ year }} MorningBrief · 语音新闻播报平台</span>
      </el-tooltip>
    </div>

    <!-- 开源软件声明 Modal -->
    <el-dialog
      v-model="licensesOpen"
      title="开源软件声明"
      width="720px"
      destroy-on-close
    >
      <el-input
        v-model="licenseSearch"
        placeholder="搜索依赖名 / 许可证…"
        :prefix-icon="Search"
        clearable
        style="margin-bottom: 16px"
      />
      <div class="license-list">
        <div v-if="filteredLicenses.length === 0" class="license-empty">
          未找到匹配的依赖
        </div>
        <div v-for="dep in filteredLicenses" :key="dep.name" class="license-item">
          <a :href="dep.repo" target="_blank" rel="noopener noreferrer" class="license-name">
            {{ dep.name }}
            <span class="license-version">@{{ dep.version }}</span>
          </a>
          <el-tag size="small" type="info">{{ dep.license }}</el-tag>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer-tip">以运行时实际安装为准</span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from '../../utils/message'
import {
  Refresh, CopyDocument, CircleCheckFilled, Top, WarningFilled, TopRight, Search,
} from '@element-plus/icons-vue'
import { getAbout, checkUpdate } from '../../api/about'

const router = useRouter()

// API 失败时的兜底值，确保 UI 不白屏
const FALLBACK_INFO = {
  product: 'MorningBrief',
  version: '--',
  build_date: '--',
  git_sha: 'unknown',
  python: '--',
  platform: '--',
}

const info = ref({ ...FALLBACK_INFO })

// 检查更新状态机：idle → loading → (latest | newer | error)
// latest 3s 后自动回 idle，newer/error 为终态
const updateState = ref({ kind: 'idle' })
let latestTimer = null
let autoCheckTimer = null
let mountDelayTimer = null
let isChecking = false

// 开源声明 Modal
const licensesOpen = ref(false)
const licenseSearch = ref('')

const year = new Date().getFullYear()

// git_sha 为 unknown 时不显示，避免误导用户
const showSha = computed(
  () => info.value.git_sha && info.value.git_sha !== 'unknown'
)

// 8 个外部链接 + 2 个站内链接（开源声明触发 Modal、帮助文档走 SPA 路由）
const menuItems = [
  { key: 'terms', label: '用户协议', href: 'https://example.com/terms', external: true },
  { key: 'privacy', label: '隐私条款', href: 'https://example.com/privacy', external: true },
  { key: 'licenses', label: '开源软件声明', href: '#licenses', external: false },
  { key: 'help', label: '帮助文档', href: '/help', external: false },
  { key: 'api', label: 'API 文档', href: '/docs', external: true },
  { key: 'contact', label: '联系我们', href: 'mailto:dev@example.com', external: true },
  { key: 'community', label: '官方社区', href: 'https://example.com/community', external: true },
  { key: 'report', label: '报告问题', href: 'https://example.com/issues/new', external: true },
]

// 开源依赖清单：首版静态写入（P2 接入 license-checker 自动生成）
// 数据来源：admin-web/package.json + backend/requirements.txt
const licenses = [
  // 前端依赖
  { name: '@element-plus/icons-vue', version: '^2.3.0', license: 'MIT', repo: 'https://github.com/element-plus/element-plus-icons' },
  { name: 'axios', version: '^1.6.0', license: 'MIT', repo: 'https://github.com/axios/axios' },
  { name: 'chart.js', version: '^4.4.0', license: 'MIT', repo: 'https://github.com/chartjs/Chart.js' },
  { name: 'dayjs', version: '^1.11.0', license: 'MIT', repo: 'https://github.com/iamkun/dayjs' },
  { name: 'element-plus', version: '^2.14.2', license: 'MIT', repo: 'https://github.com/element-plus/element-plus' },
  { name: 'pinia', version: '^2.1.0', license: 'MIT', repo: 'https://github.com/vuejs/pinia' },
  { name: 'vue', version: '^3.4.0', license: 'MIT', repo: 'https://github.com/vuejs/core' },
  { name: 'vue-chartjs', version: '^5.3.0', license: 'MIT', repo: 'https://github.com/apertureless/vue-chartjs' },
  { name: 'vue-router', version: '^4.3.0', license: 'MIT', repo: 'https://github.com/vuejs/router' },
  // 前端 devDependencies
  { name: '@playwright/test', version: '^1.61.1', license: 'Apache-2.0', repo: 'https://github.com/microsoft/playwright' },
  { name: '@vitejs/plugin-vue', version: '^5.0.0', license: 'MIT', repo: 'https://github.com/vitejs/vite-plugin-vue' },
  { name: 'sass', version: '^1.72.0', license: 'MIT', repo: 'https://github.com/sass/dart-sass' },
  { name: 'unplugin-auto-import', version: '^0.17.0', license: 'MIT', repo: 'https://github.com/unplugin/unplugin-auto-import' },
  { name: 'unplugin-vue-components', version: '^0.26.0', license: 'MIT', repo: 'https://github.com/unplugin/unplugin-vue-components' },
  { name: 'vite', version: '^5.2.0', license: 'MIT', repo: 'https://github.com/vitejs/vite' },
  // 后端依赖
  { name: 'fastapi', version: '0.110.0', license: 'MIT', repo: 'https://github.com/tiangolo/fastapi' },
  { name: 'uvicorn', version: '0.27.0', license: 'BSD-3-Clause', repo: 'https://github.com/encode/uvicorn' },
  { name: 'sqlalchemy', version: '2.0.25', license: 'MIT', repo: 'https://github.com/sqlalchemy/sqlalchemy' },
  { name: 'aiosqlite', version: '0.19.0', license: 'MIT', repo: 'https://github.com/omnilib/aiosqlite' },
  { name: 'alembic', version: '1.13.1', license: 'MIT', repo: 'https://github.com/sqlalchemy/alembic' },
  { name: 'cachetools', version: '5.3.3', license: 'MIT', repo: 'https://github.com/tkem/cachetools' },
  { name: 'pyjwt', version: '2.8.0', license: 'MIT', repo: 'https://github.com/jpadilla/pyjwt' },
  { name: 'bcrypt', version: '4.1.2', license: 'Apache-2.0', repo: 'https://github.com/pyca/bcrypt' },
  { name: 'openai', version: '1.12.0', license: 'MIT', repo: 'https://github.com/openai/openai-python' },
  { name: 'tenacity', version: '8.2.3', license: 'Apache-2.0', repo: 'https://github.com/jd/tenacity' },
  { name: 'edge-tts', version: '6.1.10', license: 'MIT', repo: 'https://github.com/rany2/edge-tts' },
  { name: 'httpx', version: '0.27.0', license: 'BSD-3-Clause', repo: 'https://github.com/encode/httpx' },
  { name: 'feedparser', version: '6.0.11', license: 'BSD-2-Clause', repo: 'https://github.com/kurtmckee/feedparser' },
  { name: 'selectolax', version: '0.4.10', license: 'MIT', repo: 'https://github.com/rushter/selectolax' },
  { name: 'jieba', version: '0.42.1', license: 'MIT', repo: 'https://github.com/fxsjy/jieba' },
  { name: 'pyahocorasick', version: '2.3.1', license: 'BSD-3-Clause', repo: 'https://github.com/WojciechMula/pyahocorasick' },
  { name: 'cos-python-sdk-v5', version: '1.9.30', license: 'MIT', repo: 'https://github.com/tencentyun/cos-python-sdk-v5' },
  { name: 'pydantic-settings', version: '2.1.0', license: 'MIT', repo: 'https://github.com/pydantic/pydantic-settings' },
  { name: 'pyyaml', version: '6.0.1', license: 'MIT', repo: 'https://github.com/yaml/pyyaml' },
  { name: 'python-dotenv', version: '1.0.1', license: 'BSD-3-Clause', repo: 'https://github.com/theskumar/python-dotenv' },
  { name: 'apscheduler', version: '3.10.4', license: 'MIT', repo: 'https://github.com/agronholm/apscheduler' },
  { name: 'loguru', version: '0.7.2', license: 'MIT', repo: 'https://github.com/Delgan/loguru' },
  { name: 'colorama', version: '0.4.6', license: 'BSD-3-Clause', repo: 'https://github.com/tartley/colorama' },
  { name: 'pytest', version: '8.0.0', license: 'MIT', repo: 'https://github.com/pytest-dev/pytest' },
  { name: 'pytest-asyncio', version: '0.23.0', license: 'Apache-2.0', repo: 'https://github.com/pytest-dev/pytest-asyncio' },
].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))

// 按搜索关键词过滤依赖
const filteredLicenses = computed(() => {
  const kw = licenseSearch.value.trim().toLowerCase()
  if (!kw) return licenses
  return licenses.filter(
    (d) => d.name.toLowerCase().includes(kw) || d.license.toLowerCase().includes(kw)
  )
})

// 加载系统元信息；失败时 FALLBACK 兜底，不阻塞 UI
async function loadAbout() {
  try {
    const data = await getAbout()
    info.value = data
  } catch (e) {
    // 失败用 FALLBACK，不阻塞列表渲染
    console.error('加载系统元信息失败', e)
  }
}

// 内部检查实现：自动/手动共用，避免重复代码
async function performCheck() {
  if (isChecking) return // 已有检查在进行中，跳过
  isChecking = true
  updateState.value = { kind: 'loading' }
  try {
    const res = await checkUpdate()
    if (res.has_update) {
      updateState.value = {
        kind: 'newer',
        url: res.release_url,
        latest: res.latest,
        publishedAt: res.published_at,
      }
    } else {
      updateState.value = { kind: 'latest' }
      // 清理上一次未触发的定时器，避免堆叠多个 timer
      if (latestTimer) {
        clearTimeout(latestTimer)
        latestTimer = null
      }
      // 3s 后自动回 idle，让按钮恢复可点击的初始态
      // 仅当当前仍为 latest 时才回退，避免覆盖 newer/error 终态
      latestTimer = setTimeout(() => {
        latestTimer = null
        if (updateState.value.kind === 'latest') {
          updateState.value = { kind: 'idle' }
        }
      }, 3000)
    }
  } catch (e) {
    // axios 错误简易判定：网络中断通常无 response
    const isNetwork = !e?.response
    updateState.value = {
      kind: 'error',
      reason: isNetwork ? 'network' : 'server',
    }
  } finally {
    isChecking = false
  }
}

function runCheckUpdate() {
  performCheck()
}

function openRelease() {
  if (updateState.value.kind === 'newer') {
    window.open(updateState.value.url, '_blank', 'noopener,noreferrer')
  }
}

async function copyVersion() {
  try {
    await navigator.clipboard.writeText(info.value.version)
    ElMessage.success('已复制')
  } catch {
    // 剪贴板权限被拒时降级：仅 toast 提示
    ElMessage.warning('复制失败，请手动选择')
  }
}

function handleMenuClick(item) {
  if (item.key === 'licenses') {
    licensesOpen.value = true
    return
  }
  if (item.key === 'help') {
    // 帮助文档走 SPA 内链，避免整页刷新
    router.push('/help')
    return
  }
  // 外部链接新窗口打开；rel=noopener 防止 window.opener 劫持
  if (item.external) {
    window.open(item.href, '_blank', 'noopener,noreferrer')
  } else {
    router.push(item.href)
  }
}

onMounted(() => {
  loadAbout()
  // 5s 后发起首次自动检查，避免阻塞首屏渲染
  mountDelayTimer = setTimeout(() => {
    performCheck()
  }, 5000)
  // 启动 60 分钟定期检查：GitHub 未认证 API 限速 60/小时/IP，
  // 后端 5 分钟缓存兜底，60 分钟轮询刚好用满配额
  autoCheckTimer = setInterval(() => {
    performCheck()
  }, 60 * 60 * 1000)
})

onUnmounted(() => {
  // 卸载时清理所有 timer，避免内存泄漏与对已卸载组件调用 setState
  if (mountDelayTimer) {
    clearTimeout(mountDelayTimer)
    mountDelayTimer = null
  }
  if (autoCheckTimer) {
    clearInterval(autoCheckTimer)
    autoCheckTimer = null
  }
  if (latestTimer) {
    clearTimeout(latestTimer)
    latestTimer = null
  }
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.about-page {
  max-width: 800px;
  margin: 0 auto;
}

.brand-card {
  padding: 24px;
  margin-bottom: 16px;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.brand-logo {
  width: 56px;
  height: 56px;
  border-radius: $radius-md;
  background: linear-gradient(135deg, $color-primary, $color-primary-dark);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 26px;
  font-weight: 700;
  box-shadow: $shadow-sm;
  flex-shrink: 0;
}

.brand-info {
  flex: 1;
  min-width: 200px;
}

.version-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;

  .version-label {
    font-size: 18px;
    font-weight: 600;
    color: $color-text-primary;
  }

  .copy-btn {
    font-size: 14px;
    color: $color-text-secondary;
    cursor: pointer;
    transition: color 0.2s;

    &:hover {
      color: $color-primary-dark;
    }
  }
}

.meta-row {
  font-size: 13px;
  color: $color-text-secondary;

  .git-sha {
    margin-left: 8px;
    font-family: 'Consolas', 'Monaco', monospace;
  }
}

.update-btn-wrap {
  flex-shrink: 0;
}

.meta-card {
  padding: 16px 24px;
  margin-bottom: 16px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;

  .meta-label {
    font-size: 12px;
    color: $color-text-secondary;
  }

  .meta-value {
    font-size: 14px;
    color: $color-text-primary;
    font-weight: 500;

    &.mono {
      font-family: 'Consolas', 'Monaco', monospace;
    }
  }
}

.menu-card {
  padding: 0;
  overflow: hidden;
  margin-bottom: 32px;
}

.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  cursor: pointer;
  border-bottom: 1px solid $color-border;
  transition: background-color 120ms cubic-bezier(0.2, 0, 0, 1);

  &:hover {
    background: var(--color-primary-light);
  }

  &.no-border {
    border-bottom: none;
  }

  .menu-label {
    font-size: 14px;
    color: $color-text-primary;
  }

  .menu-arrow {
    font-size: 14px;
    color: $color-text-secondary;
  }
}

.footer {
  text-align: center;
  padding: 16px 0 32px;

  .footer-text {
    font-size: 12px;
    color: $color-text-secondary;
    cursor: help;
  }
}

.license-list {
  max-height: 60vh;
  overflow-y: auto;
}

.license-empty {
  text-align: center;
  padding: 32px;
  color: $color-text-secondary;
}

.license-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid $color-border;

  &:last-child {
    border-bottom: none;
  }

  .license-name {
    color: $color-text-primary;
    text-decoration: none;
    font-size: 13px;

    &:hover {
      color: $color-primary-dark;
    }

    .license-version {
      color: $color-text-secondary;
      margin-left: 4px;
    }
  }
}

.dialog-footer-tip {
  font-size: 12px;
  color: $color-text-secondary;
}

@media (max-width: 768px) {
  .about-page {
    padding: 16px;
  }

  .brand-card {
    padding: 16px;
  }

  .brand-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .update-btn-wrap {
    width: 100%;

    :deep(.el-button) {
      width: 100%;
    }
  }

  .menu-item {
    padding: 16px;
  }
}
</style>
