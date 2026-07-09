<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">20_News 运营后台</h1>
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
 * 登录页：居中卡片 + 渐变背景
 *
 * 设计要点：
 * - 登录态由 useUserStore 管理，组件只负责表单与提交
 * - 登录成功后跳转 /review（运营默认入口）
 * - 错误提示由 axios 拦截器统一处理，此处仅在成功时提示
 */
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
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

async function handleLogin() {
  // 先校验表单，校验失败直接返回不发请求
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
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  // 极浅渐变：薄荷青 → 蜜桃粉，营造柔和氛围而非抢眼
  background: linear-gradient(135deg, rgba(181, 234, 215, 0.45) 0%, rgba(255, 211, 224, 0.45) 100%);
}

.login-card {
  width: 400px;
  max-width: 90vw;
  padding: 40px;
  background: $color-bg-card;
  border-radius: $radius-xl;
  box-shadow: $shadow-lg;
}

.login-title {
  text-align: center;
  font-size: 22px;
  font-weight: 700;
  color: $color-primary-dark;
  margin-bottom: 28px;
  letter-spacing: 1px;
}

// 输入框大圆角，与马卡龙风格统一
:deep(.el-input__wrapper) {
  border-radius: $radius-md;
}

.login-btn {
  width: 100%;
  border-radius: $radius-md;
  font-weight: 600;
  letter-spacing: 2px;
}
</style>
