<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useXxxStore } from '@/stores/xxx'
import { getXxxList, getXxxDetail, createXxx, updateXxx, deleteXxx } from '@/api/xxx'
import type { XxxItem } from '@/types'

const store = useXxxStore()
const loading = ref(false)
const tableData = ref<XxxItem[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增')
const formData = ref<Partial<XxxItem>>({})
const formRef = ref()

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
})

const isEdit = computed(() => !!formData.value.id)

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getXxxList({
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    tableData.value = res.data.items
    pagination.value.total = res.data.total
  } catch (err: any) {
    ElMessage.error(err.message || '加载失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增'
  formData.value = {}
  dialogVisible.value = true
}

const handleEdit = (row: XxxItem) => {
  dialogTitle.value = '编辑'
  formData.value = { ...row }
  dialogVisible.value = true
}

const handleDelete = async (row: XxxItem) => {
  try {
    await ElMessageBox.confirm(`确定删除 "${row.title}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await deleteXxx(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消或请求失败
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    
    if (isEdit.value) {
      await updateXxx(formData.value.id!, formData.value)
      ElMessage.success('更新成功')
    } else {
      await createXxx(formData.value as XxxItem)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    fetchData()
  } catch (err: any) {
    if (err.message) {
      ElMessage.error(err.message || '操作失败')
    }
  }
}

const handlePageChange = (page: number) => {
  pagination.value.current = page
  fetchData()
}

const handleSizeChange = (size: number) => {
  pagination.value.pageSize = size
  pagination.value.current = 1
  fetchData()
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="xxx-page">
    <!-- 工具栏 -->
    <div class="page-toolbar">
      <el-button type="primary" @click="handleAdd">新增</el-button>
    </div>

    <!-- 表格 -->
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="pagination.current"
      v-model:page-size="pagination.pageSize"
      :total="pagination.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @current-change="handlePageChange"
      @size-change="handleSizeChange"
      class="page-pagination"
    />

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      :close-on-click-modal="false"
      @closed="formData = {}"
    >
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="formData.title" placeholder="请输入标题" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch
            v-model="formData.status"
            active-value="active"
            inactive-value="inactive"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.xxx-page {
  padding: 20px;
}

.page-toolbar {
  margin-bottom: 16px;
}

.page-pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
