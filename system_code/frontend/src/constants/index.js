/**
 * 前端全局常量定义
 */

/**
 * 应用信息
 */
export const APP_INFO = {
  name: '养老院 AI 监护系统',
  shortName: '护卫AI',
  version: '1.0.0',
  author: 'MaLi',
  description: '智能化养老监护 · 实时告警响应 · AI 辅助决策'
};

/**
 * 路由路径
 */
export const ROUTES = {
  LOGIN: '/login',
  HOME: '/',
  DASHBOARD: '/dashboard',
  ALERTS: '/alerts',
  ELDERS: '/elders',
  CAMERAS: '/cameras',
  SCHEDULES: '/schedules',
  AGENT: '/agent',
  SETTINGS: '/settings',
  AUDIT: '/audit',
  MESSAGES: '/messages'
};

/**
 * 存储 Key
 */
export const STORAGE_KEYS = {
  TOKEN: 'elderly_token',
  USER: 'elderly_user',
  THEME: 'elderly_theme',
  LANGUAGE: 'elderly_language',
  SIDEBAR_COLLAPSED: 'elderly_sidebar_collapsed'
};

/**
 * 事件名称
 */
export const EVENTS = {
  // 用户事件
  USER_LOGIN: 'user:login',
  USER_LOGOUT: 'user:logout',
  USER_UPDATE: 'user:update',
  
  // 告警事件
  ALERT_NEW: 'alert:new',
  ALERT_UPDATE: 'alert:update',
  ALERT_CONFIRM: 'alert:confirm',
  
  // 消息事件
  MESSAGE_NEW: 'message:new',
  MESSAGE_READ: 'message:read',
  
  // 系统事件
  SYSTEM_ERROR: 'system:error',
  SYSTEM_NOTIFY: 'system:notify',
  NETWORK_OFFLINE: 'network:offline',
  NETWORK_ONLINE: 'network:online'
};

/**
 * 正则表达式
 */
export const REGEX = {
  // 手机号（中国大陆）
  PHONE: /^1[3-9]\d{9}$/,
  
  // 身份证号
  ID_CARD: /(^\d{15}$)|(^\d{18}$)|(^\d{17}(\d|X|x)$)/,
  
  // 邮箱
  EMAIL: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
  
  // 用户名（4-20位字母数字下划线）
  USERNAME: /^[a-zA-Z0-9_]{4,20}$/,
  
  // 密码（6-20位）
  PASSWORD: /^.{6,20}$/,
  
  // 房间号（数字+字母）
  ROOM_NO: /^[A-Z0-9-]+$/,
  
  // URL
  URL: /^https?:\/\/.+/,
  
  // IP 地址
  IP: /^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$/
};

/**
 * HTTP 状态码
 */
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  TOO_MANY_REQUESTS: 429,
  SERVER_ERROR: 500,
  BAD_GATEWAY: 502,
  SERVICE_UNAVAILABLE: 503,
  GATEWAY_TIMEOUT: 504
};

/**
 * 消息类型
 */
export const MESSAGE_TYPES = {
  ALERT: 'alert',
  SYSTEM: 'system',
  SCHEDULE: 'schedule',
  CAMERA: 'camera',
  MAINTENANCE: 'maintenance'
};

/**
 * 消息优先级
 */
export const MESSAGE_PRIORITY = {
  LOW: 'low',
  NORMAL: 'normal',
  HIGH: 'high',
  URGENT: 'urgent'
};

/**
 * 导出格式
 */
export const EXPORT_FORMATS = {
  CSV: 'csv',
  EXCEL: 'xlsx',
  PDF: 'pdf',
  JSON: 'json'
};

/**
 * 时间范围快捷选项
 */
export const TIME_RANGES = {
  TODAY: { label: '今天', value: 'today' },
  YESTERDAY: { label: '昨天', value: 'yesterday' },
  LAST_7_DAYS: { label: '最近7天', value: '7days' },
  LAST_30_DAYS: { label: '最近30天', value: '30days' },
  THIS_WEEK: { label: '本周', value: 'week' },
  THIS_MONTH: { label: '本月', value: 'month' },
  CUSTOM: { label: '自定义', value: 'custom' }
};

/**
 * 权限定义
 */
export const PERMISSIONS = {
  // 告警管理
  ALERT_VIEW: 'alert:view',
  ALERT_CONFIRM: 'alert:confirm',
  ALERT_DELETE: 'alert:delete',
  ALERT_EXPORT: 'alert:export',
  
  // 老人档案
  ELDER_VIEW: 'elder:view',
  ELDER_CREATE: 'elder:create',
  ELDER_UPDATE: 'elder:update',
  ELDER_DELETE: 'elder:delete',
  
  // 摄像头管理
  CAMERA_VIEW: 'camera:view',
  CAMERA_CREATE: 'camera:create',
  CAMERA_UPDATE: 'camera:update',
  CAMERA_DELETE: 'camera:delete',
  
  // 排班管理
  SCHEDULE_VIEW: 'schedule:view',
  SCHEDULE_CREATE: 'schedule:create',
  SCHEDULE_UPDATE: 'schedule:update',
  SCHEDULE_DELETE: 'schedule:delete',
  
  // 系统设置
  SETTING_VIEW: 'setting:view',
  SETTING_UPDATE: 'setting:update',
  
  // 审计日志
  AUDIT_VIEW: 'audit:view',
  
  // 系统管理
  SYSTEM_MANAGE: 'system:manage'
};

/**
 * 用户角色
 */
export const USER_ROLES = {
  ADMIN: 'admin',
  NURSE: 'nurse',
  DOCTOR: 'doctor',
  STAFF: 'staff'
};

/**
 * 审计操作类型
 */
export const AUDIT_OPERATIONS = {
  CREATE: 'create',
  UPDATE: 'update',
  DELETE: 'delete',
  CONFIRM: 'confirm',
  EXPORT: 'export',
  LOGIN: 'login',
  LOGOUT: 'logout'
};

/**
 * 通知渠道
 */
export const NOTIFY_CHANNELS = {
  HI: 'hi',           // 如流服务号
  CARD: 'card',       // 如流工作卡
  SMS: 'sms',         // 短信
  EMAIL: 'email',     // 邮箱
  CHAT: 'chat',       // 聊天
  GROUP: 'group'      // 群消息
};

/**
 * 动画时长
 */
export const ANIMATION_DURATION = {
  FAST: 150,
  NORMAL: 300,
  SLOW: 500
};

/**
 * 层级 Z-Index
 */
export const Z_INDEX = {
  MODAL: 1000,
  DROPDOWN: 900,
  TOOLTIP: 800,
  HEADER: 700,
  SIDEBAR: 600,
  LOADING: 500
};

export default {
  APP_INFO,
  ROUTES,
  STORAGE_KEYS,
  EVENTS,
  REGEX,
  HTTP_STATUS,
  MESSAGE_TYPES,
  MESSAGE_PRIORITY,
  EXPORT_FORMATS,
  TIME_RANGES,
  PERMISSIONS,
  USER_ROLES,
  AUDIT_OPERATIONS,
  NOTIFY_CHANNELS,
  ANIMATION_DURATION,
  Z_INDEX
};
