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
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.channel_type === 'course'" type="success" effect="plain">课程</el-tag>
            <el-tag v-else-if="row.channel_type === 'audiobook'" type="warning" effect="plain">有声读物</el-tag>
            <el-tag v-else effect="plain">资讯</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="广告" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.enable_ad === 0" type="info" effect="plain" size="small">关闭</el-tag>
            <span v-else class="text-muted">投放</span>
          </template>
        </el-table-column>
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
        <el-table-column label="素材回溯(天)" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.material_lookback_days != null">{{ row.material_lookback_days }}</span>
            <span v-else class="text-muted">继承动态</span>
          </template>
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
        <el-form-item label="素材回溯">
          <div class="lookback-wrap">
            <el-checkbox v-model="form.lookbackEnabled">自定义素材回溯天数</el-checkbox>
            <el-input-number
              v-model="form.material_lookback_days"
              :min="1"
              :max="90"
              :step="1"
              :disabled="!form.lookbackEnabled"
              controls-position="right"
              style="width: 160px"
            />
            <el-tooltip
              content="当天 pending 素材不足时，系统自动将选材时间范围放宽到最近 N 天。不勾选则继承系统动态回溯（按频道近 7 天入库频率 3/7/14 天），避免短节目依赖 BGM 补足。"
              placement="top"
            >
              <span class="form-tip" style="cursor: help">范围 1-90 天，留空继承动态</span>
            </el-tooltip>
          </div>
        </el-form-item>

        <!-- 新增频道时可选 AI 自动生成提示词 -->
        <el-form-item v-if="!editing" label="AI 生成">
          <el-checkbox v-model="form.auto_generate_prompts">创建后自动调用 AI 生成提示词</el-checkbox>
        </el-form-item>

        <!-- 扩展 / 学习频道配置区：类型、选题策略、广告、风险提示、封面 -->
        <el-divider content-position="left">扩展 / 学习频道</el-divider>
        <el-form-item label="频道类型">
          <el-select v-model="form.channel_type" style="width: 200px">
            <el-option label="资讯（默认）" value="news" />
            <el-option label="课程" value="course" />
            <el-option label="有声读物" value="audiobook" />
          </el-select>
          <span class="form-tip">课程/有声读物走章节列表 + 学习进度 UI，并自动展示合规提示</span>
        </el-form-item>
        <el-form-item label="类型标签">
          <el-input v-model="form.type_label" placeholder="如：课程 / 有声读物（冗余中文标签，留空用默认映射）" style="width: 320px" />
        </el-form-item>
        <el-form-item label="选题策略">
          <el-select v-model="form.selection_strategy" clearable style="width: 240px">
            <el-option label="按热度（默认）" value="heat" />
            <el-option label="按文档章节顺序" value="outline" />
            <el-option label="手动指定素材" value="manual" />
          </el-select>
          <span class="form-tip">课程频道建议选「按文档章节顺序」；手动需配合下方素材 ID</span>
        </el-form-item>
        <el-form-item v-if="form.selection_strategy === 'manual'" label="素材 ID">
          <el-input v-model="form.manual_material_ids_text" placeholder="逗号分隔的素材 ID，如：12,13,14" style="width: 320px" />
          <span class="form-tip">仅「手动指定素材」时生效，按列表顺序选题</span>
        </el-form-item>
        <el-form-item label="投放广告">
          <el-switch v-model="form.enable_ad" :active-value="1" :inactive-value="0" />
          <span class="form-tip">课程/资料频道建议关闭，避免 AI 生成内容插播广告</span>
        </el-form-item>
        <el-form-item label="风险提示">
          <el-select v-model="form.disclaimer_level" style="width: 220px">
            <el-option label="无（资讯）" value="none" />
            <el-option label="普通" value="normal" />
            <el-option label="强提示（课程/资料）" value="strong" />
          </el-select>
          <span class="form-tip">课程/资料类须显式「强提示」：AI 生成内容不构成专业建议</span>
        </el-form-item>
        <el-form-item label="封面图">
          <el-input v-model="form.cover_url" placeholder="封面图 URL（留空用类型默认封面）" style="width: 360px" />
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
  // 素材周期回溯天数：null（配合 lookbackEnabled=false）表示继承系统动态回溯；
  // 勾选自定义后由 el-input-number 写入 1-90，提交时透传给后端 material_lookback_days
  material_lookback_days: null,
  lookbackEnabled: false,
  // ===== 扩展 / 学习频道字段（多频道适配 M2 / 业务范围扩展 MVP） =====
  // 频道类型：news(默认)/course/audiobook，驱动小程序皮肤与课程链路
  channel_type: 'news',
  // 类型中文标签（冗余存储，留空则用前端默认映射）
  type_label: '',
  // 选题策略：heat(默认)/outline(按文档章节)/manual(手动)，课程频道用 outline
  selection_strategy: '',
  // manual 选题策略的素材 ID 列表（逗号分隔文本，提交时序列化为 JSON 数组）
  manual_material_ids_text: '',
  // 是否投放广告：1=投放(默认)/0=关闭（课程/资料频道设 0 实现零广告）
  enable_ad: 1,
  // 风险提示等级：none(默认)/normal/strong，课程/资料类须 strong
  disclaimer_level: 'none',
  // 频道封面图 URL，留空用类型默认封面
  cover_url: '',
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
  // 素材回溯：默认不勾选自定义，material_lookback_days 置 null 表示继承动态回溯
  form.material_lookback_days = null
  form.lookbackEnabled = false
  // 扩展 / 学习频道字段重置为默认
  form.channel_type = 'news'
  form.type_label = ''
  form.selection_strategy = ''
  form.manual_material_ids_text = ''
  form.enable_ad = 1
  form.disclaimer_level = 'none'
  form.cover_url = ''
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
  // 素材回溯：后端返回 null 表示继承动态回溯，对应不勾选自定义；
  // 非 null 则回填天数并勾选自定义，使 el-input-number 可编辑
  form.material_lookback_days = (row.material_lookback_days !== null && row.material_lookback_days !== undefined)
    ? row.material_lookback_days
    : null
  form.lookbackEnabled = form.material_lookback_days !== null
  // 扩展 / 学习频道字段回填
  form.channel_type = row.channel_type || 'news'
  form.type_label = row.type_label || ''
  form.selection_strategy = row.selection_strategy || ''
  // manual_material_ids 后端存 JSON 数组文本，解析为逗号分隔文本用于输入框
  try {
    const ids = row.manual_material_ids ? JSON.parse(row.manual_material_ids) : []
    form.manual_material_ids_text = Array.isArray(ids) ? ids.join(',') : ''
  } catch {
    form.manual_material_ids_text = ''
  }
  // enable_ad 为 0 表示关闭广告，其余（1/null）均视为投放
  form.enable_ad = (row.enable_ad === 0) ? 0 : 1
  form.disclaimer_level = row.disclaimer_level || 'none'
  form.cover_url = row.cover_url || ''
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
    // 扩展 / 学习频道字段：manual_material_ids 仅在 manual 策略且文本非空时
    // 序列化为 JSON 数组；否则提交 null（清空/禁用），避免脏数据残留
    const extPayload = {
      channel_type: form.channel_type,
      type_label: form.type_label || null,
      selection_strategy: form.selection_strategy || null,
      manual_material_ids:
        form.selection_strategy === 'manual' && form.manual_material_ids_text
          ? JSON.stringify(
              form.manual_material_ids_text
                .split(',')
                .map((s) => parseInt(s.trim(), 10))
                .filter((n) => !Number.isNaN(n)),
            )
          : null,
      enable_ad: form.enable_ad,
      disclaimer_level: form.disclaimer_level,
      cover_url: form.cover_url || null,
    }
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
        // 素材回溯：未勾选自定义则提交 null 继承动态；勾选则用 el-input-number 的值
        material_lookback_days: form.lookbackEnabled ? form.material_lookback_days : null,
        ...extPayload,
      })
      ElMessage.success('已更新')
    } else {
      // 新增：仅提交基本信息 + 定时 + AI生成标志 + BGM + 数据源配置 + 扩展字段，
      // 提示词由 AI 生成或留空
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
        // 素材回溯：未勾选自定义则提交 null 继承动态；勾选则用填写的天数
        material_lookback_days: form.lookbackEnabled ? form.material_lookback_days : null,
        ...extPayload,
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

  // 素材回溯控制区：复选框 + 数字输入 + 提示横向排列
  .lookback-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
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
