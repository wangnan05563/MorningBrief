// vite.config.js
import { defineConfig } from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/vite/dist/node/index.js";
import vue from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import AutoImport from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/unplugin-auto-import/dist/vite.js";
import Components from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/unplugin-vue-components/dist/vite.js";
import { ElementPlusResolver } from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/unplugin-vue-components/dist/resolvers.js";
import path from "path";
var __vite_injected_original_dirname = "D:\\code\\otherProjects\\20_News\\admin-web";
var vite_config_default = defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需自动导入（减小打包体积）
    AutoImport({
      resolvers: [ElementPlusResolver()]
    }),
    Components({
      resolvers: [ElementPlusResolver()]
    })
  ],
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "src")
    }
  },
  server: {
    port: 5173,
    // 开发环境代理：/admin/api → 后端 FastAPI
    proxy: {
      "/admin/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        // 切换到 modern-compiler API，消除 Dart Sass legacy-js-api 弃用警告（legacy API 将在 Dart Sass 2.0.0 移除）
        api: "modern-compiler"
      }
    }
  },
  // 生产构建：输出到 dist/，nginx 挂载此目录
  build: {
    outDir: "dist",
    assetsDir: "assets",
    // element-plus 按需导入后仍超 500kB（UI 库本身体量大，无法再拆），调高阈值消除警告
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // 拆分第三方依赖到独立 chunk：避免单 chunk 超 500kB 警告，并利用浏览器长期缓存（vendor 不变则不重新下载）
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
          "element-vendor": ["element-plus", "@element-plus/icons-vue"],
          "chart-vendor": ["chart.js", "vue-chartjs"]
        }
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJEOlxcXFxjb2RlXFxcXG90aGVyUHJvamVjdHNcXFxcMjBfTmV3c1xcXFxhZG1pbi13ZWJcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIkQ6XFxcXGNvZGVcXFxcb3RoZXJQcm9qZWN0c1xcXFwyMF9OZXdzXFxcXGFkbWluLXdlYlxcXFx2aXRlLmNvbmZpZy5qc1wiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9pbXBvcnRfbWV0YV91cmwgPSBcImZpbGU6Ly8vRDovY29kZS9vdGhlclByb2plY3RzLzIwX05ld3MvYWRtaW4td2ViL3ZpdGUuY29uZmlnLmpzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCB2dWUgZnJvbSAnQHZpdGVqcy9wbHVnaW4tdnVlJ1xuaW1wb3J0IEF1dG9JbXBvcnQgZnJvbSAndW5wbHVnaW4tYXV0by1pbXBvcnQvdml0ZSdcbmltcG9ydCBDb21wb25lbnRzIGZyb20gJ3VucGx1Z2luLXZ1ZS1jb21wb25lbnRzL3ZpdGUnXG5pbXBvcnQgeyBFbGVtZW50UGx1c1Jlc29sdmVyIH0gZnJvbSAndW5wbHVnaW4tdnVlLWNvbXBvbmVudHMvcmVzb2x2ZXJzJ1xuaW1wb3J0IHBhdGggZnJvbSAncGF0aCdcblxuLy8gVml0ZSBcdTkxNERcdTdGNkVcdUZGMUFcdTVGMDBcdTUzRDFcdTRFRTNcdTc0MDYgKyBcdTc1MUZcdTRFQTdcdTY3ODRcdTVFRkFcbi8vIFx1NUYwMFx1NTNEMVx1NjVGNiAvYWRtaW4vYXBpIFx1NEVFM1x1NzQwNlx1NTIzMFx1NTQwRVx1N0FFRiA4MDAwIFx1N0FFRlx1NTNFM1x1RkYwQ1x1OTA3Rlx1NTE0RCBDT1JTXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICBwbHVnaW5zOiBbXG4gICAgdnVlKCksXG4gICAgLy8gRWxlbWVudCBQbHVzIFx1NjMwOVx1OTcwMFx1ODFFQVx1NTJBOFx1NUJGQ1x1NTE2NVx1RkYwOFx1NTFDRlx1NUMwRlx1NjI1M1x1NTMwNVx1NEY1M1x1NzlFRlx1RkYwOVxuICAgIEF1dG9JbXBvcnQoe1xuICAgICAgcmVzb2x2ZXJzOiBbRWxlbWVudFBsdXNSZXNvbHZlcigpXSxcbiAgICB9KSxcbiAgICBDb21wb25lbnRzKHtcbiAgICAgIHJlc29sdmVyczogW0VsZW1lbnRQbHVzUmVzb2x2ZXIoKV0sXG4gICAgfSksXG4gIF0sXG4gIHJlc29sdmU6IHtcbiAgICBhbGlhczoge1xuICAgICAgJ0AnOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCAnc3JjJyksXG4gICAgfSxcbiAgfSxcbiAgc2VydmVyOiB7XG4gICAgcG9ydDogNTE3MyxcbiAgICAvLyBcdTVGMDBcdTUzRDFcdTczQUZcdTU4ODNcdTRFRTNcdTc0MDZcdUZGMUEvYWRtaW4vYXBpIFx1MjE5MiBcdTU0MEVcdTdBRUYgRmFzdEFQSVxuICAgIHByb3h5OiB7XG4gICAgICAnL2FkbWluL2FwaSc6IHtcbiAgICAgICAgdGFyZ2V0OiAnaHR0cDovL2xvY2FsaG9zdDo4MDAwJyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuICBjc3M6IHtcbiAgICBwcmVwcm9jZXNzb3JPcHRpb25zOiB7XG4gICAgICBzY3NzOiB7XG4gICAgICAgIC8vIFx1NTIwN1x1NjM2Mlx1NTIzMCBtb2Rlcm4tY29tcGlsZXIgQVBJXHVGRjBDXHU2RDg4XHU5NjY0IERhcnQgU2FzcyBsZWdhY3ktanMtYXBpIFx1NUYwM1x1NzUyOFx1OEI2Nlx1NTQ0QVx1RkYwOGxlZ2FjeSBBUEkgXHU1QzA2XHU1NzI4IERhcnQgU2FzcyAyLjAuMCBcdTc5RkJcdTk2NjRcdUZGMDlcbiAgICAgICAgYXBpOiAnbW9kZXJuLWNvbXBpbGVyJyxcbiAgICAgIH0sXG4gICAgfSxcbiAgfSxcbiAgLy8gXHU3NTFGXHU0RUE3XHU2Nzg0XHU1RUZBXHVGRjFBXHU4RjkzXHU1MUZBXHU1MjMwIGRpc3QvXHVGRjBDbmdpbnggXHU2MzAyXHU4RjdEXHU2QjY0XHU3NkVFXHU1RjU1XG4gIGJ1aWxkOiB7XG4gICAgb3V0RGlyOiAnZGlzdCcsXG4gICAgYXNzZXRzRGlyOiAnYXNzZXRzJyxcbiAgICAvLyBlbGVtZW50LXBsdXMgXHU2MzA5XHU5NzAwXHU1QkZDXHU1MTY1XHU1NDBFXHU0RUNEXHU4RDg1IDUwMGtCXHVGRjA4VUkgXHU1RTkzXHU2NzJDXHU4RUFCXHU0RjUzXHU5MUNGXHU1OTI3XHVGRjBDXHU2NUUwXHU2Q0Q1XHU1MThEXHU2MkM2XHVGRjA5XHVGRjBDXHU4QzAzXHU5QUQ4XHU5NjA4XHU1MDNDXHU2RDg4XHU5NjY0XHU4QjY2XHU1NDRBXG4gICAgY2h1bmtTaXplV2FybmluZ0xpbWl0OiAxMjAwLFxuICAgIHJvbGx1cE9wdGlvbnM6IHtcbiAgICAgIG91dHB1dDoge1xuICAgICAgICAvLyBcdTYyQzZcdTUyMDZcdTdCMkNcdTRFMDlcdTY1QjlcdTRGOURcdThENTZcdTUyMzBcdTcyRUNcdTdBQ0IgY2h1bmtcdUZGMUFcdTkwN0ZcdTUxNERcdTUzNTUgY2h1bmsgXHU4RDg1IDUwMGtCIFx1OEI2Nlx1NTQ0QVx1RkYwQ1x1NUU3Nlx1NTIyOVx1NzUyOFx1NkQ0Rlx1ODlDOFx1NTY2OFx1OTU3Rlx1NjcxRlx1N0YxM1x1NUI1OFx1RkYwOHZlbmRvciBcdTRFMERcdTUzRDhcdTUyMTlcdTRFMERcdTkxQ0RcdTY1QjBcdTRFMEJcdThGN0RcdUZGMDlcbiAgICAgICAgbWFudWFsQ2h1bmtzOiB7XG4gICAgICAgICAgJ3Z1ZS12ZW5kb3InOiBbJ3Z1ZScsICd2dWUtcm91dGVyJywgJ3BpbmlhJ10sXG4gICAgICAgICAgJ2VsZW1lbnQtdmVuZG9yJzogWydlbGVtZW50LXBsdXMnLCAnQGVsZW1lbnQtcGx1cy9pY29ucy12dWUnXSxcbiAgICAgICAgICAnY2hhcnQtdmVuZG9yJzogWydjaGFydC5qcycsICd2dWUtY2hhcnRqcyddLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxufSlcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFBaVQsU0FBUyxvQkFBb0I7QUFDOVUsT0FBTyxTQUFTO0FBQ2hCLE9BQU8sZ0JBQWdCO0FBQ3ZCLE9BQU8sZ0JBQWdCO0FBQ3ZCLFNBQVMsMkJBQTJCO0FBQ3BDLE9BQU8sVUFBVTtBQUxqQixJQUFNLG1DQUFtQztBQVN6QyxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTO0FBQUEsSUFDUCxJQUFJO0FBQUE7QUFBQSxJQUVKLFdBQVc7QUFBQSxNQUNULFdBQVcsQ0FBQyxvQkFBb0IsQ0FBQztBQUFBLElBQ25DLENBQUM7QUFBQSxJQUNELFdBQVc7QUFBQSxNQUNULFdBQVcsQ0FBQyxvQkFBb0IsQ0FBQztBQUFBLElBQ25DLENBQUM7QUFBQSxFQUNIO0FBQUEsRUFDQSxTQUFTO0FBQUEsSUFDUCxPQUFPO0FBQUEsTUFDTCxLQUFLLEtBQUssUUFBUSxrQ0FBVyxLQUFLO0FBQUEsSUFDcEM7QUFBQSxFQUNGO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUE7QUFBQSxJQUVOLE9BQU87QUFBQSxNQUNMLGNBQWM7QUFBQSxRQUNaLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxNQUNoQjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQUEsRUFDQSxLQUFLO0FBQUEsSUFDSCxxQkFBcUI7QUFBQSxNQUNuQixNQUFNO0FBQUE7QUFBQSxRQUVKLEtBQUs7QUFBQSxNQUNQO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQTtBQUFBLEVBRUEsT0FBTztBQUFBLElBQ0wsUUFBUTtBQUFBLElBQ1IsV0FBVztBQUFBO0FBQUEsSUFFWCx1QkFBdUI7QUFBQSxJQUN2QixlQUFlO0FBQUEsTUFDYixRQUFRO0FBQUE7QUFBQSxRQUVOLGNBQWM7QUFBQSxVQUNaLGNBQWMsQ0FBQyxPQUFPLGNBQWMsT0FBTztBQUFBLFVBQzNDLGtCQUFrQixDQUFDLGdCQUFnQix5QkFBeUI7QUFBQSxVQUM1RCxnQkFBZ0IsQ0FBQyxZQUFZLGFBQWE7QUFBQSxRQUM1QztBQUFBLE1BQ0Y7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
