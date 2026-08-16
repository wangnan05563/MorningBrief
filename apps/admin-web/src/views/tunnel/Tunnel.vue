<template>
  <div class="page-container tunnel-page">
    <!-- 状态卡片 -->
    <div class="card-soft status-card" v-loading="loading">
      <div class="status-row">
        <div class="status-left">
          <div class="status-tags">
            <el-tag :type="isRunning ? 'success' : 'info'" effect="light">
              {{ isRunning ? '● 运行中' : '○ 已停止' }}
            </el-tag>
            <el-tag v-if="status?.provider" type="warning" effect="plain">
              {{ providerLabel(status.provider) }}
            </el-tag>
            <el-tag v-if="isNamedTunnel" type="success" effect="dark">固定域名</el-tag>
          </div>
          <div class="status-url" v-if="status?.public_url">
            <el-tag type="success" effect="dark" class="url-tag">{{ status.public_url }}</el-tag>
            <el-button link type="primary" @click="copyUrl(status.public_url)">
              <el-icon><CopyDocument /></el-icon>
              <span>复制</span>
            </el-button>
            <el-button link type="primary" @click="openUrl(status.public_url + (status.path_prefix || ''))">
              <el-icon><Link /></el-icon>
              <span>打开</span>
            </el-button>
          </div>
          <div class="status-url text-muted" v-else>
            隧道未启动，暂无公网地址
          </div>
        </div>
        <div class="status-right">
          <el-button
            type="primary"
            :loading="starting"
            :disabled="isRunning"
            @click="handleStart"
          >
            <el-icon><VideoPlay /></el-icon>
            <span>启动隧道</span>
          </el-button>
          <el-button
            type="danger"
            :loading="stopping"
            :disabled="!isRunning"
            @click="handleStop"
          >
            <el-icon><VideoPause /></el-icon>
            <span>停止</span>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 下载失败指引 -->
    <el-alert
      v-if="downloadError"
      type="error"
      :closable="false"
      show-icon
      class="alert-block"
    >
      <template #title>二进制下载失败</template>
      <div class="download-error">
        <p>{{ downloadError.message }}</p>
        <p class="strong">请手动下载并放置到以下路径：</p>
        <div class="manual-path">
          <code>{{ downloadError.data.manual_path }}</code>
          <el-button link type="primary" size="small" @click="copyUrl(downloadError.data.manual_path)">
            复制路径
          </el-button>
        </div>
        <div class="download-links">
          <span class="text-muted">下载源：</span>
          <el-button
            v-for="url in downloadError.data.download_urls"
            :key="url"
            link
            type="primary"
            size="small"
            @click="openUrl(url)"
          >
            {{ url.length > 60 ? url.slice(0, 60) + '...' : url }}
          </el-button>
        </div>
        <p class="text-muted">放置后重新点击「启动隧道」即可</p>
      </div>
    </el-alert>

    <!-- Tailscale 授权向导 -->
    <el-alert
      v-if="tailscaleAuthError"
      type="warning"
      :closable="false"
      show-icon
      class="alert-block"
    >
      <template #title>Tailscale Funnel 需要授权</template>
      <div class="tailscale-auth">
        <p>{{ tailscaleAuthError.message }}</p>
        <el-button type="primary" @click="openUrl(tailscaleAuthError.data.auth_url)">
          <el-icon><Link /></el-icon>
          <span>前往授权</span>
        </el-button>
        <p class="text-muted">授权完成后，重新点击「启动隧道」</p>
      </div>
    </el-alert>

    <!-- 配置卡片 -->
    <div class="card-soft config-card">
      <div class="card-header">
        <el-icon><Setting /></el-icon>
        <span>Provider 配置</span>
      </div>
      <el-form :model="form" label-width="140px" class="config-form">
        <el-form-item label="穿透服务">
          <el-select v-model="form.provider" style="width: 100%">
            <el-option label="Cloudflare Tunnel（免注册）" value="cloudflare" />
            <el-option label="cpolar（国内推荐）" value="cpolar" />
            <el-option label="Tailscale Funnel（固定域名）" value="tailscale" />
          </el-select>
          <div class="form-tip">{{ providerDesc(form.provider) }}</div>
        </el-form-item>

        <!-- Cloudflare 模式选择 -->
        <el-form-item v-if="form.provider === 'cloudflare'" label="隧道模式">
          <el-radio-group v-model="form.tunnel_mode">
            <el-radio value="quick">快速模式（临时域名）</el-radio>
            <el-radio value="named">固定域名模式（需配置）</el-radio>
          </el-radio-group>
          <div class="form-tip">
            <span v-if="form.tunnel_mode === 'quick'">无需账号，每次启动随机分配 trycloudflare 域名</span>
            <span v-else>需 Cloudflare 账号 + 托管域名，一次性配置后域名永久固定</span>
          </div>
        </el-form-item>

        <!-- Named Tunnel 向导 -->
        <div v-if="form.provider === 'cloudflare' && form.tunnel_mode === 'named'" class="named-tunnel-wizard">
          <div class="wizard-header">
            <el-icon><MagicStick /></el-icon>
            <span>固定域名配置向导</span>
          </div>
          <el-steps :active="wizardStep" finish-status="success" class="wizard-steps">
            <el-step title="授权登录" />
            <el-step title="创建隧道" />
            <el-step title="配置 DNS" />
          </el-steps>

          <!-- 步骤 1：授权登录 -->
          <div class="wizard-step-content">
            <template v-if="wizardStep === 0">
              <div class="step-desc">
                点击下方按钮启动 Cloudflare 授权，浏览器会自动打开授权页面。
                完成授权后系统会自动检测并进入下一步。
              </div>
              <el-button type="primary" :loading="loginLoading" @click="handleCloudflareLogin">
                <el-icon><Key /></el-icon>
                <span>开始授权</span>
              </el-button>
              <div v-if="loginResult?.auth_url" class="auth-url-box">
                <span class="text-muted">如果浏览器未自动打开，请手动点击：</span>
                <el-button link type="primary" @click="openUrl(loginResult.auth_url)">
                  打开授权链接
                </el-button>
              </div>
              <div v-if="loginResult?.status === 'waiting'" class="login-status">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>等待授权完成...</span>
              </div>
            </template>

            <!-- 步骤 2：创建隧道 -->
            <template v-else-if="wizardStep === 1">
              <div class="step-desc">
                授权成功！cert.pem 已保存。现在创建一个命名隧道。
              </div>
              <el-input
                v-model="createTunnelName"
                placeholder="输入隧道名称（如 MorningBrief-tunnel）"
                style="max-width: 320px"
              />
              <el-button
                type="primary"
                :loading="createLoading"
                :disabled="!createTunnelName.trim()"
                @click="handleCloudflareCreate"
              >
                创建隧道
              </el-button>
              <div v-if="config?.tunnel_id" class="create-result">
                <el-tag type="success" effect="plain">已创建</el-tag>
                <span class="text-muted">ID: {{ config.tunnel_id }}</span>
              </div>
            </template>

            <!-- 步骤 3：配置 DNS -->
            <template v-else-if="wizardStep === 2">
              <div class="step-desc">
                隧道已创建！最后配置 DNS 路由，将你的域名指向此隧道。
              </div>
              <el-input
                v-model="routeHostname"
                placeholder="输入域名（如 news.example.com）"
                style="max-width: 320px"
              />
              <el-button
                type="primary"
                :loading="routeLoading"
                :disabled="!routeHostname.trim()"
                @click="handleCloudflareRouteDns"
              >
                配置 DNS
              </el-button>
            </template>

            <!-- 完成 -->
            <template v-else>
              <el-alert type="success" :closable="false" show-icon>
                <template #title>固定域名配置完成！</template>
                <div>公网地址：https://{{ config?.hostname }}</div>
                <div class="text-muted">保存配置后，点击「启动隧道」即可使用固定域名</div>
              </el-alert>
            </template>
          </div>
        </div>

        <el-form-item v-if="form.provider === 'cpolar'" label="cpolar Authtoken">
          <div class="authtoken-wrap">
            <el-input
              v-model="form.cpolar_authtoken"
              type="password"
              show-password
              :placeholder="config?.cpolar_authtoken_configured
                ? `已配置（${config.cpolar_authtoken_masked}），留空表示不修改`
                : '请输入 cpolar authtoken'"
            />
            <el-tag v-if="config?.cpolar_authtoken_configured" type="success" size="small" effect="plain">
              已配置
            </el-tag>
            <div class="form-tip">
              访问
              <a href="https://dashboard.cpolar.com/signup" target="_blank" rel="noopener noreferrer">cpolar 控制台</a>
              注册并获取 Authtoken
            </div>
          </div>
        </el-form-item>

        <el-form-item label="本地端口">
          <el-input-number
            v-model="form.local_port"
            :min="0"
            :max="65535"
            style="width: 100%"
            placeholder="0 表示从应用端口继承"
          />
          <div class="form-tip">0 表示从应用端口（APP_PORT）继承，通常无需修改</div>
        </el-form-item>

        <el-form-item label="二进制路径">
          <el-input
            v-model="form.binary_path"
            placeholder="留空自动下载，或指定手动放置路径"
          />
          <div class="form-tip">
            <span v-if="form.provider === 'tailscale'">指定 tailscale.exe 路径，留空则自动检测系统安装</span>
            <span v-else>离线环境可预先放置 cloudflared.exe / cpolar.exe 到 data 目录</span>
          </div>
        </el-form-item>

        <el-form-item label="开机自启动">
          <div class="autostart-wrap">
            <el-switch v-model="form.auto_start" />
            <span class="form-tip inline-tip">
              开启后，后端服务启动时自动在后台线程启动隧道
            </span>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="savingConfig" @click="handleSaveConfig">
            <el-icon><Check /></el-icon>
            <span>保存配置</span>
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 使用说明 -->
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="alert-block"
    >
      <template #title>使用说明</template>
      <ol class="usage-list">
        <li>选择 Provider 并保存配置（cpolar 需填写 Authtoken）</li>
        <li v-if="form.provider === 'cloudflare' && form.tunnel_mode === 'named'">
          按向导完成 Cloudflare 授权、创建隧道、配置 DNS 三步
        </li>
        <li>点击「启动隧道」，系统自动下载二进制并建立公网连接</li>
        <li>复制公网地址，在手机或其他设备浏览器打开即可远程访问</li>
        <li>隧道运行期间请勿关闭本程序</li>
        <li v-if="form.provider === 'cloudflare' && form.tunnel_mode === 'quick'" class="text-muted">
          注意：快速模式域名随机且会变化，重启隧道后需更新访问地址
        </li>
        <li v-if="form.provider === 'tailscale'" class="text-muted">
          需先安装 Tailscale 并登录，首次启用 Funnel 需在浏览器完成授权
        </li>
      </ol>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { ElMessage } from '../../utils/message'
import {
  CopyDocument, Link, VideoPlay, VideoPause, Setting, Check,
  MagicStick, Key, Loading,
} from '@element-plus/icons-vue'
import api from '../../api'

// 隧道状态
const status = ref(null)
// 隧道配置（后端返回，含脱敏 authtoken + Named Tunnel 字段）
const config = ref(null)

// 加载状态
const loading = ref(true)
const starting = ref(false)
const stopping = ref(false)
const savingConfig = ref(false)

// 配置表单（本地编辑态，保存后才生效）
const form = ref({
  provider: 'cloudflare',
  local_port: 0,
  cpolar_authtoken: '',
  binary_path: '',
  auto_start: false,
  tunnel_mode: 'quick',
  tunnel_name: '',
  tunnel_id: '',
  credentials_file: '',
  hostname: '',
  cert_file: '',
})

// 下载失败指引
const downloadError = ref(null)
// Tailscale 授权错误
const tailscaleAuthError = ref(null)

// Cloudflare Named Tunnel 向导状态
const wizardStep = ref(0)
const loginLoading = ref(false)
const loginResult = ref(null)
let loginPollTimer = null
const createTunnelName = ref('')
const createLoading = ref(false)
const routeHostname = ref('')
const routeLoading = ref(false)

// 轮询定时器
let pollTimer = null

const isRunning = computed(() => status.value?.status === 'running')
const apiBaseURL = computed(() => {
  const url = status.value?.public_url
  const prefix = status.value?.path_prefix || ''
  if (url) return url + prefix + 'admin/api/v1'
  return '/news/admin/api/v1'
})
const isNamedTunnel = computed(() =>
  config.value?.tunnel_mode === 'named' && config.value?.hostname
)

// 加载状态
// silent: true — 轮询请求不触发全局 ElMessage，避免浏览器最小化时积压错误提示弹出
async function loadStatus() {
  try {
    const data = await api.get('/tunnel/status', { silent: true })
    status.value = data
  } catch (error) {
    // 静默失败：状态查询失败不影响页面其他功能
    console.error('加载隧道状态失败', error)
  }
}

// 加载配置
async function loadConfig() {
  try {
    const data = await api.get('/tunnel/config')
    config.value = data
    form.value.provider = data.provider
    form.value.local_port = data.local_port
    form.value.binary_path = data.binary_path
    form.value.auto_start = data.auto_start
    form.value.tunnel_mode = data.tunnel_mode || 'quick'
    form.value.tunnel_name = data.tunnel_name || ''
    form.value.tunnel_id = data.tunnel_id || ''
    form.value.credentials_file = data.credentials_file || ''
    form.value.hostname = data.hostname || ''
    form.value.cert_file = data.cert_file || ''
    // authtoken 不回显明文，已配置时显示占位
    form.value.cpolar_authtoken = ''
    // 根据 Named Tunnel 配置状态同步向导步骤
    updateWizardStep()
  } catch (error) {
    console.error('加载隧道配置失败', error)
  }
}

// 根据配置状态更新向导步骤
function updateWizardStep() {
  if (form.value.tunnel_mode !== 'named') {
    wizardStep.value = 0
    return
  }
  // 已有 hostname 表示向导已完成
  if (form.value.hostname) {
    wizardStep.value = 3
    return
  }
  // 已有 tunnel_id 表示步骤 2 已完成
  if (form.value.tunnel_id) {
    wizardStep.value = 2
    return
  }
  // 已有 cert_file 表示步骤 1 已完成
  if (form.value.cert_file) {
    wizardStep.value = 1
    return
  }
  wizardStep.value = 0
}

// 启动隧道
async function handleStart() {
  starting.value = true
  downloadError.value = null
  tailscaleAuthError.value = null
  try {
    const data = await api.post('/tunnel/start', {}, { timeout: 120000 })
    status.value = data
    ElMessage.success('隧道已启动')
  } catch (error) {
    // 后端下载失败返回 code=5001 + data.error_type=binary_download_failed
    // Tailscale 授权返回 code=5003 + data.error_type=tailscale_funnel_auth
    const resp = error?.response?.data || error
    if (resp?.code === 5001 && resp?.data?.error_type === 'binary_download_failed') {
      downloadError.value = resp
      ElMessage.error('二进制下载失败，请按提示手动放置')
    } else if (resp?.code === 5003 && resp?.data?.error_type === 'tailscale_funnel_auth') {
      tailscaleAuthError.value = resp
      ElMessage.warning('需要完成 Tailscale 授权')
    } else {
      ElMessage.error(resp?.message || '隧道启动失败')
    }
  } finally {
    starting.value = false
  }
}

// 停止隧道
async function handleStop() {
  stopping.value = true
  try {
    const data = await api.post('/tunnel/stop')
    status.value = data
    ElMessage.success('隧道已关闭')
  } catch (error) {
    const resp = error?.response?.data || error
    ElMessage.error(resp?.message || '停止失败')
  } finally {
    stopping.value = false
  }
}

// 保存配置
async function handleSaveConfig() {
  savingConfig.value = true
  try {
    await api.post('/tunnel/config', {
      provider: form.value.provider,
      local_port: form.value.local_port,
      // 空串表示不修改已有 authtoken
      cpolar_authtoken: form.value.cpolar_authtoken,
      binary_path: form.value.binary_path,
      auto_start: form.value.auto_start,
      tunnel_mode: form.value.tunnel_mode,
      tunnel_name: form.value.tunnel_name,
      tunnel_id: form.value.tunnel_id,
      credentials_file: form.value.credentials_file,
      hostname: form.value.hostname,
      cert_file: form.value.cert_file,
    })
    ElMessage.success('配置已保存，下次启动隧道时生效')
    await loadConfig()
  } catch (error) {
    const resp = error?.response?.data || error
    ElMessage.error(resp?.message || '配置保存失败')
  } finally {
    savingConfig.value = false
  }
}

// ---------- Cloudflare Named Tunnel 向导 ----------

// 步骤 1：启动授权
async function handleCloudflareLogin() {
  loginLoading.value = true
  loginResult.value = null
  try {
    const data = await api.post('/tunnel/cloudflare/login')
    loginResult.value = data
    if (data.status === 'waiting') {
      // 开始轮询授权状态
      startLoginPolling()
    } else if (data.status === 'failed') {
      ElMessage.error(data.message || '授权启动失败')
    }
  } catch (error) {
    const resp = error?.response?.data || error
    ElMessage.error(resp?.message || '授权启动失败')
  } finally {
    loginLoading.value = false
  }
}

// 轮询授权状态
function startLoginPolling() {
  stopLoginPolling()
  loginPollTimer = setInterval(async () => {
    try {
      const data = await api.get('/tunnel/cloudflare/login/status')
      if (data.status === 'success') {
        stopLoginPolling()
        ElMessage.success('授权成功！cert.pem 已保存')
        await loadConfig()
        wizardStep.value = 1
      } else if (data.status === 'failed') {
        stopLoginPolling()
        ElMessage.error(data.message || '授权失败')
        loginResult.value = data
      }
    } catch (error) {
      console.error('轮询授权状态失败', error)
    }
  }, 2500)
}

function stopLoginPolling() {
  if (loginPollTimer) {
    clearInterval(loginPollTimer)
    loginPollTimer = null
  }
}

// 步骤 2：创建隧道
async function handleCloudflareCreate() {
  createLoading.value = true
  try {
    const data = await api.post(
      '/tunnel/cloudflare/create',
      { tunnel_name: createTunnelName.value.trim() },
      { timeout: 120000 }
    )
    ElMessage.success('隧道创建成功')
    await loadConfig()
    wizardStep.value = 2
  } catch (error) {
    const resp = error?.response?.data || error
    ElMessage.error(resp?.message || '创建隧道失败')
  } finally {
    createLoading.value = false
  }
}

// 步骤 3：配置 DNS
async function handleCloudflareRouteDns() {
  routeLoading.value = true
  try {
    const data = await api.post(
      '/tunnel/cloudflare/route-dns',
      {
        tunnel_name_or_id: config.value?.tunnel_name || config.value?.tunnel_id,
        hostname: routeHostname.value.trim(),
      },
      { timeout: 120000 }
    )
    ElMessage.success('DNS 路由配置成功')
    await loadConfig()
    wizardStep.value = 3
  } catch (error) {
    const resp = error?.response?.data || error
    ElMessage.error(resp?.message || 'DNS 配置失败')
  } finally {
    routeLoading.value = false
  }
}

// 复制到剪贴板
async function copyUrl(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本复制')
  }
}

// 新窗口打开
function openUrl(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

// provider 显示名
function providerLabel(name) {
  const map = {
    cloudflare: 'Cloudflare Tunnel',
    cpolar: 'cpolar（国内推荐）',
    tailscale: 'Tailscale Funnel',
  }
  return map[name] || name
}

// provider 描述
function providerDesc(name) {
  const map = {
    cloudflare: '免注册，自动分配 trycloudflare 域名。大陆访问可能不稳定。',
    cpolar: '国内服务器稳定，需注册账号获取 authtoken。',
    tailscale: '免费固定 ts.net 地址；需预装并登录 Tailscale。',
  }
  return map[name] || ''
}

// 运行中轮询状态（检测进程退出、URL 变化）
// 页面不可见时暂停轮询，避免浏览器最小化时积压请求和错误提示
function startPolling() {
  stopPolling()
  if (isRunning.value && !document.hidden) {
    pollTimer = setInterval(loadStatus, 3000)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 监听页面可见性变化：最小化/切换标签页时暂停轮询，恢复时重启
function handleVisibilityChange() {
  if (document.hidden) {
    stopPolling()
  } else if (isRunning.value) {
    loadStatus()
    startPolling()
  }
}

// 监听状态变化启停轮询
watch(isRunning, (running) => {
  if (running) {
    startPolling()
  } else {
    stopPolling()
  }
})

onMounted(async () => {
  loading.value = true
  await Promise.all([loadStatus(), loadConfig()])
  loading.value = false
  startPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  stopPolling()
  stopLoginPolling()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.tunnel-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-card {
  padding: 20px 24px;

  .status-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .status-left {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1;
    min-width: 300px;
  }

  .status-tags {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .status-url {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;

    .url-tag {
      font-size: 14px;
      font-weight: 600;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .status-right {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}

.alert-block {
  border-radius: $radius-lg;

  .download-error {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .strong {
      font-weight: 600;
    }

    .manual-path {
      display: flex;
      align-items: center;
      gap: 8px;

      code {
        background: rgba(255, 154, 162, 0.15);
        padding: 4px 8px;
        border-radius: $radius-sm;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 13px;
      }
    }

    .download-links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
  }

  .tailscale-auth {
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .usage-list {
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: $color-text-primary;

    li {
      line-height: 1.6;
    }
  }
}

.config-card {
  padding: 20px 24px;

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid $color-border;
  }

  .config-form {
    max-width: 640px;
  }

  .form-tip {
    font-size: 12px;
    color: $color-text-secondary;
    margin-top: 4px;
    line-height: 1.5;

    &.inline-tip {
      margin-top: 0;
    }

    a {
      color: $color-primary-dark;
      text-decoration: none;

      &:hover {
        text-decoration: underline;
      }
    }
  }

  .authtoken-wrap {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;

    .el-tag {
      align-self: flex-start;
    }
  }

  .autostart-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.named-tunnel-wizard {
  margin: 12px 0 20px 140px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid $color-border;
  border-radius: $radius-lg;

  .wizard-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 16px;
  }

  .wizard-steps {
    margin-bottom: 24px;
  }

  .wizard-step-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;

    .step-desc {
      color: $color-text-secondary;
      font-size: 13px;
      line-height: 1.6;
    }

    .auth-url-box {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .login-status {
      display: flex;
      align-items: center;
      gap: 6px;
      color: $color-text-secondary;
      font-size: 13px;
    }

    .create-result {
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }
}

.text-muted {
  color: $color-text-secondary;
}
</style>
