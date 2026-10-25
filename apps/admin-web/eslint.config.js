/**
 * ESLint flat config（T02610 / 来源 T02493）
 *
 * 为什么要它：`CosFiles.vue` 调了 `dangerConfirm(...)` 却没 import，Vue 模板/组合式 API
 * 这种「用了没导入」不会编译报错，运行时 ReferenceError 又被全局 Promise 守卫吞掉，
 * 界面表现成「点了没反应」——只有 e2e 断言确认框存在时才暴露。
 *
 * 范围刻意收窄：只开两条「错法静默、后果是假按钮」的规则，不用 recommended 全家桶。
 * - no-undef：引用未导入的变量/工具函数（<script setup> 里同样生效）；
 * - import/no-unresolved：import 路径写错/文件被删。
 * 其余风格类规则不进本仓，避免一次性制造几百条与缺陷无关的红。
 *
 * `<script setup>` 的编译器宏（defineProps 等）不是运行时全局，必须显式声明，
 * 否则每份 SFC 都会被 no-undef 误报。
 */
import pluginVue from 'eslint-plugin-vue'
import importPlugin from 'eslint-plugin-import'
import globals from 'globals'
import vueParser from 'vue-eslint-parser'

export default [
  {
    ignores: [
      'dist/**',
      'dist_bgmcheck/**',
      'node_modules/**',
      'playwright-report/**',
      'test-results/**',
      'runtime/**',
      'temp/**',
      'public/**',
    ],
  },
  {
    files: ['src/**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
        defineProps: 'readonly',
        defineEmits: 'readonly',
        defineExpose: 'readonly',
        defineOptions: 'readonly',
        defineSlots: 'readonly',
        defineModel: 'readonly',
        withDefaults: 'readonly',
      },
    },
    plugins: { vue: pluginVue, import: importPlugin },
    rules: {
      'no-undef': 'error',
      'import/no-unresolved': ['error', { commonjs: false, amd: false }],
    },
    settings: {
      // 源码里的相对 import 基本不带扩展名；解析要认得 .vue，否则每条组件引用都会误报
      'import/resolver': {
        node: { extensions: ['.js', '.mjs', '.cjs', '.vue', '.json'] },
      },
    },
  },
  {
    files: ['src/**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
    },
  },
]
