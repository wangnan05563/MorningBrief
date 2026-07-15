<template>
  <div class="review-list page-container" v-loading="loading">
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="待审核" name="pending" />
      <el-tab-pane label="已通过" name="approved" />
      <el-tab-pane label="已打回" name="rejected" />
    </el-tabs>

    <el-table :data="list" stripe class="list-table">
      <el-table-column prop="episode_date" label="日期" width="140" />
      <el-table-column prop="workflow_id" label="工作流ID" min-width="160" />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" effect="light">
            {{ statusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="200">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="goReview(row.id)">审核</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="prev, pager, next, total"
        background
        @current-change="loadList"
      />
    </div>
  </div>
</template>

<script setup>
/**
 * 审核列表页：按状态分 tab 展示稿件
 *
 * 设计要点：
 * - tab 与分页联动：切换 tab 时重置到第一页，避免停留在不存在的页码
 * - 状态映射到 el-tag 颜色，直观区分审核进度
 * - 列表数据由后端按 status 过滤返回，前端不做本地过滤
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api'
import { formatTime } from '../../utils/format'

const router = useRouter()

const loading = ref(false)
const activeTab = ref('pending')
const list = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(10)

async function loadList() {
  loading.value = true
  try {
    const data = await api.get('/reviews', {
      params: { status: activeTab.value, page: page.value, size: size.value },
    })
    list.value = data.list
    total.value = data.total
  } catch {
    // 错误提示由拦截器统一处理
  } finally {
    loading.value = false
  }
}

// 切换 tab 重置分页再加载
function handleTabChange() {
  page.value = 1
  loadList()
}

function goReview(id) {
  router.push(`/review/${id}`)
}

function statusTagType(status) {
  return { pending: 'warning', approved: 'success', rejected: 'danger' }[status] || 'info'
}

function statusText(status) {
  return { pending: '待审核', approved: '已通过', rejected: '已打回' }[status] || status
}

onMounted(loadList)
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.list-table {
  margin-top: 8px;
  border-radius: $radius-lg;
  overflow: hidden;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
