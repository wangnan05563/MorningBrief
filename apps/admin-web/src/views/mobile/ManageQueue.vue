<template>
  <div class="m-q">
    <section class="m-q__stats" v-if="stats">
      <div v-for="c in STAT_CARDS" :key="c.key" class="m-q__stat">
        <div class="m-q__stat-v">{{ stats[c.key] ?? '-' }}</div>
        <div class="m-q__stat-l">{{ c.label }}</div>
      </div>
    </section>

    <div v-if="loading && !tasks.length" class="m-empty">加载中…</div>
    <!-- T02496（FR-UX-302 / ACC-UX-301 第 3 条）：断网进队列页必须显示「加载失败，重试」，
         而不是「队列为空」——后者会让值班同学以为队列真的没有任务 -->
    <div v-else-if="loadError" class="m-empty">
      <div>加载失败：{{ loadError }}</div>
      <button type="button" class="m-btn m-btn--primary" :disabled="loading" @click="reload">重试</button>
    </div>
    <div v-else-if="!tasks.length" class="m-empty">队列为空</div>

    <div v-for="t in tasks" :key="t.id" class="m-q__item">
      <div class="m-q__head">
        <span class="m-q__ch">{{ t.channel_name || ('频道#' + t.channel_id) }}</span>
        <span class="m-badge" :class="statusClass(t.status)">{{ statusLabel(t.status) }}</span>
      </div>
      <div class="m-q__no">
        <span class="m-q__no-l">队列编号</span>
        <button
          type="button"
          class="m-q__no-v"
          @click="copyNo(t.id)"
          :title="'点击复制队列编号'"
        >{{ t.id }}</button>
      </div>
      <div class="m-q__meta">
        <span>{{ t.source || '—' }}</span>
        <span>期次 {{ t.episode_date || '—' }}</span>
        <span>优先级 {{ t.priority ?? '-' }}</span>
      </div>
      <div class="m-q__meta m-q__err" v-if="t.error">{{ t.error }}</div>
      <div class="m-q__actions">
        <button
          v-if="t.status === 'queued'"
          class="m-btn m-btn--sm m-btn--danger"
          @click="cancel(t)"
        >取消</button>
        <button
          v-if="t.status === 'failed'"
          class="m-btn m-btn--sm m-btn--primary"
          @click="retry(t)"
        >重试</button>
        <button
          class="m-btn m-btn--sm m-btn--primary"
          @click="goReview(t)"
        >去审核</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getQueueStats, listQueueTasks, cancelTask, retryTask } from '../../api/queue'
import { ElMessage } from '../../utils/message'
import { WORKFLOW_STATUS, enumLabel, enumBadge } from '../../constants/enums'

const router = useRouter()

const stats = ref(null)
const tasks = ref([])
const loading = ref(false)
// T02496（FR-UX-302）：非空即「这次没取到」，与「队列为空」区分开
const loadError = ref('')

// 跳转至作用域审核页：携带 workflow_id 与频道名，
// 供移动端审核页顶部上下文标题区展示「当前频道 + 工作流」
function goReview(t) {
  router.push({
    path: '/m/review',
    query: { workflow_id: t.id, channel_name: t.channel_name || '' },
  })
}

// 状态文案/配色与 PC 队列页同源（src/constants/enums.js，FR-UX-405 / T02504）。
// 此前本地映射写的是 `finished`，后端 WorkflowStatus 实为 `success`：
// 已完成任务在移动端漏出英文原值，统计卡「已完成」永远显示 -
const STAT_CARDS = ['queued', 'running', 'success', 'failed'].map((key) => ({
  key,
  label: enumLabel(WORKFLOW_STATUS, key),
}))
const statusLabel = (s) => enumLabel(WORKFLOW_STATUS, s)
const statusClass = (s) => enumBadge(WORKFLOW_STATUS, s)

async function reload() {
  loading.value = true
  try {
    const [s, d] = await Promise.all([
      getQueueStats().catch(() => null),
      listQueueTasks({ page: 1, size: 50 }),
    ])
    stats.value = s
    tasks.value = d.items || []
    loadError.value = ''
  } catch (e) {
    // 拦截器已提示；页内还要留一个可重试的错误态，不能退化成「队列为空」
    loadError.value = e?.message || '队列加载失败'
  } finally {
    loading.value = false
  }
}

async function cancel(t) {
  try {
    await cancelTask(t.id)
    t.status = 'cancelled'
    ElMessage.success('已取消')
  } catch {
    // 拦截器已提示
  }
}

async function retry(t) {
  try {
    await retryTask(t.id)
    t.status = 'queued'
    ElMessage.success('已重新入队')
  } catch {
    // 拦截器已提示
  }
}

// 移动端触摸友好的「队列编号」复制：便于在工单/沟通中引用任务编号
// 优先用 navigator.clipboard（安全上下文）；非安全上下文（http/旧 WebView）降级
// 用 textarea + execCommand('copy') 真正写入剪贴板；都失败再提示手动复制。
async function copyNo(id) {
  const text = String(id)
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      ElMessage.success('已复制队列编号')
      return
    }
  } catch {
    // 落到下方 legacy 复制
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.top = '-9999px'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.focus()
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    if (ok) {
      ElMessage.success('已复制队列编号')
      return
    }
  } catch {
    // 忽略，进入下方兜底提示
  }
  ElMessage.info(`复制失败，请长按编号手动复制：${text}`)
}

onMounted(reload)
</script>

<style scoped>
.m-q {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.m-q__stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.m-q__stat {
  background: #fff;
  border-radius: 10px;
  padding: 10px 4px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-q__stat-v {
  font-size: 18px;
  font-weight: 700;
  color: var(--el-color-primary, #409eff);
}

.m-q__stat-l {
  font-size: 11px;
  color: #8a8f99;
  margin-top: 2px;
}

.m-q__item {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-q__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.m-q__ch {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
}

.m-q__no {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.m-q__no-l {
  font-size: 12px;
  color: #8a8f99;
  flex: 0 0 auto;
}

.m-q__no-v {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  color: #1f2329;
  background: #f5f7fa;
  border: 1px dashed #d0d5dd;
  border-radius: 6px;
  padding: 3px 8px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  user-select: all;
}

.m-q__no-v:active {
  background: #eef2f7;
}

.m-q__meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #8a8f99;
  margin-top: 6px;
  flex-wrap: wrap;
}

.m-q__err {
  color: #f56c6c;
}

.m-q__actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.m-badge {
  font-size: 11px;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 500;
}

.m-badge--on { color: #67c23a; background: #f0f9eb; }
.m-badge--off { color: #f56c6c; background: #fef0f0; }
.m-badge--warn { color: #e6a23c; background: #fdf6ec; }
.m-badge--info { color: #409eff; background: #ecf5ff; }

.m-btn {
  height: 46px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

.m-btn--sm {
  height: 34px;
  padding: 0 16px;
  font-size: 14px;
}

.m-btn--primary { background: var(--el-color-primary, #409eff); color: #fff; }
.m-btn--danger { background: #fff; color: #f56c6c; border: 1px solid #fbc4c4; }

.m-empty {
  text-align: center;
  color: #b0b4bb;
  padding: 40px 0;
  font-size: 14px;
}

/* 错误态里的重试：按钮比正文高一档间距，避免贴在文字下面误触 */
.m-empty .m-btn {
  margin-top: 12px;
  height: 40px;
}
</style>
