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
import { useLoadState } from './useLoadState'

// 三态机本体在 useLoadState（T02496 抽出，列表/详情共用）；
// 这里只固定配置页的文案，保留 useConfigLoad 名字给既有配置页与测试断言。
export function useConfigLoad(loader) {
  return useLoadState(loader, {
    failMessage: '配置加载失败',
    emptyMessage: '配置接口未返回数据',
  })
}
