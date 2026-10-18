<template>
  <el-alert type="error" :closable="false" show-icon class="list-load-error">
    <template #title>
      加载失败：{{ message || '未知错误' }}
    </template>
    <div class="list-load-error__body">
      <p class="list-load-error__note">{{ note }}</p>
      <IconButton
        type="primary"
        plain
        :loading="retrying"
        label="重试"
        desc="重新发起请求，成功后恢复列表"
        :icon="Refresh"
        @click="emit('retry')"
      />
    </div>
  </el-alert>
</template>

<script setup>
/**
 * 列表/详情级加载失败态（T02496：FR-UX-302）
 *
 * 与 ConfigLoadError 的区别：配置页失败要「禁用保存」（怕默认值覆盖线上），
 * 列表页失败要的是「别把接口挂了说成没有数据」。文案与门控因此不同，
 * 但两者都必须自带重试按钮——不能只靠拦截器的一条 toast，
 * toast 会消失，用户想重试时找不到入口。
 *
 * 显隐由使用方的 v-if 决定（各页面的失败标志名不同：listError / loadFailed /
 * trendError），组件自身不再叠一层 visible 门控——否则默认 false 会让
 * 页面即使传了 message 也渲染不出任何东西。
 */
import { computed } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

const props = defineProps({
  message: { type: String, default: '' },
  retrying: { type: Boolean, default: false },
  // 列表已有旧数据时由页面传入：此时不能声称「没有数据」，只是没刷新成功
  stale: { type: Boolean, default: false },
})

const emit = defineEmits(['retry'])

const note = computed(() =>
  props.stale
    ? '下方为上次成功加载的数据，可能已过期。'
    : '这与「暂无数据」不同：请求未成功，数据并未加载。请检查网络或服务后重试。',
)
</script>

<style scoped lang="scss">
.list-load-error {
  margin-bottom: 12px;

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
