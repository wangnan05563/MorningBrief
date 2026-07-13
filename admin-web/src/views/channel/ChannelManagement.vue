<template>
  <div class="page-container channel-management">
    <!-- 工具栏：标题 + 新增按钮（仅 admin 可见） -->
    <div class="top-bar">
      <span class="page-title">频道管理</span>
      <el-button v-if="canOperate" type="primary" :icon="Plus" @click="openCreate">新增频道</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="定时触发" width="110">
          <template #default="{ row }">
            <span v-if="row.schedule_time">{{ row.schedule_time }}</span>
            <span v-else class="text-muted">默认</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <!-- active-value/inactive-value 必须匹配后端整数 0/1，否则 el-switch 用 === 比较始终判定为 inactive -->
            <el-switch
              v-model="row.is_active"
              :active-value="1"
              :inactive-value="0"
              :disabled="!canOperate"
              @change="(val) => handleToggle(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="170">
          <template #default="{ row }">{{ row.created_at || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="canOperate" label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" :loading="deletingIds.has(row.id)" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗：复用同一 Dialog，通过 editing 标志区分 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑频道' : '新增频道'" width="720px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <!-- 基本信息区 -->
        <el-divider content-position="left">基本信息</el-divider>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入频道名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="频道描述（选填）" />
        </el-form-item>
        <el-form-item label="定时触发">
          <el-input v-model="form.schedule_time" placeholder="HH:MM:SS（如 04:00:00），留空使用全局默认" style="width: 280px" />
          <span class="form-tip">为空则使用全局 cron（05:00）触发</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>

        <!-- 新增频道时可选 AI 自动生成提示词 -->
        <el-form-item v-if="!editing" label="AI 生成">
          <el-checkbox v-model="form.auto_generate_prompts">创建后自动调用 AI 生成提示词</el-checkbox>
        </el-form-item>

        <!-- 提示词区：折叠面板，减少视觉负担 -->
        <el-divider content-position="left">
          <span>频道提示词</span>
          <el-button
            v-if="editing"
            type="primary"
            link
            :loading="generating"
            @click="handleGeneratePrompts"
            style="margin-left: 12px"
          >AI 重新生成</el-button>
        </el-divider>
        <el-collapse v-model="promptCollapse">
          <el-collapse-item title="开场白（intro）" name="intro">
            <el-input v-model="form.intro_prompt" type="textarea" :rows="3" placeholder="留空使用默认开场白" />
          </el-collapse-item>
          <el-collapse-item title="结尾（outro）" name="outro">
            <el-input v-model="form.outro_prompt" type="textarea" :rows="3" placeholder="留空使用默认结尾" />
          </el-collapse-item>
          <el-collapse-item title="敏感词约束（constraint）" name="constraint">
            <el-input v-model="form.constraint_prompt" type="textarea" :rows="3" placeholder="留空使用默认约束" />
          </el-collapse-item>
          <el-collapse-item title="改写模板（template）" name="template">
            <el-input v-model="form.rewrite_template" type="textarea" :rows="8" placeholder="留空使用默认 rewrite.txt 模板" />
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'ChannelManagement' })
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { Plus } from '@element-plus/icons-vue'
import { listChannels, createChannel, updateChannel, deleteChannel, generateChannelPrompts } from '../../api/channels'

// 角色控制：直接读 localStorage，operator 隐藏增删改操作
const role = localStorage.getItem('admin_role') || ''
const canOperate = role === 'admin'

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref(false)
const submitting = ref(false)
const generating = ref(false)
const formRef = ref()

// 行级删除按钮 loading（P1-2.2 防重复点击）
const deletingIds = ref(new Set())

// 提示词折叠面板默认展开第一项
const promptCollapse = ref(['intro'])

const form = reactive({
  id: null,
  name: '',
  description: '',
  is_active: 1,
  schedule_time: '',
  intro_prompt: '',
  outro_prompt: '',
  constraint_prompt: '',
  rewrite_template: '',
  auto_generate_prompts: false,
})

const rules = {
  name: [{ required: true, message: '请输入频道名称', trigger: 'blur' }],
}

async function loadList() {
  loading.value = true
  try {
    const data = await listChannels(false)
    // 兼容后端返回数组或 { list } 两种结构
    list.value = Array.isArray(data) ? data : (data.list || [])
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.id = null
  form.name = ''
  form.description = ''
  form.is_active = 1
  form.schedule_time = ''
  form.intro_prompt = ''
  form.outro_prompt = ''
  form.constraint_prompt = ''
  form.rewrite_template = ''
  form.auto_generate_prompts = false
  promptCollapse.value = ['intro']
}

function openCreate() {
  editing.value = false
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = true
  form.id = row.id
  form.name = row.name
  form.description = row.description || ''
  form.is_active = row.is_active ? 1 : 0
  form.schedule_time = row.schedule_time || ''
  form.intro_prompt = row.intro_prompt || ''
  form.outro_prompt = row.outro_prompt || ''
  form.constraint_prompt = row.constraint_prompt || ''
  form.rewrite_template = row.rewrite_template || ''
  form.auto_generate_prompts = false
  promptCollapse.value = ['intro']
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    if (editing.value) {
      // 编辑：提交所有提示词字段（空字符串表示清空，后端会判断）
      await updateChannel(form.id, {
        name: form.name,
        description: form.description,
        is_active: form.is_active,
        schedule_time: form.schedule_time || '',
        intro_prompt: form.intro_prompt,
        outro_prompt: form.outro_prompt,
        constraint_prompt: form.constraint_prompt,
        rewrite_template: form.rewrite_template,
      })
      ElMessage.success('已更新')
    } else {
      // 新增：仅提交基本信息 + 定时 + AI生成标志，提示词由 AI 生成或留空
      await createChannel({
        name: form.name,
        description: form.description,
        schedule_time: form.schedule_time || null,
        auto_generate_prompts: form.auto_generate_prompts,
      })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await loadList()
  } finally {
    submitting.value = false
  }
}

async function handleToggle(row, val) {
  // val 为整数 1（启用）或 0（禁用），与 el-switch active-value/inactive-value 一致
  try {
    await updateChannel(row.id, { is_active: val })
    ElMessage.success(val ? '已启用' : '已禁用')
  } catch {
    // 请求失败时回滚 switch 状态，保持 UI 与后端一致
    row.is_active = val === 1 ? 0 : 1
  }
}

async function handleDelete(row) {
  // 防重复点击：同一行删除中直接忽略
  if (deletingIds.value.has(row.id)) return
  try {
    await ElMessageBox.confirm(`确认删除频道「${row.name}」？此操作不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
    })
  } catch {
    // 用户取消确认，静默退出
    return
  }
  deletingIds.value.add(row.id)
  try {
    await deleteChannel(row.id)
    ElMessage.success('已删除')
    await loadList()
  } catch (e) {
    console.warn('handleDelete failed:', e)
  } finally {
    deletingIds.value.delete(row.id)
  }
}

async function handleGeneratePrompts() {
  if (!form.id) return
  generating.value = true
  try {
    const data = await generateChannelPrompts(form.id)
    // AI 生成后回填到表单，用户可继续编辑后保存
    form.intro_prompt = data.intro_prompt || ''
    form.outro_prompt = data.outro_prompt || ''
    form.constraint_prompt = data.constraint_prompt || ''
    form.rewrite_template = data.rewrite_template || ''
    ElMessage.success('AI 已生成提示词，可编辑后点击确认保存')
  } catch (e) {
    console.warn('handleGeneratePrompts failed:', e)
  } finally {
    generating.value = false
  }
}

onMounted(() => {
  loadList()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.channel-management {
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: $color-text-primary;
    }
  }

  .text-muted {
    color: $color-text-secondary;
  }

  .form-tip {
    margin-left: 12px;
    font-size: 12px;
    color: $color-text-secondary;
  }
}
</style>
