<template>
  <div class="db-admin-page">
    <el-container class="main-container">
      <!-- 左侧：表列表 -->
      <el-aside width="220px" class="sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">数据表</span>
        </div>
        <el-input
          v-model="tableSearch"
          placeholder="搜索表名..."
          :prefix-icon="Search"
          clearable
          size="small"
          class="table-search"
        />
        <div class="table-list">
          <div
            v-for="t in filteredTables"
            :key="t.name"
            class="table-item"
            :class="{ active: t.name === selectedTable }"
            @click="selectTable(t.name)"
          >
            <span class="table-label">{{ t.label }}</span>
            <el-tag size="small" type="info" round>{{ t.rows }}</el-tag>
          </div>
          <el-empty v-if="filteredTables.length === 0" description="无匹配表" :image-size="60" />
        </div>
      </el-aside>

      <!-- 右侧：数据区 -->
      <el-main class="content-area">
        <template v-if="selectedTable">
          <!-- 工具栏 -->
          <div class="toolbar">
            <div class="toolbar-left">
              <span class="current-table">{{ currentTableLabel }}</span>
              <el-input
                v-model="searchKeyword"
                placeholder="搜索..."
                :prefix-icon="Search"
                clearable
                size="small"
                class="search-input"
                @input="debouncedSearch"
                @clear="loadRows"
              />
            </div>
            <div class="toolbar-right">
              <el-button size="small" :icon="Plus" @click="openCreateDialog">新增</el-button>
              <el-button
                size="small"
                type="danger"
                :icon="Delete"
                :disabled="selectedRows.length === 0"
                @click="handleBatchDelete"
              >
                批量删除 ({{ selectedRows.length }})
              </el-button>
              <el-dropdown @command="handleExport">
                <el-button size="small" :icon="Download">导出</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="csv">导出 CSV</el-dropdown-item>
                    <el-dropdown-item command="json">导出 JSON</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button size="small" :icon="Upload" @click="importDialogVisible = true">导入</el-button>
              <el-button size="small" :icon="View" @click="schemaDialogVisible = true">表结构</el-button>
              <el-button size="small" :icon="Document" @click="loadAuditLogs">审计日志</el-button>
              <el-button size="small" :icon="Refresh" @click="loadRows">刷新</el-button>
            </div>
          </div>

          <!-- 数据表格 -->
          <el-table
            :data="rows"
            border
            stripe
            size="small"
            class="data-table"
            @selection-change="handleSelectionChange"
            @sort-change="handleSortChange"
          >
            <el-table-column type="selection" width="40" />
            <el-table-column
              v-for="col in columns"
              :key="col.name"
              :prop="col.name"
              :label="col.name"
              :sortable="col.type.includes('INT') || col.type.includes('DATE') ? 'custom' : false"
              :min-width="getColumnWidth(col)"
              show-overflow-tooltip
            >
              <template #header>
                <span class="col-header">
                  {{ col.name }}
                  <el-tag v-if="col.primary_key" size="small" type="warning" effect="plain">PK</el-tag>
                  <el-icon v-if="col.sensitive" class="sensitive-icon"><Lock /></el-icon>
                </span>
              </template>
              <template #default="{ row }">
                <span class="cell-value" :class="{ 'cell-sensitive': col.sensitive }">
                  {{ formatCellValue(row[col.name]) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text @click="openEditDialog(row)">编辑</el-button>
                <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div class="pagination">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="total"
              :page-sizes="[20, 50, 100, 200]"
              layout="total, sizes, prev, pager, next"
              background
              @size-change="loadRows"
              @current-change="loadRows"
            />
          </div>
        </template>

        <el-empty v-else description="请从左侧选择一张表" />
      </el-main>
    </el-container>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="formDialogVisible"
      :title="formMode === 'create' ? '新增行' : '编辑行'"
      width="600px"
      @close="formDialogVisible = false"
    >
      <el-form :model="formData" label-width="140px" label-position="right">
        <el-form-item
          v-for="col in editableColumns"
          :key="col.name"
          :label="col.name"
        >
          <component
            :is="getFormComponent(col)"
            v-model="formData[col.name]"
            :placeholder="col.type"
            :disabled="formMode === 'edit' && col.primary_key"
            type="primary"
            clearable
          />
          <span class="field-hint">{{ col.type }}{{ col.nullable ? '' : ' (必填)' }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确认</el-button>
      </template>
    </el-dialog>

    <!-- 表结构弹窗 -->
    <el-dialog v-model="schemaDialogVisible" title="表结构" width="700px">
      <el-table :data="columns" border size="small">
        <el-table-column prop="name" label="列名" width="160" />
        <el-table-column prop="type" label="类型" width="160" />
        <el-table-column label="属性" width="200">
          <template #default="{ row }">
            <el-tag v-if="row.primary_key" size="small" type="warning">主键</el-tag>
            <el-tag :size="small" :type="row.nullable ? 'info' : 'danger'">
              {{ row.nullable ? '可空' : '非空' }}
            </el-tag>
            <el-tag v-if="row.sensitive" size="small" type="warning">敏感</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="default" label="默认值" />
      </el-table>
    </el-dialog>

    <!-- 审计日志弹窗 -->
    <el-dialog v-model="auditDialogVisible" title="审计日志" width="800px">
      <el-table :data="auditLogs" border size="small" max-height="500">
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="操作" width="120" />
        <el-table-column prop="target" label="目标表" width="120" />
        <el-table-column prop="operator" label="操作人" width="100" />
        <el-table-column label="详情">
          <template #default="{ row }">
            <pre class="detail-json">{{ JSON.stringify(row.detail, null, 2) }}</pre>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="导入数据" width="600px">
      <el-alert type="warning" :closable="false" class="import-alert">
        导入将直接写入数据库，敏感字段会被忽略。单次最多导入 5000 行。
      </el-alert>
      <el-tabs v-model="importFormat" class="import-tabs">
        <el-tab-pane label="CSV 粘贴" name="csv">
          <el-input
            v-model="importContent"
            type="textarea"
            :rows="8"
            placeholder="粘贴 CSV 内容（首行为列名）"
          />
        </el-tab-pane>
        <el-tab-pane label="JSON 粘贴" name="json">
          <el-input
            v-model="importContent"
            type="textarea"
            :rows="8"
            placeholder='粘贴 JSON 数组，如 [{"id":1,"name":"test"}]'
          />
        </el-tab-pane>
      </el-tabs>
      <div class="import-mode">
        <span>导入模式：</span>
        <el-radio-group v-model="importMode">
          <el-radio value="insert">新增（主键冲突跳过）</el-radio>
          <el-radio value="replace">替换（主键冲突覆盖）</el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="warning" @click="handleImport">确认导入</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认弹窗（含级联预览 + 令牌输入） -->
    <el-dialog v-model="deleteDialogVisible" title="确认删除" width="500px">
      <div v-if="deleteCascade" class="cascade-preview">
        <p class="cascade-title">将删除 {{ deleteTarget }} 表的 {{ deleteIds.length }} 行记录</p>
        <div v-if="deleteCascade.relations.length > 0" class="cascade-relations">
          <p class="cascade-subtitle">关联影响：</p>
          <div v-for="rel in deleteCascade.relations" :key="rel.table" class="cascade-item">
            <el-icon :color="rel.action === 'cascade' ? '#FF9AA2' : '#FFE5B4'">
              <Delete v-if="rel.action === 'cascade'" />
              <EditPen v-else />
            </el-icon>
            <span>{{ rel.description }}</span>
            <el-tag size="small" :type="rel.action === 'cascade' ? 'danger' : 'warning'">
              {{ rel.count }} 行
            </el-tag>
          </div>
        </div>
        <el-alert v-else type="success" :closable="false">无关联影响</el-alert>
      </div>
      <el-divider />
      <p class="confirm-hint">请输入 <code>CONFIRM_DELETE</code> 以确认删除操作：</p>
      <el-input v-model="deleteConfirmInput" placeholder="CONFIRM_DELETE" clearable />
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" :disabled="deleteConfirmInput !== 'CONFIRM_DELETE'" @click="confirmDelete">
          确认删除
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from '../../utils/message'
import {
  Search, Plus, Delete, Download, Upload, View, Document, Refresh, Lock, EditPen,
} from '@element-plus/icons-vue'
import {
  listTables, getTableSchema, listRows,
  createRow, updateRow, deleteRow, batchDelete,
  cascadePreview, exportRows, importRows, listAuditLogs,
} from '../../api/dbAdmin'

// ---- 表列表 ----
const tables = ref([])
const tableSearch = ref('')
const selectedTable = ref('')

const filteredTables = computed(() => {
  if (!tableSearch.value) return tables.value
  const kw = tableSearch.value.toLowerCase()
  return tables.value.filter(
    (t) => t.name.includes(kw) || t.label.includes(tableSearch.value),
  )
})

const currentTableLabel = computed(() => {
  const t = tables.value.find((x) => x.name === selectedTable.value)
  return t ? t.label : selectedTable.value
})

// ---- 表结构 ----
const columns = ref([])
const editableColumns = computed(() => columns.value)

// ---- 行数据 ----
const rows = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const searchKeyword = ref('')
const orderBy = ref('')
const orderDir = ref('ASC')
const selectedRows = ref([])

// ---- 弹窗状态 ----
const formDialogVisible = ref(false)
const formMode = ref('create')
const formData = ref({})
const editingPkValue = ref(null)

const schemaDialogVisible = ref(false)
const auditDialogVisible = ref(false)
const auditLogs = ref([])

const importDialogVisible = ref(false)
const importFormat = ref('csv')
const importContent = ref('')
const importMode = ref('insert')

const deleteDialogVisible = ref(false)
const deleteCascade = ref(null)
const deleteIds = ref([])
const deleteTarget = ref('')
const deleteConfirmInput = ref('')

// ---- 防抖搜索 ----
let searchTimer = null
function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    loadRows()
  }, 400)
}

// ---- 加载方法 ----
async function loadTables() {
  try {
    tables.value = await listTables()
    if (tables.value.length > 0 && !selectedTable.value) {
      selectTable(tables.value[0].name)
    }
  } catch (e) {
    console.warn('loadTables failed:', e)
  }
}

async function selectTable(name) {
  selectedTable.value = name
  currentPage.value = 1
  searchKeyword.value = ''
  orderBy.value = ''
  selectedRows.value = []
  await loadSchema()
  await loadRows()
}

async function loadSchema() {
  if (!selectedTable.value) return
  try {
    const schema = await getTableSchema(selectedTable.value)
    columns.value = schema.columns || []
  } catch (e) {
    console.warn('loadSchema failed:', e)
    columns.value = []
  }
}

async function loadRows() {
  if (!selectedTable.value) return
  try {
    const data = await listRows(selectedTable.value, {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value,
      order_by: orderBy.value || undefined,
      order_dir: orderDir.value,
      search: searchKeyword.value || undefined,
    })
    rows.value = data.rows || []
    total.value = data.total || 0
  } catch (e) {
    console.warn('loadRows failed:', e)
    rows.value = []
    total.value = 0
  }
}

// ---- 新增/编辑 ----
function openCreateDialog() {
  formMode.value = 'create'
  formData.value = {}
  formDialogVisible.value = true
}

function openEditDialog(row) {
  formMode.value = 'edit'
  // 深拷贝行数据，避免直接修改原数据
  formData.value = { ...row }
  // 记录主键值（用于更新接口）
  const pkCol = columns.value.find((c) => c.primary_key)
  editingPkValue.value = pkCol ? String(row[pkCol.name]) : null
  formDialogVisible.value = true
}

async function submitForm() {
  try {
    if (formMode.value === 'create') {
      await createRow(selectedTable.value, formData.value)
      ElMessage.success('新增成功')
    } else {
      await updateRow(selectedTable.value, editingPkValue.value, formData.value)
      ElMessage.success('更新成功')
    }
    formDialogVisible.value = false
    await loadRows()
  } catch (e) {
    console.warn('submitForm failed:', e)
  }
}

// ---- 删除（含级联预览 + 令牌确认） ----
async function handleDelete(row) {
  const pkCol = columns.value.find((c) => c.primary_key)
  if (!pkCol) {
    ElMessage.error('无主键列，无法删除')
    return
  }
  const pkValue = String(row[pkCol.name])
  deleteIds.value = [pkValue]
  deleteTarget.value = selectedTable.value
  deleteConfirmInput.value = ''
  // 预览级联影响
  try {
    deleteCascade.value = await cascadePreview(selectedTable.value, [pkValue])
  } catch (e) {
    console.warn('cascadePreview failed:', e)
    deleteCascade.value = null
  }
  deleteDialogVisible.value = true
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  const pkCol = columns.value.find((c) => c.primary_key)
  if (!pkCol) {
    ElMessage.error('无主键列，无法删除')
    return
  }
  deleteIds.value = selectedRows.value.map((r) => String(r[pkCol.name]))
  deleteTarget.value = selectedTable.value
  deleteConfirmInput.value = ''
  try {
    deleteCascade.value = await cascadePreview(selectedTable.value, deleteIds.value)
  } catch (e) {
    console.warn('batch cascadePreview failed:', e)
    deleteCascade.value = null
  }
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  try {
    if (deleteIds.value.length === 1) {
      await deleteRow(selectedTable.value, deleteIds.value[0])
    } else {
      await batchDelete(selectedTable.value, deleteIds.value)
    }
    ElMessage.success(`已删除 ${deleteIds.value.length} 行`)
    deleteDialogVisible.value = false
    selectedRows.value = []
    await loadRows()
  } catch (e) {
    console.warn('confirmDelete failed:', e)
  }
}

// ---- 导出 ----
async function handleExport(format) {
  try {
    await exportRows(selectedTable.value, format)
    ElMessage.success('导出成功')
  } catch (e) {
    console.warn('handleExport failed:', e)
  }
}

// ---- 导入 ----
async function handleImport() {
  if (!importContent.value.trim()) {
    ElMessage.warning('请粘贴导入内容')
    return
  }
  let rowsData = []
  try {
    if (importFormat.value === 'json') {
      rowsData = JSON.parse(importContent.value)
      if (!Array.isArray(rowsData)) {
        ElMessage.error('JSON 必须是数组格式')
        return
      }
    } else {
      // CSV 解析：首行为列名
      const lines = importContent.value.trim().split('\n')
      const headers = lines[0].split(',').map((h) => h.trim())
      rowsData = lines.slice(1).map((line) => {
        const vals = line.split(',')
        const obj = {}
        headers.forEach((h, i) => { obj[h] = vals[i]?.trim() || null })
        return obj
      })
    }
  } catch (e) {
    ElMessage.error('解析失败: ' + e.message)
    return
  }

  try {
    const result = await importRows(selectedTable.value, rowsData, importMode.value)
    ElMessage.success(`导入完成：成功 ${result.inserted}，跳过 ${result.skipped}`)
    importDialogVisible.value = false
    importContent.value = ''
    await loadRows()
  } catch (e) {
    console.warn('handleImport failed:', e)
  }
}

// ---- 审计日志 ----
async function loadAuditLogs() {
  try {
    auditLogs.value = await listAuditLogs(100)
    auditDialogVisible.value = true
  } catch (e) {
    console.warn('loadAuditLogs failed:', e)
  }
}

// ---- 事件处理 ----
function handleSelectionChange(val) {
  selectedRows.value = val
}

function handleSortChange({ prop, order }) {
  if (order) {
    orderBy.value = prop
    orderDir.value = order === 'ascending' ? 'ASC' : 'DESC'
  } else {
    orderBy.value = ''
  }
  loadRows()
}

// ---- 辅助方法 ----
function getColumnWidth(col) {
  // 文本类列宽一些，其他列窄一些
  if (col.type.includes('TEXT') || col.type.includes('JSON')) return 200
  if (col.type.includes('VARCHAR') && col.type.includes('256')) return 200
  return 120
}

function getFormComponent(col) {
  const type = col.type.toUpperCase()
  if (type.includes('INT') || type.includes('FLOAT') || type.includes('REAL')) {
    return 'el-input-number'
  }
  if (type.includes('BOOL')) {
    return 'el-switch'
  }
  if (type.includes('TEXT') || type.includes('JSON')) {
    return 'el-input'
  }
  return 'el-input'
}

function formatCellValue(val) {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'object') return JSON.stringify(val)
  if (typeof val === 'string' && val.length > 100) return val.substring(0, 100) + '...'
  return String(val)
}

function formatTime(t) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

onMounted(() => {
  loadTables()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.db-admin-page {
  height: 100%;
  background: $color-bg;

  .main-container {
    height: 100%;
  }

  .sidebar {
    background: $color-bg-card;
    border-right: 1px solid $color-border;
    overflow-y: auto;

    .sidebar-header {
      padding: 16px;
      border-bottom: 1px solid $color-border;

      .sidebar-title {
        font-size: 16px;
        font-weight: 600;
        color: $color-text-primary;
      }
    }

    .table-search {
      margin: 12px;
      width: calc(100% - 24px);
    }

    .table-list {
      padding: 0 8px 8px;
    }

    .table-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      border-radius: $radius-sm;
      cursor: pointer;
      transition: all 0.2s;
      margin-bottom: 4px;

      &:hover {
        background: rgba(181, 234, 215, 0.4);
      }

      &.active {
        background: $color-primary-light;
        border-left: 3px solid $color-primary;
      }

      .table-label {
        font-size: 13px;
        color: $color-text-primary;
      }
    }
  }

  .content-area {
    padding: 16px;
    overflow-y: auto;

    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 12px;

      .toolbar-left {
        display: flex;
        align-items: center;
        gap: 16px;

        .current-table {
          font-size: 18px;
          font-weight: 600;
          color: $color-text-primary;
        }

        .search-input {
          width: 240px;
        }
      }

      .toolbar-right {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
      }
    }

    .data-table {
      .col-header {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;

        .sensitive-icon {
          color: $color-secondary-dark;
        }
      }

      .cell-sensitive {
        color: $color-secondary-dark;
      }
    }

    .pagination {
      margin-top: 16px;
      display: flex;
      justify-content: flex-end;
    }
  }
}

.field-hint {
  font-size: 12px;
  color: $color-text-secondary;
  margin-left: 8px;
}

.detail-json {
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 100px;
  overflow-y: auto;
  margin: 0;
}

.import-alert {
  margin-bottom: 16px;
}

.import-tabs {
  margin-bottom: 16px;
}

.import-mode {
  margin-top: 12px;

  span {
    margin-right: 12px;
    color: $color-text-primary;
  }
}

.cascade-preview {
  .cascade-title {
    font-size: 15px;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 12px;
  }

  .cascade-subtitle {
    font-size: 13px;
    color: $color-text-secondary;
    margin-bottom: 8px;
  }

  .cascade-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    font-size: 13px;
  }
}

.confirm-hint {
  margin-bottom: 12px;
  color: $color-text-primary;

  code {
    background: $color-warning;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
  }
}
</style>
