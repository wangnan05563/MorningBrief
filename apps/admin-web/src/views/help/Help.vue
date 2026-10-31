<template>
  <div data-guide="help-page" class="page-container help-page">
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
        <!-- /about 是 admin 专属接口，运营角色点了只会得到「需要管理员权限」，故不显示入口 -->
        <IconButton
          v-if="userStore.role === 'admin'"
          type="primary"
          plain
          :icon="Document"
          label="API 文档"
          desc="打开后端 API 文档"
          @click="openApiDocs"
        />
      </div>
    </div>

    <!-- 搜索 + 章节导航 -->
    <div class="layout-row">
      <div data-guide="help-catalog" class="card-soft sidebar-card">
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

        <!-- T02502 / FR-UX-403：引导重放入口。
             首访引导只弹一次、且点「跳过」后不再弹（同一需求要求的行为），
             没有这个入口，用户想再看某个菜单的引导就只能清 localStorage。 -->
        <div data-guide="help-replay" class="replay-block">
          <div class="replay-head">
            <span class="replay-title">菜单引导重放</span>
            <IconButton
              link
              type="info"
              size="small"
              :icon="Delete"
              label="清除引导记录"
              desc="清除全部「已引导」记账，各菜单首访引导会恢复"
              @click="resetGuideRecords"
            />
          </div>
          <div class="replay-list">
            <button
              v-for="g in replayableMenus"
              :key="g.path"
              type="button"
              class="replay-chip"
              :aria-label="`播放「${g.title}」引导`"
              @click="playGuide(g.path)"
            >
              {{ g.title }}
              <el-icon v-if="g.done" class="replay-done"><Check /></el-icon>
            </button>
          </div>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, notifyErrorOnce } from '../../utils/message'
import {
  Promotion, Document, Search, Aim, CircleCheck, Warning,
  Setting, MagicStick, DataLine, List, Picture, Bell, Cpu, Coin,
  Brush, Connection, Monitor, Operation, Menu, Calendar, Delete, Check,
} from '@element-plus/icons-vue'
import IconButton from '../../components/IconButton.vue'
import { useUserStore } from '../../stores/user'
import { useGuide } from '../../guide/useGuide'
import { GUIDE_STEPS } from '../../guide/guideConfig'
import { getAbout } from '../../api/about'
import { API_DOCS_PATH } from '../../utils/appPath'
import { filterHelpSections } from '../../utils/helpSearch'

const router = useRouter()
const userStore = useUserStore()
const guide = useGuide()

// 菜单引导重放（T02502 / FR-UX-403）：清单来自 GUIDE_STEPS 的键，
// 标题走 router.resolve 取路由 meta.title——菜单口径的唯一事实源仍是路由（FR-UX-401），
// 这里不另写一份菜单名，免得两处漂移。
const replayableMenus = computed(() =>
  Object.keys(GUIDE_STEPS)
    .filter((path) => path !== '/help')
    .map((path) => ({ path, meta: router.resolve(path).meta || {} }))
    // 与侧栏同一可见性口径（Layout.vue menuGroups）：requireRole=admin 的菜单对运营角色进不去，
    // 放进来点了只会被路由守卫弹回，引导永远弹不出来
    .filter(({ meta }) => !(meta.requireRole === 'admin' && userStore.role !== 'admin'))
    .map(({ path, meta }) => ({ path, title: meta.title || path, done: guide.isDone(path) })),
)

function playGuide(path) {
  // 重放前撤销「已引导」记账：否则落地后 maybeGuide 见 isDone 为真就不会再弹
  guide.markUndone(path)
  guide.requestReplay(path)
  router.push(path)
}

async function resetGuideRecords() {
  // 与全站一致走 ElMessageBox（Layout.vue 退出登录同款），不用 window.confirm
  try {
    await ElMessageBox.confirm('清除全部菜单的「已引导」记账？各菜单的首访引导会恢复。', '清除引导记录', {
      type: 'warning',
      confirmButtonText: '确认清除',
    })
  } catch {
    return // 取消：safeElMessageBox 被阻断时也走这里，不产生副作用
  }
  for (const m of replayableMenus.value) guide.markUndone(m.path)
  guide.markUndone('/help')
  ElMessage.success('已清除引导记录，重新进入各菜单会再次引导')
}

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
    // 跨页章节：本节讲的是从零跑通全流程，没有单一对应页面
    routes: [],
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
          '启动服务：双击 scripts/启动服务.bat 或 python backend/launcher.py',
          '访问运营后台：浏览器打开 http://127.0.0.1:8000/，账号 admin，初始口令取 .env 的 ADMIN_INITIAL_PASSWORD（留空为 admin123）',
          '配置频道：在「频道管理」页面设置 RSS 源、关键词、调度时间',
          '创建工作流：在「工作流监控」页面新建工作流，关联频道',
          '审核内容：在「内容审核」页面审核工作流产出的稿件',
          '发布音频：审核通过后节目立即发布，音频由小程序播放',
          '移动端访问：同一地址的 /m 路径可使用审批与管理快捷入口，账号与 PC 相同',
          '修改口令：登录后从右上角用户菜单「修改密码」更换，新口令至少 8 位',
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
        content: '首次启动自动 seed 默认 admin 账户，口令取 .env 的 ADMIN_INITIAL_PASSWORD，留空为 admin123；只在库里还没有 admin 时生效。登录后可在右上角用户菜单「修改密码」更换口令（新口令至少 8 位），改完需用新口令重新登录。LLM/TTS API Key 必填，否则工作流会在对应步骤失败。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'help-usage',
    routes: ['/help'],
    title: '帮助文档使用',
    icon: markRaw(Search),
    intro: '检索文档内容、跳转章节，或重放各菜单的首访引导。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '左侧「文档目录」按业务模块列出全部章节，点击即跳到对应位置；搜索框会匹配章节标题、简介与正文，包括操作步骤、参数表和注意事项。页面滚动时目录会高亮当前章节。侧栏底部还有「菜单引导重放」，可逐个重放菜单首访引导。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '在左侧搜索框输入关键词，目录与正文会同步过滤',
          '点目录中的章节名跳转到对应位置',
          '想再看某个菜单的引导时，在「菜单引导重放」点对应菜单名，页面会跳转并重新播放',
          '点「清除引导记录」可恢复所有菜单的首访提示',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '重放列表只包含配了引导步骤、且当前账号有权限访问的菜单，帮助页自身不在列表内；已引导过的菜单会显示勾选标记。搜索无结果时会显示「未找到匹配的章节」。',
        noteType: 'info',
      },
    ],
  },
  {
    id: 'review',
    routes: ['/review', '/review/:id'],
    title: '内容审核',
    icon: markRaw(Document),
    intro: '审核工作流产出的稿件，决定是否发布上线。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '展示待审核稿件列表，支持查看原文、改写稿、热力评分；稿件由工作流按「爬虫采集 → LLM 改写 → 质量审核 → 语音合成 → 音频拼接 → 创建审核」产出，审核通过后节目立即发布，打回则记录原因并退回改写。列表分「待审核」「已通过」「已打回」三个页签，「已通过」页签下可切换「仅已通过 / 仅已替换」子筛选；支持按工作流 ID、审核人、节目日期区间、频道四类条件定位。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「内容审核」页面，先选页签（待审核 / 已通过 / 已打回）',
          '需要定位时填写工作流 ID、审核人、节目日期或频道；筛选条件会写入地址栏，刷新与分享不丢',
          '点击稿件标题进入审核详情页',
          '对比原文与改写稿，查看 LLM 改写质量',
          '查看热力评分（关键词密度、可读性、敏感词检测）',
          '通过：在「审核操作」里选 通过，点「提交」，节目立即自动发布',
          '打回：选 打回 并填写理由，点「提交」；界面动作名是「打回」而非「驳回」',
          '替换段落：选 替换段落 → 选择段落 → 填写理由 → 点「提交」（该记录状态变为 replaced，可在「已通过」页签的「仅已替换」子筛选里查看）',
          '提交前会弹出确认，写明本次动作的影响（通过=立即发布、打回=退回改写、替换=按段重提）；提交后无法在本页撤销',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '审核操作会触发后续工作流，请确认稿件内容无误后再通过。敏感词检测命中时会在卡片上以红色标签提示。地址栏参数非法时，列表顶部会提示「链接里的参数已修正」并回落到默认值。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'ads',
    routes: ['/ads/materials', '/ads/placements', '/ads/schedule'],
    title: '广告管理',
    icon: markRaw(Picture),
    intro: '管理广告素材、投放规则与排期。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '登记音频素材（名称、描述、素材 URL、时长；页面不提供文件上传）；投放规则按广告位（开头/中间/结尾）与生效日期区间配置，频道是否插播由频道编辑里的「投放广告」开关决定；排期日历按月查看每日各广告位的投放安排。投放规则页可按「全部状态 / 仅启用 / 仅停用」筛选，状态由服务端按开关与日期区间派生为启用、已停用、待投放、已过期四种。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '在「广告素材」页面新增素材：填写名称、描述、音频 URL 与时长（秒），列表可试听，并标注默认占位素材',
          '在「投放规则」页面点左上角「新建投放」，选择素材、广告位与日期范围并启用',
          '在「投放规则」页面用状态下拉筛选，核对哪些规则在投、哪些已停用',
          '在「排期日历」页面选择月份查看投放安排；同一广告位同日有多条重叠时，日期格上会出现重叠角标',
          '点开重叠角标可查看冲突清单，并就地停用其中一条；停用后该投放不再播出',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '同一广告位在日期区间重叠时会被拒绝保存并提示冲突（停用的投放不参与冲突判定，可先停用旧的再建新的）；排期日历角标列出的是历史重叠数据，可当场处置。素材 URL 需指向可公网访问的音频，播放失败不会自动改用其它素材。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'stats',
    routes: ['/stats'],
    title: '数据统计',
    icon: markRaw(DataLine),
    intro: '查看播放量、DAU、完播率等核心指标及趋势。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '提供当日核心指标看板（DAU、播放量、完播率、平均收听、推算广告曝光）、7 天/30 天趋势图、按日期切换的历史数据查询。指标名称、单位与换算取自接口下发的元数据，页面不另写一套口径。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「数据统计」页面',
          '通过顶部日期选择器切换查询日期（只影响上方指标卡片）',
          '查看 5 个核心指标卡片',
          '在趋势图区切换指标（DAU/播放量/完播率）与时间范围（7 天/30 天）',
          '趋势指标与时间范围会被记住，刷新页面后保持上次选择',
        ],
      },
      {
        type: 'note',
        title: '口径提醒',
        content: '趋势图固定按近 7 天/30 天从今天往前取，页面会标明实际统计区间，不随上方日期选择器改变；概览取数失败时会明确提示「未取到」，不会把空值显示成当日为 0。',
        noteType: 'info',
      },
    ],
  },
  {
    id: 'channel-health',
    routes: ['/stats/channel-health'],
    title: '频道健康度',
    icon: markRaw(DataLine),
    intro: '按频道查看抓取与产出健康度，快速定位异常频道。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '顶部汇总卡统计健康、警告、严重与频道总数；下方每个频道一张卡片，展示今日待改写、区间入库、本频道已配源与关键词，并附每日入库迷你趋势。顶部可切换近 7 天 / 近 14 天 / 近 30 天。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「频道健康度」页面，先看顶部汇总判断整体状态',
          '切换统计区间，页面会标明实际统计区间',
          '按频道卡片查看今日待改写与区间入库，异常频道会以警告或严重配色标识',
          '需要排查抓取源时，转到「数据分析 → RSS 源状态」',
        ],
      },
      {
        type: 'note',
        title: '口径提醒',
        content: '卡片上的「本频道已配源」是各频道自己的配置条数，与「RSS 源状态」页的全局源清单不是同一口径，两处数字不必相等。',
        noteType: 'info',
      },
    ],
  },
  {
    id: 'rss-health',
    routes: ['/stats/rss-health'],
    title: 'RSS 源状态',
    icon: markRaw(Connection),
    intro: '查看全局 RSS 源清单的可达性与解析状态。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '展示后端 rss.yaml 的全局源清单，汇总总数、正常、失败与未巡检；可按状态筛选、按源名/URL/品类搜索，并可「立即巡检」触发后端探测全部源的可达性，失败源会标注失败原因。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「RSS 源状态」页面查看汇总卡与源列表',
          '用状态筛选切换全部 / 正常 / 失败 / 未巡检',
          '按源名、URL 或品类搜索定位具体源',
          '点「立即巡检」触发一次全量探测，巡检结束后查看最近巡检时间与失败原因',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '巡检状态与连续失败次数保存在服务进程内存中，服务重启后归零，页面会标明本轮统计的起点与已运行时长。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'llm-metrics',
    routes: ['/stats/llm-metrics'],
    title: 'LLM 重试指标',
    icon: markRaw(MagicStick),
    intro: '查看 LLM 调用重试率与改善效果，评估模型与提示词稳定性。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '用触发率与改善率两个派生率概括重试效果，并给出总调用、触发重试、重试改善、未改善四项基础计数与重试漏斗。触发率 = 触发次数 / 总调用；改善率 = 改善次数 / 触发次数。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「LLM 重试指标」页面，先看页面顶部说明理解派生率含义',
          '查看三个派生率卡片与四项基础计数',
          '查看重试漏斗，判断重试主要发生在哪一步',
          '点「刷新」重新拉取指标',
        ],
      },
      {
        type: 'note',
        title: '口径提醒',
        content: '页面所有计数都是服务进程内的累计值，重启即清零，页面会标明起点与已运行时长；触发率高于 50% 说明 LLM 字数缩水严重、需要优化提示词；改善率低于 30% 说明硬约束后缀效果不佳、需要更换策略。',
        noteType: 'info',
      },
    ],
  },
  {
    id: 'channels',
    routes: ['/channels'],
    title: '频道管理',
    icon: markRaw(Menu),
    intro: '配置新闻频道、RSS 源、关键词、调度时间与 LLM 提示词。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '每个频道独立配置 RSS 源、关键词、调度时间、开场/结尾/约束提示词、BGM、TTS 音色，实现频道级内容隔离与个性化播报风格。频道列表可直接启停、编辑与排序；素材侧入口为「素材库管理」「讲书稿素材池」，采集入口为「素材录入」「找书工具」，各自用法见对应章节。',
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
    id: 'material-library',
    routes: ['/channels/material-library'],
    title: '素材库管理',
    icon: markRaw(Menu),
    intro: '在频道级素材库里检索、维护与导出素材。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '按频道、状态、来源类型、媒体类型与关键词筛选素材，支持「明细」与「按书聚合」两种视图；可在库内手工新增素材，并按当前筛选导出 CSV（导出不受分页限制）。这里与工作流详情「爬虫采集 · 素材库」是同一份数据。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「素材库管理」页面，按频道、状态、来源类型、媒体类型或关键词筛选',
          '点「搜索」或「刷新」加载当前条件下的素材；跨页改动后需手动刷新才能看到',
          '在「视图」处切换「明细」与「按书聚合」两种查看方式',
          '点「库内手工新增素材」直接补一条记录；上传书稿或文档请走「素材录入」',
          '点「导出 CSV」按当前筛选导出全部匹配素材',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '「库内手工新增素材」与「素材录入」是两个不同入口：前者是在库中补一条记录，后者按渠道（上传书稿、云端对象、手动录入、URL 拉取、二维码分享）入库。编辑时来源是讲书稿按书聚合的键，不应清空。',
        noteType: 'info',
      },
    ],
  },
  {
    id: 'book-pool',
    routes: ['/channels/book-pool'],
    title: '讲书稿素材池',
    icon: markRaw(Menu),
    intro: '按频道维护讲书稿模式、书单、排序与进度。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '讲书稿模式按频道独立配置：开关、书单、排序与进度都属于所选频道。支持从素材库一键加入书目，面板与频道编辑弹窗内的素材池弹窗是同一组件，两端状态一致。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「讲书稿素材池」页面，先在顶部选择频道',
          '在面板内开启或关闭该频道的讲书稿模式',
          '从素材库把书目加入书单，并调整书单顺序',
          '查看或更新每本书的进度，供工作流按章节顺序生成讲书稿',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '未选择频道时面板不会加载，因为素材池、排序与进度都按频道独立；非有声频道开启讲书稿模式会先给出提示。地址里的频道不存在时，页面会明示已切换到实际频道。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'course-materials',
    routes: ['/materials'],
    title: '素材录入',
    icon: markRaw(List),
    intro: '按渠道录入单条或批量素材，素材必须归属一个频道。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '有声读物与课程频道共享五个输入渠道：本地文件上传、云端存储导入、手动录入、API / URL 拉取、二维码 / 链接分享。文档类文件按章节结构分章，每章作为一条素材。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「素材录入」页面，先在右上角「选择目标频道」',
          '本地文件上传：拖入文本、Markdown、EPUB、DOCX、HTML 或 PDF 文件，填写来源/书名与分类后点「上传并解析」',
          '云端存储导入：填写对象 Key 与来源/书名后点「导入」',
          '手动录入：填写标题与正文，可选 URL；留空 URL 时按正文内容去重，点「保存到素材池」',
          'API / URL 拉取：填写 URL 与类型后点「拉取并入库」',
          '二维码 / 链接分享：先「获取预览」，复核后点「转为手动录入」正式入库',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '素材必须归属一个频道，未选频道时上传会提示；本地文件一次只上传一个，.mobi 请先转存为 EPUB；扫描版 PDF 需先 OCR。整本上传使用单事务并支持断点续传，跳过章节会明示。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'book-finder',
    routes: ['/ebooks'],
    title: '找书工具',
    icon: markRaw(Search),
    intro: '检索第三方书源仓库，为讲书稿选题。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '按书名或作者检索书源，也可先选分类立即搜索；支持随机抽取一批书目作为选题参考，结果列表展示命中书目与下载状态。全量检索走本地索引，页面顶部显示索引就绪状态、书目与分类数量、构建时间。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「找书工具」页面，查看顶部索引状态',
          '不选分类的全量搜索需先点「构建索引」；索引过期时系统会自动触发后台更新',
          '输入书名或作者点检索，或先选分类再搜索',
          '需要选题灵感时可使用随机抽取',
          '人工下载 EPUB/DOCX 后，到「内容运营 → 素材录入」上传入库',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '找书工具只负责检索，下载与入库需人工完成：书源链接指向城通网盘，无直链、无法自动下载。书源内容来自网络搜集并声明「请勿用于商业目的」，对外发布前请自行确认授权。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'queue',
    routes: ['/queue'],
    title: '队列管理',
    icon: markRaw(Operation),
    intro: '查看工作流任务队列的执行状态并调整执行模式。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '顶部按任务状态分列计数卡片（排队中/运行中/成功/失败）；可切换执行模式（串行或并行，并行时设置并发数 1-5）；任务列表支持按状态与频道筛选，行内可取消、改优先级、从失败步骤重试；管理员可批量删除选中任务（删除稿件、审核、节目及播放记录，素材重置为待处理）。',
      },
    ],
  },
  {
    id: 'workflows',
    routes: ['/workflows', '/workflows/:id'],
    title: '工作流监控',
    icon: markRaw(Monitor),
    intro: '查看工作流执行状态、步骤进度与日志。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '工作流按状态（queued/running/success/failed/cancelled）分类展示；点击进入详情页可查看每个步骤（爬虫采集/LLM改写/质量审核/语音合成/音频拼接/创建审核）的执行情况、耗时、日志、错误信息。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「工作流监控」页面查看工作流列表',
          '按状态、频道、日期筛选',
          '点击工作流 ID 进入详情页',
          '查看步骤进度条与每步日志',
          '展开「步骤产物」可按需查看并编辑素材、稿件、审核记录与音频文件',
          '失败工作流可在详情页底部「从指定步骤重跑」里选步骤后点「重跑」断点续跑（界面无「重试」按钮）',
          '页面提示连接中断时，点「立即重连并刷新」恢复实时进度',
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
    routes: ['/tunnel'],
    title: '内网穿透',
    icon: markRaw(Connection),
    intro: '通过 cloudflared/cpolar 暴露本地服务到公网，便于小程序真机测试。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '支持 Cloudflare、cpolar 与 Tailscale Funnel 三种隧道方案，一键启动/停止；页面显示当前 provider 与公网地址，可复制、打开，并展示运行状态。Cloudflare 支持 quick 与 named 两种模式。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '在「Provider 配置」选择 Cloudflare、cpolar 或 Tailscale Funnel 并保存',
          'cpolar 需填写控制台获取的 Authtoken；Tailscale 需预装并登录，首次启用 Funnel 要在浏览器完成授权',
          'Cloudflare named 模式按向导配置固定域名；quick 模式无需配置',
          '点「启动隧道」建立公网连接，启动后可复制或打开公网地址；点「停止」断开',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'Cloudflare quick 隧道为临时地址，重启后变化；named 模式与 Tailscale Funnel 才提供固定域名。cpolar 需配置 Authtoken。若二进制下载失败，页面会给出需手动放置的路径。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'ai-config',
    routes: ['/ai-config'],
    title: 'AI 服务',
    icon: markRaw(Cpu),
    intro: '配置 LLM 与 TTS 服务商、API Key、模型、预算等。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '支持 LLM（通义千问 OpenAI 兼容接口）与 TTS 多 provider 配置（阿里云 NLS / Edge-TTS / 腾讯云 / Kokoro / Piper）；AI 预算限流 60 次/分钟/服务类型；前端修改后热生效无需重启。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '在「LLM 大模型」页签选择服务商预设，或直接填写接口地址与模型名称，可拉取可用模型并测试连接',
          '在同页签设置节目参数（目标时长、段间静音、最大段数、预期字数），与参数计算器的口径一致',
          '在「TTS 语音合成」页签选择 provider，填写对应凭证与音色，可试音与测试连接',
          '需要避免同一音色同质化时，开启交叉音色并选择切换策略（轮流 / 随机 / 每隔 N 段），至少选两个音色',
          '保存配置后热生效；需要作废凭据时点对应页签的「恢复初始配置」',
        ],
      },
      {
        type: 'config',
        title: '参数配置',
        content: [
          ['LLM_API_KEY', 'sk-...', '通义千问 API Key'],
          ['LLM_MODEL', 'qwen-max', '模型名称'],
          ['TTS_PROVIDER', 'aliyun', 'TTS 服务商：aliyun/edge/tencent/kokoro/piper'],
          ['ALIYUN_TTS_APPKEY', '...', '阿里云 NLS AppKey'],
          ['ALIYUN_TTS_API_KEY', 'AccessToken', '非 AccessKey Secret'],
          ['EDGE_TTS_VOICE', 'zh-CN-XiaoxiaoNeural', 'Edge-TTS 音色'],
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'TTS AccessToken 与 AccessKey Secret 不同，从 NLS 控制台获取。测试连接时若用脱敏值（****xxxx）会自动回退到真实 Key 测试。密钥类输入框留空保存表示不修改，不会清除库内已有密钥；要真正作废请用「恢复初始配置」。Piper 为单说话人模型，交叉音色不生效。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'ai-qa',
    routes: ['/ai-qa'],
    title: '智能助手',
    icon: markRaw(MagicStick),
    intro: '用自然语言驱动后台配置，或在知识库中检索答案。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '页面分「自动调度」与「知识库问答」两个页签。自动调度用于对系统菜单下达自然语言指令，助手先生成可编辑的配置草稿，经你核对确认后才落地；知识库问答基于知识库回答运营问题。顶部可选择模型，并切换模型列表的自动刷新（90 秒一次）或手动刷新。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「智能助手」页面，先在顶部选择模型；模型列表为空时会提示原因',
          '需要自动配置时，在「自动调度」页签用一句话描述目标，例如新增频道',
          '助手生成配置草稿后，逐项核对字段，点「确认创建」落地',
          '需要查资料时，切到「知识库问答」页签，输入问题后 Enter 发送、Shift+Enter 换行',
          '长回答卡住时可点「停止生成」中止本次请求，界面立即恢复可输入',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '仅 admin 角色可访问。「自动刷新」刷新的是模型列表，不是对话内容；模型列表拉取失败会给出错误提示与重试入口，不会显示成空列表。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'notification',
    routes: ['/notification'],
    title: '通知管理',
    icon: markRaw(Bell),
    intro: '配置钉钉/企微等通知渠道与事件订阅模板。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '支持钉钉群机器人（Webhook + 加签）、企业微信与邮件（SMTP）多渠道通知；通知开关按场景控制（工作流失败、待审核、发布成功），另有全局总开关。消息模板可编辑标题与正文并预览渲染效果；发送日志可按事件类型筛选，查看逐渠道结果并重发。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '在「基础配置」页签设置通知开关与各渠道凭证，填写 Admin Web 地址作为消息跳转链接的基础地址',
          '点「测试发送」向所有已配置渠道发送测试通知，确认链路可用',
          '在「消息模板」页签选择事件模板，修改标题与正文，点「预览」核对后保存',
          '在「发送日志」页签按事件类型筛选，展开逐渠道结果；失败记录可重发',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '全局总开关关闭后所有通知都不发送，场景开关随之失效。Webhook 等密钥类字段保存后显示为脱敏值；清空表示删除该渠道配置。预设模板首次启动自动 seed。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'auto-review',
    routes: ['/auto-review'],
    title: '自动审批',
    icon: markRaw(CircleCheck),
    intro: '配置稿件自动通过的规则，并查看命中统计与执行历史。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '开启后工作流完成时按校验逐项检查，全部命中的稿件跳过人工审核直接发布。校验项包括内容安全检测通过、工作流步骤一次成功与关键词白名单，默认全部生效，关闭即跳过，但至少要保留一条；首次开启或跳过项变化时必须勾选风险确认。下方展示统计卡片与执行历史（结果、触发原因、节省时间），失败记录可重试。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「自动审批」页面，点「刷新」加载配置、统计与历史',
          '按需开启「启用自动审批」，并逐项确认要保留的校验',
          '需要按关键词放行时，在「关键词白名单」输入并点「添加」；白名单按子串包含匹配',
          '首次开启或跳过项变化时，勾选「我已确认风险」',
          '点「保存配置」，随后在统计卡片与执行历史中核对命中情况',
          '执行历史里失败的记录可在行内点「重试」',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '过短的关键词会把大量稿件一并放行，保存会被服务端拒绝，请先删除或改写。风险确认机制上线前已开启的存量配置，页面会点名提示补确认，但不阻断现有自动发布。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'admin-users',
    routes: ['/system/users'],
    title: '用户管理',
    icon: markRaw(Document),
    intro: '管理可登录运营后台的账号（管理员 / 运营）。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '支持新增、编辑、重置口令、启用/禁用与删除后台账号；列表显示用户名、昵称、角色、状态、最近登录与创建时间，当前登录账号会标注「当前登录」。页面底部展示最近账号变更审计。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '进入「用户管理」页面，按用户名或昵称搜索，点「查询」',
          '点「新增账号」填写用户名、昵称、角色与初始口令，可写备注；备注与操作都会写入审计',
          '在行内点「编辑」修改昵称、角色或状态',
          '在行内点「重置口令」为该账号设置新口令',
          '用「禁用 / 启用」控制账号能否登录，点「删除」移除账号',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '这里只管理可登录运营后台的账号；小程序终端用户请在移动端「用户管理」中处理。不能修改自己的角色，也不能禁用或删除当前登录的账号。重置口令后旧口令立即失效，但已登录会话最长仍会持续到当前凭证过期（约 2 小时），需要立即失效请让其先退出登录。口令至少 8 位。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'tools',
    routes: ['/tools/calculator'],
    title: '参数计算器',
    icon: markRaw(Calendar),
    intro: '在时长、总字数、语速倍率之间三选一锁定，由另外两项推导。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '三个参数（时长/总字数/语速倍率）一次只锁定一项，锁定项由另外两项实时推导：时长(秒) = 总字数 ÷ (210 × 倍率) × 60。基础语速是项目常量 210 字/分，不设额外容差；可调范围是时长 60–1800 秒、总字数 200–10000 字、倍率 0.5–2.5。页面提供新闻速递、标准节目、完整节目、快节奏精华四个预设，点击顶部「应用到 AI 配置」可把三项参数带入 AI 服务。',
      },
      {
        type: 'note',
        title: '口径提醒',
        content: '这里只输出三个参数本身，不提供额外的语速结论；旧版帮助文档的时长单位、语速基线与容差都与界面不符，已按当前实现订正。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'db-admin',
    routes: ['/db-admin'],
    title: '数据库维护',
    icon: markRaw(Coin),
    intro: '在线查看/编辑 SQLite 数据库表数据。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '提供白名单内 16 张业务表的在线浏览与增删改（搜索、排序、分页、表结构查看），支持 CSV/JSON 导入导出，导入前有 dry-run 预览（预计插入/更新/错误行，预览不写库）。页面不提供 SQL 查询或 SQL 执行入口。敏感字段（password/secret/token/key）在列表、编辑与审计日志中均自动脱敏，且保存时不会把脱敏占位值写回真实凭据。危险操作需手输确认文本（删除输入表名、导入输入 IMPORT），且仅在服务端配置了 DB_ADMIN_CONFIRM_TOKEN 时才放行。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '在左侧「数据表」搜索并选择要维护的表，右侧加载数据',
          '用搜索框、排序与分页浏览行数据，可查看表结构',
          '点「新增」插入记录，双击或点行内编辑修改，勾选多行后可批量删除',
          '导出：从工具栏下拉选择 CSV 或 JSON，按当前表导出',
          '导入：先选择 CSV 或 JSON 输入并执行 dry-run 预览，确认预计插入/更新/错误行后，手输 IMPORT 正式导入',
          '删除记录属于危险操作，需按提示手输表名确认',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '直接操作数据库有风险，建议先备份。表操作受白名单机制限制，仅允许操作配置中声明的表。危险操作确认依赖服务端配置的总开关，未配置时确认一律不放行；界面上的脱敏占位值不会写回真实凭据。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'maintenance',
    routes: ['/maintenance'],
    title: '系统清理',
    icon: markRaw(Brush),
    intro: '清理历史数据、缓存、日志，VACUUM 压缩 SQLite。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '三组清理卡片：缓存（全部缓存/TTLCache/__pycache__ 目录/临时文件）、数据库（全部清理/旧播放日志/旧工作流记录/旧审核记录/过期 JWT 黑名单/旧爬虫去重记录/旧运营收件箱/旧 AI 用量日志/VACUUM 压缩/指定工作流全链清理/无主素材解绑/无主素材删除）、日志（全部清理/旧日志文件/大日志文件）；每组都有 dry_run 预览开关，关掉预览才会真实删除。旧运营收件箱按保留天数清理，后台每日 03:30 自动按 ADMIN_INBOX_KEEP_DAYS（默认 90 天）执行（读没读都清），页面入口只是手动兜底、可指定更短窗口。指定工作流全链清理按工作流 ID 删除其稿件/节目/审核/播放数据等子表，运行中的工作流会被拒绝。无主素材指 channel_id 还指向已删除频道的素材行，两个目标都只按这一个条件筛（没有保留天数），也不参与「全部清理」：解绑只清空归属、正文回到全局素材池；删除连正文一起删。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '先看顶部存储状态卡片，确认数据库、日志文件与缓存的实际占用',
          '在对应分组选择「清理目标」，保持「预览模式」开启并点「预览清理」',
          '核对预览条数与样例后，关闭预览模式，点「立即执行清理」',
          '长任务会转后台作业并显示进度，可离开页面，回来后在卡片上查看状态',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'VACUUM 会锁定数据库直到压缩完成，建议在低峰期执行。清理操作不可逆，建议先预览，预览不写库。正在写入的最新日志文件不会被清理。页面底部还有「应急停服」卡片：停服会暂停所有新任务触发、不影响已在执行的任务，必须填写原因并逐字输入「停服」确认，解除时输入「解除停服」；停服不会自动到期恢复，停服期间未触发的任务不会自动补跑，停服与恢复记录可在卡片内查看。仅 admin 角色可访问。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'cos-storage',
    routes: ['/cos-config', '/cos-files'],
    // 侧栏叫「云端配置」「文件管理」，章节标题与首句沿用同一套菜单名（T02635）
    title: '云端存储（COS）',
    icon: markRaw(Coin),
    intro: '在「云端配置」填写腾讯云 COS 凭证，在「文件管理」查看云端音频；音频直连 COS 可加速小程序播放。生产环境强烈推荐。',
    blocks: [
      {
        type: 'feature',
        title: '为什么需要 COS',
        content: '未配置 COS 时，音频文件经 Tailscale Funnel 中转播放，受限于家庭宽带上行与公网中转延迟，首字播放延迟明显偏高。配置 COS 后音频直走腾讯云边缘节点，首字延迟随之下降，且播放不再依赖开发电脑在线。凭证在「云端配置」维护，已上传的云端音频在「文件管理」查看。',
      },
      {
        type: 'steps',
        title: '获取 COS 凭证步骤',
        content: [
          '注册腾讯云账号：访问 cloud.tencent.com，用微信扫码或手机号注册并完成实名认证（个人认证即可）',
          '开通对象存储：控制台搜索"对象存储" → 首次进入会提示开通（按用量计费，个人测试量级费用很低，具体以腾讯云报价页为准）',
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
          '验证凭证：python scripts/jmeter_test/verify_cos.py（自动上传测试文件 → 公网访问 → 清理）',
          '迁移历史音频：python scripts/jmeter_test/migrate_audio_to_cos.py（自动扫描 /audio/ 路径的 episode 并上传 COS）',
          '重启后端服务：执行 scripts/stop.ps1 → scripts/start.ps1',
          '配置小程序域名白名单：mp.weixin.qq.com → 开发管理 → 服务器域名 → downloadFile 合法域名 → 添加 https://<bucket>.cos.<region>.myqcloud.com',
          '真机验证：小程序播放任意节目，观察首字播放延迟应显著降低',
        ],
      },
      {
        type: 'steps',
        title: '文件管理操作',
        content: [
          '进入「文件管理」查看云端目录，点文件夹进入子目录，顶部显示当前路径',
          '点「上传文件」可单个或批量上传；同名文件会先探测并弹出覆盖确认',
          '点「新建文件夹」创建目录；行内「重命名」仅用于同级改名，不能跨目录移动',
          '行内「下载」获取文件，「删除」移除对象；删除前请确认影响范围',
          '按「快照保留份数」设置，覆盖或恢复前会生成备份；进入 .backup 快照目录可对旧版本点「恢复」',
        ],
      },
      {
        type: 'scenario',
        title: '使用场景',
        content: '生产环境部署完成后，音频播放慢于局域网；或希望音频播放不依赖开发电脑在线。开发环境调试时可不配置 COS，音频走本地 /audio 路径即可。',
      },
      {
        type: 'note',
        title: '文件管理注意事项',
        content: '批量上传结束会在页面上给出成功、失败与取消的汇总，并列出失败清单，直到手动关闭。同名覆盖是否可回退取决于「快照保留份数」：设为 0 时覆盖与恢复都不留快照，确认框会明确提示不可找回。重命名只支持同级改名，不能借它跨目录移动。',
        noteType: 'warning',
      },
      {
        type: 'note',
        title: '注意事项',
        content: 'COS_CDN_DOMAIN 留空时会用 COS 默认域名（xxx.cos.xxx.myqcloud.com），该域名已备案可直用。若需自定义 CDN 域名（如 audio.example.com），需先注册域名并完成 ICP 备案（周期以管局实测为准，非即时生效）。SecretKey 切勿提交到 Git 或泄露给前端。迁移脚本幂等可重复执行。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'mobile',
    routes: ['/m/login', '/m/home', '/m/review', '/m/message', '/m/mine', '/m/manage'],
    title: '移动端（运营）',
    icon: markRaw(Monitor),
    intro: '在手机浏览器使用运营后台的审批与管理快捷入口。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '移动端页面位于 /m 路径下，与 PC 后台共用鉴权、接口与数据。首页展示今日关键指标、待我审批与未读消息；审批列表支持单条处理与一键全部审批，展开可看完整正文、封面与音频，并标注成品时长与凑时；消息中心支持全部已读与加载更多；「我的」页可切回 PC 完整后台与退出登录。管理员另有「管理」页，提供用户管理、用户反馈、频道管理、广告投放、队列监控与应急停服快捷入口。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '手机浏览器打开运营后台地址的 /m 路径并登录，账号与 PC 后台相同',
          '在首页查看今日关键指标，点「待我审批」进入审批列表',
          '审批时可展开稿件查看详情；批量处理前会二次确认并展示频道分布',
          '在消息中心点「全部已读」，或在列表底部点「加载更多」翻页',
          '管理员从底部「管理」进入各快捷入口，两端数据实时同步',
        ],
      },
      {
        type: 'note',
        title: '注意事项',
        content: '跨端打开深链会自动切换到对应端的同名页面，并在落点页给出提示与「仍要查看原页面」的回链。移动端的应急停服与 PC 端使用同一份状态、确认强度与审计记录。仅管理员可见「管理」入口。',
        noteType: 'warning',
      },
    ],
  },
  {
    id: 'about',
    routes: ['/about'],
    title: '关于 / 版本信息',
    icon: markRaw(Promotion),
    intro: '系统元信息与文档资源统一入口。',
    blocks: [
      {
        type: 'feature',
        title: '核心功能',
        content: '展示当前版本号、发布日期、Git SHA、Python 版本、平台；一键检查最新发布版本——检查未完成时显示具体原因与重试入口，不会谎报「已是最新」。链接入口为帮助文档、开源软件声明，以及由后端配置的仓库地址派生的项目主页、版本发布、报告问题（未配置仓库则不显示）；开发环境另有 API 文档。开源许可清单列出前后端依赖，其版本号在构建期与 package.json / requirements.txt 逐条比对，漂移即构建失败。',
      },
      {
        type: 'steps',
        title: '操作步骤',
        content: [
          '点击侧边栏「关于」进入关于页面',
          '查看版本号、发布日期、Git SHA 等元信息',
          '点击「检查更新」查询最新发布；显示「无法确认」时按提示的原因处理后再重试',
          '点击列表项打开项目主页、版本发布或报告问题',
          '在开源软件声明 Modal 搜索框按包名/许可证过滤依赖',
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

// M88：搜索此前只匹配 title/intro，正文里的「CONFIRM_DELETE」「VACUUM」「COS」「密钥」
// 一律搜不到，用户会以为文档没写。匹配口径（含步骤数组、表格行、注意事项）收在
// utils/helpSearch.js：那是对真实文档可跑用例的纯函数，留在这里就只能断言源码写法。
const filteredSections = computed(() => filterHelpSections(docSections, search.value))

async function openApiDocs() {
  // 交互式文档只在后端 development 环境挂载（main.py 的 docs_url 受 is_dev 控制），
  // 生产点 /docs 是 404 死链——先向 /about 取这个事实，再决定打开还是说明（FR-UX-404）。
  try {
    const info = await getAbout()
    if (!info?.docs_enabled) {
      ElMessage.info('当前环境未开放交互式 API 文档（仅开发环境挂载）；接口清单见 docs/详细设计说明书.md。')
      return
    }
    window.open(API_DOCS_PATH, '_blank', 'noopener,noreferrer')
  } catch (e) {
    notifyErrorOnce(e, '无法确认 API 文档是否开放，请稍后重试')
  }
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

// 菜单引导重放（T02502 / FR-UX-403）：侧栏窄，用 chips 换行而不是逐个占一行
.replay-block {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid $color-border;
}

.replay-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;

  .replay-title {
    font-size: 14px;
    font-weight: 600;
    color: $color-text-primary;
  }
}

.replay-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.replay-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  color: $color-text-secondary;
  background: var(--color-bg);
  border: 1px solid $color-border;
  border-radius: $radius-md;
  cursor: pointer;
  transition: background-color 120ms cubic-bezier(0.2, 0, 0, 1);

  .replay-done {
    font-size: 12px;
    color: $color-primary-dark;
  }

  &:hover {
    background: var(--color-primary-light);
    color: $color-primary-dark;
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
