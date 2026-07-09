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
  // 生产构建：输出到 dist/，nginx 挂载此目录
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
