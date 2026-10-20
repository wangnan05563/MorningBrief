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
        ref="passwordRef"
        v-model="password"
        class="m-input"
        type="password"
        placeholder="密码"
        autocomplete="current-password"
      />
      <!-- 失败原因常驻：移动端 toast 更容易被忽略，且键盘收起后用户看不到提示 -->
      <p v-if="loginError" class="m-login__error" role="alert" data-testid="login-error">{{ loginError }}</p>
      <button class="m-btn m-btn--primary" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登 录' }}
      </button>
    </form>

    <p class="m-login__hint">建议使用企业微信/钉钉内置浏览器访问</p>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { ElMessage } from '../../utils/message'
import { describeLoginError } from '../../utils/loginError'
import { sanitizeRedirect, isMobilePath } from '../../utils/urlState'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const loginError = ref('')
const passwordRef = ref(null)

async function onLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  loginError.value = ''
  try {
    await userStore.login(username.value, password.value)
    // 深链优先（T02511 / FR-UX-602）：只接受仍留在 /m 命名空间内的 redirect，
    // 否则手机上会被送回 PC 页再由 App.vue 反弹回来，出现一次无谓的闪烁。
    const back = sanitizeRedirect(route.query.redirect)
    router.replace(back && isMobilePath(back) ? back : '/m/home')
  } catch (e) {
    // 保留已输入内容，把原因常驻显示并聚焦密码框（FR-UX-304）
    loginError.value = describeLoginError(e)
    await nextTick()
    passwordRef.value?.focus?.()
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

.m-login__error {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef0f0;
  color: #d54941;
  font-size: 14px;
  line-height: 1.5;
  text-align: left;
}

.m-login__hint {
  margin-top: 20px;
  color: #b0b4bb;
  font-size: 12px;
}
</style>
