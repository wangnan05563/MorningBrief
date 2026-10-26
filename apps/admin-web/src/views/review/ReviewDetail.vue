<template>
  <div class="review-detail page-container" v-loading="loading">
    <!-- T02626（FR-UX-302）：详情拉取失败与「详情为空」必须分开。
         失败时只给页内错误态 + 重试，不渲染日期/工作流 ID 的空壳，也不允许提交审核。 -->
    <ListLoadError
      v-if="detailLoad.isError"
      :message="detailLoad.errorMessage"
      :stale="!!detail.id"
      :retrying="detailLoad.retrying"
      @retry="detailLoad.retry()"
    />

    <div class="detail-header">
      <div class="header-title">
        <div class="header-row">
          <IconButton :icon="ArrowLeft" plain label="返回列表" desc="返回进入本页时的那一页（保留审核状态与分页）" @click="goBack" />
          <PageBreadcrumb :items="breadcrumb" @back="goBack" />
        </div>
        <div v-if="detail.id" class="header-info">
          <span class="info-item">日期：<strong>{{ detail.episode_date }}</strong></span>
          <span class="info-item">工作流ID：<strong>{{ detail.workflow_id }}</strong></span>
          <el-tag :type="statusTagType(detail.status)" effect="light">
            {{ statusText(detail.status) }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 没有数据时不渲染空卡片：否则首次加载失败会显示「暂无音频」等假空态 -->
    <el-row v-if="detail.id" :gutter="16">
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
            <div class="card-header-row">
              <span class="card-title">音频试听</span>
              <!-- B12：加载成功后才有时长可比对——审核员要确认「听到的是不是这一期」 -->
              <span v-if="audioDuration" class="audio-duration">时长 {{ audioDuration }}</span>
            </div>
          </template>
          <div v-if="detail.audio_url" class="audio-wrap">
            <el-skeleton v-if="audioLoading" :rows="2" animated />
            <el-alert
              v-else-if="audioError"
              data-guide="review-audio-error"
              type="error"
              :closable="false"
              show-icon
              :title="`试听音频加载失败：${audioError}`"
              description="成品音频在私有桶/COS 时直连会被拒绝（403/CORS），必须经后端代理与登录态拉取。请重试；若持续失败，请检查音频代理接口与存储配置。"
            />
            <audio
              v-else
              ref="audioEl"
              :src="audioSrc"
              controls
              class="audio-player"
              @loadedmetadata="onAudioMeta"
              @error="onAudioElementError"
            ></audio>
            <div v-if="audioSrc" class="audio-actions">
              <IconButton link :icon="RefreshLeft" label="重听" desc="从头播放这段试听音频" @click="replayAudio" />
            </div>
            <IconButton
              v-if="audioError"
              class="audio-retry"
              :icon="Refresh"
              label="重试加载"
              desc="重新经代理拉取试听音频"
              :loading="audioLoading"
              @click="loadAudio"
            />
          </div>
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
              <!-- T02626：详情没加载成功时禁用提交——拿空对象/旧详情去改审核状态是静默破坏 -->
              <IconButton type="primary" :loading="submitting" :disabled="detailLoad.isError" :icon="Check" label="提交" desc="提交当前审核操作" @click="handleSubmit" />
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
 * - 提交前用 dangerConfirm 二次确认，写清对象/后果/可撤销性（T02596）
 * - 操作成功后返回列表页，让列表重新拉取最新待审核数据
 * - **返回保留来源**（T02512 / FR-UX-603）：列表进本页时把当时地址（含 tab/分页）挂在 `?from=`，
 *   返回与操作后回跳都按它走；深链直接打开（没有 from）时兜回 `/review` 首页，
 *   绝不用 `router.back()`——操作成功后那次是前向导航，back() 会退回详情页自己
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import { ArrowLeft, Check, Close, ZoomIn, Refresh, RefreshLeft } from '@element-plus/icons-vue'
import api from '../../api'
import { getEpisodeAudioUrl } from '../../api/audio'
import { REVIEW_STATUS, enumLabel, enumTagType } from '../../constants/enums'
import { returnTarget } from '../../utils/urlState'
import PageBreadcrumb from '../../components/PageBreadcrumb.vue'
import ListLoadError from '../../components/ListLoadError.vue'
import { useLoadState } from '../../composables/useLoadState'

const route = useRoute()
const router = useRouter()

const submitting = ref(false)
const detail = ref({})
// T02626（FR-UX-302）：详情三态收敛到 useLoadState。失败时保留旧详情（stale 提示），
// 只有「拿到详情」才算 ready——此前 catch 后什么都不变，首屏失败就落一屏空字段。
const detailLoad = useLoadState(
  async () => {
    const data = await api.get(`/reviews/${route.params.id}`)
    detail.value = data || {}
    await loadAudio()
    return detail.value
  },
  { failMessage: '审核详情加载失败' },
)
const loading = detailLoad.isLoading
// T00809 下一步：默认展示前 9 张缩略图，「查看全部」弹窗展示全量（后端已返回完整 images）
const IMAGE_SHOW_LIMIT = 9
const galleryVisible = ref(false)
const action = ref('approve')
const segmentId = ref(null)
const reason = ref('')

// B12（FR-UX-602）：试听音频必须走 /audio/proxy（JWT + 私有桶），不能把远端 URL 直接塞进 <audio>。
// 直连时 403/CORS 在界面上没有任何反馈，审核员会「没听到就盲批」。
const audioEl = ref(null)
const audioSrc = ref('')
const audioLoading = ref(false)
const audioError = ref('')
const audioDuration = ref('')
// 并发/重试令牌：旧请求晚回来时不能覆盖新一轮的状态
let audioToken = 0

function releaseAudio() {
  if (audioSrc.value) {
    URL.revokeObjectURL(audioSrc.value)
    audioSrc.value = ''
  }
}

async function loadAudio() {
  const remoteUrl = detail.value.audio_url
  if (!remoteUrl) {
    releaseAudio()
    audioError.value = ''
    audioDuration.value = ''
    return
  }
  const workflowId = detail.value.workflow_id
  if (!workflowId) {
    audioError.value = '详情缺少工作流 ID，无法经代理加载音频'
    return
  }
  const token = ++audioToken
  audioLoading.value = true
  audioError.value = ''
  audioDuration.value = ''
  releaseAudio()
  try {
    const blobUrl = await getEpisodeAudioUrl(workflowId, remoteUrl)
    if (token !== audioToken) {
      URL.revokeObjectURL(blobUrl)
      return
    }
    audioSrc.value = blobUrl
  } catch (e) {
    if (token === audioToken) audioError.value = e?.message || '未知错误'
  } finally {
    if (token === audioToken) audioLoading.value = false
  }
}

function formatClock(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return ''
  const total = Math.round(sec)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function onAudioMeta() {
  audioDuration.value = formatClock(audioEl.value?.duration)
}

function onAudioElementError() {
  // 元素自身的解码/网络错误也要落成页面文字：blob 拉取成功但内容不是音频时同样不能静默
  audioError.value = '浏览器无法解码该音频（文件可能损坏或格式不支持）'
  releaseAudio()
}

function replayAudio() {
  if (!audioEl.value) return
  audioEl.value.currentTime = 0
  audioEl.value.play().catch(() => {})
}

/** 返回目标：`?from=` 里那条列表地址（含 tab/分页），没有就回 `/review` */
const backTo = computed(() => returnTarget(route.query, '/review'))

// 层级提示：上级用列表页的真名（与侧栏菜单一致），当前层用路由 meta 标题
const breadcrumb = computed(() => [
  { label: '内容审核', to: backTo.value },
  { label: route.meta?.title || '审核详情' },
])

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

  // T02596：审核动作有副作用（通过=自动发布，打回/替换=稿件退回重做），
  // 确认框要把对象、后果和可撤销性一起说清，而不是一句「确认执行」。
  const actionLabel = actionText(action.value)
  const ok = await dangerConfirm({
    action: `${actionLabel}审核`,
    target: `审核 #${detail.value?.id ?? route.params.id}（工作流 ${detail.value?.workflow_id || '未知'}，${detail.value?.episode_date || '日期未知'}）`,
    scope:
      action.value === 'approve'
        ? '审核 1 条（通过后立即自动发布对应节目）'
        : action.value === 'reject'
          ? '审核 1 条（打回后内容需要重新改写）'
          : `审核 1 条（替换第 ${segmentId.value} 段后重新提交）`,
    lines: action.value === 'approve' ? ['节目发布后听众即刻可见。'] : [],
    irreversible:
      action.value === 'approve'
        ? '发布后无法在本页撤回，需要到节目侧手工下线。'
        : '审核状态会立即变更，无法在本页撤销；重新生成/改写后才能再次提交。',
    confirmLabel: `确认${actionLabel}`,
  })
  if (!ok) return // 用户取消

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

onMounted(detailLoad.load)
onBeforeUnmount(() => {
  audioToken += 1
  releaseAudio()
})
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

.audio-duration {
  font-size: 12px;
  color: $color-text-secondary;
}

.audio-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.audio-retry {
  margin-top: 8px;
}

.action-card {
  :deep(.el-radio-group) {
    display: flex;
    gap: 8px;
  }
}
</style>
