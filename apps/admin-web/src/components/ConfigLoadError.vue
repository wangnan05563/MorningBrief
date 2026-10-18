<template>
  <el-alert v-if="visible" type="error" :closable="false" show-icon class="config-load-error">
    <template #title>
      配置加载失败：{{ message || '未知错误' }}
    </template>
    <div class="config-load-error__body">
      <p class="config-load-error__note">{{ note }}</p>
      <IconButton
        type="primary"
        plain
        :loading="retrying"
        label="重新加载"
        desc="重新拉取服务端配置，成功后才能保存"
        :icon="Refresh"
        @click="emit('retry')"
      />
    </div>
  </el-alert>
</template>

<script setup>
/**
 * 配置页加载失败态（T02487：FR-UX-104）
 *
 * 为什么单独成组件：COS / 内网穿透 / 通知 / AI 四个配置页都要同一套
 * 「页内错误态 + 重试 + 禁用保存 + 草稿不恢复」提示，文案与图标必须一致。
 */
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  message: { type: String, default: '' },
  retrying: { type: Boolean, default: false },
  // 存在未恢复的本地草稿时由页面传入专门提示，其余情况用默认说明
  draftBlocked: { type: Boolean, default: false },
})

const emit = defineEmits(['retry'])

const note = computed(() =>
  props.draftBlocked
    ? '配置未加载，保存会覆盖线上值；本地草稿已保留但未恢复，重试成功后会自动带出。'
    : '为避免把表单默认值当成已加载配置提交，保存已禁用。请重试或刷新页面。',
)
</script>

<style scoped lang="scss">
.config-load-error {
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
}
</style>
