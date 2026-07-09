<template>
  <div class="page-container workflow-list">
    <!-- 顶部操作区：标题 + 手动触发按钮（仅 admin 可见） -->
    <div class="top-bar">
      <span class="page-title">工作流监控</span>
      <el-button
        v-if="userStore.isAdmin"
        type="primary"
        :icon="VideoPlay"
        :loading="triggering"
        @click="handleTrigger"
      >
        手动触发
      </el-button>
    </div>

    <!-- 工作流列表 -->
    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="工作流 ID" width="180">
          <template #default="{ row }">
            <!-- 点击跳详情：使用 replace 避免列表页堆积历史 -->
            <el-link type="primary" @click="goDetail(row.id)">{{ row.id }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="episode_date" label="节目日期" width="130" />
        <el-table-column prop="source" label="来源" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.source === 'cron' ? 'info' : 'warning'">
              {{ row.source === 'cron' ? '定时' : '手动' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" min-width="170" />
        <el-table-column prop="finished_at" label="结束时间" min-width="170" />
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadList"
          @current-change="loadList"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'
import api from '../../api'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const triggering = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)

// 状态到 el-tag 类型的映射：保持与 UI 语义一致（橙/绿/红/灰）
const STATUS_TAG_MAP = {
  running: 'warning',
  success: 'success',
  failed: 'danger',
  cancelled: 'info',
}
const STATUS_LABEL_MAP = {
  running: '运行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}
function statusTagType(s) {
  return STATUS_TAG_MAP[s] || 'info'
}
function statusLabel(s) {
  return STATUS_LABEL_MAP[s] || s
}

async function loadList() {
  loading.value = true
  try {
    const data = await api.get('/workflows', { params: { page: page.value, size: size.value } })
    list.value = data.list || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

async function handleTrigger() {
  // 二次确认：手动触发会真实消耗资源（爬虫/LLM/TTS）
  await ElMessageBox.confirm('确认立即触发一期新闻工作流？', '提示', { type: 'warning' })
  triggering.value = true
  try {
    const data = await api.post('/workflows/trigger')
    ElMessage.success(`已触发，工作流 ID: ${data.workflow_id}`)
    // 触发后回到第一页查看最新记录
    page.value = 1
    await loadList()
  } finally {
    triggering.value = false
  }
}

function goDetail(id) {
  router.push(`/workflows/${id}`)
}

onMounted(loadList)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.workflow-list {
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

  .pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
