<template>
  <div class="login-page">
    <!-- 装饰背景层：Aqueous Whisper 声波图谱 PNG + CSS 动态色块，随主题色混合变换 -->
    <div class="bg-decor">
      <!-- 艺术背景层：声波图谱 PNG，通过 mix-blend-mode 与主题色融合，实现随主题变换 -->
      <!-- 背景图用内联 style：CSS url() 不支持 Vite base，需在 JS 中拼接路径 -->
      <div class="bg-art" :style="{ backgroundImage: `url(${publicPath}login/aqueous-whisper-bg.png)` }" />

      <!-- 大色块光晕：径向渐变球，缓慢浮动，与背景图声波叠加营造呼吸感 -->
      <div class="blob blob-1" />
      <div class="blob blob-2" />
      <div class="blob blob-3" />

      <!-- 漂浮粒子：小圆点错落分布 -->
      <div class="particles">
        <span v-for="n in 12" :key="n" class="particle" :style="particleStyle(n)" />
      </div>
    </div>

    <!-- 登录卡片 -->
    <div class="login-card">
      <!-- 品牌图标：Aqueous Whisper 声纹胶囊，磨砂玻璃质感抽象 IP，替代具象机器人 -->
      <div class="avatar-wrap">
        <img :src="`${publicPath}login/aqueous-whisper-icon.png`" alt="MorningBrief" class="brand-icon" />
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
 * 登录页：磨砂玻璃卡片 + Aqueous Whisper 声波图谱（主题自适应）
 *
 * 设计要点：
 * - 背景由 PNG 声波图谱（Aqueous Whisper 艺术运动）+ CSS 浮动光晕层叠而成
 * - 通过 mix-blend-mode（multiply/screen）让单张中性 macaron 背景图随 6 套主题色融合变换
 * - 品牌图标采用磨砂玻璃质感声纹胶囊，呼应"声波凝结成图谱"的设计哲学
 * - 装饰元素缓慢浮动，营造柔和动态氛围
 * - 登录态由 useUserStore 管理，组件只负责表单与提交
 */
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from '../../utils/message'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'

// publicPath 跟随 Vite base：base='/news/' 时 publicPath='/news/'
// public/ 目录的文件引用不会自动加 base 前缀，需手动拼接
const publicPath = import.meta.env.BASE_URL

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
    // 登录后跳转到审核页（懒加载分块）；catch 避免分块瞬时拉取失败冒泡为 Uncaught
    router.push('/review').catch((err) => console.warn('[Login] 跳转被拒绝（已静默处理）:', err?.message || err))
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

// 艺术背景层：Aqueous Whisper 声波图谱 PNG
// 浅色主题用 multiply（声波纹理融入主题色渐变），暗色主题用 screen（浅色声波在深底上提亮显现）
// 这样一张中性偏 macaron 的背景图即可随 6 套主题色融合变换
.bg-art {
  position: absolute;
  inset: 0;
  // background-image 由内联 style 设置（跟随 Vite base path）
  background-size: cover;
  background-position: center;
  opacity: 0.62;
  mix-blend-mode: multiply;

  // showcase 暗黑主题：浅色 PNG 在深底上用 screen 提亮，避免被黑色吞没
  :global([data-theme='showcase']) & {
    mix-blend-mode: screen;
    opacity: 0.48;
  }
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

/* === 品牌图标 === */
.avatar-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;

  .brand-icon {
    width: 96px;
    height: 96px;
    // 图标轻微浮动，呼应声波呼吸
    animation: avatarFloat 3s ease-in-out infinite;
    // 圆形柔光，融入磨砂玻璃质感
    filter: drop-shadow(0 4px 12px rgba(126, 206, 193, 0.18));
  }
}

@keyframes avatarFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
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
