import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'

// Vite 配置：开发代理 + 生产构建
// 开发时 /admin/api 代理到后端 8000 端口，避免 CORS
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需自动导入（减小打包体积）
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    // 开发环境代理：/admin/api → 后端 FastAPI
    proxy: {
      '/admin/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
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
})
