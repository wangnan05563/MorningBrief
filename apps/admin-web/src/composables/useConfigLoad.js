/**
 * 配置页「加载—就绪—失败」状态封装（T02487：FR-UX-104 配置加载失败禁存 + 重试）
 *
 * 为什么自建：配置页的保存动作把整个表单原样 PUT 回服务端，
 * 首次加载失败时表单里全是代码默认值，点保存等于用默认值覆盖线上配置。
 * 页面只需把 loader 交进来，即可得到一个门控保存/草稿恢复的三态标志。
 *
 * 用法：
 *   const cfg = useConfigLoad(loadConfig)   // loadConfig 失败时必须抛出
 *   await cfg.load()                        // onMounted
 *   await cfg.retry()                       // 错误态里的「重新加载」按钮
 *   <el-button :disabled="!cfg.isReady">    // 保存门控
 *
 * 约定：loader 返回 null/undefined 视为失败——「接口通了但没给配置」
 * 同样不能让默认值冒充已加载值。retry() 不复位成 loading 态，
 * 否则错误提示连同按钮会在重试期间消失。
 */
import { computed, ref } from 'vue'

export function useConfigLoad(loader) {
  const state = ref('loading')
  const errorMessage = ref('')
  const retrying = ref(false)

  const isReady = computed(() => state.value === 'ready')
  const isError = computed(() => state.value === 'error')
  const isLoading = computed(() => state.value === 'loading')

  async function attempt() {
    try {
      const data = await loader()
      if (data === null || data === undefined) {
        state.value = 'error'
        errorMessage.value = '配置接口未返回数据'
        return false
      }
      state.value = 'ready'
      errorMessage.value = ''
      return true
    } catch (e) {
      state.value = 'error'
      errorMessage.value = e?.message || '配置加载失败'
      return false
    }
  }

  async function load() {
    state.value = 'loading'
    errorMessage.value = ''
    return attempt()
  }

  async function retry() {
    retrying.value = true
    try {
      return await attempt()
    } finally {
      retrying.value = false
    }
  }

  return { state, errorMessage, isReady, isError, isLoading, retrying, load, retry }
}
