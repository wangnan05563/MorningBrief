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
          <IconButton
            label="上传文件"
            desc="上传文件到当前目录"
            :icon="Upload"
            :disabled="!configured"
            @click="triggerUpload"
          />
          <IconButton
            label="新建文件夹"
            desc="在当前目录新建文件夹"
            :icon="Plus"
            :disabled="!configured"
            @click="openNewFolder"
          />
          <IconButton
            label="刷新"
            desc="重新加载当前目录列表"
            :icon="Refresh"
            :loading="loading"
            @click="loadList"
          />
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
              <el-tooltip :content="row.name" placement="top" :fallback-placements="['bottom', 'left', 'right']">
                <span :class="{ 'is-folder': row.isFolder }">{{ row.name }}</span>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sizeText" label="大小" width="140" />
        <el-table-column prop="last_modified" label="最后修改" width="200" />
        <el-table-column prop="content_type" label="类型" width="160" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <IconButton
              v-if="!row.isFolder"
              type="primary"
              link
              label="下载"
              desc="下载该文件"
              :icon="Download"
              @click="handleDownload(row)"
            />
            <IconButton
              type="primary"
              link
              label="重命名"
              desc="重命名或移动该对象"
              :icon="Edit"
              @click="openRename(row)"
            />
            <IconButton
              type="danger"
              link
              label="删除"
              desc="删除该对象"
              :icon="Delete"
              @click="handleDelete(row)"
            />
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
        <IconButton
          label="取消"
          desc="关闭对话框"
          :icon="Close"
          @click="newFolderVisible = false"
        />
        <IconButton
          type="primary"
          :loading="opLoading"
          label="确定"
          desc="创建该文件夹"
          :icon="Check"
          @click="confirmNewFolder"
        />
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
        <IconButton
          label="取消"
          desc="关闭对话框"
          :icon="Close"
          @click="renameVisible = false"
        />
        <IconButton
          type="primary"
          :loading="opLoading"
          label="确定"
          desc="确认重命名"
          :icon="Check"
          @click="confirmRename"
        />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  Upload, FolderOpened, Refresh, Download, Edit, Delete, Document,
  Plus, Close, Check,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { dangerConfirm } from '../../utils/dangerConfirm'
import {
  getCosStatus,
  listCosObjects,
  uploadCosFile,
  checkCosObject,
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
    const targetKey = currentPrefix.value + file.name
    // 同名检测以服务端 HEAD 为准（列表是进入目录时的快照，可能已过期）。
    // 检测失败就中止：不知道会不会覆盖时不允许盲传（FR-UX-205 / H9）
    let exists = false
    let hit = null
    try {
      hit = await checkCosObject(targetKey)
      exists = !!hit?.exists
    } catch {
      ElMessage.error('同名检测失败，已取消上传：无法确认是否会覆盖已有文件')
      return
    }
    if (exists) {
      const ok = await dangerConfirm({
        action: '上传并覆盖同名文件',
        target: `${currentPrefix.value || '/'}${file.name}`,
        scope: `云端已存在同名对象（${formatSize(hit.size)}${hit.last_modified ? `，更新于 ${hit.last_modified}` : ''}）`,
        lines: [
          `覆盖前旧文件自动备份到 ${currentPrefix.value}.backup/<时间戳>/${file.name}，可在文件列表逐层找回`,
        ],
        irreversible: '快照只保留覆盖前的那一份：如需长期保留多版本请为存储桶开启版本控制。',
        confirmWord: '覆盖',
        confirmLabel: '确认覆盖上传',
      })
      if (!ok) return
    }
    // overwrite 由服务端把关：绕过本页直接调接口时，同名上传会被拒绝而不是静默覆盖
    let result
    try {
      result = await uploadCosFile(file, currentPrefix.value, { overwrite: exists })
    } catch {
      // 服务端同名检测兜底命中（业务码 409）等错误，全局拦截器已给出可读提示
      return
    }
    ElMessage.success(
      result?.backup_key
        ? `已覆盖 ${file.name}，旧文件已备份至 ${result.backup_key}`
        : `已上传 ${file.name}`,
    )
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
