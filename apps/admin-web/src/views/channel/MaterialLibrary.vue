<template>
  <!-- page-container：补齐 24px 页面内边距（同 BookPool，缺它会 0px 贴边） -->
  <div data-guide="material-library-page" class="material-library page-container">
    <el-card shadow="never">
      <template #header>
        <div class="page-header">
          <!-- T00811：移除与导航栏重复的页面标题，仅保留操作按钮 -->
          <IconButton type="primary" size="small" :icon="Plus" label="手动录入素材" desc="手动新增一条素材" @click="openCreate" />
        </div>
      </template>

      <!-- T00775：由深链/聚合视图下钻产生的筛选条件提示（可一键清除），避免"查不到素材"的错觉 -->
      <el-alert
        v-if="activeScopes.length"
        type="success"
        :closable="false"
        show-icon
        style="margin-bottom: 10px"
      >
        <template #title>
          <div class="scope-bar">
            <span v-for="s in activeScopes" :key="s.key">{{ s.text }}</span>
            <IconButton link type="primary" :icon="Close" label="清除筛选" desc="清除精确定位条件" @click="clearScope" />
          </div>
        </template>
      </el-alert>

      <el-form :inline="true" class="filter-form">
        <el-form-item label="频道">
          <el-select v-model="filters.channel_id" placeholder="全部频道" clearable filterable style="width: 200px" @change="onSearch">
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 140px" @change="onSearch">
            <el-option label="待消费" value="pending" />
            <el-option label="已选题" value="selected" />
            <el-option label="已跳过" value="skipped" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源类型">
          <el-select
            v-model="filters.source_type"
            placeholder="全部渠道"
            clearable
            style="width: 210px"
            @change="onSearch"
          >
            <el-option v-for="o in SOURCE_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="媒体类型">
          <el-select v-model="filters.media_type" placeholder="全部类型" clearable style="width: 130px" @change="onSearch">
            <el-option v-for="o in MEDIA_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="标题 / 来源" clearable style="width: 220px" @keyup.enter="onSearch" />
        </el-form-item>
        <el-form-item>
          <IconButton type="primary" :loading="loading" :icon="Search" label="搜索" desc="按当前条件查询素材" @click="onSearch" />
          <IconButton :icon="RefreshLeft" label="重置" desc="重置筛选条件" @click="onReset" />
        </el-form-item>
        <el-form-item label="视图">
          <el-radio-group v-model="viewMode" size="small" @change="onSearch">
            <el-radio-button value="list">明细</el-radio-button>
            <el-radio-button value="book">按书聚合</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <!-- T02517（FR-UX-703 / C52）：两张表都补勾选列 + 批量删除。
           此前只能一行一行点删除，清理一本误入库的书要重复几十次同样动作。
           明细表按素材 ID 批删，聚合表按书名（含当前频道筛选）整本批删。 -->
      <div v-if="selectedCount > 0" class="batch-bar">
        <span class="batch-info">
          已选 {{ selectedCount }} {{ viewMode === 'book' ? '本书' : '条素材' }}
          <template v-if="viewMode === 'book' && selectedChapters">（共 {{ selectedChapters }} 章）</template>
        </span>
        <div class="batch-actions">
          <IconButton
            size="small"
            type="danger"
            plain
            :icon="Delete"
            :loading="batchDeleting"
            label="批量删除"
            desc="删除勾选的素材，需二次确认且不可恢复"
            @click="onBatchDelete"
          />
          <IconButton
            size="small"
            link
            :icon="Close"
            label="取消选择"
            desc="清空当前勾选"
            @click="clearSelection"
          />
        </div>
      </div>

      <!-- 明细视图：一条素材一行 -->
      <el-table data-guide="material-library-table"
        v-if="viewMode === 'list'"
        ref="itemsTableRef"
        :data="items"
        v-loading="loading"
        stripe
        style="width: 100%"
        @selection-change="onItemSelectionChange"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column label="来源" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <!-- T00775：点来源即按该来源（书名）精确过滤，从"看到一条"到"看到整本书"只需一次点击 -->
            <el-link v-if="row.source" type="primary" @click="drilldownBook(row.source)">{{ row.source }}</el-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.crawled_at) }}</template>
        </el-table-column>
        <!-- T00716：媒体类型列 + 预览列（图片缩略图 / 视频徽标） -->
        <el-table-column label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="mediaTagType(row.media_type)">{{ mediaLabel(row.media_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预览" width="96" align="center">
          <template #default="{ row }">
            <el-image
              v-if="row.media_type === 'image' && row.media_url"
              :src="row.media_url"
              :preview-src-list="[row.media_url]"
              fit="cover"
              style="width: 56px; height: 64px; border-radius: 6px"
            />
            <el-tag v-else-if="row.media_type === 'video'" size="small" type="warning">视频</el-tag>
            <el-icon v-else-if="row.media_type === 'image'" class="muted"><Picture /></el-icon>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <IconButton size="small" :icon="Edit" label="编辑" desc="编辑该素材" @click="openEdit(row)" />
            <IconButton size="small" type="danger" plain :icon="Delete" label="删除" desc="删除该素材" @click="onDelete(row)" />
          </template>
        </el-table-column>
        <template #empty><el-empty description="没有匹配的素材" :image-size="90" /></template>
      </el-table>

      <!-- 按书聚合视图（T00775 遗留建议）：一行一本书，点书名下钻到该书全部章节 -->
      <el-table
        v-else
        ref="booksTableRef"
        :data="books"
        v-loading="loading"
        stripe
        style="width: 100%"
        @selection-change="onBookSelectionChange"
      >
        <!-- 勾选列与单条「删除整本书」同权限（仅 admin）：给不出删除的行就不给勾选 -->
        <el-table-column v-if="canOperate" type="selection" width="44" />
        <el-table-column prop="source" label="书名" min-width="240" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column label="章节" width="150">
          <template #default="{ row }">{{ row.chapters }} 章（待消费 {{ row.pending_chapters }}）</template>
        </el-table-column>
        <el-table-column label="最近入库" width="170">
          <template #default="{ row }">{{ formatTime(row.latest_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <IconButton size="small" :icon="View" label="查看章节" desc="下钻查看该书的章节素材" @click="drilldownBook(row.source)" />
            <!-- T00895：删除整本书聚合（仅 admin 显示）；点击弹二次确认 -->
            <IconButton
              v-if="canOperate"
              size="small"
              type="danger"
              :loading="deletingBook === row.source"
              :icon="Delete"
              label="删除"
              desc="删除该书名下全部章节素材"
              @click="onDeleteBook(row)"
            />
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="没有可聚合的书——上传 EPUB/DOCX 时「来源」会记为书名" :image-size="90" />
        </template>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="PANEL_PAGE_SIZE_OPTIONS"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 12px; justify-content: flex-end"
        @current-change="load"
        @size-change="onSearch"
      />
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑素材" width="640px">
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" maxlength="256" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="editForm.source" maxlength="64" />
          <span class="form-tip">讲书稿模式按「来源＝书名」聚合整本书章节，改来源会影响书的归属</span>
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="editForm.category" maxlength="64" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 160px">
            <el-option label="待消费" value="pending" />
            <el-option label="已选题" value="selected" />
            <el-option label="已跳过" value="skipped" />
          </el-select>
        </el-form-item>
        <!-- T00716：媒体类型 + 媒体 URL（text 素材隐藏媒体输入） -->
        <el-form-item label="媒体类型">
          <el-select v-model="editForm.media_type" style="width: 160px">
            <el-option v-for="o in MEDIA_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.media_type !== 'text'" label="媒体 URL">
          <el-input v-model="editForm.media_url" placeholder="图片/视频资源 URL" style="width: 400px" />
        </el-form-item>
        <el-form-item v-if="editForm.media_type === 'image'" label="缩略图">
          <el-input v-model="editForm.media_thumb_url" placeholder="可选：缩略图 URL" style="width: 400px" />
          <el-image
            v-if="editForm.media_url"
            :src="editForm.media_url"
            :preview-src-list="[editForm.media_url]"
            fit="cover"
            style="width: 56px; height: 80px; border-radius: 6px; margin-left: 8px"
          />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="editForm.content" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <IconButton :icon="Close" label="取消" desc="关闭弹窗，放弃修改" @click="editVisible = false" />
        <IconButton type="primary" :loading="saving" :icon="Check" label="保存" desc="保存素材修改" @click="onSaveEdit" />
      </template>
    </el-dialog>

    <!-- 新增弹窗（手动录入） -->
    <el-dialog v-model="createVisible" title="手动录入素材" width="640px">
      <el-form label-width="80px">
        <el-form-item label="频道">
          <el-select v-model="createForm.channel_id" filterable style="width: 100%">
            <el-option v-for="c in channels" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="createForm.source" maxlength="64" placeholder="书稿类请填书名（讲书稿按书名聚合整本章节）" />
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="createForm.title" maxlength="256" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="createForm.category" maxlength="64" />
        </el-form-item>
        <!-- T00716：媒体类型 + 媒体 URL（text 素材隐藏，图片/视频可填 URL 预览） -->
        <el-form-item label="媒体类型">
          <el-select v-model="createForm.media_type" style="width: 160px">
            <el-option v-for="o in MEDIA_TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="createForm.media_type !== 'text'" label="媒体 URL">
          <el-input v-model="createForm.media_url" placeholder="图片/视频资源 URL" style="width: 400px" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="createForm.content" type="textarea" :rows="8" placeholder="素材正文全文（必填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <IconButton :icon="Close" label="取消" desc="关闭弹窗，放弃录入" @click="createVisible = false" />
        <IconButton type="primary" :loading="saving" :icon="Check" label="保存" desc="保存素材录入" @click="onSaveCreate" />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 素材库管理页（T00716）
 *
 * 背景：讲书稿素材池的「从素材库加入」只能浏览，找不到素材库管理入口，
 * 也无法对已入库素材做增删改查。本页提供完整管理能力：
 * - 查询：频道/状态筛选 + 标题/来源关键词 + 分页（后端 list_materials 已扩展 keyword/status）；
 * - 新增：手动录入（source_type=list）；
 * - 编辑：标题/来源/分类/状态/正文（PUT，PATCH 语义仅更新显式字段）；
 * - 删除：二次确认后删除（不影响讲书稿素材池，池项与素材是引用关系）。
 *
 * 入口：① 侧边菜单「内容运营 → 素材库管理」；② 讲书稿素材池「从素材库加入」弹窗的「管理素材」链接。
 *
 * T00775：后端 list_materials 返回 { total, list }，本页曾按 `items` 取值 → 列表恒为空
 * （「从素材库加入」能看到书，点「管理素材」却查不到）。取值统一为 `list`，与
 * WorkflowDetail 保持一致；同时支持 ?keyword / ?materialId 深链定位。
 *
 * T02517（FR-UX-703 / C52）：明细表与按书聚合表都补上勾选列与「批量删除」，
 * 清理误入库的一本书不再需要逐行点删除几十次；勾选按视图各自计数（切视图即清空），
 * 批量删除走后端单事务接口 POST /materials/batch-delete（一次审计日志、一个事务）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, Close, Search, RefreshLeft, Edit, Delete, View, Check, Picture } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { formatTime } from '../../utils/format'
import { useUserStore } from '../../stores/user'
import { listChannels } from '../../api/channels'
import { aggregateMaterials } from '../../api/materialLibrary'
import { PANEL_PAGE_SIZE_OPTIONS } from '../../constants/pagination'
import {
  MATERIAL_STATUS,
  MATERIAL_MEDIA_TYPE,
  MATERIAL_SOURCE_TYPE,
  enumLabel,
  enumTagType,
  enumOptions,
} from '../../constants/enums'
import {
  batchDeleteMaterials,
  createMaterial,
  deleteMaterial,
  deleteMaterialsBySource,
  getMaterial,
  listMaterials,
  updateMaterial,
} from '../../api/materials'

/** 录入渠道 / 媒体类型选项与展示文案统一取自 src/constants/enums.js（FR-UX-405 / T02504） */
const SOURCE_TYPE_OPTIONS = enumOptions(MATERIAL_SOURCE_TYPE)
const MEDIA_TYPE_OPTIONS = enumOptions(MATERIAL_MEDIA_TYPE)

const route = useRoute()
const statusLabel = (s) => enumLabel(MATERIAL_STATUS, s)
const statusTagType = (s) => enumTagType(MATERIAL_STATUS, s)
const mediaLabel = (t) => enumLabel(MATERIAL_MEDIA_TYPE, t)
const mediaTagType = (t) => enumTagType(MATERIAL_MEDIA_TYPE, t)

const channels = ref([])
const items = ref([])
const books = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const filters = reactive({ channel_id: null, status: null, keyword: '', source_type: null, media_type: null })
// T00775：视图模式——list=素材明细，book=按书聚合（讲书稿场景找整本书）
const viewMode = ref('list')
// T00775：精确过滤（后端 material_id / source 精确等值，不走 keyword 的 LIKE 模糊匹配）
const materialIdFilter = ref(null)
const sourceFilter = ref('')

const editVisible = ref(false)
const editForm = reactive({ id: null, title: '', source: '', category: '', status: 'pending', content: '', media_type: 'text', media_url: '', media_thumb_url: '' })
const createVisible = ref(false)
const createForm = reactive({ channel_id: null, source: '', title: '', category: '', content: '', media_type: 'text', media_url: '', media_thumb_url: '' })
const saving = ref(false)

// T00895：整本书聚合删除仅 admin 可用；deletingBook 记录进行中书名用于按钮 loading
const userStore = useUserStore()
const canOperate = computed(() => userStore.role === 'admin')
const deletingBook = ref('')

// T02517（FR-UX-703 / C52）：勾选批量删除状态。两张表各自一份 selection，
// 计数按「当前视图」取——聚合视图勾了 3 本书，明细表的历史勾选不该跟着冒出来。
const itemsTableRef = ref(null)
const booksTableRef = ref(null)
const selectedItems = ref([])
const selectedBooks = ref([])
const batchDeleting = ref(false)
const selectedCount = computed(() =>
  viewMode.value === 'book' ? selectedBooks.value.length : selectedItems.value.length,
)
/** 勾选书的总章数（确认文案要写清「影响多少条数据」，见 PRD §6.3 确认规范） */
const selectedChapters = computed(() =>
  selectedBooks.value.reduce((n, b) => n + (b.chapters || 0), 0),
)

function onItemSelectionChange(rows) {
  selectedItems.value = rows
}

function onBookSelectionChange(rows) {
  selectedBooks.value = rows
}

function clearSelection() {
  selectedItems.value = []
  selectedBooks.value = []
  itemsTableRef.value?.clearSelection()
  booksTableRef.value?.clearSelection()
}

/** 当前生效的精确定位条件（展示为可清除的提示条） */
const activeScopes = computed(() => {
  const scopes = []
  if (materialIdFilter.value) scopes.push({ key: 'id', text: `已按素材 ID ${materialIdFilter.value} 定位` })
  if (sourceFilter.value) scopes.push({ key: 'source', text: `已按书名《${sourceFilter.value}》过滤` })
  return scopes
})

function clearScope() {
  materialIdFilter.value = null
  sourceFilter.value = ''
  onSearch()
}

async function load() {
  loading.value = true
  // 数据换了一茬，勾选随之作废（T02517）：留着会让「批量删除」删掉用户已经看不见的行
  clearSelection()
  try {
    if (viewMode.value === 'book') {
      // 按书聚合：一行一本书（source＝书名），点书名下钻进明细视图
      const data = await aggregateMaterials({
        channel_id: filters.channel_id || undefined,
        keyword: filters.keyword || undefined,
        status: filters.status || undefined,
        page: page.value,
        size: size.value,
      })
      // 注意键名是 list（不是 items）——见 T00775 根因
      books.value = data?.list || []
      total.value = data?.total || 0
      return
    }
    const data = await listMaterials({
      channel_id: filters.channel_id || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined,
      source_type: filters.source_type || undefined,
      media_type: filters.media_type || undefined,
      material_id: materialIdFilter.value || undefined,
      source: sourceFilter.value || undefined,
      page: page.value,
      size: size.value,
    })
    // T00775：后端返回键是 list（不是 items），取错键会导致列表恒为空
    items.value = data?.list || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

function onSearch() {
  page.value = 1
  load()
}

function onReset() {
  filters.channel_id = null
  filters.status = null
  filters.keyword = ''
  filters.source_type = null
  filters.media_type = null
  materialIdFilter.value = null
  sourceFilter.value = ''
  onSearch()
}

/** T00775：按来源（书名）精确过滤下钻；聚合视图点「查看章节」与明细表点「来源」共用 */
function drilldownBook(source) {
  sourceFilter.value = source || ''
  viewMode.value = 'list'
  page.value = 1
  onSearch()
}

async function openEdit(row) {
  // 列表无 content 全文，编辑需走详情接口回填
  const detail = await getMaterial(row.id)
  editForm.id = row.id
  editForm.title = detail?.title || ''
  editForm.source = detail?.source || ''
  editForm.category = detail?.category || ''
  editForm.status = detail?.status || 'pending'
  editForm.content = detail?.content || ''
  editForm.media_type = detail?.media_type || 'text'
  editForm.media_url = detail?.media_url || ''
  editForm.media_thumb_url = detail?.media_thumb_url || ''
  editVisible.value = true
}

async function onSaveEdit() {
  if (!editForm.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  saving.value = true
  try {
    await updateMaterial(editForm.id, {
      title: editForm.title,
      source: editForm.source,
      category: editForm.category || null,
      status: editForm.status,
      content: editForm.content,
      media_type: editForm.media_type,
      media_url: editForm.media_url || null,
      media_thumb_url: editForm.media_thumb_url || null,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function openCreate() {
  createForm.channel_id = filters.channel_id || (channels.value[0] ? channels.value[0].id : null)
  createForm.source = ''
  createForm.title = ''
  createForm.category = ''
  createForm.content = ''
  createForm.media_type = 'text'
  createForm.media_url = ''
  createForm.media_thumb_url = ''
  createVisible.value = true
}

async function onSaveCreate() {
  if (!createForm.title.trim() || !createForm.content.trim()) {
    ElMessage.warning('标题与正文为必填项')
    return
  }
  saving.value = true
  try {
    await createMaterial({
      workflow_id: '',
      channel_id: createForm.channel_id,
      source: createForm.source || '手动录入',
      title: createForm.title,
      content: createForm.content,
      category: createForm.category || null,
      source_type: 'list',
      media_type: createForm.media_type,
      media_url: createForm.media_url || null,
      media_thumb_url: createForm.media_thumb_url || null,
    })
    ElMessage.success('已录入素材库')
    createVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  await ElMessageBox.confirm(
    `确定删除素材「${row.title}」（ID ${row.id}）？删除后不可恢复；讲书稿书单中的对应条目取书时会提示书稿缺失。`,
    '删除素材',
    { type: 'warning' },
  )
  await deleteMaterial(row.id)
  ElMessage.success('已删除')
  await load()
}

// T00895：删除整本书聚合记录（按来源删除该书全部章节素材）
// 必须二次确认且提示不可恢复；后端返回 deleted=0 时视为该书名已无关联素材，友好提示
async function onDeleteBook(row) {
  await ElMessageBox.confirm(
    `确定删除《${row.source}》全部 ${row.chapters} 条章节素材？删除后不可恢复。`,
    '删除整本书',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
  )
  deletingBook.value = row.source
  try {
    const data = await deleteMaterialsBySource(row.source, filters.channel_id || undefined)
    if (!data || !data.deleted) {
      ElMessage.info(data?.message || '该书名下无关联素材')
    } else {
      ElMessage.success(`已删除 ${data.deleted} 条素材`)
    }
    await load()
  } finally {
    deletingBook.value = ''
  }
}

/**
 * T02517（FR-UX-703 / C52）：批量删除勾选的素材 / 整本书。
 *
 * 确认文案按 PRD §6.3「动作 + 对象 + 影响条数 + 不可逆声明」写全：明细视图给条数，
 * 聚合视图给「几本书 / 共几章」——只说「删除 3 条」会让人低估影响。
 * 未选频道时必须把「跨频道同名书也会被删」讲出来（与后端 sources 那一路的收窄口径一致），
 * 不能让用户以为删的是当前列表里看到的那几行。
 */
async function onBatchDelete() {
  if (viewMode.value === 'book') {
    const sources = selectedBooks.value.map((b) => b.source).filter(Boolean)
    if (!sources.length) return
    const scopeNote = filters.channel_id ? '' : '（未选频道：各频道下同名书的素材都会被删）'
    try {
      await ElMessageBox.confirm(
        `确定删除勾选的 ${sources.length} 本书（共 ${selectedChapters.value} 章）的全部章节素材？` +
          `${scopeNote}删除后不可恢复。`,
        '批量删除整本书',
        { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
    batchDeleting.value = true
    try {
      const data = await batchDeleteMaterials({
        sources,
        channel_id: filters.channel_id || undefined,
      })
      reportBatchDelete(data, sources.length)
      await load()
    } finally {
      batchDeleting.value = false
    }
    return
  }

  const ids = selectedItems.value.map((r) => r.id).filter(Boolean)
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除勾选的 ${ids.length} 条素材？删除后不可恢复；讲书稿书单中的对应条目取书时会提示书稿缺失。`,
      '批量删除素材',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  batchDeleting.value = true
  try {
    const data = await batchDeleteMaterials({ ids })
    reportBatchDelete(data, ids.length)
    await load()
  } finally {
    batchDeleting.value = false
  }
}

/** 批量删除结果提示：deleted=0 要说「已无匹配素材」，而不是假装成功删了几条 */
function reportBatchDelete(data, requested) {
  const deleted = data?.deleted || 0
  if (!deleted) {
    ElMessage.info('所选素材已不存在（可能已被其他操作删除），列表已重新查询')
    return
  }
  if (deleted < requested) {
    ElMessage.warning(`已删除 ${deleted} 条，另有 ${requested - deleted} 条已不存在`)
    return
  }
  ElMessage.success(`已删除 ${deleted} 条素材`)
}

onMounted(async () => {
  channels.value = await listChannels()
  const qid = Number(route.query.channelId)
  if (qid) filters.channel_id = qid
  applyDeepLink()
  await load()
})

/**
 * T00775：深链定位（讲书稿书单「素材 ID」链接 / 「管理素材」按钮跳转）
 * - materialId：走后端 material_id 精确等值过滤（不再用标题关键词模糊匹配，
 *   避免标题含 % / _ 时被当作 LIKE 通配符）；
 * - keyword：直接回填搜索框；
 * - view=book：直接落到按书聚合视图。
 */
function applyDeepLink() {
  const mid = Number(route.query.materialId)
  if (mid) {
    materialIdFilter.value = mid
    viewMode.value = 'list'
    return
  }
  if (route.query.source) {
    sourceFilter.value = String(route.query.source)
    viewMode.value = 'list'
    return
  }
  if (route.query.view === 'book') viewMode.value = 'book'
  if (route.query.keyword) filters.keyword = String(route.query.keyword)
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.page-title {
  font-weight: 600;
}
/* T02517（C52）：勾选后的批量操作条（仅在已选 > 0 时出现，避免常驻占位） */
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}
.batch-info {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.batch-actions {
  display: flex;
  gap: 8px;
}
.filter-form {
  margin-bottom: 4px;
}
/* T00775：精确定位条件的提示条（限定了某项时才出现，带一键清除） */
.scope-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.form-tip {
  display: block;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
</style>
