<template>
  <div data-guide="ads-placements-page" class="page-container ad-placements">
    <div class="toolbar">
      <!-- T00811：移除与导航栏重复的页面标题，仅保留操作按钮 -->
      <!-- D13：后端一直下发 enabled，但列表既无状态列也无筛选——移动端停用的规则
           在 PC 列表里与生效规则完全同貌，运营据此判断「这条还在投」。 -->
      <el-select
        v-model="enabledFilter"
        data-guide="ads-enabled-filter"
        style="width: 140px"
        @change="onFilterChange"
      >
        <el-option label="全部状态" :value="''" />
        <el-option label="仅启用" :value="1" />
        <el-option label="仅停用" :value="0" />
      </el-select>
      <IconButton
        type="primary"
        label="新建投放"
        desc="打开新建投放对话框"
        :icon="Plus"
        @click="openCreateDialog"
      />
    </div>

    <div class="card-soft table-card">
      <el-table data-guide="ads-placements-table" :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="material_name" label="素材名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="广告位" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="positionTagType(row.position)" size="small">
              {{ positionLabel(row.position) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="140" align="center" />
        <el-table-column prop="end_date" label="结束日期" width="140" align="center" />
        <!-- D13/D14：状态列同时给出文字与开关——只看开关分不清左右哪边是「启用」，
             移动端停用的规则此前在 PC 里与生效规则完全同貌 -->
        <el-table-column label="状态" width="170" align="center">
          <template #default="{ row }">
            <div class="status-cell">
              <el-switch
                :model-value="row.enabled === 1"
                :loading="togglingIds.includes(row.id)"
                @update:model-value="(v) => handleToggle(row, v)"
              />
              <!-- T02602：状态由服务端按「开关 + 今天是否落在区间」派生，
                   待投放/已过期不再显示成「已启用」 -->
              <span class="status-text" :class="`status-text--${statusTone(row.status)}`">
                {{ statusLabel(row.status) }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <IconButton
              link
              type="danger"
              label="删除"
              desc="删除该投放规则"
              :icon="Delete"
              @click="handleDelete(row)"
            />
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无投放规则，点击右上角「新增规则」创建" :image-size="90" /></template>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </div>

    <!-- 新建投放对话框：日期范围选择后需拆分为 start_date / end_date 提交 -->
    <el-dialog v-model="dialogVisible" title="新建投放" width="500px">
      <!-- T02927：后端拒绝同位重叠时点名冲突对象，不能只留一句「保存失败」。
           拦截器已弹过 toast，这里把结构化 conflicts 落回表单内部，方便对照修改 -->
      <el-alert
        v-if="submitError"
        data-guide="ads-placement-conflict"
        class="submit-error"
        type="error"
        :closable="false"
        show-icon
      >
        <template #title>{{ submitError.title }}</template>
        <ul v-if="submitError.conflicts.length" class="conflict-list">
          <li v-for="c in submitError.conflicts" :key="c.id">
            素材「{{ c.material_name }}」（投放 #{{ c.id }}）{{ c.start_date }} ~ {{ c.end_date }}
          </li>
        </ul>
        <div v-if="submitError.conflicts.length" class="conflict-hint">
          请先停用或删除冲突投放，或调整本次日期区间
        </div>
      </el-alert>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="素材" prop="material_id">
          <!-- D16：改为服务端搜索（remote），并在下方如实显示「共 N 条」，
               避免「前 100 条之外不存在」被误读成「素材没上传成功」 -->
          <el-select
            v-model="form.material_id"
            placeholder="输入素材名称搜索（服务端检索）"
            filterable
            remote
            :remote-method="searchMaterials"
            :remote-show-suffix="true"
            :loading="materialSearching"
            style="width: 100%"
          >
            <el-option
              v-for="m in materialOptions"
              :key="m.id"
              :label="m.name"
              :value="m.id"
            />
          </el-select>
          <div class="material-count-hint">
            <template v-if="materialTotal > materialOptions.length">
              已显示 {{ materialOptions.length }} 条 / 素材库共 {{ materialTotal }} 条——请按名称搜索，或到「广告素材」页确认素材是否已上传
            </template>
            <template v-else>素材库共 {{ materialTotal }} 条</template>
          </div>
        </el-form-item>
        <el-form-item label="广告位" prop="position">
          <el-select
            v-model="form.position"
            placeholder="请选择广告位"
            style="width: 100%"
          >
            <el-option v-for="o in positionOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围" prop="dateRange">
          <el-date-picker
            v-model="form.dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 100%"
          />
          <!-- D15：把闭区间与单日投放口径写在界面上，否则运营只能靠试错猜规则 -->
          <div class="field-hint">区间含首尾（结束日当天仍会播放）；只投一天可让两个日期相同</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <IconButton
          label="取消"
          desc="关闭对话框"
          :icon="Close"
          @click="dialogVisible = false"
        />
        <IconButton
          type="primary"
          :loading="submitting"
          label="确定"
          desc="提交新建投放"
          :icon="Check"
          @click="handleSubmit"
        />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import { Plus, Delete, Close, Check } from '@element-plus/icons-vue'

import api from '../../api'
import { readBizError } from '../../api/bizError'
import { AD_POSITION, enumLabel, enumTagType, enumOptions } from '../../constants/enums'
import { placementStatusMeta } from '../../utils/placementStatus'

const positionOptions = enumOptions(AD_POSITION)

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)
// D13：'' = 全部状态，1 = 仅启用，0 = 仅停用
const enabledFilter = ref('')

const materialOptions = ref([])
const togglingIds = ref([])
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref()
// T02927：保存被拒时在对话框内展示后端点名的冲突投放（null = 无错误）
const submitError = ref(null)

const form = reactive({
  material_id: null,
  position: '',
  dateRange: [],
})

const rules = {
  material_id: [{ required: true, message: '请选择素材', trigger: 'change' }],
  position: [{ required: true, message: '请选择广告位', trigger: 'change' }],
  dateRange: [
    { required: true, message: '请选择日期范围', trigger: 'change' },
    // D15：日期区间是闭区间（结束日当天仍播放），允许同一天=单日投放。
    // 真正的错只有倒序，且必须用中文说清，不能把 start_date/end_date 原样弹给运营。
    {
      validator: (_rule, value, callback) => {
        const [start, end] = value || []
        if (!start || !end) return callback()
        if (start > end) return callback(new Error('结束日期不能早于开始日期；只投一天可让两者相同'))
        callback()
      },
      trigger: 'change',
    },
  ],
}

// 广告位文案/标签色取自 src/constants/enums.js，与排期日历同源（FR-UX-405 / T02504）
const positionLabel = (p) => enumLabel(AD_POSITION, p)
const positionTagType = (p) => enumTagType(AD_POSITION, p)

// T02602：四态文案与色调统一走 utils/placementStatus，与移动端/排期日历同源
const statusLabel = (status) => placementStatusMeta(status).label
const statusTone = (status) => placementStatusMeta(status).tone

async function fetchList() {
  loading.value = true
  try {
    const data = await api.get('/ads/placements', {
      params: {
        page: page.value,
        size: size.value,
        enabled: enabledFilter.value === '' ? undefined : enabledFilter.value,
      },
    })
    tableData.value = data.list || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

// 换筛选条件回到第 1 页，否则第 3 页筛完可能一条都没有（空页≠没有匹配项）
function onFilterChange() {
  page.value = 1
  fetchList()
}

// D16：素材下拉此前硬截断 page=1&size=100，第 101 条起的素材在列表里根本不存在，
// `filterable` 只能在已加载的 100 条内搜索，且没有任何提示 → 运营判定「素材没上传成功」。
// 改为服务端关键词搜索 + 回显总数，让「搜不到」和「没上传」可区分。
const materialTotal = ref(0)
const materialSearching = ref(false)

async function searchMaterials(keyword = '') {
  materialSearching.value = true
  try {
    const data = await api.get('/ads/materials', {
      params: { page: 1, size: 100, keyword: keyword || undefined },
    })
    materialOptions.value = data.list || []
    materialTotal.value = data.total || 0
  } finally {
    materialSearching.value = false
  }
}

// 加载素材选项：每次打开对话框都拉取，确保使用最新素材列表
async function fetchMaterials() {
  await searchMaterials('')
}

// 启停切换：先确认再发请求，失败回滚开关（后端提交后会清「生效投放」缓存，停用即时生效）
async function handleToggle(row, next) {
  const enabled = next ? 1 : 0
  const ok = await dangerConfirm({
    action: enabled === 0 ? '停用投放' : '启用投放',
    target: `${positionLabel(row.position)}位 · ${row.material_name || `投放 #${row.id}`}`,
    scope: `生效区间 ${row.start_date} ~ ${row.end_date}`,
    lines: [
      enabled === 0
        ? '停用后，之后新生成的节目不再插入该广告；生效投放缓存同步失效。'
        : '启用后，之后新生成的节目在排期区间内恢复插入。',
      '注意：已经生成好的节目里广告是拼在音频里的，停用不会把它们里面的广告去掉。',
    ],
    irreversible: '启停可随时回退，不影响已生成的节目数据。',
    confirmLabel: enabled === 0 ? '确认停用' : '确认启用',
  })
  if (!ok) return
  togglingIds.value = [...togglingIds.value, row.id]
  try {
    const data = await api.put(`/ads/placements/${row.id}`, { enabled })
    row.enabled = data.enabled
    // 状态由服务端派生后回传：重新启用一条「已过期」的投放不应显示成「生效中」（T02602）
    row.status = data.status
    ElMessage.success(enabled === 0 ? '已停用' : '已启用')
  } catch {
    // 请求失败保持原状态：开关由 :model-value 驱动，不写 row.enabled 即自动回弹
  } finally {
    togglingIds.value = togglingIds.value.filter((id) => id !== row.id)
  }
}

async function openCreateDialog() {
  Object.assign(form, { material_id: null, position: '', dateRange: [] })
  submitError.value = null
  await fetchMaterials()
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    // dateRange 是 [start, end] 数组，拆分为两个字段提交给后端
    const [start_date, end_date] = form.dateRange
    await api.post('/ads/placements', {
      material_id: form.material_id,
      position: form.position,
      start_date,
      end_date,
    })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchList()
  } catch (error) {
    // 后端按 INT-UX-01 回传 data.conflicts：在表单里点名「哪条投放占了同一广告位」，
    // 而不是把一句通用报错丢给运营去猜
    const biz = readBizError(error)
    const conflicts = biz?.data?.conflicts || []
    submitError.value = {
      title: conflicts.length
        ? '无法保存：该广告位在所选区间内已有启用中的投放'
        : biz?.message || '保存失败',
      conflicts,
    }
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm('确认删除该投放规则？', '提示', { type: 'warning' })
  await api.delete(`/ads/placements/${row.id}`)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(fetchList)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.ad-placements {
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .page-title {
      font-size: 20px;
      font-weight: 700;
      color: $color-text-primary;
    }
  }

  .table-card {
    padding: 16px;
  }

  .status-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .status-text {
    font-size: 12px;
    color: var(--el-color-success-dark, #529b2e);
  }

  // T02602：四态各自有色调——「待投放/已过期」不能和「生效中」同色
  .status-text--pending {
    color: #b88230;
  }

  .status-text--off,
  .status-text--expired {
    color: $color-text-secondary;
  }

  .pagination-wrap {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }

  .submit-error {
    margin-bottom: 16px;
  }

  .conflict-list {
    margin: 6px 0 0;
    padding-left: 18px;
    line-height: 1.8;
  }

  .conflict-hint {
    margin-top: 4px;
    font-size: 12px;
  }
}
</style>
