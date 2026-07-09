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
