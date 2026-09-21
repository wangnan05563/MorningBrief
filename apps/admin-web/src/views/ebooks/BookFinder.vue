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
          <!-- T00619：索引过期（默认 >14 天）时醒目提示，并说明已自动后台更新 -->
          <el-tag v-if="indexInfo.stale" type="warning" size="small">索引已过期</el-tag>
          <el-tag v-else type="success" size="small">索引就绪</el-tag>
          <span class="index-text">
            共 {{ indexInfo.book_count }} 本书 / {{ indexInfo.category_count }} 个分类，
            构建于 {{ formatTime(indexInfo.built_at) }}
            <template v-if="indexInfo.stale">
              （{{ indexInfo.age_days }} 天前{{ building ? '，正在后台自动更新' : '，系统已自动触发后台更新' }}，
              期间结果可能不含最新书籍）
            </template>
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
        <IconButton
          size="small"
          :loading="building"
          :disabled="building"
          :icon="Refresh"
          :label="indexReady ? '重建索引' : '构建索引'"
          :desc="indexReady ? '重建本地书源索引' : '构建本地书源索引'"
          @click="onRebuildIndex"
        />
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
          <IconButton type="primary" :loading="searching" :icon="Search" label="检索" desc="按关键词与分类检索书目" @click="onSearch" />
          <!-- T00810：随机浏览入口，紧邻检索按钮右侧，布局与菜单整体一致 -->
          <IconButton :loading="searching" :icon="Sort" label="随机" desc="随机抽取书目浏览" @click="onRandom" />
          <IconButton :disabled="searching" :icon="Refresh" label="刷新分类" desc="重新拉取书源分类列表" @click="onRefreshCategories" />
        </el-form-item>
      </el-form>

      <!-- 结果元信息：把「扫描范围 / 失败分类」显式回传，避免被误读为「书源里没有」 -->
      <div v-if="searched" class="result-meta">
        <el-tag size="small" type="info">命中 {{ hits.length }} 条</el-tag>
        <el-tag size="small" type="info">扫描 {{ scannedCount }} 个分类</el-tag>
        <el-tag v-if="failedCategories.length" size="small" type="warning">
          {{ failedCategories.length }} 个分类拉取失败：{{ failedCategories.join('、') }}
        </el-tag>
        <span v-if="indexStaleForQuery" class="meta-hint stale-hint">
          索引数据为 {{ indexAgeDays }} 天前，正在后台自动更新——本次结果可能不含最新书籍。
        </span>
        <span v-else-if="indexReadyForQuery" class="meta-hint">结果来自本地索引（毫秒级）。</span>
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
        <el-table-column label="下载" width="130" fixed="right">
          <template #default="{ row }">
            <el-link type="primary" :href="row.url" target="_blank" rel="noopener">
              打开链接 ↗
            </el-link>
          </template>
        </el-table-column>
        <!-- T00626：一键加入待讲书单（写素材占位，运营据此补齐书稿） -->
        <el-table-column label="待讲书单" width="130" fixed="right">
          <template #default="{ row }">
            <IconButton
              size="small"
              :loading="draftingUrl === row.url"
              :icon="Check"
              label="加入书单"
              desc="把该书加入待讲书单"
              @click="onAddToBookList(row)"
            />
          </template>
        </el-table-column>
        <template #empty>
          <el-empty
            :description="searched ? '没有匹配的书目（可尝试换关键词或先选分类）' : '点击「检索」或「随机」开始浏览'"
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
import { Refresh, Search, Sort, Check } from '@element-plus/icons-vue'
import { ElMessage } from '../../utils/message'
import {
  createDraftMaterial,
  getEbookCategories,
  getEbookIndexStatus,
  getRandomEbooks,
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
// T00619：本次检索所用索引是否已过期（后端随响应回传）
const indexStaleForQuery = ref(false)
// T00626：正在加入待讲书单的 url（按钮 loading 用）
const draftingUrl = ref('')
const indexAgeDays = ref(null)
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

/**
 * T00626：把命中的书加入待讲书单（写一条"待上传书稿"的素材占位，url 去重幂等）。
 * 取件仍人工：下载 EPUB/DOCX 后到「素材录入」上传，素材占位随之被替换/补齐。
 */
async function onAddToBookList(row) {
  draftingUrl.value = row.url
  try {
    const data = await createDraftMaterial({
      title: row.title,
      author: row.author,
      category: row.category,
      url: row.url,
    })
    if (data?.created === false) {
      ElMessage.info(data?.message || '该书已在素材库中')
    } else {
      ElMessage.success(data?.message || '已加入待讲书单')
    }
  } catch (e) {
    // 错误提示由拦截器统一处理
  } finally {
    draftingUrl.value = ''
  }
}

/**
 * 统一结果落表：检索与随机共用同一套元信息赋值，避免两处漂移。
 * 后端在检索/随机时若发现索引过期/缺失会自动触发后台重建 → 起轮询让用户看到进度。
 */
function applyResult(data) {
  hits.value = data?.hits || []
  scannedCount.value = (data?.scanned_categories || []).length
  failedCategories.value = data?.failed_categories || []
  indexReadyForQuery.value = !!data?.index_ready
  indexStaleForQuery.value = !!data?.index_stale
  indexAgeDays.value = data?.index_age_days ?? null
  if (data?.auto_rebuild?.triggered) startPolling()
  searched.value = true
}

/**
 * T00810：随机抽取——从书源索引无重复抽取 10 本（不足返回全部），渲染到同一结果表。
 * 随机是「浏览发现」路径：不依赖关键词/分类输入（后端从全索引抽样），点击只切换 loading。
 */
async function onRandom() {
  searching.value = true
  try {
    const data = await getRandomEbooks(10)
    applyResult(data)
  } catch (e) {
    // 索引未就绪（428）等由请求拦截器提示；刷新一次状态便于用户看到构建进度
    await loadIndexStatus()
  } finally {
    searching.value = false
  }
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
    applyResult(data)
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
.book-finder .stale-hint {
  color: var(--el-color-warning, #e6a23c);
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
