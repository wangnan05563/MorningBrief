<template>
  <div class="page-container channel-management">
    <!-- 工具栏：标题 + 新增按钮（仅 admin 可见） -->
    <div class="top-bar">
      <span class="page-title">频道管理</span>
      <el-button v-if="canOperate" type="primary" :icon="Plus" @click="openCreate">新增频道</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <!-- 用 v-model 直接绑定，失败时手动回滚，保证 UI 即时反馈 -->
            <el-switch
              v-model="row.is_active"
              :disabled="!canOperate"
              @change="(val) => handleToggle(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="170">
          <template #default="{ row }">{{ row.created_at || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="canOperate" label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" :loading="deletingIds.has(row.id)" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗：复用同一 Dialog，通过 editing 标志区分 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑频道' : '新增频道'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入频道名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="频道描述（选填）" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'ChannelManagement' })
import { ref, reactive, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { ElMessage } from '../../utils/message'
import { Plus } from '@element-plus/icons-vue'
import { listChannels, createChannel, updateChannel, deleteChannel } from '../../api/channels'

// 角色控制：直接读 localStorage，operator 隐藏增删改操作
const role = localStorage.getItem('admin_role') || ''
const canOperate = role === 'admin'

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref(false)
const submitting = ref(false)
const formRef = ref()

// 行级删除按钮 loading（P1-2.2 防重复点击）
const deletingIds = ref(new Set())

const form = reactive({
  id: null,
  name: '',
  description: '',
  is_active: true,
})

const rules = {
  name: [{ required: true, message: '请输入频道名称', trigger: 'blur' }],
}

async function loadList() {
  loading.value = true
  try {
    const data = await listChannels(false)
    // 兼容后端返回数组或 { list } 两种结构
    list.value = Array.isArray(data) ? data : (data.list || [])
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  form.id = null
  form.name = ''
  form.description = ''
  form.is_active = true
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = true
  form.id = row.id
  form.name = row.name
  form.description = row.description || ''
  form.is_active = !!row.is_active
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      description: form.description,
      is_active: form.is_active,
    }
    if (editing.value) {
      await updateChannel(form.id, payload)
      ElMessage.success('已更新')
    } else {
      await createChannel(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await loadList()
  } finally {
    submitting.value = false
  }
}

async function handleToggle(row, val) {
  try {
    await updateChannel(row.id, { is_active: val })
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch {
    // 请求失败时回滚 switch 状态，保持 UI 与后端一致
    row.is_active = !val
  }
}

async function handleDelete(row) {
  // 防重复点击：同一行删除中直接忽略
  if (deletingIds.value.has(row.id)) return
  try {
    await ElMessageBox.confirm(`确认删除频道「${row.name}」？此操作不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
    })
  } catch {
    // 用户取消确认，静默退出
    return
  }
  deletingIds.value.add(row.id)
  try {
    await deleteChannel(row.id)
    ElMessage.success('已删除')
    await loadList()
  } catch (e) {
    console.warn('handleDelete failed:', e)
  } finally {
    deletingIds.value.delete(row.id)
  }
}

onMounted(() => {
  loadList()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.channel-management {
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: $color-text-primary;
    }
  }
}
</style>
