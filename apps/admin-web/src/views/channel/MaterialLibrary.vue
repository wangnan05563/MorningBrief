<template>
  <!-- page-container：补齐 24px 页面内边距（同 BookPool，缺它会 0px 贴边） -->
  <div data-guide="material-library-page" class="material-library page-container">
    <el-card shadow="never">
      <template #header>
        <div class="page-header">
          <!-- T00811：移除与导航栏重复的页面标题，仅保留操作按钮 -->
          <!-- C45：这颗按钮和菜单「素材录入」是两个不同对象——这里是在库里直接补一条记录，
               「素材录入」是按渠道（上传书稿 / URL / 二维码）入库。两处此前都叫「手动录入」，
               首次用户无法判断「库 / 池 / 录入」到底是几个东西。 -->
          <IconButton
            type="primary"
            size="small"
            :icon="Plus"
            label="库内手工新增素材"
            desc="在素材库里直接补一条记录；上传书稿/文档请走菜单「素材录入」"
            :disabled="!!loadError"
            @click="openCreate"
          />
          <!-- C114：这里与工作流详情「爬虫采集 · 素材库」是同一份频道级素材，
               跨页写入不会自动推送，各自刷新即可看到对方改动 -->
          <span class="page-scope-note">
            与工作流详情「爬虫采集 · 素材库」是同一份数据；在另一页增删改后，请点「刷新」。
          </span>
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
            <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
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
          <IconButton :loading="loading" :icon="Refresh" label="刷新" desc="重新加载当前条件下的素材（跨页改动需手动刷新）" @click="load" />
          <IconButton :icon="RefreshLeft" label="重置" desc="重置筛选条件" @click="onReset" />
        </el-form-item>
        <el-form-item label="视图">
          <el-radio-group v-model="viewMode" size="small" @change="onViewModeChange">
            <el-radio-button value="list">明细</el-radio-button>
            <el-radio-button value="book">按书聚合</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <!-- T02626：列表失败时页内说明 + 重试；已有旧行时注明是上次成功的数据 -->
      <ListLoadError
        v-if="loadError"
        :message="loadError"
        :stale="viewMode === 'book' ? books.length > 0 : items.length > 0"
        :retrying="loading"
        @retry="load"
      />

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
            :disabled="!!loadError"
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
            <IconButton size="small" :icon="Edit" :disabled="!!loadError" label="编辑" desc="编辑该素材" @click="openEdit(row)" />
            <IconButton size="small" type="danger" plain :icon="Delete" :disabled="!!loadError" label="删除" desc="删除该素材" @click="onDelete(row)" />
          </template>
        </el-table-column>
        <!-- T02626：失败态不出「没有匹配的素材」 -->
        <template #empty><el-empty v-if="!loadError" description="没有匹配的素材" :image-size="90" /></template>
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
              :disabled="!!loadError"
              label="删除"
              desc="删除该书名下全部章节素材"
              @click="onDeleteBook(row)"
            />
          </template>
        </el-table-column>
        <template #empty>
          <el-empty v-if="!loadError" description="没有可聚合的书——上传 EPUB/DOCX 时「来源」会记为书名" :image-size="90" />
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
            <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
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

    <!-- 新增弹窗（库内手工补一条记录；渠道入库见菜单「素材录入」，C45 术语分工） -->
    <el-dialog v-model="createVisible" title="库内手工新增素材" width="640px">
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
        <IconButton :icon="Close" label="取消" desc="关闭弹窗，放弃新增" @click="createVisible = false" />
        <IconButton type="primary" :loading="saving" :icon="Check" label="保存" desc="保存这条素材（C45：这是库内补录，渠道入库见菜单「素材录入」）" @click="onSaveCreate" />
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
import { Plus, Close, Search, Refresh, RefreshLeft, Edit, Delete, View, Check, Picture } from '@element-plus/icons-vue'
import { ElMessage } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import { readUrlState, MATERIALS_QUERY_SPECS } from '../../utils/urlState'
import { formatTime } from '../../utils/format'
import { blankedFieldMessage, findBlankedCriticalField } from '../../utils/blankGuard'
import { useUserStore } from '../../stores/user'
import { listChannels } from '../../api/channels'
import { aggregateMaterials } from '../../api/materialLibrary'
import ListLoadError from '../../components/ListLoadError.vue'
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
// C114：筛选与编辑弹窗共用同一份状态字典，页面不再自带第二套「待消费/已选题/已跳过」
const statusOptions = enumOptions(MATERIAL_STATUS)

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
// T02626（FR-UX-302）：此前 load() 只有 try/finally，失败时既无页内错误态也无留痕，
// 首屏失败直接落「没有匹配的素材」——把接口挂了说成筛选没命中。
const loadError = ref('')
const filters = reactive({ channel_id: null, status: null, keyword: '', source_type: null, media_type: null })
// T00775：视图模式——list=素材明细，book=按书聚合（讲书稿场景找整本书）
const viewMode = ref('list')
// T00775：精确过滤（后端 material_id / source 精确等值，不走 keyword 的 LIKE 模糊匹配）
const materialIdFilter = ref(null)
const sourceFilter = ref('')

// C43（界面不能撒谎）：material_id / source 是**明细视图专有**的精确过滤，
// 聚合接口 /materials/aggregate 只接受 channel_id / keyword / status（外加 page/size），
// 多传的参数 pydantic/Query 根本不认。此前从讲书稿书单点「素材 ID」进来后
// 提示条显示「已按素材 ID 123 定位」，用户切到「按书聚合」，结果已不再过滤，
// 而提示条原样挂着——运营据此判定「这本书只有这些章节」。
// 切视图即作废精确过滤并说明原因，而不是留着一条已经不成立的承诺。
function onViewModeChange(mode) {
  if (mode === 'book' && (materialIdFilter.value || sourceFilter.value)) {
    materialIdFilter.value = null
    sourceFilter.value = ''
    ElMessage.info(
      '「按书聚合」视图不支持按素材 ID / 来源精确定位（聚合接口只按频道、关键词、状态汇总），已清除该定位条件',
    )
  }
  page.value = 1
  onSearch()
}

const editVisible = ref(false)
const editForm = reactive({ id: null, title: '', source: '', category: '', status: 'pending', content: '', media_type: 'text', media_url: '', media_thumb_url: '' })
// C56：弹窗打开时的原值，用于识别「删光已有内容」而不是「没填」
const editOriginal = ref({ content: '', source: '' })
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
      loadError.value = ''
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
    loadError.value = ''
  } catch (e) {
    // T02626：保留上次成功的行（stale），错误态由模板负责，绝不把失败渲染成「没有匹配的素材」
    loadError.value = e?.response?.data?.message || e?.message || '素材列表加载失败'
    console.error('[material-library] 素材列表加载失败', {
      status: e?.response?.status,
      viewMode: viewMode.value,
      page: page.value,
      message: loadError.value,
    })
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
  // C56：记住打开弹窗时的原值，用来区分「没填」和「把已有内容删光了」
  editOriginal.value = { content: editForm.content, source: editForm.source }
  editVisible.value = true
}

// C56：关键列清空预检（口径与后端 PUT 的同名护栏一致，见 utils/blankGuard）
function blankedCriticalField() {
  return findBlankedCriticalField(editOriginal.value, editForm)
}

async function onSaveEdit() {
  if (!editForm.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  const blanked = blankedCriticalField()
  if (blanked) {
    ElMessage.warning(blankedFieldMessage(blanked))
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
  // T02596：素材是硬删除且无外键级联，影响范围就是这 1 条；但书单里引用它的条目会失效，
  // 必须写出来（只写「不可恢复」会让人以为删完就没事）
  const ok = await dangerConfirm({
    action: '删除素材',
    target: `「${row.title}」（ID ${row.id}）`,
    scope: '素材 1 条',
    lines: ['素材为硬删除，无关联数据被连带删除；讲书稿书单中引用它的条目取书时会提示书稿缺失。'],
    irreversible: '删除后不可恢复：素材没有回收站，只能重新采集或录入。',
    confirmLabel: '确认删除',
  })
  if (!ok) return
  await deleteMaterial(row.id)
  ElMessage.success('已删除')
  await load()
}

// T00895：删除整本书聚合记录（按来源删除该书全部章节素材）
// 必须二次确认且提示不可恢复；后端返回 deleted=0 时视为该书名已无关联素材，友好提示
async function onDeleteBook(row) {
  const ok = await dangerConfirm({
    action: '删除整本书',
    target: `《${row.source}》`,
    scope: `素材 ${row.chapters} 条（该书全部章节）`,
    lines: [
      filters.channel_id
        ? `仅删除当前频道（channel_id=${filters.channel_id}）下的同名素材。`
        : '未选频道：各频道下同名书的素材都会被删。',
    ],
    irreversible: '删除后不可恢复：素材为硬删除，没有回收站，只能重新采集。',
    confirmLabel: '确认删除',
  })
  if (!ok) return
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
    const ok = await dangerConfirm({
      action: '批量删除整本书',
      target: `${sources.length} 本书（共 ${selectedChapters.value} 章）`,
      scope: `${sources.length} 本书的全部章节素材`,
      lines: [
        filters.channel_id
          ? `仅删除当前频道（channel_id=${filters.channel_id}）下的同名素材。`
          : '未选频道：各频道下同名书的素材都会被删。',
      ],
      irreversible: '删除后不可恢复：素材为硬删除，没有回收站，只能重新采集。',
      confirmLabel: '确认删除',
    })
    if (!ok) return
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
  const ok = await dangerConfirm({
    action: '批量删除素材',
    target: `${ids.length} 条素材`,
    scope: `素材 ${ids.length} 条`,
    lines: ['讲书稿书单中引用这些素材的条目，取书时会提示书稿缺失。'],
    irreversible: '删除后不可恢复：素材为硬删除，没有回收站，只能重新采集或录入。',
    confirmLabel: '确认删除',
  })
  if (!ok) return
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
  try {
    channels.value = await listChannels()
  } catch {
    // T02626：频道筛选拉不到不阻断素材列表；拦截器已提示，此处不让整个挂载流程中断
  }
  // T02760：深链参数先过 urlState 的规格，再决定是否进查询（非法值回落并告知）
  const deepLink = readUrlState(route.query, MATERIALS_QUERY_SPECS)
  const dropped = deepLink.invalid.map((i) => i.key)
  if (deepLink.values.channelId) {
    // 存在性校验：指向不存在的频道只会得到空列表，与「该频道没素材」无法区分
    if ((channels.value || []).some((c) => c.id === deepLink.values.channelId)) {
      filters.channel_id = deepLink.values.channelId
    } else {
      dropped.push('channelId')
    }
  }
  applyDeepLink(deepLink.values)
  if (dropped.length) {
    ElMessage.warning(`地址中的筛选参数无效（${[...new Set(dropped)].join('、')}），已按默认视图展示`)
  }
  await load()
})

/**
 * T00775：深链定位（讲书稿书单「素材 ID」链接 / 「管理素材」按钮跳转）
 * - materialId：走后端 material_id 精确等值过滤（不再用标题关键词模糊匹配，
 *   避免标题含 % / _ 时被当作 LIKE 通配符）；
 * - keyword：直接回填搜索框；
 * - view=book：直接落到按书聚合视图。
 * T02760：入参已由 MATERIALS_QUERY_SPECS 规整，这里只消费合法值。
 */
function applyDeepLink(values) {
  if (values.materialId) {
    materialIdFilter.value = values.materialId
    viewMode.value = 'list'
    return
  }
  if (values.source) {
    sourceFilter.value = values.source
    viewMode.value = 'list'
    return
  }
  if (values.view === 'book') viewMode.value = 'book'
  if (values.keyword) filters.keyword = values.keyword
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
/* C114：与工作流详情同一份数据的提示，弱化到不抢按钮的注意力 */
.page-scope-note {
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
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
