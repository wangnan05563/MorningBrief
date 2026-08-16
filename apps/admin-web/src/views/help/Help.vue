<template>
  <div class="page-container help-page">
    <!-- 文档头部 -->
    <div class="card-soft header-card">
      <div class="header-row">
        <el-icon class="header-icon"><Promotion /></el-icon>
        <div class="header-text">
          <h2 class="header-title">MorningBrief 使用文档</h2>
          <p class="header-desc">
            系统涵盖 RSS 抓取、LLM 改写、TTS 合成、音频拼接、审核发布、小程序播放全流程。
            本文档详细介绍各功能模块的使用方法，包括核心功能、操作步骤、使用场景、参数配置和注意事项。
          </p>
        </div>
        <el-button type="primary" plain :icon="Document" @click="openApiDocs">
          API 文档
        </el-button>
      </div>
    </div>

    <!-- 搜索 + 章节导航 -->
    <div class="layout-row">
      <div class="card-soft sidebar-card">
        <div class="sidebar-title">文档目录</div>
        <el-input
          v-model="search"
          placeholder="搜索章节..."
          size="small"
          :prefix-icon="Search"
          clearable
          style="margin: 8px 0 12px"
        />
        <div class="anchor-list">
          <a
            v-for="s in filteredSections"
            :key="s.id"
            :href="`#${s.id}`"
            class="anchor-item"
            :class="{ active: activeSection === s.id }"
            @click.prevent="scrollToSection(s.id)"
          >
            <el-icon class="anchor-icon"><component :is="s.icon" /></el-icon>
            <span class="anchor-text">{{ s.title }}</span>
          </a>
        </div>
      </div>

      <div class="content-area">
        <div
          v-for="section in filteredSections"
          :key="section.id"
          :id="section.id"
          class="card-soft section-card"
        >
          <div class="section-header">
            <el-icon class="section-icon"><component :is="section.icon" /></el-icon>
            <h3 class="section-title">{{ section.title }}</h3>
          </div>
          <p class="section-intro">{{ section.intro }}</p>
          <el-divider />

          <div v-for="block in section.blocks" :key="block.title" class="block">
            <div class="block-title">
              <el-icon class="block-icon">
                <component :is="getBlockIcon(block.type)" />
              </el-icon>
              <span>{{ block.title }}</span>
            </div>
            <div class="block-content">
              <p v-if="block.type === 'feature'" class="block-text">{{ block.content }}</p>
              <ol v-else-if="block.type === 'steps'" class="step-list">
                <li v-for="(step, i) in block.content" :key="i">{{ step }}</li>
              </ol>
              <p v-else-if="block.type === 'scenario'" class="block-text">{{ block.content }}</p>
              <div v-else-if="block.type === 'config'" class="config-table-wrap">
                <table class="config-table">
                  <thead>
                    <tr>
                      <th>参数</th>
                      <th>示例</th>
                      <th>说明</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, i) in block.content" :key="i">
                      <td><code>{{ row[0] }}</code></td>
                      <td class="text-muted">{{ row[1] }}</td>
                      <td class="text-muted">{{ row[2] }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <el-alert
                v-else-if="block.type === 'note'"
                :type="block.noteType || 'info'"
                :closable="false"
                show-icon
              >
                {{ block.content }}
              </el-alert>
            </div>
          </div>
        </div>

        <div v-if="filteredSections.length === 0" class="empty-state">
          未找到匹配的章节
        </div>

        <div class="footer-text">
          <el-divider />
          <span>MorningBrief · 帮助文档</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, markRaw } from 'vue'
import {
  Promotion, Document, Search, Aim, CircleCheck, Warning,
  Setting, MagicStick, DataLine, List, Picture, Bell, Cpu, Coin,
  Brush, Connection, Monitor, Operation, Menu, Calendar,
} from '@element-plus/icons-vue'

const search = ref('')
const activeSection = ref('quickstart')

// 块类型 → 图标映射
const blockIconMap = {
  feature: markRaw(Aim),
  steps: markRaw(CircleCheck),
  scenario: markRaw(MagicStick),
  config: markRaw(Setting),
  note: markRaw(Warning),
}

function getBlockIcon(type) {
  return blockIconMap[type] || Aim
}

// 完整文档章节：按业务模块顺序组织
// 块类型：feature（核心功能）/ steps（操作步骤）/ scenario（使用场景）/ config（参数配置）/ note（注意事项）
const docSections = [
  {
    id: 'quickstart',
    title: '快速开始',
    icon: markRaw(MagicStick),
    intro: '从安装到首次跑通工作流的完整流程，新用户必读。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: 'MorningBrief 是 AI 驱动的语音新闻播报平台，支持 RSS 自动抓取、LLM 智能改写、TTS 语音合成、音频拼接发布、小程序播放等完整能力，提供运营后台与微信小程序双端。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '安装依赖：pip install -r backend/requirements.txt',
          '复制配置：copy backend/.env.example backend/.env，填入 LLM API Key、TTS 配置、COS 凭证',
          '启动服务：双击 启动服务.bat 或 python backend/launcher.py',
          '访问运营后台：浏览器打开 http://127.0.0.1:8000/，默认账号 admin / admin123',
          '配置频道：在「频道管理」页面设置 RSS 源、关键词、调度时间',
          '创建工作流：在「工作流监控」页面新建工作流，关联频道',
          '审核内容：在「内容审核」页面审核 LLM 改写后的稿件',
          '发布音频：审核通过后自动合成 TTS 并发布到小程序',
        ],
      },
      {
        type: 'scenario',
        title: '使用场景',
        content: '刚部署完系统，需要从零开始配置并跑通第一个新闻播报工作流。',
      },
      {
        type: 'note',
        title: '注意事项',
        content: '首次启动自动 seed 默认 admin 账户（admin/admin123），生产环境请立即修改密码。LLM/TTS API Key 必填，否则工作流会在对应步骤失败。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'review',
    title: '内容审核',
    icon: markRaw(Document),
    intro: '审核 LLM 改写后的稿件，决定是否进入 TTS 合成流程。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '展示待审核稿件列表，支持查看原文、改写稿、热力评分；审核通过后自动触发 TTS 合成与音频拼接，审核驳回则记录原因并通知运营。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「内容审核」页面查看待审核列表',
          '点击稿件标题进入审核详情页',
          '对比原文与改写稿，查看 LLM 改写质量',
          '查看热力评分（关键词密度、可读性、敏感词检测）',
          '通过：点击「审核通过」，进入 TTS 合成队列',
          '驳回：点击「驳回」，填写驳回原因',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '审核操作会触发后续工作流，请确认稿件内容无误后再通过。敏感词检测命中时会在卡片上以红色标签提示。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'ads',
    title: '广告管理',
    icon: markRaw(Picture),
    intro: '管理广告素材、投放规则与排期。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '支持上传音频/图片广告素材、配置投放规则（按频道、时段、频次）、可视化排期日历查看本周/本月投放计划。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '在「广告素材」页面上传广告音频/图片',
          '在「投放规则」页面配置投放条件（频道、时段、频次）',
          '在「排期日历」页面查看与调整投放计划',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '广告素材大小限制 10MB；排期冲突时系统会自动提示并拒绝保存。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'stats',
    title: '数据统计',
    icon: markRaw(DataLine),
    intro: '查看播放量、DAU、完播率等核心指标及趋势。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '提供当日核心指标看板（DAU、播放量、完播率、收藏数、反馈数）、7 天/30 天趋势图、按日期切换的历史数据查询。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「数据统计」页面',
          '通过顶部日期选择器切换查询日期',
          '查看 5 个核心指标卡片',
          '在趋势图区切换指标（DAU/播放量/完播率）与时间范围（7 天/30 天）',
        ],
      },
    ],
  },
  {
    id: 'channels',
    title: '频道管理',
    icon: markRaw(Menu),
    intro: '配置新闻频道、RSS 源、关键词、调度时间与 LLM 提示词。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '每个频道独立配置 RSS 源、关键词、调度时间、开场/结尾/约束提示词、BGM、TTS 音色，实现频道级内容隔离与个性化播报风格。',
      },
      {
        type: 'config',
        title: '参数配置',
        content: [
          ['rss_sources', '["人民网-时政","新华社"]', 'RSS 源 JSON 数组，name 必须与 rss.yaml 一致'],
          ['keywords', '人工智能,芯片', '标题关键词，逗号分隔，匹配则采集'],
          ['schedule_time', '"08:00"', '每日调度时间（HH:MM），留空则不自动调度'],
          ['intro_prompt', '"欢迎收听..."', '开场白提示词模板'],
          ['outro_prompt', '"感谢收听..."', '结尾提示词模板'],
          ['bgm_path', 'preset/tech_news_intro.mp3', '频道 BGM 路径'],
          ['bgm_volume', '0.15', 'BGM 音量（0-1）'],
          ['segment_gap_sec', '0.5', '段落间隔秒数'],
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '修改 RSS 源 name 后必须同步 rss.yaml，否则 crawler 找不到源返回 0 条素材。专门频道（channel_id 非空）严格按频道过滤，不会消费全局素材池。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'queue',
    title: '队列管理',
    icon: markRaw(Operation),
    intro: '查看 TTS 合成队列与音频拼接队列状态。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '展示 TTS 合成队列与音频拼接队列的待处理、处理中、完成、失败数量；支持手动重试失败任务、清空已完成任务。',
      },
    ],
  },
  {
    id: 'workflows',
    title: '工作流监控',
    icon: markRaw(Monitor),
    intro: '查看工作流执行状态、步骤进度与日志。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '工作流按状态（pending/running/success/failed/cancelled）分类展示；点击进入详情页可查看每个步骤（爬取/改写/审核/TTS/拼接/发布）的执行情况、耗时、日志、错误信息。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「工作流监控」页面查看工作流列表',
          '按状态、频道、日期筛选',
          '点击工作流 ID 进入详情页',
          '查看步骤进度条与每步日志',
          '失败工作流可点击「重试」从失败步骤恢复',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '工作流 ID 由数据库当日最大序号生成，服务重启后会自动校正 TTLCache 计数器。仅 admin 角色可访问此页面。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'tunnel',
    title: '内网穿透',
    icon: markRaw(Connection),
    intro: '通过 cloudflared/cpolar 暴露本地服务到公网，便于小程序真机测试。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '集成 cloudflared 与 cpolar 两种隧道方案，一键启动/停止；支持自动启动、URL 复制、启动通知。',
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'cloudflared 隧道为临时 URL，重启后变化；cpolar 需配置 authtoken。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'ai-config',
    title: 'AI 服务',
    icon: markRaw(Cpu),
    intro: '配置 LLM 与 TTS 服务商、API Key、模型、预算等。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '支持 LLM（通义千问 OpenAI 兼容）与 TTS（阿里云 NLS / Edge-TTS / 腾讯云）多 provider 配置；AI 预算限流 60 次/分钟/服务类型；前端修改后热生效无需重启。',
      },
      {
        type: 'config',
        title: '参数配置',
        content: [
          ['LLM_API_KEY', 'sk-...', '通义千问 API Key'],
          ['LLM_MODEL', 'qwen-max', '模型名称'],
          ['TTS_PROVIDER', 'aliyun', 'TTS 服务商：aliyun/edge/tencent'],
          ['ALIYUN_TTS_APPKEY', '...', '阿里云 NLS AppKey'],
          ['ALIYUN_TTS_API_KEY', 'AccessToken', '非 AccessKey Secret'],
          ['EDGE_TTS_VOICE', 'zh-CN-XiaoxiaoNeural', 'Edge-TTS 音色'],
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'TTS AccessToken 与 AccessKey Secret 不同，从 NLS 控制台获取。测试连接时若用脱敏值（****xxxx）会自动回退到真实 Key 测试。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'notification',
    title: '通知管理',
    icon: markRaw(Bell),
    intro: '配置钉钉/企微等通知渠道与事件订阅模板。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '支持钉钉、企业微信、邮件多渠道通知；事件订阅模板化（工作流成功/失败、隧道启动等）；预设模板首次启动自动 seed。',
      },
    ],
  },
  {
    id: 'tools',
    title: '参数计算器',
    icon: markRaw(Calendar),
    intro: '根据目标时长反推 LLM 字数与 TTS 语速参数。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '输入目标时长（分钟），自动计算 LLM 应生成字数（330 WPM 基线 ±10%）与 TTS 语速调节建议，避免后续拼接超时返工。',
      },
    ],
  },
  {
    id: 'db-admin',
    title: '数据库维护',
    icon: markRaw(Coin),
    intro: '在线查看/编辑 SQLite 数据库表数据。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '提供 20+ 业务表的在线 CRUD 操作，支持表结构查看、记录编辑、SQL 查询、CSV 导入导出；敏感字段（password/secret/token/key）自动脱敏；危险操作需 CONFIRM_DELETE 令牌双重确认。',
      },
      {
        type: 'note',
        title: '注意事项',
        content: '直接操作数据库有风险，建议先备份。表操作受白名单机制限制，仅允许操作配置中声明的表。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'maintenance',
    title: '系统清理',
    icon: markRaw(Brush),
    intro: '清理历史数据、缓存、日志，VACUUM 压缩 SQLite。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '三列清理卡片：缓存（TTLCache/pycache/临时文件）、数据库（黑名单/去重/AI 用量/播放日志/VACUUM）、日志（旧日志/大日志）；全部支持 dry_run 预览模式。',
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'VACUUM 会锁定数据库直到压缩完成，建议在低峰期执行。清理操作不可逆，建议先预览。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'cos-storage',
    title: '音频存储（COS）',
    icon: markRaw(Coin),
    intro: '配置腾讯云 COS 对象存储，加速小程序音频播放。生产环境强烈推荐。',
    blocks: [
      {
        type: 'feature',
        title: '为什么需要 COS',
        content: '未配置 COS 时，音频文件经 Tailscale Funnel 中转播放，受限于家庭宽带上行与公网中转延迟，首字播放延迟可达 300-1000ms。配置 COS 后音频直走腾讯云边缘节点，首字延迟降至 50-200ms，下载速度提升 5-10 倍，且不依赖用户电脑在线。',
      },
      {
        type: 'steps',
        title: '获取 COS 凭证步骤',
        content: [
          '注册腾讯云账号：访问 cloud.tencent.com，用微信扫码或手机号注册并完成实名认证（个人认证即可）',
          '开通对象存储：控制台搜索"对象存储" → 首次进入会提示开通（按用量计费，10GB 内约 1 元/月）',
          '创建存储桶：存储桶列表 → 创建存储桶，名称自定义（如 morningbrief-audio），地域选离你近的（如 ap-beijing/ap-shanghai），访问权限选"公有读私有写"',
          '获取 API 密钥：访问管理 → API 密钥管理（console.cloud.tencent.com/cam/capi）→ 新建密钥 → 复制 SecretId 和 SecretKey（SecretKey 只显示一次，请妥善保存）',
          '记录 Bucket 信息：存储桶详情页复制完整 Bucket 名称（格式：名称-appid，如 morningbrief-audio-1311027859）和所属地域（如 ap-beijing）',
        ],
      },
      {
        type: 'config',
        title: '.env 配置参数',
        content: [
          ['COS_SECRET_ID', 'AKIDxxxxxxxxxxxxxxxxxxxxxx', '访问管理 API 密钥 ID'],
          ['COS_SECRET_KEY', 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', '访问管理 API 密钥（保密，切勿泄露）'],
          ['COS_BUCKET', 'morningbrief-audio-1311027859', '存储桶完整名称（含 appid 后缀）'],
          ['COS_REGION', 'ap-beijing', '存储桶地域（创建时选择）'],
          ['COS_CDN_DOMAIN', '（留空）', 'CDN 加速域名，留空则用 COS 默认域名（已备案可直用）'],
        ],
      },
      {
        type: 'steps',
        title: '部署步骤',
        content: [
          '编辑 backend/.env：填入上述 5 个 COS 参数（COS_CDN_DOMAIN 留空即可）',
          '安装 COS SDK：pip install cos-python-sdk-v5',
          '验证凭证：python jmeter_test/verify_cos.py（自动上传测试文件 → 公网访问 → 清理）',
          '迁移历史音频：python jmeter_test/migrate_audio_to_cos.py（自动扫描 /audio/ 路径的 episode 并上传 COS）',
          '重启后端服务：执行 stop.ps1 → start.ps1',
          '配置小程序域名白名单：mp.weixin.qq.com → 开发管理 → 服务器域名 → downloadFile 合法域名 → 添加 https://<bucket>.cos.<region>.myqcloud.com',
          '真机验证：小程序播放任意节目，观察首字播放延迟应显著降低',
        ],
      },
      {
        type: 'scenario',
        title: '使用场景',
        content: '生产环境部署完成后，音频播放慢于局域网；或希望音频播放不依赖开发电脑在线。开发环境调试时可不配置 COS，音频走本地 /audio 路径即可。',
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'COS_CDN_DOMAIN 留空时会用 COS 默认域名（xxx.cos.xxx.myqcloud.com），该域名已备案可直用。若需自定义 CDN 域名（如 audio.example.com），需先注册域名并完成 ICP 备案（约 7-20 个工作日）。SecretKey 切勿提交到 Git 或泄露给前端。迁移脚本幂等可重复执行。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'about',
    title: '关于 / 版本信息',
    icon: markRaw(Promotion),
    intro: '系统元信息与文档资源统一入口。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '展示当前版本号、发布日期、Git SHA、Python 版本、平台；一键检查 GitHub 最新版本；汇总 8 项外部资源链接（用户协议、隐私条款、开源声明、帮助文档、API 文档、联系我们、官方社区、报告问题）；浏览 40+ 项前后端依赖的开源许可清单。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '点击侧边栏「关于」进入关于页面',
          '查看版本号、发布日期、Git SHA 等元信息',
          '点击「检查更新」按钮查询 GitHub 最新发布',
          '点击菜单列表项跳转外部资源或打开开源声明 Modal',
          '在 Modal 搜索框按包名/许可证过滤依赖',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '自动检查更新：进入页面 5 秒后首次检查，之后每 60 分钟检查一次；后端 5 分钟缓存避免触发 GitHub 限流。',
        noteType: 'warning',
      },
    ],
  },
]

// 搜索过滤：标题或简介包含关键词的章节保留
const filteredSections = computed(() => {
  if (!search.value.trim()) return docSections
  const kw = search.value.toLowerCase()
  return docSections.filter(
    (s) => s.title.toLowerCase().includes(kw) || s.intro.toLowerCase().includes(kw)
  )
})

function openApiDocs() {
  window.open('/docs', '_blank', 'noopener,noreferrer')
}

function scrollToSection(id) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    activeSection.value = id
  }
}

// 监听滚动更新高亮章节
let scrollContainer = null
function handleScroll() {
  if (!scrollContainer) return
  const scrollTop = scrollContainer.scrollTop
  // 找到当前可视区域顶部的章节
  for (const section of docSections) {
    const el = document.getElementById(section.id)
    if (el) {
      const rect = el.getBoundingClientRect()
      // 章节顶部距视口顶部 80px 内视为当前章节
      if (rect.top >= 0 && rect.top < 120) {
        activeSection.value = section.id
        break
      }
    }
  }
}

onMounted(() => {
  // 主内容滚动容器（el-main）
  scrollContainer = document.querySelector('.el-main')
  if (scrollContainer) {
    scrollContainer.addEventListener('scroll', handleScroll)
  }
})

onUnmounted(() => {
  if (scrollContainer) {
    scrollContainer.removeEventListener('scroll', handleScroll)
    scrollContainer = null
  }
})
</script>

<style scoped lang="scss">
@use '../../styles/variables.scss' as *;

.help-page {
  max-width: 1200px;
  margin: 0 auto;
}

.header-card {
  padding: 20px 24px;
  margin-bottom: 16px;
}

.header-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.header-icon {
  font-size: 32px;
  color: $color-primary-dark;
  flex-shrink: 0;
}

.header-text {
  flex: 1;
  min-width: 200px;

  .header-title {
    font-size: 20px;
    font-weight: 600;
    color: $color-text-primary;
    margin-bottom: 8px;
  }

  .header-desc {
    font-size: 13px;
    color: $color-text-secondary;
    line-height: 1.6;
  }
}

.layout-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.sidebar-card {
  width: 220px;
  flex-shrink: 0;
  padding: 16px;
  position: sticky;
  top: 0;

  .sidebar-title {
    font-size: 14px;
    font-weight: 600;
    color: $color-text-primary;
  }
}

.anchor-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.anchor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: $radius-sm;
  text-decoration: none;
  color: $color-text-primary;
  font-size: 13px;
  transition: background-color 120ms cubic-bezier(0.2, 0, 0, 1);

  .anchor-icon {
    font-size: 14px;
    color: $color-text-secondary;
  }

  &:hover {
    background: var(--color-primary-light);
  }

  &.active {
    background: var(--color-primary-light);
    color: $color-primary-dark;
    font-weight: 500;

    .anchor-icon {
      color: $color-primary-dark;
    }
  }
}

.content-area {
  flex: 1;
  min-width: 0;
}

.section-card {
  padding: 20px 24px;
  margin-bottom: 16px;
  scroll-margin-top: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;

  .section-icon {
    font-size: 22px;
    color: $color-primary-dark;
  }

  .section-title {
    font-size: 18px;
    font-weight: 600;
    color: $color-text-primary;
    margin: 0;
  }
}

.section-intro {
  font-size: 13px;
  color: $color-text-secondary;
  line-height: 1.6;
  margin-bottom: 16px;
}

.block {
  margin-bottom: 20px;

  &:last-child {
    margin-bottom: 0;
  }
}

.block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: $color-text-primary;
  margin-bottom: 8px;

  .block-icon {
    font-size: 16px;

    :deep(.bullet) {
      color: $color-primary-dark;
    }
  }
}

.block-content {
  padding-left: 22px;
}

.block-text {
  font-size: 13px;
  color: $color-text-secondary;
  line-height: 1.6;
}

.step-list {
  padding-left: 20px;
  font-size: 13px;
  color: $color-text-secondary;
  line-height: 1.8;
}

.config-table-wrap {
  overflow-x: auto;
}

.config-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;

  th {
    padding: 8px 12px;
    text-align: left;
    background: var(--color-primary-light);
    border-bottom: 1px solid $color-border;
    color: $color-text-primary;
    font-weight: 500;
  }

  td {
    padding: 8px 12px;
    border-bottom: 1px solid $color-border;

    code {
      padding: 2px 6px;
      border-radius: $radius-sm;
      background: var(--color-primary-light);
      color: $color-primary-dark;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 12px;
    }
  }
}

.text-muted {
  color: $color-text-secondary;
}

.empty-state {
  text-align: center;
  padding: 64px 16px;
  color: $color-text-secondary;
  font-size: 14px;
}

.footer-text {
  text-align: center;
  color: $color-text-secondary;
  font-size: 13px;
  padding-top: 16px;

  span {
    color: $color-text-secondary;
  }
}

@media (max-width: 992px) {
  .layout-row {
    flex-direction: column;
  }

  .sidebar-card {
    width: 100%;
    position: static;
  }
}
</style>
