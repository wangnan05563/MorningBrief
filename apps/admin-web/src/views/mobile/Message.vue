<template>
  <div class="m-msg">
    <div class="m-msg__bar">
      <span class="m-msg__count">未读 {{ unreadCount }}</span>
      <button class="m-msg__action" :disabled="unreadCount === 0" @click="markAll">
        全部已读
      </button>
    </div>

    <div v-if="loading && list.length === 0" class="m-msg__empty">加载中…</div>
    <!-- T02517（B6 同源）：移动端也不能把「请求失败」渲染成「暂无消息」。
         失败时给出原因 + 重试入口，与 PC 列表页的 ListLoadError 同一口径。 -->
    <div v-else-if="error" class="m-msg__error">
      <span class="m-msg__error-text">加载失败：{{ error }}</span>
      <button class="m-msg__action" :disabled="loading" @click="refresh">重试</button>
    </div>
    <div v-else-if="list.length === 0" class="m-msg__empty">暂无消息</div>

    <div
      v-for="m in list"
      :key="m.id"
      class="m-msg__item"
      :class="{ 'm-msg__item--unread': !m.read }"
      @click="open(m)"
    >
      <span class="m-msg__dot" :class="'m-msg__dot--' + m.level"></span>
      <div class="m-msg__body">
        <div class="m-msg__title">
          <span class="m-msg__tag">{{ typeLabel[m.msg_type] || m.msg_type }}</span>
          {{ m.title }}
        </div>
        <div v-if="m.body" class="m-msg__text">{{ m.body }}</div>
        <div class="m-msg__time">{{ formatTime(m.created_at) }}</div>
      </div>
    </div>

    <!-- T02517（FR-UX-703 / I21）：真正的分页出口。后端 m/inbox 一直支持
         page/page_size 并回 total（mobile.py:52-57、mobile_service.get_inbox），
         此前前端只取第 1 页 20 条，第 21 条之后的消息在界面上根本不存在。
         移动端用「加载更多」增量追加而非页码器（小屏上 5 个页码 + 上下页太难点）。 -->
    <div v-if="list.length > 0" class="m-msg__pager">
      <span class="m-msg__count">已显示 {{ list.length }} / {{ total }}</span>
      <button
        v-if="hasMore"
        class="m-msg__action"
        :disabled="loadingMore"
        @click="loadMore"
      >
        {{ loadingMore ? '加载中…' : '加载更多' }}
      </button>
      <span v-else class="m-msg__count">没有更多了</span>
    </div>
  </div>
</template>

<script setup>
/**
 * 移动端消息中心（T02517 / I21：接上真实分页）
 *
 * 此前 `load()` 把首页 20 条写死，后端 `m/inbox` 早就支持
 * page/page_size 并回 total——第 21 条之后的消息在界面上等于不存在，只能靠「全部已读」
 * 一把梭。这里改成按页取、可「加载更多」，并保留未读数与「已显示 x / y」的口径。
 *
 * 不引入自动轮询（NFR-UX-03）：增量只由用户点击驱动，页面自己不会定时请求。
 */
import { ref, computed, onMounted } from 'vue'
import { getInbox, markRead } from '../../api/mobile'
import { ElMessage } from '../../utils/message'

// 后端 page_size 上限 100（mobile.py:Query(20, ge=1, le=100)）；
// 移动端按 20 一页：首屏轻，且 20 条在一屏内滚得完
const PAGE_SIZE = 20

const list = ref([])
const total = ref(0)
const unreadCount = ref(0)
const page = ref(1)
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')

const typeLabel = { review: '审批', alert: '告警', system: '系统' }

const levelClass = { info: 'info', warning: 'warning', critical: 'critical' }

/** 已取到的条数 < 后端总数就还有下一页 */
const hasMore = computed(() => list.value.length < total.value)

/**
 * 取某一页。第 1 页整表替换，之后增量追加。
 *
 * 追加时按 id 去重：翻页期间有新消息入库，后端偏移量会整体后移，
 * 不去重就会把同一条消息渲染成两行（`v-for :key="m.id"` 还会撞 key）。
 */
async function fetchPage(nextPage) {
  const data = await getInbox({ page: nextPage, page_size: PAGE_SIZE })
  const items = data.items || []
  if (nextPage <= 1) {
    list.value = items
  } else {
    const seen = new Set(list.value.map((m) => m.id))
    list.value = list.value.concat(items.filter((m) => !seen.has(m.id)))
  }
  // 后端没回 total 时按「已取到的条数」收口，宁可显示到底也不给一个永远点不完的按钮
  total.value = data.total ?? list.value.length
  unreadCount.value = data.unread_count ?? 0
  page.value = nextPage
}

async function refresh() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    await fetchPage(1)
  } catch (e) {
    error.value = e?.response?.data?.message || e?.message || String(e) || '未知错误'
    console.error('[m/message] 收件箱加载失败', { page: 1, pageSize: PAGE_SIZE, message: error.value })
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  error.value = ''
  try {
    await fetchPage(page.value + 1)
  } catch (e) {
    // 加载更多失败不能把已展示的列表抹掉：列表仍在，只是没续上
    error.value = e?.response?.data?.message || e?.message || String(e) || '未知错误'
    console.error('[m/message] 加载更多失败', {
      page: page.value + 1,
      pageSize: PAGE_SIZE,
      message: error.value,
    })
  } finally {
    loadingMore.value = false
  }
}

async function markAll() {
  await markRead({ mark_all: true })
  ElMessage.success('已全部标记已读')
  await refresh()
}

async function open(m) {
  if (m.read) {
    // 已读项若带深链可跳转（如审批详情）
    return
  }
  await markRead({ message_ids: [m.id] })
  m.read = true
  unreadCount.value = Math.max(0, unreadCount.value - 1)
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(refresh)
</script>

<style scoped>
.m-msg {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-msg__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 2px 6px;
}

.m-msg__count {
  font-size: 13px;
  color: #8a8f99;
}

.m-msg__action {
  font-size: 13px;
  color: var(--el-color-primary, #409eff);
  background: none;
  border: none;
  cursor: pointer;
}

.m-msg__action:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
}

.m-msg__empty {
  text-align: center;
  color: #b0b4bb;
  font-size: 14px;
  padding: 40px 0;
}

/* T02517：加载失败态（区别于「暂无消息」的空态） */
.m-msg__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #fef0f0;
  color: #c45656;
  font-size: 13px;
}

.m-msg__error-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 分页出口：左「已显示 x / y」右「加载更多」，375px 宽度下不挤行 */
.m-msg__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 2px 14px;
}

.m-msg__item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-msg__item--unread {
  border-left: 3px solid var(--el-color-primary, #409eff);
}

.m-msg__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex: 0 0 auto;
  background: #c0c4cc;
}

.m-msg__dot--warning {
  background: #e6a23c;
}

.m-msg__dot--critical {
  background: #f56c6c;
}

.m-msg__body {
  flex: 1;
  min-width: 0;
}

.m-msg__title {
  font-size: 15px;
  color: #1f2329;
  display: flex;
  align-items: center;
  gap: 6px;
}

.m-msg__tag {
  font-size: 11px;
  color: #fff;
  background: var(--el-color-primary, #409eff);
  border-radius: 4px;
  padding: 1px 5px;
}

.m-msg__text {
  font-size: 13px;
  color: #8a8f99;
  margin-top: 4px;
  line-height: 1.5;
}

.m-msg__time {
  font-size: 11px;
  color: #b0b4bb;
  margin-top: 6px;
}
</style>
