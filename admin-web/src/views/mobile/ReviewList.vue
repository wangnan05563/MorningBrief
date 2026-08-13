<template>
  <div class="m-review">
    <!-- 上下文标题区：同时标明当前频道 + 工作流，清晰呈现所属上下文 -->
    <header class="m-review__ctx">
      <div class="m-review__ctx-head">
        <span class="m-review__ctx-label">{{ scoped ? '审核上下文' : '全部待审' }}</span>
        <span v-if="list.length" class="m-review__ctx-count">待审 {{ list.length }}</span>
      </div>

      <!-- 作用域模式：直接展示当前频道与工作流名称 -->
      <div v-if="scoped" class="m-review__ctx-tags">
        <span class="m-chip m-chip--ch"><i>频道</i>{{ channelName }}</span>
        <span class="m-chip m-chip--wf"><i>工作流</i>{{ workflowName }}</span>
      </div>
      <p v-else class="m-review__ctx-hint">跨频道 / 工作流的待审内容，每条卡片下方标注其归属。</p>

      <button
        class="m-btn m-btn--approve-all"
        :disabled="!list.length || approving"
        @click="approveAll"
      >
        <span v-if="approving" class="m-btn__loading">审批中…</span>
        <span v-else>一键全部审批（{{ list.length }}）</span>
      </button>
    </header>

    <div v-if="loading && !list.length" class="m-empty">加载中…</div>

    <div v-for="item in list" :key="item.id" class="m-review__item">
      <!-- 标题区域：点击展开/收起详情（触摸友好，清晰返回路径） -->
      <div
        class="m-review__title-row"
        role="button"
        :aria-expanded="item.expanded"
        tabindex="0"
        @click="toggleExpand(item)"
        @keydown.enter.prevent="toggleExpand(item)"
        @keydown.space.prevent="toggleExpand(item)"
      >
        <div class="m-review__title">{{ item.title || ('审核 #' + item.id) }}</div>
        <span class="m-review__chev" :class="{ 'is-open': item.expanded }">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
      </div>

      <div class="m-review__meta">
        <span v-if="!scoped" class="m-review__ch">{{ item.channel_name || '—' }}</span>
        <span v-if="!scoped" class="m-review__wf">{{ item.workflow_name || item.workflow_id }}</span>
        <span class="m-review__type">{{ item.channel_type || '—' }}</span>
        <span v-if="item.auto_approved" class="m-review__auto">系统</span>
      </div>

      <!-- 折叠态显示摘要，展开时由完整文本替代，避免重复 -->
      <div v-if="!item.expanded" class="m-review__text">{{ item.content_preview || '（暂无摘要）' }}</div>

      <!-- 展开详情：完整文本 / 图片 / 字段明细等 -->
      <div v-if="item.expanded" class="m-review__detail">
        <div v-if="item.loadingDetail" class="m-detail__loading">加载详情…</div>

        <template v-else-if="item.detail">
          <!-- 封面图片 -->
          <img
            v-if="item.detail.cover_url"
            :src="item.detail.cover_url"
            class="m-detail__cover"
            alt="内容封面"
            loading="lazy"
          />

          <!-- 语音内容（音频播放）：优先 review.audio_url，缺省回退 episode.hls_url -->
          <div v-if="item.detail.audio_url || item.detail.hls_url" class="m-detail__audio">
            <span class="m-detail__audio-label">语音内容</span>
            <audio controls preload="none" :src="item.detail.audio_url || item.detail.hls_url"></audio>
          </div>

          <!-- 字段明细 -->
          <dl class="m-detail__fields">
            <div class="m-detail__field">
              <dt>频道</dt><dd>{{ item.channel_name || '—' }}</dd>
            </div>
            <div class="m-detail__field">
              <dt>工作流</dt><dd>{{ item.workflow_name || item.workflow_id }}</dd>
            </div>
            <div class="m-detail__field">
              <dt>期次</dt><dd>{{ item.detail.episode_date || '—' }}</dd>
            </div>
            <div class="m-detail__field">
              <dt>类型</dt><dd>{{ item.channel_type || '—' }}</dd>
            </div>
            <div v-if="item.auto_approved" class="m-detail__field">
              <dt>自动审批</dt>
              <dd>{{ item.detail.auto_trigger_reason || '系统自动通过' }}</dd>
            </div>
            <div class="m-detail__field">
              <dt>创建时间</dt><dd>{{ item.detail.created_at || '—' }}</dd>
            </div>
          </dl>

          <!-- 完整文本 -->
          <section class="m-detail__section">
            <h4 class="m-detail__h">完整文本</h4>
            <p class="m-detail__text">{{ item.detail.script?.full_text || '（无全文内容）' }}</p>
          </section>

          <!-- 分段明细 -->
          <section
            v-if="item.detail.script?.segments?.length"
            class="m-detail__section"
          >
            <h4 class="m-detail__h">分段明细（{{ item.detail.script.segments.length }}）</h4>
            <div
              v-for="(seg, i) in item.detail.script.segments"
              :key="i"
              class="m-detail__seg"
            >
              <div class="m-detail__seg-title">{{ seg.title || ('第 ' + (i + 1) + ' 段') }}</div>
              <div class="m-detail__seg-text">{{ seg.content }}</div>
            </div>
          </section>

          <!-- 分类 / 引用素材 -->
          <section
            v-if="item.detail.script?.categories?.length || item.detail.script?.referenced_materials?.length"
            class="m-detail__section"
          >
            <h4 class="m-detail__h">分类 / 引用素材</h4>
            <div class="m-detail__chips">
              <span
                v-for="c in (item.detail.script.categories || [])"
                :key="'c' + c"
                class="m-chip2"
              >{{ c }}</span>
              <a
                v-for="(m, i) in (item.detail.script.referenced_materials || [])"
                :key="'m' + i"
                :href="m"
                class="m-chip2 m-chip2--link"
                target="_blank"
                rel="noopener"
              >素材 {{ i + 1 }}</a>
            </div>
          </section>
        </template>

        <!-- 加载失败态：detail 为空且非加载中（拦截器已 toast，此处再给内联提示便于重试） -->
        <div v-else class="m-detail__err">详情加载失败，点击标题重试</div>
      </div>

      <div class="m-review__actions">
        <button class="m-btn m-btn--ghost" :disabled="item.busy" @click="act(item, 'reject')">驳回</button>
        <button class="m-btn m-btn--primary" :disabled="item.busy" @click="act(item, 'approve')">通过</button>
      </div>
    </div>

    <div v-if="!loading && !list.length" class="m-empty">暂无待审内容 🎉</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { listReviews, getReview, handleReviewAction, batchHandleReviewAction } from '../../api/reviews'
import { ElMessage, ElMessageBox } from '../../utils/message'

const route = useRoute()

// 作用域模式：从队列页带 workflow_id（+channel_name）进入，列表按工作流过滤
const scoped = computed(() => !!route.query.workflow_id)
const channelName = computed(
  () => route.query.channel_name || list.value[0]?.channel_name || '—'
)
const workflowName = computed(
  () => route.query.workflow_id || list.value[0]?.workflow_name || '—'
)

const list = ref([])
const loading = ref(false)
const approving = ref(false)

async function load() {
  loading.value = true
  try {
    // size 对齐后端 BATCH_MAX_SIZE=50（批量操作入口上限）。后端 list_reviews
    // 用 limit(size) 不做额外截断，但若待审量 > size，单次请求会漏掉后续页；
    // 为防御"一键全部审批"静默漏批，这里分页累加拉全所有待审（最多 4 页/200 条）。
    const size = 50
    const all = []
    let page = 1
    while (true) {
      const params = { status: 'pending', page, size }
      // 作用域模式按工作流过滤，使顶部上下文与卡片一致
      if (route.query.workflow_id) params.workflow_id = route.query.workflow_id
      const data = await listReviews(params)
      const items = (data.list || []).map((it) => ({
        ...it,
        busy: false,
        expanded: false,
        detail: null,
        loadingDetail: false,
      }))
      all.push(...items)
      // 已取满全部(total) 或本页不足 size（末页）→ 停止；page>=4 防御异常无限循环
      if (all.length >= (data.total || all.length) || items.length < size || page >= 4) break
      page += 1
    }
    list.value = all
  } catch {
    // 错误提示由拦截器统一处理
  } finally {
    loading.value = false
  }
}

// 懒加载单条审核详情（完整文本/图片/字段），失败保留展开态且 detail 置空
async function loadDetail(item) {
  if (item.loadingDetail) return
  item.loadingDetail = true
  try {
    item.detail = await getReview(item.id)
  } catch {
    // 拦截器已提示；失败保留展开态且 detail 置空以便重试
    item.detail = null
  } finally {
    item.loadingDetail = false
  }
}

// 点击标题：展开/收起详情；首次展开时懒加载审核详情
async function toggleExpand(item) {
  // 失败态（已展开但详情为空）：点击标题直接重试重载，而非 toggle 收起，
  // 避免"点击标题重试"需额外点击才能重新加载（见 m-detail__err）
  if (item.expanded && !item.detail) {
    await loadDetail(item)
    return
  }
  item.expanded = !item.expanded
  if (item.expanded && !item.detail && !item.loadingDetail) {
    await loadDetail(item)
  }
}

// 单条审核：通过 / 驳回
async function act(item, action) {
  let reason = null
  // 驳回需采集理由（桌面端强约束的语义对齐）：弹窗输入，留空则用默认理由；
  // 用户取消则直接返回，不改动审核状态
  if (action === 'reject') {
    const r = await ElMessageBox.prompt(
      '请输入驳回理由（留空则使用默认理由）',
      '驳回确认',
      {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '如：内容有误 / 需重新改写 / 信息不全',
      },
    ).catch(() => null)
    if (!r) return
    reason = (r.value && r.value.trim()) || '移动端驳回'
  }

  item.busy = true
  try {
    await handleReviewAction(item.id, action, reason)
    ElMessage.success(action === 'approve' ? '已通过' : '已驳回')
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    item.busy = false
  }
}

// 构造批量结果摘要，便于用户识别通过/跳过/失败/发布失败
function buildSummary(r) {
  const parts = []
  if (r.succeeded?.length) parts.push(`通过 ${r.succeeded.length}`)
  if (r.skipped?.length) parts.push(`跳过 ${r.skipped.length}`)
  if (r.failed?.length) parts.push(`失败 ${r.failed.length}`)
  if (r.publish_failed?.length) parts.push(`发布失败 ${r.publish_failed.length}`)
  return parts.join('，') || '无变更'
}

// 一键全部审批：对本页所有待审项批量通过，含确认与结果反馈
async function approveAll() {
  const ids = list.value.map((i) => i.id)
  if (!ids.length) return

  try {
    await ElMessageBox.confirm(
      `确认一键通过当前 ${ids.length} 条待审内容？\n通过后系统将自动发布对应节目。`,
      '批量审批确认',
      { type: 'warning', confirmButtonText: '确认通过', cancelButtonText: '取消' }
    )
  } catch {
    return // 用户取消
  }

  approving.value = true
  try {
    const data = await batchHandleReviewAction(ids, 'approve')
    const summary = buildSummary(data)
    // 全部成功用 success，存在失败/发布失败用 warning
    if (data.failed?.length || data.publish_failed?.length) {
      ElMessage.warning(`批量审批完成：${summary}`)
    } else {
      ElMessage.success(`批量审批完成：${summary}`)
    }
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    approving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.m-review {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 上下文标题区 */
.m-review__ctx {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.m-review__ctx-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.m-review__ctx-label {
  font-size: 16px;
  font-weight: 700;
  color: #1f2329;
}

.m-review__ctx-count {
  font-size: 12px;
  color: #8a8f99;
}

.m-review__ctx-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.m-review__ctx-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #8a8f99;
  line-height: 1.5;
}

.m-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  max-width: 100%;
}

.m-chip i {
  font-style: normal;
  font-weight: 500;
  opacity: 0.7;
  font-size: 11px;
}

.m-chip--ch {
  color: #409eff;
  background: #ecf5ff;
}

.m-chip--wf {
  color: #67c23a;
  background: #f0f9eb;
}

/* 一键全部审批按钮 */
.m-btn--approve-all {
  width: 100%;
  height: 44px;
  margin-top: 12px;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(90deg, #409eff, #67c23a);
  cursor: pointer;
}

.m-btn--approve-all:disabled {
  background: #c8c9cc;
  cursor: not-allowed;
}

.m-btn__loading {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* 审核卡片 */
.m-review__item {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

/* 标题行：可点击展开，触摸目标足够大 */
.m-review__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 44px;
  padding: 4px 0;
  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  outline: none;
}

.m-review__title-row:active {
  opacity: 0.6;
}

.m-review__title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2329;
  flex: 1;
}

.m-review__chev {
  flex: 0 0 auto;
  color: #8a8f99;
  transition: transform 0.2s ease;
  display: inline-flex;
}

.m-review__chev.is-open {
  transform: rotate(180deg);
}

.m-review__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 6px 0;
  font-size: 12px;
  color: #8a8f99;
}

.m-review__ch {
  color: #409eff;
}

.m-review__wf {
  color: #67c23a;
}

.m-review__type {
  color: var(--el-color-primary, #409eff);
}

.m-review__auto {
  color: #e6a23c;
  background: #fdf6ec;
  border-radius: 4px;
  padding: 0 5px;
}

.m-review__text {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.5;
  margin-bottom: 12px;
}

/* 展开详情区 */
.m-review__detail {
  border-top: 1px dashed #ebeef5;
  margin-top: 10px;
  padding-top: 12px;
}

.m-detail__loading {
  text-align: center;
  color: #8a8f99;
  font-size: 13px;
  padding: 16px 0;
}

.m-detail__err {
  text-align: center;
  color: #f56c6c;
  font-size: 13px;
  padding: 16px 0;
}

.m-detail__cover {
  width: 100%;
  max-height: 220px;
  object-fit: cover;
  border-radius: 10px;
  margin-bottom: 12px;
  background: #f5f6f8;
}

.m-detail__audio {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.m-detail__audio-label {
  font-size: 12px;
  color: #8a8f99;
}

.m-detail__audio audio {
  width: 100%;
}

/* 字段明细栅格 */
.m-detail__fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin: 0 0 12px;
}

.m-detail__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.m-detail__field dt {
  font-size: 11px;
  color: #a0a4ab;
}

.m-detail__field dd {
  margin: 0;
  font-size: 13px;
  color: #1f2329;
  word-break: break-all;
}

.m-detail__section {
  margin-bottom: 12px;
}

.m-detail__h {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
  margin: 0 0 6px;
}

.m-detail__text {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  background: #fafbfc;
  border-radius: 8px;
  padding: 10px;
  margin: 0;
}

.m-detail__seg {
  background: #fafbfc;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
}

.m-detail__seg-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2329;
  margin-bottom: 4px;
}

.m-detail__seg-text {
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.m-detail__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.m-chip2 {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #4e5969;
  background: #f0f2f5;
  border-radius: 6px;
  padding: 4px 10px;
  max-width: 100%;
  word-break: break-all;
}

.m-chip2--link {
  color: #409eff;
  background: #ecf5ff;
  text-decoration: none;
}

.m-chip2--link:active {
  opacity: 0.7;
}

.m-review__actions {
  display: flex;
  gap: 10px;
}

.m-btn {
  flex: 1;
  height: 40px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
}

.m-btn--primary {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.m-btn--ghost {
  background: #fff;
  border-color: #dcdfe6;
  color: #4e5969;
}

.m-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.m-empty {
  text-align: center;
  color: #b0b4bb;
  padding: 40px 0;
  font-size: 14px;
}
</style>
