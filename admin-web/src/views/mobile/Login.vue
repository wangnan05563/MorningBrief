<template>
  <div class="m-login">
    <div class="m-login__brand">运营助手</div>
    <p class="m-login__sub">移动端运营管理</p>

    <form class="m-login__form" @submit.prevent="onLogin">
      <input
        v-model="username"
        class="m-input"
        type="text"
        placeholder="账号"
        autocomplete="username"
      />
      <input
        v-model="password"
        class="m-input"
        type="password"
        placeholder="密码"
        autocomplete="current-password"
      />
      <button class="m-btn m-btn--primary" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登 录' }}
      </button>
    </form>

    <p class="m-login__hint">建议使用企业微信/钉钉内置浏览器访问</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { ElMessage } from '../../utils/message'

const router = useRouter()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function onLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    await userStore.login(username.value, password.value)
    router.replace('/m/home')
  } catch {
    // 错误已由响应拦截器统一提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.m-login {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #f5f6f8;
}

.m-login__brand {
  font-size: 26px;
  font-weight: 700;
  color: var(--el-color-primary, #409eff);
}

.m-login__sub {
  margin: 8px 0 28px;
  color: #8a8f99;
  font-size: 14px;
}

.m-login__form {
  width: 100%;
  max-width: 320px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.m-input {
  height: 46px;
  border: 1px solid #dcdfe6;
  border-radius: 10px;
  padding: 0 14px;
  font-size: 16px; /* ≥16px 避免 iOS 聚焦放大 */
  background: #fff;
  outline: none;
}

.m-input:focus {
  border-color: var(--el-color-primary, #409eff);
}

.m-btn {
  height: 46px;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

.m-btn--primary {
  background: var(--el-color-primary, #409eff);
  color: #fff;
}

.m-btn--primary:disabled {
  opacity: 0.6;
}

.m-login__hint {
  margin-top: 20px;
  color: #b0b4bb;
  font-size: 12px;
}
</style>
