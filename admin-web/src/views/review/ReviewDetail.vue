<template>
  <div class="review-detail page-container" v-loading="loading">
    <div class="detail-header">
      <el-button :icon="ArrowLeft" plain @click="goBack">返回</el-button>
      <div class="header-info">
        <span class="info-item">日期：<strong>{{ detail.episode_date }}</strong></span>
        <span class="info-item">工作流ID：<strong>{{ detail.workflow_id }}</strong></span>
        <el-tag :type="statusTagType(detail.status)" effect="light">
          {{ statusText(detail.status) }}
        </el-tag>
      </div>
    </div>

    <el-row :gutter="16">
      <!-- 左侧：稿件全文 + 引用素材 -->
      <el-col :span="14">
        <el-card class="script-card">
          <template #header>
            <span class="card-title">稿件全文</span>
          </template>
          <div class="script-content" v-html="detail.script?.full_text"></div>
          <div class="materials" v-if="detail.script?.referenced_materials?.length">
            <div class="card-subtitle">引用素材</div>
            <ul class="material-list">
              <li v-for="(url, i) in detail.script.referenced_materials" :key="i">
                <a :href="url" target="_blank">{{ url }}</a>
              </li>
            </ul>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：音频试听 + 审核操作 -->
      <el-col :span="10">
        <el-card class="audio-card">
          <template #header>
            <span class="card-title">音频试听</span>
          </template>
          <audio v-if="detail.audio_url" :src="detail.audio_url" controls class="audio-player"></audio>
          <el-empty v-else description="暂无音频" />
        </el-card>

        <el-card class="action-card">
          <template #header>
            <span class="card-title">审核操作</span>
          </template>
          <el-form label-position="top">
            <el-form-item label="操作">
              <el-radio-group v-model="action">
                <el-radio value="approve">通过</el-radio>
                <el-radio value="reject">打回</el-radio>
                <el-radio value="replace">替换段落</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="action === 'replace'" label="选择段落">
              <el-select v-model="segmentId" placeholder="请选择段落" style="width: 100%">
                <el-option
                  v-for="seg in detail.script?.segments || []"
                  :key="seg.seq"
                  :label="`${seg.seq}. ${seg.title}`"
                  :value="seg.seq"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="action === 'reject' || action === 'replace'" label="理由">
              <el-input v-model="reason" type="textarea" :rows="3" placeholder="请输入理由" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="handleSubmit">提交</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
/**
 * 审核详情页：左侧看稿件、右侧听音频并执行审核操作
 *
 * 设计要点：
 * - 三种操作共用一个表单，按 action 动态显示段落选择与理由输入
 * - 提交前用 ElMessageBox 二次确认，避免误操作（审核不可逆）
 * - 操作成功后返回列表页，让列表重新拉取最新待审核数据
 */
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from '../../utils/message'
import { ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import api from '../../api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const detail = ref({})
const action = ref('approve')
const segmentId = ref(null)
const reason = ref('')

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await api.get(`/reviews/${route.params.id}`)
  } catch {
    // 错误提示由拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  // 前置校验：replace 需选段落，reject/replace 需填理由（approve 无需理由）
  if (action.value === 'replace' && !segmentId.value) {
    ElMessage.warning('请选择要替换的段落')
    return
  }
  if ((action.value === 'reject' || action.value === 'replace') && !reason.value.trim()) {
    ElMessage.warning('请填写理由')
    return
  }

  try {
    await ElMessageBox.confirm(`确认执行「${actionText(action.value)}」操作？`, '提示', {
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }

  submitting.value = true
  try {
    // 仅在对应操作下携带 segment_id / reason，保持请求体精简
    const payload = { action: action.value }
    if (action.value === 'replace') payload.segment_id = segmentId.value
    if (action.value === 'reject' || action.value === 'replace') payload.reason = reason.value
    await api.post(`/reviews/${route.params.id}/action`, payload)
    ElMessage.success('操作成功')
    router.push('/review')
  } catch {
    // 错误提示由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

function actionText(a) {
  return { approve: '通过', reject: '打回', replace: '替换段落' }[a]
}

function statusTagType(status) {
  return { pending: 'warning', approved: 'success', rejected: 'danger' }[status] || 'info'
}

function statusText(status) {
  return { pending: '待审核', approved: '已通过', rejected: '已打回' }[status] || status
}

function goBack() {
  router.push('/review')
}

onMounted(loadDetail)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.detail-header {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 16px;

  .header-info {
    display: flex;
    align-items: center;
    gap: 24px;

    .info-item {
      font-size: 14px;
      color: $color-text-secondary;

      strong {
        color: $color-text-primary;
        font-weight: 600;
      }
    }
  }
}

.card-title {
  font-weight: 600;
  color: $color-text-primary;
}

.card-subtitle {
  font-weight: 600;
  color: $color-text-primary;
  margin-top: 20px;
  margin-bottom: 10px;
}

.script-content {
  line-height: 1.8;
  color: $color-text-primary;

  // v-html 渲染的稿件可能含段落标签，统一间距
  :deep(p) {
    margin-bottom: 12px;
  }
}

.material-list {
  list-style: none;
  padding: 0;

  li a {
    color: $color-primary-dark;
    text-decoration: none;
    word-break: break-all;
    font-size: 13px;

    &:hover {
      text-decoration: underline;
    }
  }
}

.audio-card {
  margin-bottom: 16px;
}

.audio-player {
  width: 100%;
  outline: none;
}

.action-card {
  :deep(.el-radio-group) {
    display: flex;
    gap: 8px;
  }
}
</style>
