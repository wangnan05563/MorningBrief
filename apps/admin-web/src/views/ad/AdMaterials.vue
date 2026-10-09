<template>
  <div class="page-container ad-materials">
    <!-- 顶部工具栏：主操作按钮（T00811：移除与导航栏重复的页面标题） -->
    <div class="toolbar">
      <IconButton
        type="primary"
        label="新增素材"
        desc="打开新增素材对话框"
        :icon="Plus"
        @click="openCreateDialog"
      />
    </div>

    <!-- 表格卡片化：复用全局 .card-soft 保持视觉一致 -->
    <div class="card-soft table-card">
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column
          prop="description"
          label="描述"
          min-width="200"
          show-overflow-tooltip
        />
        <el-table-column prop="duration" label="时长(秒)" width="100" align="center" />
        <el-table-column label="默认占位" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <IconButton
              link
              type="primary"
              label="试听"
              desc="播放该素材音频"
              :icon="VideoPlay"
              @click="playAudio(row)"
            />
            <IconButton
              link
              type="danger"
              :disabled="row.is_default"
              label="删除"
              desc="删除该素材"
              :icon="Delete"
              @click="handleDelete(row)"
            />
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无广告素材，点击右上角「新增素材」上传" :image-size="90" /></template>
      </el-table>

      <!-- 分页：素材量可能较大，必须支持分页 -->
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

    <!-- 新增素材对话框：后端要求 JSON 提交 file_url+duration，而非 multipart 文件上传 -->
    <el-dialog v-model="dialogVisible" title="新增素材" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input
            v-model="form.name"
            placeholder="请输入素材名称"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="可选，素材描述"
          />
        </el-form-item>
        <el-form-item label="文件URL" prop="file_url">
          <el-input v-model="form.file_url" placeholder="音频文件的访问地址" />
        </el-form-item>
        <el-form-item label="时长(秒)" prop="duration">
          <el-input-number
            v-model="form.duration"
            :min="1"
            :max="3600"
            controls-position="right"
          />
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
          desc="提交新增素材"
          :icon="Check"
          @click="handleSubmit"
        />
      </template>
    </el-dialog>

    <!-- 隐藏的 audio 元素：通过 ref 控制 src 和播放，避免页面上出现多个原生播放器 -->
    <audio ref="audioRef" style="display: none"></audio>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { Plus, VideoPlay, Delete, Close, Check } from '@element-plus/icons-vue'

import api from '../../api'

const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)

const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref()
const audioRef = ref()

const form = reactive({
  name: '',
  description: '',
  file_url: '',
  duration: 10,
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  file_url: [{ required: true, message: '请输入文件URL', trigger: 'blur' }],
  duration: [{ required: true, message: '请输入时长', trigger: 'blur' }],
}

async function fetchList() {
  loading.value = true
  try {
    const data = await api.get('/ads/materials', {
      params: { page: page.value, size: size.value },
    })
    tableData.value = data.list || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  // 重置表单，避免上次输入残留污染本次提交
  Object.assign(form, { name: '', description: '', file_url: '', duration: 10 })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    await api.post('/ads/materials', { ...form })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  // 删除是不可逆操作，需二次确认避免误触
  await ElMessageBox.confirm(`确认删除素材「${row.name}」？`, '提示', {
    type: 'warning',
  })
  await api.delete(`/ads/materials/${row.id}`)
  ElMessage.success('删除成功')
  fetchList()
}

function playAudio(row) {
  const audio = audioRef.value
  if (!audio) return
  // 复用同一个 audio 元素：每次设置 src 后重新加载并播放
  audio.src = row.file_url
  audio.play().catch(() => {
    ElMessage.warning('音频播放失败，请检查文件URL')
  })
}

onMounted(fetchList)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.ad-materials {
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

  .text-muted {
    color: $color-text-secondary;
  }
}
</style>
