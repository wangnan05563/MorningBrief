<template>
  <div class="page-container admin-users-page" data-guide="admin-users-page">
    <div class="top-bar">
      <el-input
        v-model="keyword"
        class="search-input"
        placeholder="搜索用户名 / 昵称"
        clearable
        @keyup.enter="load"
        @clear="load"
      />
      <el-button :loading="loading" @click="load">查询</el-button>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增账号</el-button>
    </div>

    <el-alert type="info" :closable="false" show-icon class="scope-tip">
      <template #title>
        这里管理的是可登录运营后台的账号（管理员 / 运营）。小程序终端用户请在移动端「用户管理」中处理。
      </template>
    </el-alert>

    <el-card shadow="never">
      <ListLoadError
        v-if="error"
        :message="error"
        :retrying="loading"
        :stale="list.length > 0"
        @retry="load"
      />
      <el-table
        v-else
        data-guide="admin-users-table"
        :data="list"
        v-loading="loading"
        stripe
      >
        <el-table-column label="用户名" min-width="140">
          <template #default="{ row }">
            <span>{{ row.username }}</span>
            <el-tag v-if="isSelf(row)" size="small" type="info" effect="plain" class="self-tag">
              当前登录
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="nickname" label="昵称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.nickname || '-' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="enumTagType(ADMIN_ROLE, row.role)" effect="plain">
              {{ enumLabel(ADMIN_ROLE, row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'" effect="plain">
              {{ row.status ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="170">
          <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" :disabled="isSelf(row)" @click="openReset(row)">
              重置口令
            </el-button>
            <el-button
              link
              :type="row.status ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status ? '禁用' : '启用' }}
            </el-button>
            <el-button link type="danger" :disabled="isSelf(row)" @click="remove(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- T02909：账号增删改停都写 category=admin_user，审计挂在动作发生的同页 -->
    <AuditTrail category="admin_user" guide="admin-user-audit" title="最近账号变更审计" :limit="5" />

    <el-dialog
      v-model="createVisible"
      title="新增后台账号"
      width="480px"
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="3-32 位字母、数字或下划线" autocomplete="off" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="createForm.nickname" placeholder="用于列表与审计展示（可选）" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" class="full-width">
            <el-option
              v-for="opt in roleOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="初始口令" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="`至少 ${MIN_ADMIN_PASSWORD_LEN} 位`"
          />
        </el-form-item>
        <el-form-item label="备注 / 原因（可选，会写入审计）" prop="reason">
          <el-input v-model="createForm.reason" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editVisible"
      :title="`编辑账号「${editForm.username}」`"
      width="480px"
      :close-on-click-modal="false"
      @closed="resetEditForm"
    >
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-position="top">
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="editForm.nickname" placeholder="留空表示不设置昵称" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="editForm.role" class="full-width" :disabled="editingSelf">
            <el-option
              v-for="opt in roleOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <div v-if="editingSelf" class="field-hint">不能修改自己的角色</div>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch
            v-model="editForm.status"
            :active-value="1"
            :inactive-value="0"
            active-text="启用"
            inactive-text="禁用"
            :disabled="editingSelf"
          />
          <div v-if="editingSelf" class="field-hint">不能禁用当前登录的账号</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="resetVisible"
      :title="`重置口令「${resetForm.username}」`"
      width="480px"
      :close-on-click-modal="false"
      @closed="resetResetForm"
    >
      <el-alert type="warning" :closable="false" show-icon class="reset-tip">
        <template #title>
          重置后该账号的旧口令立即失效；已登录的会话最长仍会持续到当前凭证过期（约 2 小时）。
          如需立即失效，请让其先退出登录。
        </template>
      </el-alert>
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-position="top">
        <el-form-item label="新口令" prop="password">
          <el-input
            v-model="resetForm.password"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="`至少 ${MIN_ADMIN_PASSWORD_LEN} 位`"
          />
        </el-form-item>
        <el-form-item label="确认新口令" prop="confirm">
          <el-input
            v-model="resetForm.confirm"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="请再次输入新口令"
          />
        </el-form-item>
        <el-form-item label="操作原因（可选，会写入审计）" prop="reason">
          <el-input v-model="resetForm.reason" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="warning" :loading="submitting" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 后台账号管理（T03439，参考 wiki 项目用户权限模块）
 *
 * 管的是「能登录后台的账号」，与移动端 C 端用户管理（/m/manage/users）不是一件事。
 * 与后端同口径的守卫在这里也做一遍：自己不能降级/禁用/删自己，最后一个启用管理员不能动。
 * 服务端仍是最终判据——前端守卫只负责把不可点的按钮先灰掉。
 *
 * 会话边界：admin JWT 有效期 2 小时，禁用/降级不会立刻吊销已签发 token，
 * 因此界面文案只承诺「下次登录被拒」，不承诺「立即下线」。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from '../../utils/message'
import { dangerConfirmWithReason } from '../../utils/dangerConfirm'
import { useUserStore } from '../../stores/user'
import { ADMIN_ROLE, enumLabel, enumOptions, enumTagType } from '../../constants/enums'
import { MIN_ADMIN_PASSWORD_LEN } from '../../constants/password'
import {
  createAdminUser,
  deleteAdminUser,
  listAdminUsers,
  updateAdminUser,
} from '../../api/adminUsers'
import ListLoadError from '../../components/ListLoadError.vue'
import AuditTrail from '../../components/AuditTrail.vue'

const userStore = useUserStore()
const roleOptions = enumOptions(ADMIN_ROLE)

const keyword = ref('')
const list = ref([])
const loading = ref(false)
const error = ref('')
const submitting = ref(false)

const createVisible = ref(false)
const createFormRef = ref()
const createForm = reactive({
  username: '',
  nickname: '',
  role: 'operator',
  password: '',
  reason: '',
})

const editVisible = ref(false)
const editFormRef = ref()
const editForm = reactive({
  id: null,
  username: '',
  nickname: '',
  role: 'operator',
  status: 1,
  originRole: 'operator',
  originStatus: 1,
  originNickname: '',
})

const resetVisible = ref(false)
const resetFormRef = ref()
const resetForm = reactive({
  id: null,
  username: '',
  password: '',
  confirm: '',
  reason: '',
})

const editingSelf = computed(() => editForm.username === userStore.username)

const createRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9_]{3,32}$/,
      message: '用户名需为 3-32 位字母、数字或下划线',
      trigger: 'blur',
    },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [
    { required: true, message: '请输入初始口令', trigger: 'blur' },
    {
      min: MIN_ADMIN_PASSWORD_LEN,
      message: `口令至少 ${MIN_ADMIN_PASSWORD_LEN} 位`,
      trigger: 'blur',
    },
  ],
}

const editRules = {
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

const resetRules = {
  password: [
    { required: true, message: '请输入新口令', trigger: 'blur' },
    {
      min: MIN_ADMIN_PASSWORD_LEN,
      message: `口令至少 ${MIN_ADMIN_PASSWORD_LEN} 位`,
      trigger: 'blur',
    },
  ],
  confirm: [
    { required: true, message: '请再次输入新口令', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== resetForm.password) callback(new Error('两次输入的口令不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

function isSelf(row) {
  return row.username === userStore.username
}

function formatTime(iso) {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listAdminUsers({
      keyword: keyword.value.trim() || undefined,
      page: 1,
      size: 100,
    })
    list.value = data?.list ?? []
  } catch (e) {
    error.value = e?.message || '账号列表读取失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createVisible.value = true
}

function resetCreateForm() {
  createFormRef.value?.resetFields()
  Object.assign(createForm, {
    username: '',
    nickname: '',
    role: 'operator',
    password: '',
    reason: '',
  })
}

async function submitCreate() {
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await createAdminUser({
      username: createForm.username.trim(),
      nickname: createForm.nickname.trim(),
      role: createForm.role,
      password: createForm.password,
      reason: createForm.reason.trim(),
    })
    createVisible.value = false
    ElMessage.success('账号已创建')
    await load()
  } catch {
    // 拦截器已提示（重名 / 口令长度 / 角色非法等）
  } finally {
    submitting.value = false
  }
}

function openEdit(row) {
  Object.assign(editForm, {
    id: row.id,
    username: row.username,
    nickname: row.nickname || '',
    role: row.role,
    status: row.status,
    originRole: row.role,
    originStatus: row.status,
    originNickname: row.nickname || '',
  })
  editVisible.value = true
}

function resetEditForm() {
  editFormRef.value?.resetFields()
}

async function submitEdit() {
  try {
    await editFormRef.value.validate()
  } catch {
    return
  }

  const payload = {}
  const lines = []
  if (editForm.role !== editForm.originRole) {
    payload.role = editForm.role
    lines.push(
      `角色：${enumLabel(ADMIN_ROLE, editForm.originRole)} → ${enumLabel(ADMIN_ROLE, editForm.role)}`,
    )
  }
  if (editForm.status !== editForm.originStatus) {
    payload.status = editForm.status
    lines.push(`状态：${editForm.originStatus ? '启用' : '禁用'} → ${editForm.status ? '启用' : '禁用'}`)
  }
  if (editForm.nickname.trim() !== editForm.originNickname) {
    payload.nickname = editForm.nickname.trim()
  }

  if (!Object.keys(payload).length) {
    ElMessage.info('没有修改')
    return
  }

  if (lines.length) {
    const nextStatus = payload.status ?? editForm.originStatus
    if (nextStatus === 0) {
      lines.push('禁用后该账号无法再登录；已登录的会话最长再持续约 2 小时。')
    }
    if (payload.role === 'operator' && editForm.originRole === 'admin') {
      lines.push('降级后该账号不能再执行管理员操作；已签发的会话最长再持续约 2 小时。')
    }
    const { confirmed, reason } = await dangerConfirmWithReason({
      action: '修改后台账号',
      target: `「${editForm.username}」`,
      scope: '后台账号 1 个',
      lines,
      irreversible: '权限调整可再改回，但调整期间的操作权限不会追溯。',
      confirmLabel: '确认修改',
    })
    if (!confirmed) return
    payload.reason = reason
  }

  submitting.value = true
  try {
    await updateAdminUser(editForm.id, payload)
    editVisible.value = false
    ElMessage.success('账号已更新')
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

function openReset(row) {
  Object.assign(resetForm, {
    id: row.id,
    username: row.username,
    password: '',
    confirm: '',
    reason: '',
  })
  resetVisible.value = true
}

function resetResetForm() {
  resetFormRef.value?.resetFields()
}

async function submitReset() {
  try {
    await resetFormRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await updateAdminUser(resetForm.id, {
      password: resetForm.password,
      reason: resetForm.reason.trim(),
    })
    resetVisible.value = false
    ElMessage.success('口令已重置，请通过安全渠道告知对方')
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row) {
  const next = row.status ? 0 : 1
  const action = next ? '启用后台账号' : '禁用后台账号'
  const { confirmed, reason } = await dangerConfirmWithReason({
    action,
    target: `「${row.username}」`,
    scope: '后台账号 1 个',
    lines: next
      ? ['启用后该账号可重新登录后台。']
      : [
          '禁用后该账号无法再登录后台。',
          '已登录的会话最长再持续约 2 小时；如需立即失效，请让其先退出登录。',
        ],
    irreversible: next ? '可随时改回禁用。' : '可随时改回启用，但禁用期间的访问不会被补回。',
    confirmLabel: `确认${next ? '启用' : '禁用'}`,
  })
  if (!confirmed) return
  try {
    await updateAdminUser(row.id, { status: next, reason })
    ElMessage.success(`已${next ? '启用' : '禁用'}`)
    await load()
  } catch {
    // 拦截器已提示
  }
}

async function remove(row) {
  const { confirmed, reason } = await dangerConfirmWithReason({
    action: '删除后台账号',
    target: `「${row.username}」`,
    scope: '后台账号 1 个',
    lines: ['该账号将立即从列表移除，之后无法登录后台。', '历史审计记录保留。'],
    irreversible: '删除后不可恢复；重新创建同名账号也不会带回旧口令与登录记录。',
    confirmLabel: '确认删除',
  })
  if (!confirmed) return
  try {
    await deleteAdminUser(row.id, reason)
    ElMessage.success('账号已删除')
    await load()
  } catch {
    // 拦截器已提示
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.top-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.search-input {
  width: 260px;
}

.scope-tip {
  margin-bottom: 12px;
}

.self-tag {
  margin-left: 6px;
}

.full-width {
  width: 100%;
}

.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--m-text-sub);
}

.reset-tip {
  margin-bottom: 12px;
}
</style>
