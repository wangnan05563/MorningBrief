<template>
  <div data-guide="about-page" class="page-container about-page">
    <!-- 品牌卡：版本号 + 检查更新 -->
    <div data-guide="about-brand" class="card-soft brand-card">
      <div class="brand-row">
        <!-- Logo：薄荷青渐变 + 首字母 M -->
        <div class="brand-logo" aria-hidden="true">M</div>
        <div class="brand-info">
          <div class="version-row">
            <span class="version-label">版本：{{ info.version }}</span>
            <IconButton :icon="CopyDocument" label="复制版本号" desc="复制完整版本号到剪贴板" @click="copyVersion" />
          </div>
          <div class="meta-row">
            <span>发布于 {{ info.build_date }}</span>
            <span v-if="showSha" class="git-sha">@{{ info.git_sha }}</span>
          </div>
        </div>
        <div class="update-btn-wrap">
          <!-- 一键升级进度（T00879）：下载中展示进度条，终态提示重启/错误重试 -->
          <div v-if="upgradeState.active" class="upgrade-panel">
            <div v-if="upgradeState.state === 'error'" class="upgrade-error-row">
              <IconButton type="danger" plain :icon="Refresh" label="升级失败，重试" desc="重新执行一键升级" @click="runUpgrade" />
              <span class="upgrade-msg">{{ upgradeState.error }}</span>
            </div>
            <template v-else>
              <div class="upgrade-line">
                <el-icon class="is-loading upgrade-spin"><Loading /></el-icon>
                <span class="upgrade-msg">{{ upgradeState.message }}</span>
              </div>
              <el-progress
                v-if="upgradeState.state === 'downloading' && upgradeState.percent >= 0"
                :percentage="upgradeState.percent"
                :stroke-width="6"
                class="upgrade-progress"
              />
            </template>
          </div>

          <!-- 六态按钮：idle / loading / latest / newer / unavailable / error -->
          <template v-else>
            <IconButton
              v-if="updateState.kind === 'idle'"
              type="primary"
              :icon="Refresh"
              label="检查更新"
              desc="检查 GitHub 是否有新版本"
              @click="runCheckUpdate"
            />
            <IconButton
              v-else-if="updateState.kind === 'loading'"
              loading
              :icon="Refresh"
              label="检查中…"
              desc="正在检查 GitHub 新版本"
            />
            <IconButton
              v-else-if="updateState.kind === 'latest'"
              type="success"
              :icon="CircleCheckFilled"
              plain
              label="已是最新"
              desc="当前已是最新版本"
            />
            <div v-else-if="updateState.kind === 'newer'" class="newer-btns">
              <IconButton type="primary" :icon="Download" :label="`立即更新 (${updateState.latest})`" desc="下载并安装新版本" @click="runUpgrade" />
              <IconButton plain :icon="Top" label="查看详情" desc="打开版本发布页" @click="openRelease" />
            </div>
            <!-- 检查未完成：显示原因并提供重试，不得伪装成「已是最新」（M94） -->
            <div v-else-if="updateState.kind === 'unavailable'" class="unavailable-row">
              <IconButton
                type="warning"
                plain
                :icon="Refresh"
                label="无法确认，点击重试"
                desc="更新检查未完成，点击重新检查"
                @click="runCheckUpdate"
              />
              <span class="update-hint">{{ updateState.error }}</span>
            </div>
            <IconButton
              v-else
              type="danger"
              plain
              :icon="Refresh"
              :label="updateState.reason === 'network' ? '网络异常，点击重试' : '服务异常，点击重试'"
              desc="重新检查更新"
              @click="runCheckUpdate"
            />
          </template>
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
      <el-tooltip content="本工具仅供个人研究学习，详见 README 中的「风险免责」" placement="top" :fallback-placements="['bottom', 'left', 'right']">
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
import { dangerConfirm } from '../../utils/dangerConfirm'
import {
  Refresh, CopyDocument, CircleCheckFilled, Top, TopRight, Search, Download, Loading,
} from '@element-plus/icons-vue'
import { getAbout, checkUpdate, startUpgrade, getUpgradeStatus } from '../../api/about'
import { API_DOCS_PATH, buildRepoLinks } from '../../utils/links'

const router = useRouter()

// API 失败时的兜底值，确保 UI 不白屏
// repo_url 为空意味着「后端未配置代码仓库」，此时项目类外链入口整体隐藏
const FALLBACK_INFO = {
  product: 'MorningBrief',
  version: '--',
  build_date: '--',
  git_sha: 'unknown',
  python: '--',
  platform: '--',
  repo_url: '',
  docs_enabled: false,
}

const info = ref({ ...FALLBACK_INFO })

// 检查更新状态机：idle → loading → (latest | newer | unavailable | error)
// latest 3s 后自动回 idle；newer/unavailable/error 为终态（unavailable=没能确认，不是没更新）
const updateState = ref({ kind: 'idle' })
let latestTimer = null
let autoCheckTimer = null
let mountDelayTimer = null
let isChecking = false

// 一键升级状态（T00879）：active 时进入升级进度面板；终态含 restarting/dev_staged/error
const upgradeState = ref({ active: false, state: 'idle', percent: -1, message: '', error: '' })
let pollTimer = null

// 开源声明 Modal
const licensesOpen = ref(false)
const licenseSearch = ref('')

const year = new Date().getFullYear()

// git_sha 为 unknown 时不显示，避免误导用户
const showSha = computed(
  () => info.value.git_sha && info.value.git_sha !== 'unknown'
)

// 链接清单：2 个站内入口（开源声明 Modal、帮助文档 SPA 路由）+ 后端下发的仓库派生外链
// + 仅在开放了交互式文档时才出现的 API 文档。
// 曾经这里有 5 条 example.com 占位外链（用户协议/隐私条款/官方社区/报告问题/联系我们），
// 它们不是「以后会填」而是没人填过——占位地址会原样出厂并被当成官方入口，
// 故直接移除而非改名（FR-UX-404 / M101）。真实协议文本若需要，属产品决策，另单跟踪。
const menuItems = computed(() => {
  const items = [
    { key: 'help', label: '帮助文档', href: '/help', external: false },
    { key: 'licenses', label: '开源软件声明', href: '#licenses', external: false },
    ...buildRepoLinks(info.value.repo_url),
  ]
  if (info.value.docs_enabled) {
    items.push({ key: 'api', label: 'API 文档', href: API_DOCS_PATH, external: true })
  }
  return items
})

// 开源依赖清单：首版静态写入（P2 接入 license-checker 自动生成）
// 数据来源：admin-web/package.json + backend/requirements.txt
// 版本号是抄来的，抄来的东西会过期——所以构建期由 scripts/validate-nav.mjs
// 把这张表与两份清单逐条比对（缺失/多余/版本不符都让构建失败），改依赖时不必再记得改这里。
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
  { name: 'edge-tts', version: '7.2.8', license: 'MIT', repo: 'https://github.com/rany2/edge-tts' },
  { name: 'httpx', version: '0.27.0', license: 'BSD-3-Clause', repo: 'https://github.com/encode/httpx' },
  { name: 'feedparser', version: '6.0.11', license: 'BSD-2-Clause', repo: 'https://github.com/kurtmckee/feedparser' },
  { name: 'selectolax', version: '0.4.10', license: 'MIT', repo: 'https://github.com/rushter/selectolax' },
  { name: 'jieba', version: '0.42.1', license: 'MIT', repo: 'https://github.com/fxsjy/jieba' },
  { name: 'pyahocorasick', version: '2.3.1', license: 'BSD-3-Clause', repo: 'https://github.com/WojciechMula/pyahocorasick' },
  { name: 'cos-python-sdk-v5', version: '1.9.30', license: 'MIT', repo: 'https://github.com/tencentyun/cos-python-sdk-v5' },
  { name: 'pydantic-settings', version: '2.1.0', license: 'MIT', repo: 'https://github.com/pydantic/pydantic-settings' },
  { name: 'pyyaml', version: '6.0.1', license: 'MIT', repo: 'https://github.com/yaml/pyyaml' },
  { name: 'python-dotenv', version: '1.0.1', license: 'BSD-3-Clause', repo: 'https://github.com/theskumar/python-dotenv' },
  { name: 'python-multipart', version: '0.0.9', license: 'Apache-2.0', repo: 'https://github.com/Kludex/python-multipart' },
  { name: 'slowapi', version: '0.1.9', license: 'MIT', repo: 'https://github.com/laurents/slowapi' },
  { name: 'PyMuPDF', version: '1.28.2', license: 'AGPL-3.0', repo: 'https://github.com/pymupdf/PyMuPDF' },
  { name: 'apscheduler', version: '3.10.4', license: 'MIT', repo: 'https://github.com/agronholm/apscheduler' },
  { name: 'loguru', version: '0.7.2', license: 'MIT', repo: 'https://github.com/Delgan/loguru' },
  { name: 'colorama', version: '0.4.6', license: 'BSD-3-Clause', repo: 'https://github.com/tartley/colorama' },
  { name: 'pytest', version: '8.4.2', license: 'MIT', repo: 'https://github.com/pytest-dev/pytest' },
  { name: 'pytest-asyncio', version: '0.24.0', license: 'Apache-2.0', repo: 'https://github.com/pytest-dev/pytest-asyncio' },
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

// 将 GitHub 的 ISO 时间（如 2026-07-20T00:00:00Z）转为 YYYY-MM-DD（UTC+8）
// 检查更新拿到真实发布时间时，用于把「发布于」显示为 release 实际发布日，
// 而非过期的打包 build_date 硬编码值。
function _formatPublishedAt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  // 转 UTC+8 后取日期部分，与后端 _CST 时区保持一致
  const cst = new Date(d.getTime() + 8 * 60 * 60 * 1000)
  const y = cst.getUTCFullYear()
  const m = String(cst.getUTCMonth() + 1).padStart(2, '0')
  const day = String(cst.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// 内部检查实现：自动/手动共用，避免重复代码
async function performCheck() {
  if (isChecking) return // 已有检查在进行中，跳过
  isChecking = true
  updateState.value = { kind: 'loading' }
  try {
    const res = await checkUpdate()
    if (res.source !== 'remote') {
      // 后端没能确认远端版本（未配置仓库 / 仓库无 release / GitHub 限速 / 网络失败）。
      // 「没能确认」不等于「已是最新」——原先一律显示绿色「已是最新」，
      // 用户据此以为版本没问题（M94 的谎报形态）。改为独立终态 + 后端给的原文案。
      updateState.value = {
        kind: 'unavailable',
        error: res.error || '暂时无法确认是否有新版本',
        url: res.release_url,
      }
      return
    }
    if (res.has_update) {
      updateState.value = {
        kind: 'newer',
        url: res.release_url,
        latest: res.latest,
        publishedAt: res.published_at,
      }
      return
    }
    if (res.published_at) {
      // 已是最新但拿到了远端发布时间：把「发布于」替换为本次 release 的真实发布时间，
      // 而非过期的打包 build_date 硬编码值
      info.value = { ...info.value, build_date: _formatPublishedAt(res.published_at) }
    }
    _showLatest()
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

// 「已是最新」是 3 秒的瞬时反馈，随后自动回 idle 让按钮恢复可点击初始态。
// 定时器先清后设：反复检查会堆叠多个 timer，后到的定时器会把新状态又打回 idle。
function _showLatest() {
  updateState.value = { kind: 'latest' }
  if (latestTimer) {
    clearTimeout(latestTimer)
    latestTimer = null
  }
  latestTimer = setTimeout(() => {
    latestTimer = null
    if (updateState.value.kind === 'latest') {
      updateState.value = { kind: 'idle' }
    }
  }, 3000)
}

function runCheckUpdate() {
  performCheck()
}

function openRelease() {
  if (updateState.value.kind === 'newer') {
    window.open(updateState.value.url, '_blank', 'noopener,noreferrer')
  }
}

// 触发一键升级：先调起后端下载，再轮询进度直至进入终态
// 为什么轮询：后端下载整包耗时可达分钟级，POST 同步等待会占用 axios 连接，
// 改为立即返回 + 轮询 /about/upgrade/status，前端持续刷新进度条
async function runUpgrade() {
  // 一键升级会替换程序并重启服务，进行中的工作流/审核会中断（M95）
  const st = updateState.value
  const ok = await dangerConfirm({
    action: '立即更新',
    target: `当前版本 ${info.value?.version || '未知'} → ${st.latest || '最新版本'}`,
    scope: st.publishedAt ? `发布时间 ${st.publishedAt}` : '发布时间未知',
    lines: [
      '桌面端将在下载完成后自动替换文件并重启服务；',
      '重启会中断进行中的工作流与审核任务，请先确认队列为空；',
      st.url ? `更新包来源：<a href="${st.url}" target="_blank" rel="noopener noreferrer">Release 页面</a>` : '',
    ],
    irreversible: '升级后不支持在管理端内回滚，如需回退要手动重装旧版本。',
    confirmWord: 'UPDATE',
    confirmLabel: '开始更新',
  })
  if (!ok) return
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  upgradeState.value = {
    active: true,
    state: 'downloading',
    percent: -1,
    message: '正在准备更新包…',
    error: '',
  }
  try {
    await startUpgrade()
  } catch (e) {
    // 启动失败（如未配置仓库/无更新包）给出可读提示与重试入口
    upgradeState.value = {
      active: true,
      state: 'error',
      percent: -1,
      message: '启动升级失败',
      error: e?.message || '请稍后重试',
    }
    return
  }
  pollUpgradeStatus()
}

async function pollUpgradeStatus() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  try {
    const s = await getUpgradeStatus()
    upgradeState.value = {
      active: true,
      state: s.state,
      percent: s.percent,
      message: s.message || '',
      error: s.error || '',
    }
    // restarting/dev_staged/error 为终态，无需继续轮询
    const terminal = ['restarting', 'dev_staged', 'error']
    if (!terminal.includes(s.state)) {
      pollTimer = setTimeout(pollUpgradeStatus, 2000)
    }
  } catch (e) {
    // 轮询瞬时失败不中断升级，短暂后重试即可
    upgradeState.value = { ...upgradeState.value, state: 'downloading' }
    pollTimer = setTimeout(pollUpgradeStatus, 2000)
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
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
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

  .update-sub {
    margin-left: 6px;
    font-size: 12px;
    opacity: 0.85;
    font-weight: 400;
  }

  .newer-btns {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  // 未能确认远端版本：按钮 + 一行原因文案（原因来自后端，前端不再自行猜测错误类型）
  .unavailable-row {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    min-width: 200px;
  }

  .update-hint {
    font-size: 12px;
    line-height: 1.5;
    color: $color-text-secondary;
  }

  .upgrade-panel {
    min-width: 240px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .upgrade-line {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: $color-text-primary;
  }

  .upgrade-spin {
    color: $color-primary;
    font-size: 15px;
  }

  .upgrade-msg {
    font-size: 13px;
    color: $color-text-primary;
  }

  .upgrade-progress {
    width: 240px;
  }

  .upgrade-error-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
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
