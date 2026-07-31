<template>
  <div class="page-container notification-config">
    <div class="top-bar">
      <el-button
        v-if="activeTab === 'config'"
        type="primary"
        :icon="Check"
        :loading="saving"
        @click="handleSaveConfig"
      >
        保存配置
      </el-button>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs">
      <!-- 基础配置 -->
      <el-tab-pane label="基础配置" name="config">
        <el-card shadow="never" v-loading="configLoading">
          <!-- 开关组 -->
          <el-divider content-position="left">通知开关</el-divider>
          <el-form :model="configForm" label-width="160px" class="config-form">
            <el-form-item label="全局总开关">
              <el-switch v-model="configForm.global_enabled" />
              <span class="field-tip" style="margin-left: 12px">
                关闭后所有通知都不发送（场景开关失效）
              </span>
            </el-form-item>
            <el-form-item label="工作流失败通知">
              <el-switch v-model="configForm.failed_enabled" />
              <span class="field-tip" style="margin-left: 12px">
                工作流异常时通知（推荐开启）
              </span>
            </el-form-item>
            <el-form-item label="待审核通知">
              <el-switch v-model="configForm.review_enabled" />
              <span class="field-tip" style="margin-left: 12px">
                工作流完成后通知管理员审核
              </span>
            </el-form-item>
            <el-form-item label="发布成功通知">
              <el-switch v-model="configForm.published_enabled" />
              <span class="field-tip" style="margin-left: 12px">
                节目发布上线时通知（默认关闭，避免噪音）
              </span>
            </el-form-item>
          </el-form>

          <!-- 钉钉凭证 -->
          <el-divider content-position="left">钉钉群机器人</el-divider>
          <el-form :model="configForm" label-width="160px" class="config-form">
            <el-form-item label="Webhook 地址">
              <el-input
                v-model="configForm.dingtalk_webhook"
                :type="showWebhook ? 'text' : 'password'"
                placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx"
              >
                <template #append>
                  <el-button @click="showWebhook = !showWebhook">
                    {{ showWebhook ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                钉钉群机器人 → 安全设置 → 自定义 → Webhook 地址
              </div>
            </el-form-item>
            <el-form-item label="加签密钥">
              <el-input
                v-model="configForm.dingtalk_secret"
                :type="showSecret ? 'text' : 'password'"
                placeholder="SEC开头（可选，配置后启用加签验证）"
              >
                <template #append>
                  <el-button @click="showSecret = !showSecret">
                    {{ showSecret ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                钉钉群机器人 → 安全设置 → 加签 → 密钥（以 SEC 开头）
              </div>
            </el-form-item>
          </el-form>

          <!-- 企业微信凭证 -->
          <el-divider content-position="left">企业微信群机器人</el-divider>
          <el-form :model="configForm" label-width="160px" class="config-form">
            <el-form-item label="Webhook 地址">
              <el-input
                v-model="configForm.wecom_webhook"
                :type="showWecomWebhook ? 'text' : 'password'"
                placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
              >
                <template #append>
                  <el-button @click="showWecomWebhook = !showWecomWebhook">
                    {{ showWecomWebhook ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                企业微信群机器人 → 添加机器人 → 复制 Webhook 地址
              </div>
            </el-form-item>
          </el-form>

          <!-- 邮件 SMTP -->
          <el-divider content-position="left">邮件通知（SMTP）</el-divider>
          <el-form :model="configForm" label-width="160px" class="config-form">
            <el-form-item label="SMTP 服务器">
              <el-input
                v-model="configForm.email_smtp_host"
                placeholder="smtp.qq.com / smtp.163.com / smtp.gmail.com"
              />
            </el-form-item>
            <el-form-item label="SMTP 端口">
              <el-input-number
                v-model="configForm.email_smtp_port"
                :min="1"
                :max="65535"
                controls-position="right"
                style="width: 200px"
              />
              <span class="field-tip" style="margin-left: 12px">
                465 = SSL 直连；587/25 = STARTTLS
              </span>
            </el-form-item>
            <el-form-item label="发件人账号">
              <el-input
                v-model="configForm.email_smtp_user"
                placeholder="sender@example.com"
              />
            </el-form-item>
            <el-form-item label="发件人密码">
              <el-input
                v-model="configForm.email_smtp_password"
                :type="showEmailPwd ? 'text' : 'password'"
                placeholder="SMTP 授权码（非邮箱登录密码）"
              >
                <template #append>
                  <el-button @click="showEmailPwd = !showEmailPwd">
                    {{ showEmailPwd ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                多数邮箱需用授权码（QQ/163/Gmail 均在账户设置中开启 SMTP 后生成）
              </div>
            </el-form-item>
            <el-form-item label="收件人">
              <el-input
                v-model="configForm.email_to"
                placeholder="ops@example.com（多个用英文逗号分隔）"
              />
            </el-form-item>
          </el-form>

          <!-- 测试发送（独立段，避免与单一渠道混淆） -->
          <el-divider content-position="left">测试发送</el-divider>
          <el-form :model="configForm" label-width="160px" class="config-form">
            <el-form-item>
              <el-button
                type="primary"
                plain
                :loading="testing"
                @click="handleTestSend"
              >
                测试发送到所有已配置渠道
              </el-button>
              <el-tag
                v-if="testResult"
                :type="testResult.success ? 'success' : 'danger'"
                style="margin-left: 12px"
              >
                {{ testResult.message }}
              </el-tag>
            </el-form-item>
          </el-form>

          <!-- Admin Web 地址 -->
          <el-divider content-position="left">访问地址</el-divider>
          <el-form :model="configForm" label-width="160px" class="config-form">
            <el-form-item label="Admin Web 地址">
              <el-input
                v-model="configForm.admin_base_url"
                placeholder="https://your-domain.com 或 http://localhost:5173"
              />
              <div class="field-tip">
                钉钉消息中的跳转链接基础地址。留空则使用后端自动检测值：
                <el-tag size="small" type="info" style="margin-left: 4px">
                  {{ detectedBaseUrl || '检测中...' }}
                </el-tag>
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 消息模板 -->
      <el-tab-pane label="消息模板" name="templates">
        <el-card shadow="never" v-loading="templatesLoading">
          <el-alert
            :title="alertTitle"
            type="info"
            :closable="false"
            style="margin-bottom: 16px"
          />
          <div
            v-for="tpl in templates"
            :key="tpl.id"
            class="template-block"
          >
            <div class="template-header">
              <div class="template-title">
                <span class="template-name">{{ tpl.name }}</span>
                <el-tag size="small" :type="tpl.is_preset ? 'info' : 'success'">
                  {{ tpl.is_preset ? '预设' : '自定义' }}
                </el-tag>
                <el-tag size="small" type="warning" style="margin-left: 4px">
                  {{ tpl.event_type }}
                </el-tag>
              </div>
              <div class="template-actions">
                <el-switch
                  v-model="tpl.enabled"
                  :active-value="1"
                  :inactive-value="0"
                  active-text="启用"
                  inactive-text="禁用"
                  @change="handleTemplateChange(tpl)"
                />
                <el-button
                  size="small"
                  :icon="View"
                  @click="handlePreview(tpl)"
                  style="margin-left: 12px"
                >
                  预览
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :icon="Check"
                  :loading="tpl._saving"
                  @click="handleSaveTemplate(tpl)"
                  style="margin-left: 8px"
                >
                  保存
                </el-button>
              </div>
            </div>

            <el-form label-width="100px" class="template-form">
              <el-form-item label="模板名称">
                <el-input v-model="tpl.name" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="标题模板">
                <el-input
                  v-model="tpl.title_template"
                  :placeholder="titlePlaceholder"
                />
              </el-form-item>
              <el-form-item label="正文模板">
                <el-input
                  v-model="tpl.body_template"
                  type="textarea"
                  :rows="6"
                  placeholder="支持 Markdown 语法，变量用双花括号引用"
                />
              </el-form-item>
              <el-form-item label="可用变量">
                <div class="vars-list">
                  <el-tag
                    v-for="v in tpl.variables"
                    :key="v"
                    size="small"
                    type="info"
                    effect="plain"
                    style="margin: 2px"
                  >
                    {{ formatVarName(v) }}
                  </el-tag>
                  <span v-if="!tpl.variables?.length" class="field-tip">
                    当前模板未引用任何变量
                  </span>
                </div>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 发送日志 -->
      <el-tab-pane label="发送日志" name="logs">
        <el-card shadow="never">
          <!-- 过滤栏 -->
          <div class="filter-bar">
            <el-select
              v-model="logFilter.event_type"
              placeholder="事件类型"
              clearable
              style="width: 200px"
              @change="handleLogFilterChange"
            >
              <el-option label="待审核" value="workflow.pending_review" />
              <el-option label="工作流失败" value="workflow.failed" />
              <el-option label="发布成功" value="workflow.published" />
              <el-option label="测试通知" value="test" />
            </el-select>
            <el-select
              v-model="logFilter.status"
              placeholder="发送状态"
              clearable
              style="width: 160px; margin-left: 12px"
              @change="handleLogFilterChange"
            >
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
              <el-option label="已抑制" value="suppressed" />
            </el-select>
            <el-button
              :icon="Refresh"
              @click="loadLogs"
              style="margin-left: 12px"
            >
              刷新
            </el-button>
          </div>

          <el-table
            :data="logs"
            v-loading="logsLoading"
            stripe
            style="margin-top: 16px"
          >
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="event_type" label="事件" width="180">
              <template #default="{ row }">
                <el-tag size="small" :type="getEventTagType(row.event_type)">
                  {{ row.event_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="workflow_id" label="工作流" width="180" show-overflow-tooltip />
            <el-table-column prop="error" label="错误信息" min-width="200" show-overflow-tooltip />
            <el-table-column prop="created_at" label="发送时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="primary"
                  link
                  :loading="row._resending"
                  @click="handleResend(row)"
                >
                  重发
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div class="pagination-wrap">
            <el-pagination
              v-model:current-page="logFilter.page"
              v-model:page-size="logFilter.page_size"
              :total="logTotal"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @size-change="loadLogs"
              @current-change="loadLogs"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 预览对话框 -->
    <el-dialog
      v-model="previewVisible"
      title="模板预览"
      width="640px"
      :destroy-on-close="true"
    >
      <el-form label-width="120px">
        <el-form-item
          v-for="varName in previewVariables"
          :key="varName"
          :label="varName"
        >
          <el-input
            v-model="previewInput[varName]"
            :placeholder="`输入测试值（${varName}）`"
          />
        </el-form-item>
        <el-form-item v-if="!previewVariables.length">
          <span class="field-tip">当前模板未引用任何变量</span>
        </el-form-item>
      </el-form>

      <div v-if="previewResult" class="preview-result">
        <el-divider content-position="left">渲染结果</el-divider>
        <div class="preview-title">{{ previewResult.title }}</div>
        <div class="preview-body">{{ previewResult.body }}</div>
      </div>

      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :loading="previewing"
          @click="handleDoPreview"
        >
          渲染预览
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Check, View, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from '../../utils/message'
import {
  getNotificationConfig,
  saveNotificationConfig,
  sendTestNotification,
  listNotificationTemplates,
  updateNotificationTemplate,
  previewNotificationTemplate,
  listNotificationLogs,
  resendNotificationLog,
} from '../../api/notification'

const activeTab = ref('config')

// 文案常量（避免在模板属性中直接写双花括号引发 Vue 解析冲突）
const alertTitle = '模板变量使用双花括号语法（如 channel_name 写作 {{ channel_name }}），缺失变量会降级为空字符串'
const titlePlaceholder = '如：📰 {{ channel_name }} {{ episode_date }} 待审核'

// 格式化变量名展示（避免在模板中拼接双花括号引发解析冲突）
function formatVarName(name) {
  return '{{ ' + name + ' }}'
}

// ===== 基础配置 =====
const configLoading = ref(false)
const saving = ref(false)
const testing = ref(false)
const showWebhook = ref(false)
const showSecret = ref(false)
const showWecomWebhook = ref(false)
const showEmailPwd = ref(false)
const detectedBaseUrl = ref('')
const testResult = ref(null)

const configForm = reactive({
  global_enabled: true,
  failed_enabled: true,
  review_enabled: true,
  published_enabled: false,
  dingtalk_webhook: '',
  dingtalk_secret: '',
  wecom_webhook: '',
  email_smtp_host: '',
  email_smtp_port: 587,
  email_smtp_user: '',
  email_smtp_password: '',
  email_to: '',
  admin_base_url: '',
})

async function loadConfig() {
  configLoading.value = true
  try {
    const data = await getNotificationConfig()
    // 后端返回脱敏值 "****" 时直接显示，保存时后端会忽略该值
    Object.assign(configForm, {
      global_enabled: data.global_enabled ?? true,
      failed_enabled: data.failed_enabled ?? true,
      review_enabled: data.review_enabled ?? true,
      published_enabled: data.published_enabled ?? false,
      dingtalk_webhook: data.dingtalk_webhook || '',
      dingtalk_secret: data.dingtalk_secret || '',
      wecom_webhook: data.wecom_webhook || '',
      email_smtp_host: data.email_smtp_host || '',
      email_smtp_port: data.email_smtp_port ?? 587,
      email_smtp_user: data.email_smtp_user || '',
      email_smtp_password: data.email_smtp_password || '',
      email_to: data.email_to || '',
      admin_base_url: data.admin_base_url || '',
    })
    detectedBaseUrl.value = data.auto_detected_base_url || ''
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    configLoading.value = false
  }
}

async function handleSaveConfig() {
  saving.value = true
  try {
    await saveNotificationConfig({ ...configForm })
    ElMessage.success('配置已保存')
    // 重新加载以刷新脱敏显示与 detected_base_url
    await loadConfig()
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    saving.value = false
  }
}

async function handleTestSend() {
  testing.value = true
  testResult.value = null
  try {
    // 先保存配置，确保 webhook/secret 已持久化到 ai_config 表
    // 后端 send_test 会从 ai_config 表读取最新配置临时创建 notifier
    await saveNotificationConfig({ ...configForm })
    // 再发送测试通知
    const result = await sendTestNotification()
    testResult.value = result
    if (result.success) {
      ElMessage.success('测试通知已发送，请检查已配置渠道')
    } else {
      ElMessage.warning('测试通知发送失败，请检查配置')
    }
  } catch (e) {
    testResult.value = { success: false, message: e.message || '请求失败' }
  } finally {
    testing.value = false
  }
}

// ===== 消息模板 =====
const templatesLoading = ref(false)
const templates = ref([])

async function loadTemplates() {
  templatesLoading.value = true
  try {
    const data = await listNotificationTemplates()
    // _saving 为前端临时状态字段，不在后端存储
    templates.value = (data || []).map((t) => ({ ...t, _saving: false }))
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    templatesLoading.value = false
  }
}

function handleTemplateChange(tpl) {
  // 启用/禁用切换时自动保存，避免用户忘记保存导致开关不生效
  handleSaveTemplate(tpl)
}

async function handleSaveTemplate(tpl) {
  tpl._saving = true
  try {
    await updateNotificationTemplate(tpl.id, {
      name: tpl.name,
      title_template: tpl.title_template,
      body_template: tpl.body_template,
      enabled: tpl.enabled,
    })
    ElMessage.success(`模板「${tpl.name}」已保存`)
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    tpl._saving = false
  }
}

// ===== 模板预览 =====
const previewVisible = ref(false)
const previewing = ref(false)
const previewVariables = ref([])
const previewInput = reactive({})
const previewResult = ref(null)
const currentPreviewTpl = ref(null)

function handlePreview(tpl) {
  currentPreviewTpl.value = tpl
  previewVariables.value = [...(tpl.variables || [])]
  // 初始化变量输入为空字符串
  previewVariables.value.forEach((v) => {
    previewInput[v] = ''
  })
  previewResult.value = null
  previewVisible.value = true
}

async function handleDoPreview() {
  if (!currentPreviewTpl.value) return
  previewing.value = true
  try {
    const result = await previewNotificationTemplate(
      currentPreviewTpl.value.id,
      { ...previewInput },
    )
    previewResult.value = result
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    previewing.value = false
  }
}

// ===== 发送日志 =====
const logsLoading = ref(false)
const logs = ref([])
const logTotal = ref(0)
const logFilter = reactive({
  page: 1,
  page_size: 20,
  event_type: '',
  status: '',
})

async function loadLogs() {
  logsLoading.value = true
  try {
    const params = {
      page: logFilter.page,
      page_size: logFilter.page_size,
    }
    if (logFilter.event_type) params.event_type = logFilter.event_type
    if (logFilter.status) params.status = logFilter.status
    const data = await listNotificationLogs(params)
    logs.value = (data.items || []).map((l) => ({ ...l, _resending: false }))
    logTotal.value = data.total || 0
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    logsLoading.value = false
  }
}

function handleLogFilterChange() {
  logFilter.page = 1
  loadLogs()
}

async function handleResend(row) {
  row._resending = true
  try {
    const result = await resendNotificationLog(row.id)
    // 重发后后端会创建新日志记录（非更新原记录）。
    // 若用户当前按 status 过滤（如查看失败记录），新记录的状态与过滤不一致时不会出现在列表中，
    // 会导致用户看不到重发结果。此处主动清空 status 过滤并回到首页，确保新记录可见。
    if (logFilter.status && logFilter.status !== result.status) {
      logFilter.status = ''
      logFilter.page = 1
    }
    if (result.status === 'success') {
      ElMessage.success('重发成功，已为你展示最新记录')
    } else {
      ElMessage.warning(`重发失败: ${result.message || ''}`)
    }
    await loadLogs()
  } catch (e) {
    // 拦截器已统一提示
  } finally {
    row._resending = false
  }
}

// ===== 辅助函数 =====
function getEventTagType(eventType) {
  if (eventType === 'workflow.pending_review') return 'warning'
  if (eventType === 'workflow.failed') return 'danger'
  if (eventType === 'workflow.published') return 'success'
  return 'info'
}

function getStatusTagType(status) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'suppressed') return 'info'
  return ''
}

function getStatusLabel(status) {
  const map = {
    success: '成功',
    failed: '失败',
    suppressed: '已抑制',
  }
  return map[status] || status
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

onMounted(() => {
  loadConfig()
  loadTemplates()
  loadLogs()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.notification-config {
  .top-bar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .config-form {
    max-width: 720px;

    .field-tip {
      font-size: 12px;
      color: $color-text-secondary;
      margin-top: 4px;
    }
  }

  .template-block {
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 16px;
    margin-bottom: 16px;
    background: var(--el-bg-color);

    .template-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px dashed $color-border;
    }

    .template-title {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .template-name {
      font-size: 16px;
      font-weight: 600;
      color: $color-text-primary;
    }

    .template-actions {
      display: flex;
      align-items: center;
    }

    .template-form {
      .vars-list {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
      }
    }
  }

  .filter-bar {
    display: flex;
    align-items: center;
  }

  .pagination-wrap {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .preview-result {
    margin-top: 16px;

    .preview-title {
      font-size: 16px;
      font-weight: 600;
      color: $color-text-primary;
      margin-bottom: 8px;
    }

    .preview-body {
      white-space: pre-wrap;
      background: var(--el-fill-color-light);
      padding: 12px;
      border-radius: $radius-sm;
      font-family: monospace;
      font-size: 13px;
      line-height: 1.6;
    }
  }
}
</style>
