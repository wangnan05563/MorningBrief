/**
 * 列表/详情「加载—就绪—失败」三态封装（T02496：FR-UX-302 错误态与重试）
 *
 * 为什么自建：这些页面在请求失败时把数据置空，界面于是显示「暂无数据」——
 * 用户无法区分「库里真的没有」和「接口挂了没取到」。三态把这两种情况分开：
 * error 态显示页内错误 + 重试按钮，只有 ready 且结果为空才叫「暂无数据」。
 *
 * 用法：
 *   const list = useLoadState(fetchRows, { failMessage: '频道列表加载失败' })
 *   await list.load()          // onMounted / 筛选变化
 *   await list.retry()         // 错误态里的「重试」按钮
 *   <ListLoadError v-if="list.isError" :message="list.errorMessage"
 *                  :retrying="list.retrying" @retry="list.retry()" />
 *
 * 约定：fetchRows 失败时必须抛出（不吞异常），否则无法进入 error 态。
 * retry() 不复位成 loading 态——错误提示连同重试按钮会在重试期间消失，
 * 用户看不到「正在重试」而以为按钮没生效。
 */
import { computed, ref } from 'vue'

export function useLoadState(loader, options = {}) {
  const { failMessage = '加载失败', emptyMessage = '接口未返回数据' } = options
  const state = ref('loading')
  const errorMessage = ref('')
  const retrying = ref(false)

  const isLoading = computed(() => state.value === 'loading')
  const isError = computed(() => state.value === 'error')
  const isReady = computed(() => state.value === 'ready')

  async function attempt() {
    try {
      const data = await loader()
      if (data === null || data === undefined) {
        state.value = 'error'
        errorMessage.value = emptyMessage
        return false
      }
      state.value = 'ready'
      errorMessage.value = ''
      return true
    } catch (e) {
      state.value = 'error'
      errorMessage.value = e?.message || failMessage
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

  return { state, errorMessage, isLoading, isError, isReady, retrying, load, retry }
}
