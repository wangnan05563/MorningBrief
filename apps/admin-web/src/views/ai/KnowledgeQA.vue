<template>
  <div data-guide="assistant-page" class="page-container assistant">
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
              <div class="as-msg-content" :class="{ 'as-msg-content-failed': msg.failed }">
                {{ msg.content }}
                <!-- 超时才给「重试」：ACC-UX-701 要求超时提示可重试；
                     其他失败（如 API Key 未配置）重试同一个错没有意义，只留文案引导去改配置 -->
                <div v-if="msg.retryable" class="as-msg-actions">
                  <IconButton
                    type="warning"
                    plain
                    size="small"
                    :icon="Refresh"
                    inline-text="重试"
                    label="重试这一问"
                    desc="用同一份上下文重新提问（可先切换更快的模型再重试）"
                    :disabled="replying || !currentModel"
                    @click="retryMessage(idx)"
                  />
                </div>
              </div>
            </div>

            <div v-if="replying" class="as-msg as-msg-assistant">
              <div class="as-msg-role">AI</div>
              <div class="as-msg-content as-typing">正在思考…长回答可能要等 1-2 分钟，等不及可以点下方「停止生成」</div>
            </div>
          </div>

          <div class="as-input-bar">
            <el-input data-guide="assistant-input"
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
            <!-- FR-UX-701「停止生成」：只在等待回答时出现。
                 点它中止的是浏览器这条请求（上游模型任务不会因此停，见 api/aiChat.js），
                 但界面必须立刻回到可输入状态——原来没有这个出口，长回答卡住时只能刷新整页。 -->
            <IconButton
              v-if="replying"
              type="danger"
              plain
              :icon="Delete"
              inline-text="停止生成"
              label="停止生成"
              desc="中止本次问答请求，界面立即可继续输入"
              @click="stopGenerating"
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
import { ElMessage, notifyErrorOnce } from '../../utils/message'
import { Refresh, Promotion, ChatDotRound, MagicStick, Check, Delete, ArrowRight } from '@element-plus/icons-vue'
import api from '../../api'
import { callAiChat } from '../../api/aiChat'
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
    // 拦截器已为这条失败弹过后不再重复弹（FR-UX-303）
    notifyErrorOnce(e, '生成草稿失败')
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
    notifyErrorOnce(e, '创建失败')
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
// 本轮问答的中止句柄（FR-UX-701「停止生成」）。
// 用普通变量而不是 ref：AbortController 塞进响应式代理后，axios 取 signal 时拿到的是
// Proxy，浏览器会抛 "signal is not an AbortSignal" 这类看不懂的错。
let chatAbort = null

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

  // 组装对话历史（OpenAI 格式），追加当前问题。
  // 过滤掉失败气泡（msg.failed）：它们不该作为上下文喂回模型，
  // 否则一次超时会把「⚠️ 生成超时…」这种系统话术当成 AI 的回答带进后续每一轮对话。
  const history = messages.value
    .filter((m) => !m.failed)
    .map((m) => ({ role: m.role, content: m.content }))
  history.push({ role: 'user', content: text })

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  await runChat(history)
}

/**
 * 真正发一轮问答（FR-UX-701 / T02515）。
 * 三种收场各自有不同后续动作，所以单独成函数给「重试」复用：
 * - ok        → 追加回复
 * - aborted   → 用户点了「停止生成」：把问题放回输入框（他多半想改一改再问），不留 loading
 * - timeout   → 超时：留一条带「重试」的气泡（ACC 要求「超时提示可重试」）
 * - error     → 其他失败：同样留气泡 + toast，但不给重试按钮（重试同一个模型错误没意义，
 *               例如 API Key 未配置——那种情况要的是去改配置，不是再点一次）
 */
async function runChat(history) {
  replying.value = true
  chatAbort = new AbortController()
  await scrollQa()

  const question = history[history.length - 1]?.content || ''
  let res
  try {
    res = await callAiChat({ client: api, model: currentModel.value, messages: history, signal: chatAbort.signal })
  } finally {
    // 放在 finally：任何异常路径都不能把 replying 留在 true——
    // 这个页面是菜单 tab 常驻组件（tabRefs.qa），loading 卡住后切走再切回来还是卡着，
    // 用户只能刷新整页（F19 原本「一直转圈」的观感就是这么来的）
    replying.value = false
    chatAbort = null
  }

  if (res.ok) {
    messages.value.push({ role: 'assistant', content: res.data.reply || '(空回复)' })
  } else if (res.kind === 'aborted') {
    messages.value.push({ role: 'assistant', content: '⏹ 已停止生成', stopped: true })
    if (!inputText.value) inputText.value = question
  } else if (res.kind === 'timeout') {
    messages.value.push({
      role: 'assistant',
      content: `⚠️ ${res.message || '生成超时'}`,
      failed: true,
      retryable: true,
      retryHistory: history,
    })
  } else {
    messages.value.push({
      role: 'assistant',
      content: `⚠️ ${res.message || '问答失败'}`,
      failed: true,
    })
    notifyErrorOnce(new Error(res.message || '问答失败'))
  }
  await scrollQa()
}

/** 「停止生成」：中止浏览器侧请求。上游模型任务无法从客户端取消，详见 api/aiChat.js 注释 */
function stopGenerating() {
  if (!replying.value || !chatAbort) return
  chatAbort.abort()
}

/** 点超时气泡里的「重试」：摘掉这条失败气泡，用同一份历史重发（模型按当前选择，方便换快的） */
async function retryMessage(idx) {
  if (replying.value) return
  const msg = messages.value[idx]
  if (!msg?.retryable || !Array.isArray(msg.retryHistory)) return
  messages.value.splice(idx, 1)
  await runChat(msg.retryHistory)
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
  // 离开页面时中止在途问答：否则请求继续占着连接，而组件已销毁，
  // 回来时（tab 常驻会被重建）既看不到结果也停不掉
  if (chatAbort) chatAbort.abort()
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
/* 失败/超时气泡（FR-UX-701）：用 danger 描边与正常回答区分，重试入口跟在气泡内右下 */
.as-msg-content-failed {
  border-color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}
.as-msg-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
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