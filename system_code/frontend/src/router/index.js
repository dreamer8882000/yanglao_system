import { createRouter, createWebHistory } from 'vue-router';
import Layout from '../views/Layout.vue';

const routes = [
  {
    path: '/login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'monitor', component: () => import('../views/Monitor.vue') },
      { path: 'video-detect', component: () => import('../views/VideoDetect.vue') },
      { path: 'elders', component: () => import('../views/Elders.vue') },
      { path: 'alerts', component: () => import('../views/Alerts.vue') },
      { path: 'evaluation', component: () => import('../views/Evaluation.vue'), meta: { requiresAdmin: true } },
      { path: 'schedule', component: () => import('../views/Schedule.vue') },
      { path: 'audit', component: () => import('../views/Audit.vue'), meta: { requiresAdmin: true } },
      { path: 'settings', component: () => import('../views/Settings.vue'), meta: { requiresAdmin: true } },
      { path: 'agent', component: () => import('../views/Agent.vue') },
      { path: 'system-monitor', component: () => import('../views/SystemMonitor.vue'), meta: { requiresAdmin: true } },
      // 平台运维（跨机构只读）。与机构管理员的「系统管理」是两种身份：
      // 机构管理员只能看到自己的机构，跨机构视图只对平台账号开放。
      { path: 'platform', component: () => import('../views/Platform.vue'), meta: { requiresPlatform: true } },
      { path: 'patrol', component: () => import('../views/Patrol.vue') },
      { path: 'medication', component: () => import('../views/Medication.vue') },
      { path: 'vital-sign', component: () => import('../views/VitalSign.vue') },
    ]
  }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.VITE_BASE_PATH || '/'),
  routes
});

function currentRole() {
  try {
    return JSON.parse(sessionStorage.getItem('current_user') || '{}').role || '';
  } catch { return ''; }
}

function isPlatform() {
  try {
    return JSON.parse(sessionStorage.getItem('current_user') || '{}').isPlatform === true;
  } catch { return false; }
}

router.beforeEach((to) => {
  const token = sessionStorage.getItem('api_token');
  if (to.meta.requiresAuth && !token) {
    return { path: '/login' };
  }
  if (to.meta.public && token && to.path === '/login') {
    return { path: '/dashboard' };
  }
  // 管理员专属页面：效果评测给出的是**机构级的模型能力与运营质量指标**
  // （召回率、误报率、按姿态/表情的归因）。护理员的职责是处置告警，
  // 这些数字对他们的日常工作没有用；直接在路由层拦住，也避免误入后
  // 看到一堆接口 403、页面半空白。
  //
  // 系统监控 / 操作审计 / 系统设置同样是管理员专属：前两者是机构级的
  // 运行与合规视图，后者能改 AI 阈值、摄像头、账号与通知渠道 —— 都是
  // 会改变全院行为的管理动作。之前只挡住了效果评测，护理员可以直接
  // 输入 URL 打开这三个页面并成功读写（实测 200，无 403），属于越权。
  // 前端守卫只是第一道（避免误入半空白页），后端才是真正的权限边界。
  // 与后端同口径：平台账号（role 也是 admin 但不属于任何机构）不算机构管理员，
  // 它对 /api/audit、/api/settings、/api/monitor/performance 会拿到 403。
  if (to.meta.requiresAdmin && (currentRole() !== 'admin' || isPlatform())) {
    return { path: '/dashboard' };
  }
  // 平台页对机构管理员同样关闭：管理员访问 /platform/* 接口会拿到 403，
  // 放进来只会看到一堆错误。默认拒绝，且与后端 require_platform 同一口径。
  if (to.meta.requiresPlatform && !isPlatform()) {
    return { path: '/dashboard' };
  }
  return true;
});

export default router;
