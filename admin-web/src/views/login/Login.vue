<template>
  <div class="login-page">
    <!-- 装饰背景层：纯 CSS + SVG 绘制，通过 CSS 变量自动适配各主题色 -->
    <div class="bg-decor">
      <!-- 大色块光晕：两个径向渐变球，缓慢浮动 -->
      <div class="blob blob-1" />
      <div class="blob blob-2" />
      <div class="blob blob-3" />

      <!-- 声波圆环：呼应 favicon 声波图标，象征播客新闻 -->
      <svg class="rings" viewBox="0 0 600 600" xmlns="http://www.w3.org/2000/svg">
        <circle cx="300" cy="300" r="120" fill="none" stroke="var(--color-primary)" stroke-width="1.5" opacity="0.15" />
        <circle cx="300" cy="300" r="180" fill="none" stroke="var(--color-primary)" stroke-width="1.5" opacity="0.10" />
        <circle cx="300" cy="300" r="240" fill="none" stroke="var(--color-primary)" stroke-width="1.5" opacity="0.06" />
      </svg>

      <!-- 漂浮粒子：小圆点错落分布 -->
      <div class="particles">
        <span v-for="n in 12" :key="n" class="particle" :style="particleStyle(n)" />
      </div>
    </div>

    <!-- 登录卡片 -->
    <div class="login-card">
      <!-- 机器人 IP 头像：SVG 绘制，戴耳机的新闻主播机器人 -->
      <div class="avatar-wrap">
        <svg class="robot-avatar" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
          <!-- 头部主体：圆角方形 -->
          <rect x="28" y="24" width="64" height="64" rx="20" ry="20" fill="var(--color-primary)" opacity="0.9" />
          <!-- 天线 -->
          <line x1="60" y1="24" x2="60" y2="14" stroke="var(--color-primary-dark)" stroke-width="2.5" stroke-linecap="round" />
          <circle cx="60" cy="12" r="3.5" fill="var(--color-primary-dark)" />
          <!-- 眼睛：两个白圆点 -->
          <circle cx="48" cy="50" r="6" fill="#FFFFFF" />
          <circle cx="72" cy="50" r="6" fill="#FFFFFF" />
          <circle cx="48" cy="50" r="2.5" fill="var(--color-primary-dark)" />
          <circle cx="72" cy="50" r="2.5" fill="var(--color-primary-dark)" />
          <!-- 腮红 -->
          <ellipse cx="40" cy="64" rx="4" ry="2.5" fill="var(--color-secondary)" opacity="0.6" />
          <ellipse cx="80" cy="64" rx="4" ry="2.5" fill="var(--color-secondary)" opacity="0.6" />
          <!-- 嘴巴：小弧线微笑 -->
          <path d="M 52 68 Q 60 74 68 68" stroke="#FFFFFF" stroke-width="2.5" fill="none" stroke-linecap="round" />
          <!-- 耳机：两侧圆角矩形 -->
          <rect x="20" y="44" width="10" height="20" rx="4" fill="var(--color-primary-dark)" />
          <rect x="90" y="44" width="10" height="20" rx="4" fill="var(--color-primary-dark)" />
          <!-- 耳机连接弧线 -->
          <path d="M 28 44 Q 60 28 92 44" stroke="var(--color-primary-dark)" stroke-width="2.5" fill="none" stroke-linecap="round" />
          <!-- 声波：耳机两侧律动线条 -->
          <g class="sound-wave" stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round" fill="none">
            <line x1="12" y1="50" x2="12" y2="58" opacity="0.6" />
            <line x1="8" y1="48" x2="8" y2="60" opacity="0.4" />
            <line x1="108" y1="50" x2="108" y2="58" opacity="0.6" />
            <line x1="112" y1="48" x2="112" y2="60" opacity="0.4" />
          </g>
          <!-- 身体：小圆角矩形（领口） -->
          <rect x="44" y="88" width="32" height="16" rx="8" fill="var(--color-primary)" opacity="0.7" />
          <circle cx="60" cy="96" r="3" fill="var(--color-secondary)" />
        </svg>
      </div>

      <h1 class="login-title">MorningBrief</h1>
      <p class="login-subtitle">智能新闻播客运营平台</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-btn"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
/**
 * 登录页：磨砂玻璃卡片 + SVG 装饰背景（主题自适应）
 *
 * 设计要点：
 * - 背景全部 CSS + SVG 绘制，通过 var(--color-*) 自动适配 6 套主题
 * - 机器人 IP 形象呼应 favicon 声波图标，传达"AI 新闻主播"定位
 * - 装饰元素缓慢浮动 + 声波律动，营造柔和动态氛围
 * - 登录态由 useUserStore 管理，组件只负责表单与提交
 */
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from '../../utils/message'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

// 12 个粒子错落分布：每个粒子的位置、大小、动画延迟各不相同
// 使用确定性公式而非随机数，确保刷新后位置稳定不闪烁
function particleStyle(n) {
  const positions = [
    { top: '15%', left: '10%', size: 8, delay: 0 },
    { top: '25%', left: '85%', size: 6, delay: 0.5 },
    { top: '70%', left: '8%', size: 10, delay: 1 },
    { top: '80%', left: '90%', size: 7, delay: 1.5 },
    { top: '40%', left: '5%', size: 5, delay: 2 },
    { top: '60%', left: '92%', size: 9, delay: 0.3 },
    { top: '10%', left: '50%', size: 6, delay: 0.8 },
    { top: '90%', left: '45%', size: 8, delay: 1.2 },
    { top: '35%', left: '78%', size: 5, delay: 1.8 },
    { top: '55%', left: '15%', size: 7, delay: 0.6 },
    { top: '85%', left: '70%', size: 6, delay: 2.2 },
    { top: '20%', left: '30%', size: 9, delay: 1.4 },
  ]
  const p = positions[n - 1]
  return {
    top: p.top,
    left: p.left,
    width: p.size + 'px',
    height: p.size + 'px',
    animationDelay: p.delay + 's',
  }
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/review')
  } catch {
    // 错误提示由 axios 拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  // 基础背景：主题色渐变 + 极轻微的径向光晕
  background:
    radial-gradient(ellipse at 30% 20%, var(--color-primary-light) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 80%, var(--color-secondary) 0%, transparent 50%),
    var(--color-bg);
  overflow: hidden;

  // 暗黑主题（showcase）背景特殊处理：霓虹光晕而非色块
  :global([data-theme='showcase']) & {
    background:
      radial-gradient(ellipse at 30% 20%, rgba(0, 229, 255, 0.15) 0%, transparent 50%),
      radial-gradient(ellipse at 70% 80%, rgba(179, 136, 255, 0.12) 0%, transparent 50%),
      var(--color-bg);
  }
}

/* === 装饰背景层 === */
.bg-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

// 浮动色块光晕：模糊大圆，缓慢上下浮动
.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.4;
  animation: float 12s ease-in-out infinite;

  &-1 {
    width: 400px;
    height: 400px;
    top: -100px;
    left: -100px;
    background: var(--color-primary);
  }
  &-2 {
    width: 350px;
    height: 350px;
    bottom: -80px;
    right: -80px;
    background: var(--color-secondary);
    animation-delay: -4s;
  }
  &-3 {
    width: 250px;
    height: 250px;
    top: 50%;
    left: 60%;
    background: var(--color-primary-light);
    opacity: 0.3;
    animation-delay: -8s;
  }
}

// 声波圆环：居中，呼吸缩放
.rings {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 600px;
  height: 600px;
  transform: translate(-50%, -50%);
  animation: breathe 8s ease-in-out infinite;
}

// 漂浮粒子：小圆点，缓慢上下浮动 + 淡入淡出
.particles {
  position: absolute;
  inset: 0;

  .particle {
    position: absolute;
    border-radius: 50%;
    background: var(--color-primary);
    opacity: 0.25;
    animation: particleFloat 6s ease-in-out infinite;
  }
}

@keyframes float {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-30px) scale(1.05); }
}

@keyframes breathe {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.6; }
  50% { transform: translate(-50%, -50%) scale(1.1); opacity: 0.3; }
}

@keyframes particleFloat {
  0%, 100% { transform: translateY(0); opacity: 0.15; }
  50% { transform: translateY(-20px); opacity: 0.35; }
}

/* === 登录卡片 === */
.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  max-width: 90vw;
  padding: 40px 36px 32px;
  // 磨砂玻璃质感：半透明背景 + backdrop-blur
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-lg);
  // 页面加载时渐入 + 上滑
  animation: cardIn 0.6s ease-out;
}

@keyframes cardIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* === 机器人头像 === */
.avatar-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;

  .robot-avatar {
    width: 88px;
    height: 88px;
    // 头像轻微浮动，呼应"活的主播"
    animation: avatarFloat 3s ease-in-out infinite;
  }
}

@keyframes avatarFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

// 声波律动：耳机两侧线条交替缩放
.sound-wave line {
  animation: wavePulse 1.2s ease-in-out infinite;
  transform-origin: center;

  &:nth-child(1) { animation-delay: 0s; }
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0s; }
  &:nth-child(4) { animation-delay: 0.2s; }
}

@keyframes wavePulse {
  0%, 100% { opacity: 0.3; transform: scaleY(0.8); }
  50% { opacity: 0.7; transform: scaleY(1.2); }
}

.login-title {
  text-align: center;
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary-dark);
  margin-bottom: 4px;
  letter-spacing: 1px;
}

.login-subtitle {
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 28px;
  letter-spacing: 0.5px;
}

// 输入框大圆角，与马卡龙风格统一
:deep(.el-input__wrapper) {
  border-radius: var(--radius-md);
}

.login-btn {
  width: 100%;
  border-radius: var(--radius-md);
  font-weight: 600;
  letter-spacing: 2px;
}
</style>
