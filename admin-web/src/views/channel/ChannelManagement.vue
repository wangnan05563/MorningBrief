<template>
  <div class="page-container channel-management">
    <!-- 工具栏：新增按钮（仅 admin 可见），标题由顶部导航栏提供 -->
    <div class="top-bar">
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
        <el-table-column label="段间静音" width="120">
          <template #default="{ row }">
            <span v-if="row.segment_gap_sec !== null && row.segment_gap_sec !== undefined">
              {{ row.segment_gap_sec }}s
            </span>
            <span v-else class="text-muted">继承全局</span>
          </template>
        </el-table-column>
        <el-table-column label="段间BGM" width="120">
          <template #default="{ row }">
            <span v-if="row.bgm_gap_mode === 'bridge'">BGM桥接</span>
            <span v-else-if="row.bgm_gap_mode === 'silence'">真实静音</span>
            <span v-else class="text-muted">继承全局</span>
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
        <el-table-column label="展示排序" width="100" align="center">
          <template #default="{ row }">{{ row.display_order ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
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
        <el-form-item label="展示排序">
          <el-input-number
            v-model="form.display_order"
            :min="0"
            :step="1"
            controls-position="right"
            style="width: 160px"
          />
          <span class="form-tip">数值越小越靠前（小程序/首页 tab 顺序），默认 0</span>
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

        <!-- BGM 设置区：选择预制/上传自定义/AI推荐/试听 -->
        <el-divider content-position="left">背景音乐（BGM）</el-divider>
        <el-form-item label="BGM 文件">
          <div class="bgm-controls">
            <!-- 下拉选择：预制 + 自定义 BGM 列表 -->
            <el-select
              v-model="form.bgm_path"
              placeholder="选择 BGM（留空使用全局配置）"
              clearable
              filterable
              style="width: 320px"
              @change="handleBgmChange"
            >
              <el-option-group label="预制">
                <el-option
                  v-for="b in presetBgmList"
                  :key="b.path"
                  :label="`${b.name} (${b.size_kb}KB)`"
                  :value="b.path"
                />
              </el-option-group>
              <el-option-group label="自定义">
                <el-option
                  v-for="b in customBgmList"
                  :key="b.path"
                  :label="`${b.name} (${b.size_kb}KB)`"
                  :value="b.path"
                />
              </el-option-group>
            </el-select>
            <!-- 试听按钮：选了 BGM 后才显示，用原生 audio 避免组件库依赖 -->
            <el-button
              v-if="form.bgm_path"
              :icon="VideoPlay"
              @click="handlePreviewBgm"
            >试听</el-button>
            <!-- AI 推荐：仅编辑模式可用，调用 LLM 根据频道定位推荐 -->
            <el-button
              v-if="editing"
              type="primary"
              link
              :loading="recommendingBgm"
              @click="handleRecommendBgm"
            >AI 推荐</el-button>
            <!-- 上传自定义 BGM -->
            <el-upload
              :show-file-list="false"
              :before-upload="handleBgmBeforeUpload"
              :http-request="handleBgmUpload"
              accept=".mp3,.wav,.m4a,.aac,.ogg"
            >
              <el-button :icon="Upload" :loading="uploadingBgm">
                {{ uploadingBgm ? `上传中 ${uploadProgress}%` : '上传 BGM' }}
              </el-button>
            </el-upload>
          </div>
          <!-- 试听播放器：选中 BGM 时显示，原生 controls 避免组件耦合 -->
          <audio
            v-if="form.bgm_path && showAudioPlayer"
            ref="audioPlayerRef"
            :src="bgmPreviewUrl"
            controls
            style="margin-top: 8px; width: 100%"
          />
          <!-- AI 推荐理由：展示 LLM 的选择依据，增强可解释性 -->
          <div v-if="bgmRecommendReason" class="recommend-reason">
            AI 推荐理由：{{ bgmRecommendReason }}
          </div>
        </el-form-item>
        <el-form-item label="BGM 音量">
          <el-slider
            v-model="form.bgm_volume"
            :min="0"
            :max="1"
            :step="0.05"
            style="width: 280px"
          />
          <span class="form-tip">留空/0.15 为默认，TTS 播报期间垫底音量</span>
        </el-form-item>

        <!-- 音频节奏区：段间静音 + 思考问题开关 -->
        <el-divider content-position="left">音频节奏</el-divider>
        <el-form-item label="段间静音">
          <div class="gap-controls">
            <el-checkbox
              v-model="form.inherit_segment_gap"
              style="margin-right: 12px"
            >
              继承全局（AI 服务页设置）
            </el-checkbox>
            <el-slider
              v-model="form.segment_gap_sec"
              :min="0"
              :max="3"
              :step="0.1"
              :disabled="form.inherit_segment_gap"
              style="width: 240px"
            />
          </div>
          <span class="form-tip">TTS 段落之间的停顿时长（秒），BGM 在此时段自然浮现；勾选继承后回退到 AI 服务页的全局段间静音</span>
        </el-form-item>
        <el-form-item label="段间 BGM">
          <div class="gap-controls">
            <el-checkbox
              v-model="form.inherit_bgm_gap"
              style="margin-right: 12px"
            >
              继承全局
            </el-checkbox>
            <el-select
              v-model="form.bgm_gap_mode"
              :disabled="form.inherit_bgm_gap"
              style="width: 200px"
            >
              <el-option label="真实静音（推荐）" value="silence" />
              <el-option label="BGM 桥接（旧版）" value="bridge" />
            </el-select>
          </div>
          <span class="form-tip">段间静音处 BGM 的处理方式：真实静音=停顿可感知；BGM 桥接=旧版 BGM 铺满（无停顿感）</span>
        </el-form-item>
        <el-form-item label="结尾思考">
          <el-switch
            v-model="form.enable_thinking_question"
            :active-value="1"
            :inactive-value="0"
          />
          <span class="form-tip">开启后每段新闻末尾自动追加引发思考的问题</span>
        </el-form-item>

        <!-- 数据源配置区：RSS 源白名单 + 关键词过滤 -->
        <el-divider content-position="left">
          <span>数据源配置</span>
          <!-- AI 推荐：仅编辑模式可用，与 BGM 推荐按钮风格保持一致 -->
          <el-button
            v-if="editing"
            type="primary"
            link
            :loading="recommendingSources"
            @click="handleRecommendSources"
            style="margin-left: 12px"
          >AI 推荐</el-button>
        </el-divider>
        <el-form-item label="RSS 源">
          <el-select
            v-model="form.rss_sources"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="留空使用全部源（全局模式）"
            style="width: 100%"
          >
            <el-option
              v-for="src in rssSourcesList"
              :key="src.name"
              :label="`${src.name}（${src.category_hint}）`"
              :value="src.name"
            />
          </el-select>
          <span class="form-tip">选择频道专属 RSS 源，仅采集选中源的数据；留空使用全部源</span>
        </el-form-item>
        <el-form-item label="关键词过滤">
          <el-input
            v-model="form.keywords"
            type="textarea"
            :rows="2"
            placeholder="逗号分隔，如：游戏,主机,PS5,Xbox,任天堂。留空表示不过滤"
          />
          <span class="form-tip">标题包含任一关键词的素材才会入库，在正文提取前过滤以节省网络请求</span>
          <!-- AI 推荐理由：展示 LLM 的选择依据，增强可解释性，复用通用 recommend-reason 类 -->
          <div v-if="sourcesRecommendReason" class="recommend-reason">
            AI 推荐理由：{{ sourcesRecommendReason }}
          </div>
        </el-form-item>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from '../../utils/message'
import { Plus, VideoPlay, Upload } from '@element-plus/icons-vue'
import {
  listChannels, createChannel, updateChannel, deleteChannel, generateChannelPrompts,
  listBgmFiles, uploadBgmFile, recommendChannelBgm, listRssSources, recommendChannelSources,
} from '../../api/channels'
import { formatTime } from '../../utils/format'

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

// ===== BGM 相关状态 =====
// BGM 文件列表（从后端加载），分预制/自定义两组展示
const bgmList = ref([])
const presetBgmList = computed(() => bgmList.value.filter((b) => b.category === '预制'))
const customBgmList = computed(() => bgmList.value.filter((b) => b.category === '自定义'))
// 试听播放器显隐 + URL
const showAudioPlayer = ref(false)
const audioPlayerRef = ref(null)
// AI 推荐 BGM loading
const recommendingBgm = ref(false)
// AI 推荐理由（展示 LLM 选择依据）
const bgmRecommendReason = ref('')
// 上传 BGM 状态
const uploadingBgm = ref(false)
const uploadProgress = ref(0)

// RSS 源列表（从 rss.yaml 加载，供频道配置选择）
const rssSourcesList = ref([])
// AI 推荐 RSS 源 + 关键词 loading
const recommendingSources = ref(false)
// AI 推荐理由（展示 LLM 选择依据）
const sourcesRecommendReason = ref('')

const form = reactive({
  id: null,
  name: '',
  description: '',
  is_active: 1,
  // 展示排序权重：数值越小越靠前（对应小程序/首页 tab 顺序），默认 0
  display_order: 0,
  schedule_time: '',
  intro_prompt: '',
  outro_prompt: '',
  constraint_prompt: '',
  rewrite_template: '',
  auto_generate_prompts: false,
  // BGM 字段：bgm_path 为相对 data/bgm/ 的路径，空表示用全局配置
  bgm_path: null,
  // bgm_volume 为 null 时后端使用全局 BGM_VOLUME
  bgm_volume: 0.15,
  // 段间静音时长（秒），null 时后端使用全局 SEGMENT_GAP_SEC
  segment_gap_sec: 0.5,
  // 是否继承全局段间静音（AI 服务页配置）：勾选时提交 null，让该频道回退到全局值，
  // 否则频道始终使用自身 segment_gap_sec，会完全遮蔽 AI 服务页的全局设置
  inherit_segment_gap: false,
  // 段间 BGM 模式：'silence'=真实静音（默认），'bridge'=BGM 桥接（旧版）
  bgm_gap_mode: 'silence',
  // 是否继承全局段间 BGM 模式（settings.BGM_GAP_MODE）：勾选时提交 null，回退全局
  inherit_bgm_gap: true,
  // 是否在每段新闻末尾追加思考问题（1=开启，0=关闭）
  enable_thinking_question: 1,
  // 频道专属 RSS 源（数组，空数组表示使用全部源）
  rss_sources: [],
  // 频道关键词过滤（逗号分隔字符串，空表示不过滤）
  keywords: '',
})

const rules = {
  name: [{ required: true, message: '请输入频道名称', trigger: 'blur' }],
}

// BGM 试听 URL：后端 /bgm/ 静态目录直接访问，无需鉴权
const bgmPreviewUrl = computed(() => {
  if (!form.bgm_path) return ''
  return `/bgm/${form.bgm_path}`
})

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

async function loadBgmList() {
  try {
    const data = await listBgmFiles()
    bgmList.value = data.list || []
  } catch {
    bgmList.value = []
  }
}

async function loadRssSources() {
  try {
    const data = await listRssSources()
    rssSourcesList.value = data.sources || []
  } catch {
    rssSourcesList.value = []
  }
}

function resetForm() {
  form.id = null
  form.name = ''
  form.description = ''
  form.is_active = 1
  form.display_order = 0
  form.schedule_time = ''
  form.intro_prompt = ''
  form.outro_prompt = ''
  form.constraint_prompt = ''
  form.rewrite_template = ''
  form.auto_generate_prompts = false
  form.bgm_path = null
  form.bgm_volume = 0.15
  form.segment_gap_sec = 0.5
  form.inherit_segment_gap = false
  form.bgm_gap_mode = 'silence'
  form.inherit_bgm_gap = true
  form.enable_thinking_question = 1
  form.rss_sources = []
  form.keywords = ''
  promptCollapse.value = ['intro']
  showAudioPlayer.value = false
  bgmRecommendReason.value = ''
  sourcesRecommendReason.value = ''
}

function openCreate() {
  editing.value = false
  resetForm()
  loadBgmList()
  loadRssSources()
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = true
  form.id = row.id
  form.name = row.name
  form.description = row.description || ''
  form.is_active = row.is_active ? 1 : 0
  // 展示排序权重：后端未返回时回退 0，保持与默认值一致
  form.display_order = row.display_order ?? 0
  form.schedule_time = row.schedule_time || ''
  form.intro_prompt = row.intro_prompt || ''
  form.outro_prompt = row.outro_prompt || ''
  form.constraint_prompt = row.constraint_prompt || ''
  form.rewrite_template = row.rewrite_template || ''
  form.auto_generate_prompts = false
  form.bgm_path = row.bgm_path || null
  form.bgm_volume = row.bgm_volume !== null && row.bgm_volume !== undefined ? row.bgm_volume : 0.15
  // 频道未显式配置段间静音（NULL）即视为继承全局，勾选"继承全局"
  form.inherit_segment_gap = (row.segment_gap_sec === null || row.segment_gap_sec === undefined)
  form.segment_gap_sec = row.segment_gap_sec !== null && row.segment_gap_sec !== undefined ? row.segment_gap_sec : 0.5
  // 频道未显式配置段间 BGM 模式（NULL）即视为继承全局
  form.inherit_bgm_gap = (row.bgm_gap_mode === null || row.bgm_gap_mode === undefined)
  form.bgm_gap_mode = row.bgm_gap_mode || 'silence'
  form.enable_thinking_question = row.enable_thinking_question !== null && row.enable_thinking_question !== undefined ? row.enable_thinking_question : 1
  // RSS 源：后端存储为 JSON 数组字符串，前端解析为数组用于多选绑定
  try {
    form.rss_sources = row.rss_sources ? JSON.parse(row.rss_sources) : []
  } catch {
    form.rss_sources = []
  }
  form.keywords = row.keywords || ''
  promptCollapse.value = ['intro']
  showAudioPlayer.value = false
  bgmRecommendReason.value = ''
  sourcesRecommendReason.value = ''
  loadBgmList()
  loadRssSources()
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    // rss_sources 数组序列化为 JSON 字符串存储，空数组序列化为 "[]"
    const rssSourcesJson = JSON.stringify(form.rss_sources || [])
    if (editing.value) {
      // 编辑：提交所有字段（空字符串表示清空，后端会判断）
      await updateChannel(form.id, {
        name: form.name,
        description: form.description,
        is_active: form.is_active,
        display_order: form.display_order,
        schedule_time: form.schedule_time || '',
        intro_prompt: form.intro_prompt,
        outro_prompt: form.outro_prompt,
        constraint_prompt: form.constraint_prompt,
        rewrite_template: form.rewrite_template,
        bgm_path: form.bgm_path || '',
        bgm_volume: form.bgm_volume,
        // 勾选继承全局时提交 null，让频道回退到 AI 服务页的全局段间静音；
        // 否则使用本页滑块值，覆盖全局配置
        segment_gap_sec: form.inherit_segment_gap ? null : form.segment_gap_sec,
        // 段间 BGM 模式：继承全局则提交 null，否则提交具体模式
        bgm_gap_mode: form.inherit_bgm_gap ? null : form.bgm_gap_mode,
        enable_thinking_question: form.enable_thinking_question,
        rss_sources: rssSourcesJson,
        keywords: form.keywords || '',
      })
      ElMessage.success('已更新')
    } else {
      // 新增：仅提交基本信息 + 定时 + AI生成标志 + BGM + 数据源配置，提示词由 AI 生成或留空
      await createChannel({
        name: form.name,
        description: form.description,
        display_order: form.display_order,
        schedule_time: form.schedule_time || null,
        auto_generate_prompts: form.auto_generate_prompts,
        bgm_path: form.bgm_path || null,
        bgm_volume: form.bgm_volume,
        // 新增频道同样支持继承全局段间静音（提交 null）
        segment_gap_sec: form.inherit_segment_gap ? null : form.segment_gap_sec,
        // 段间 BGM 模式：继承全局则提交 null，否则提交具体模式
        bgm_gap_mode: form.inherit_bgm_gap ? null : form.bgm_gap_mode,
        enable_thinking_question: form.enable_thinking_question,
        rss_sources: rssSourcesJson,
        keywords: form.keywords || '',
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

// ===== BGM 操作 =====

function handleBgmChange() {
  // 切换 BGM 时重置试听播放器和推荐理由
  showAudioPlayer.value = false
  bgmRecommendReason.value = ''
}

function handlePreviewBgm() {
  // 切换显隐实现"点击试听"交互：已显示则隐藏，未显示则展示并自动播放
  if (showAudioPlayer.value) {
    showAudioPlayer.value = false
    return
  }
  showAudioPlayer.value = true
  // DOM 更新后自动播放，避免用户再点一次
  setTimeout(() => {
    if (audioPlayerRef.value) {
      audioPlayerRef.value.play().catch(() => {
        // 浏览器自动播放策略可能阻止，忽略错误，用户可手动点击播放
      })
    }
  }, 100)
}

function handleBgmBeforeUpload(file) {
  // 客户端预校验：类型 + 大小，避免无效上传浪费带宽
  const allowedExts = ['.mp3', '.wav', '.m4a', '.aac', '.ogg']
  const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
  if (!allowedExts.includes(ext)) {
    ElMessage.error(`不支持的格式：${ext}，允许：${allowedExts.join(', ')}`)
    return false
  }
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.error('文件过大，上限 20MB')
    return false
  }
  return true
}

async function handleBgmUpload({ file }) {
  uploadingBgm.value = true
  uploadProgress.value = 0
  try {
    const data = await uploadBgmFile(file, (p) => {
      uploadProgress.value = p
    })
    // 上传成功后自动选中，并刷新 BGM 列表
    form.bgm_path = data.path
    ElMessage.success(`BGM「${data.name}」上传成功`)
    await loadBgmList()
  } catch (e) {
    console.warn('BGM 上传失败:', e)
  } finally {
    uploadingBgm.value = false
    uploadProgress.value = 0
  }
}

async function handleRecommendBgm() {
  if (!form.id) return
  recommendingBgm.value = true
  try {
    const data = await recommendChannelBgm(form.id)
    if (data.path) {
      form.bgm_path = data.path
      bgmRecommendReason.value = data.reason || ''
      // 推荐成功后立即保存到 DB，避免用户忘记点"确认"导致 BGM 配置丢失
      // 后端 ChannelUpdateRequest 字段均为 Optional，支持部分更新
      await updateChannel(form.id, {
        bgm_path: data.path,
        bgm_volume: form.bgm_volume,
      })
      ElMessage.success('AI 已推荐 BGM 并已保存，可试听效果')
    } else {
      ElMessage.warning('AI 未能推荐合适的 BGM')
    }
  } catch (e) {
    console.warn('BGM 推荐失败:', e)
  } finally {
    recommendingBgm.value = false
  }
}

// ===== RSS 源 + 关键词推荐 =====

async function handleRecommendSources() {
  if (!form.id) return
  recommendingSources.value = true
  try {
    const data = await recommendChannelSources(form.id)
    const recommendedSources = Array.isArray(data.rss_sources) ? data.rss_sources : []
    const recommendedKeywords = data.keywords || ''
    // 推荐结果可能为空（LLM 全部幻觉时），此时仅展示理由但不清空用户已有配置
    // 避免误覆盖用户手动配置，与 BGM 推荐的"有结果才覆盖"策略保持一致
    if (recommendedSources.length === 0 && !recommendedKeywords) {
      sourcesRecommendReason.value = data.reason || ''
      ElMessage.warning('AI 未能推荐合适的 RSS 源与关键词')
      return
    }
    // rss_sources 为空数组表示"走全局模式"（使用全部源），与 keywords 配套使用：
    // 即便 LLM 仅推荐了关键词未推荐源，也按"全部源 + 关键词过滤"组合生效
    form.rss_sources = recommendedSources
    form.keywords = recommendedKeywords
    sourcesRecommendReason.value = data.reason || ''
    // 推荐成功后立即保存到 DB，与 BGM 推荐保持一致行为
    // rss_sources 需序列化为 JSON 字符串，与 handleSubmit 中的格式保持一致
    await updateChannel(form.id, {
      rss_sources: JSON.stringify(recommendedSources),
      keywords: recommendedKeywords,
    })
    ElMessage.success('AI 已推荐 RSS 源与关键词并已保存')
  } catch (e) {
    console.warn('RSS 源推荐失败:', e)
    // 失败时清空推荐理由，避免残留上次成功推荐的结果造成用户误解
    sourcesRecommendReason.value = ''
  } finally {
    recommendingSources.value = false
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
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .text-muted {
    color: $color-text-secondary;
  }

  .form-tip {
    margin-left: 12px;
    font-size: 12px;
    color: $color-text-secondary;
  }

  // BGM 控制区：按钮组横向排列，避免换行错乱
  .bgm-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  // 段间静音控制区：复选框 + 滑块横向排列，对齐基线
  .gap-controls {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: nowrap;
  }

  // AI 推荐理由：弱化背景突出文本，BGM/RSS 推荐共用此类
  .recommend-reason {
    margin-top: 8px;
    padding: 6px 10px;
    font-size: 12px;
    color: $color-text-secondary;
    background: rgba(64, 158, 255, 0.08);
    border-radius: 4px;
  }
}
</style>
