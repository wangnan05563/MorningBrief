<template>
  <div class="book-pool-panel">
    <!-- C73（FR-UX-302）：加载失败时页内错误态优先展示。同时把下面所有「会声称一件事实」的块
         撤下——失败态里它们只会显示复位后的 false / 0，等于把「接口挂了」说成
         「模式未开启、共 0 本」，正是本批缺陷的母题。 -->
    <ListLoadError
      v-if="poolError"
      :message="poolError"
      :retrying="poolRetrying"
      @retry="retryLoadAll"
    />

    <!-- 讲书稿模式开关 + 状态提示 -->
    <el-alert
      v-if="!poolError && state.enabled"
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
      v-else-if="!poolError"
      type="info"
      :closable="false"
      show-icon
      title="讲书稿模式未开启：当前内容来自频道书源；开启后忽略书源、改按下方书单顺序逐日取书"
    />

    <!-- 调度与进度 -->
    <el-form v-if="!poolError" :inline="true" class="schedule-form" label-width="90px">
      <!-- C27（FR-UX-704）：这里此前只有「模式状态」提示，开关却不在本组件里——
           独立页 /channels/book-pool 根本没有开关可用，频道编辑弹窗内则只在另一个页签里有开关，
           于是出现「同屏两处与模式相关的提示、只有一处能操作」。onToggleMode 早已写好并接了 API，
           只是没有任何控件绑定它（死代码）。补上开关，两个使用方都可直接操作同一份后端状态。 -->
      <el-form-item label="讲书稿模式">
        <el-switch
          v-model="scriptMode"
          :loading="modeLoading"
          active-text="开启"
          inactive-text="关闭"
          inline-prompt
          data-guide="book-pool-mode-switch"
          @change="onToggleMode"
        />
        <span class="unit-hint">开启后忽略书源、按下方书单顺序逐日取书</span>
      </el-form-item>
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
        <IconButton :loading="previewLoading" :icon="View" label="预览下次生成" desc="预览下次将取哪本书" @click="onPreview" />
        <IconButton type="warning" plain :icon="RefreshLeft" label="重置进度" desc="重置进度，从书单第一本重新开始" @click="onResetProgress" />
      </el-form-item>
    </el-form>
    <el-alert v-if="preview" :type="previewType" :closable="false" show-icon :title="previewText" />

    <!-- 书单（顺序即取书顺序） -->
    <div class="pool-header">
      <span class="pool-title">书单（顺序即取书顺序）</span>
      <IconButton type="primary" size="small" :icon="Plus" label="从素材库加入" desc="从素材库按书聚合选择加入书单" @click="openCandidates" />
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
          <!-- T00775：原 href="/materials?highlight=id" 指向「素材录入」页且不处理 highlight（生产还缺 /news 前缀）
               ——改为路由跳转到「素材库管理」并按素材 ID 定位。 -->
          <el-link type="primary" @click="goMaterial(row)">{{ row.material_id || '-' }}</el-link>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row, $index }">
          <IconButton size="small" :disabled="$index === 0" :icon="ArrowUp" label="上移" desc="在书单中上移该条目" @click="onMove(row, 'up')" />
          <IconButton size="small" :disabled="$index === items.length - 1" :icon="ArrowDown" label="下移" desc="在书单中下移该条目" @click="onMove(row, 'down')" />
          <IconButton size="small" type="danger" plain :icon="Delete" label="移出" desc="将该书移出书单" @click="onRemove(row)" />
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
            @keyup.enter="onCandidateSearch"
          />
        </el-form-item>
        <el-form-item>
          <IconButton type="primary" :loading="candidatesLoading" :icon="Search" label="搜索" desc="按书名搜索可加入的书籍" @click="onCandidateSearch" />
          <!-- T00716：素材库管理入口（增删改查在「素材库管理」页） -->
          <el-link type="primary" style="margin-left: 12px" @click="goLibrary">管理素材 ↗</el-link>
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
      <!-- C84：候选此前固定 page:1、size:50，后端返回的 total 被丢弃，界面既无翻页控件
           也不显示总数——本频道书多于 50 本时，第 51 本起「不存在」，运营会判定素材库里没有这本书。 -->
      <div class="candidate-pager">
        <span class="candidate-total">本频道共 {{ candidateTotal }} 本书可加入</span>
        <el-pagination
          v-model:current-page="candidatePage"
          v-model:page-size="candidateSize"
          :total="candidateTotal"
          :page-sizes="PANEL_PAGE_SIZE_OPTIONS"
          layout="sizes, prev, pager, next"
          size="small"
          background
          @current-change="loadCandidates"
          @size-change="onCandidateSizeChange"
        />
      </div>
      <template #footer>
        <div class="dialog-footer">
          <span>已选 {{ selectedCandidates.length }} 本</span>
          <IconButton :icon="Close" label="取消" desc="关闭弹窗" @click="candidatesVisible = false" />
          <IconButton type="primary" :disabled="!selectedCandidates.length" :loading="adding" :icon="Check" label="加入书单" desc="将选中的书加入书单" @click="onAddSelected" />
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
import { useRouter } from 'vue-router'
import { View, RefreshLeft, Plus, ArrowUp, ArrowDown, Delete, Search, Close, Check } from '@element-plus/icons-vue'
import { ElMessage } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import ListLoadError from '../../components/ListLoadError.vue'
// C84：候选分页页长档位与素材库面板共用同一常量
import { PANEL_PAGE_SIZE_OPTIONS } from '../../constants/pagination'
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

const router = useRouter()

const props = defineProps({
  channelId: { type: Number, required: true },
})

const loading = ref(false)
// C73（FR-UX-302）：两个 loader 的失败聚合进同一条页内错误态，重试走完整 loadAll。
const poolError = ref('')
const poolRetrying = ref(false)
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
// C84：候选分页态（此前固定 page:1/size:50，第 51 本起在界面上「不存在」）
const candidatePage = ref(1)
const candidateSize = ref(20)
const candidateTotal = ref(0)
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
  // C73（FR-UX-302）：切频道**先清残留再拉**。此前两个 loader 一个连 try 都没有、
  // 一个只 try/finally 无 catch，请求失败时 state/items 原样保留上一个频道的值，
  // 界面继续显示「已取 X / 共 Y 本 · 上次《Z》」——那是**别的频道**的进度，
  // 比显示空态更危险（空态至少不会让人把 A 频道当成 B 频道）。
  resetPoolView()
  const errors = []
  await Promise.all([loadState(errors), loadPool(errors)])
  poolError.value = errors.length ? `讲书稿书单/进度未能加载：${errors.join('；')}` : ''
}

// C73：失败态复位。只清「会被误读成当前频道数据」的展示字段，不动弹窗一类的交互态。
function resetPoolView() {
  Object.assign(state, {
    enabled: false, cursor: 0, pool_total: 0, interval_days: 1, loop: false,
    last_run_date: null, last_title: null, rss_sources: [], book_rss_sources: [],
  })
  items.value = []
  scriptMode.value = false
  schedule.interval_days = 1
  schedule.loop = false
  preview.value = null
}

async function loadState(errors) {
  try {
    const data = await getScriptMode(props.channelId)
    Object.assign(state, data || {})
    scriptMode.value = !!state.enabled
    schedule.interval_days = state.interval_days || 1
    schedule.loop = !!state.loop
  } catch (e) {
    // 交给 loadAll 聚合到页内错误态；单个 loader 不各自弹 toast（FR-UX-303 单一出口）
    errors?.push(e?.message || '取书状态接口失败')
  }
}

async function loadPool(errors) {
  loading.value = true
  try {
    const data = await listBookPool(props.channelId)
    items.value = data?.items || []
    if (data?.state) {
      Object.assign(state, data.state)
      scriptMode.value = !!state.enabled
    }
    // C80（FR-UX-704）：池子内容一变，「预览下次生成」的结果就过期了。
    // 此前预览是一次性 POST 且结果常驻显示，此后任何排序/加入/移出都不让它失效，
    // 用户看到的「下次将生成《X》」可能早已不成立——属于典型的数据被误读。
    preview.value = null
  } catch (e) {
    errors?.push(e?.message || '书单接口失败')
  } finally {
    loading.value = false
  }
}

// C73：重试重新拉「取书状态 + 书单」两份数据——只补其中一个，另一个还是旧的
function retryLoadAll() {
  poolRetrying.value = true
  return loadAll().finally(() => {
    poolRetrying.value = false
  })
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
  // C80：间隔/循环直接影响「下次是否取书、取哪本」，改完必须让旧预览作废
  preview.value = null
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
  const ok = await dangerConfirm({
    action: '重置书单进度',
    target: `频道 ID ${props.channelId} 的讲书稿书单（共 ${items.value.length} 本）`,
    scope: '取书进度 1 项（复位到书单第 1 本；书单与排序保留）',
    lines: ['下一次生成会从第 1 本重新开始。'],
    irreversible: '重置后原来的取书位置不会保留，无法撤销。',
    confirmLabel: '确认重置',
  })
  if (!ok) return
  const res = await resetBookPoolProgress(props.channelId)
  Object.assign(state, res || {})
  preview.value = null
  ElMessage.success('进度已重置')
}

async function onMove(row, direction) {
  const data = await moveBookInPool(props.channelId, row.id, direction)
  items.value = data?.items || items.value
  // C80：顺序即取书顺序，挪动一格就可能换一本「下次生成」
  preview.value = null
}

async function onRemove(row) {
  const ok = await dangerConfirm({
    action: '移出书单',
    target: `《${row.title}》`,
    scope: `书单条目 1 条（${items.value.length} 本 → ${Math.max(items.value.length - 1, 0)} 本）`,
    lines: ['素材库中的素材不受影响；再次加入需从候选书单重新选择。'],
    irreversible: '移出后书单顺序会重排，原来的位置需要手动恢复。',
    confirmLabel: '确认移出',
  })
  if (!ok) return
  const data = await removeBookFromPool(props.channelId, row.id)
  items.value = data?.items || []
  await loadState()
  // C80：移出后取书指针指向的书变了，旧预览不能继续挂着
  preview.value = null
  ElMessage.success('已移出书单')
}

function openCandidates() {
  candidatesVisible.value = true
  candidateKeyword.value = ''
  candidatePage.value = 1
  loadCandidates()
}

// C84：带上页码/页长，并把后端返回的 total 显示出来
// （此前固定 page:1、size:50，第 51 本起在界面上「不存在」）
async function loadCandidates() {
  candidatesLoading.value = true
  try {
    const data = await listBookCandidates(props.channelId, {
      keyword: candidateKeyword.value || undefined,
      page: candidatePage.value,
      size: candidateSize.value,
    })
    candidates.value = data?.items || []
    candidateTotal.value = data?.total || 0
  } finally {
    candidatesLoading.value = false
  }
}

// 换页长或按关键词重新搜索都要回到第 1 页，否则会停在越界的旧页码上看到空列表
function onCandidateSearch() {
  candidatePage.value = 1
  loadCandidates()
}

function onCandidateSizeChange() {
  candidatePage.value = 1
  loadCandidates()
}

function onCandidateSelect(rows) {
  selectedCandidates.value = rows
}

/** T00716：跳转「素材库管理」页（增删改查；携带当前频道便于筛选） */
function goLibrary() {
  // T00775：把弹窗里已输入的书名关键词一并带过去，跳转后直接命中该书的章节素材
  router.push({
    path: '/channels/material-library',
    query: { channelId: props.channelId, keyword: candidateKeyword.value || undefined },
  })
}

/** T00775：书单「素材 ID」→ 素材库管理页定位到该条素材（可编辑/删除） */
function goMaterial(row) {
  if (!row.material_id) {
    ElMessage.info('该书目尚无代表素材（书稿未上传）')
    return
  }
  router.push({
    path: '/channels/material-library',
    query: { channelId: props.channelId, materialId: row.material_id },
  })
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
/* C84：候选分页条（页长档位 + 总数） */
.candidate-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}
.candidate-total {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
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
