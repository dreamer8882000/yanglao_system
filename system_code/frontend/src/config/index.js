/**
 * 前端系统配置
 */

/**
 * API 配置
 */
export const API_CONFIG = {
  baseURL: import.meta.env.VITE_API_BASE_URL + '/api',
  timeout: 120000, // 2 分钟
  retryCount: 3,
  retryDelay: 1000
};

/**
 * 分页配置
 */
export const PAGINATION = {
  defaultPageSize: 20,
  pageSizes: [10, 20, 50, 100],
  maxPageSize: 100
};

/**
 * 告警配置
 */
export const ALERT_CONFIG = {
  // 等级色不再在这里写第二份字面量：色值只在 assets/styles/tokens.css 定义，
  // 这里给出 token 名，实际渲染时用 var(--level-x)。
  // （这份常量目前零引用，保留是为了与 token 保持同一口径，避免它变成第 5 套说法。）
  riskLevels: [
    { value: 'NORMAL', label: '正常', color: 'var(--level-normal)', icon: '🟢' },
    { value: 'LOW', label: '低危', color: 'var(--level-low)', icon: '🔵' },
    { value: 'MEDIUM', label: '中危', color: 'var(--level-medium)', icon: '🟡' },
    { value: 'HIGH', label: '高危', color: 'var(--level-high)', icon: '🔴' },
    { value: 'URGENT', label: '紧急', color: 'var(--level-urgent)', icon: '🚨' }
  ],
  
  statusOptions: [
    { value: 0, label: '待处理', color: 'var(--warning)' },
    { value: 1, label: '已处理', color: 'var(--success)' }
  ],
  
  autoRefreshInterval: 30000, // 30 秒自动刷新
  soundEnabled: true,
  notificationEnabled: true
};

/**
 * 摄像头配置
 */
export const CAMERA_CONFIG = {
  sourceTypes: [
    { value: 'stream', label: '视频流', icon: '📹' },
    { value: 'upload', label: '图片上传', icon: '📸' },
    { value: 'local', label: '本地设备', icon: '📷' }
  ],
  
  yoloModels: [
    { value: 'pose', label: '融合推理', desc: '姿态估计 + 表情识别 + D-S 风险融合' },
    { value: 'face', label: '表情辅助', desc: '跌倒风险触发后裁剪人脸并识别表情' },
    { value: 'none', label: '不启用', desc: '仅监控画面' }
  ],
  
  heartbeatInterval: 60000, // 1 分钟心跳
  offlineThreshold: 300000 // 5 分钟离线阈值
};

/**
 * 排班配置
 */
export const SCHEDULE_CONFIG = {
  shiftTypes: [
    { value: 'day', label: '白班', time: '08:00-20:00', color: 'var(--primary)' },
    { value: 'night', label: '夜班', time: '20:00-08:00', color: 'var(--violet)' },
    { value: 'custom', label: '自定义', time: '自定义时段', color: 'var(--info)' }
  ],
  
  maxDaysInAdvance: 90, // 最多提前 90 天排班
  minStaffPerShift: 2 // 每班最少 2 人
};

/**
 * 老人档案配置
 */
export const ELDER_CONFIG = {
  genderOptions: [
    { value: 1, label: '男' },
    { value: 2, label: '女' }
  ],
  
  statusOptions: [
    { value: 1, label: '在院', color: 'var(--success)' },
    { value: 0, label: '离院', color: 'var(--text-disabled)' }
  ],
  
  ageRange: { min: 60, max: 120 },
  
  healthLevels: [
    { value: 1, label: '健康', color: 'var(--success)' },
    { value: 2, label: '一般', color: 'var(--warning)' },
    { value: 3, label: '较差', color: 'var(--danger)' }
  ]
};

/**
 * Agent AI 配置
 */
export const AGENT_CONFIG = {
  maxHistoryMessages: 20,
  streamTimeout: 60000,
  reconnectInterval: 3000,
  maxReconnectAttempts: 3,
  
  quickQuestions: [
    '系统整体运行情况如何？',
    '今天有多少高危告警？',
    '查看当前值班人员',
    '查询最近待处理的告警'
  ]
};

/**
 * 文件上传配置
 */
export const UPLOAD_CONFIG = {
  maxSize: 10 * 1024 * 1024, // 10MB
  acceptTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
  acceptExtensions: ['.jpg', '.jpeg', '.png', '.gif', '.webp']
};

/**
 * 主题配置
 */
export const THEME_CONFIG = {
  primaryColor: 'var(--primary)',
  secondaryColor: 'var(--violet)',
  // 色值只引用 token（具体色值在 assets/styles/tokens.css 按主题定义）
  accentColor: 'var(--info)',
  successColor: 'var(--success)',
  warningColor: 'var(--warning)',
  errorColor: 'var(--danger)',

  borderRadius: 'var(--radius-md)',
  boxShadow: 'var(--shadow-sm)',
  
  animations: {
    duration: '300ms',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
  }
};

/**
 * 缓存配置
 */
export const CACHE_CONFIG = {
  userTTL: 7 * 24 * 60 * 60 * 1000, // 用户信息缓存 7 天
  pageTTL: 5 * 60 * 1000, // 页面状态缓存 5 分钟
  draftTTL: 24 * 60 * 60 * 1000 // 表单草稿缓存 24 小时
};

/**
 * 性能监控配置
 */
export const PERFORMANCE_CONFIG = {
  enableTracking: true,
  sampleRate: 1.0, // 采样率 100%
  slowRequestThreshold: 3000, // 慢请求阈值 3 秒
  
  debounceDelay: 300, // 防抖延迟
  throttleInterval: 200 // 节流间隔
};

/**
 * 错误处理配置
 */
export const ERROR_CONFIG = {
  showErrorDetails: import.meta.env.DEV, // 开发环境显示详细错误
  maxRetries: 3,
  retryStatusCodes: [408, 429, 500, 502, 503, 504],
  
  messages: {
    400: '请求参数错误',
    401: '未授权，请重新登录',
    403: '无权限访问',
    404: '请求的资源不存在',
    408: '请求超时',
    429: '请求过于频繁',
    500: '服务器内部错误',
    502: '网关错误',
    503: '服务不可用',
    504: '网关超时',
    
    network: '网络连接失败',
    timeout: '请求超时',
    cancel: '请求已取消',
    unknown: '未知错误'
  }
};

/**
 * WebSocket 配置
 */
export const WS_CONFIG = {
  reconnectDelay: 3000,
  maxReconnectAttempts: 5,
  heartbeatInterval: 30000,
  heartbeatTimeout: 5000
};

/**
 * 导出配置
 */
export const EXPORT_CONFIG = {
  csvEncoding: 'UTF-8',
  csvBOM: '\uFEFF',
  maxExportRows: 10000
};

/**
 * 统计图表配置
 */
export const CHART_CONFIG = {
  colors: ['var(--primary)', 'var(--violet)', 'var(--info)', 'var(--success)', 'var(--warning)', 'var(--danger)'],
  
  defaultOptions: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 500
    }
  }
};

export default {
  API_CONFIG,
  PAGINATION,
  ALERT_CONFIG,
  CAMERA_CONFIG,
  SCHEDULE_CONFIG,
  ELDER_CONFIG,
  AGENT_CONFIG,
  UPLOAD_CONFIG,
  THEME_CONFIG,
  CACHE_CONFIG,
  PERFORMANCE_CONFIG,
  ERROR_CONFIG,
  WS_CONFIG,
  EXPORT_CONFIG,
  CHART_CONFIG
};
