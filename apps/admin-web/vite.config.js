import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'
import { validate as validateNav } from './scripts/validate-nav.mjs'

/**
 * 导航一致性门禁（T02500 / FR-UX-401）
 *
 * 菜单、引导、帮助文档之间的引用失配属于「文案级」错误：运行时不报错，
 * 只表现为引导气泡指错元素、帮助文档把人带不到页面、侧栏少一项，
 * 用户说不清、e2e 也测不出。所以放在构建期失败，而不是等运行时的偶然反馈。
 *
 * 只挂 build：dev 不该因为一条分组注释漂移而启不了服务（e2e 也跑在 dev 上）。
 * 独立校验走 `npm run validate:nav`。
 */
function navConsistencyGate() {
  return {
    name: 'nav-consistency-gate',
    apply: 'build',
    async buildStart() {
      const { errors } = await validateNav()
      if (errors.length) {
        this.error(`[validate-nav] 导航引用不一致，构建中止：\n${errors.map((e) => `  ✗ ${e}`).join('\n')}`)
      }
    },
  }
}

// Vite 配置：开发代理 + 生产构建
// dev 模式 base 为 '/'：Playwright 测试可直接用 page.goto('/ads/materials') 导航，
//   且 Vite 热更新 / 路由编译均走根路径，避免 /news/ 前缀导致测试 URL 解析问题
// build 模式 base 为 '/news/'：构建产物资源路径带 /news/ 前缀，
//   配合 Tailscale Funnel 的 --set-path /news/ 路径区分模式
// 开发时 /news/admin/api 代理到后端 8000 端口，rewrite 去除 /news 前缀
export default defineConfig(({ command }) => ({
  plugins: [
    vue(),
    // Element Plus 按需自动导入（减小打包体积）
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
    navConsistencyGate(),
  ],
  // dev base '/' 方便本地测试；build base '/news/' 适配生产路径区分
  base: command === 'build' ? '/news/' : '/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    // 端口固定 5181（5173 与其他项目冲突）；strictPort 禁止 Vite 自动跳号，
    // 保证实际端口与测试/文档引用一致
    port: 5181,
    strictPort: true,
    // 开发环境代理：/news/admin/api → 后端 FastAPI（去除 /news 前缀）
    proxy: {
      '/news/admin/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/news/, ''),
      },
      // 频道资源（图标/预制封面）静态目录：T00730 修复——前端预览统一带 /news 前缀
      // （与 axios baseURL 同一约定，生产 Funnel 只路由 /news/*，裸 /channel-assets 会 404）
      '/news/channel-assets': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/news/, ''),
      },
      // 兼容旧入口：不带前缀的裸路径仍代理（DB 里存量 icon_url/cover_url 为相对路径）
      '/channel-assets': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // T00827：启动画面就绪探针（/news/api/health/ready）——与后端健康检查同路径约定，
      // 生产经 Funnel 路由 /news/* 到后端，dev 在此代理并去除 /news 前缀
      '/news/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/news/, ''),
      },
    },
  },
  // 切换到 Sass modern API，避免 legacy JS API 在 Dart Sass 2.0 被移除
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern-compiler',
      },
    },
  },
  // 生产构建：输出到 dist/，nginx 挂载此目录
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // element-plus 经按需导入后仍超 1MB（已拆出 CSS），无法再有效拆分，
    // 调高阈值至 1200kB，仅对真正异常的 chunk 告警
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // 按依赖维度拆分 chunk，避免单个 bundle 过大触发 500kB 告警
        // element-plus 与 chart.js 体积较大且独立，单独拆出便于浏览器长缓存
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
            if (id.includes('chart.js') || id.includes('vue-chartjs')) return 'chart'
            if (id.includes('vue-router') || id.includes('pinia') || id.includes('/vue/')) return 'vue-vendor'
          }
        },
      },
    },
  },
}))
