// vite.config.js
import { defineConfig } from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/vite/dist/node/index.js";
import vue from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import AutoImport from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/unplugin-auto-import/dist/vite.js";
import Components from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/unplugin-vue-components/dist/vite.js";
import { ElementPlusResolver } from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/unplugin-vue-components/dist/resolvers.js";
import compression from "file:///D:/code/otherProjects/20_News/admin-web/node_modules/vite-plugin-compression/dist/index.mjs";
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
      resolvers: [ElementPlusResolver({ importStyle: "css" })]
    }),
    // gzip 压缩：产出 .gz 文件，由 Nginx 或反向代理按 Accept-Encoding 协商返回
    // 仅压缩 >10KB 的文件，小文件压缩收益不抵 CPU 开销
    compression({
      algorithm: "gzip",
      threshold: 10240,
      deleteOriginFile: false
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
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJEOlxcXFxjb2RlXFxcXG90aGVyUHJvamVjdHNcXFxcMjBfTmV3c1xcXFxhZG1pbi13ZWJcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZmlsZW5hbWUgPSBcIkQ6XFxcXGNvZGVcXFxcb3RoZXJQcm9qZWN0c1xcXFwyMF9OZXdzXFxcXGFkbWluLXdlYlxcXFx2aXRlLmNvbmZpZy5qc1wiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9pbXBvcnRfbWV0YV91cmwgPSBcImZpbGU6Ly8vRDovY29kZS9vdGhlclByb2plY3RzLzIwX05ld3MvYWRtaW4td2ViL3ZpdGUuY29uZmlnLmpzXCI7aW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCB2dWUgZnJvbSAnQHZpdGVqcy9wbHVnaW4tdnVlJ1xuaW1wb3J0IEF1dG9JbXBvcnQgZnJvbSAndW5wbHVnaW4tYXV0by1pbXBvcnQvdml0ZSdcbmltcG9ydCBDb21wb25lbnRzIGZyb20gJ3VucGx1Z2luLXZ1ZS1jb21wb25lbnRzL3ZpdGUnXG5pbXBvcnQgeyBFbGVtZW50UGx1c1Jlc29sdmVyIH0gZnJvbSAndW5wbHVnaW4tdnVlLWNvbXBvbmVudHMvcmVzb2x2ZXJzJ1xuaW1wb3J0IGNvbXByZXNzaW9uIGZyb20gJ3ZpdGUtcGx1Z2luLWNvbXByZXNzaW9uJ1xuaW1wb3J0IHBhdGggZnJvbSAncGF0aCdcblxuLy8gVml0ZSBcdTkxNERcdTdGNkVcdUZGMUFcdTVGMDBcdTUzRDFcdTRFRTNcdTc0MDYgKyBcdTc1MUZcdTRFQTdcdTY3ODRcdTVFRkFcbi8vIFx1NUYwMFx1NTNEMVx1NjVGNiAvYWRtaW4vYXBpIFx1NEVFM1x1NzQwNlx1NTIzMFx1NTQwRVx1N0FFRiA4MDAwIFx1N0FFRlx1NTNFM1x1RkYwQ1x1OTA3Rlx1NTE0RCBDT1JTXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICBwbHVnaW5zOiBbXG4gICAgdnVlKCksXG4gICAgLy8gRWxlbWVudCBQbHVzIFx1NjMwOVx1OTcwMFx1ODFFQVx1NTJBOFx1NUJGQ1x1NTE2NVx1RkYwOFx1NTFDRlx1NUMwRlx1NjI1M1x1NTMwNVx1NEY1M1x1NzlFRlx1RkYwOVxuICAgIEF1dG9JbXBvcnQoe1xuICAgICAgcmVzb2x2ZXJzOiBbRWxlbWVudFBsdXNSZXNvbHZlcigpXSxcbiAgICB9KSxcbiAgICBDb21wb25lbnRzKHtcbiAgICAgIHJlc29sdmVyczogW0VsZW1lbnRQbHVzUmVzb2x2ZXIoeyBpbXBvcnRTdHlsZTogJ2NzcycgfSldLFxuICAgIH0pLFxuICAgIC8vIGd6aXAgXHU1MzhCXHU3RjI5XHVGRjFBXHU0RUE3XHU1MUZBIC5neiBcdTY1ODdcdTRFRjZcdUZGMENcdTc1MzEgTmdpbnggXHU2MjE2XHU1M0NEXHU1NDExXHU0RUUzXHU3NDA2XHU2MzA5IEFjY2VwdC1FbmNvZGluZyBcdTUzNEZcdTU1NDZcdThGRDRcdTU2REVcbiAgICAvLyBcdTRFQzVcdTUzOEJcdTdGMjkgPjEwS0IgXHU3Njg0XHU2NTg3XHU0RUY2XHVGRjBDXHU1QzBGXHU2NTg3XHU0RUY2XHU1MzhCXHU3RjI5XHU2NTM2XHU3NkNBXHU0RTBEXHU2MkI1IENQVSBcdTVGMDBcdTk1MDBcbiAgICBjb21wcmVzc2lvbih7XG4gICAgICBhbGdvcml0aG06ICdnemlwJyxcbiAgICAgIHRocmVzaG9sZDogMTAyNDAsXG4gICAgICBkZWxldGVPcmlnaW5GaWxlOiBmYWxzZSxcbiAgICB9KSxcbiAgXSxcbiAgcmVzb2x2ZToge1xuICAgIGFsaWFzOiB7XG4gICAgICAnQCc6IHBhdGgucmVzb2x2ZShfX2Rpcm5hbWUsICdzcmMnKSxcbiAgICB9LFxuICB9LFxuICBzZXJ2ZXI6IHtcbiAgICBwb3J0OiA1MTczLFxuICAgIC8vIFx1NUYwMFx1NTNEMVx1NzNBRlx1NTg4M1x1NEVFM1x1NzQwNlx1RkYxQS9hZG1pbi9hcGkgXHUyMTkyIFx1NTQwRVx1N0FFRiBGYXN0QVBJXG4gICAgcHJveHk6IHtcbiAgICAgICcvYWRtaW4vYXBpJzoge1xuICAgICAgICB0YXJnZXQ6ICdodHRwOi8vbG9jYWxob3N0OjgwMDAnLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG4gIGNzczoge1xuICAgIHByZXByb2Nlc3Nvck9wdGlvbnM6IHtcbiAgICAgIHNjc3M6IHtcbiAgICAgICAgLy8gXHU1MjA3XHU2MzYyXHU1MjMwIG1vZGVybi1jb21waWxlciBBUElcdUZGMENcdTZEODhcdTk2NjQgRGFydCBTYXNzIGxlZ2FjeS1qcy1hcGkgXHU1RjAzXHU3NTI4XHU4QjY2XHU1NDRBXHVGRjA4bGVnYWN5IEFQSSBcdTVDMDZcdTU3MjggRGFydCBTYXNzIDIuMC4wIFx1NzlGQlx1OTY2NFx1RkYwOVxuICAgICAgICBhcGk6ICdtb2Rlcm4tY29tcGlsZXInLFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuICAvLyBcdTc1MUZcdTRFQTdcdTY3ODRcdTVFRkFcdUZGMUFcdThGOTNcdTUxRkFcdTUyMzAgZGlzdC9cdUZGMENuZ2lueCBcdTYzMDJcdThGN0RcdTZCNjRcdTc2RUVcdTVGNTVcbiAgYnVpbGQ6IHtcbiAgICBvdXREaXI6ICdkaXN0JyxcbiAgICBhc3NldHNEaXI6ICdhc3NldHMnLFxuICAgIC8vIGVsZW1lbnQtcGx1cyBcdTYzMDlcdTk3MDBcdTVCRkNcdTUxNjVcdTU0MEVcdTRFQ0RcdThEODUgNTAwa0JcdUZGMDhVSSBcdTVFOTNcdTY3MkNcdThFQUJcdTRGNTNcdTkxQ0ZcdTU5MjdcdUZGMENcdTY1RTBcdTZDRDVcdTUxOERcdTYyQzZcdUZGMDlcdUZGMENcdThDMDNcdTlBRDhcdTk2MDhcdTUwM0NcdTZEODhcdTk2NjRcdThCNjZcdTU0NEFcbiAgICBjaHVua1NpemVXYXJuaW5nTGltaXQ6IDEyMDAsXG4gICAgcm9sbHVwT3B0aW9uczoge1xuICAgICAgb3V0cHV0OiB7XG4gICAgICAgIC8vIFx1NjJDNlx1NTIwNlx1N0IyQ1x1NEUwOVx1NjVCOVx1NEY5RFx1OEQ1Nlx1NTIzMFx1NzJFQ1x1N0FDQiBjaHVua1x1RkYxQVx1OTA3Rlx1NTE0RFx1NTM1NSBjaHVuayBcdThEODUgNTAwa0IgXHU4QjY2XHU1NDRBXHVGRjBDXHU1RTc2XHU1MjI5XHU3NTI4XHU2RDRGXHU4OUM4XHU1NjY4XHU5NTdGXHU2NzFGXHU3RjEzXHU1QjU4XHVGRjA4dmVuZG9yIFx1NEUwRFx1NTNEOFx1NTIxOVx1NEUwRFx1OTFDRFx1NjVCMFx1NEUwQlx1OEY3RFx1RkYwOVxuICAgICAgICBtYW51YWxDaHVua3M6IHtcbiAgICAgICAgICAndnVlLXZlbmRvcic6IFsndnVlJywgJ3Z1ZS1yb3V0ZXInLCAncGluaWEnXSxcbiAgICAgICAgICAnZWxlbWVudC12ZW5kb3InOiBbJ2VsZW1lbnQtcGx1cycsICdAZWxlbWVudC1wbHVzL2ljb25zLXZ1ZSddLFxuICAgICAgICAgICdjaGFydC12ZW5kb3InOiBbJ2NoYXJ0LmpzJywgJ3Z1ZS1jaGFydGpzJ10sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gIH0sXG59KVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUFpVCxTQUFTLG9CQUFvQjtBQUM5VSxPQUFPLFNBQVM7QUFDaEIsT0FBTyxnQkFBZ0I7QUFDdkIsT0FBTyxnQkFBZ0I7QUFDdkIsU0FBUywyQkFBMkI7QUFDcEMsT0FBTyxpQkFBaUI7QUFDeEIsT0FBTyxVQUFVO0FBTmpCLElBQU0sbUNBQW1DO0FBVXpDLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLFNBQVM7QUFBQSxJQUNQLElBQUk7QUFBQTtBQUFBLElBRUosV0FBVztBQUFBLE1BQ1QsV0FBVyxDQUFDLG9CQUFvQixDQUFDO0FBQUEsSUFDbkMsQ0FBQztBQUFBLElBQ0QsV0FBVztBQUFBLE1BQ1QsV0FBVyxDQUFDLG9CQUFvQixFQUFFLGFBQWEsTUFBTSxDQUFDLENBQUM7QUFBQSxJQUN6RCxDQUFDO0FBQUE7QUFBQTtBQUFBLElBR0QsWUFBWTtBQUFBLE1BQ1YsV0FBVztBQUFBLE1BQ1gsV0FBVztBQUFBLE1BQ1gsa0JBQWtCO0FBQUEsSUFDcEIsQ0FBQztBQUFBLEVBQ0g7QUFBQSxFQUNBLFNBQVM7QUFBQSxJQUNQLE9BQU87QUFBQSxNQUNMLEtBQUssS0FBSyxRQUFRLGtDQUFXLEtBQUs7QUFBQSxJQUNwQztBQUFBLEVBQ0Y7QUFBQSxFQUNBLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQTtBQUFBLElBRU4sT0FBTztBQUFBLE1BQ0wsY0FBYztBQUFBLFFBQ1osUUFBUTtBQUFBLFFBQ1IsY0FBYztBQUFBLE1BQ2hCO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLEtBQUs7QUFBQSxJQUNILHFCQUFxQjtBQUFBLE1BQ25CLE1BQU07QUFBQTtBQUFBLFFBRUosS0FBSztBQUFBLE1BQ1A7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBO0FBQUEsRUFFQSxPQUFPO0FBQUEsSUFDTCxRQUFRO0FBQUEsSUFDUixXQUFXO0FBQUE7QUFBQSxJQUVYLHVCQUF1QjtBQUFBLElBQ3ZCLGVBQWU7QUFBQSxNQUNiLFFBQVE7QUFBQTtBQUFBLFFBRU4sY0FBYztBQUFBLFVBQ1osY0FBYyxDQUFDLE9BQU8sY0FBYyxPQUFPO0FBQUEsVUFDM0Msa0JBQWtCLENBQUMsZ0JBQWdCLHlCQUF5QjtBQUFBLFVBQzVELGdCQUFnQixDQUFDLFlBQVksYUFBYTtBQUFBLFFBQzVDO0FBQUEsTUFDRjtBQUFBLElBQ0Y7QUFBQSxFQUNGO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
