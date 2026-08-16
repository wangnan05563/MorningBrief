<template>
  <div class="page-container ai-config">
    <div class="top-bar">
      <el-button type="primary" :icon="Check" :loading="saving" @click="handleSave">
        保存配置
      </el-button>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs" @tab-change="handleTabChange">
      <!-- LLM 配置 -->
      <el-tab-pane label="LLM 大模型" name="llm">
        <el-card shadow="never">
          <!-- 预设选择 -->
          <div class="preset-section">
            <span class="section-label">快速选择提供商：</span>
            <el-select
              v-model="selectedPreset"
              placeholder="选择预设"
              @change="applyPreset"
              style="width: 200px"
            >
              <el-option
                v-for="p in presets"
                :key="p.key"
                :label="p.label"
                :value="p.key"
              />
            </el-select>
            <el-link
              v-if="currentPreset?.api_key_url"
              :href="currentPreset.api_key_url"
              target="_blank"
              type="primary"
              underline="hover"
              style="margin-left: 12px"
            >
              获取 API Key
            </el-link>
            <el-button
              type="warning"
              plain
              :icon="RefreshLeft"
              :loading="resetting"
              style="margin-left: auto"
              @click="handleResetConfig"
            >
              恢复初始配置
            </el-button>
          </div>

          <el-form :model="llmForm" label-width="120px" class="config-form">
            <el-divider content-position="left">节目参数（时长/字数联动）</el-divider>
            <el-form-item label="目标时长">
              <el-slider
                v-model="llmForm.target_duration_sec"
                :min="180" :max="1200" :step="30"
                show-input
                style="max-width: 500px"
              />
              <span class="field-tip">默认 600 秒（10 分钟），与稿件字数反向关联</span>
            </el-form-item>
            <el-form-item label="段间静音">
              <el-slider
                v-model="llmForm.segment_gap_sec"
                :min="0" :max="3" :step="0.1"
                show-input
                style="max-width: 500px"
              />
              <span class="field-tip">TTS 段间留白（秒），默认 0.5s，BGM 在此时段自然浮现</span>
            </el-form-item>
            <el-form-item label="预期字数">
              <el-tag type="info">
                当前配置下需约 {{ calculatedWords }} 字
                （{{ calculatedSegments }} 段 × {{ calculatedWordsPerSeg }} 字/段 + 开场白/结尾 145 字）
              </el-tag>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="llmForm.api_key"
                :type="showLlmKey ? 'text' : 'password'"
                placeholder="输入 LLM API Key"
              >
                <template #append>
                  <el-button @click="showLlmKey = !showLlmKey">
                    {{ showLlmKey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="llmForm.base_url" placeholder="OpenAI 兼容 API 地址" />
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="llmForm.model" placeholder="如 qwen-max, gpt-4o-mini" />
            </el-form-item>
            <el-form-item label="超时(秒)">
              <el-input-number v-model="llmForm.timeout_sec" :min="5" :max="120" />
            </el-form-item>
            <el-form-item label="重试次数">
              <el-input-number v-model="llmForm.retry_attempts" :min="0" :max="10" />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                plain
                :loading="testingLlm"
                @click="handleTestLLM"
              >
                测试连接
              </el-button>
              <el-tag
                v-if="llmTestResult"
                :type="llmTestResult.success ? 'success' : 'danger'"
                style="margin-left: 12px"
              >
                {{ llmTestResult.message }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- TTS 配置 -->
      <el-tab-pane label="TTS 语音合成" name="tts">
        <el-card shadow="never">
          <!-- Provider 选择 -->
          <div class="preset-section">
            <span class="section-label">TTS 引擎：</span>
            <el-select
              v-model="ttsForm.provider"
              placeholder="选择 TTS Provider"
              @change="handleProviderChange"
              style="width: 320px"
            >
              <el-option
                v-for="p in ttsProviders"
                :key="p.key"
                :label="p.label"
                :value="p.key"
              />
            </el-select>
            <el-tag
              v-if="['edge', 'kokoro', 'piper'].includes(ttsForm.provider)"
              type="success"
              style="margin-left: 12px"
            >
              免费 · 无需 API Key
            </el-tag>
          </div>

          <!-- TTS 交叉音色（段落间轮流换声，避免同质化） -->
          <el-divider content-position="left">交叉音色（段落轮流换声，避免同质化）</el-divider>
          <el-form :model="ttsForm.cross_voice" label-width="120px" class="config-form">
            <el-form-item label="启用交叉音色">
              <el-switch v-model="ttsForm.cross_voice.enabled" />
              <span class="field-tip" style="margin-left: 12px;">
                开启后，稿件各段落将按所选策略轮流使用不同音色，避免单一音色同质化
              </span>
            </el-form-item>
            <el-form-item label="切换策略">
              <el-select v-model="ttsForm.cross_voice.strategy" style="width: 220px">
                <el-option label="轮流（段落依次轮换）" value="round_robin" />
                <el-option label="随机（避免相邻重复）" value="random" />
                <el-option label="每隔 N 段切换" value="interval" />
              </el-select>
              <el-input-number
                v-if="ttsForm.cross_voice.strategy === 'interval'"
                v-model="ttsForm.cross_voice.interval"
                :min="1" :max="20" :step="1"
                controls-position="right"
                style="margin-left: 12px; width: 140px;"
              />
              <span v-if="ttsForm.cross_voice.strategy === 'interval'" class="field-tip" style="margin-left: 8px;">段</span>
            </el-form-item>
            <el-form-item label="音色组合">
              <el-select
                v-model="currentCrossVoiceList"
                multiple
                filterable
                collapse-tags
                collapse-tags-tooltip
                :disabled="crossVoiceDisabledForProvider"
                placeholder="选择 2 个及以上音色"
                style="width: 520px;"
              >
                <el-option
                  v-for="v in voices"
                  :key="v.key"
                  :label="v.label"
                  :value="v.key"
                />
              </el-select>
              <span class="field-tip" style="margin-left: 12px;">
                至少选 2 个；当前引擎：{{ ttsForm.provider }}
                <template v-if="crossVoiceDisabledForProvider">（Piper 为单说话人模型，交叉音色不生效）</template>
              </span>
            </el-form-item>
            <el-alert
              v-if="crossVoiceInsufficientForProvider"
              type="warning"
              :closable="false"
              show-icon
              title="交叉音色当前不会生效"
              description="已启用交叉音色，但当前引擎「{{ ttsForm.provider }}」下仅选了不足 2 个音色；保存后合成将回退为单音色。请至少选择 2 个音色后再保存。"
              style="margin-top: 4px;"
            />
          </el-form>

          <!-- 阿里云 NLS 配置 -->
          <el-form
            v-if="ttsForm.provider === 'aliyun'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <div class="preset-section" style="border-bottom: none; padding-bottom: 0;">
              <span class="section-label">获取密钥：</span>
              <el-link
                href="https://ram.console.aliyun.com/manage/ak"
                target="_blank"
                type="primary"
                underline="hover"
                style="margin-right: 16px"
              >
                AccessKey 管理
              </el-link>
              <el-link
                href="https://nls-portal.console.aliyun.com/applist"
                target="_blank"
                type="primary"
                underline="hover"
              >
                NLS 项目 AppKey
              </el-link>
            </div>
            <el-form-item label="AccessToken">
              <el-input
                v-model="ttsForm.api_key"
                :type="showTtsKey ? 'text' : 'password'"
                placeholder="NLS AccessToken（32位hex，非 AccessKey Secret）"
              >
                <template #append>
                  <el-button @click="showTtsKey = !showTtsKey">
                    {{ showTtsKey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                NLS 控制台「获取 Token」生成的访问令牌，不要填 AccessKey Secret
              </div>
            </el-form-item>
            <el-form-item label="App Key">
              <el-input
                v-model="ttsForm.appkey"
                :type="showTtsAppkey ? 'text' : 'password'"
                placeholder="NLS 项目 AppKey"
              >
                <template #append>
                  <el-button @click="showTtsAppkey = !showTtsAppkey">
                    {{ showTtsAppkey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
              <div class="field-tip">
                NLS 项目详情页的 AppKey（非 AccessKey ID）
              </div>
            </el-form-item>
            <el-form-item label="音色">
              <el-select v-model="ttsForm.voice" style="width: 240px">
                <el-option
                  v-for="v in voices"
                  :key="v.key"
                  :label="v.label"
                  :value="v.key"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="采样率">
              <el-input-number v-model="ttsForm.sample_rate" :min="8000" :max="48000" :step="1000" />
            </el-form-item>
            <el-form-item label="音频格式">
              <el-select v-model="ttsForm.format" style="width: 120px">
                <el-option label="MP3" value="mp3" />
                <el-option label="WAV" value="wav" />
                <el-option label="PCM" value="pcm" />
              </el-select>
            </el-form-item>
            <el-form-item label="超时(秒)">
              <el-input-number v-model="ttsForm.timeout_sec" :min="10" :max="300" />
            </el-form-item>
            <el-form-item label="重试次数">
              <el-input-number v-model="ttsForm.retry_attempts" :min="0" :max="10" />
            </el-form-item>
            <el-form-item label="音量">
              <el-input-number v-model="ttsForm.aliyun_volume" :min="0" :max="100" />
              <span class="field-tip" style="margin-left: 8px">[0, 100]，默认 50</span>
            </el-form-item>
            <el-form-item label="语速">
              <el-input-number v-model="ttsForm.aliyun_speech_rate" :min="-500" :max="500" />
              <span class="field-tip" style="margin-left: 8px">[-500, 500]，默认 0</span>
            </el-form-item>
            <el-form-item label="基频">
              <el-input-number v-model="ttsForm.aliyun_pitch_rate" :min="-500" :max="500" />
              <span class="field-tip" style="margin-left: 8px">[-500, 500]，默认 0</span>
            </el-form-item>
          </el-form>

          <!-- Edge-TTS 配置（免费方案） -->
          <el-form
            v-else-if="ttsForm.provider === 'edge'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <el-alert
              type="success"
              :closable="false"
              style="margin-bottom: 16px"
            >
              Edge-TTS 基于微软 Edge 浏览器在线 TTS 接口，音色与 Azure 神经网络
              音色同源。完全免费、无字符上限、无需 API Key。非官方接口，建议作为
              降级或开发调试方案。
            </el-alert>
            <el-form-item label="音色">
              <el-select v-model="ttsForm.edge_voice" style="width: 360px">
                <el-option
                  v-for="v in voices"
                  :key="v.key"
                  :label="v.label"
                  :value="v.key"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="语速调节">
              <el-slider
                v-model="edgeRatePercent"
                :min="-50" :max="100" :step="5"
                show-input
                style="max-width: 500px"
              />
              <span class="field-tip">
                当前倍率 {{ (edgeRatePercent / 100 + 1).toFixed(2) }}x，
                实际播报速率约 {{ Math.round(210 * (edgeRatePercent / 100 + 1)) }} 字/分
              </span>
            </el-form-item>
            <el-form-item label="音量调节">
              <el-input
                v-model="ttsForm.edge_volume"
                placeholder="如 +20% / -10%（可为空）"
              />
            </el-form-item>
            <el-form-item label="基频调节">
              <el-input
                v-model="ttsForm.edge_pitch"
                placeholder="如 +5Hz / -3Hz（可为空）"
              />
            </el-form-item>
          </el-form>

          <!-- 腾讯云 TTS 配置 -->
          <el-form
            v-else-if="ttsForm.provider === 'tencent'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <el-alert
              type="info"
              :closable="false"
              style="margin-bottom: 16px"
            >
              腾讯云 TTS 凭证可复用 COS 的 SecretId/SecretKey（留空则自动回退到
              COS 配置）。免费额度：精品音色 800 万字符（3 个月内，需控制台领取）。
            </el-alert>
            <el-form-item label="SecretId">
              <el-input
                v-model="ttsForm.tencent_secret_id"
                :type="showTencentId ? 'text' : 'password'"
                placeholder="留空则回退到 COS_SECRET_ID"
              >
                <template #append>
                  <el-button @click="showTencentId = !showTencentId">
                    {{ showTencentId ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="SecretKey">
              <el-input
                v-model="ttsForm.tencent_secret_key"
                :type="showTencentKey ? 'text' : 'password'"
                placeholder="留空则回退到 COS_SECRET_KEY"
              >
                <template #append>
                  <el-button @click="showTencentKey = !showTencentKey">
                    {{ showTencentKey ? '隐藏' : '显示' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
            <el-form-item label="地域">
              <el-input
                v-model="ttsForm.tencent_region"
                placeholder="如 ap-guangzhou"
              />
            </el-form-item>
            <el-form-item label="音色">
              <el-select v-model="ttsForm.tencent_voice_type" style="width: 360px">
                <el-option
                  v-for="v in voices"
                  :key="Number(v.key)"
                  :label="v.label"
                  :value="Number(v.key)"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="音量">
              <el-input-number v-model="ttsForm.tencent_volume" :min="-10" :max="10" />
              <span class="field-tip" style="margin-left: 8px">[-10, 10]，0 为默认</span>
            </el-form-item>
            <el-form-item label="语速">
              <el-input-number v-model="ttsForm.tencent_speed" :min="-2" :max="6" />
              <span class="field-tip" style="margin-left: 8px">[-2, 6]，0 为默认</span>
            </el-form-item>
          </el-form>

          <!-- Kokoro TTS 配置（Apache 2.0 本地离线，免费高质量） -->
          <el-form
            v-else-if="ttsForm.provider === 'kokoro'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <el-alert
              type="success"
              :closable="false"
              style="margin-bottom: 16px"
            >
              Kokoro 是基于 Apache 2.0 开源许可证的本地离线神经网络 TTS（82M 参数），
              完全免费、无需 API Key、不依赖任何云服务、不联网。中文音质自然度
              对标或优于 Edge-TTS。启用前需安装依赖并首次下载模型权重（见部署文档）。
            </el-alert>
            <el-form-item label="语言">
              <el-select v-model="ttsForm.kokoro_lang" style="width: 240px">
                <el-option label="中文普通话 (z)" value="z" />
                <el-option label="美式英语 (a)" value="a" />
                <el-option label="英式英语 (b)" value="b" />
                <el-option label="西班牙语 (e)" value="e" />
                <el-option label="法语 (f)" value="f" />
                <el-option label="印地语 (h)" value="h" />
                <el-option label="意大利语 (i)" value="i" />
                <el-option label="日语 (j)" value="j" />
                <el-option label="巴西葡萄牙语 (p)" value="p" />
              </el-select>
              <div class="field-tip">语言代码须与下方音色匹配（如中文配 zf_*/zm_*）</div>
            </el-form-item>
            <el-form-item label="音色">
              <el-select v-model="ttsForm.kokoro_voice" style="width: 380px">
                <el-option
                  v-for="v in voices"
                  :key="v.key"
                  :label="v.label"
                  :value="v.key"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="语速">
              <el-slider
                v-model="ttsForm.kokoro_speed"
                :min="0.5" :max="2.0" :step="0.05"
                show-input
                style="max-width: 500px"
              />
              <span class="field-tip">倍率，1.0 为正常，&gt;1 加快，&lt;1 减慢</span>
            </el-form-item>
            <el-form-item label="模型下载">
              <el-button
                type="warning"
                plain
                :loading="downloadingTts"
                @click="handleDownloadTtsModels"
              >
                下载模型
              </el-button>
              <el-tag
                v-if="ttsDownloadStatus"
                :type="ttsDownloadStatus.status === 'success' ? 'success' : (ttsDownloadStatus.status === 'failed' ? 'danger' : 'info')"
                style="margin-left: 12px"
              >
                {{ ttsDownloadStatus.message }}
                <span v-if="downloadPercent != null">（{{ downloadPercent }}%）</span>
              </el-tag>
              <div class="field-tip">
                首次使用需从 HuggingFace 下载模型权重（中文 ~165MB），之后完全离线。
                若提示未安装 kokoro，请先 <code>pip install kokoro misaki[zh]</code>。
              </div>
            </el-form-item>
          </el-form>

          <!-- Piper TTS 配置（MIT 本地离线，轻量免费） -->
          <el-form
            v-else-if="ttsForm.provider === 'piper'"
            :model="ttsForm"
            label-width="120px"
            class="config-form"
          >
            <el-alert
              type="success"
              :closable="false"
              style="margin-bottom: 16px"
            >
              Piper 是基于 MIT 开源许可证的本地离线轻量 TTS，完全免费、无需 API Key、
              不联网。模型仅 40-100MB，CPU 实时因子 &lt;0.2，适合资源受限设备部署。
              启用前需安装 piper-tts 并下载语音模型（.onnx + .onnx.json）。
            </el-alert>
            <el-form-item label="音色模型">
              <el-select v-model="ttsForm.piper_voice" style="width: 360px">
                <el-option
                  v-for="v in voices"
                  :key="v.key"
                  :label="v.label"
                  :value="v.key"
                />
              </el-select>
              <div class="field-tip">
                也可点击下方「下载模型」按钮在后台自动拉取（无需登录服务器）
              </div>
            </el-form-item>
            <el-form-item label="模型目录">
              <el-input
                v-model="ttsForm.piper_voice_dir"
                placeholder="./models/piper"
              />
              <div class="field-tip">
                存放 {音色}.onnx 与 {音色}.onnx.json 的目录（相对/绝对路径皆可）
              </div>
            </el-form-item>
            <el-form-item label="语速">
              <el-slider
                v-model="ttsForm.piper_length_scale"
                :min="0.5" :max="2.0" :step="0.05"
                show-input
                style="max-width: 500px"
              />
              <span class="field-tip">length_scale，1.0 正常，&gt;1 变慢，&lt;1 变快</span>
            </el-form-item>
            <el-form-item label="音量">
              <el-slider
                v-model="ttsForm.piper_volume"
                :min="0" :max="1" :step="0.05"
                show-input
                style="max-width: 500px"
              />
            </el-form-item>
            <el-form-item label="自然度">
              <el-slider
                v-model="ttsForm.piper_noise_scale"
                :min="0" :max="1" :step="0.01"
                show-input
                style="max-width: 500px"
              />
              <span class="field-tip">noise_scale，影响音色随机性/自然度</span>
            </el-form-item>
            <el-form-item label="模型下载">
              <el-button
                type="warning"
                plain
                :loading="downloadingTts"
                @click="handleDownloadTtsModels"
              >
                下载模型
              </el-button>
              <el-tag
                v-if="ttsDownloadStatus"
                :type="ttsDownloadStatus.status === 'success' ? 'success' : (ttsDownloadStatus.status === 'failed' ? 'danger' : 'info')"
                style="margin-left: 12px"
              >
                {{ ttsDownloadStatus.message }}
                <span v-if="downloadPercent != null">（{{ downloadPercent }}%）</span>
              </el-tag>
              <div class="field-tip">
                下载 .onnx + .onnx.json 到上方「模型目录」。支持 HF_ENDPOINT 镜像（如
                https://hf-mirror.com）以适配网络受限环境。
              </div>
            </el-form-item>
          </el-form>

          <!-- 试音区域（三套 Provider 共用） -->
          <div class="preview-section">
            <div class="preset-section" style="border-bottom: none; padding-bottom: 0; margin-bottom: 12px;">
              <span class="section-label">风格预设：</span>
              <el-button-group>
                <el-button
                  v-for="p in currentTtsPresets"
                  :key="p.name"
                  size="small"
                  @click="applyTtsPreset(p)"
                >
                  {{ p.name }}
                </el-button>
              </el-button-group>
              <span class="field-tip" style="margin-left: 12px;">点击预设一键填入参数，然后试音</span>
            </div>
            <el-form label-width="120px" class="config-form">
              <el-form-item label="试音文本">
                <el-input
                  v-model="previewText"
                  type="textarea"
                  :rows="2"
                  placeholder="输入试音文本"
                  style="max-width: 500px"
                />
              </el-form-item>
              <el-form-item>
                <el-button
                  type="primary"
                  plain
                  :loading="previewing"
                  @click="handlePreviewTTS"
                >
                  试音
                </el-button>
                <audio
                  v-if="previewAudioUrl"
                  :src="previewAudioUrl"
                  controls
                  style="margin-left: 12px; height: 36px; vertical-align: middle;"
                />
              </el-form-item>
            </el-form>
          </div>

          <!-- 测试连接（三套 Provider 共用） -->
          <el-form
            :model="ttsForm"
            label-width="120px"
            class="config-form"
            style="margin-top: 16px; border-top: 1px solid var(--el-border-color); padding-top: 16px;"
          >
            <el-form-item>
              <el-button
                type="primary"
                plain
                :loading="testingTts"
                @click="handleTestTTS"
              >
                测试连接
              </el-button>
              <el-tag
                v-if="ttsTestResult"
                :type="ttsTestResult.success ? 'success' : 'danger'"
                style="margin-left: 12px"
              >
                {{ ttsTestResult.message }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- 用量统计 -->
      <el-tab-pane label="用量统计" name="usage">
        <el-card shadow="never" v-loading="usageLoading">
          <!-- 今日数据卡片 -->
          <div class="usage-cards">
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.llm_calls }}</div>
              <div class="usage-label">LLM 调用次数</div>
            </div>
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.llm_tokens }}</div>
              <div class="usage-label">LLM Token 消耗</div>
            </div>
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.tts_calls }}</div>
              <div class="usage-label">TTS 调用次数</div>
            </div>
            <div class="usage-card">
              <div class="usage-value">{{ todayUsage.tts_chars }}</div>
              <div class="usage-label">TTS 合成字符</div>
            </div>
            <div class="usage-card highlight">
              <div class="usage-value">${{ todayUsage.cost_usd.toFixed(4) }}</div>
              <div class="usage-label">今日费用</div>
            </div>
          </div>

          <!-- 7 天趋势表 -->
          <el-table :data="usageTrend" stripe style="margin-top: 24px">
            <el-table-column prop="date" label="日期" width="130" />
            <el-table-column prop="llm_calls" label="LLM 调用" width="100" />
            <el-table-column prop="llm_tokens" label="LLM Token" width="120" />
            <el-table-column prop="tts_calls" label="TTS 调用" width="100" />
            <el-table-column prop="tts_chars" label="TTS 字符" width="120" />
            <el-table-column label="费用 (USD)" width="120">
              <template #default="{ row }">
                ${{ row.cost_usd.toFixed(4) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElMessage, ElMessageBox } from '../../utils/message'
import { Check, RefreshLeft } from '@element-plus/icons-vue'
import api from '../../api'

const route = useRoute()
const router = useRouter()

const activeTab = ref('llm')
const saving = ref(false)
const loading = ref(false)

// LLM 配置
const llmForm = ref({
  api_key: '',
  base_url: '',
  model: '',
  timeout_sec: 30,
  retry_attempts: 3,
  target_duration_sec: 600,
  segment_gap_sec: 0.5,
})
const showLlmKey = ref(false)
const testingLlm = ref(false)
const llmTestResult = ref(null)
const selectedPreset = ref('')
const presets = ref([])
// 每个预设独立保存的配置（API Key 脱敏），结构：{preset_key: {api_key, base_url, model}}
const presetConfigs = ref({})
const resetting = ref(false)

// TTS 配置（覆盖阿里云/Edge-TTS/腾讯云三套字段）
const ttsForm = ref({
  provider: 'aliyun',
  // 阿里云 NLS
  api_key: '',
  appkey: '',
  voice: 'xiaoyun',
  sample_rate: 44100,
  format: 'mp3',
  timeout_sec: 60,
  retry_attempts: 3,
  // 阿里云 TTS 音量/语速/基频（NLS tts_request 参数）
  aliyun_volume: 50,
  aliyun_speech_rate: 0,
  aliyun_pitch_rate: 0,
  // Edge-TTS
  edge_voice: 'zh-CN-XiaoxiaoNeural',
  edge_rate: '',
  edge_volume: '',
  edge_pitch: '',
  // 腾讯云 TTS
  tencent_secret_id: '',
  tencent_secret_key: '',
  tencent_region: 'ap-guangzhou',
  tencent_voice_type: 101011,
  tencent_volume: 0,
  tencent_speed: 0,
  // Kokoro TTS（本地离线，免费高质量）
  kokoro_lang: 'z',
  kokoro_voice: 'zf_xiaoxiao',
  kokoro_speed: 1.0,
  // Piper TTS（本地离线，轻量免费）
  piper_voice: 'zh_CN-huayan-medium',
  piper_voice_dir: './models/piper',
  piper_length_scale: 1.0,
  piper_volume: 0.5,
  piper_noise_scale: 0.667,
  // TTS 交叉音色（段落间轮流换声，避免同质化）
  // voices 按 provider 维度存音色 key 列表；strategy: round_robin/random/interval
  cross_voice: {
    enabled: false,
    strategy: 'round_robin',
    interval: 2,
    voices: {},
  },
})
const showTtsKey = ref(false)
const showTtsAppkey = ref(false)
const showTencentId = ref(false)
const showTencentKey = ref(false)
const testingTts = ref(false)
const ttsTestResult = ref(null)
const voices = ref([])

// TTS Provider 选项
const ttsProviders = [
  { key: 'aliyun', label: '阿里云 NLS（付费，需 API Key）' },
  { key: 'edge', label: 'Edge-TTS（免费，微软神经网络音色）' },
  { key: 'tencent', label: '腾讯云 TTS（付费，可复用 COS 凭证）' },
  { key: 'kokoro', label: 'Kokoro（免费开源，本地离线神经网络）' },
  { key: 'piper', label: 'Piper（免费开源，本地离线轻量）' },
]

// TTS 风格预设：按 provider 提供不同的参数组合
// 每组预设覆盖该 provider 支持的音量/语速/基频参数
const ttsPresets = {
  edge: [
    { name: '标准', rate: 0, volume: 0, pitch: 0 },
    { name: '沉稳新闻', rate: -10, volume: 0, pitch: -3 },
    { name: '活泼播报', rate: 10, volume: 10, pitch: 5 },
    { name: '柔和轻语', rate: -5, volume: -15, pitch: -2 },
  ],
  tencent: [
    { name: '标准', volume: 0, speed: 0 },
    { name: '沉稳新闻', volume: 0, speed: -1 },
    { name: '活泼播报', volume: 2, speed: 1 },
    { name: '柔和轻语', volume: -3, speed: -1 },
  ],
  aliyun: [
    { name: '标准', volume: 50, speech_rate: 0, pitch_rate: 0 },
    { name: '沉稳新闻', volume: 50, speech_rate: -100, pitch_rate: -50 },
    { name: '活泼播报', volume: 60, speech_rate: 100, pitch_rate: 50 },
    { name: '柔和轻语', volume: 40, speech_rate: -50, pitch_rate: -30 },
  ],
  kokoro: [
    { name: '标准', speed: 1.0 },
    { name: '沉稳新闻', speed: 0.9 },
    { name: '活泼播报', speed: 1.15 },
    { name: '柔和轻语', speed: 0.85 },
  ],
  piper: [
    { name: '标准', length_scale: 1.0 },
    { name: '沉稳新闻', length_scale: 1.1 },
    { name: '活泼播报', length_scale: 0.9 },
    { name: '柔和轻语', length_scale: 1.05 },
  ],
}

// 当前 provider 对应的预设列表
const currentTtsPresets = computed(() => ttsPresets[ttsForm.value.provider] || [])

// 交叉音色：当前 provider 选中的音色列表（按 provider 维度隔离存储）
const currentCrossVoiceList = computed({
  get() {
    const cv = ttsForm.value.cross_voice
    return (cv && cv.voices && cv.voices[ttsForm.value.provider]) || []
  },
  set(val) {
    if (!ttsForm.value.cross_voice.voices) ttsForm.value.cross_voice.voices = {}
    ttsForm.value.cross_voice.voices[ttsForm.value.provider] = val || []
  },
})
// Piper 为单说话人模型，交叉音色不生效（参数被忽略），给出提示
const crossVoiceDisabledForProvider = computed(
  () => ttsForm.value.provider === 'piper',
)
// 已启用交叉音色但当前引擎可选音色不足 2 个时告警，避免保存后静默 no-op
const crossVoiceInsufficientForProvider = computed(() => {
  if (!ttsForm.value.cross_voice.enabled) return false
  if (ttsForm.value.provider === 'piper') return false
  return (currentCrossVoiceList.value || []).length < 2
})

// 试音相关状态
const previewText = ref('大家好，欢迎收听今日新闻早报。以下是本期为您精选的头条资讯。')
const previewing = ref(false)
const previewAudioUrl = ref('')

// TTS 模型下载（Kokoro/Piper 本地离线引擎）状态
const downloadingTts = ref(false)
const ttsDownloadStatus = ref(null)
let ttsDownloadTimer = null

// 下载进度百分比（仅下载中展示）
const downloadPercent = computed(() => {
  const s = ttsDownloadStatus.value
  if (s && s.status === 'downloading' && s.progress != null) {
    return Math.round(s.progress * 100)
  }
  return null
})

// 停止进度轮询
function stopDownloadPolling() {
  if (ttsDownloadTimer) {
    clearInterval(ttsDownloadTimer)
    ttsDownloadTimer = null
  }
}

// 触发下载并轮询进度
async function handleDownloadTtsModels() {
  const f = ttsForm.value
  if (f.provider !== 'kokoro' && f.provider !== 'piper') {
    ElMessage.info('该 TTS 引擎无需下载模型')
    return
  }
  downloadingTts.value = true
  ttsDownloadStatus.value = { status: 'downloading', message: '正在启动下载...', progress: 0 }

  const payload = { provider: f.provider }
  if (f.provider === 'kokoro') {
    payload.kokoro_lang = f.kokoro_lang
    payload.kokoro_voice = f.kokoro_voice
  } else {
    payload.piper_voice = f.piper_voice
    payload.piper_voice_dir = f.piper_voice_dir
  }

  try {
    await api.post('/ai/download-tts-models', payload)
  } catch (e) {
    downloadingTts.value = false
    ttsDownloadStatus.value = {
      status: 'failed',
      message: e.response?.data?.message || e.message || '启动下载失败',
    }
    return
  }

  // 启动后轮询状态（2s），直到 success/failed
  stopDownloadPolling()
  ttsDownloadTimer = setInterval(async () => {
    try {
      const st = await api.get('/ai/download-tts-models/status', {
        params: { provider: f.provider },
        silent: true,
      })
      ttsDownloadStatus.value = st
      if (st.status === 'success' || st.status === 'failed') {
        stopDownloadPolling()
        downloadingTts.value = false
        if (st.status === 'success') {
          ElMessage.success('TTS 模型下载完成')
        } else {
          ElMessage.error(st.message || 'TTS 模型下载失败')
        }
      }
    } catch (e) {
      // 轮询静默失败：继续下一次轮询，不阻断用户操作
      if (e.response?.status === 401) {
        stopDownloadPolling()
        downloadingTts.value = false
      }
    }
  }, 2000)
}

// 用量统计
const usageLoading = ref(false)
const todayUsage = ref({
  llm_calls: 0,
  llm_tokens: 0,
  tts_calls: 0,
  tts_chars: 0,
  cost_usd: 0,
})
const usageTrend = ref([])

// 当前选中的预设（用于显示 API Key 获取链接）
const currentPreset = computed(() =>
  presets.value.find((p) => p.key === selectedPreset.value)
)

// Edge-TTS 语速百分比（-50 ~ 100，对应 0.5x ~ 2.0x）
// 后端 edge_rate 字符串格式 "+50%" / "-10%" / ""
const edgeRatePercent = computed({
  get() {
    const s = (ttsForm.value.edge_rate || '').toString().trim().replace('%', '').replace('+', '')
    const n = parseFloat(s)
    return isNaN(n) ? 0 : n
  },
  set(val) {
    // 0 视为无调整（后端 _normalize_edge_adjustment 会把 0 转为空字符串）
    ttsForm.value.edge_rate = val === 0 ? '' : (val > 0 ? `+${val}%` : `${val}%`)
  }
})

// 字数反算：总字数 = 目标时长 × 210 × 倍率 / 60
const calculatedWords = computed(() => {
  const rate = edgeRatePercent.value / 100 + 1
  return Math.round(llmForm.value.target_duration_sec * 210 * rate / 60)
})

// 段数：clamp(round((总字数 - 145) / 350), 3, 6)
const calculatedSegments = computed(() => {
  const body = Math.max(300, calculatedWords.value - 145)
  return Math.max(3, Math.min(6, Math.round(body / 350)))
})

// 每段字数
const calculatedWordsPerSeg = computed(() => {
  const body = Math.max(300, calculatedWords.value - 145)
  return Math.max(200, Math.round(body / calculatedSegments.value))
})

// 加载配置
async function loadConfig() {
  loading.value = true
  try {
    const [configData, presetData] = await Promise.all([
      api.get('/ai/config'),
      api.get('/ai/presets'),
    ])
    // 填充 LLM 配置
    if (configData.llm) {
      Object.assign(llmForm.value, configData.llm)
      // 加载每个预设独立保存的配置（API Key 脱敏）
      presetConfigs.value = configData.llm.preset_configs || {}
      // 优先使用后端根据 base_url 反向匹配的 selected_preset
      if (configData.llm.selected_preset) {
        selectedPreset.value = configData.llm.selected_preset
      }
    }
    // 填充 TTS 配置
    if (configData.tts) {
      Object.assign(ttsForm.value, configData.tts)
    }
    presets.value = presetData || []
    // 音色列表按当前 provider 加载（不同 provider 音色 ID 体系不同）
    await loadVoices(ttsForm.value.provider)
    // 兜底：后端未返回 selected_preset 时根据 base_url 自动匹配
    if (!selectedPreset.value && llmForm.value.base_url) {
      const matched = presets.value.find((p) => p.base_url === llmForm.value.base_url)
      if (matched) selectedPreset.value = matched.key
    }
  } catch (e) {
    // 拦截器已弹出错误提示；此处兜底，防止 Promise 拒绝冒泡为 uncaught rejection
  } finally {
    loading.value = false
  }
}

// 按 provider 加载音色列表
async function loadVoices(provider) {
  try {
    voices.value = await api.get('/ai/voices', { params: { provider } }) || []
  } catch (e) {
    voices.value = []
  }
}

// 切换 TTS Provider：重新加载音色列表并清空测试结果
async function handleProviderChange(provider) {
  ttsTestResult.value = null
  // 清空下载状态与轮询，避免跨引擎显示错误状态
  stopDownloadPolling()
  downloadingTts.value = false
  ttsDownloadStatus.value = null
  // 清空试音音频，避免切换 provider 后播放上一个引擎的音频
  if (previewAudioUrl.value) {
    URL.revokeObjectURL(previewAudioUrl.value)
    previewAudioUrl.value = ''
  }
  await loadVoices(provider)
}

// 应用预设：切换预设时返显之前保存的配置（API Key/Base URL/Model）
function applyPreset(key) {
  const preset = presets.value.find((p) => p.key === key)
  if (!preset) return
  selectedPreset.value = key
  // 优先使用该预设之前保存的配置，未保存过则用预设默认值
  const saved = presetConfigs.value[key]
  if (saved) {
    llmForm.value.api_key = saved.api_key || ''
    llmForm.value.base_url = saved.base_url || preset.base_url
    llmForm.value.model = saved.model || preset.model
  } else {
    // 未保存过的预设：清空 API Key，使用预设默认 base_url 和 model
    llmForm.value.api_key = ''
    llmForm.value.base_url = preset.base_url
    llmForm.value.model = preset.model
  }
}

// 保存配置
async function handleSave() {
  saving.value = true
  try {
    await api.put('/ai/config', {
      llm: llmForm.value,
      tts: ttsForm.value,
      selected_preset: selectedPreset.value,
    })
    ElMessage.success('配置已保存并热更新')
    // 保存后重新加载配置，刷新 presetConfigs 中的脱敏值
    await loadConfig()
    saving.value = false
  } catch (e) {
    // 拦截器已弹出错误提示；兜底重置保存按钮 loading 态，避免界面卡死
    saving.value = false
  } finally {
    loading.value = false
  }
}

// 恢复初始配置：清空所有预设配置和当前 LLM 配置，回退到出厂默认值
async function handleResetConfig() {
  try {
    await ElMessageBox.confirm(
      '确认恢复 LLM 初始配置？将清空所有预设的已保存配置（API Key/Base URL/Model）和当前 LLM 配置，此操作不可恢复。',
      '恢复初始配置',
      { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' }
    )
  } catch {
    return // 用户取消
  }

  resetting.value = true
  try {
    const data = await api.post('/ai/reset-config')
    // 用后端返回的重置后配置刷新表单
    if (data?.llm) {
      llmForm.value.api_key = data.llm.api_key || ''
      llmForm.value.base_url = data.llm.base_url || ''
      llmForm.value.model = data.llm.model || ''
    }
    // 清空预设配置缓存和选中状态
    presetConfigs.value = {}
    selectedPreset.value = ''
    llmTestResult.value = null
    ElMessage.success('LLM 配置已恢复初始状态')
    resetting.value = false
  } finally {
    loading.value = false
  }
}

// 测试 LLM 连接
async function handleTestLLM() {
  testingLlm.value = true
  llmTestResult.value = null
  try {
    const data = await api.post('/ai/test-llm', {
      base_url: llmForm.value.base_url,
      api_key: llmForm.value.api_key,
      model: llmForm.value.model,
    })
    llmTestResult.value = data
    testingLlm.value = false
  } finally {
    loading.value = false
  }
}

// 测试 TTS 连接（按 provider 传递对应字段）
async function handleTestTTS() {
  testingTts.value = true
  ttsTestResult.value = null
  try {
    const f = ttsForm.value
    const payload = { provider: f.provider }
    // 按 provider 附加对应字段，避免传无关字段干扰
    if (f.provider === 'aliyun') {
      payload.api_key = f.api_key
      payload.appkey = f.appkey
    } else if (f.provider === 'edge') {
      payload.edge_voice = f.edge_voice
    } else if (f.provider === 'tencent') {
      payload.tencent_secret_id = f.tencent_secret_id
      payload.tencent_secret_key = f.tencent_secret_key
      payload.tencent_region = f.tencent_region
      payload.tencent_voice_type = f.tencent_voice_type
    } else if (f.provider === 'kokoro') {
      payload.kokoro_lang = f.kokoro_lang
      payload.kokoro_voice = f.kokoro_voice
    } else if (f.provider === 'piper') {
      payload.piper_voice = f.piper_voice
      payload.piper_voice_dir = f.piper_voice_dir
    }
    const data = await api.post('/ai/test-tts', payload)
    ttsTestResult.value = data
    testingTts.value = false
  } catch (e) {
    ttsTestResult.value = { success: false, message: e.response?.data?.message || e.message || '连接测试失败' }
    testingTts.value = false
  } finally {
    loading.value = false
  }
}

// 应用 TTS 风格预设：按当前 provider 将预设参数填入表单
function applyTtsPreset(preset) {
  const f = ttsForm.value
  if (f.provider === 'edge') {
    // Edge-TTS rate/volume/pitch 为百分比字符串，0 视为无调整（空字符串）
    f.edge_rate = preset.rate === 0 ? '' : (preset.rate > 0 ? `+${preset.rate}%` : `${preset.rate}%`)
    f.edge_volume = preset.volume === 0 ? '' : (preset.volume > 0 ? `+${preset.volume}%` : `${preset.volume}%`)
    f.edge_pitch = preset.pitch === 0 ? '' : (preset.pitch > 0 ? `+${preset.pitch}Hz` : `${preset.pitch}Hz`)
  } else if (f.provider === 'tencent') {
    f.tencent_volume = preset.volume
    f.tencent_speed = preset.speed
  } else if (f.provider === 'aliyun') {
    f.aliyun_volume = preset.volume
    f.aliyun_speech_rate = preset.speech_rate
    f.aliyun_pitch_rate = preset.pitch_rate
  } else if (f.provider === 'kokoro') {
    f.kokoro_speed = preset.speed
  } else if (f.provider === 'piper') {
    f.piper_length_scale = preset.length_scale
  }
  ElMessage.success(`已应用「${preset.name}」预设，点击试音听效果`)
}

// 试音：用当前表单参数合成测试文本，返回音频后播放
async function handlePreviewTTS() {
  if (!previewText.value.trim()) {
    ElMessage.warning('请输入试音文本')
    return
  }
  previewing.value = true
  // 清空旧音频 URL，避免播放上一次的音频
  if (previewAudioUrl.value) {
    URL.revokeObjectURL(previewAudioUrl.value)
    previewAudioUrl.value = ''
  }
  try {
    const f = ttsForm.value
    const payload = {
      provider: f.provider,
      text: previewText.value,
    }
    // 按 provider 附加当前表单参数，使试音使用未保存的临时值
    if (f.provider === 'aliyun') {
      payload.aliyun_api_key = f.api_key
      payload.aliyun_appkey = f.appkey
      payload.aliyun_voice = f.voice
      payload.aliyun_volume = f.aliyun_volume
      payload.aliyun_speech_rate = f.aliyun_speech_rate
      payload.aliyun_pitch_rate = f.aliyun_pitch_rate
    } else if (f.provider === 'edge') {
      payload.edge_voice = f.edge_voice
      payload.edge_rate = f.edge_rate
      payload.edge_volume = f.edge_volume
      payload.edge_pitch = f.edge_pitch
    } else if (f.provider === 'tencent') {
      payload.tencent_secret_id = f.tencent_secret_id
      payload.tencent_secret_key = f.tencent_secret_key
      payload.tencent_region = f.tencent_region
      payload.tencent_voice_type = f.tencent_voice_type
      payload.tencent_volume = f.tencent_volume
      payload.tencent_speed = f.tencent_speed
    } else if (f.provider === 'kokoro') {
      payload.kokoro_lang = f.kokoro_lang
      payload.kokoro_voice = f.kokoro_voice
      payload.kokoro_speed = f.kokoro_speed
    } else if (f.provider === 'piper') {
      payload.piper_voice = f.piper_voice
      payload.piper_voice_dir = f.piper_voice_dir
      payload.piper_length_scale = f.piper_length_scale
      payload.piper_volume = f.piper_volume
      payload.piper_noise_scale = f.piper_noise_scale
    }
    const blob = await api.post('/ai/preview-tts', payload, {
      responseType: 'blob',
      timeout: 60000,
      silent: true,
    })
    previewAudioUrl.value = URL.createObjectURL(blob)
    ElMessage.success('试音合成成功')
  } catch (e) {
    // axios blob 错误响应需手动解析 JSON，否则只拿到 Blob 对象无法读取 message
    if (e.response?.data instanceof Blob) {
      try {
        const text = await e.response.data.text()
        const errData = JSON.parse(text)
        ElMessage.error(errData.message || '试音失败')
      } catch {
        ElMessage.error('试音失败')
      }
    } else if (e.response?.status === 401) {
      ElMessage.error('登录已过期，请重新登录')
    } else {
      ElMessage.error(e.message || '试音失败')
    }
  } finally {
    previewing.value = false
  }
}

// 加载用量统计
async function loadUsage() {
  usageLoading.value = true
  try {
    const data = await api.get('/ai/usage')
    todayUsage.value = data.today || todayUsage.value
    usageTrend.value = data.trend || []
    usageLoading.value = false
  } finally {
    loading.value = false
  }
}

// 切换 Tab 时加载对应数据
function handleTabChange(tab) {
  if (tab === 'usage' && usageTrend.value.length === 0) {
    loadUsage()
  }
}

// 从参数计算器同步配置：读取 query 中的 duration 和 rate，映射到表单字段
function applyCalculatorParams() {
  const { duration, rate } = route.query
  let applied = []

  if (duration !== undefined) {
    const sec = parseInt(duration, 10)
    if (!isNaN(sec)) {
      // clamp 到滑块范围 180-1200
      llmForm.value.target_duration_sec = Math.max(180, Math.min(1200, sec))
      applied.push('目标时长')
    }
  }

  if (rate !== undefined) {
    const rateVal = parseFloat(rate)
    if (!isNaN(rateVal)) {
      // rateMultiplier → edge_rate 字符串：1.5 → "+50%", 0.8 → "-20%", 1.0 → ""
      const percent = Math.round((rateVal - 1) * 100)
      ttsForm.value.edge_rate = percent === 0 ? '' : (percent > 0 ? `+${percent}%` : `${percent}%`)
      applied.push('语速倍率')
    }
  }

  if (applied.length > 0) {
    ElMessage.info(`已从参数计算器同步：${applied.join('、')}，请点击保存配置持久化`)
  }

  // 清除 query 参数，避免刷新页面时重复应用
  router.replace({ path: route.path })
}

onMounted(async () => {
  try {
    await loadConfig()
  } catch (e) {
    // loadConfig 内部已兜底，这里防止 onMounted 异步异常冒泡为 uncaught rejection
  }
  applyCalculatorParams()
})

onUnmounted(() => {
  stopDownloadPolling()
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.ai-config {
  .top-bar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .config-tabs {
    :deep(.el-tabs__item) {
      font-size: 15px;
    }
  }

  .preset-section {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid $color-border;

    .section-label {
      font-size: 14px;
      color: $color-text-secondary;
      margin-right: 8px;
    }
  }

  .config-form {
    max-width: 600px;

    .field-tip {
      font-size: 12px;
      color: $color-text-secondary;
      line-height: 1.5;
      margin-top: 4px;
    }
  }

  .preview-section {
    margin-top: 16px;
    padding: 16px;
    background: $color-bg-card;
    border: 1px solid $color-border;
    border-radius: $radius-md;
  }

  .usage-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
  }

  .usage-card {
    background: $color-bg-card;
    border: 1px solid $color-border;
    border-radius: $radius-md;
    padding: 20px;
    text-align: center;
    transition: box-shadow 0.2s;

    &:hover {
      box-shadow: $shadow-md;
    }

    &.highlight {
      background: linear-gradient(135deg, $color-primary-light, $color-primary);
      border-color: $color-primary;

      .usage-value {
        color: #fff;
      }

      .usage-label {
        color: rgba(255, 255, 255, 0.9);
      }
    }

    .usage-value {
      font-size: 28px;
      font-weight: 700;
      color: $color-primary-dark;
      margin-bottom: 8px;
    }

    .usage-label {
      font-size: 13px;
      color: $color-text-secondary;
    }
  }
}
</style>
