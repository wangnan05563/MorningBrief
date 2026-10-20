<template>
  <div class="review-detail page-container" v-loading="loading">
    <div class="detail-header">
      <div class="header-title">
        <div class="header-row">
          <IconButton :icon="ArrowLeft" plain label="返回列表" desc="返回进入本页时的那一页（保留审核状态与分页）" @click="goBack" />
          <PageBreadcrumb :items="breadcrumb" @back="goBack" />
        </div>
        <div class="header-info">
          <span class="info-item">日期：<strong>{{ detail.episode_date }}</strong></span>
          <span class="info-item">工作流ID：<strong>{{ detail.workflow_id }}</strong></span>
          <el-tag :type="statusTagType(detail.status)" effect="light">
            {{ statusText(detail.status) }}
          </el-tag>
        </div>
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

        <!-- T00809：采集到的图片——审核员据此核对抓取质量（是否抓到正文配图、有无脏图） -->
        <el-card class="images-card">
          <template #header>
            <div class="card-header-row">
              <span class="card-title">采集图片</span>
              <span v-if="detail.images?.length" class="image-count">共 {{ detail.image_total ?? detail.images.length }} 张</span>
              <IconButton
                v-if="(detail.images?.length || 0) > IMAGE_SHOW_LIMIT"
                link
                type="primary"
                :icon="ZoomIn"
                label="查看全部图片"
                desc="查看本篇采集到的全部图片"
                @click="galleryVisible = true"
              />
            </div>
          </template>
          <div v-if="detail.images?.length" class="image-grid">
            <el-image
              v-for="(url, i) in detail.images.slice(0, IMAGE_SHOW_LIMIT)"
              :key="url"
              class="image-item"
              :src="url"
              fit="cover"
              referrerpolicy="no-referrer"
              :preview-src-list="detail.images"
              :initial-index="i"
              preview-teleported
              hide-on-click-modal
            >
              <template #error>
                <div class="image-fallback">加载失败</div>
              </template>
            </el-image>
          </div>
          <el-empty v-else description="本篇稿件引用的素材没有采集到图片" :image-size="72" />
        </el-card>
        <!-- T00809 下一步：查看全部采集图片弹窗（全量列表，可点击放大预览） -->
        <el-dialog v-model="galleryVisible" title="全部采集图片" width="840px">
          <div class="gallery-grid">
            <el-image
              v-for="(url, i) in detail.images || []"
              :key="url"
              class="image-item"
              :src="url"
              fit="cover"
              referrerpolicy="no-referrer"
              :preview-src-list="detail.images || []"
              :initial-index="i"
              preview-teleported
              hide-on-click-modal
            >
              <template #error><div class="image-fallback">加载失败</div></template>
            </el-image>
          </div>
          <template #footer>
            <IconButton type="primary" :icon="Close" label="关闭" desc="关闭图片列表" @click="galleryVisible = false" />
          </template>
        </el-dialog>
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
              <IconButton type="primary" :loading="submitting" :icon="Check" label="提交" desc="提交当前审核操作" @click="handleSubmit" />
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
 * - **返回保留来源**（T02512 / FR-UX-603）：列表进本页时把当时地址（含 tab/分页）挂在 `?from=`，
 *   返回与操作后回跳都按它走；深链直接打开（没有 from）时兜回 `/review` 首页，
 *   绝不用 `router.back()`——操作成功后那次是前向导航，back() 会退回详情页自己
 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { ArrowLeft, Check, Close, ZoomIn } from '@element-plus/icons-vue'
import api from '../../api'
import { REVIEW_STATUS, enumLabel, enumTagType } from '../../constants/enums'
import { returnTarget } from '../../utils/urlState'
import PageBreadcrumb from '../../components/PageBreadcrumb.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const detail = ref({})
// T00809 下一步：默认展示前 9 张缩略图，「查看全部」弹窗展示全量（后端已返回完整 images）
const IMAGE_SHOW_LIMIT = 9
const galleryVisible = ref(false)
const action = ref('approve')
const segmentId = ref(null)
const reason = ref('')

/** 返回目标：`?from=` 里那条列表地址（含 tab/分页），没有就回 `/review` */
const backTo = computed(() => returnTarget(route.query, '/review'))

// 层级提示：上级用列表页的真名（与侧栏菜单一致），当前层用路由 meta 标题
const breadcrumb = computed(() => [
  { label: '内容审核', to: backTo.value },
  { label: route.meta?.title || '审核详情' },
])

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
    // 回来源那一页而不是写死 /review：在「已通过 第 3 页」里复核通过后应停回原处，
    // 否则每次操作都被弹回待审核第 1 页，批量复核时得反复重新筛（T02512 / FR-UX-603）
    goBack()
  } catch {
    // 错误提示由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

function actionText(a) {
  return { approve: '通过', reject: '打回', replace: '替换段落' }[a]
}

// 与 ReviewList.vue / WorkflowDetail.vue 同一套 4 态口径，同取 src/constants/enums.js（T02504）
function statusTagType(status) {
  return enumTagType(REVIEW_STATUS, status)
}

function statusText(status) {
  return enumLabel(REVIEW_STATUS, status)
}

/**
 * 回「进入本页时的那一页」：带 query 一起回，来源筛选与分页不丢（T02512）。
 * 面包屑上级与「返回列表」按钮共用这一个出口（面包屑会带上被点的 item，参数忽略即可）。
 */
function goBack() {
  const target = backTo.value
  router
    .push(target)
    .catch((err) => console.warn('[review-detail] 返回列表被拒绝（已静默处理）:', err?.message || err))
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

  // T02512：面包屑与「返回列表」并排，都在信息行之上，避免把日期/状态挤成一长条
  .header-title {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .header-row {
      display: flex;
      align-items: center;
      gap: 16px;
    }
  }

  :deep(.page-breadcrumb) {
    margin-bottom: 0;
  }

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

/* T00809 采集图片：缩略图网格 + 点击 el-image 预览（原图/换图浏览） */
.images-card {
  margin-top: 16px;
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.image-count {
  font-size: 12px;
  color: $color-text-secondary;
}

.image-grid {
  display: grid;
  // 桌面端一行放 5-6 张，窗口变窄自动换行；审核员主要看"抓到了什么"，缩略图足够
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  gap: 8px;
}

.image-item {
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid $color-border;
  background: #f5f7fa;
  cursor: zoom-in;
}

.image-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: $color-text-secondary;
}

/* T00809 下一步：「查看全部」弹窗的大图网格——复用卡片缩略图并放大尺寸 */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
  max-height: 60vh;
  overflow-y: auto;
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
