<template>
  <div class="book-pool-panel">
    <!-- 讲书稿模式开关 + 状态提示 -->
    <el-alert
      v-if="state.enabled"
      type="success"
      :closable="false"
      show-icon
      title="讲书稿模式已开启：内容来自本素材池（按书单顺序逐日取书）"
    >
      <template #default>
        <div class="alert-body">
          频道书源已停用（配置保留、编辑页中灰显）——
          当前 RSS 源 {{ (state.rss_sources || []).length }} 个 / 书籍源 {{ (state.book_rss_sources || []).length }} 个。
        </div>
      </template>
    </el-alert>
    <el-alert
      v-else
      type="info"
      :closable="false"
      show-icon
      title="讲书稿模式未开启：当前内容来自频道书源；开启后忽略书源、改按下方书单顺序逐日取书"
    />

    <!-- 调度与进度 -->
    <el-form :inline="true" class="schedule-form" label-width="90px">
      <el-form-item label="取书间隔">
        <el-input-number v-model="schedule.interval_days" :min="1" :max="365" controls-position="right" @change="onScheduleChange" />
        <span class="unit-hint">天（1 = 每日）</span>
      </el-form-item>
      <el-form-item label="末尾处理">
        <el-switch v-model="schedule.loop" active-text="循环" inactive-text="停止" inline-prompt @change="onScheduleChange" />
      </el-form-item>
      <el-form-item label="进度">
        <el-tag type="info">已取 {{ state.cursor || 0 }} / 共 {{ state.pool_total || 0 }} 本</el-tag>
        <span v-if="state.last_title" class="unit-hint">
          上次：《{{ state.last_title }}》{{ state.last_run_date ? '（' + state.last_run_date + '）' : '' }}
        </span>
      </el-form-item>
      <el-form-item>
        <el-button :loading="previewLoading" @click="onPreview">预览下次生成</el-button>
        <el-button type="warning" plain @click="onResetProgress">重置进度</el-button>
      </el-form-item>
    </el-form>
    <el-alert v-if="preview" :type="previewType" :closable="false" show-icon :title="previewText" />

    <!-- 书单（顺序即取书顺序） -->
    <div class="pool-header">
      <span class="pool-title">书单（顺序即取书顺序）</span>
      <el-button type="primary" size="small" @click="openCandidates">从素材库加入</el-button>
    </div>
    <el-table :data="items" v-loading="loading" stripe style="width: 100%">
      <el-table-column label="顺序" width="86">
        <template #default="{ $index }">
          <el-tag v-if="state.enabled && $index === state.cursor" type="success" size="small">下一本</el-tag>
          <span v-else>{{ $index + 1 }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="书名" min-width="220" show-overflow-tooltip />
      <el-table-column prop="category" label="分类" width="110" />
      <el-table-column label="素材 ID" width="96">
        <template #default="{ row }">
          <el-link type="primary" :href="`/materials?highlight=${row.material_id}`" target="_blank">
            {{ row.material_id }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row, $index }">
          <el-button size="small" :disabled="$index === 0" @click="onMove(row, 'up')">上移</el-button>
          <el-button size="small" :disabled="$index === items.length - 1" @click="onMove(row, 'down')">下移</el-button>
          <el-button size="small" type="danger" plain @click="onRemove(row)">移出</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty
          description="书单为空——点击右上角「从素材库加入」，整本书加入后按从上到下的顺序逐日生成讲书稿"
          :image-size="90"
        />
      </template>
    </el-table>
    <div class="tips">
      整本书以「书」为单位加入书单（章节素材按来源自动聚合）。
      讲解完一本后进度自动 +1（**在节目发布成功后**推进，失败重跑不会丢书）。
      新书素材请到「素材录入」上传 EPUB/DOCX 并选择本频道——后端会自动把「来源」写为书名，无需手动维护。
    </div>

    <!-- 候选加入弹窗（按书聚合） -->
    <el-dialog v-model="candidatesVisible" title="从素材库加入书籍（按书聚合）" width="780px" append-to-body>
      <el-form :inline="true">
        <el-form-item label="关键词">
          <el-input
            v-model="candidateKeyword"
            placeholder="按书名搜索"
            clearable
            style="width: 240px"
            @keyup.enter="loadCandidates"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="candidatesLoading" @click="loadCandidates">搜索</el-button>
        </el-form-item>
      </el-form>
      <el-table
        ref="candidateTable"
        :data="candidates"
        v-loading="candidatesLoading"
        height="380"
        @selection-change="onCandidateSelect"
      >
        <el-table-column type="selection" width="46" :selectable="(row) => !row.in_pool" />
        <el-table-column prop="title" label="书名" min-width="240" show-overflow-tooltip />
        <el-table-column label="章节" width="90">
          <template #default="{ row }">{{ row.chapters }} 章（待讲 {{ row.pending_chapters }}）</template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.in_pool" type="info" size="small">已在书单</el-tag>
            <el-tag v-else type="success" size="small">可加入</el-tag>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty
            description="没有可加入的书——请先到「素材录入」上传 EPUB/DOCX（来源会自动记为书名）"
            :image-size="80"
          />
        </template>
      </el-table>
      <template #footer>
        <div class="dialog-footer">
          <span>已选 {{ selectedCandidates.length }} 本</span>
          <el-button @click="candidatesVisible = false">取消</el-button>
          <el-button type="primary" :disabled="!selectedCandidates.length" :loading="adding" @click="onAddSelected">
            加入书单
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 讲书稿素材池面板（T00656，用户反馈改造）
 *
 * 一处实现，两处映射：频道编辑弹窗（数据源配置下方「讲书稿素材池」链接弹出）
 * 与「讲书稿素材池」独立页共用本组件——保证书单/排序/进度状态一致。
 *
 * 职责：
 * - 讲书稿模式开关（幂等；开启后编辑页的书源输入灰显，真正的采集隔离在 crawler 行为层）；
 * - 书单管理：从素材库按**书**加入（book_key=素材 source，整本入池）、上移/下移、移出；
 * - 调度与进度：取书间隔、末尾循环、进度展示与重置、下次生成预览（只读）。
 */
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import {
  addBooksToPool,
  getScriptMode,
  listBookCandidates,
  listBookPool,
  moveBookInPool,
  previewNextBook,
  removeBookFromPool,
  resetBookPoolProgress,
  setScriptMode,
  updateBookPoolSchedule,
} from '../../api/bookPool'

const props = defineProps({
  channelId: { type: Number, required: true },
})

const loading = ref(false)
const items = ref([])
const state = reactive({
  enabled: false, cursor: 0, pool_total: 0, interval_days: 1, loop: false,
  last_run_date: null, last_title: null, rss_sources: [], book_rss_sources: [],
})
const schedule = reactive({ interval_days: 1, loop: false })
const scriptMode = ref(false)
const modeLoading = ref(false)
const preview = ref(null)
const previewLoading = ref(false)

// 候选弹窗
const candidatesVisible = ref(false)
const candidates = ref([])
const candidatesLoading = ref(false)
const candidateKeyword = ref('')
const selectedCandidates = ref([])
const adding = ref(false)

const previewType = computed(() => {
  if (!preview.value) return 'info'
  return { ok: 'success', not_due: 'warning', empty: 'warning', exhausted: 'warning' }[preview.value.status] || 'info'
})
const previewText = computed(() => {
  const p = preview.value
  if (!p) return ''
  if (p.status === 'ok') {
    return `下次将生成：《${(p.item || {}).title}》（书单第 ${(p.cursor ?? 0) + 1} 本 / 共 ${p.total} 本）`
  }
  if (p.status === 'not_due') return `未到取书间隔：上次 ${p.last_run_date}，下次 ${p.next_due_date}（间隔 ${p.interval_days} 天）`
  if (p.status === 'empty') return '书单为空：请先加入书籍'
  if (p.status === 'exhausted') return `已到书单末尾（${p.cursor}/${p.total}）且未开启循环——可开启「末尾处理 → 循环」或重置进度`
  return `取书状态：${p.status}`
})

watch(() => props.channelId, () => loadAll(), { immediate: true })

async function loadAll() {
  if (!props.channelId) return
  await Promise.all([loadState(), loadPool()])
}

async function loadState() {
  const data = await getScriptMode(props.channelId)
  Object.assign(state, data || {})
  scriptMode.value = !!state.enabled
  schedule.interval_days = state.interval_days || 1
  schedule.loop = !!state.loop
}

async function loadPool() {
  loading.value = true
  try {
    const data = await listBookPool(props.channelId)
    items.value = data?.items || []
    if (data?.state) {
      Object.assign(state, data.state)
      scriptMode.value = !!state.enabled
    }
  } finally {
    loading.value = false
  }
}

async function onToggleMode(val) {
  modeLoading.value = true
  try {
    const res = await setScriptMode(props.channelId, val)
    scriptMode.value = !!res?.enabled
    ElMessage[res?.changed ? 'success' : 'info'](res?.message || (val ? '已开启讲书稿模式' : '已关闭讲书稿模式'))
    await loadAll()
  } catch (e) {
    scriptMode.value = !val // 失败回滚开关显示，避免"显示开启但实际未生效"
  } finally {
    modeLoading.value = false
  }
}

async function onScheduleChange() {
  const res = await updateBookPoolSchedule(props.channelId, {
    interval_days: schedule.interval_days,
    loop: schedule.loop,
  })
  Object.assign(state, res || {})
  ElMessage.success('调度参数已保存')
}

async function onPreview() {
  previewLoading.value = true
  try {
    preview.value = await previewNextBook(props.channelId)
  } finally {
    previewLoading.value = false
  }
}

async function onResetProgress() {
  await ElMessageBox.confirm('重置后将从书单第一本重新开始（书单与排序保留），确定继续？', '重置进度', { type: 'warning' })
  const res = await resetBookPoolProgress(props.channelId)
  Object.assign(state, res || {})
  preview.value = null
  ElMessage.success('进度已重置')
}

async function onMove(row, direction) {
  const data = await moveBookInPool(props.channelId, row.id, direction)
  items.value = data?.items || items.value
}

async function onRemove(row) {
  await ElMessageBox.confirm(`确定把《${row.title}》移出书单？（素材库中的素材不受影响）`, '移出书单', { type: 'warning' })
  const data = await removeBookFromPool(props.channelId, row.id)
  items.value = data?.items || []
  await loadState()
  ElMessage.success('已移出书单')
}

function openCandidates() {
  candidatesVisible.value = true
  candidateKeyword.value = ''
  loadCandidates()
}

async function loadCandidates() {
  candidatesLoading.value = true
  try {
    const data = await listBookCandidates(props.channelId, {
      keyword: candidateKeyword.value || undefined,
      page: 1,
      size: 50,
    })
    candidates.value = data?.items || []
  } finally {
    candidatesLoading.value = false
  }
}

function onCandidateSelect(rows) {
  selectedCandidates.value = rows
}

async function onAddSelected() {
  adding.value = true
  try {
    const res = await addBooksToPool(props.channelId, selectedCandidates.value.map((r) => r.book_key))
    ElMessage.success(res?.message || '已加入书单')
    candidatesVisible.value = false
    await loadAll()
  } finally {
    adding.value = false
  }
}
</script>

<style scoped>
.alert-body {
  margin-top: 4px;
  font-size: 13px;
}
.schedule-form {
  margin-bottom: 4px;
}
.unit-hint {
  margin-left: 8px;
  color: #909399;
  font-size: 13px;
}
.pool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 8px 0;
}
.pool-title {
  font-weight: 600;
}
.tips {
  margin-top: 10px;
  color: #909399;
  font-size: 12px;
  line-height: 1.7;
}
.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
</style>
