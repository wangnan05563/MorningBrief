<template>
  <div class="page-container book-finder">
    <!-- 顶部说明：讲清「找书自动化 / 取件人工」的分工与取件后去向，避免误期待 -->
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="找书工具：检索结果来自第三方书源仓库，下载与入库需人工完成"
      description="书源链接指向城通网盘（无直链，无法自动下载）。请人工下载 EPUB/DOCX 后，到「内容运营 → 素材录入」上传，系统会按章节解析入库，再由频道工作流按章节顺序改写为讲书稿。书源内容来自网络搜集，其声明「请勿用于商业目的」，对外发布前请自行确认授权。"
      style="margin-bottom: 12px"
    />

    <!-- 索引状态条（T00612）：全量检索走本地索引，未构建时引导构建 -->
    <el-card shadow="never" class="index-card">
      <div class="index-row">
        <template v-if="indexReady">
          <el-tag type="success" size="small">索引就绪</el-tag>
          <span class="index-text">
            共 {{ indexInfo.book_count }} 本书 / {{ indexInfo.category_count }} 个分类，
            构建于 {{ formatTime(indexInfo.built_at) }}
          </span>
        </template>
        <template v-else-if="building">
          <el-tag type="warning" size="small">索引构建中</el-tag>
          <span class="index-text">
            {{ indexInfo.build.done || 0 }} / {{ indexInfo.build.total || '…' }} 个分类
            （首次约 2-5 分钟，期间可先选具体分类搜索）
          </span>
        </template>
        <template v-else>
          <el-tag type="info" size="small">索引未构建</el-tag>
          <span class="index-text">
            不选分类的全量搜索需先构建本地索引；也可先选择具体分类立即搜索
          </span>
        </template>
        <el-button
          size="small"
          :loading="building"
          :disabled="building"
          @click="onRebuildIndex"
        >{{ indexReady ? '重建索引' : '构建索引' }}</el-button>
      </div>
    </el-card>

    <!-- 检索区 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="关键词">
          <el-input
            v-model="keyword"
            placeholder="书名或作者，如：余华 / 论语"
            clearable
            style="width: 240px"
            @keyup.enter="onSearch"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-select
            v-model="category"
            placeholder="全部分类（较慢）"
            clearable
            filterable
            :loading="categoryLoading"
            style="width: 200px"
          >
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number v-model="limit" :min="1" :max="100" :step="10" controls-position="right" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="searching" @click="onSearch">检索</el-button>
          <el-button :disabled="searching" @click="onRefreshCategories">刷新分类</el-button>
        </el-form-item>
      </el-form>

      <!-- 结果元信息：把「扫描范围 / 失败分类」显式回传，避免被误读为「书源里没有」 -->
      <div v-if="searched" class="result-meta">
        <el-tag size="small" type="info">命中 {{ hits.length }} 条</el-tag>
        <el-tag size="small" type="info">扫描 {{ scannedCount }} 个分类</el-tag>
        <el-tag v-if="failedCategories.length" size="small" type="warning">
          {{ failedCategories.length }} 个分类拉取失败：{{ failedCategories.join('、') }}
        </el-tag>
        <span v-if="indexReadyForQuery" class="meta-hint">结果来自本地索引（毫秒级）。</span>
        <span v-else-if="!category" class="meta-hint">索引未就绪时，未限定分类的搜索需先构建索引；可先选分类。</span>
      </div>
    </el-card>

    <!-- 结果表 -->
    <el-card shadow="never" class="result-card">
      <el-table :data="hits" v-loading="searching" stripe style="width: 100%">
        <el-table-column type="index" width="56" label="#" />
        <el-table-column prop="title" label="书名" min-width="240" show-overflow-tooltip />
        <el-table-column prop="author" label="作者" width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column label="下载" width="140" fixed="right">
          <template #default="{ row }">
            <el-link type="primary" :href="row.url" target="_blank" rel="noopener">
              打开链接 ↗
            </el-link>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty
            :description="searched ? '没有匹配的书目（可尝试换关键词或先选分类）' : '输入关键词后点击「检索」'"
            :image-size="90"
          />
        </template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
/**
 * 找书工具（T00601 / T00603）：书源检索 → 人工取件 → 素材录入上传入库。
 *
 * 职责边界（与后端一致）：
 * - 本页只做「检索」；下载在城通网盘页面完成（无直链，程序化取件不可行）；
 * - 取件后走既有「素材录入」（支持 .epub/.docx/.html/.txt/.md）入库，再由频道工作流改写。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from '../../utils/message'
import {
  getEbookCategories,
  getEbookIndexStatus,
  rebuildEbookIndex,
  searchEbooks,
} from '../../api/ebooks'

const keyword = ref('')
const category = ref('')
const limit = ref(20)

const categories = ref([])
const categoryLoading = ref(false)

const hits = ref([])
const scannedCount = ref(0)
const failedCategories = ref([])
const searching = ref(false)
const searched = ref(false)

// 索引状态（T00612：全量检索走本地索引，避免全量抓取超时）
const indexInfo = ref({ book_count: 0, category_count: 0, built_at: null, build: {} })
const indexReady = ref(false)
const indexReadyForQuery = ref(false)
let pollTimer = null

const building = computed(() => !!(indexInfo.value.build && indexInfo.value.build.running))

async function loadCategories(force = false) {
  categoryLoading.value = true
  try {
    const data = await getEbookCategories(force)
    categories.value = data?.categories || []
  } catch (e) {
    // 分类拉取失败不阻断检索（用户可留空走全量扫描）
    ElMessage.warning('书源分类拉取失败，可直接用关键词全量检索')
  } finally {
    categoryLoading.value = false
  }
}

function onRefreshCategories() {
  loadCategories(true)
}

async function onSearch() {
  const kw = keyword.value.trim()
  if (!kw) {
    ElMessage.warning('请输入关键词（书名或作者）')
    return
  }
  // 未选分类且索引未就绪：先说明机制并触发构建，避免请求挂到超时（T00612 根因）
  if (!category.value && !indexReady.value) {
    ElMessage.warning('全量搜索需要先构建书源索引，已开始构建；也可选择具体分类立即搜索')
    await onRebuildIndex()
    return
  }
  searching.value = true
  try {
    const data = await searchEbooks({ keyword: kw, category: category.value, limit: limit.value })
    hits.value = data?.hits || []
    scannedCount.value = (data?.scanned_categories || []).length
    failedCategories.value = data?.failed_categories || []
    indexReadyForQuery.value = !!data?.index_ready
    searched.value = true
  } catch (e) {
    // 索引缺失（428）等业务错误由拦截器提示；刷新一次状态便于用户看到进度
    await loadIndexStatus()
  } finally {
    searching.value = false
  }
}

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

async function loadIndexStatus() {
  try {
    const data = await getEbookIndexStatus()
    indexInfo.value = data || {}
    indexReady.value = !!data?.ready
    // 构建结束（running=false 且有结果）后停止轮询
    if (!building.value && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  } catch (e) {
    // 状态查询失败不阻断检索
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(loadIndexStatus, 3000)
}

async function onRebuildIndex() {
  try {
    await rebuildEbookIndex()
    ElMessage.success('索引构建已开始，完成后即可全量搜索（约 2-5 分钟）')
    await loadIndexStatus()
    startPolling()
  } catch (e) {
    // 错误提示由请求拦截器统一处理
  }
}

onMounted(() => {
  loadCategories()
  loadIndexStatus()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.book-finder .search-card {
  margin-bottom: 12px;
}
.book-finder .index-card {
  margin-bottom: 12px;
}
.book-finder .index-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.book-finder .index-text {
  color: var(--el-text-color-regular, #606266);
  font-size: 13px;
  margin-right: auto;
}
.book-finder .result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.book-finder .meta-hint {
  color: var(--el-text-color-secondary, #909399);
  font-size: 12px;
}
</style>
