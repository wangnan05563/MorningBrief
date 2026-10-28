<template>
  <el-alert
    v-if="visible"
    type="warning"
    :closable="false"
    show-icon
    class="draft-restored"
    data-testid="draft-restored"
  >
    <template #title>
      已恢复本地未保存草稿（{{ count }} 项与服务器值不同）
    </template>
    <div class="draft-restored__body">
      <p class="draft-restored__note">
        这些输入尚未保存到服务器。直接保存会把草稿写回线上；丢弃则用服务器值重填表单并删除本机草稿。
      </p>
      <div class="draft-restored__actions">
        <el-button size="small" @click="emit('keep')">保留草稿</el-button>
        <el-button size="small" type="primary" plain @click="emit('discard')">
          丢弃草稿，载入服务器值
        </el-button>
      </div>
    </div>
  </el-alert>
</template>

<script setup>
/**
 * 配置页「已恢复本地草稿」明示横幅（T02534 / F2 裁决：草稿优先 + 明示）
 *
 * 背景：useDraft 恢复草稿时是静默深合并，页面看不出屏幕上的值不是服务器值，
 * 一次保存就把陈旧草稿写回线上，且 commitDraft 会抹掉唯一的痕迹。
 * 这里把「恢复了什么、怎么办」摆到页顶：保留＝继续用草稿，丢弃＝回填服务器值并清本机草稿。
 */
defineProps({
  visible: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
})

const emit = defineEmits(['keep', 'discard'])
</script>

<style scoped lang="scss">
.draft-restored {
  margin-bottom: 16px;

  &__body {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  &__note {
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
  }

  &__actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}
</style>
