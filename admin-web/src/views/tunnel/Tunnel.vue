<template>
  <div class="page-container tunnel-page">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <h2 class="page-title">内网穿透</h2>
    </div>

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
          </div>
          <div class="status-url" v-if="status?.public_url">
            <el-tag type="success" effect="dark" class="url-tag">{{ status.public_url }}</el-tag>
            <el-button link type="primary" @click="copyUrl(status.public_url)">
              <el-icon><CopyDocument /></el-icon>
              <span>复制</span>
            </el-button>
            <el-button link type="primary" @click="openUrl(status.public_url)">
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
          </el-select>
          <div class="form-tip">{{ providerDesc(form.provider) }}</div>
        </el-form-item>

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
          <div class="form-tip">离线环境可预先放置 cloudflared.exe / cpolar.exe 到 data 目录</div>
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
        <li>点击「启动隧道」，系统自动下载二进制并建立公网连接</li>
        <li>复制公网地址，在手机或其他设备浏览器打开即可远程访问</li>
        <li>隧道运行期间请勿关闭本程序</li>
        <li class="text-muted">注意：免费版域名随机且会变化，重启隧道后需更新访问地址</li>
      </ol>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CopyDocument, Link, VideoPlay, VideoPause, Setting, Check,
} from '@element-plus/icons-vue'
import api from '../../api'

// 隧道状态
const status = ref(null)
// 隧道配置（后端返回，含脱敏 authtoken）
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
})

// 下载失败指引
const downloadError = ref(null)

// 轮询定时器
let pollTimer = null

const isRunning = computed(() => status.value?.status === 'running')

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
    // authtoken 不回显明文，已配置时显示占位
    form.value.cpolar_authtoken = ''
  } catch (error) {
    // 401 表示未登录，配置端点需认证
    console.error('加载隧道配置失败', error)
  }
}

// 启动隧道
async function handleStart() {
  starting.value = true
  downloadError.value = null
  try {
    const data = await api.post('/tunnel/start')
    status.value = data
    ElMessage.success('隧道已启动')
  } catch (error) {
    // 后端下载失败返回 code=5001 + data.error_type=binary_download_failed
    const resp = error?.response?.data || error
    if (resp?.code === 5001 && resp?.data?.error_type === 'binary_download_failed') {
      downloadError.value = resp
      ElMessage.error('二进制下载失败，请按提示手动放置')
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
  const map = { cloudflare: 'Cloudflare Tunnel', cpolar: 'cpolar（国内推荐）' }
  return map[name] || name
}

// provider 描述
function providerDesc(name) {
  const map = {
    cloudflare: '免注册，自动分配 trycloudflare 域名。大陆访问可能不稳定。',
    cpolar: '国内服务器稳定，需注册账号获取 authtoken。',
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
    // 恢复可见时立即刷新一次状态，再恢复轮询
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

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .page-title {
    font-size: 20px;
    font-weight: 700;
    color: $color-text-primary;
  }
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

.text-muted {
  color: $color-text-secondary;
}
</style>
