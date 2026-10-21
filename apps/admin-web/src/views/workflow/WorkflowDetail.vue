<template>
  <div class="page-container workflow-detail">
    <!-- 顶部：返回按钮 + 层级提示（T02512 / FR-UX-603：隐藏子页要看得出上级，返回要带回来源筛选）
         spacer 占位把后续可能新增的按钮推到右侧 -->
    <div class="top-bar">
      <IconButton :icon="ArrowLeft" plain label="返回列表" desc="返回进入本页时的那一页（保留筛选与分页）" @click="goBack" />
      <PageBreadcrumb :items="breadcrumb" @back="goBack" />
      <span class="spacer" />
    </div>

    <!-- T02516（FR-UX-702）：SSE 断流 / 轮询失败常驻提示 + 「立即重连并刷新」入口 -->
    <FeedHealthBanner :feed="feed" @refresh="feed.refreshNow()" />

    <el-card v-loading="loading" shadow="never" class="info-card">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="工作流 ID">{{ detail.workflow_id }}</el-descriptions-item>
        <el-descriptions-item label="频道">
          <!-- 频道可能因频道删除而悬空（ON DELETE SET NULL），显示占位而非空白 -->
          <el-tag v-if="detail.channel_name" size="small" type="info">{{ detail.channel_name }}</el-tag>
          <span v-else class="text-muted">默认</span>
        </el-descriptions-item>
        <el-descriptions-item label="节目日期">{{ detail.episode_date }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ sourceLabel(detail.source) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(detail.status)">{{ statusLabel(detail.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatTime(detail.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ formatTime(detail.finished_at) }}</el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="detail.error"
        class="error-alert"
        :title="detail.error"
        type="error"
        :closable="false"
        show-icon
      />
    </el-card>

    <!-- 步骤进度条：5 步流水线可视化 -->
    <el-card shadow="never" class="steps-card">
      <el-steps :active="activeStep" align-center>
        <el-step
          v-for="(s, i) in orderedSteps"
          :key="s.name"
          :title="stepLabel(s.name)"
          :status="stepElStatus(s.status)"
          :description="i === activeStep ? stepStatusText(s.status) : ''"
        />
      </el-steps>
    </el-card>

    <!-- 步骤详情表格 -->
    <el-card shadow="never" class="table-card">
      <el-table :data="orderedSteps" stripe>
        <el-table-column label="步骤" width="160">
          <template #default="{ row }">{{ stepLabel(row.name) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="stepTagType(row.status)" size="small">{{ stepStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="结束时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
        </el-table-column>
        <el-table-column label="耗时(秒)" width="110">
          <template #default="{ row }">{{ formatDuration(row) }}</template>
        </el-table-column>
        <el-table-column prop="retry_count" label="重试次数" width="100" />
        <el-table-column prop="error" label="错误信息" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 步骤产物折叠面板：展开后懒加载对应产物并支持 CRUD -->
    <el-card shadow="never" class="products-card">
      <template #header>
        <span class="card-title">步骤产物</span>
      </template>
      <el-collapse v-model="activePanels" @change="handlePanelChange">
        <!-- crawl 素材 -->
        <el-collapse-item name="crawl">
          <template #title>
            <span class="panel-title">爬虫采集 · 素材</span>
            <el-badge :value="materials.total" :hidden="materials.total === 0" class="panel-badge" />
          </template>
          <div class="panel-content">
            <div class="panel-toolbar">
              <IconButton size="small" type="primary" :icon="Plus" label="新增素材" desc="新增一条素材" @click="openMaterialDialog()" />
              <IconButton size="small" :icon="Refresh" label="刷新" desc="重新加载素材列表" @click="loadMaterials" />
            </div>
            <el-table :data="materials.list" v-loading="materials.loading" size="small" stripe>
              <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
              <el-table-column prop="source" label="来源" width="100" />
              <el-table-column prop="category" label="品类" width="80" />
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="materialStatusType(row.status)">{{ materialStatusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <IconButton size="small" link :icon="View" label="查看" desc="查看素材全文" @click="viewMaterial(row)" />
                  <IconButton size="small" link :icon="Edit" label="编辑" desc="编辑该素材" @click="openMaterialDialog(row)" />
                  <IconButton size="small" link type="danger" :icon="Delete" label="删除" desc="删除该素材" @click="handleDeleteMaterial(row)" />
                </template>
              </el-table-column>
              <template #empty><el-empty description="本工作流尚未关联素材" :image-size="80" /></template>
            </el-table>
            <el-pagination
              v-if="materials.total > 20"
              v-model:current-page="materialsPage"
              :total="materials.total"
              :page-size="20"
              layout="total, prev, pager, next"
              small
              @current-change="loadMaterials"
              class="panel-pagination"
            />
          </div>
        </el-collapse-item>

        <!-- rewrite 稿件 -->
        <el-collapse-item name="rewrite">
          <template #title>
            <span class="panel-title">LLM改写 · 稿件</span>
          </template>
          <div class="panel-content">
            <div v-loading="script.loading">
              <template v-if="script.data">
                <el-descriptions :column="3" border size="small" class="script-info">
                  <el-descriptions-item label="稿件 ID">{{ script.data.id }}</el-descriptions-item>
                  <el-descriptions-item label="总字数">{{ script.data.total_words }}</el-descriptions-item>
                  <el-descriptions-item label="估算时长">{{ script.data.estimated_duration }}s</el-descriptions-item>
                  <el-descriptions-item label="状态">
                    <el-tag size="small">{{ script.data.status }}</el-tag>
                  </el-descriptions-item>
                </el-descriptions>
                <div class="panel-toolbar">
                  <IconButton size="small" type="primary" :icon="Edit" label="编辑分段" desc="编辑稿件各分段标题与内容" @click="openSegmentsEditor" />
                  <IconButton size="small" type="danger" :icon="Delete" label="删除稿件" desc="删除该稿件" @click="handleDeleteScript" />
                </div>
                <el-table :data="script.data.segments" size="small" stripe>
                  <el-table-column prop="seq" label="#" width="50" />
                  <el-table-column prop="title" label="段标题" min-width="150" show-overflow-tooltip />
                  <el-table-column label="段内容" min-width="300" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.content?.slice(0, 80) }}...</template>
                  </el-table-column>
                  <el-table-column label="字数" width="80">
                    <template #default="{ row }">{{ row.content?.length || 0 }}</template>
                  </el-table-column>
                </el-table>

                <!-- LLM 语义级质量审核报告（T01712 P1 只告警不回退，供人工审核参考）
                     服务端仅在审核实际执行时才落库报告，无报告（老稿/未启用）不渲染区块 -->
                <template v-if="qualityReport">
                  <div class="qc-header">
                    <span class="qc-title">质量审核报告</span>
                    <el-tag size="small" :type="qualityReport.passed ? 'success' : 'warning'">
                      {{ qualityReport.passed ? '通过' : `发现 ${qualityReport.issue_count} 个问题` }}
                    </el-tag>
                    <span class="qc-time">{{ formatTime(qualityReport.checked_at) }}</span>
                    <el-tag v-if="qualityReport.alert_count" size="small" type="danger">
                      高优告警 {{ qualityReport.alert_count }}
                    </el-tag>
                  </div>
                  <el-table
                    v-if="qualityReport.issues?.length"
                    :data="qualityReport.issues"
                    size="small" stripe
                  >
                    <el-table-column prop="seq" label="段" width="50" />
                    <el-table-column label="类型" width="110">
                      <template #default="{ row }">{{ issueTypeLabel(row.issue_type) }}</template>
                    </el-table-column>
                    <el-table-column label="级别" width="80">
                      <template #default="{ row }">
                        <el-tag size="small" :type="severityTagType(row.severity)">{{ severityLabel(row.severity) }}</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="evidence" label="问题片段" min-width="200" show-overflow-tooltip />
                    <el-table-column prop="suggestion" label="修改建议" min-width="200" show-overflow-tooltip />
                  </el-table>
                  <el-empty
                    v-else
                    description="未发现语义级问题"
                    :image-size="48"
                  />
                </template>
              </template>
              <el-empty v-else-if="!script.loading" description="该工作流暂无稿件" />
            </div>
          </div>
        </el-collapse-item>

        <!-- tts 音频片段 -->
        <el-collapse-item name="tts">
          <template #title>
            <span class="panel-title">语音合成 · TTS 片段</span>
            <el-badge :value="audioFiles.tts.length" :hidden="audioFiles.tts.length === 0" class="panel-badge" />
          </template>
          <div class="panel-content">
            <div class="panel-toolbar">
              <IconButton size="small" :icon="Refresh" label="刷新" desc="重新加载音频文件列表" @click="loadAudioFiles" />
            </div>
            <el-table :data="audioFiles.tts" v-loading="audioFiles.loading" size="small" stripe>
              <el-table-column prop="name" label="文件名" min-width="200" show-overflow-tooltip />
              <el-table-column label="大小" width="100">
                <template #default="{ row }">{{ formatFileSize(row.size_bytes) }}</template>
              </el-table-column>
              <el-table-column label="播放" min-width="280">
                <template #default="{ row }">
                  <div class="inline-audio">
                    <audio
                      v-if="row.blobUrl"
                      :src="row.blobUrl"
                      controls
                      preload="none"
                      class="audio-bar"
                    />
                    <IconButton
                      v-else
                      size="small"
                      link
                      :loading="row.loading"
                      :icon="VideoPlay"
                      label="点击加载播放"
                      desc="加载并播放该音频片段"
                      @click="ensureTtsBlob(row)"
                    />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" fixed="right">
                <template #default="{ row }">
                  <IconButton v-if="!row.remote" size="small" link type="danger" :icon="Delete" label="删除" desc="删除该音频片段" @click="handleDeleteTts(row.name)" />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-item>

        <!-- stitch 成品音频 -->
        <el-collapse-item name="stitch">
          <template #title>
            <span class="panel-title">音频拼接 · 成品</span>
          </template>
          <div class="panel-content">
            <div v-loading="audioFiles.loading">
              <template v-if="audioFiles.episode">
                <el-descriptions :column="2" border size="small">
                  <el-descriptions-item label="文件路径">{{ audioFiles.episode.path }}</el-descriptions-item>
                  <el-descriptions-item label="状态">
                    <el-tag size="small" type="success">已生成</el-tag>
                  </el-descriptions-item>
                </el-descriptions>
                <div class="episode-player">
                  <audio
                    v-if="episodePlayer.blobUrl"
                    :src="episodePlayer.blobUrl"
                    controls
                    autoplay
                    class="audio-bar"
                  />
                  <IconButton
                    v-else
                    type="primary"
                    :loading="episodePlayer.loading"
                    :icon="VideoPlay"
                    label="点击加载播放"
                    desc="加载并播放成品音频"
                    @click="ensureEpisodeBlob"
                  />
                </div>
                <div class="panel-toolbar">
                  <IconButton v-if="!audioFiles.episode?.remote" size="small" type="danger" :icon="Delete" label="删除成品" desc="删除成品音频" @click="handleDeleteEpisode" />
                </div>
              </template>
              <el-empty v-else-if="!audioFiles.loading" description="尚未生成成品音频" />
            </div>
          </div>
        </el-collapse-item>

        <!-- review 审核记录 -->
        <el-collapse-item name="review">
          <template #title>
            <span class="panel-title">创建审核 · 审核记录</span>
          </template>
          <div class="panel-content">
            <div v-loading="review.loading">
              <template v-if="review.data">
                <el-descriptions :column="3" border size="small">
                  <el-descriptions-item label="审核 ID">{{ review.data.id }}</el-descriptions-item>
                  <el-descriptions-item label="状态">
                    <el-tag size="small" :type="reviewStatusType(review.data.status)">{{ reviewStatusLabel(review.data.status) }}</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="创建时间">{{ formatTime(review.data.created_at) }}</el-descriptions-item>
                </el-descriptions>
                <div class="panel-toolbar">
                  <IconButton
                    v-if="review.data.status === 'pending'"
                    size="small" type="success"
                    :icon="Check"
                    label="通过"
                    desc="审核通过该稿件"
                    @click="onReviewAction('approve')"
                  />
                  <IconButton
                    v-if="review.data.status === 'pending'"
                    size="small" type="danger"
                    :icon="Close"
                    label="打回"
                    desc="打回该稿件"
                    @click="onReviewAction('reject')"
                  />
                </div>
              </template>
              <el-empty v-else-if="!review.loading" description="该工作流暂无审核记录" />
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 底部操作区：选步骤重跑 -->
    <el-card shadow="never" class="action-card">
      <div class="action-bar">
        <span class="action-label">从指定步骤重跑：</span>
        <el-select v-model="retryStep" placeholder="选择步骤" style="width: 200px">
          <el-option v-for="s in STEP_ORDER" :key="s" :label="stepLabel(s)" :value="s" />
        </el-select>
        <IconButton
          type="primary"
          :disabled="!retryStep"
          :loading="retrying"
          :icon="Refresh"
          label="重跑"
          desc="从指定步骤断点续跑该工作流"
          @click="handleRetry"
        />
      </div>
    </el-card>

    <!-- 素材编辑对话框 -->
    <el-dialog
      v-model="materialDialog.visible"
      :title="materialDialog.id ? '编辑素材' : '新增素材'"
      width="700px"
    >
      <el-form :model="materialDialog.form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="materialDialog.form.title" maxlength="256" />
        </el-form-item>
        <el-form-item label="来源" required>
          <el-input v-model="materialDialog.form.source" />
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="materialDialog.form.url" />
        </el-form-item>
        <el-form-item label="品类">
          <el-input v-model="materialDialog.form.category" />
        </el-form-item>
        <el-form-item label="状态" v-if="materialDialog.id">
          <el-select v-model="materialDialog.form.status" style="width: 120px">
            <el-option v-for="o in materialStatusOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input
            v-model="materialDialog.form.content"
            type="textarea"
            :rows="8"
            :placeholder="materialDialog.contentLoading ? '正文加载中...' : ''"
            :disabled="materialDialog.contentLoading"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <IconButton :icon="Close" label="取消" desc="关闭弹窗，放弃修改" @click="materialDialog.visible = false" />
        <IconButton
          type="primary"
          :loading="materialDialog.saving"
          :disabled="materialDialog.contentLoading"
          :icon="Check"
          label="保存"
          desc="保存素材修改"
          @click="saveMaterial"
        />
      </template>
    </el-dialog>

    <!-- 分段编辑对话框 -->
    <el-dialog v-model="segmentsEditor.visible" title="编辑稿件分段" width="900px" top="5vh">
      <div class="segments-editor">
        <div v-for="(seg, idx) in segmentsEditor.segments" :key="idx" class="segment-item">
          <div class="segment-header">
            <span class="segment-seq">#{{ idx + 1 }}</span>
            <el-input v-model="seg.title" placeholder="段标题" class="segment-title" />
            <IconButton size="small" type="danger" :icon="Delete" circle label="删除分段" desc="删除该分段" @click="removeSegment(idx)" />
          </div>
          <el-input v-model="seg.content" type="textarea" :rows="4" placeholder="段正文" />
        </div>
        <IconButton :icon="Plus" label="新增分段" desc="在末尾追加一个分段" @click="addSegment" class="add-segment" />
      </div>
      <template #footer>
        <IconButton :icon="Close" label="取消" desc="关闭弹窗，放弃修改" @click="segmentsEditor.visible = false" />
        <IconButton type="primary" :loading="segmentsEditor.saving" :icon="Check" label="保存" desc="保存分段修改" @click="saveSegments" />
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
/**
 * 工作流详情页：展示元数据、5 步流水线进度、步骤详情、步骤产物（支持 CRUD）
 *
 * 产物面板设计：
 * - 每个步骤一个折叠面板，展开时懒加载对应产物数据
 * - crawl → Material 表（增删改查）
 * - rewrite → Script 表（查看/编辑分段/删除）
 * - tts → 音频文件列表（试听/删除）
 * - stitch → 成品音频（试听/删除）
 * - review → 审核记录（查看/改状态）
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { ArrowLeft, Plus, Edit, Delete, Refresh, View, VideoPlay, Check, Close } from '@element-plus/icons-vue'
import api from '../../api'
import { subscribe } from '../../utils/sse'
import { cleanupLoadingMasks } from '../../utils/window-guard'
import { formatTime } from '../../utils/format'
import {
  listMaterials, getMaterial, createMaterial, updateMaterial, deleteMaterial,
} from '../../api/materials'
import {
  getScriptByWorkflow, updateSegments, deleteScript,
} from '../../api/scripts'
import {
  listAudioFiles, getTtsAudioUrl, getEpisodeAudioUrl,
  deleteTtsAudio, deleteEpisodeAudio,
} from '../../api/audio'
import { listReviews, handleReviewAction } from '../../api/reviews'
import {
  WORKFLOW_STATUS,
  WORKFLOW_SOURCE,
  WORKFLOW_STEP_NAME,
  WORKFLOW_STEP_STATUS,
  REVIEW_STATUS,
  MATERIAL_STATUS,
  enumLabel,
  enumTagType,
  enumStepStatus,
  enumOptions,
} from '../../constants/enums'
import { returnTarget } from '../../utils/urlState'
import PageBreadcrumb from '../../components/PageBreadcrumb.vue'
import FeedHealthBanner from '../../components/FeedHealthBanner.vue'
import { useFeedHealth } from '../../composables/useFeedHealth'

const route = useRoute()
const router = useRouter()

/**
 * 返回目标（T02512 / FR-UX-603）：列表进本页时把当时的地址（含频道/日期/状态/来源与分页）
 * 挂在 `?from=` 上，返回按它走。
 *
 * 这里刻意**不用 `router.back()`**：后退只回到那个 URL，而列表页的筛选活在组件内存里，
 * 重新挂载即全部重置——从「来源=定时 / 状态=失败」的详情退回去看到的是全量列表，
 * 正是本条需求要点名解决的「返回时来源筛选丢失」。
 */
const backTo = computed(() => returnTarget(route.query, '/workflows'))

const breadcrumb = computed(() => [
  { label: '工作流监控', to: backTo.value },
  { label: route.meta?.title || '工作流详情' },
])

function goBack() {
  router
    .push(backTo.value)
    .catch((err) => console.warn('[workflow-detail] 返回列表被拒绝（已静默处理）:', err?.message || err))
}

const loading = ref(false)
const retrying = ref(false)
const detail = ref({})
// T02516（FR-UX-702）：SSE 状态 + 刷新成败的统一记账；onRefresh 复用 loadDetail()
// （用户主动触发的非 silent 刷新），不新增任何定时器——NFR-UX-03。
const feed = useFeedHealth({ onRefresh: () => loadDetail() })
const retryStep = ref('')

// 详情页 6 阶段时间线只展示产出可见的 6 步（publish 不产素材，后端仍会返回其状态）；
// 步骤名/状态文案一律取自 src/constants/enums.js（FR-UX-405 / T02504）
const STEP_ORDER = ['crawl', 'rewrite', 'quality_check', 'tts', 'stitch', 'review']

const statusTagType = (s) => enumTagType(WORKFLOW_STATUS, s)
const statusLabel = (s) => enumLabel(WORKFLOW_STATUS, s)
const sourceLabel = (s) => enumLabel(WORKFLOW_SOURCE, s, '-')
const stepLabel = (name) => enumLabel(WORKFLOW_STEP_NAME, name)
const stepElStatus = (s) => enumStepStatus(WORKFLOW_STEP_STATUS, s)
const stepStatusText = (s) => enumLabel(WORKFLOW_STEP_STATUS, s)
const stepTagType = (s) => enumTagType(WORKFLOW_STEP_STATUS, s)

const orderedSteps = computed(() => {
  const steps = detail.value.steps || []
  return STEP_ORDER.map((name) => steps.find((s) => s.name === name) || { name, status: 'pending' })
})

const activeStep = computed(() => {
  const idx = orderedSteps.value.findIndex((s) => s.status !== 'success')
  return idx === -1 ? orderedSteps.value.length : idx
})

// ===== 质量审核报告（T01712 P1：只告警不回退，供人工审核参考） =====
// 服务端仅在实际执行审核后才落库报告，无报告（老稿/功能关闭）不渲染
const qualityReport = computed(() => script.value.data?.quality_report || null)

const ISSUE_TYPE_LABELS = {
  fact_anchor: '事实锚点',
  semantic_drift: '语义漂移',
  perspective: '视角混乱',
  structure: '结构问题',
  hook: '钩子问题',
  readability: '可读性',
}
const SEVERITY_LABELS = { high: '高', medium: '中', low: '低' }
const SEVERITY_TAG_TYPES = { high: 'danger', medium: 'warning', low: 'info' }

function issueTypeLabel(t) { return ISSUE_TYPE_LABELS[t] || t }
function severityLabel(s) { return SEVERITY_LABELS[s] || s }
function severityTagType(s) { return SEVERITY_TAG_TYPES[s] || 'info' }


function formatDuration(row) {
  if (!row?.started_at || !row?.finished_at) return '-'
  const ms = new Date(row.finished_at).getTime() - new Date(row.started_at).getTime()
  if (Number.isNaN(ms) || ms < 0) return '-'
  return (ms / 1000).toFixed(1)
}

// silent=true 时为轮询调用：不显示整表遮罩、不弹错误提示
// 避免轮询期间频繁触发 v-loading 遮罩残留导致"卡死"现象
async function loadDetail(silent = false) {
  if (!silent) loading.value = true
  try {
    detail.value = await api.get(`/workflows/${route.params.id}`, { silent })
    feed.markPollSuccess()
    // 根据最新状态启停轮询：工作流非终态时启动，终态时停止
    startPollingIfNeeded()
  } catch (e) {
    // T02516（FR-UX-702）：silent 模式下拦截器把提示一并抑制了，
    // 「轮询整晚挂掉、页面一直显示旧进度」此前零痕迹——失败只能在这里落到健康度条。
    feed.markPollFailure(e)
  } finally {
    if (!silent) loading.value = false
  }
}

// ===== 步骤产物折叠面板 =====
const activePanels = ref([])

// 已加载过的面板集合，避免重复加载
const loadedPanels = new Set()

function handlePanelChange(panels) {
  // panels 是当前展开的面板 name 数组
  const newlyOpened = panels.filter((p) => !loadedPanels.has(p))
  newlyOpened.forEach((p) => {
    loadedPanels.add(p)
    loadPanelData(p)
  })
}

async function loadPanelData(panelName) {
  switch (panelName) {
    case 'crawl': await loadMaterials(); break
    case 'rewrite': await loadScript(); break
    case 'tts':
    case 'stitch': await loadAudioFiles(); break
    case 'review': await loadReview(); break
  }
}

// ===== crawl 素材 =====
const materials = ref({ list: [], total: 0, loading: false })
const materialsPage = ref(1)

async function loadMaterials() {
  materials.value.loading = true
  try {
    // 素材是「频道级素材池」：按当前工作流的 channel_id 查询，而非 workflow_id
    // （workflow_id 终态后被调度器释放为 NULL，按它查必然为空）
    const data = await listMaterials({
      channel_id: detail.value.channel_id,
      page: materialsPage.value,
      size: 20,
    })
    materials.value.list = data.list || []
    materials.value.total = data.total || 0
  } catch { /* 拦截器已提示 */ } finally {
    materials.value.loading = false
  }
}

// 素材状态文案取自 src/constants/enums.js（FR-UX-405 / T02504）：
// 此前这里抄了一份「待处理/已选中」，素材库管理页同字段叫「待消费/已选题」——
// 同一条素材在两个页面两种说法，门禁（validate-nav）现在会拦住这种第二份映射
const materialStatusOptions = enumOptions(MATERIAL_STATUS)
function materialStatusLabel(s) { return enumLabel(MATERIAL_STATUS, s) }
function materialStatusType(s) { return enumTagType(MATERIAL_STATUS, s) }

const materialDialog = ref({
  visible: false, id: null, saving: false, contentLoading: false,
  form: { title: '', source: '', url: '', category: '', status: 'pending', content: '' },
})
// 编辑素材时拉取全文的请求序号，用于丢弃过期响应（用户快速切换素材时旧请求不应覆盖新对话框）
let materialContentReqId = 0

function openMaterialDialog(material = null) {
  if (material) {
    materialDialog.value = {
      visible: true, id: material.id, saving: false, contentLoading: true,
      form: { title: material.title, source: material.source, url: material.url,
        category: material.category || '', status: material.status || 'pending', content: '' },
    }
    // 编辑时拉取全文，使用序号避免快速切换素材时旧响应覆盖新对话框内容
    const reqId = ++materialContentReqId
    getMaterial(material.id).then((data) => {
      if (reqId !== materialContentReqId) return  // 过期响应丢弃
      materialDialog.value.form.content = data.content || ''
    }).catch(() => {
      if (reqId !== materialContentReqId) return
      ElMessage.warning('素材正文加载失败，请重试')
    }).finally(() => {
      if (reqId !== materialContentReqId) return
      materialDialog.value.contentLoading = false
    })
  } else {
    // 新增素材无需拉取全文，重置序号使任何在途的编辑请求过期失效
    materialContentReqId++
    materialDialog.value = {
      visible: true, id: null, saving: false, contentLoading: false,
      form: { title: '', source: '手动添加', url: '', category: '', status: 'pending', content: '' },
    }
  }
}

async function saveMaterial() {
  const f = materialDialog.value.form
  if (!f.title || !f.source || !f.url || !f.content) {
    ElMessage.warning('请填写标题、来源、URL 和正文')
    return
  }
  materialDialog.value.saving = true
  try {
    if (materialDialog.value.id) {
      await updateMaterial(materialDialog.value.id, f)
      ElMessage.success('素材已更新')
    } else {
      await createMaterial({
        ...f,
        workflow_id: route.params.id,
        channel_id: detail.value.channel_id,
      })
      ElMessage.success('素材已新增')
    }
    materialDialog.value.visible = false
    await loadMaterials()
  } catch { /* 拦截器已提示 */ } finally {
    materialDialog.value.saving = false
  }
}

async function handleDeleteMaterial(row) {
  try {
    await ElMessageBox.confirm(`确认删除素材「${row.title}」？`, '危险操作', { type: 'warning' })
  } catch { return }
  try {
    await deleteMaterial(row.id)
    ElMessage.success('已删除')
    await loadMaterials()
  } catch { /* 拦截器已提示 */ }
}

function viewMaterial(row) {
  getMaterial(row.id).then((data) => {
    // 使用 VNode 渲染替代 HTML 字符串拼接，避免爬虫数据含恶意脚本导致 XSS
    // ElMessageBox 的 message 参数支持 VNode，无需 dangerouslyUseHTMLString
    ElMessageBox.alert(
      h('div', { style: 'max-height:60vh;overflow:auto' }, [
        h('h4', null, data.title),
        h('p', { style: 'color:#999;font-size:12px' }, `来源: ${data.source} | 品类: ${data.category || '-'}`),
        h('div', { style: 'white-space:pre-wrap;margin-top:12px' }, data.content),
      ]),
      '素材详情',
      { customClass: 'material-detail-dialog' },
    )
  })
}

// ===== rewrite 稿件 =====
const script = ref({ data: null, loading: false })

async function loadScript() {
  script.value.loading = true
  try {
    script.value.data = await getScriptByWorkflow(route.params.id)
  } catch {
    // 404 表示暂无稿件，不算错误
    script.value.data = null
  } finally {
    script.value.loading = false
  }
}

async function handleDeleteScript() {
  if (!script.value.data) return
  try {
    await ElMessageBox.confirm('确认删除该稿件？删除后无法恢复。', '危险操作', { type: 'warning' })
  } catch { return }
  try {
    await deleteScript(script.value.data.id)
    ElMessage.success('稿件已删除')
    script.value.data = null
  } catch { /* 拦截器已提示 */ }
}

const segmentsEditor = ref({ visible: false, saving: false, segments: [] })

function openSegmentsEditor() {
  if (!script.value.data) return
  // 深拷贝 segments 避免直接修改原数据
  segmentsEditor.value.segments = (script.value.data.segments || []).map((s) => ({
    title: s.title || '', content: s.content || '', material_ids: s.material_ids || [],
  }))
  segmentsEditor.value.visible = true
}

function addSegment() {
  segmentsEditor.value.segments.push({ title: '', content: '', material_ids: [] })
}

function removeSegment(idx) {
  segmentsEditor.value.segments.splice(idx, 1)
}

async function saveSegments() {
  if (segmentsEditor.value.segments.length === 0) {
    ElMessage.warning('至少保留一个分段')
    return
  }
  segmentsEditor.value.saving = true
  try {
    const data = await updateSegments(script.value.data.id, segmentsEditor.value.segments)
    ElMessage.success('分段已更新')
    if (data.sensitive_warning?.length > 0) {
      ElMessage.warning(`${data.sensitive_warning.length} 段命中敏感词，请注意`)
    }
    segmentsEditor.value.visible = false
    await loadScript()
  } catch { /* 拦截器已提示 */ } finally {
    segmentsEditor.value.saving = false
  }
}

// ===== tts/stitch 音频 =====
// 每项附加 blobUrl（按需加载）和 loading 状态，供内联 <audio> 控件使用
const audioFiles = ref({ tts: [], episode: null, loading: false })
// 成品音频的播放状态（单条，独立于 TTS 列表）
const episodePlayer = ref({ blobUrl: null, loading: false })

async function loadAudioFiles() {
  audioFiles.value.loading = true
  try {
    const data = await listAudioFiles(route.params.id)
    // 为每个 TTS 文件附加播放状态字段，避免每次播放重新拉取列表
    audioFiles.value.tts = (data.tts_dir || []).map((f) => ({
      ...f,
      blobUrl: null,
      loading: false,
    }))
    audioFiles.value.episode = data.episode_file || null
  } catch { /* 拦截器已提示 */ } finally {
    audioFiles.value.loading = false
  }
}

function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

// 按需加载 TTS 音频 blob URL：首次点击播放时拉取，后续直接使用缓存的 blobUrl
// remote=true 时（打包态 COS 对象）走代理端点，否则走本地 audio_cache 端点
async function ensureTtsBlob(row) {
  if (row.blobUrl) return
  row.loading = true
  try {
    row.blobUrl = row.remote && row.url
      ? await getTtsAudioUrl(route.params.id, row.name, row.url)
      : await getTtsAudioUrl(route.params.id, row.name)
  } catch (err) {
    // blob 请求为 silent，需手动提示
    ElMessage.error(err.message || '音频加载失败')
  } finally {
    row.loading = false
  }
}

// 按需加载成品音频 blob URL
// 传入 remoteUrl 时（打包态 COS 对象）走代理，否则走本地 endpoint
async function ensureEpisodeBlob() {
  if (episodePlayer.value.blobUrl) return
  episodePlayer.value.loading = true
  try {
    const ep = audioFiles.value.episode
    episodePlayer.value.blobUrl = ep?.remote && ep?.url
      ? await getEpisodeAudioUrl(route.params.id, ep.url)
      : await getEpisodeAudioUrl(route.params.id)
  } catch (err) {
    ElMessage.error(err.message || '成品音频加载失败')
  } finally {
    episodePlayer.value.loading = false
  }
}

// 释放所有 blob URL，避免内存泄漏（列表刷新/组件卸载时调用）
function revokeAllBlobUrls() {
  audioFiles.value.tts.forEach((f) => {
    if (f.blobUrl) {
      URL.revokeObjectURL(f.blobUrl)
      f.blobUrl = null
    }
  })
  if (episodePlayer.value.blobUrl) {
    URL.revokeObjectURL(episodePlayer.value.blobUrl)
    episodePlayer.value.blobUrl = null
  }
}

async function handleDeleteTts(filename) {
  try {
    await ElMessageBox.confirm(`确认删除音频「${filename}」？`, '危险操作', { type: 'warning' })
  } catch { return }
  try {
    await deleteTtsAudio(route.params.id, filename)
    ElMessage.success('已删除')
    revokeAllBlobUrls()
    await loadAudioFiles()
  } catch { /* 拦截器已提示 */ }
}

async function handleDeleteEpisode() {
  try {
    await ElMessageBox.confirm('确认删除成品音频？', '危险操作', { type: 'warning' })
  } catch { return }
  try {
    await deleteEpisodeAudio(route.params.id)
    ElMessage.success('已删除')
    revokeAllBlobUrls()
    await loadAudioFiles()
  } catch { /* 拦截器已提示 */ }
}

// ===== review 审核 =====
const review = ref({ data: null, loading: false })

function reviewStatusLabel(s) { return enumLabel(REVIEW_STATUS, s) }
function reviewStatusType(s) { return enumTagType(REVIEW_STATUS, s) }

async function loadReview() {
  review.value.loading = true
  try {
    const data = await listReviews({ workflow_id: route.params.id, size: 1 })
    review.value.data = data.list?.[0] || null
  } catch {
    review.value.data = null
  } finally {
    review.value.loading = false
  }
}

async function onReviewAction(action) {
  const reviewId = review.value.data?.id
  if (!reviewId) return
  let reason = null
  if (action === 'reject') {
    try {
      const res = await ElMessageBox.prompt('请输入打回理由', '打回审核', { type: 'warning' })
      reason = res.value
    } catch { return }
  }
  try {
    await handleReviewAction(reviewId, action, reason)
    ElMessage.success(action === 'approve' ? '审核已通过' : '已打回')
    await loadReview()
  } catch { /* 拦截器已提示 */ }
}

// ===== 重跑 =====
async function handleRetry() {
  if (!retryStep.value) return
  try {
    await ElMessageBox.confirm(
      `确认从「${stepLabel(retryStep.value)}」步骤开始重跑？将在当前工作流上断点续跑，保留已完成的步骤产出。`,
      '提示', { type: 'warning' },
    )
  } catch { return }
  retrying.value = true
  try {
    await api.post(`/workflows/${route.params.id}/retry`, { step: retryStep.value })
    ElMessage.success('已开始重跑，SSE 将自动刷新进度')
    // 原工作流重跑：workflow_id 不变，无需跳转，直接刷新当前页数据
    await loadDetail()
  } catch { /* 拦截器已提示 */ } finally {
    retrying.value = false
  }
}

// ===== SSE =====
let unsubscribeSseHandlers = []
function setupSSE() {
  const eventTypes = [
    'workflow.started', 'workflow.completed', 'workflow.failed',
    'workflow.step.completed', 'workflow.step.failed',
  ]
  unsubscribeSseHandlers = eventTypes.map((type) =>
    subscribe(type, (event) => {
      const wid = event.data?.workflow_id
      if (!wid || wid !== detail.value.workflow_id) return
      if (document.hidden) return
      // SSE 事件触发时使用 silent 刷新：不显示整表遮罩，不弹错误提示
      loadDetail(true)
    }),
  )
}

// ===== 轮询兜底：当前工作流非终态时 5s 轮询，SSE 断连时仍能感知状态变化 =====
let pollTimer = null
const TERMINAL_STATUSES = new Set(['success', 'failed', 'cancelled'])

function isWorkflowActive() {
  return !TERMINAL_STATUSES.has(detail.value.status)
}

function startPollingIfNeeded() {
  if (pollTimer && !isWorkflowActive()) {
    clearInterval(pollTimer)
    pollTimer = null
    return
  }
  if (!pollTimer && isWorkflowActive()) {
    // silent=true 局部刷新：不显示整表遮罩，避免遮罩残留卡死
    pollTimer = setInterval(() => {
      if (!document.hidden) loadDetail(true)
    }, 5000)
  }
}

// 页面恢复可见时刷新：弥补隐藏期间错过的 SSE 事件
// 根因：页面最小化时浏览器暂停 CSS transition 和 setTimeout，
// Element Plus v-loading 指令的 mask 隐藏流程不执行，DOM 残留。
// 之前用 toggle (true→nextTick→false) 修复不可靠：值未变化时 watch 不触发，
// transitionend 不触发，setTimeout 被 throttle。改为直接调用
// cleanupLoadingMasks() 强制从 DOM 移除残留 mask，不依赖任何时序。
function handleVisibilityChange() {
  if (!document.hidden) {
    // 强制重置所有 loading 状态
    loading.value = false
    materials.value.loading = false
    audioFiles.value.loading = false
    script.value.loading = false
    review.value.loading = false
    // 直接清理所有残留 mask
    cleanupLoadingMasks()
    // rAF 等待浏览器完成一帧渲染后加载新数据
    // silent=true：避免恢复可见时立即触发整表遮罩，造成"卡死"观感
    requestAnimationFrame(() => {
      loadDetail(true)
      startPollingIfNeeded()
    })
  }
}

onMounted(() => {
  loadDetail()
  setupSSE()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  unsubscribeSseHandlers.forEach((fn) => fn())
  unsubscribeSseHandlers = []
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  // 清理所有 blob URL，避免内存泄漏
  revokeAllBlobUrls()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.workflow-detail {
  .top-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;

    .spacer { flex: 1; }
  }

  // 频道悬空时的占位文字：与列表页样式保持一致
  .text-muted {
    font-size: 13px;
    color: $color-text-secondary;
  }

  .info-card, .steps-card, .table-card, .products-card, .action-card {
    margin-bottom: 16px;
  }

  .error-alert { margin-top: 12px; }

  .card-title {
    font-size: 15px;
    font-weight: 600;
  }

  .panel-title {
    font-size: 14px;
    font-weight: 500;
  }

  .panel-badge {
    margin-left: 8px;
  }

  .panel-content {
    padding: 12px 0;
  }

  // 质量审核报告（T01712 P1）：标题行 + issue 明细表
  .qc-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 14px 0 8px;

    .qc-title {
      font-size: 13px;
      font-weight: 600;
    }

    .qc-time {
      font-size: 12px;
      color: $color-text-secondary;
    }
  }

  .panel-toolbar {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }

  .panel-pagination {
    margin-top: 12px;
    justify-content: flex-end;
  }

  .script-info {
    margin-bottom: 12px;
  }

  .action-bar {
    display: flex;
    align-items: center;
    gap: 12px;

    .action-label {
      font-size: 14px;
      color: $color-text-primary;
    }
  }
}

// 分段编辑器
.segments-editor {
  .segment-item {
    margin-bottom: 16px;
    padding: 12px;
    border: 1px solid #ebeef5;
    border-radius: 8px;

    .segment-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;

      .segment-seq {
        font-weight: 600;
        color: $color-primary;
        min-width: 28px;
      }

      .segment-title {
        flex: 1;
      }
    }
  }

  .add-segment {
    width: 100%;
    margin-top: 8px;
  }
}

// 内联音频播放器：列表行内与成品区域共用
.audio-bar {
  width: 100%;
  height: 32px;
  vertical-align: middle;
}
.inline-audio {
  display: flex;
  align-items: center;
}
.episode-player {
  margin: 12px 0;
}
</style>
