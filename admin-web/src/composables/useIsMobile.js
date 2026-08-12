import { ref, onMounted, onBeforeUnmount } from 'vue';

// 响应式移动端判定（移植自 Karpathy-Wiki 的 useIsMobile，适配本项目的 vue-router 架构）。
//
// 设计要点（与 Karpathy 一致）：
// - 断点 768px：平板（≥768px）回退桌面端布局，手机（<768px）启用 /m 移动端路由。
// - 用 matchMedia 而非读 UA：避免伪装 UA 误判，且能在旋转/缩放/DevTools 设备工具栏切换时
//   实时触发（设备工具栏只改视口、不触发路由导航，因此必须在 App.vue 用 watch 监听 isMobile 变化）。
//
// 与 Karpathy 的差异：
// - Karpathy 是单 SPA、用 v-if="isMobile" 切换根组件；本项目有 vue-router + /m 命名空间，
//   所以这里只暴露响应式 isMobile，真正的"切换"由 App.vue 监听后 router.replace 到对应命名空间完成。
// - 额外提供 ?mode= 会话级覆盖（sessionStorage），便于在宽屏上强制预览移动端（开发/演示用）。

const MOBILE_QUERY = '(max-width: 768px)';

// 会话级强制模式：'mobile' | 'desktop' | null(跟随视口)
const OVERRIDE_KEY = 'admin_force_mode';

export function getForcedMode() {
  try {
    return sessionStorage.getItem(OVERRIDE_KEY);
  } catch {
    return null;
  }
}

// mode: 'mobile' | 'desktop' | 'auto'(清除覆盖，恢复跟随视口)
export function setForcedMode(mode) {
  try {
    if (mode && mode !== 'auto') sessionStorage.setItem(OVERRIDE_KEY, mode);
    else sessionStorage.removeItem(OVERRIDE_KEY);
  } catch {
    /* sessionStorage 不可用时静默忽略 */
  }
}

function mediaMatches() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia(MOBILE_QUERY).matches;
}

// 解析当前应处的模式：显式覆盖优先，否则跟随视口断点
export function resolveMode() {
  const forced = getForcedMode();
  if (forced === 'mobile') return true;
  if (forced === 'desktop') return false;
  return mediaMatches();
}

/**
 * 返回响应式 isMobile。挂载后自动监听视口变化并更新，卸载时移除监听。
 * 同时导出 setForcedMode / getForcedMode 供需要手动覆盖模式的场景使用。
 */
export function useIsMobile() {
  const isMobile = ref(resolveMode());
  let mql = null;

  const update = () => {
    isMobile.value = resolveMode();
  };

  onMounted(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    mql = window.matchMedia(MOBILE_QUERY);
    // 现代浏览器用 addEventListener；老浏览器回退 addListener
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', update);
    } else if (typeof mql.addListener === 'function') {
      mql.addListener(update);
    }
    update();
  });

  onBeforeUnmount(() => {
    if (!mql) return;
    if (typeof mql.removeEventListener === 'function') {
      mql.removeEventListener('change', update);
    } else if (typeof mql.removeListener === 'function') {
      mql.removeListener(update);
    }
  });

  return { isMobile, setForcedMode, getForcedMode };
}
