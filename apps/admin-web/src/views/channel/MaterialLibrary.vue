<template>
  <div class="material-library">
    <el-card shadow="never">
      <template #header>
        <div class="page-header">
          <span class="page-title">素材库管理</span>
          <el-button type="primary" size="small" @click="openCreate">手动录入素材</el-button>
        </div>
      </template>

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
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="标题 / 来源" clearable style="width: 220px" @keyup.enter="onSearch" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onSearch">搜索</el-button>
          <el-button @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="items" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="150" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.crawled_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="没有匹配的素材" :image-size="90" /></template>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="[20, 50, 100]"
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
        <el-form-item label="正文">
          <el-input v-model="editForm.content" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveEdit">保存</el-button>
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
        <el-form-item label="正文">
          <el-input v-model="createForm.content" type="textarea" :rows="8" placeholder="素材正文全文（必填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveCreate">保存</el-button>
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
 */
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { formatTime } from '../../utils/format'
import { listChannels } from '../../api/channels'
import {
  createMaterial,
  deleteMaterial,
  getMaterial,
  listMaterials,
  updateMaterial,
} from '../../api/materials'

const route = useRoute()
const STATUS_LABELS = { pending: '待消费', selected: '已选题', skipped: '已跳过' }
const STATUS_TAGS = { pending: 'info', selected: 'success', skipped: 'warning' }
const statusLabel = (s) => STATUS_LABELS[s] || s || '-'
const statusTagType = (s) => STATUS_TAGS[s] || 'info'

const channels = ref([])
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const filters = reactive({ channel_id: null, status: null, keyword: '' })

const editVisible = ref(false)
const editForm = reactive({ id: null, title: '', source: '', category: '', status: 'pending', content: '' })
const createVisible = ref(false)
const createForm = reactive({ channel_id: null, source: '', title: '', category: '', content: '' })
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await listMaterials({
      channel_id: filters.channel_id || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined,
      page: page.value,
      size: size.value,
    })
    items.value = data?.items || []
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

onMounted(async () => {
  channels.value = await listChannels()
  const qid = Number(route.query.channelId)
  if (qid) filters.channel_id = qid
  await load()
})
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
.filter-form {
  margin-bottom: 4px;
}
.form-tip {
  display: block;
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
}
</style>
