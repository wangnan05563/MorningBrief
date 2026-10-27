<template>
  <section class="audit-trail" :data-guide="guide">
    <div class="audit-trail__head">
      <h3 class="audit-trail__title">{{ title }}</h3>
      <button
        type="button"
        class="audit-trail__refresh"
        :disabled="loading"
        @click="load"
      >
        刷新
      </button>
    </div>

    <!-- T02496 口径：读取失败不能说成「暂无记录」 -->
    <ListLoadError
      v-if="error"
      :message="error"
      :retrying="loading"
      :stale="items.length > 0"
      @retry="load"
    />
    <p v-else-if="loading && !items.length" class="audit-trail__hint">加载中…</p>
    <p v-else-if="!items.length" class="audit-trail__hint">该模块暂无审计记录</p>
    <ul v-else class="audit-trail__list">
      <li v-for="row in items" :key="row.id" class="audit-trail__item">
        <span class="audit-trail__time">{{ formatTime(row.created_at) }}</span>
        <span class="audit-trail__who">{{ row.operator || '系统' }}</span>
        <span class="audit-trail__what">{{ row.action }}{{ row.target ? ` · ${row.target}` : '' }}</span>
        <span class="audit-trail__why">{{ summarize(row.detail) }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
/**
 * 模块内「最近 N 条审计」（T02909）
 *
 * 存在的理由：这些动作一直有写审计，但读口只覆盖 db_admin 与移动端停服两类，
 * 出事以后查「谁做的」得手工捞表。这里按 category 取最近几条挂在动作发生的页面旁，
 * 让值班不用离开当前页面就能回答「刚才那次是谁做的」。
 *
 * 只做只读展示：详情里的密钥形状字段由后端读侧脱敏（`***`），前端不再猜哪些算敏感。
 */
import { onMounted, ref } from 'vue'
import { listAuditLogs } from '../api/audit'
import ListLoadError from './ListLoadError.vue'

const props = defineProps({
  category: { type: String, required: true },
  limit: { type: Number, default: 5 },
  title: { type: String, default: '最近操作审计' },
  guide: { type: String, default: 'module-audit' },
})

const items = ref([])
const loading = ref(false)
const error = ref('')

function formatTime(iso) {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 19)
}

function summarize(detail) {
  if (!detail || typeof detail !== 'object') return String(detail ?? '')
  const keys = ['reason', 'note', 'message', 'days', 'count', 'deleted', 'cleaned_count']
  const picked = keys.filter((k) => detail[k] !== undefined && detail[k] !== null && detail[k] !== '')
  const shown = (picked.length ? picked : Object.keys(detail)).slice(0, 3)
  return shown.map((k) => `${k}=${detail[k]}`).join(' · ')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listAuditLogs({ category: props.category, page: 1, page_size: props.limit })
    items.value = data?.items ?? []
  } catch (e) {
    error.value = e?.message || '审计读取失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

defineExpose({ reload: load })
</script>

<style scoped lang="scss">
.audit-trail {
  margin-top: 16px;
  padding: 12px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  &__title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__refresh {
    padding: 2px 10px;
    font-size: 12px;
    color: var(--el-color-primary);
    background: none;
    border: 1px solid var(--el-border-color);
    border-radius: 4px;
    cursor: pointer;

    &:disabled {
      cursor: default;
      opacity: 0.6;
    }
  }

  &__hint {
    margin: 4px 0;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__list {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  &__item {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 4px 0;
    font-size: 12px;
    color: var(--el-text-color-regular);
    border-bottom: 1px dashed var(--el-border-color-lighter);

    &:last-child {
      border-bottom: none;
    }
  }

  &__time,
  &__who {
    color: var(--el-text-color-secondary);
    font-variant-numeric: tabular-nums;
  }

  &__what {
    font-weight: 600;
  }

  &__why {
    flex: 1;
    min-width: 120px;
    color: var(--el-text-color-secondary);
    word-break: break-all;
  }
}
</style>
