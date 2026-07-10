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
          <el-form :model="ttsForm" label-width="120px" class="config-form">
            <el-form-item label="API Key">
              <el-input
                v-model="ttsForm.api_key"
                :type="showTtsKey ? 'text' : 'password'"
                placeholder="阿里云 NLS 访问令牌"
              >
                <template #append>
                  <el-button @click="showTtsKey = !showTtsKey">
                    {{ showTtsKey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="App Key">
              <el-input
                v-model="ttsForm.appkey"
                :type="showTtsAppkey ? 'text' : 'password'"
                placeholder="阿里云 NLS 项目 appkey"
              >
                <template #append>
                  <el-button @click="showTtsAppkey = !showTtsAppkey">
                    {{ showTtsAppkey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
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
import { ElMessage } from 'element-plus'
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

// TTS 配置
const ttsForm = ref({
  api_key: '',
  appkey: '',
  voice: 'xiaoyun',
  sample_rate: 44100,
  format: 'mp3',
  timeout_sec: 60,
  retry_attempts: 3,
})
const showTtsKey = ref(false)
const showTtsAppkey = ref(false)
const testingTts = ref(false)
const ttsTestResult = ref(null)
const voices = ref([])

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
    const [configData, presetData, voiceData] = await Promise.all([
      api.get('/ai/config'),
      api.get('/ai/presets'),
      api.get('/ai/voices'),
    ])
    // 填充 LLM 配置
    if (configData.llm) {
      Object.assign(llmForm.value, configData.llm)
    }
    // 填充 TTS 配置
    if (configData.tts) {
      Object.assign(ttsForm.value, configData.tts)
    }
    presets.value = presetData || []
    voices.value = voiceData || []
  } finally {
    loading.value = false
  }
}

// 应用预设
function applyPreset(key) {
  const preset = presets.value.find((p) => p.key === key)
  if (!preset) return
  llmForm.value.base_url = preset.base_url
  llmForm.value.model = preset.model
}

// 保存配置
async function handleSave() {
  saving.value = true
  try {
    await api.put('/ai/config', { llm: llmForm.value, tts: ttsForm.value })
    ElMessage.success('配置已保存并热更新')
  } finally {
    saving.value = false
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
  } finally {
    testingLlm.value = false
  }
}

// 测试 TTS 连接
async function handleTestTTS() {
  testingTts.value = true
  ttsTestResult.value = null
  try {
    const data = await api.post('/ai/test-tts', {
      api_key: ttsForm.value.api_key,
      appkey: ttsForm.value.appkey,
    })
    ttsTestResult.value = data
  } finally {
    testingTts.value = false
  }
}

// 加载用量统计
async function loadUsage() {
  usageLoading.value = true
  try {
    const data = await api.get('/ai/usage')
    todayUsage.value = data.today || todayUsage.value
    usageTrend.value = data.trend || []
  } finally {
    usageLoading.value = false
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
