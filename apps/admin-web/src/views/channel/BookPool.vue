<template>
  <div class="book-pool">
    <!-- 顶部：频道选择 + 讲书稿模式开关 -->
    <el-card shadow="never">
      <template #header>
        <div class="page-header">
          <span class="page-title">讲书稿素材池</span>
          <div class="header-right">
            <el-select
              v-model="channelId"
              placeholder="选择频道"
              filterable
              style="width: 260px"
              @change="onChannelChange"
            >
              <el-option
                v-for="c in channels"
                :key="c.id"
                :label="`${c.name}（${typeLabel(c.channel_type)}）`"
                :value="c.id"
              />
            </el-select>
            <el-switch
              v-model="scriptMode"
              :loading="modeLoading"
              :disabled="!channelId"
              active-text="讲书稿模式"
              inline-prompt
              style="margin-left: 16px"
              @change="onToggleMode"
            />
          </div>
        </div>
      </template>

      <el-alert v-if="!channelId" type="info" :closable="false" show-icon
        title="请先选择频道：讲书稿模式按频道独立配置（素材池、排序与进度都属于所选频道）" />
      <template v-else>
        <el-alert
          v-if="state.enabled"
          type="success"
          :closable="false"
          show-icon
          title="讲书稿模式已开启：内容不再来自频道书源，改为按下方顺序逐日取书"
        >
          <template #default>
            <div class="alert-body">
              已清除频道书源（快照已保存，关闭开关即恢复）——
              当前书源：RSS {{ (state.rss_sources || []).length }} 个 / 书籍源 {{ (state.book_rss_sources || []).length }} 个（均为空属预期）。
            </div>
          </template>
        </el-alert>
        <el-alert
          v-else
          type="info"
          :closable="false"
          show-icon
          title="当前为常规模式：内容来自频道书源；开启讲书稿模式后将自动清空频道书源并改从素材池取书"
        />
      </template>
    </el-card>

    <!-- 调度与进度 -->
    <el-card v-if="channelId" shadow="never" style="margin-top: 12px">
      <template #header><span class="card-title">调度与进度</span></template>
      <el-form :inline="true" label-width="90px">
        <el-form-item label="取书间隔">
          <el-input-number v-model="schedule.interval_days" :min="1" :max="365" controls-position="right" @change="onScheduleChange" />
          <span class="unit-hint">天（1 = 每日）</span>
        </el-form-item>
        <el-form-item label="末尾处理">
          <el-switch v-model="schedule.loop" active-text="循环" inactive-text="停止" inline-prompt @change="onScheduleChange" />
        </el-form-item>
        <el-form-item label="进度">
          <el-tag type="info">已取 {{ state.cursor || 0 }} / 共 {{ state.pool_total || 0 }} 本</el-tag>
          <span v-if="state.last_title" class="unit-hint">上次：《{{ state.last_title }}》{{ state.last_run_date ? '（' + state.last_run_date + '）' : '' }}</span>
        </el-form-item>
        <el-form-item>
          <el-button :loading="previewLoading" @click="onPreview">预览下次生成</el-button>
          <el-button type="warning" plain @click="onResetProgress">重置进度</el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="preview" :type="previewType" :closable="false" show-icon :title="previewText" />
    </el-card>

    <!-- 池列表 -->
    <el-card v-if="channelId" shadow="never" style="margin-top: 12px">
      <template #header>
        <div class="page-header">
          <span class="card-title">书单（顺序即取书顺序）</span>
          <el-button type="primary" size="small" @click="openCandidates">从素材库加入</el-button>
        </div>
      </template>
      <el-table :data="items" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="顺序" width="80">
          <template #default="{ $index }">
            <el-tag v-if="!state.enabled ? false : $index === state.cursor" type="success" size="small">下一本</el-tag>
            <span v-else>{{ $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="书名" min-width="240" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column label="素材 ID" width="100">
          <template #default="{ row }">
            <el-link type="primary" :href="materialLink(row.material_id)" target="_blank">{{ row.material_id }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row, $index }">
            <el-button size="small" :disabled="$index === 0" @click="onMove(row, 'up')">上移</el-button>
            <el-button size="small" :disabled="$index === items.length - 1" @click="onMove(row, 'down')">下移</el-button>
            <el-button size="small" type="danger" plain @click="onRemove(row)">移出</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="书单为空——点击右上角「从素材库加入」，加入的书籍将按从上到下的顺序逐日生成讲书稿" :image-size="90" />
        </template>
      </el-table>
      <div class="tips">
        顺序 = 取书顺序：讲解完一本后进度自动 +1（**在节目发布成功后**推进，失败重跑不会丢书）。
        一本书的多章素材需在「素材录入」上传 EPUB/DOCX 并选择本频道，上传时把「来源」填为书名可自动聚合全书章节。
      </div>
    </el-card>

    <!-- 候选加入弹窗 -->
    <el-dialog v-model="candidatesVisible" title="从素材库加入书籍" width="820px">
      <el-form :inline="true">
        <el-form-item label="关键词">
          <el-input v-model="candidateKeyword" placeholder="按书名搜索" clearable style="width: 240px" @keyup.enter="loadCandidates" />
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
        <el-table-column prop="title" label="书名 / 素材标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column prop="source" label="来源" width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.in_pool" type="info" size="small">已在书单</el-tag>
            <el-tag v-else size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <template #empty><el-empty description="没有匹配的素材（可换关键词）" :image-size="80" /></template>
      </el-table>
      <template #footer>
        <span class="dialog-footer">
          已选 {{ selectedCandidates.length }} 本
          <el-button @click="candidatesVisible = false">取消</el-button>
          <el-button type="primary" :disabled="!selectedCandidates.length" :loading="adding" @click="onAddSelected">加入书单</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 讲书稿素材池（T00656）
 *
 * 职责：
 * - 讲书稿模式开关（开启自动清空频道书源并保存快照；关闭恢复）——幂等；
 * - 素材池管理：从素材库选书加入、上移/下移排序、移出；
 * - 调度与进度：取书间隔（每日/每 N 天）、末尾循环/停止、进度查看与重置、下次生成预览。
 *
 * 设计说明：排序即取书顺序；进度在**节目发布成功后**由后端推进，故本页只读展示 + 手动重置。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listChannels } from '../../api/channels'
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

const route = useRoute()
const TYPE_LABELS = { news: '资讯', course: '课程', audiobook: '有声读物' }
const typeLabel = (t) => TYPE_LABELS[t] || t || '资讯'

const channels = ref([])
const channelId = ref(null)
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
const candidateTable = ref(null)
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

function materialLink(id) {
  return `/materials?highlight=${id}`
}

async function loadChannels() {
  channels.value = await listChannels()
  const qid = Number(route.query.channelId)
  if (qid) {
    channelId.value = qid
  } else {
    const preferred = channels.value.find((c) => c.channel_type === 'audiobook') || channels.value[0]
    channelId.value = preferred ? preferred.id : null
  }
  if (channelId.value) await loadAll()
}

async function loadAll() {
  await Promise.all([loadState(), loadPool()])
}

async function loadState() {
  const data = await getScriptMode(channelId.value)
  Object.assign(state, data || {})
  scriptMode.value = !!state.enabled
  schedule.interval_days = state.interval_days || 1
  schedule.loop = !!state.loop
}

async function loadPool() {
  loading.value = true
  try {
    const data = await listBookPool(channelId.value)
    items.value = data?.items || []
    if (data?.state) {
      Object.assign(state, data.state)
      scriptMode.value = !!state.enabled
    }
  } finally {
    loading.value = false
  }
}

async function onChannelChange() {
  preview.value = null
  await loadAll()
}

async function onToggleMode(val) {
  modeLoading.value = true
  try {
    const res = await setScriptMode(channelId.value, val)
    ElMessage[res?.changed ? 'success' : 'info'](res?.message || (val ? '已开启讲书稿模式' : '已关闭讲书稿模式'))
    await loadAll()
  } catch (e) {
    scriptMode.value = !val // 失败回滚开关显示，避免"显示开启但实际未生效"
  } finally {
    modeLoading.value = false
  }
}

async function onScheduleChange() {
  const res = await updateBookPoolSchedule(channelId.value, {
    interval_days: schedule.interval_days,
    loop: schedule.loop,
  })
  Object.assign(state, res || {})
  ElMessage.success('调度参数已保存')
}

async function onPreview() {
  previewLoading.value = true
  try {
    preview.value = await previewNextBook(channelId.value)
  } finally {
    previewLoading.value = false
  }
}

async function onResetProgress() {
  await ElMessageBox.confirm('重置后将从书单第一本重新开始（书单与排序保留），确定继续？', '重置进度', { type: 'warning' })
  const res = await resetBookPoolProgress(channelId.value)
  Object.assign(state, res || {})
  preview.value = null
  ElMessage.success('进度已重置')
}

async function onMove(row, direction) {
  const data = await moveBookInPool(channelId.value, row.id, direction)
  items.value = data?.items || items.value
}

async function onRemove(row) {
  await ElMessageBox.confirm(`确定把《${row.title}》移出书单？（素材库中的素材不受影响）`, '移出书单', { type: 'warning' })
  const data = await removeBookFromPool(channelId.value, row.id)
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
    const data = await listBookCandidates(channelId.value, {
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
    const res = await addBooksToPool(channelId.value, selectedCandidates.value.map((r) => r.material_id))
    ElMessage.success(res?.message || '已加入书单')
    candidatesVisible.value = false
    await loadAll()
  } finally {
    adding.value = false
  }
}

onMounted(loadChannels)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-right {
  display: flex;
  align-items: center;
}
.page-title {
  font-weight: 600;
}
.card-title {
  font-weight: 600;
}
.alert-body {
  margin-top: 4px;
  font-size: 13px;
}
.unit-hint {
  margin-left: 8px;
  color: #909399;
  font-size: 13px;
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
