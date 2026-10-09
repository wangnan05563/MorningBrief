<template>
  <div class="page-container assistant">
    <!-- 顶部：标题 + 模型选择 + 自动刷新 -->
    <div class="as-header">
      <div class="as-title">
        <!-- T00811：主标题「智能助手」与导航栏重复，移除；副标题为功能说明保留 -->
        <span class="as-title-sub">协助管理员对系统菜单做自动调度，AI 生成完整配置、会话内确认落地</span>
      </div>

      <div class="as-model-bar">
        <el-select
          v-model="currentModel"
          placeholder="选择模型"
          filterable
          :loading="loadingModels"
          :disabled="models.length === 0"
          class="as-model-select"
          @change="onModelChange"
        >
          <el-option
            v-for="m in models"
            :key="m.id"
            :label="m.owned_by ? `${m.id}（${m.owned_by}）` : m.id"
            :value="m.id"
          />
        </el-select>

        <el-tooltip :content="autoRefresh ? '自动刷新已开启' : '自动刷新已关闭'" :fallback-placements="['bottom', 'left', 'right']">
          <el-switch
            v-model="autoRefresh"
            inline-prompt
            active-text="自动"
            inactive-text="手动"
            @change="onAutoRefreshChange"
          />
        </el-tooltip>

        <IconButton
          :icon="Refresh"
          :loading="loadingModels"
          label="刷新模型"
          desc="重新拉取可用模型列表"
          @click="fetchModels"
        />
      </div>
    </div>

    <!-- 模型拉取错误提示 -->
    <el-alert
      v-if="modelError"
      type="error"
      :closable="false"
      show-icon
      class="as-alert"
    >
      <template #title>无法获取模型列表</template>
      <span>{{ modelError }}</span>
    </el-alert>

    <!-- 分页签：自动调度 / 知识库问答 -->
    <el-tabs v-model="activeTab" class="as-tabs">
      <!-- ============ 自动调度 ============ -->
      <el-tab-pane label="自动调度" name="dispatch">
        <div class="as-body">
          <div ref="dispatchRef" class="as-messages">
            <div v-if="dispatchMsgs.length === 0" class="as-empty">
              <el-icon class="as-empty-icon"><MagicStick /></el-icon>
              <p>用一句话下达调度指令，例如：</p>
              <ul class="as-examples">
                <li>帮我新增一个 AI 咨询频道，定位科技前沿资讯</li>
                <li>创建一个有声读物频道，主题是历史传记</li>
              </ul>
              <p class="as-empty-tip">
                我会先生成一份可编辑的配置草稿，由你核对确认后再落地到对应菜单。
              </p>
            </div>

            <div v-for="(msg, idx) in dispatchMsgs" :key="idx">
              <!-- 用户消息 -->
              <div v-if="msg.role === 'user'" class="as-msg as-msg-user">
                <div class="as-msg-role">我</div>
                <div class="as-msg-content">{{ msg.content }}</div>
              </div>

              <!-- 助理动作草稿卡片 -->
              <div v-else-if="msg.type === 'action'" class="as-msg as-msg-assistant">
                <div class="as-msg-role">AI</div>
                <div class="as-action-card">
                  <div class="as-action-head">
                    <el-tag type="primary" effect="plain" size="small">{{ msg.group }}</el-tag>
                    <b class="as-action-title">{{ msg.title }}</b>
                    <span
                      v-if="msg.executed"
                      class="as-action-done"
                    >✅ 已创建</span>
                  </div>
                  <div v-if="msg.reason" class="as-action-reason">{{ msg.reason }}</div>

                  <template v-if="msg.executed">
                    <el-result
                      icon="success"
                      :title="`频道「${msg.resultName}」已创建`"
                      sub-title="可在频道管理中查询、修改其完整配置"
                    >
                      <template #extra>
                        <IconButton link type="primary" :icon="ArrowRight" label="前往频道管理" desc="跳转到频道管理页面" @click="goChannels" />
                      </template>
                    </el-result>
                  </template>

                  <template v-else>
                    <!-- 可编辑字段表单 -->
                    <el-form label-position="top" size="small" class="as-action-form">
                      <el-form-item
                        v-for="f in msg.fields"
                        :key="f.key"
                        :label="f.label + (f.required ? ' *' : '')"
                        :required="f.required"
                        :class="f.required ? 'is-required' : ''"
                      >
                        <el-select
                          v-if="f.type === 'select'"
                          v-model="f.value"
                          :placeholder="f.help"
                          clearable
                        >
                          <el-option
                            v-for="o in f.options"
                            :key="o.value"
                            :label="o.label"
                            :value="o.value"
                          />
                        </el-select>
                        <el-input
                          v-else-if="f.type === 'textarea'"
                          v-model="f.value"
                          type="textarea"
                          :rows="2"
                          :placeholder="f.help"
                        />
                        <el-input-number
                          v-else-if="f.type === 'number'"
                          v-model="f.value"
                          :min="0"
                          :max="f.key === 'material_lookback_days' ? 90 : 9999"
                          controls-position="right"
                          style="width: 180px"
                        />
                        <el-switch
                          v-else-if="f.type === 'switch'"
                          v-model="f.value"
                          :active-value="1"
                          :inactive-value="0"
                        />
                        <el-input
                          v-else
                          v-model="f.value"
                          :placeholder="f.help"
                        />
                        <div v-if="f.help && f.type !== 'switch'" class="as-field-tip">{{ f.help }}</div>
                      </el-form-item>
                    </el-form>
                    <div class="as-action-actions">
                      <IconButton
                        type="primary"
                        :icon="Check"
                        :loading="msg.loading"
                        :disabled="!msg.fields.find((f) => f.key === 'name')?.value"
                        label="确认创建"
                        desc="确认并创建该频道"
                        @click="confirmExecute(msg)"
                      />
                      <IconButton :icon="Delete" label="丢弃" desc="丢弃该配置草稿" @click="removeDispatch(idx)" />
                    </div>
                  </template>
                </div>
              </div>

              <!-- 助理文本消息（含非调度回复） -->
              <div v-else class="as-msg as-msg-assistant">
                <div class="as-msg-role">AI</div>
                <div class="as-msg-content">{{ msg.content }}</div>
              </div>
            </div>

            <div v-if="planning" class="as-msg as-msg-assistant">
              <div class="as-msg-role">AI</div>
              <div class="as-msg-content as-typing">正在生成配置草稿…</div>
            </div>
          </div>

          <div class="as-input-bar">
            <el-input
              v-model="dispatchInput"
              type="textarea"
              :rows="3"
              resize="none"
              placeholder="输入调度指令，如：帮我新增一个 AI 咨询频道…"
              :disabled="planning"
              @keydown.enter.exact.prevent="sendPlan"
            />
            <IconButton
              type="primary"
              :icon="Promotion"
              :loading="planning"
              :disabled="!dispatchInput.trim()"
              label="生成草稿"
              desc="生成频道配置草稿，核对后可落地"
              @click="sendPlan"
            />
          </div>
        </div>
      </el-tab-pane>

      <!-- ============ 知识库问答 ============ -->
      <el-tab-pane label="知识库问答" name="qa">
        <div class="as-body">
          <div ref="messagesRef" class="as-messages">
            <div v-if="messages.length === 0" class="as-empty">
              <el-icon class="as-empty-icon"><ChatDotRound /></el-icon>
              <p>向知识库提问吧。当前模型：<b>{{ currentModel || '未选择' }}</b></p>
              <p class="as-empty-tip">切换上方模型后立即生效，无需重启。</p>
            </div>

            <div
              v-for="(msg, idx) in messages"
              :key="idx"
              class="as-msg"
              :class="msg.role === 'user' ? 'as-msg-user' : 'as-msg-assistant'"
            >
              <div class="as-msg-role">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
              <div class="as-msg-content">{{ msg.content }}</div>
            </div>

            <div v-if="replying" class="as-msg as-msg-assistant">
              <div class="as-msg-role">AI</div>
              <div class="as-msg-content as-typing">正在思考…</div>
            </div>
          </div>

          <div class="as-input-bar">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="3"
              resize="none"
              placeholder="输入问题，Enter 发送 / Shift+Enter 换行"
              :disabled="!currentModel || replying"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <IconButton
              type="primary"
              :icon="Promotion"
              :loading="replying"
              :disabled="!currentModel || !inputText.trim()"
              label="发送"
              desc="发送问题到知识库"
              @click="sendMessage"
            />
          </div>
          <div v-if="!currentModel" class="as-input-hint">
            请先在上方选择模型后再提问。
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from '../../utils/message'
import { Refresh, Promotion, ChatDotRound, MagicStick, Check, Delete, ArrowRight } from '@element-plus/icons-vue'
import api from '../../api'
import { planAssistantAction, executeAssistantAction } from '../../api/assistant'

const AUTO_REFRESH_MS = 90_000

// ===== 模型管理（自动调度与问答共用）=====
const models = ref([])
const currentModel = ref('')
const loadingModels = ref(false)
const modelError = ref('')
const autoRefresh = ref(true)

// ===== 分页签 =====
const activeTab = ref('dispatch')
// 切换 tab 后滚动到底部
const tabRefs = {}
function scrollPane(name) {
  nextTick(() => {
    const el = tabRefs[name]
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ===== 自动调度 =====
const dispatchMsgs = ref([])
const dispatchInput = ref('')
const planning = ref(false)
const dispatchRef = ref(null)
tabRefs.dispatch = dispatchRef

const router = useRouter()

// 字段可编辑：直接修改 msg.fields 中对应项的 value
async function sendPlan() {
  const text = dispatchInput.value.trim()
  if (!text || planning.value) return

  dispatchMsgs.value.push({ role: 'user', content: text })
  dispatchInput.value = ''
  planning.value = true
  await scrollDispatch()

  try {
    const data = await planAssistantAction(text, currentModel.value)
    if (data?.is_action) {
      // 动作草稿：合并字段为可编辑对象
      data.fields.forEach((f) => {
        // 显式让每个字段可被动态表单双向绑定
        if (f.type !== 'select') {
          f.value = f.value ?? (f.type === 'switch' ? 1 : (f.type === 'number' ? 0 : ''))
        }
      })
      dispatchMsgs.value.push({
        role: 'assistant',
        type: 'action',
        group: data.group,
        title: data.title,
        reason: data.reason,
        actionId: data.action_id,
        fields: data.fields,
        executed: false,
        loading: false,
        resultName: '',
      })
    } else {
      dispatchMsgs.value.push({
        role: 'assistant',
        type: 'text',
        content: data.raw_reply || data.reason || '暂时无法将这条指令解析为可调度的动作。',
      })
    }
  } catch (e) {
    ElMessage.error(e?.message || '生成草稿失败')
    dispatchMsgs.value.push({
      role: 'assistant',
      type: 'text',
      content: `⚠️ ${e?.message || '生成草稿失败'}`,
    })
  } finally {
    planning.value = false
    await scrollDispatch()
  }
}

async function confirmExecute(msg) {
  if (msg.loading) return
  msg.loading = true
  try {
    // 汇聚为 key:value 字典传给后端
    const fields = {}
    msg.fields.forEach((f) => {
      fields[f.key] = f.value
    })
    const data = await executeAssistantAction(msg.actionId, fields)
    msg.executed = true
    msg.resultName = data?.name || ''
    ElMessage.success(`频道「${data?.name}」已创建`)
    await scrollDispatch()
  } catch (e) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    msg.loading = false
  }
}

function removeDispatch(idx) {
  dispatchMsgs.value.splice(idx, 1)
}

function goChannels() {
  router.push('/channels')
}

async function scrollDispatch() {
  await nextTick()
  if (dispatchRef.value) {
    dispatchRef.value.scrollTop = dispatchRef.value.scrollHeight
  }
}

// ===== 知识库问答（保留原能力）=====
const messages = ref([])
const inputText = ref('')
const replying = ref(false)
const messagesRef = ref(null)
tabRefs.qa = messagesRef

let refreshTimer = null

// 从模型中挑一个适合对话的默认模型：排除 embedding/图像/语音等专用模型，
// 否则会选到第一个模型导致问答报「Model does not exist」。
const NON_CHAT_RE = /embed|rerank|bge-|image|ocr|asr|whisper|tts|voice|diarize|cosyvoice|sensevoice|captioner|kolors|wan|qwen3-omni|deepseek-ocr/i
const CHAT_KEYWORDS = ['Instruct', 'Chat', 'omini', 'Omni', 'GLM-4', 'GLM-5', 'Kimi', 'DeepSeek-V', 'DeepSeek-R']
function pickChatModel(list) {
  const cands = list.filter((m) => !NON_CHAT_RE.test(m.id))
  const hit = CHAT_KEYWORDS.map((kw) => cands.find((m) => m.id.includes(kw))).find(Boolean)
  return hit ? hit.id : (cands.length ? cands[0].id : list[0].id)
}

async function fetchModels(opts = {}) {
  loadingModels.value = true
  if (!opts.silent) modelError.value = ''
  try {
    // 后端使用已保存的 API Base URL / API Key 拉取（API Key 脱敏不回传）
    const data = await api.post('/ai/models', {}, { silent: !!opts.silent })
    if (data?.success) {
      models.value = data.models || []
      modelError.value = ''
      if (models.value.length === 0) {
        modelError.value = '模型列表为空，请确认该账户有可用模型'
      } else {
        // 保持当前选择；若当前模型已不在列表中则回退
        const ids = models.value.map((m) => m.id)
        if (!currentModel.value || !ids.includes(currentModel.value)) {
          // 优先使用已保存的默认模型，否则选一个适合对话的模型
          // （模型列表混有 embedding / 推理 / 图像 / 语音等专用模型，直接取第一个会选错）
          const saved = await loadSelectedModel()
          currentModel.value = saved && ids.includes(saved) ? saved : pickChatModel(models.value)
        }
      }
    } else {
      models.value = []
      modelError.value = data?.message || '获取模型列表失败'
    }
  } catch (e) {
    models.value = []
    modelError.value = e?.message || '获取模型列表失败'
  } finally {
    loadingModels.value = false
  }
}

async function loadSelectedModel() {
  try {
    const data = await api.get('/ai/selected-model', { silent: true })
    return data?.model || ''
  } catch {
    return ''
  }
}

async function onModelChange(val) {
  currentModel.value = val
  // 记录最后选择的模型作为默认选项
  try {
    await api.post('/ai/selected-model', { model: val }, { silent: true })
  } catch {
    /* 静默保存，不影响问答 */
  }
  ElMessage.success(`已切换模型：${val}`)
}

function onAutoRefreshChange(val) {
  if (val) startAutoRefresh()
  else stopAutoRefresh()
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = setInterval(() => fetchModels({ silent: true }), AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || !currentModel.value || replying.value) return

  // 组装对话历史（OpenAI 格式），追加当前问题
  const history = messages.value.map((m) => ({ role: m.role, content: m.content }))
  history.push({ role: 'user', content: text })

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  replying.value = true
  await scrollQa()

  try {
    const data = await api.post('/ai/chat', {
      model: currentModel.value,
      messages: history,
    })
    if (data?.success) {
      messages.value.push({ role: 'assistant', content: data.reply || '(空回复)' })
    } else {
      modelError.value = ''
      ElMessage.error(data?.message || '问答失败')
      messages.value.push({
        role: 'assistant',
        content: `⚠️ ${data?.message || '问答失败'}`,
      })
    }
  } catch (e) {
    const msg = e?.message || '问答失败'
    ElMessage.error(msg)
    messages.value.push({ role: 'assistant', content: `⚠️ ${msg}` })
  } finally {
    replying.value = false
    await scrollQa()
  }
}

async function scrollQa() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

onMounted(() => {
  fetchModels()
  if (autoRefresh.value) startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.assistant {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  min-height: 480px;
}
.as-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}
.as-title-main {
  font-size: 18px;
  font-weight: 600;
  margin-right: 10px;
}
.as-title-sub {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.as-model-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.as-model-select {
  width: 320px;
}
.as-alert {
  margin-bottom: 8px;
}
.as-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.as-tabs :deep(.el-tabs__header) {
  margin-bottom: 8px;
}
.as-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
}
.as-tabs :deep(.el-tab-pane) {
  height: 100%;
}
.as-body {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-fill-color-light);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}
.as-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.as-empty {
  text-align: center;
  color: var(--el-text-color-secondary);
  margin-top: 40px;
}
.as-empty-icon {
  font-size: 40px;
  margin-bottom: 8px;
}
.as-examples {
  display: inline-block;
  text-align: left;
  color: var(--el-text-color-regular);
  margin: 8px 0;
  line-height: 1.8;
}
.as-empty-tip {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.as-msg {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  max-width: 92%;
}
.as-msg-user {
  flex-direction: row-reverse;
  margin-left: auto;
}
.as-msg-role {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fff;
  background: #c0c4cc;
}
.as-msg-user .as-msg-role {
  background: #409eff;
}
.as-msg-assistant .as-msg-role {
  background: #67c23a;
}
.as-msg-content {
  background: var(--el-bg-color);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 10px 14px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  min-width: 0;
}
.as-msg-user .as-msg-content {
  /* 用户气泡：用主题 primary-light-9（本主题体系下为品牌浅色/暗色透明 tint），随 6 套主题切换 */
  background: var(--el-color-primary-light-9);
}
.as-typing {
  color: var(--el-text-color-secondary);
}
/* 动作草稿卡片 */
.as-action-card {
  flex: 1;
  background: var(--el-bg-color);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px;
}
.as-action-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.as-action-title {
  font-size: 15px;
}
.as-action-done {
  color: #67c23a;
  font-size: 12px;
  margin-right: auto;
}
.as-action-reason {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-bottom: 10px;
}
.as-action-form {
  max-height: 340px;
  overflow-y: auto;
}
.as-field-tip {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  line-height: 1.4;
}
.as-action-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
}
.as-input-bar {
  display: flex;
  gap: 10px;
  padding: 12px;
  background: var(--el-bg-color);
  border-top: 1px solid var(--color-border);
  align-items: flex-end;
}
.as-input-bar .el-textarea {
  flex: 1;
}
.as-input-hint {
  padding: 0 12px 10px;
  background: var(--el-bg-color);
  color: #e6a23c;
  font-size: 12px;
}
</style>