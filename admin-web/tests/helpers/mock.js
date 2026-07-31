/**
 * Mock 数据集中管理
 *
 * 所有响应均遵循后端统一格式：{ code, message, data }
 * code === 0 表示业务成功，axios 拦截器会解包返回 data
 */

// ============== 登录相关 ==============
export const loginSuccessResponse = {
  code: 0,
  message: 'success',
  data: {
    token: 'test-token-admin',
    username: 'admin',
    role: 'admin',
  },
}

// operator 角色用于工作流权限测试
export const loginOperatorResponse = {
  code: 0,
  message: 'success',
  data: {
    token: 'test-token-operator',
    username: 'operator01',
    role: 'operator',
  },
}

// 业务错误：用户名或密码错误（HTTP 200，code !== 0）
export const loginFailResponse = {
  code: 1001,
  message: '用户名或密码错误',
  data: null,
}

export const logoutResponse = { code: 0, message: 'success', data: null }

// ============== 审核相关 ==============
export const reviewListResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 2,
    list: [
      {
        id: 1,
        episode_date: '2026-07-08',
        workflow_id: 'wf-001',
        status: 'pending',
        created_at: '2026-07-08T05:00:00',
      },
      {
        id: 2,
        episode_date: '2026-07-07',
        workflow_id: 'wf-002',
        status: 'pending',
        created_at: '2026-07-07T05:00:00',
      },
    ],
  },
}

export const reviewApprovedListResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 1,
    list: [
      {
        id: 3,
        episode_date: '2026-07-06',
        workflow_id: 'wf-003',
        status: 'approved',
        created_at: '2026-07-06T05:00:00',
      },
    ],
  },
}

export const reviewRejectedListResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 1,
    list: [
      {
        id: 4,
        episode_date: '2026-07-05',
        workflow_id: 'wf-004',
        status: 'rejected',
        created_at: '2026-07-05T05:00:00',
      },
    ],
  },
}

export const reviewDetailResponse = {
  code: 0,
  message: 'success',
  data: {
    id: 1,
    episode_date: '2026-07-08',
    workflow_id: 'wf-001',
    status: 'pending',
    audio_url: 'https://example.com/audio/001.mp3',
    script: {
      full_text: '<p>这是第一条稿件内容。</p><p>这是第二条稿件内容。</p>',
      referenced_materials: ['https://source1.com', 'https://source2.com'],
      segments: [
        { seq: 1, title: '头条新闻' },
        { seq: 2, title: '科技快讯' },
      ],
    },
  },
}

export const reviewActionSuccessResponse = {
  code: 0,
  message: 'success',
  data: null,
}

// 批量审核成功响应：2 条成功、0 跳过、0 失败
export const reviewBatchActionSuccessResponse = {
  code: 0,
  message: 'success',
  data: {
    succeeded: [
      { id: 1, workflow_id: 'wf-001', need_publish: true },
      { id: 2, workflow_id: 'wf-002', need_publish: true },
    ],
    failed: [],
    skipped: [],
    published: [
      { id: 1, episode_id: 101 },
      { id: 2, episode_id: 102 },
    ],
    publish_failed: [],
    total: 2,
  },
}

// ============== 广告相关 ==============
export const adMaterialsListResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 2,
    list: [
      {
        id: 1,
        name: '品牌广告A',
        description: '品牌宣传音频',
        duration: 15,
        file_url: 'https://example.com/ads/a.mp3',
        is_default: true,
      },
      {
        id: 2,
        name: '促销广告B',
        description: '促销活动音频',
        duration: 30,
        file_url: 'https://example.com/ads/b.mp3',
        is_default: false,
      },
    ],
  },
}

export const adMaterialCreateSuccessResponse = {
  code: 0,
  message: 'success',
  data: { id: 3 },
}

export const adPlacementsListResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 2,
    list: [
      {
        id: 1,
        material_id: 1,
        material_name: '品牌广告A',
        position: 'head',
        start_date: '2026-07-01',
        end_date: '2026-07-31',
      },
      {
        id: 2,
        material_id: 2,
        material_name: '促销广告B',
        position: 'mid',
        start_date: '2026-07-05',
        end_date: '2026-07-10',
      },
    ],
  },
}

export const adPlacementCreateSuccessResponse = {
  code: 0,
  message: 'success',
  data: { id: 3 },
}

export const adScheduleResponse = {
  code: 0,
  message: 'success',
  data: {
    placements: [
      {
        material_name: '品牌广告A',
        position: 'head',
        start_date: '2026-07-01',
        end_date: '2026-07-31',
      },
      {
        material_name: '促销广告B',
        position: 'mid',
        start_date: '2026-07-05',
        end_date: '2026-07-10',
      },
    ],
  },
}

// ============== 统计相关 ==============
export const statsOverviewResponse = {
  code: 0,
  message: 'success',
  data: {
    dau: 12345,
    play_count: 67890,
    completion_rate: 0.65,
    avg_listen_duration: 8.5,
    ad_impression: 5432,
  },
}

export const statsTrendResponse = {
  code: 0,
  message: 'success',
  data: {
    dates: ['2026-07-01', '2026-07-02', '2026-07-03'],
    values: [1000, 1200, 1500],
  },
}

// 频道素材健康度：3 个频道覆盖 healthy/warning/critical 三种状态
export const channelHealthResponse = {
  code: 0,
  message: 'success',
  data: {
    channels: [
      {
        channel_id: 1,
        name: '科技前沿',
        description: '科技资讯',
        is_active: true,
        rss_source_count: 5,
        keyword_count: 12,
        today_pending: 8,
        range_total: 35,
        daily_trend: [
          { date: '2026-07-15', count: 5 },
          { date: '2026-07-16', count: 6 },
          { date: '2026-07-17', count: 4 },
          { date: '2026-07-18', count: 7 },
          { date: '2026-07-19', count: 5 },
          { date: '2026-07-20', count: 4 },
          { date: '2026-07-21', count: 4 },
        ],
        health_status: 'healthy',
      },
      {
        channel_id: 2,
        name: '财经观察',
        description: '财经动态',
        is_active: true,
        rss_source_count: 3,
        keyword_count: 10,
        today_pending: 2,
        range_total: 18,
        daily_trend: [
          { date: '2026-07-15', count: 0 },
          { date: '2026-07-16', count: 8 },
          { date: '2026-07-17', count: 0 },
          { date: '2026-07-18', count: 0 },
          { date: '2026-07-19', count: 10 },
          { date: '2026-07-20', count: 0 },
          { date: '2026-07-21', count: 0 },
        ],
        health_status: 'warning',
      },
      {
        channel_id: 3,
        name: '主机游戏',
        description: '主机游戏资讯',
        is_active: true,
        rss_source_count: 4,
        keyword_count: 15,
        today_pending: 0,
        range_total: 0,
        daily_trend: [
          { date: '2026-07-15', count: 0 },
          { date: '2026-07-16', count: 0 },
          { date: '2026-07-17', count: 0 },
          { date: '2026-07-18', count: 0 },
          { date: '2026-07-19', count: 0 },
          { date: '2026-07-20', count: 0 },
          { date: '2026-07-21', count: 0 },
        ],
        health_status: 'critical',
      },
    ],
    summary: { healthy: 1, warning: 1, critical: 1, total: 3 },
  },
}

// RSS 源可达性：覆盖 ok/fail/unknown 三种状态
export const rssHealthResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 3,
    ok: 1,
    fail: 1,
    unknown: 1,
    checked_at: '2026-07-21T05:00:00+00:00',
    sources: [
      {
        name: '人民网-国内',
        url: 'http://www.people.com.cn/rss/politics.xml',
        category_hint: '时政',
        status: 'ok',
        latency_ms: 320,
        consecutive_failures: 0,
        last_check: '2026-07-21T05:00:00+00:00',
        last_error: null,
      },
      {
        name: 'rsshub 失效源',
        url: 'https://rsshub.app/failed',
        category_hint: '科技',
        status: 'fail',
        latency_ms: 8000,
        consecutive_failures: 3,
        last_check: '2026-07-21T05:00:00+00:00',
        last_error: 'ConnectError: DNS resolution failed',
      },
      {
        name: '未巡检源',
        url: 'http://example.com/rss',
        category_hint: '科技',
        status: 'unknown',
        latency_ms: 0,
        consecutive_failures: 0,
        last_check: null,
        last_error: null,
      },
    ],
  },
}

// LLM 字数硬约束重试命中率：覆盖触发率/改善率/未改善率三种典型场景数据
// mock 值典型场景：100 次调用 → 30 次触发 → 20 次改善 + 10 次未改善
export const llmMetricsResponse = {
  code: 0,
  message: 'success',
  data: {
    total_calls: 100,
    triggered: 30,
    improved: 20,
    not_improved: 10,
    trigger_rate: 30.0,
    improve_rate: 66.67,
    not_improve_rate: 33.33,
  },
}

// ============== 工作流相关 ==============
export const workflowListResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 2,
    list: [
      {
        id: 'wf-001',
        episode_date: '2026-07-08',
        source: 'cron',
        status: 'success',
        started_at: '2026-07-08T05:00:00',
        finished_at: '2026-07-08T05:30:00',
      },
      {
        id: 'wf-002',
        episode_date: '2026-07-07',
        source: 'manual',
        status: 'running',
        started_at: '2026-07-07T05:00:00',
        finished_at: null,
      },
    ],
  },
}

export const workflowTriggerResponse = {
  code: 0,
  message: 'success',
  data: { workflow_id: 'wf-003' },
}

export const workflowDetailResponse = {
  code: 0,
  message: 'success',
  data: {
    workflow_id: 'wf-001',
    episode_date: '2026-07-08',
    source: 'cron',
    status: 'success',
    started_at: '2026-07-08T05:00:00',
    finished_at: '2026-07-08T05:30:00',
    error: null,
    steps: [
      { name: 'crawl', status: 'success', started_at: '2026-07-08T05:00:00', finished_at: '2026-07-08T05:10:00', retry_count: 0, error: null },
      { name: 'rewrite', status: 'success', started_at: '2026-07-08T05:10:00', finished_at: '2026-07-08T05:20:00', retry_count: 0, error: null },
      { name: 'tts', status: 'success', started_at: '2026-07-08T05:20:00', finished_at: '2026-07-08T05:25:00', retry_count: 0, error: null },
      { name: 'stitch', status: 'success', started_at: '2026-07-08T05:25:00', finished_at: '2026-07-08T05:28:00', retry_count: 0, error: null },
      { name: 'review', status: 'success', started_at: '2026-07-08T05:28:00', finished_at: '2026-07-08T05:30:00', retry_count: 0, error: null },
    ],
  },
}

export const workflowRetryResponse = {
  code: 0,
  message: 'success',
  data: { new_workflow_id: 'wf-004' },
}

// 批量删除成功响应：返回被删除的 workflow_id 列表
export const workflowBatchDeleteResponse = {
  code: 0,
  message: 'success',
  data: { deleted: ['wf-001', 'wf-002'] },
}

// 多选删除测试专用列表：3 条 success 状态工作流均可删除
// 与 workflowListResponse 区分，避免影响其他测试用例
export const workflowListMultiSelectResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 3,
    list: [
      {
        id: 'wf-001',
        episode_date: '2026-07-08',
        source: 'cron',
        status: 'success',
        started_at: '2026-07-08T05:00:00',
        finished_at: '2026-07-08T05:30:00',
      },
      {
        id: 'wf-002',
        episode_date: '2026-07-07',
        source: 'manual',
        status: 'success',
        started_at: '2026-07-07T05:00:00',
        finished_at: '2026-07-07T05:30:00',
      },
      {
        id: 'wf-003',
        episode_date: '2026-07-06',
        source: 'cron',
        status: 'failed',
        started_at: '2026-07-06T05:00:00',
        finished_at: '2026-07-06T05:10:00',
      },
    ],
  },
}

// ============== 队列管理相关 ==============
// 后端响应字段为 execution_mode / max_concurrent（SRS 5.1 API 规范）
export const queueConfigResponse = {
  code: 0,
  message: 'success',
  data: {
    execution_mode: 'serial',
    max_concurrent: 1,
  },
}

export const queueStatsResponse = {
  code: 0,
  message: 'success',
  data: {
    queued: 3,
    running: 1,
    success: 10,
    failed: 2,
    cancelled: 1,
  },
}

// 任务列表：后端返回 items 字段（SRS 5.1），含 channel_name（joinedload）
export const queueTasksResponse = {
  code: 0,
  message: 'success',
  data: {
    total: 2,
    items: [
      {
        id: 'wf-20260708-0001',
        episode_date: '2026-07-08',
        source: 'cron',
        status: 'queued',
        channel_id: 1,
        channel_name: '科技频道',
        priority: 8,
        started_at: '2026-07-08T05:00:00',
        finished_at: null,
        error: null,
      },
      {
        id: 'wf-20260708-0002',
        episode_date: '2026-07-08',
        source: 'manual',
        status: 'failed',
        channel_id: 2,
        channel_name: '财经频道',
        priority: 5,
        started_at: '2026-07-08T06:00:00',
        finished_at: '2026-07-08T06:10:00',
        error: 'TTS 合成失败',
      },
    ],
  },
}

export const queueActionSuccessResponse = {
  code: 0,
  message: 'success',
  data: null,
}

// ============== 频道管理相关 ==============
export const channelsListResponse = {
  code: 0,
  message: 'success',
  data: [
    {
      id: 1,
      name: '科技频道',
      description: '科技资讯',
      is_active: 1,
      created_at: '2026-07-01T10:00:00',
    },
    {
      id: 2,
      name: '财经频道',
      description: '财经动态',
      is_active: 1,
      created_at: '2026-07-02T10:00:00',
    },
  ],
}

export const channelCreateSuccessResponse = {
  code: 0,
  message: 'success',
  data: { id: 3 },
}

/**
 * 注入登录态到 localStorage
 * 用于跳过登录页直接进入受保护路由，简化非登录场景的测试
 */
export async function setLoginState(page, role = 'admin') {
  await page.addInitScript(([role]) => {
    const token = role === 'admin' ? 'test-token-admin' : 'test-token-operator'
    const username = role === 'admin' ? 'admin' : 'operator01'
    window.localStorage.setItem('admin_token', token)
    window.localStorage.setItem('admin_username', username)
    window.localStorage.setItem('admin_role', role)
  }, [role])
}
