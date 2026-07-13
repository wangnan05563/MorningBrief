<template>
  <div class="page-container param-calculator">
    <div class="top-bar">
      <span class="page-title">参数计算器</span>
      <el-button type="primary" :icon="ArrowRight" @click="goToAiConfig">
        应用到 AI 配置
      </el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      class="intro-alert"
      show-icon
    >
      <template #title>
        新闻语音三参数关系：时长(秒) = 总字数 / (210 × 倍率) × 60。固定一项由其他两项计算得出，基础语速 210 字/分为项目常量。
      </template>
    </el-alert>

    <!-- 三个参数卡片：auto-fit 在桌面横向、移动端纵向 -->
    <div class="cards-grid">
      <!-- 时长卡片 -->
      <el-card
        shadow="never"
        class="param-card"
        :class="{ locked: lockedParam === 'duration' }"
      >
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <el-icon><Timer /></el-icon>
              <span>时长</span>
            </div>
            <el-tag
              v-if="lockedParam === 'duration'"
              type="warning"
              size="small"
            >
              计算中
            </el-tag>
            <el-button
              v-else
              size="small"
              :icon="Lock"
              @click="lockParam('duration')"
            >
              锁定此项
            </el-button>
          </div>
        </template>

        <div class="card-body">
          <el-input-number
            v-model="durationSec"
            :min="60"
            :max="1800"
            :step="15"
            :disabled="lockedParam === 'duration'"
            controls-position="right"
            style="width: 100%"
          />
          <div class="result-line">
            <span class="result-label">
              {{ lockedParam === 'duration' ? '由其他参数计算得出' : '当前值' }}
            </span>
            <span class="result-value">{{ formatDuration(durationSec) }}</span>
          </div>
        </div>
      </el-card>

      <!-- 总字数卡片 -->
      <el-card
        shadow="never"
        class="param-card"
        :class="{ locked: lockedParam === 'words' }"
      >
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <el-icon><Document /></el-icon>
              <span>总字数</span>
            </div>
            <el-tag
              v-if="lockedParam === 'words'"
              type="warning"
              size="small"
            >
              计算中
            </el-tag>
            <el-button
              v-else
              size="small"
              :icon="Lock"
              @click="lockParam('words')"
            >
              锁定此项
            </el-button>
          </div>
        </template>

        <div class="card-body">
          <el-input-number
            v-model="totalWords"
            :min="200"
            :max="10000"
            :step="50"
            :disabled="lockedParam === 'words'"
            controls-position="right"
            style="width: 100%"
          />
          <div class="result-line">
            <span class="result-label">
              {{ lockedParam === 'words' ? '由其他参数计算得出' : '当前值' }}
            </span>
            <span class="result-value">{{ totalWords }} 字</span>
          </div>
        </div>
      </el-card>

      <!-- 语速倍率卡片 -->
      <el-card
        shadow="never"
        class="param-card"
        :class="{ locked: lockedParam === 'rate' }"
      >
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <el-icon><Odometer /></el-icon>
              <span>语速倍率</span>
            </div>
            <el-tag
              v-if="lockedParam === 'rate'"
              type="warning"
              size="small"
            >
              计算中
            </el-tag>
            <el-button
              v-else
              size="small"
              :icon="Lock"
              @click="lockParam('rate')"
            >
              锁定此项
            </el-button>
          </div>
        </template>

        <div class="card-body">
          <!-- show-input 内置 input-number 与 slider 双向联动 -->
          <el-slider
            v-model="rateMultiplier"
            :min="0.5"
            :max="2.5"
            :step="0.05"
            :disabled="lockedParam === 'rate'"
            show-input
            :show-input-controls="false"
          />
          <div class="result-line">
            <span class="result-label">
              {{ lockedParam === 'rate' ? '由其他参数计算得出' : '当前值' }}
            </span>
            <span class="result-value">{{ formatRate(rateMultiplier) }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 预设方案 -->
    <el-card shadow="never" class="preset-card">
      <template #header>
        <div class="card-header">
          <div class="card-title">
            <el-icon><MagicStick /></el-icon>
            <span>预设方案</span>
          </div>
        </div>
      </template>
      <div class="preset-buttons">
        <el-button
          v-for="p in presets"
          :key="p.key"
          class="preset-btn"
          @click="applyPreset(p)"
        >
          <span class="preset-label">{{ p.label }}</span>
          <span class="preset-hint">{{ p.duration / 60 }}分钟 · {{ p.rate }}x · {{ p.expectedWords }}字</span>
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Timer,
  Document,
  Odometer,
  MagicStick,
  Lock,
  ArrowRight,
} from '@element-plus/icons-vue'

// 项目常量：与 AIConfig 中 calculatedWords 公式保持一致
const BASE_WORDS_PER_MIN = 210

const router = useRouter()

// 三个核心参数（初始值对应"完整节目"预设，方便用户首次进入即可看到自洽状态）
const durationSec = ref(600)
const totalWords = ref(2100)
const rateMultiplier = ref(1.0)

// 锁定项：'duration' | 'words' | 'rate'，默认锁定倍率（用户通常先确定时长和字数）
const lockedParam = ref('rate')

const presets = [
  { key: 'express', label: '新闻速递', duration: 300, rate: 1.0, expectedWords: 1050 },
  { key: 'standard', label: '标准节目', duration: 480, rate: 1.0, expectedWords: 1680 },
  { key: 'full', label: '完整节目', duration: 600, rate: 1.0, expectedWords: 2100 },
  { key: 'fast', label: '快节奏精华', duration: 600, rate: 1.5, expectedWords: 3150 },
]

// 根据当前锁定项，由另外两个参数推算锁定项的值
function recalculate() {
  if (lockedParam.value === 'duration') {
    const v = Math.round(
      totalWords.value / (BASE_WORDS_PER_MIN * rateMultiplier.value) * 60
    )
    durationSec.value = Math.max(60, Math.min(1800, v))
  } else if (lockedParam.value === 'words') {
    const v = Math.round(
      durationSec.value * BASE_WORDS_PER_MIN * rateMultiplier.value / 60
    )
    totalWords.value = Math.max(200, Math.min(10000, v))
  } else if (lockedParam.value === 'rate') {
    const v = Math.round(
      totalWords.value * 60 / (durationSec.value * BASE_WORDS_PER_MIN) * 100
    ) / 100
    rateMultiplier.value = Math.max(0.5, Math.min(2.5, v))
  }
}

// 每个 watch 仅在对应锁定态下触发，避免重算引发链式死循环
watch(
  [totalWords, rateMultiplier],
  () => {
    if (lockedParam.value === 'duration') recalculate()
  }
)
watch(
  [durationSec, rateMultiplier],
  () => {
    if (lockedParam.value === 'words') recalculate()
  }
)
watch(
  [durationSec, totalWords],
  () => {
    if (lockedParam.value === 'rate') recalculate()
  }
)

function lockParam(name) {
  lockedParam.value = name
  // 切换后立即重算，使新锁定项的值与另外两项自洽
  recalculate()
}

function applyPreset(preset) {
  durationSec.value = preset.duration
  rateMultiplier.value = preset.rate
  // 按任务要求：设置时长和倍率后锁定字数进行计算展示
  lockedParam.value = 'words'
  recalculate()
}

function formatDuration(sec) {
  const minutes = Math.floor(sec / 60)
  const remainSec = sec % 60
  return `${minutes}分${remainSec}秒`
}

function formatRate(rate) {
  const wordsPerMin = Math.round(BASE_WORDS_PER_MIN * rate)
  return `${rate.toFixed(2)}x (≈${wordsPerMin}字/分)`
}

// 应用到 AI 配置：通过 query 传参，AIConfig 页面接收后同步到表单
function goToAiConfig() {
  router.push({
    path: '/ai-config',
    query: {
      duration: durationSec.value,
      rate: rateMultiplier.value,
    },
  })
}
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.param-calculator {
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

  .intro-alert {
    margin-bottom: 20px;
  }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
  }

  .param-card {
    transition: all 0.3s ease;

    &.locked {
      border-color: $color-primary;
      box-shadow: 0 0 0 2px rgba(126, 206, 193, 0.2), $shadow-md;
    }

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .card-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 15px;
      font-weight: 600;
      color: $color-text-primary;
    }

    .card-body {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .result-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: $color-bg;
      border-radius: $radius-sm;
      font-size: 13px;

      .result-label {
        color: $color-text-secondary;
      }

      .result-value {
        color: $color-primary-dark;
        font-weight: 600;
      }
    }
  }

  .preset-card {
    .preset-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;

      .preset-btn {
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        height: auto;
        padding: 12px 20px;
        line-height: 1.4;

        .preset-label {
          font-size: 14px;
          font-weight: 600;
        }

        .preset-hint {
          font-size: 12px;
          color: $color-text-secondary;
          font-weight: normal;
        }
      }
    }
  }
}
</style>
