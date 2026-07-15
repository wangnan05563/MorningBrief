<template>
  <div class="page-container workflow-detail">
    <!-- 顶部：仅保留返回按钮，去掉页面标题（导航栏已显示页面名称）
         spacer 占位把后续可能新增的按钮推到右侧 -->
    <div class="top-bar">
      <el-button :icon="ArrowLeft" plain @click="router.back()">返回</el-button>
      <span class="spacer" />
    </div>

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
              <el-button size="small" type="primary" :icon="Plus" @click="openMaterialDialog()">新增素材</el-button>
              <el-button size="small" :icon="Refresh" @click="loadMaterials">刷新</el-button>
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
                  <el-button size="small" link @click="viewMaterial(row)">查看</el-button>
                  <el-button size="small" link @click="openMaterialDialog(row)">编辑</el-button>
                  <el-button size="small" link type="danger" @click="handleDeleteMaterial(row)">删除</el-button>
                </template>
              </el-table-column>
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
                  <el-button size="small" type="primary" :icon="Edit" @click="openSegmentsEditor">编辑分段</el-button>
                  <el-button size="small" type="danger" :icon="Delete" @click="handleDeleteScript">删除稿件</el-button>
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
              <el-button size="small" :icon="Refresh" @click="loadAudioFiles">刷新</el-button>
            </div>
            <el-table :data="audioFiles.tts" v-loading="audioFiles.loading" size="small" stripe>
              <el-table-column prop="name" label="文件名" min-width="200" />
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
                    <el-button
                      v-else
                      size="small"
                      link
                      :loading="row.loading"
                      @click="ensureTtsBlob(row)"
                    >
                      点击加载播放
                    </el-button>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" link type="danger" @click="handleDeleteTts(row.name)">删除</el-button>
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
                  <el-button
                    v-else
                    type="primary"
                    :loading="episodePlayer.loading"
                    @click="ensureEpisodeBlob"
                  >
                    点击加载播放
                  </el-button>
                </div>
                <div class="panel-toolbar">
                  <el-button size="small" type="danger" :icon="Delete" @click="handleDeleteEpisode">删除成品</el-button>
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
                  <el-button
                    v-if="review.data.status === 'pending'"
                    size="small" type="success"
                    @click="onReviewAction('approve')"
                  >通过</el-button>
                  <el-button
                    v-if="review.data.status === 'pending'"
                    size="small" type="danger"
                    @click="onReviewAction('reject')"
                  >打回</el-button>
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
        <el-button
          type="primary"
          :icon="RefreshRight"
          :disabled="!retryStep"
          :loading="retrying"
          @click="handleRetry"
        >
          重跑
        </el-button>
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
            <el-option label="待处理" value="pending" />
            <el-option label="已选中" value="selected" />
            <el-option label="已跳过" value="skipped" />
          </el-select>
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input v-model="materialDialog.form.content" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="materialDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="materialDialog.saving" @click="saveMaterial">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分段编辑对话框 -->
    <el-dialog v-model="segmentsEditor.visible" title="编辑稿件分段" width="900px" top="5vh">
      <div class="segments-editor">
        <div v-for="(seg, idx) in segmentsEditor.segments" :key="idx" class="segment-item">
          <div class="segment-header">
            <span class="segment-seq">#{{ idx + 1 }}</span>
            <el-input v-model="seg.title" placeholder="段标题" class="segment-title" />
            <el-button size="small" type="danger" :icon="Delete" circle @click="removeSegment(idx)" />
          </div>
          <el-input v-model="seg.content" type="textarea" :rows="4" placeholder="段正文" />
        </div>
        <el-button :icon="Plus" @click="addSegment" class="add-segment">新增分段</el-button>
      </div>
      <template #footer>
        <el-button @click="segmentsEditor.visible = false">取消</el-button>
        <el-button type="primary" :loading="segmentsEditor.saving" @click="saveSegments">保存</el-button>
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
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, RefreshRight, Plus, Edit, Delete, Refresh } from '@element-plus/icons-vue'
import api from '../../api'
import { subscribe } from '../../utils/sse'
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

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const retrying = ref(false)
const detail = ref({})
const retryStep = ref('')

const STEP_ORDER = ['crawl', 'rewrite', 'tts', 'stitch', 'review']
const STEP_LABEL_MAP = {
  crawl: '爬虫采集',
  rewrite: 'LLM改写',
  tts: '语音合成',
  stitch: '音频拼接',
  review: '创建审核',
}
const STEP_EL_STATUS_MAP = {
  success: 'success', failed: 'error', running: 'process',
  pending: 'wait', retrying: 'process',
}
const STEP_STATUS_TEXT = {
  pending: '等待中', running: '运行中', success: '成功',
  retrying: '重试中', failed: '失败',
}
const STEP_TAG_TYPE_MAP = {
  success: 'success', failed: 'danger', running: 'warning',
  pending: 'info', retrying: 'warning',
}
const STATUS_TAG_MAP = {
  running: 'warning', success: 'success', failed: 'danger', cancelled: 'info', queued: 'info',
}
const STATUS_LABEL_MAP = {
  running: '运行中', success: '成功', failed: '失败', cancelled: '已取消', queued: '排队中',
}

function statusTagType(s) { return STATUS_TAG_MAP[s] || 'info' }
function statusLabel(s) { return STATUS_LABEL_MAP[s] || s }
function sourceLabel(s) { return s === 'cron' ? '定时' : s === 'manual' ? '手动' : s || '-' }
function stepLabel(name) { return STEP_LABEL_MAP[name] || name }
function stepElStatus(s) { return STEP_EL_STATUS_MAP[s] || 'wait' }
function stepStatusText(s) { return STEP_STATUS_TEXT[s] || s }
function stepTagType(s) { return STEP_TAG_TYPE_MAP[s] || 'info' }

const orderedSteps = computed(() => {
  const steps = detail.value.steps || []
  return STEP_ORDER.map((name) => steps.find((s) => s.name === name) || { name, status: 'pending' })
})

const activeStep = computed(() => {
  const idx = orderedSteps.value.findIndex((s) => s.status !== 'success')
  return idx === -1 ? orderedSteps.value.length : idx
})

function formatDuration(row) {
  if (!row?.started_at || !row?.finished_at) return '-'
  const ms = new Date(row.finished_at).getTime() - new Date(row.started_at).getTime()
  if (Number.isNaN(ms) || ms < 0) return '-'
  return (ms / 1000).toFixed(1)
}

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await api.get(`/workflows/${route.params.id}`)
    // 根据最新状态启停轮询：工作流非终态时启动，终态时停止
    startPollingIfNeeded()
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
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
    const data = await listMaterials(route.params.id, materialsPage.value)
    materials.value.list = data.list || []
    materials.value.total = data.total || 0
  } catch { /* 拦截器已提示 */ } finally {
    materials.value.loading = false
  }
}

const MATERIAL_STATUS_MAP = {
  pending: { label: '待处理', type: 'info' },
  selected: { label: '已选中', type: 'success' },
  skipped: { label: '已跳过', type: 'warning' },
}
function materialStatusLabel(s) { return MATERIAL_STATUS_MAP[s]?.label || s }
function materialStatusType(s) { return MATERIAL_STATUS_MAP[s]?.type || 'info' }

const materialDialog = ref({
  visible: false, id: null, saving: false,
  form: { title: '', source: '', url: '', category: '', status: 'pending', content: '' },
})

function openMaterialDialog(material = null) {
  if (material) {
    materialDialog.value = {
      visible: true, id: material.id, saving: false,
      form: { title: material.title, source: material.source, url: material.url,
        category: material.category || '', status: material.status || 'pending', content: '' },
    }
    // 编辑时拉取全文
    getMaterial(material.id).then((data) => {
      materialDialog.value.form.content = data.content || ''
    })
  } else {
    materialDialog.value = {
      visible: true, id: null, saving: false,
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
      await createMaterial({ ...f, workflow_id: route.params.id })
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
    ElMessageBox.alert(
      `<div style="max-height:60vh;overflow:auto"><h4>${data.title}</h4><p style="color:#999;font-size:12px">来源: ${data.source} | 品类: ${data.category || '-'}</p><div style="white-space:pre-wrap;margin-top:12px">${data.content}</div></div>`,
      '素材详情',
      { dangerouslyUseHTMLString: true, customClass: 'material-detail-dialog' },
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
async function ensureTtsBlob(row) {
  if (row.blobUrl) return
  row.loading = true
  try {
    row.blobUrl = await getTtsAudioUrl(route.params.id, row.name)
  } catch (err) {
    // blob 请求为 silent，需手动提示
    ElMessage.error(err.message || '音频加载失败')
  } finally {
    row.loading = false
  }
}

// 按需加载成品音频 blob URL
async function ensureEpisodeBlob() {
  if (episodePlayer.value.blobUrl) return
  episodePlayer.value.loading = true
  try {
    episodePlayer.value.blobUrl = await getEpisodeAudioUrl(route.params.id)
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

const REVIEW_STATUS_MAP = {
  pending: { label: '待审核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已打回', type: 'danger' },
  replaced: { label: '已替换', type: 'info' },
}
function reviewStatusLabel(s) { return REVIEW_STATUS_MAP[s]?.label || s }
function reviewStatusType(s) { return REVIEW_STATUS_MAP[s]?.type || 'info' }

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
      loadDetail()
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
    pollTimer = setInterval(() => {
      if (!document.hidden) loadDetail()
    }, 5000)
  }
}

// 页面恢复可见时刷新：弥补隐藏期间错过的 SSE 事件
// 根因：页面最小化时浏览器暂停 CSS transition，v-loading mask 的 after-leave
// 回调不触发，DOM 残留；恢复可见时 loading 已是 false，赋值 false 不触发 Vue 更新
// 修复：强制 toggle（true→nextTick→false）触发 v-loading update 清理残留 mask，
// 配合 themes.scss 中 .el-loading-mask transition:none 让 mask 移除变为同步操作
function handleVisibilityChange() {
  if (!document.hidden) {
    // 强制设 true，触发 v-loading 指令 update 钩子（即使之前是 true 也无副作用）
    loading.value = true
    materials.value.loading = true
    audioFiles.value.loading = true
    script.value.loading = true
    review.value.loading = true
    // nextTick 让 Vue 处理 loading=true 的 DOM 更新（创建/复用 mask）
    nextTick(() => {
      // 设 false 触发 mask 隐藏（transition 已禁用，同步移除 DOM）
      loading.value = false
      materials.value.loading = false
      audioFiles.value.loading = false
      script.value.loading = false
      review.value.loading = false
      // rAF 等待浏览器完成一次真实 paint 后再加载新数据
      requestAnimationFrame(() => {
        loadDetail()
        startPollingIfNeeded()
      })
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
