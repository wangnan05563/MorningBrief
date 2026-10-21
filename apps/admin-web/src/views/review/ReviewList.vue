<template>
  <div data-guide="review-page" class="review-list page-container" v-loading="loading">
    <el-tabs data-guide="review-tabs" v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="待审核" name="pending" />
      <el-tab-pane label="已通过" name="approved" />
      <el-tab-pane label="已打回" name="rejected" />
    </el-tabs>

    <!-- 地址栏带来的非法参数（如 ?tab=xxx / ?page=abc）已按默认值渲染，这里如实点名，
         不静默吞掉——用户分享链接后看到的数据与链接写明的不一致，必须可见（T02511） -->
    <el-alert
      v-if="invalidParams.length"
      data-guide="review-url-corrected"
      type="warning"
      :closable="false"
      show-icon
      :title="`链接里的参数已修正：${invalidParams.map((p) => p.key).join('、')}`"
      :description="invalidParams.map((p) => `${p.key}=${p.raw}（${p.reason}）`).join('；')"
    />

    <!-- T02517（FR-UX-703 / B4）：工作流 ID 筛选。后端 list_reviews 一直支持
         `workflow_id` 精确过滤（reviews.py:44），但界面上没有任何入口，
         定位某一条只能盲翻页。筛选条件跟着 URL 走（同 tab/page/size），
         刷新与分享都不会丢。审核人/日期/频道筛选后端尚无参数，未在此假装有。 -->
    <el-form :inline="true" class="filter-form" data-guide="review-filters">
      <el-form-item label="工作流 ID">
        <el-input
          v-model="filters.workflow_id"
          placeholder="按工作流 ID 精确定位"
          clearable
          style="width: 240px"
          @keyup.enter="onFilterSearch"
          @clear="onFilterSearch"
        />
      </el-form-item>
      <el-form-item>
        <IconButton
          type="primary"
          size="small"
          :loading="loading"
          :icon="Search"
          label="搜索"
          desc="按当前工作流 ID 查询审核记录"
          @click="onFilterSearch"
        />
        <IconButton
          size="small"
          :icon="RefreshLeft"
          label="重置"
          desc="清空工作流 ID 筛选"
          @click="onFilterReset"
        />
      </el-form-item>
    </el-form>

    <!-- T02517（B6）：加载失败必须上屏。此前空 catch 块只靠拦截器一条 toast，
         list/total 保持旧值既不清空也不标注，用户分不清「刷新失败但残留旧数据」与「正常」。
         已有旧数据时由 ListLoadError 的 stale 文案说明「下方是上次成功的数据」，
         绝不把它渲染成「暂无待审核稿件」。 -->
    <ListLoadError
      v-if="listError"
      :message="listError"
      :stale="list.length > 0"
      :retrying="loading"
      @retry="loadList"
    />

    <!-- 批量操作栏：仅在待审核 tab 显示，选中后才可操作 -->
    <div v-if="activeTab === 'pending'" class="batch-bar">
      <span class="batch-info" v-if="selectedRows.length > 0">
        已选 {{ selectedRows.length }} 条
      </span>
      <span class="batch-info" v-else>勾选下方记录后可批量操作</span>
      <div class="batch-actions">
        <IconButton
          type="success"
          size="small"
          :disabled="selectedRows.length === 0 || batchLoading"
          :loading="batchLoading && batchAction === 'approve'"
          :icon="Select"
          label="批量通过"
          desc="批量通过选中的审核记录并自动发布"
          @click="handleBatchApprove"
        />
        <IconButton
          type="danger"
          size="small"
          :disabled="selectedRows.length === 0 || batchLoading"
          :loading="batchLoading && batchAction === 'reject'"
          :icon="Close"
          label="批量打回"
          desc="批量打回选中的审核记录"
          @click="handleBatchReject"
        />
      </div>
    </div>

    <el-table data-guide="review-table"
      ref="tableRef"
      :data="list"
      stripe
      class="list-table"
      @selection-change="handleSelectionChange"
    >
      <!-- 选择列仅在待审核 tab 显示，避免误操作已处理记录 -->
      <el-table-column
        v-if="activeTab === 'pending'"
        type="selection"
        width="48"
      />
      <el-table-column prop="episode_date" label="日期" width="140" />
      <el-table-column prop="workflow_id" label="工作流ID" min-width="160" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" effect="light">
            {{ statusText(row.status) }}
          </el-tag>
          <!-- 自动审批标记：仅在系统自动审批通过时显示 -->
          <el-tag
            v-if="row.auto_approved"
            size="small"
            type="primary"
            effect="plain"
            style="margin-left: 4px"
          >
            系统
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时长" width="170">
        <template #default="{ row }">
          <span v-if="row.measured_duration_sec != null">
            {{ formatDuration(row.measured_duration_sec) }}
          </span>
          <span v-else class="text-muted">—</span>
          <!-- T02028：拼接阶段为达时长下限用 BGM/静音凑过时，成品时长不代表内容真实长度，
               运营按「凑时」标记改用内容实测时长核验（如 30 分钟保底） -->
          <el-tooltip
            v-if="row.supplement_sec > 0"
            :content="`成品含 ${row.supplement_sec}s BGM/静音凑时，内容实测 ${formatDuration(row.original_duration_sec)}`"
          >
            <el-tag type="warning" effect="plain" size="small" style="margin-left: 4px">
              凑时 {{ row.supplement_sec }}s
            </el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="审核人" width="140">
        <template #default="{ row }">
          {{ row.reviewer_name || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="200">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <IconButton type="primary" size="small" :icon="View" label="审核" desc="进入该稿件的审核详情" @click="goReview(row.id)" />
        </template>
      </el-table-column>
      <!-- 失败时不能再说「暂无…稿件」：那会把「接口挂了」伪装成「没有数据」（B6 / PRD §6.5），
           与 ChannelManagement（T02496）同一口径：错误态存在就不渲染空态文案 -->
      <template #empty><el-empty v-if="!listError" :description="emptyText" :image-size="90" /></template>
    </el-table>

    <div class="pagination-wrap">
      <!-- T02517（B3）：补 sizes 选择器。此前 size 固定 10 且 layout 里没有 sizes，
           每天几百条时只能 10 行一页反复翻；上限按 NFR-UX-03 收在 100（后端 le=100）。 -->
      <el-pagination data-guide="review-pagination"
        v-model:current-page="page"
        v-model:page-size="size"
        :page-sizes="PAGE_SIZE_OPTIONS"
        :total="total"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="loadList"
        @size-change="handleSizeChange"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 审核列表页：按状态分 tab 展示稿件
 *
 * 设计要点：
 * - tab 与分页联动：切换 tab 时重置到第一页，避免停留在不存在的页码
 * - 状态映射到 el-tag 颜色，直观区分审核进度
 * - 列表数据由后端按 status 过滤返回，前端不做本地过滤
 * - 批量审批仅在待审核 tab 启用：已通过/已打回的记录不允许批量操作
 * - 批量操作结果按 succeeded/failed/skipped 分类提示，便于用户识别
 * - **tab/page/size 写入 URL**（T02511 / FR-UX-602 / ACC-UX-601#3）：刷新
 *   `/review?tab=approved&page=3` 仍在原状态，链接可分享可收藏；等于默认值的
 *   参数不写进 URL，非法参数回落默认值并在页内点名（见 composables/useUrlState.js）
 * - T02517（FR-UX-703）：分页尺寸可选（B3，上限 100 见 NFR-UX-03）、工作流 ID 筛选
 *   并同样持久化到 URL（B4）、加载失败上屏错误态 + 重试且保留旧数据标注（B6）
 */
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Select, Close, View, Search, RefreshLeft } from '@element-plus/icons-vue'
import api from '../../api'
import { batchHandleReviewAction } from '../../api/reviews'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { formatTime } from '../../utils/format'
import { REVIEW_STATUS, enumLabel, enumTagType } from '../../constants/enums'
import { PAGE_SIZE_OPTIONS, MAX_PAGE_SIZE, clampPageSize } from '../../constants/pagination'
import { useUrlState } from '../../composables/useUrlState'
import { detailLocation } from '../../utils/urlState'
import ListLoadError from '../../components/ListLoadError.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const activeTab = ref('pending')
const list = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
// T02517（B6）：列表加载失败原因（空字符串=无失败）。失败时**保留** list 里的旧数据，
// 由错误态组件注明「下方为上次成功加载的数据」，不谎报「暂无数据」。
const listError = ref('')
// T02517（B4）：筛选条件（后端 list_reviews 目前只支持 workflow_id，其余不假装有）
const filters = reactive({ workflow_id: '' })

// URL 参数规格。tab 的白名单**只放这三个**：el-tabs 只渲染三个 pane，
// 把 enum 全量（含 replaced）放进去会让 `?tab=replaced` 通过校验却渲染出空表格。
// page.max 在拿到 total 之后动态改写（深链 ?page=999 应落到最后一页，而不是空表）。
// size.max 按 NFR-UX-03 收在 100（后端 reviews/materials 都是 le=100，给更大只会被静默钳回）。
const URL_SPECS = {
  tab: { default: 'pending', enum: ['pending', 'approved', 'rejected'] },
  page: { default: 1, type: 'int', min: 1 },
  size: { default: 10, type: 'int', min: 1, max: MAX_PAGE_SIZE },
  workflow_id: { default: '', maxLength: 64, pattern: '^[A-Za-z0-9_-]+$' },
}
const urlState = useUrlState(URL_SPECS, () => ({
  tab: activeTab.value,
  page: page.value,
  size: size.value,
  workflow_id: filters.workflow_id,
}), { onExternalChange: applyFromUrl })

/**
 * 把地址栏/内部 size 值收敛到可选尺寸（T02517）。
 *
 * `?size=7` 是合法整数（过得了 parseInteger），但选择器里没有 7 这一档：
 * 原样发请求会渲染出「7 行 + 一个显示不出当前值的尺寸选择器」。
 * 这里就近取允许值，并把校正过程记进 invalidParams，地址栏与界面最终一致。
 */
function resolveSize(raw) {
  const n = Number(raw)
  const clamped = clampPageSize(n)
  sizeClamp.value =
    Number.isFinite(n) && n > 0 && n !== clamped
      ? {
          key: 'size',
          raw: String(raw),
          reason: `不在可选尺寸 ${PAGE_SIZE_OPTIONS.join('/')} 中：已按 ${clamped} 处理`,
        }
      : null
  return clamped
}

/** 地址栏被外部改动（手改 URL / 前进后退）时：把校验后的值灌回状态并重载 */
function applyFromUrl(values) {
  const nextSize = resolveSize(values.size)
  const nextWorkflowId = values.workflow_id || ''
  const changed =
    values.tab !== activeTab.value ||
    values.page !== page.value ||
    nextSize !== size.value ||
    nextWorkflowId !== filters.workflow_id
  activeTab.value = values.tab
  page.value = values.page
  size.value = nextSize
  filters.workflow_id = nextWorkflowId
  if (changed) loadList()
}

/** 被回落过的非法参数（页内提示用；不打断操作，也不弹 toast） */
// 页码越界的校正另存一份：`urlState.invalid` 由 useUrlState 在每次读 URL 时整体重写，
// 而我们钳制完就会回写 URL —— 写进 invalid 的补记会当场被清掉，提示永远出不来。
const pageClamp = ref(null)
// 同上：size 不在允许档位里的钳制补记（T02517）
const sizeClamp = ref(null)
const invalidParams = computed(() => {
  const extra = []
  if (pageClamp.value) extra.push(pageClamp.value)
  if (sizeClamp.value) extra.push(sizeClamp.value)
  return extra.length ? [...urlState.invalid.value, ...extra] : urlState.invalid.value
})

// 空态文案跟着 tab 走：在「已通过」tab 下写「暂无待审核稿件」是自相矛盾的
// （与移动端 I48 同源的那类错误——空态引错文案会让人以为系统没数据）。
// 措辞直接取共享字典里的枚举标签，不再本地另写一份映射（FR-UX-405 / T02504）
const emptyText = computed(() => `暂无${enumLabel(REVIEW_STATUS, activeTab.value)}的稿件`)

// 批量操作状态
const tableRef = ref(null)
const selectedRows = ref([])
const batchLoading = ref(false)
const batchAction = ref('')

/**
 * 页码越界要等拿到 total 才知道上限，所以这条校正是加载后补记的（readUrlState 只能管
 * 「是不是整数 / 有没有小于下限」）。不补记的话地址被悄悄改写，用户看到的仍是「我分享的那个 page」。
 */
async function loadList() {
  loading.value = true
  try {
    // 最多两轮：第一轮拿到 total 后若发现深链页码越界，校正到最后一页再取一次。
    // 用固定轮次而不是递归，`?page=999` 这种地址不会把请求打成无限循环。
    for (let attempt = 0; attempt < 2; attempt++) {
      const data = await api.get('/reviews', {
        params: {
          status: activeTab.value,
          page: page.value,
          size: size.value,
          // T02517（B4）：后端一直支持 workflow_id 精确过滤，界面此前没有入口
          workflow_id: filters.workflow_id || undefined,
        },
      })
      list.value = data.list
      total.value = data.total
      const maxPage = Math.max(1, Math.ceil((data.total || 0) / size.value))
      // 动态上限：让 readUrlState 之后的校验也知道「这一页最多到几」
      URL_SPECS.page.max = maxPage
      // 深链可能指向一个不存在的页（`?page=999`，或别人分享后数据变少）。
      // 落到**最后一页**而不是退回第 1 页——用户想看的是尾部数据，回到头部会让
      // 「数据好像变少了」变成一次误导；同时把校正后的值写回 URL，地址栏不再撒谎。
      if (page.value > maxPage && attempt === 0) {
        pageClamp.value = {
          key: 'page',
          raw: String(page.value),
          reason: `超过上限 ${maxPage}：已落到最后一页`,
        }
        page.value = maxPage
        continue
      }
      // 页码本来就在范围内（只有第一轮能判定这件事）：清掉上一轮的越界提示，
      // 否则用户点了正常页码后「参数已修正」的告警会一直挂着，变成新的误导。
      // ⚠ 不能无条件清——钳制后的第二轮就在范围内，会把刚记下的这条当场抹掉（实测踩过）。
      if (attempt === 0) pageClamp.value = null
      break
    }
    listError.value = ''
    urlState.pushToUrl()
  } catch (e) {
    // 错误三件套（PRD §6.1）：拦截器已经发过一次去重 toast，这里补「页内错误态 + 控制台留痕」。
    // ⚠ 不清空 list：请求失败时表格里的仍是上次成功的数据，把它抹掉等于把
    // 「刷新失败」伪装成「没有数据」（B6 的原始症状）。
    listError.value = e?.response?.data?.message || e?.message || String(e) || '未知错误'
    console.error('[review] 列表加载失败', {
      status: e?.response?.status,
      tab: activeTab.value,
      page: page.value,
      size: size.value,
      workflow_id: filters.workflow_id || null,
      message: listError.value,
    })
  } finally {
    loading.value = false
  }
}

/** 改分页尺寸：回到第 1 页再取（第 8 页 × 10 行换成 100 行/页时，第 8 页已不存在） */
function handleSizeChange() {
  page.value = 1
  loadList()
}

/** 筛选查询：条件变了必须回第 1 页，否则「筛完落在第 3 页」是个空表 */
function onFilterSearch() {
  page.value = 1
  loadList()
}

function onFilterReset() {
  filters.workflow_id = ''
  onFilterSearch()
}

// 切换 tab 重置分页再加载
function handleTabChange() {
  page.value = 1
  // 切换 tab 时清空选中状态，避免选中其他 tab 的记录
  selectedRows.value = []
  tableRef.value?.clearSelection()
  loadList()
}

// 深链优先：URL 上有 tab/page/size/workflow_id 就按 URL 起（非法值由 readFromUrl 回落并记录）
onMounted(() => {
  const v = urlState.readFromUrl()
  activeTab.value = v.tab
  page.value = v.page
  size.value = resolveSize(v.size)
  filters.workflow_id = v.workflow_id || ''
  loadList()
})

function goReview(id) {
  // T02512（FR-UX-603）：把「我来的这一页」（含 tab/分页）挂到 ?from= 交给详情页，
  // 详情返回与操作成功后的回跳都按它还原，不再被写死的 /review 抹成第 1 页待审核。
  router.push(detailLocation(route.fullPath, `/review/${id}`))
}

// 后端 review 有 4 态（见 backend/app/models/review.py ReviewStatus），
// 文案与标签色取自 src/constants/enums.js，与详情页/工作流页同源（FR-UX-405 / T02504）
function statusTagType(status) {
  return enumTagType(REVIEW_STATUS, status)
}

function statusText(status) {
  return enumLabel(REVIEW_STATUS, status)
}

function formatDuration(sec) {
  if (sec == null) return '-'
  if (sec < 60) return `${sec} 秒`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
  return `${Math.floor(sec / 3600)} 时 ${Math.floor((sec % 3600) / 60)} 分`
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

/**
 * 构造批量操作结果提示文本
 * 显示成功/跳过/失败/发布失败的统计，便于用户识别处理情况
 */
function buildBatchSummary(result) {
  const parts = []
  if (result.succeeded?.length) parts.push(`成功 ${result.succeeded.length}`)
  if (result.skipped?.length) parts.push(`跳过 ${result.skipped.length}`)
  if (result.failed?.length) parts.push(`失败 ${result.failed.length}`)
  if (result.publish_failed?.length) parts.push(`发布失败 ${result.publish_failed.length}`)
  return parts.join('，') || '无变更'
}

async function handleBatchApprove() {
  const ids = selectedRows.value.map((r) => r.id)
  if (ids.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确认批量通过选中的 ${ids.length} 条审核记录？\n通过后将自动发布对应节目。`,
      '批量通过确认',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  batchAction.value = 'approve'
  batchLoading.value = true
  try {
    const data = await batchHandleReviewAction(ids, 'approve')
    const summary = buildBatchSummary(data)
    // 全部成功时 success，部分失败时 warning
    if (data.failed?.length || data.publish_failed?.length) {
      ElMessage.warning(`批量通过完成：${summary}`)
    } else {
      ElMessage.success(`批量通过完成：${summary}`)
    }
    // 清空选中状态并刷新列表
    tableRef.value?.clearSelection()
    selectedRows.value = []
    await loadList()
  } finally {
    batchLoading.value = false
    batchAction.value = ''
  }
}

async function handleBatchReject() {
  const ids = selectedRows.value.map((r) => r.id)
  if (ids.length === 0) return

  // 批量打回必须填写统一理由，使用 prompt 收集
  let reason
  try {
    const result = await ElMessageBox.prompt(
      `请输入批量打回理由（将应用于选中的 ${ids.length} 条记录）：`,
      '批量打回确认',
      {
        type: 'warning',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPlaceholder: '请输入打回理由',
        inputValidator: (val) => (val && val.trim() ? true : '打回理由不能为空'),
      }
    )
    reason = result.value
  } catch {
    return
  }

  batchAction.value = 'reject'
  batchLoading.value = true
  try {
    const data = await batchHandleReviewAction(ids, 'reject', reason)
    const summary = buildBatchSummary(data)
    if (data.failed?.length) {
      ElMessage.warning(`批量打回完成：${summary}`)
    } else {
      ElMessage.success(`批量打回完成：${summary}`)
    }
    tableRef.value?.clearSelection()
    selectedRows.value = []
    await loadList()
  } finally {
    batchLoading.value = false
    batchAction.value = ''
  }
}
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: $radius-lg;

  .batch-info {
    font-size: 13px;
    color: var(--el-text-color-secondary);
  }

  .batch-actions {
    display: flex;
    gap: 8px;
  }
}

.list-table {
  border-radius: $radius-lg;
  overflow: hidden;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
