<template>
  <div class="page-container cos-files">
    <!-- 顶部状态 / 工具栏 -->
    <div class="top-bar">
      <el-alert
        v-if="!configured"
        type="warning"
        :closable="false"
        show-icon
        title="COS 尚未配置"
        description="请先在「云端配置」页填写 SecretId / SecretKey / Bucket 后再管理云端文件。"
        style="flex: 1; margin-right: 12px"
      />
      <template v-else>
        <div class="path-bar">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>
              <el-link type="primary" underline="never" @click="navigateTo('')">桶根</el-link>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-for="(seg, idx) in pathSegments" :key="idx">
              <el-link
                v-if="idx < pathSegments.length - 1"
                type="primary"
                underline="never"
                @click="navigateToSegment(idx)"
              >{{ seg }}</el-link>
              <span v-else>{{ seg }}</span>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <el-button-group style="margin-left: 12px">
          <el-button :icon="Upload" :disabled="!configured" @click="triggerUpload">上传文件</el-button>
          <el-button :icon="FolderAdd" :disabled="!configured" @click="openNewFolder">新建文件夹</el-button>
          <el-button :icon="Refresh" :loading="loading" @click="loadList">刷新</el-button>
        </el-button-group>
        <input
          ref="fileInput"
          type="file"
          style="display: none"
          @change="handleFileSelected"
        />
      </template>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-empty v-if="configured && !loading && folders.length === 0 && files.length === 0" description="该目录下暂无内容" />

      <el-table v-else :data="tableData" stripe style="width: 100%">
        <el-table-column label="名称" min-width="280">
          <template #default="{ row }">
            <div class="name-cell" @click="row.isFolder ? enterFolder(row) : null">
              <el-icon v-if="row.isFolder" class="name-icon folder"><FolderOpened /></el-icon>
              <el-icon v-else class="name-icon"><Document /></el-icon>
              <span :class="{ 'is-folder': row.isFolder }">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sizeText" label="大小" width="140" />
        <el-table-column prop="last_modified" label="最后修改" width="200" />
        <el-table-column prop="content_type" label="类型" width="160" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.isFolder"
              type="primary"
              link
              :icon="Download"
              @click="handleDownload(row)"
            >下载</el-button>
            <el-button
              type="primary"
              link
              :icon="Edit"
              @click="openRename(row)"
            >重命名</el-button>
            <el-button
              type="danger"
              link
              :icon="Delete"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建文件夹对话框 -->
    <el-dialog v-model="newFolderVisible" title="新建文件夹" width="420px">
      <el-form label-width="80px">
        <el-form-item label="文件夹名">
          <el-input v-model="newFolderName" placeholder="请输入文件夹名称（不含 /）" @keyup.enter="confirmNewFolder" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newFolderVisible = false">取消</el-button>
        <el-button type="primary" :loading="opLoading" @click="confirmNewFolder">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重命名 / 移动对话框 -->
    <el-dialog v-model="renameVisible" title="重命名 / 移动" width="460px">
      <el-form label-width="80px">
        <el-form-item label="原名称">
          <el-input :model-value="renameTarget?.name" disabled />
        </el-form-item>
        <el-form-item label="新名称">
          <el-input
            v-model="renameNewName"
            :placeholder="renameTarget?.isFolder ? '新文件夹名（不含 /）' : '新文件名'"
            @keyup.enter="confirmRename"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :loading="opLoading" @click="confirmRename">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  Upload, FolderAdd, FolderOpened, Refresh, Download, Edit, Delete, Document,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import {
  getCosStatus,
  listCosObjects,
  uploadCosFile,
  getCosDownloadUrl,
  deleteCosObject,
  createCosFolder,
  deleteCosFolder,
  moveCosObject,
} from '../../api/cos'

const loading = ref(false)
const opLoading = ref(false)
const configured = ref(false)
const currentPrefix = ref('')
const folders = ref([])
const files = ref([])
const fileInput = ref(null)

// 对话框状态
const newFolderVisible = ref(false)
const newFolderName = ref('')
const renameVisible = ref(false)
const renameTarget = ref(null)
const renameNewName = ref('')

// 面包屑分段（去掉尾随 /）
const pathSegments = computed(() => {
  const p = currentPrefix.value
  if (!p) return []
  return p.replace(/\/$/, '').split('/').filter(Boolean)
})

// 表格数据：文件夹在前，文件在后
const tableData = computed(() => {
  const f = folders.value.map((name) => ({
    key: currentPrefix.value + name,
    name,
    isFolder: true,
    sizeText: '-',
    last_modified: '',
    content_type: '文件夹',
  }))
  const fi = files.value.map((item) => ({
    key: item.key,
    name: item.name,
    isFolder: false,
    size: item.size,
    sizeText: formatSize(item.size),
    last_modified: item.last_modified,
    content_type: item.content_type || '-',
  }))
  return [...f, ...fi]
})

function formatSize(bytes) {
  if (bytes === undefined || bytes === null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

async function loadStatus() {
  try {
    const st = await getCosStatus()
    configured.value = !!(st && st.configured)
  } catch (e) {
    configured.value = false
  }
}

async function loadList() {
  if (!configured.value) return
  loading.value = true
  try {
    const data = await listCosObjects(currentPrefix.value)
    folders.value = data.folders || []
    files.value = data.files || []
  } catch (e) {
    // 全局拦截器已提示
  } finally {
    loading.value = false
  }
}

// 进入文件夹
function enterFolder(row) {
  currentPrefix.value = row.key // row.key 已是完整前缀（以 / 结尾）
  loadList()
}

// 点击面包屑某段跳转（idx 为该段索引）
function navigateToSegment(idx) {
  const segs = pathSegments.value.slice(0, idx + 1)
  currentPrefix.value = segs.length ? segs.join('/') + '/' : ''
  loadList()
}

// 回到桶根
function navigateTo() {
  currentPrefix.value = ''
  loadList()
}

// 上传
function triggerUpload() {
  fileInput.value?.click()
}
async function handleFileSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  opLoading.value = true
  try {
    await uploadCosFile(file, currentPrefix.value)
    ElMessage.success(`已上传 ${file.name}`)
    await loadList()
  } finally {
    opLoading.value = false
    e.target.value = '' // 允许重复选择同名文件
  }
}

// 新建文件夹
function openNewFolder() {
  newFolderName.value = ''
  newFolderVisible.value = true
}
async function confirmNewFolder() {
  const name = (newFolderName.value || '').trim()
  if (!name || name.includes('/')) {
    ElMessage.warning('文件夹名不能为空且不能包含 /')
    return
  }
  opLoading.value = true
  try {
    await createCosFolder(currentPrefix.value + name + '/')
    ElMessage.success('文件夹已创建')
    newFolderVisible.value = false
    await loadList()
  } finally {
    opLoading.value = false
  }
}

// 重命名 / 移动
function openRename(row) {
  renameTarget.value = row
  renameNewName.value = row.name
  renameVisible.value = true
}
async function confirmRename() {
  const row = renameTarget.value
  if (!row) return
  const newName = (renameNewName.value || '').trim()
  if (!newName) {
    ElMessage.warning('新名称不能为空')
    return
  }
  // 仅支持同级重命名（文件名/文件夹名变更），保持前缀不变
  const destKey = currentPrefix.value + newName + (row.isFolder ? '/' : '')
  if (destKey === row.key) {
    renameVisible.value = false
    return
  }
  opLoading.value = true
  try {
    await moveCosObject(row.key, destKey)
    ElMessage.success('重命名成功')
    renameVisible.value = false
    await loadList()
  } finally {
    opLoading.value = false
  }
}

// 删除
async function handleDelete(row) {
  const isFolder = row.isFolder
  try {
    await ElMessageBox.confirm(
      `确认删除${isFolder ? '文件夹' : '文件'}「${row.name}」${isFolder ? '及其下所有内容' : ''}？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  opLoading.value = true
  try {
    if (isFolder) {
      await deleteCosFolder(row.key)
    } else {
      await deleteCosObject(row.key)
    }
    ElMessage.success('已删除')
    await loadList()
  } finally {
    opLoading.value = false
  }
}

// 下载
async function handleDownload(row) {
  try {
    const data = await getCosDownloadUrl(row.key)
    const url = data?.url
    if (!url) {
      ElMessage.error('获取下载链接失败')
      return
    }
    window.open(url, '_blank')
  } catch (e) {
    // 全局拦截器已提示
  }
}

onMounted(async () => {
  await loadStatus()
  if (configured.value) await loadList()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.cos-files {
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .path-bar {
    flex: 1;
    display: flex;
    align-items: center;
    background: $color-bg-card;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 8px 14px;
    overflow-x: auto;
  }

  .name-cell {
    display: flex;
    align-items: center;
    cursor: default;

    .name-icon {
      margin-right: 8px;
      color: $color-primary;

      &.folder {
        color: #e6a23c;
      }
    }

    .is-folder {
      color: $color-primary-dark;
      cursor: pointer;
      font-weight: 600;

      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>
