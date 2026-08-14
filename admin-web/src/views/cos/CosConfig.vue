<template>
  <div class="page-container cos-config">
    <div class="top-bar">
      <el-tag v-if="status.configured" type="success" effect="dark">COS 已配置</el-tag>
      <el-tag v-else type="info">{{ status.bucket ? '凭证未齐' : '尚未配置' }}</el-tag>
      <el-button
        type="primary"
        plain
        :loading="testing"
        style="margin-left: 12px"
        @click="handleTest"
      >
        测试连接
      </el-button>
      <el-button type="primary" :icon="Check" :loading="saving" @click="handleSave">
        保存配置
      </el-button>
    </div>

    <!-- 连接测试结果 -->
    <el-alert
      v-if="testResult"
      :type="testResult.success ? 'success' : 'error'"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      {{ testResult.message }}
      <span v-if="testResult.success && testResult.bucket">
        （Bucket: {{ testResult.bucket }} · Region: {{ testResult.region }}）
      </span>
    </el-alert>

    <el-card shadow="never" v-loading="loading">
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        腾讯云 COS 凭证用于音频/成品文件的云端存储与 CDN 分发。SecretId / SecretKey
        保存后以脱敏形式展示，重新填写即为更新，留空（显示为 **** ）则保留原值。
      </el-alert>

      <el-form :model="form" label-width="140px" class="config-form">
        <el-form-item label="SecretId" prop="secret_id">
          <el-input
            v-model="form.secret_id"
            :type="showId ? 'text' : 'password'"
            placeholder="腾讯云 API 密钥 ID（AKID...）"
          >
            <template #append>
              <el-button @click="showId = !showId">{{ showId ? '隐藏' : '显示' }}</el-button>
            </template>
          </el-input>
          <div class="field-tip" v-if="isMasked(form.secret_id)">当前为已保存的脱敏值，留空表示不修改</div>
        </el-form-item>

        <el-form-item label="SecretKey" prop="secret_key">
          <el-input
            v-model="form.secret_key"
            :type="showKey ? 'text' : 'password'"
            placeholder="腾讯云 API 密钥 Key"
          >
            <template #append>
              <el-button @click="showKey = !showKey">{{ showKey ? '隐藏' : '显示' }}</el-button>
            </template>
          </el-input>
          <div class="field-tip" v-if="isMasked(form.secret_key)">当前为已保存的脱敏值，留空表示不修改</div>
        </el-form-item>

        <el-form-item label="地域" prop="region">
          <el-select v-model="form.region" style="width: 320px" filterable>
            <el-option
              v-for="r in regions"
              :key="r.value"
              :label="r.label"
              :value="r.value"
            />
          </el-select>
          <span class="field-tip" style="margin-left: 8px">存储桶所在地域</span>
        </el-form-item>

        <el-form-item label="存储桶 Bucket" prop="bucket">
          <el-input
            v-model="form.bucket"
            placeholder="如 news-1250000000（不含 -{appid} 后缀亦可，系统按 SecretId APPID 拼接）"
          />
          <div class="field-tip">桶名称，需与 SecretId 归属的 APPID 匹配</div>
        </el-form-item>

        <el-form-item label="CDN 加速域名" prop="cdn_domain">
          <el-input
            v-model="form.cdn_domain"
            placeholder="可选，如 https://cdn.example.com（公开读）"
          />
          <div class="field-tip">
            配置后下载走 CDN 直链（更快），留空则使用预签名临时 URL
          </div>
        </el-form-item>

        <el-form-item>
          <el-link
            href="https://console.cloud.tencent.com/cam/capi"
            target="_blank"
            type="primary"
            underline="hover"
          >
            获取 API 密钥（腾讯云控制台）
          </el-link>
          <el-link
            href="https://console.cloud.tencent.com/cos"
            target="_blank"
            type="primary"
            underline="hover"
            style="margin-left: 16px"
          >
            管理存储桶 COS
          </el-link>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { Check } from '@element-plus/icons-vue'
import { ElMessage } from '../../utils/message'
import {
  getCosConfig,
  saveCosConfig,
  testCosConnection,
  getCosStatus,
} from '../../api/cos'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const showId = ref(false)
const showKey = ref(false)

const form = ref({
  secret_id: '',
  secret_key: '',
  region: 'ap-guangzhou',
  bucket: '',
  cdn_domain: '',
})

// 配置就绪状态（进入页面快速判断）
const status = ref({ configured: false, bucket: '', region: '', cdn_domain: '' })
const testResult = ref(null)

// 腾讯云 COS 常见地域
const regions = [
  { value: 'ap-guangzhou', label: 'ap-guangzhou（广州）' },
  { value: 'ap-shenzhen-fsi', label: 'ap-shenzhen-fsi（深圳金融）' },
  { value: 'ap-shanghai', label: 'ap-shanghai（上海）' },
  { value: 'ap-shanghai-fsi', label: 'ap-shanghai-fsi（上海金融）' },
  { value: 'ap-beijing', label: 'ap-beijing（北京）' },
  { value: 'ap-chengdu', label: 'ap-chengdu（成都）' },
  { value: 'ap-chongqing', label: 'ap-chongqing（重庆）' },
  { value: 'ap-nanjing', label: 'ap-nanjing（南京）' },
  { value: 'ap-hongkong', label: 'ap-hongkong（中国香港）' },
  { value: 'ap-singapore', label: 'ap-singapore（新加坡）' },
  { value: 'ap-tokyo', label: 'ap-tokyo（东京）' },
  { value: 'ap-seoul', label: 'ap-seoul（首尔）' },
  { value: 'ap-bangkok', label: 'ap-bangkok（曼谷）' },
  { value: 'na-siliconvalley', label: 'na-siliconvalley（硅谷）' },
  { value: 'na-ashburn', label: 'na-ashburn（弗吉尼亚）' },
  { value: 'eu-frankfurt', label: 'eu-frankfurt（法兰克福）' },
]

// 判断是否为脱敏值（保留原值标记）
function isMasked(val) {
  return Boolean(val) && typeof val === 'string' && val.startsWith('****')
}

async function loadConfig() {
  loading.value = true
  try {
    const [cfg, st] = await Promise.all([getCosConfig(), getCosStatus()])
    if (cfg) Object.assign(form.value, cfg)
    if (st) status.value = st
  } catch (e) {
    // 全局拦截器已提示
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await saveCosConfig({
      secret_id: form.value.secret_id,
      secret_key: form.value.secret_key,
      region: form.value.region,
      bucket: form.value.bucket,
      cdn_domain: form.value.cdn_domain,
    })
    ElMessage.success('COS 配置已保存并热更新')
    await loadConfig()
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    const data = await testCosConnection()
    testResult.value = data || { success: false, message: '未返回测试结果' }
  } catch (e) {
    testResult.value = { success: false, message: e.message || '连接测试失败' }
  } finally {
    testing.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.cos-config {
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .config-form {
    max-width: 640px;

    .field-tip {
      font-size: 12px;
      color: $color-text-secondary;
      line-height: 1.5;
      margin-top: 4px;
    }
  }
}
</style>
