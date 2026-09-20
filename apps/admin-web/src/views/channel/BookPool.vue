<template>
  <!-- page-container：提供 24px 页面内边距（Layout 的 .main-content padding 为 0，由页面负责）。
       缺失时卡片与内部标题/按钮会 0px 紧贴侧栏与窗口右缘（用户反馈「书单标题和从素材库
       导入按钮太靠近边缘」即此），与其它 25 个页面口径不一致。 -->
  <div class="book-pool page-container">
    <!-- 顶部：频道选择（讲书稿模式开关在下方面板内，与编辑弹窗的素材池弹窗映射同一组件） -->
    <el-card shadow="never">
      <template #header>
        <div class="page-header">
          <span class="page-title">讲书稿素材池</span>
          <el-select
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
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { listChannels } from '../../api/channels'
import BookPoolPanel from './BookPoolPanel.vue'

const TYPE_LABELS = { news: '资讯', course: '课程', audiobook: '有声读物' }
const typeLabel = (t) => TYPE_LABELS[t] || t || '资讯'

const route = useRoute()
const channels = ref([])
const channelId = ref(null)

async function loadChannels() {
  channels.value = await listChannels()
  const qid = Number(route.query.channelId)
  if (qid) {
    channelId.value = qid
  } else {
    const preferred = channels.value.find((c) => c.channel_type === 'audiobook') || channels.value[0]
    channelId.value = preferred ? preferred.id : null
  }
}

function onChannelChange() {
  // 切频道后面板经 props.channelId watch 自动重载
}

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
