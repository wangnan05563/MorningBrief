<template>
  <div class="page-container ai-config">
    <div class="top-bar">
      <span class="page-title">AI 服务配置</span>
      <el-button type="primary" :icon="Check" :loading="saving" @click="handleSave">
        保存配置
      </el-button>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs" @tab-change="handleTabChange">
      <!-- LLM 配置 -->
      <el-tab-pane label="LLM 大模型" name="llm">
        <el-card shadow="never">
          <!-- 预设选择 -->
          <div class="preset-section">
            <span class="section-label">快速选择提供商：</span>
            <el-select
              v-model="selectedPreset"
              placeholder="选择预设"
              @change="applyPreset"
              style="width: 200px"
            >
              <el-option
                v-for="p in presets"
                :key="p.key"
                :label="p.label"
                :value="p.key"
              />
            </el-select>
            <el-link
              v-if="currentPreset?.api_key_url"
              :href="currentPreset.api_key_url"
              target="_blank"
              type="primary"
              style="margin-left: 12px"
            >
              获取 API Key
            </el-link>
            <el-button
              type="warning"
              plain
              :icon="RefreshLeft"
              :loading="resetting"
              style="margin-left: auto"
              @click="handleResetConfig"
            >
              恢复初始配置
            </el-button>
          </div>

          <el-form :model="llmForm" label-width="120px" class="config-form">
            <el-form-item label="API Key">
              <el-input
                v-model="llmForm.api_key"
                :type="showLlmKey ? 'text' : 'password'"
                placeholder="输入 LLM API Key"
              >
                <template #append>
                  <el-button @click="showLlmKey = !showLlmKey">
                    {{ showLlmKey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="llmForm.base_url" placeholder="OpenAI 兼容 API 地址" />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="llmForm.model" placeholder="如 qwen-max, gpt-4o-mini" />
            </el-form-item>
            <el-form-item label="超时(秒)">
              <el-input-number v-model="llmForm.timeout_sec" :min="5" :max="120" />
            </el-form-item>
            <el-form-item label="重试次数">
              <el-input-number v-model="llmForm.retry_attempts" :min="0" :max="10" />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                plain
                :loading="testingLlm"
                @click="handleTestLLM"
              >
                测试连接
              </el-button>
              <el-tag
                v-if="llmTestResult"
                :type="llmTestResult.success ? 'success' : 'danger'"
                style="margin-left: 12px"
              >
                {{ llmTestResult.message }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- TTS 配置 -->
      <el-tab-pane label="TTS 语音合成" name="tts">
        <el-card shadow="never">
          <!-- Provider 选择 -->
          <div class="preset-section">
            <span class="section-label">TTS 引擎：</span>
            <el-select
              v-model="ttsForm.provider"
              placeholder="选择 TTS Provider"
              @change="handleProviderChange"
              style="width: 320px"
            >
              <el-option
                v-for="p in ttsProviders"
                :key="p.key"
                :label="p.label"
                :value="p.key"
              />
            </el-select>
            <el-tag
              v-if="ttsForm.provider === 'edge'"
              type="success"
              style="margin-left: 12px"
            >
              免费 · 无需 API Key
            </el-tag>
          </div>

          <!-- 阿里云 NLS 配置 -->
          <el-form
            v-if="ttsForm.provider === 'aliyun'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <div class="preset-section" style="border-bottom: none; padding-bottom: 0;">
              <span class="section-label">获取密钥：</span>
              <el-link
                href="https://ram.console.aliyun.com/manage/ak"
                target="_blank"
                type="primary"
                style="margin-right: 16px"
              >
                AccessKey 管理
              </el-link>
              <el-link
                href="https://nls-portal.console.aliyun.com/applist"
                target="_blank"
                type="primary"
              >
                NLS 项目 AppKey
              </el-link>
            </div>
            <el-form-item label="AccessToken">
              <el-input
                v-model="ttsForm.api_key"
                :type="showTtsKey ? 'text' : 'password'"
                placeholder="NLS AccessToken（32位hex，非 AccessKey Secret）"
              >
                <template #append>
                  <el-button @click="showTtsKey = !showTtsKey">
                    {{ showTtsKey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                NLS 控制台「获取 Token」生成的访问令牌，不要填 AccessKey Secret
              </div>
            </el-form-item>
            <el-form-item label="App Key">
              <el-input
                v-model="ttsForm.appkey"
                :type="showTtsAppkey ? 'text' : 'password'"
                placeholder="NLS 项目 AppKey"
              >
                <template #append>
                  <el-button @click="showTtsAppkey = !showTtsAppkey">
                    {{ showTtsAppkey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                NLS 项目详情页的 AppKey（非 AccessKey ID）
              </div>
            </el-form-item>
            <el-form-item label="音色">
              <el-select v-model="ttsForm.voice" style="width: 240px">
                <el-option
                  v-for="v in voices"
                  :key="v.key"
                  :label="v.label"
                  :value="v.key"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="采样率">
              <el-input-number v-model="ttsForm.sample_rate" :min="8000" :max="48000" :step="1000" />
            </el-form-item>
            <el-form-item label="音频格式">
              <el-select v-model="ttsForm.format" style="width: 120px">
                <el-option label="MP3" value="mp3" />
                <el-option label="WAV" value="wav" />
                <el-option label="PCM" value="pcm" />
              </el-select>
            </el-form-item>
            <el-form-item label="超时(秒)">
              <el-input-number v-model="ttsForm.timeout_sec" :min="10" :max="300" />
            </el-form-item>
            <el-form-item label="重试次数">
              <el-input-number v-model="ttsForm.retry_attempts" :min="0" :max="10" />
            </el-form-item>
          </el-form>

          <!-- Edge-TTS 配置（免费方案） -->
          <el-form
            v-else-if="ttsForm.provider === 'edge'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <el-alert
              type="success"
              :closable="false"
              style="margin-bottom: 16px"
            >
              Edge-TTS 基于微软 Edge 浏览器在线 TTS 接口，音色与 Azure 神经网络
              音色同源。完全免费、无字符上限、无需 API Key。非官方接口，建议作为
              降级或开发调试方案。
            </el-alert>
            <el-form-item label="音色">
              <el-select v-model="ttsForm.edge_voice" style="width: 360px">
                <el-option
                  v-for="v in voices"
                  :key="v.key"
                  :label="v.label"
                  :value="v.key"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="语速调节">
              <el-input
                v-model="ttsForm.edge_rate"
                placeholder="如 +10% / -10%（可为空）"
              />
            </el-form-item>
            <el-form-item label="音量调节">
              <el-input
                v-model="ttsForm.edge_volume"
                placeholder="如 +20% / -10%（可为空）"
              />
            </el-form-item>
            <el-form-item label="基频调节">
              <el-input
                v-model="ttsForm.edge_pitch"
                placeholder="如 +5Hz / -3Hz（可为空）"
              />
            </el-form-item>
          </el-form>

          <!-- 腾讯云 TTS 配置 -->
          <el-form
            v-else-if="ttsForm.provider === 'tencent'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <el-alert
              type="info"
              :closable="false"
              style="margin-bottom: 16px"
            >
              腾讯云 TTS 凭证可复用 COS 的 SecretId/SecretKey（留空则自动回退到
              COS 配置）。免费额度：精品音色 800 万字符（3 个月内，需控制台领取）。
            </el-alert>
            <el-form-item label="SecretId">
              <el-input
                v-model="ttsForm.tencent_secret_id"
                :type="showTencentId ? 'text' : 'password'"
                placeholder="留空则回退到 COS_SECRET_ID"
              >
                <template #append>
                  <el-button @click="showTencentId = !showTencentId">
                    {{ showTencentId ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="SecretKey">
              <el-input
                v-model="ttsForm.tencent_secret_key"
                :type="showTencentKey ? 'text' : 'password'"
                placeholder="留空则回退到 COS_SECRET_KEY"
              >
                <template #append>
                  <el-button @click="showTencentKey = !showTencentKey">
                    {{ showTencentKey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="地域">
              <el-input
                v-model="ttsForm.tencent_region"
                placeholder="如 ap-guangzhou"
              />
            </el-form-item>
            <el-form-item label="音色">
              <el-select v-model="ttsForm.tencent_voice_type" style="width: 360px">
                <el-option
                  v-for="v in voices"
                  :key="Number(v.key)"
                  :label="v.label"
                  :value="Number(v.key)"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="音量">
              <el-input-number v-model="ttsForm.tencent_volume" :min="-10" :max="10" />
              <span class="field-tip" style="margin-left: 8px">[-10, 10]，0 为默认</span>
            </el-form-item>
            <el-form-item label="语速">
              <el-input-number v-model="ttsForm.tencent_speed" :min="-2" :max="6" />
              <span class="field-tip" style="margin-left: 8px">[-2, 6]，0 为默认</span>
            </el-form-item>
          </el-form>

          <!-- 测试连接（三套 Provider 共用） -->
          <el-form
            :model="ttsForm"
            label-width="120px"
            class="config-form"
            style="margin-top: 16px; border-top: 1px solid var(--el-border-color); padding-top: 16px;"
          >
            <el-form-item>
              <el-button
                type="primary"
                plain
                :loading="testingTts"
                @click="handleTestTTS"
              >
                测试连接
              </el-button>
              <el-tag
                v-if="ttsTestResult"
                :type="ttsTestResult.success ? 'success' : 'danger'"
                style="margin-left: 12px"
              >
                {{ ttsTestResult.message }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 用量统计 -->
      <el-tab-pane label="用量统计" name="usage">
        <el-card shadow="never" v-loading="usageLoading">
          <!-- 今日数据卡片 -->
          <div class="usage-cards">
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.llm_calls }}</div>
              <div class="usage-label">LLM 调用次数</div>
            </div>
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.llm_tokens }}</div>
              <div class="usage-label">LLM Token 消耗</div>
            </div>
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.tts_calls }}</div>
              <div class="usage-label">TTS 调用次数</div>
            </div>
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.tts_chars }}</div>
              <div class="usage-label">TTS 合成字符</div>
            </div>
            <div class="usage-card highlight">
              <div class="usage-value">${{ todayUsage.cost_usd.toFixed(4) }}</div>
              <div class="usage-label">今日费用</div>
            </div>
          </div>

          <!-- 7 天趋势表 -->
          <el-table :data="usageTrend" stripe style="margin-top: 24px">
            <el-table-column prop="date" label="日期" width="130" />
            <el-table-column prop="llm_calls" label="LLM 调用" width="100" />
            <el-table-column prop="llm_tokens" label="LLM Token" width="120" />
            <el-table-column prop="tts_calls" label="TTS 调用" width="100" />
            <el-table-column prop="tts_chars" label="TTS 字符" width="120" />
            <el-table-column label="费用 (USD)" width="120">
              <template #default="{ row }">
                ${{ row.cost_usd.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

import { ElMessage } from '../../utils/message'
import { Check } from '@element-plus/icons-vue'
import api from '../../api'

const activeTab = ref('llm')
const saving = ref(false)
const loading = ref(false)

// LLM 配置
const llmForm = ref({
  api_key: '',
  base_url: '',
  model: '',
  timeout_sec: 30,
  retry_attempts: 3,
})
const showLlmKey = ref(false)
const testingLlm = ref(false)
const llmTestResult = ref(null)
const selectedPreset = ref('')
const presets = ref([])
// 每个预设独立保存的配置（API Key 脱敏），结构：{preset_key: {api_key, base_url, model}}
const presetConfigs = ref({})
const resetting = ref(false)

// TTS 配置（覆盖阿里云/Edge-TTS/腾讯云三套字段）
const ttsForm = ref({
  provider: 'aliyun',
  // 阿里云 NLS
  api_key: '',
  appkey: '',
  voice: 'xiaoyun',
  sample_rate: 44100,
  format: 'mp3',
  timeout_sec: 60,
  retry_attempts: 3,
  // Edge-TTS
  edge_voice: 'zh-CN-XiaoxiaoNeural',
  edge_rate: '',
  edge_volume: '',
  edge_pitch: '',
  // 腾讯云 TTS
  tencent_secret_id: '',
  tencent_secret_key: '',
  tencent_region: 'ap-guangzhou',
  tencent_voice_type: 101011,
  tencent_volume: 0,
  tencent_speed: 0,
})
const showTtsKey = ref(false)
const showTtsAppkey = ref(false)
const showTencentId = ref(false)
const showTencentKey = ref(false)
const testingTts = ref(false)
const ttsTestResult = ref(null)
const voices = ref([])

// TTS Provider 选项
const ttsProviders = [
  { key: 'aliyun', label: '阿里云 NLS（付费，需 API Key）' },
  { key: 'edge', label: 'Edge-TTS（免费，微软神经网络音色）' },
  { key: 'tencent', label: '腾讯云 TTS（付费，可复用 COS 凭证）' },
]

// 用量统计
const usageLoading = ref(false)
const todayUsage = ref({
  llm_calls: 0,
  llm_tokens: 0,
  tts_calls: 0,
  tts_chars: 0,
  cost_usd: 0,
})
const usageTrend = ref([])

// 当前选中的预设（用于显示 API Key 获取链接）
const currentPreset = computed(() =>
  presets.value.find((p) => p.key === selectedPreset.value)
)

// 加载配置
async function loadConfig() {
  loading.value = true
  try {
    const [configData, presetData] = await Promise.all([
      api.get('/ai/config'),
      api.get('/ai/presets'),
    ])
    // 填充 LLM 配置
    if (configData.llm) {
      Object.assign(llmForm.value, configData.llm)
      // 加载每个预设独立保存的配置（API Key 脱敏）
      presetConfigs.value = configData.llm.preset_configs || {}
      // 优先使用后端根据 base_url 反向匹配的 selected_preset
      if (configData.llm.selected_preset) {
        selectedPreset.value = configData.llm.selected_preset
      }
    }
    // 填充 TTS 配置
    if (configData.tts) {
      Object.assign(ttsForm.value, configData.tts)
    }
    presets.value = presetData || []
    // 音色列表按当前 provider 加载（不同 provider 音色 ID 体系不同）
    await loadVoices(ttsForm.value.provider)
    // 兜底：后端未返回 selected_preset 时根据 base_url 自动匹配
    if (!selectedPreset.value && llmForm.value.base_url) {
      const matched = presets.value.find((p) => p.base_url === llmForm.value.base_url)
      if (matched) selectedPreset.value = matched.key
    }
  } finally {
    loading.value = false
  }
}

// 按 provider 加载音色列表
async function loadVoices(provider) {
  try {
    voices.value = await api.get('/ai/voices', { params: { provider } }) || []
  } catch (e) {
    voices.value = []
  }
}

// 切换 TTS Provider：重新加载音色列表并清空测试结果
async function handleProviderChange(provider) {
  ttsTestResult.value = null
  await loadVoices(provider)
}

// 应用预设：切换预设时返显之前保存的配置（API Key/Base URL/Model）
function applyPreset(key) {
  const preset = presets.value.find((p) => p.key === key)
  if (!preset) return
  selectedPreset.value = key
  // 优先使用该预设之前保存的配置，未保存过则用预设默认值
  const saved = presetConfigs.value[key]
  if (saved) {
    llmForm.value.api_key = saved.api_key || ''
    llmForm.value.base_url = saved.base_url || preset.base_url
    llmForm.value.model = saved.model || preset.model
  } else {
    // 未保存过的预设：清空 API Key，使用预设默认 base_url 和 model
    llmForm.value.api_key = ''
    llmForm.value.base_url = preset.base_url
    llmForm.value.model = preset.model
  }
}

// 保存配置
async function handleSave() {
  saving.value = true
  try {
    await api.put('/ai/config', {
      llm: llmForm.value,
      tts: ttsForm.value,
      selected_preset: selectedPreset.value,
    })
    ElMessage.success('配置已保存并热更新')
    // 保存后重新加载配置，刷新 presetConfigs 中的脱敏值
    await loadConfig()
    saving.value = false
  } finally {
    loading.value = false
  }
}

// 测试 LLM 连接
async function handleTestLLM() {
  testingLlm.value = true
  llmTestResult.value = null
  try {
    const data = await api.post('/ai/test-llm', {
      base_url: llmForm.value.base_url,
      api_key: llmForm.value.api_key,
      model: llmForm.value.model,
    })
    llmTestResult.value = data
    testingLlm.value = false
  } finally {
    loading.value = false
  }
}

// 测试 TTS 连接（按 provider 传递对应字段）
async function handleTestTTS() {
  testingTts.value = true
  ttsTestResult.value = null
  try {
    const f = ttsForm.value
    const payload = { provider: f.provider }
    // 按 provider 附加对应字段，避免传无关字段干扰
    if (f.provider === 'aliyun') {
      payload.api_key = f.api_key
      payload.appkey = f.appkey
    } else if (f.provider === 'edge') {
      payload.edge_voice = f.edge_voice
    } else if (f.provider === 'tencent') {
      payload.tencent_secret_id = f.tencent_secret_id
      payload.tencent_secret_key = f.tencent_secret_key
      payload.tencent_region = f.tencent_region
      payload.tencent_voice_type = f.tencent_voice_type
    }
    const data = await api.post('/ai/test-tts', payload)
    ttsTestResult.value = data
    testingTts.value = false
  } finally {
    loading.value = false
  }
}

// 加载用量统计
async function loadUsage() {
  usageLoading.value = true
  try {
    const data = await api.get('/ai/usage')
    todayUsage.value = data.today || todayUsage.value
    usageTrend.value = data.trend || []
    usageLoading.value = false
  } finally {
    loading.value = false
  }
}

// 切换 Tab 时加载对应数据
function handleTabChange(tab) {
  if (tab === 'usage' && usageTrend.value.length === 0) {
    loadUsage()
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.ai-config {
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: $color-text-primary;
    }
  }

  .config-tabs {
    :deep(.el-tabs__item) {
      font-size: 15px;
    }
  }

  .preset-section {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid $color-border;

    .section-label {
      font-size: 14px;
      color: $color-text-secondary;
      margin-right: 8px;
    }
  }

  .config-form {
    max-width: 600px;

    .field-tip {
      font-size: 12px;
      color: $color-text-secondary;
      line-height: 1.5;
      margin-top: 4px;
    }
  }

  .usage-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
  }

  .usage-card {
    background: $color-bg-card;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 20px;
    text-align: center;
    transition: box-shadow 0.2s;

    &:hover {
      box-shadow: $shadow-md;
    }

    &.highlight {
      background: linear-gradient(135deg, $color-primary-light, $color-primary);
      border-color: $color-primary;

      .usage-value {
        color: #fff;
      }

      .usage-label {
        color: rgba(255, 255, 255, 0.9);
      }
    }

    .usage-value {
      font-size: 28px;
      font-weight: 700;
      color: $color-primary-dark;
      margin-bottom: 8px;
    }

    .usage-label {
      font-size: 13px;
      color: $color-text-secondary;
    }
  }
}
</style>
