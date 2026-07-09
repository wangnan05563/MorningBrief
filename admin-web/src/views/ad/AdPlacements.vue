<template>
  <div class="page-container ad-placements">
    <div class="toolbar">
      <h2 class="page-title">投放规则管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>
        <span>新建投放</span>
      </el-button>
    </div>

    <div class="card-soft table-card">
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="material_name" label="素材名称" min-width="160" />
        <el-table-column label="广告位" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="positionTagType(row.position)" size="small">
              {{ positionLabel(row.position) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="140" align="center" />
        <el-table-column prop="end_date" label="结束日期" width="140" align="center" />
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
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
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="素材" prop="material_id">
          <el-select
            v-model="form.material_id"
            placeholder="请选择素材"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="m in materialOptions"
              :key="m.id"
              :label="m.name"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="广告位" prop="position">
          <el-select
            v-model="form.position"
            placeholder="请选择广告位"
            style="width: 100%"
          >
            <el-option label="开头" value="head" />
            <el-option label="中间" value="mid" />
            <el-option label="结尾" value="tail" />
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
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)

const materialOptions = ref([])
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  material_id: null,
  position: '',
  dateRange: [],
})

const rules = {
  material_id: [{ required: true, message: '请选择素材', trigger: 'change' }],
  position: [{ required: true, message: '请选择广告位', trigger: 'change' }],
  dateRange: [{ required: true, message: '请选择日期范围', trigger: 'change' }],
}

// 广告位中文映射：head/mid/tail 对应开头/中间/结尾
const POSITION_LABEL = { head: '开头', mid: '中间', tail: '结尾' }
// tag 颜色与排期日历的小标签视觉保持一致
const POSITION_TAG_TYPE = { head: 'success', mid: 'danger', tail: 'info' }

function positionLabel(p) {
  return POSITION_LABEL[p] || p
}
function positionTagType(p) {
  return POSITION_TAG_TYPE[p] || 'info'
}

async function fetchList() {
  loading.value = true
  try {
    const data = await api.get('/ads/placements', {
      params: { page: page.value, size: size.value },
    })
    tableData.value = data.list || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

// 加载素材选项：每次打开对话框都拉取，确保使用最新素材列表
async function fetchMaterials() {
  const data = await api.get('/ads/materials', {
    params: { page: 1, size: 100 },
  })
  materialOptions.value = data.list || []
}

async function openCreateDialog() {
  Object.assign(form, { material_id: null, position: '', dateRange: [] })
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

  .pagination-wrap {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
