<template>
  <!-- page-container：提供 24px 页面内边距（Layout 的 .main-content padding 为 0，由页面负责）。
       缺失时卡片与内部标题/按钮会 0px 紧贴侧栏与窗口右缘（用户反馈「书单标题和从素材库
       导入按钮太靠近边缘」即此），与其它 25 个页面口径不一致。 -->
  <div data-guide="book-pool-page" class="book-pool page-container">
    <!-- 顶部：频道选择（讲书稿模式开关在下方面板内，与编辑弹窗的素材池弹窗映射同一组件） -->
    <!-- 标题卡片：内容全部放在 #header（标题 + 频道选择），默认插槽为空。
         Element Plus 的空 body 仍有 20px 上下内边距 ⇒ 标题与下方面板之间多出一条
         40px 空白带（用户反馈「中间有一行空行」），故显式清零 body 内边距。
         若将来要往 body 放内容，请恢复默认内边距（去掉 :body-style）。 -->
    <el-card shadow="never" :body-style="{ padding: 0 }">
      <template #header>
        <div class="page-header">
          <!-- T00811：移除与导航栏重复的页面标题，保留频道选择 -->
          <el-select data-guide="book-pool-channel"
            v-model="channelId"
            placeholder="选择频道"
            filterable
            style="width: 260px"
            @change="onChannelChange"
          >
            <el-option
              v-for="c in channels"
              :key="c.id"
              :label="`${c.name}（${typeLabel(c.channel_type)}）`"
              :value="c.id"
            />
          </el-select>
        </div>
      </template>
      <el-alert v-if="!channelId" type="info" :closable="false" show-icon
        title="请先选择频道：讲书稿模式按频道独立配置（素材池、排序与进度都属于所选频道）" />
    </el-card>

    <!-- C68（FR-UX-602）：地址里的 channelId 查无此频道时显式说明「已回落到哪个频道」，
         而不是静默换频道——否则用户以为看的是地址里那个频道的配置。 -->
    <el-alert v-if="deadChannelId && channelId" data-guide="book-pool-dead-channel" type="warning"
      :closable="false" show-icon style="margin-top: 12px"
      :title="`地址中的频道 #${deadChannelId} 不存在或已删除，已切换到「${currentChannelName}」`" />

    <!-- 核心交互面板（与频道编辑弹窗内的素材池弹窗映射同一组件） -->
    <BookPoolPanel v-if="channelId" :channel-id="channelId" style="margin-top: 12px" />
  </div>
</template>

<script setup>
/**
 * 讲书稿素材池页（T00656）
 *
 * 薄壳：频道选择 + <BookPoolPanel>（讲书稿模式开关、书单/排序/进度/候选加入的
 * 核心交互封装在 BookPoolPanel，与频道编辑弹窗内的素材池弹窗**映射同一组件**，状态一致）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listChannels } from '../../api/channels'
import BookPoolPanel from './BookPoolPanel.vue'
import { CHANNEL_TYPE, enumLabel } from '../../constants/enums'

// 频道类型文案取自 src/constants/enums.js（FR-UX-405 / T02504）；
// 此前类型为空会无条件显示「资讯」，与频道真实类型无关
const typeLabel = (t) => enumLabel(CHANNEL_TYPE, t)

const route = useRoute()
const router = useRouter()
const channels = ref([])
const channelId = ref(null)
// 地址里给了 channelId 但频道列表里查无此频道（C68：深链参数不校验存在性）
const deadChannelId = ref('')

async function loadChannels() {
  try {
    channels.value = (await listChannels()) || []
  } catch {
    // 拦截器已提示；拿不到列表时**不要**把地址里的 channelId 当真值用——
    // 那会让面板去打一个可能不存在的频道，退化成「未开启 + 空池」的误导画面
    channels.value = []
    return
  }

  const raw = route.query.channelId
  const qid = Number(Array.isArray(raw) ? raw[0] : raw)
  const hit = Number.isFinite(qid) && qid > 0 ? channels.value.find((c) => c.id === qid) : null
  // 只在「地址确实写了 channelId 且查不到」时点名；没写 channelId 属正常进入
  deadChannelId.value = raw && !hit ? String(Array.isArray(raw) ? raw[0] : raw) : ''

  const preferred = hit || channels.value.find((c) => c.channel_type === 'audiobook') || channels.value[0]
  channelId.value = preferred ? preferred.id : null

  // 校正后的频道写回 URL：这一页的有效状态从此可以用地址表达（可分享、可收藏、刷新不回退）。
  // 无效 channelId 也会被替换成真正生效的那个——地址栏不再撒谎。
  if (channelId.value && String(channelId.value) !== String(raw ?? '')) {
    router
      .replace({ query: { ...route.query, channelId: String(channelId.value) } })
      .catch((err) => console.warn('[book-pool] URL 回写被拒绝:', err?.message || err))
  }
}

function onChannelChange() {
  // 切频道后面板经 props.channelId watch 自动重载；同步把选择写回地址（FR-UX-602 状态保留）
  if (channelId.value) {
    router
      .replace({ query: { ...route.query, channelId: String(channelId.value) } })
      .catch((err) => console.warn('[book-pool] URL 回写被拒绝:', err?.message || err))
  }
  deadChannelId.value = ''
}

// 告警文案里显示回落到的频道名（比裸 ID 可读）
const currentChannelName = computed(() => {
  const hit = channels.value.find((c) => c.id === channelId.value)
  return hit ? hit.name : `#${channelId.value}`
})

onMounted(loadChannels)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.page-title {
  font-weight: 600;
}
</style>
