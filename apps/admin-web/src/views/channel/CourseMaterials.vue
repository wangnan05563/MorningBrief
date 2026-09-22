<template>
  <!-- page-container：补齐 24px 页面内边距（同 BookPool / MaterialLibrary，缺它会 0px 贴边） -->
  <div class="course-materials page-container">
    <el-card shadow="never">
      <template #header>
        <div class="page-header">
          <!-- T00811：移除与导航栏重复的页面标题，保留频道选择；
               多输入渠道信息由下方 el-alert「各渠道适用场景与数据格式要求」承载 -->
          <el-select
            v-model="targetChannelId"
            placeholder="选择目标频道（必选）"
            filterable
            clearable
            style="width: 280px"
            @change="onChannelChange"
          >
            <el-option
              v-for="c in channels"
              :key="c.id"
              :label="`${c.name}（${typeLabel(c.channel_type)}）`"
              :value="c.id"
            />
          </el-select>
        </div>
      </template>

      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
        <template #title>各渠道适用场景与数据格式要求</template>
        RSS（通用）与书籍 RSS 预制源在「频道管理」按频道选择（有声读物专用）；
        本页负责单条 / 批量素材录入，有声读物与课程频道共享以下输入渠道。
      </el-alert>

      <el-tabs v-model="activeTab">
        <!-- 本地文件上传 -->
        <el-tab-pane label="本地文件上传" name="upload">
          <div class="hint">
            适用场景：离线书稿 / 电子书 / 讲义 / 稿件。<br />
            数据格式：.txt / .md（按 Markdown 标题 # 或空行分章）；.epub / .docx / .html（按章节结构分章）；
            .pdf（按文本层分章，扫描版需先 OCR）。每章作为一条素材。
          </div>
          <el-alert
            v-if="!targetChannelId"
            type="warning"
            :closable="false"
            show-icon
            title="素材必须归属一个频道：请先在页面右上角「选择目标频道」，再上传"
            style="margin-bottom: 12px"
          />
          <el-upload
            drag
            v-model:file-list="fileList"
            :auto-upload="false"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            accept=".txt,.md,.markdown,.epub,.docx,.html,.htm,.pdf"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">将文件拖到此处，或<em>点击选择</em></div>
            <template #tip>支持 .txt / .md / .epub / .docx / .html / .pdf，单个文件；.mobi 请先转存为 EPUB</template>
          </el-upload>
          <el-form :inline="true" style="margin-top: 12px">
            <!-- T00895：来源语义即书名，标签改为"来源/书名" -->
            <el-form-item label="来源/书名"><el-input v-model="uploadSource" placeholder="上传后自动填入文件名" /></el-form-item>
            <el-form-item label="分类"><el-input v-model="uploadCategory" placeholder="文档" /></el-form-item>
            <el-tooltip
              :content="uploadDisabledReason"
              :disabled="canUpload || uploading"
              placement="top"
              :fallback-placements="['bottom', 'left', 'right']"
            >
              <span class="upload-btn-wrap">
                <IconButton
                  type="primary"
                  :disabled="!canUpload"
                  :loading="uploading"
                  :icon="Plus"
                  label="上传并解析"
                  desc="上传文件并解析为章节素材"
                  @click="doUpload"
                />
              </span>
            </el-tooltip>
          </el-form>
          <el-alert v-if="uploadResult" type="success" :closable="true" style="margin-top: 10px">{{
            uploadResult
          }}</el-alert>
        </el-tab-pane>

        <!-- 云端存储导入 COS -->
        <el-tab-pane label="云端存储导入" name="cos">
          <div class="hint">
            适用场景：团队素材已存对象存储（COS）。<br />
            数据格式：COS 对象（.txt / .md 等），按 key 取回后解析为章节素材（source_type=cos）。
          </div>
          <el-form label-width="90px" style="max-width: 560px">
            <el-form-item label="对象 Key">
              <el-input v-model="cosKey" placeholder="如 materials/book1.txt" />
            </el-form-item>
            <el-form-item label="来源/书名"><el-input v-model="cosSource" placeholder="COS导入" /></el-form-item>
            <el-form-item label="分类"><el-input v-model="cosCategory" placeholder="可选" /></el-form-item>
            <IconButton
              type="primary"
              :disabled="!cosKey || !targetChannelId"
              :loading="cosLoading"
              :icon="Upload"
              label="导入"
              desc="从云端存储导入 COS 对象"
              @click="doCos"
            />
          </el-form>
          <el-alert v-if="cosResult" type="success" :closable="true" style="margin-top: 10px">{{
            cosResult
          }}</el-alert>
        </el-tab-pane>

        <!-- 手动录入 -->
        <el-tab-pane label="手动录入" name="manual">
          <div class="hint">
            适用场景：单篇短稿 / 临时补充。<br />
            数据格式：表单（标题 + 正文 + 可选 URL）；留空 URL 时按正文内容去重。
          </div>
          <el-form label-width="80px" style="max-width: 640px">
            <el-form-item label="标题" required
              ><el-input v-model="manual.title" placeholder="素材标题"
            /></el-form-item>
            <el-form-item label="正文" required>
              <el-input v-model="manual.content" type="textarea" :rows="6" placeholder="正文全文" />
            </el-form-item>
            <el-form-item label="来源/书名"><el-input v-model="manual.source" placeholder="手动录入" /></el-form-item>
            <el-form-item label="分类"><el-input v-model="manual.category" placeholder="可选" /></el-form-item>
            <el-form-item label="URL"
              ><el-input v-model="manual.url" placeholder="可选（留空则按内容去重）"
            /></el-form-item>
            <IconButton type="primary" :disabled="!canManual" :loading="manualLoading" :icon="Check" label="保存到素材池" desc="将手动录入内容保存为素材" @click="doManual" />
          </el-form>
        </el-tab-pane>

        <!-- API / URL 拉取 -->
        <el-tab-pane label="API / URL 拉取" name="url">
          <div class="hint">
            适用场景：对接 CMS / 知识库 / 第三方接口。<br />
            数据格式：HTTP GET 返回 JSON 或 HTML，复用正文解析器提取内容（source_type=api）。
          </div>
          <el-form label-width="90px" style="max-width: 640px">
            <el-form-item label="URL" required
              ><el-input v-model="urlInput" placeholder="https://..." />
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="urlType" style="width: 180px">
                <el-option label="API 拉取" value="api" />
                <el-option label="分享链接" value="qrcode" />
              </el-select>
            </el-form-item>
            <el-form-item label="来源/书名"><el-input v-model="urlSource" placeholder="URL拉取" /></el-form-item>
            <el-form-item label="分类"><el-input v-model="urlCategory" placeholder="可选" /></el-form-item>
            <IconButton
              type="primary"
              :disabled="!urlInput || !targetChannelId"
              :loading="urlLoading"
              :icon="Upload"
              label="拉取并入库"
              desc="从 URL 拉取内容并入库为素材"
              @click="doUrl"
            />
          </el-form>
        </el-tab-pane>

        <!-- 二维码 / 链接分享 -->
        <el-tab-pane label="二维码 / 链接分享" name="share">
          <div class="hint">
            适用场景：运营从微信 / 网页分享的链接。<br />
            先拉取预览，复核后转「手动录入」正式入库（source_type=qrcode），避免自动入库脏数据。
          </div>
          <el-form label-width="90px" style="max-width: 640px">
            <el-form-item label="分享链接" required
              ><el-input v-model="shareUrl" placeholder="https://..." />
            </el-form-item>
            <IconButton :disabled="!shareUrl || !targetChannelId" :loading="shareLoading" :icon="View" label="获取预览" desc="拉取分享链接的标题与正文预览" @click="doSharePreview" />
          </el-form>
          <el-card v-if="shareData" shadow="never" style="margin-top: 12px">
            <div><b>标题：</b>{{ shareData.title }}</div>
            <div style="margin: 8px 0"><b>正文预览：</b></div>
            <el-input :model-value="shareData.content" type="textarea" :rows="6" readonly />
            <div style="margin-top: 8px">
              <IconButton type="success" :disabled="!shareData.available" :icon="Plus" label="转为手动录入" desc="将预览内容预填到手动录入表单" @click="fillManualFromShare" />
              <span v-if="!shareData.available" style="color: #e6a23c; margin-left: 8px"
                >未提取到正文，请改用手动录入</span
              >
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from '../../utils/message'
import { UploadFilled, Plus, Upload, Check, View } from '@element-plus/icons-vue'
import { listChannels } from '../../api/channels'
import {
  uploadMaterialFile,
  importFromCos,
  createMaterial,
  importFromUrl,
  sharePreview,
} from '../../api/materials'

const TYPE_LABELS = { news: '资讯', course: '课程', audiobook: '有声读物' }
const typeLabel = (t) => TYPE_LABELS[t] || t || '资讯'

const channels = ref([])
const targetChannelId = ref(null)
const activeTab = ref('upload')

// 本地文件上传
const fileList = ref([])
// T00895：来源即书名，未上传文档时保持为空（后端会以文件名兜底），选择文件后自动填充
const uploadSource = ref('')
const uploadCategory = ref('文档')
const uploading = ref(false)
const uploadResult = ref('')
const selectedFile = ref(null)
const canUpload = computed(() => !!selectedFile.value && !!targetChannelId.value)
/** 禁用原因（悬停按钮可见，T00621：不再静默置灰让用户猜） */
const uploadDisabledReason = computed(() => {
  if (!selectedFile.value && !targetChannelId.value) return '请先选择文件，并在页面右上角选择目标频道'
  if (!targetChannelId.value) return '请先在页面右上角「选择目标频道」'
  if (!selectedFile.value) return '请先选择要上传的文件'
  return ''
})

function onFileChange(file) {
  selectedFile.value = file.raw
  // T00895：上传文档后自动把文件名（去扩展名）填入「来源/书名」，无需手动输入
  // 后端对默认/空来源也会用 `Path(filename).stem` 兜底为书名，前端预填仅为用户可见可改
  const name = (file.name || '').trim()
  if (name) uploadSource.value = name.replace(/\.[^.]+$/, '')
}
function onFileRemove() {
  selectedFile.value = null
  fileList.value = []
}
async function doUpload() {
  if (!selectedFile.value) return
  uploading.value = true
  uploadResult.value = ''
  try {
    const res = await uploadMaterialFile(selectedFile.value, {
      channelId: targetChannelId.value,
      source: uploadSource.value || '文档上传',
      category: uploadCategory.value,
    })
    uploadResult.value = `解析完成，新增 ${res.count} 条素材`
    ElMessage.success('上传成功')
    fileList.value = []
    selectedFile.value = null
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    uploading.value = false
  }
}

// 云端存储导入
const cosKey = ref('')
const cosSource = ref('COS导入')
const cosCategory = ref('')
const cosLoading = ref(false)
const cosResult = ref('')
async function doCos() {
  cosLoading.value = true
  cosResult.value = ''
  try {
    const res = await importFromCos({
      key: cosKey.value,
      channel_id: targetChannelId.value,
      source: cosSource.value || 'COS导入',
      category: cosCategory.value,
    })
    cosResult.value = `导入完成，新增 ${res.count} 条素材`
    ElMessage.success('COS 导入成功')
    cosKey.value = ''
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    cosLoading.value = false
  }
}

// 手动录入
const manual = reactive({ title: '', content: '', source: '手动录入', category: '', url: '' })
const manualLoading = ref(false)
const canManual = computed(() => !!manual.title && !!manual.content && !!targetChannelId.value)
async function doManual() {
  manualLoading.value = true
  try {
    await createMaterial({
      workflow_id: '',
      channel_id: targetChannelId.value,
      source: manual.source || '手动录入',
      title: manual.title,
      content: manual.content,
      url: manual.url || '',
      category: manual.category || '',
      source_type: 'list',
    })
    ElMessage.success('已保存到素材池')
    manual.title = ''
    manual.content = ''
    manual.url = ''
    manual.category = ''
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    manualLoading.value = false
  }
}

// API / URL 拉取
const urlInput = ref('')
const urlType = ref('api')
const urlSource = ref('URL拉取')
const urlCategory = ref('')
const urlLoading = ref(false)
async function doUrl() {
  urlLoading.value = true
  try {
    await importFromUrl({
      url: urlInput.value,
      channel_id: targetChannelId.value,
      source: urlSource.value || 'URL拉取',
      category: urlCategory.value || '',
      source_type: urlType.value,
    })
    ElMessage.success('拉取并入库成功')
    urlInput.value = ''
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    urlLoading.value = false
  }
}

// 二维码 / 链接分享
const shareUrl = ref('')
const shareLoading = ref(false)
const shareData = ref(null)
async function doSharePreview() {
  shareLoading.value = true
  shareData.value = null
  try {
    const res = await sharePreview({ url: shareUrl.value, channel_id: targetChannelId.value })
    shareData.value = res
    if (!res.available) {
      ElMessage.warning('未提取到正文，请改用手动录入')
    }
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    shareLoading.value = false
  }
}
function fillManualFromShare() {
  if (!shareData.value) return
  activeTab.value = 'manual'
  manual.title = shareData.value.title || ''
  manual.content = shareData.value.content || ''
  manual.source = '分享导入'
  manual.url = shareData.value.url || ''
  manual.category = ''
  ElMessage.info('已预填到「手动录入」，复核后保存（source_type=qrcode）')
}

function onChannelChange() {
  // 切换频道时清空各渠道结果，避免误操作
  uploadResult.value = ''
  cosResult.value = ''
}

onMounted(async () => {
  try {
    channels.value = await listChannels()
    // 仅有一个频道时自动选中：素材必须归属频道，单频道场景没有让用户手选的价值
    if (channels.value.length === 1 && !targetChannelId.value) {
      targetChannelId.value = channels.value[0].id
    }
  } catch (e) {
    /* 拦截器已提示 */
  }
})
</script>

<style scoped>
/* T00621：tooltip 需要块级包裹元素，禁用按钮的悬停提示才能命中 */
.upload-btn-wrap {
  display: inline-block;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.page-title {
  font-weight: 600;
  font-size: 15px;
}
.hint {
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px 12px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 14px;
}
</style>
