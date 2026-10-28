<template>
  <div data-guide="db-admin-page" class="db-admin-page">
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
      <el-main data-guide="db-admin-content" class="content-area">
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
                @click="openImportDialog"
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
              :show-overflow-tooltip="!col.sensitive"
            >
              <template #header>
                <span class="col-header">
                  {{ col.name }}
                  <el-tag v-if="col.primary_key" size="small" type="warning" effect="plain">PK</el-tag>
                  <el-icon v-if="col.sensitive" class="sensitive-icon"><Lock /></el-icon>
                </span>
              </template>
              <template #default="{ row }">
                <!-- T02827：*** 不是脏数据。悬停说明它为什么被脱敏、该去哪里改原文 -->
                <el-tooltip
                  v-if="col.sensitive && isMaskedValue(row[col.name])"
                  :content="sensitiveCellTooltip(row)"
                  placement="top"
                >
                  <span class="cell-value cell-sensitive">{{ formatCellValue(row[col.name]) }}</span>
                </el-tooltip>
                <span v-else class="cell-value" :class="{ 'cell-sensitive': col.sensitive }">
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
            <!-- T02517（NFR-UX-03）：档位收到共享口径（原本自带一个 200 档）。
                 后端 db_admin 的 limit 允许到 1000，但产品口径是「列表分页尺寸上限 100」——
                 界面上给得出 200，实际是一次比 NFR 更重的全表读取，不该由一页表格顺手触发。 -->
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="total"
              :page-sizes="PANEL_PAGE_SIZE_OPTIONS"
              layout="total, sizes, prev, pager, next"
              background
              @size-change="loadRows"
              @current-change="loadRows"
            />
          </div>
        </template>

        <el-empty v-else-if="!loadFailed" description="请从左侧选择一张表" />

        <!-- T02909：备份/恢复写在 category=backup，此前只有 category=db_admin 读得到。
             恢复是「用旧快照覆盖当前库」的操作，事后要能在本页直接看到是谁做的 -->
        <AuditTrail category="backup" guide="backup-audit" title="最近备份/恢复审计" :limit="5" />
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
            :disabled="(formMode === 'edit' && (col.primary_key || col.sensitive)) || isAutoMaintained(col)"
            type="primary"
            clearable
          />
          <span class="field-hint">
            {{ col.type }}{{ col.nullable ? '' : ' (必填)' }}
            <template v-if="col.sensitive">
              · 敏感字段{{ formMode === 'edit' ? '（编辑时只读，保持原值）' : '' }}
            </template>
            <!-- M20：时间戳列必须显式声明「界面不改它」，否则运营会以为改了生效 -->
            <template v-if="isAutoMaintained(col)">
              · 时间戳由系统自动写入，界面只读（{{ formMode === 'create' ? '新增时留空由数据库填充' : '编辑时不会回写，保持原值' }}）
            </template>
          </span>
          <!-- T02827：脱敏值来源要说清，并给出专用配置入口；否则操作者会猜菜单或手工清库 -->
          <span v-if="isMaskedValue(formData[col.name])" class="mask-hint">
            <template v-if="maskedEntries.length">
              该值已脱敏显示，请前往
              <router-link
                v-for="entry in maskedEntries"
                :key="entry.to"
                :to="entry.to"
                class="mask-hint__link"
              >「{{ entry.label }}」</router-link>
              修改；直接保存 *** 会被拒绝。
            </template>
            <template v-else>该值已脱敏显示：请留空保持原值，直接保存 *** 会被拒绝。</template>
          </span>
          <!-- 后端字段级错误（INT-UX-01）落到出错那一栏，而不是只有一句 toast -->
          <span v-if="fieldErrors[col.name]" class="field-error">
            {{ fieldErrors[col.name] }}
            <!-- T02827：拒绝「*** 回写」时，错误行里就要给出可点的专用入口 -->
            <template v-if="isMaskWritebackError(fieldErrors[col.name]) && maskedEntries.length">
              → 前往
              <router-link
                v-for="entry in maskedEntries"
                :key="entry.to"
                :to="entry.to"
                class="mask-hint__link"
              >「{{ entry.label }}」</router-link>
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
        导入将直接写入数据库，敏感字段会被忽略。
      </el-alert>
      <el-tabs v-model="importFormat" class="import-tabs" @tab-change="importPreview = null">
        <el-tab-pane label="CSV 粘贴" name="csv">
          <el-input
            v-model="importCsvContent"
            type="textarea"
            :rows="8"
            placeholder="粘贴 CSV 内容（首行为列名，支持引号内逗号与换行）"
            @input="importPreview = null"
          />
        </el-tab-pane>
        <el-tab-pane label="JSON 粘贴" name="json">
          <el-input
            v-model="importJsonContent"
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
      <!-- T03603：「冲突」是子集而非独立桶（insert 下 ⊆ 错误，replace 下 ⊆ 更新），
           与新增/更新/错误并列相加会让 1 行读成 2 行，故只在括号里点名、不参与总数拆分 -->
      <div v-if="importPreview" class="import-preview">
        <div v-if="importPreview.mode === 'insert'">
          共 {{ importPreview.total }} 行：预计新增 {{ importPreview.to_insert }}、预计跳过
          {{ importPreview.error_rows }} 行<template v-if="importPreview.conflicts">（其中主键已存在
            {{ importPreview.conflicts }} 行）</template>（预览不写库）
        </div>
        <div v-else>
          共 {{ importPreview.total }} 行：预计新增 {{ importPreview.to_insert }}、更新
          {{ importPreview.to_update }}<template v-if="importPreview.conflicts">（其中主键已存在
            {{ importPreview.conflicts }} 行）</template>、错误
          {{ importPreview.error_rows }} 行（预览不写库）
        </div>
        <ul v-if="importPreview.errors.length" class="import-preview-errors">
          <li v-for="err in importPreview.errors.slice(0, 10)" :key="err.row">
            第 {{ err.row }} 行：{{ err.error }}
          </li>
        </ul>
        <!-- INT-UX-02：被忽略的列不算错误行（那一行照样会写），但仍要提示，否则警告就丢了 -->
        <ul v-if="importPreview.notices?.length" class="import-preview-notices">
          <li v-for="n in importPreview.notices.slice(0, 10)" :key="n.row">
            第 {{ n.row }} 行：{{ n.message }}
          </li>
        </ul>
      </div>
      <!-- M49：执行导入后的逐行失败明细。此前 errors 被整个丢弃、界面只说一句「导入完成」，
           坏行就这么无声地没进库 -->
      <div v-if="importResult && importResult.errors && importResult.errors.length" class="import-preview">
        <div>
          本次实际写入：新增 {{ importResult.inserted }}、更新 {{ importResult.updated ?? 0 }}；
          未写入 {{ importResult.skipped || 0 }} 行，其中 {{ importResult.errors.length }} 行给出了原因：
        </div>
        <ul class="import-preview-errors">
          <li v-for="err in importResult.errors.slice(0, 20)" :key="err.row">
            第 {{ err.row }} 行：{{ err.error }}
          </li>
        </ul>
        <div v-if="importResult.errors.length > 20">
          仅显示前 20 行，共 {{ importResult.errors.length }} 行有错误
        </div>
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
import { PANEL_PAGE_SIZE_OPTIONS } from '../../constants/pagination'
import ListLoadError from '../../components/ListLoadError.vue'
import AuditTrail from '../../components/AuditTrail.vue'

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
// M20：时间戳列（后端 auto_maintained）由 server_default / onupdate 维护。
// 它们在表单里保留可见，但一律禁用输入并在提交时整列剔除——
// 编辑回写会把 isoformat() 的 `T` 分隔串写进库里，破坏按字符串比较的保留天数清理与排序；
// 新增时把未填的空串写进 DATETIME 列同样是坏数据。
const isAutoMaintained = (col) => !!col.auto_maintained
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
// 提交被拒后的字段级错误：{ 列名: 说明 }，来自后端信封 data.errors
const fieldErrors = ref({})

const schemaDialogVisible = ref(false)
const auditDialogVisible = ref(false)
const auditLogs = ref([])

const importDialogVisible = ref(false)
const importFormat = ref('csv')
// M50：CSV/JSON 各用各的输入框。共用一份时，切到另一种格式会把上一段文本
// 按新格式再解析——CSV 在 JSON 页报解析失败，JSON 在 CSV 页则可能切成垃圾行
const importCsvContent = ref('')
const importJsonContent = ref('')
const importContent = computed(() =>
  importFormat.value === 'json' ? importJsonContent.value : importCsvContent.value,
)
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
  fieldErrors.value = {}
  formDialogVisible.value = true
}

function openEditDialog(row) {
  formMode.value = 'edit'
  // 深拷贝行数据，避免直接修改原数据
  formData.value = { ...row }
  originalForm.value = { ...row }
  fieldErrors.value = {}
  // 记录主键值（用于更新接口）
  const pkCol = columns.value.find((c) => c.primary_key)
  editingPkValue.value = pkCol ? String(row[pkCol.name]) : null
  formDialogVisible.value = true
}

const MASK_SENTINEL_RE = /^\*{2,}$/

// T02827：脱敏值不是脏数据。ai_config 里这两族行各有专用配置入口，提示直接给出
// 可点跳转——否则操作者只能猜菜单，现实路径往往是手工清库重填（更危险）。
// 路由用页面路径而非 /news 前缀：base 由 router 统一处理，dev/prod 都指向同一页。
const CONFIG_ENTRY_LINKS = [
  { to: '/notification', label: '通知设置', match: ['notify'] },
  { to: '/ai-config', label: 'AI 服务配置', match: ['llm', 'preset', 'tts', 'asr'] },
]

const isMaskedValue = (val) => typeof val === 'string' && MASK_SENTINEL_RE.test(val.trim())

// 后端拒绝哨兵回写的文案（_mask_field_message）固定带这两个词之一
const isMaskWritebackError = (msg) => /脱敏|专用配置入口/.test(String(msg ?? ''))

function dedicatedEntries(row) {
  if (selectedTable.value !== 'ai_config') return []
  const key = String(row?.config_key ?? '').toLowerCase()
  if (!key) return []
  return CONFIG_ENTRY_LINKS.filter((entry) => entry.match.some((m) => key.includes(m)))
}

// 编辑弹窗里 formData 带着 config_key，按行判定该去哪个专用入口
const maskedEntries = computed(() => dedicatedEntries(formData.value))

function sensitiveCellTooltip(row) {
  const labels = dedicatedEntries(row).map((entry) => `「${entry.label}」`)
  if (labels.length) {
    return `脱敏显示，不是脏数据；原文请到${labels.join('或')}查看/修改，在此保存 *** 会被拒绝`
  }
  return '脱敏显示，不是脏数据；请留空保持原值，*** 不能写回数据库'
}

// 界面不提交的列：主键（用 WHERE 定位）、敏感列（脱敏值回写会覆盖真实凭据）、
// 以及系统维护的时间戳列（M20：isoformat() 的 `T` 分隔串回写会破坏按字符串比较的清理与排序）
function nonSubmitColumns() {
  return new Set(
    columns.value
      .filter((c) => c.primary_key || c.sensitive || c.auto_maintained)
      .map((c) => c.name),
  )
}

// 编辑时只提交变化过的字段：整行回传会把后端下发的 *** 脱敏值写回真实凭据列
function buildDirtyValues() {
  const skip = nonSubmitColumns()
  const payload = {}
  for (const [name, value] of Object.entries(formData.value)) {
    if (skip.has(name)) continue
    if (typeof value === 'string' && MASK_SENTINEL_RE.test(value.trim())) continue
    if (String(originalForm.value[name] ?? '') === String(value ?? '')) continue
    payload[name] = value
  }
  return payload
}

// M20：新增同样剔除时间戳列——没填就是空串，把空串写进 DATETIME 列同样是坏数据，
// 该由 server_default 负责填「当下」
function buildCreateValues() {
  const skip = nonSubmitColumns()
  const payload = {}
  for (const [name, value] of Object.entries(formData.value)) {
    if (skip.has(name)) continue
    payload[name] = value
  }
  return payload
}

async function submitForm() {
  try {
    if (formMode.value === 'create') {
      await createRow(selectedTable.value, buildCreateValues())
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
    // 后端给出字段级明细时（INT-UX-01），逐栏标在输入框下方；只有一句中文时维持原状
    const entries = e?.payload?.errors
    fieldErrors.value = Array.isArray(entries)
      ? Object.fromEntries(entries.filter((x) => x?.field).map((x) => [x.field, x.message || '该字段保存被拒绝']))
      : {}
    console.warn('submitForm failed:', e)
  }
}

// ---- 删除（含级联预览 + 表名确认） ----
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
// M49：执行导入后保留后端返回的逐行失败明细（此前只拼一句 toast 就丢弃）
const importResult = ref(null)
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

// M49：重新打开导入弹窗要先清掉上一次的失败明细，
// 否则这次的「未写入 N 行」说的其实是上一批粘贴内容
function openImportDialog() {
  importResult.value = null
  importDialogVisible.value = true
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
    // M49：后端逐行返回 errors:[{row,error}]，此前只取 inserted/skipped 拼一句「导入完成」，
    // 用户永远看不到哪一行因何失败；skipped 还混装了「主键冲突跳过 / 非法行 / 列名不匹配」
    // 三种语义。有行没写进去时不再声称导入完成，明细留在面板里，粘贴内容也不清空。
    importResult.value = result
    await loadRows()
    // T03603：skipped 已经包含错误行（后端每条错误分支都同时 +1），再加 errors.length
    // 就是把同一行数两遍——1 行失败曾报「未写入 2 行」，与下方面板的「未写入 1 行」同屏矛盾。
    const dropped = result.skipped || 0
    if (dropped) {
      ElMessage.warning(
        `导入未全部成功：新增 ${result.inserted}，未写入 ${dropped} 行，明细见下方`,
      )
      return
    }
    ElMessage.success(`导入完成：新增 ${result.inserted}，更新 ${result.updated ?? 0}`)
    importDialogVisible.value = false
    importCsvContent.value = ''
    importJsonContent.value = ''
    importPreview.value = null
    importResult.value = null
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

// T02827：脱敏字段的「去哪里改」提示（编辑弹窗内，带可点跳转）
.mask-hint {
  display: block;
  font-size: 12px;
  color: $color-text-secondary;
  margin-left: 8px;
  line-height: 1.6;

  &__link {
    color: $color-primary;
    text-decoration: underline;
    margin: 0 2px;
  }
}

.field-error {
  display: block;
  font-size: 12px;
  color: $color-danger;
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
