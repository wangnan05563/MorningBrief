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
          <el-empty v-if="filteredTables.length === 0 && !tablesError" description="无匹配表" :image-size="60" />
        </div>
      </el-aside>

      <!-- 右侧：数据区 -->
      <el-main class="content-area">
        <!-- T02496（FR-UX-302 / M54）：拉不到表/数据时必须显式报错并禁用写操作，
             不能让失败显示成「请从左侧选择一张表」——那会让人以为库里没东西 -->
        <ListLoadError
          v-if="loadFailed"
          :message="loadErrorMessage"
          :retrying="retryingLoad"
          :stale="rows.length > 0"
          @retry="reloadAll"
        />
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
              <IconButton
                size="small"
                label="新增"
                desc="新增一行记录"
                :icon="Plus"
                :disabled="loadFailed"
                @click="openCreateDialog"
              />
              <IconButton
                size="small"
                type="danger"
                :icon="Delete"
                :disabled="selectedRows.length === 0 || loadFailed"
                :label="`批量删除 (${selectedRows.length})`"
                desc="删除选中的多行记录"
                @click="handleBatchDelete"
              />
              <el-dropdown @command="handleExport">
                <!-- T00812：dropdown 触发按钮关闭 Tooltip，避免与下拉菜单同时弹出 -->
                <IconButton
                  size="small"
                  label="导出"
                  desc="导出当前表数据"
                  :icon="Download"
                  :loading="exporting"
                  :tooltip="false"
                />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="csv">导出 CSV</el-dropdown-item>
                    <el-dropdown-item command="json">导出 JSON</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <IconButton
                size="small"
                label="导入"
                desc="从 CSV/JSON 导入数据"
                :icon="Upload"
                :disabled="loadFailed"
                @click="importDialogVisible = true"
              />
              <IconButton
                size="small"
                label="表结构"
                desc="查看当前表结构"
                :icon="View"
                @click="schemaDialogVisible = true"
              />
              <IconButton
                size="small"
                label="审计日志"
                desc="查看操作审计日志"
                :icon="Document"
                @click="loadAuditLogs"
              />
              <IconButton
                size="small"
                label="刷新"
                desc="重新加载当前表数据"
                :icon="Refresh"
                @click="loadRows"
              />
            </div>
          </div>

          <!-- 数据表格 -->
          <el-table
            v-loading="rowsLoading"
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
                <IconButton
                  size="small"
                  text
                  label="编辑"
                  desc="编辑该行记录"
                  :icon="Edit"
                  :disabled="loadFailed"
                  @click="openEditDialog(row)"
                />
                <IconButton
                  size="small"
                  text
                  type="danger"
                  label="删除"
                  desc="删除该行记录"
                  :icon="Delete"
                  :disabled="loadFailed"
                  @click="handleDelete(row)"
                />
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

        <el-empty v-else-if="!loadFailed" description="请从左侧选择一张表" />
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
            :disabled="formMode === 'edit' && (col.primary_key || col.sensitive)"
            type="primary"
            clearable
          />
          <span class="field-hint">
            {{ col.type }}{{ col.nullable ? '' : ' (必填)' }}
            <template v-if="col.sensitive">
              · 敏感字段{{ formMode === 'edit' ? '（编辑时只读，保持原值）' : '' }}
            </template>
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <IconButton
          label="取消"
          desc="关闭对话框"
          :icon="Close"
          @click="formDialogVisible = false"
        />
        <IconButton
          type="primary"
          label="确认"
          desc="保存当前行记录"
          :icon="Check"
          @click="submitForm"
        />
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
      <el-tabs v-model="importFormat" class="import-tabs" @tab-change="importPreview = null">
        <el-tab-pane label="CSV 粘贴" name="csv">
          <el-input
            v-model="importContent"
            type="textarea"
            :rows="8"
            placeholder="粘贴 CSV 内容（首行为列名，支持引号内逗号与换行）"
            @input="importPreview = null"
          />
        </el-tab-pane>
        <el-tab-pane label="JSON 粘贴" name="json">
          <el-input
            v-model="importContent"
            type="textarea"
            :rows="8"
            placeholder='粘贴 JSON 数组，如 [{"id":1,"name":"test"}]'
            @input="importPreview = null"
          />
        </el-tab-pane>
      </el-tabs>
      <div class="import-mode">
        <span>导入模式：</span>
        <el-radio-group v-model="importMode" @change="importPreview = null">
          <el-radio value="insert">新增（主键冲突跳过）</el-radio>
          <el-radio value="replace">替换（仅更新本次提供的列，其余保持原值）</el-radio>
        </el-radio-group>
      </div>
      <div v-if="importPreview" class="import-preview">
        <div>
          共 {{ importPreview.total }} 行：预计新增 {{ importPreview.to_insert }}、更新
          {{ importPreview.to_update }}、冲突 {{ importPreview.conflicts }}、错误
          {{ importPreview.error_rows }}（预览不写库）
        </div>
        <ul v-if="importPreview.errors.length" class="import-preview-errors">
          <li v-for="err in importPreview.errors.slice(0, 10)" :key="err.row">
            第 {{ err.row }} 行：{{ err.error }}
          </li>
        </ul>
      </div>
      <template #footer>
        <IconButton
          label="取消"
          desc="关闭对话框"
          :icon="Close"
          @click="importDialogVisible = false"
        />
        <IconButton
          label="预览"
          desc=" dry-run 预计写入行数，不写数据库"
          :icon="View"
          :loading="importPreviewing"
          @click="handlePreviewImport"
        />
        <IconButton
          type="warning"
          label="确认导入"
          desc="将粘贴内容写入数据库"
          :icon="Check"
          @click="handleImport"
        />
      </template>
    </el-dialog>

    <!-- 删除确认弹窗（含级联预览 + 确认词；预览失败不允许进入本弹窗） -->
    <el-dialog v-model="deleteDialogVisible" title="确认删除" width="500px">
      <div v-if="deleteCascade" class="cascade-preview">
        <p class="cascade-title">
          删除「{{ selectedTableLabel }}」（{{ deleteTarget }}）表的
          {{ deleteIds.length }} 行记录
        </p>
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
        <el-alert v-else type="success" :closable="false">无已声明的关联影响</el-alert>
        <p class="cascade-total">
          合计受影响 {{ deleteTotalAffected }} 行（主表 {{ deleteIds.length }} +
          级联 {{ deleteCascade.total_affected || 0 }}）
        </p>
        <el-alert
          v-if="deleteCascade.undeclared_downstream"
          type="warning"
          :closable="false"
          class="cascade-undeclared"
          :title="deleteCascade.undeclared_downstream"
        />
      </div>
      <el-alert type="error" :closable="false" class="cascade-irreversible">
        此操作不可恢复：SQLite 没有回收站，删除后只能靠事先备份还原。
      </el-alert>
      <el-divider />
      <p class="confirm-hint">请输入表名 <code>{{ selectedTable }}</code> 以确认删除操作：</p>
      <el-input v-model="deleteConfirmInput" :placeholder="selectedTable" clearable />
      <template #footer>
        <IconButton
          label="取消"
          desc="关闭对话框"
          :icon="Close"
          @click="deleteDialogVisible = false"
        />
        <IconButton
          type="danger"
          :disabled="deleteConfirmInput !== selectedTable"
          label="确认删除"
          desc="执行删除操作"
          :icon="Delete"
          @click="confirmDelete"
        />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from '../../utils/message'
import {
  Search, Plus, Delete, Download, Upload, View, Document, Refresh, Lock, EditPen,
  Close, Edit, Check,
} from '@element-plus/icons-vue'
import {
  listTables, getTableSchema, listRows,
  createRow, updateRow, deleteRow, batchDelete,
  cascadePreview, exportRows, importRows, listAuditLogs, previewImport,
} from '../../api/dbAdmin'
import { formatTime } from '../../utils/format'
import ListLoadError from '../../components/ListLoadError.vue'

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
const rowsLoading = ref(false)

// T02496（FR-UX-302 / M54）：加载失败态。失败时页面不得显示成「没有表/没有数据」，
// 且新增、编辑、删除、导入这些写操作必须禁用——列信息（columns）没拿到时
// 弹出的编辑表单是空的，提交上去等于用空对象覆盖该行。
const tablesError = ref('')
const schemaError = ref('')
const rowsError = ref('')
const retryingLoad = ref(false)
const loadFailed = computed(() => !!tablesError.value || !!schemaError.value || !!rowsError.value)
const loadErrorMessage = computed(() => tablesError.value || schemaError.value || rowsError.value)

// ---- 弹窗状态 ----
const formDialogVisible = ref(false)
const formMode = ref('create')
const formData = ref({})
const originalForm = ref({})
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

// 左栏给的是中文名（t.label），确认框只用英文表名会让人对不上对象（M32）
const selectedTableLabel = computed(() => {
  const hit = tables.value.find((t) => t.name === deleteTarget.value || t.name === selectedTable.value)
  return hit?.label || deleteTarget.value || selectedTable.value
})
const deleteTotalAffected = computed(
  () => deleteIds.value.length + (deleteCascade.value?.total_affected || 0),
)

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
    tablesError.value = ''
    if (tables.value.length > 0 && !selectedTable.value) {
      selectTable(tables.value[0].name)
    }
  } catch (e) {
    tablesError.value = e?.message || '数据表清单加载失败'
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
    schemaError.value = columns.value.length === 0 ? '表结构未返回列信息' : ''
  } catch (e) {
    // 列信息缺失时编辑弹窗会渲染成空表单，必须按失败处理而不是「这张表没有字段」
    schemaError.value = e?.message || '表结构加载失败'
    columns.value = []
  }
}

async function loadRows() {
  if (!selectedTable.value) return
  rowsLoading.value = true
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
    rowsError.value = ''
  } catch (e) {
    // 旧行为：置空 rows + console.warn → 界面显示空表，与「这张表真的没有数据」同形。
    // 现在保留上一次的行并进入错误态，写操作按钮同步禁用。
    rowsError.value = e?.message || '表数据加载失败'
  } finally {
    rowsLoading.value = false
  }
}

// 错误态里的「重试」：重新拉清单 + 当前表的结构与数据
async function reloadAll() {
  retryingLoad.value = true
  try {
    tablesError.value = ''
    schemaError.value = ''
    rowsError.value = ''
    await loadTables()
    if (selectedTable.value) {
      await loadSchema()
      await loadRows()
    }
  } finally {
    retryingLoad.value = false
  }
}

// ---- 新增/编辑 ----
function openCreateDialog() {
  formMode.value = 'create'
  formData.value = {}
  originalForm.value = {}
  formDialogVisible.value = true
}

function openEditDialog(row) {
  formMode.value = 'edit'
  // 深拷贝行数据，避免直接修改原数据
  formData.value = { ...row }
  originalForm.value = { ...row }
  // 记录主键值（用于更新接口）
  const pkCol = columns.value.find((c) => c.primary_key)
  editingPkValue.value = pkCol ? String(row[pkCol.name]) : null
  formDialogVisible.value = true
}

const MASK_SENTINEL_RE = /^\*{2,}$/

// 编辑时只提交变化过的字段：整行回传会把后端下发的 *** 脱敏值写回真实凭据列
function buildDirtyValues() {
  const skip = new Set(
    columns.value
      .filter((c) => c.primary_key || c.sensitive)
      .map((c) => c.name),
  )
  const payload = {}
  for (const [name, value] of Object.entries(formData.value)) {
    if (skip.has(name)) continue
    if (typeof value === 'string' && MASK_SENTINEL_RE.test(value.trim())) continue
    if (String(originalForm.value[name] ?? '') === String(value ?? '')) continue
    payload[name] = value
  }
  return payload
}

async function submitForm() {
  try {
    if (formMode.value === 'create') {
      await createRow(selectedTable.value, formData.value)
      ElMessage.success('新增成功')
    } else {
      const values = buildDirtyValues()
      if (!Object.keys(values).length) {
        ElMessage.info('没有需要保存的修改')
        return
      }
      await updateRow(selectedTable.value, editingPkValue.value, values)
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
  // 预览级联影响：失败时不得降级成「零信息确认」，直接拒绝进入删除流程（M31）
  try {
    deleteCascade.value = await cascadePreview(selectedTable.value, [pkValue])
  } catch (e) {
    deleteCascade.value = null
    ElMessage.error(`级联影响预览失败，已禁止删除：${e?.message || '请重试'}`)
    return
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
    deleteCascade.value = null
    ElMessage.error(`级联影响预览失败，已禁止批量删除：${e?.message || '请重试'}`)
    return
  }
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  const confirmText = (deleteConfirmInput.value || '').trim()
  if (confirmText !== selectedTable.value) {
    ElMessage.error(`请输入表名 ${selectedTable.value} 以确认删除`)
    return
  }
  const requested = deleteIds.value.length
  try {
    const res =
      requested === 1
        ? await deleteRow(selectedTable.value, deleteIds.value[0], confirmText)
        : await batchDelete(selectedTable.value, deleteIds.value, confirmText)
    // 以服务端实际影响行数为准（请求数 ≠ 实际数，M37）
    const affected = res?.affected ?? requested
    const cascadeAffected = Object.values(res?.cascade || {}).reduce(
      (sum, n) => sum + (Number(n) || 0),
      0,
    )
    const detail = cascadeAffected ? `，级联 ${cascadeAffected} 行` : ''
    if (affected < requested) {
      ElMessage.warning(
        `已删除 ${affected}/${requested} 行（其余主键未命中）${detail}，请刷新核对剩余数据`,
      )
    } else {
      ElMessage.success(`已删除 ${affected} 行${detail}`)
    }
    deleteDialogVisible.value = false
    deleteConfirmInput.value = ''
    deleteCascade.value = null
    selectedRows.value = []
    await loadRows()
  } catch (e) {
    console.warn('confirmDelete failed:', e)
  }
}

// ---- 导出 ----
const exporting = ref(false)
async function handleExport(format) {
  exporting.value = true
  try {
    await exportRows(selectedTable.value, format)
    ElMessage.success('导出成功')
  } catch (e) {
    console.warn('handleExport failed:', e)
  } finally {
    exporting.value = false
  }
}

// ---- 导入 ----
// CSV/JSON 解析统一交给后端标准库（引号内逗号、CRLF、BOM 前端手拆会出错）
const importPreview = ref(null)
const importPreviewing = ref(false)

async function handlePreviewImport() {
  if (!importContent.value.trim()) {
    ElMessage.warning('请粘贴导入内容')
    return
  }
  importPreviewing.value = true
  try {
    importPreview.value = await previewImport(
      selectedTable.value,
      importContent.value,
      importFormat.value,
      importMode.value,
    )
  } catch (e) {
    importPreview.value = null
    console.warn('previewImport failed:', e)
  } finally {
    importPreviewing.value = false
  }
}

async function handleImport() {
  if (!importContent.value.trim()) {
    ElMessage.warning('请粘贴导入内容')
    return
  }
  if (!importPreview.value) {
    ElMessage.warning('请先预览，确认预计写入行数后再导入')
    return
  }
  try {
    const result = await importRows(
      selectedTable.value,
      importContent.value,
      importFormat.value,
      importMode.value,
    )
    ElMessage.success(
      `导入完成：新增 ${result.inserted}，更新 ${result.updated ?? 0}，跳过 ${result.skipped}`,
    )
    importDialogVisible.value = false
    importContent.value = ''
    importPreview.value = null
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

  .cascade-total {
    margin-top: 10px;
    font-size: 13px;
    font-weight: 600;
    color: $color-text-primary;
  }

  .cascade-undeclared {
    margin-top: 10px;
  }
}

.cascade-irreversible {
  margin-top: 12px;
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
