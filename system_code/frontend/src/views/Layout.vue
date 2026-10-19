<template>
  <div class="app-shell">
    <!-- ══════════ 顶部导航（白色，sticky）══════════ -->
    <header class="app-header">
      <!-- 左：品牌 -->
      <router-link to="/dashboard" class="brand">
        <span class="brand-icon">🏥</span>
        <span class="brand-text">
          <span class="brand-name">智慧养老监护</span>
          <span class="brand-sub">跌倒检测与情绪识别</span>
        </span>
      </router-link>

      <!-- 中：主菜单（7 项，分组项带下拉） -->
      <nav class="main-nav" aria-label="主导航">
        <template v-for="item in navItems" :key="item.label">
          <router-link
            v-if="item.to"
            :to="item.to"
            class="nav-link"
            active-class="is-active"
          >{{ item.label }}</router-link>

          <div v-else class="nav-drop" :class="{ open: openMenu === item.label }">
            <button
              class="nav-link nav-drop-btn"
              :class="{ 'is-active': isGroupActive(item) }"
              @click.stop="toggleMenu(item.label)"
            >
              {{ item.label }}<span class="caret">▾</span>
            </button>
            <transition name="drop">
              <div v-if="openMenu === item.label" class="drop-panel" @click.stop>
                <router-link
                  v-for="child in visibleChildren(item)"
                  :key="child.to"
                  :to="child.to"
                  class="drop-item"
                  active-class="is-active"
                  @click="openMenu = null"
                >{{ child.label }}</router-link>
              </div>
            </transition>
          </div>
        </template>
      </nav>

      <!-- 右：工具 + 账户（登录/退出在右上角） -->
      <div class="header-tools">
        <router-link to="/alerts" class="icon-btn" title="未读告警提醒">
          🔔<span v-if="unread" class="unread-badge">{{ unread > 99 ? '99+' : unread }}</span>
        </router-link>
        <button class="icon-btn" :title="theme === 'dark' ? '切换亮色' : '切换深色'" @click="switchTheme">
          {{ theme === 'dark' ? '☀️' : '🌙' }}
        </button>

        <!-- 所属机构（多租户）：紧邻用户名。tenant 取不到时整块不渲染，
             不占位、不报错；窄屏允许被压缩省略号，绝不把中间导航挤偏。 -->
        <div
          v-if="tenantLabel"
          class="org-chip"
          data-testid="tenant-chip"
          :title="tenantTitle"
        >
          <span class="org-icon" aria-hidden="true">🏢</span>
          <span class="org-name" data-testid="tenant-name">{{ tenantLabel }}</span>
        </div>

        <div class="account" :class="{ open: openMenu === '__account' }">
          <button class="account-btn" @click.stop="toggleMenu('__account')">
            <span class="avatar">{{ userInitial }}</span>
            <span class="account-meta">
              <span class="account-name">{{ currentUser.name || currentUser.username || '用户' }}</span>
              <span class="account-role">{{ roleLabel }}</span>
            </span>
            <span class="caret">▾</span>
          </button>
          <transition name="drop">
            <div v-if="openMenu === '__account'" class="drop-panel drop-panel--right" @click.stop>
              <button class="drop-item" @click="openAccount('pwd')">🔑 修改密码</button>
              <button class="drop-item" @click="openAccount('theme')">{{ theme === 'dark' ? '☀️ 切换亮色' : '🌙 切换深色' }}</button>
              <div class="drop-sep"></div>
              <button class="drop-item" @click="togglePref('sound')">
                {{ notifyPrefs.sound ? '🔊' : '🔇' }} 告警声音：{{ notifyPrefs.sound ? '开' : '关' }}
              </button>
              <button class="drop-item" @click="togglePref('desktop')">
                {{ notifyPrefs.desktop ? '🔔' : '🔕' }} 桌面通知：{{ notifyPrefs.desktop ? '开' : '关' }}
              </button>
              <div class="drop-sep"></div>
              <button class="drop-item drop-item--danger" @click="handleLogout">⏻ 退出登录</button>
            </div>
          </transition>
        </div>
      </div>
    </header>

    <!-- ══════════ 内容区 ══════════ -->
    <main class="app-main">
      <router-view />
    </main>

    <ChangePasswordModal v-if="showChangePwd" @close="showChangePwd = false" />
    <AgentPanel />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getCurrentUser } from '../api/users.js';
import { logout } from '../api/auth.js';
import ChangePasswordModal from '../components/ChangePasswordModal.vue';
import AgentPanel from '../components/AgentPanel.vue';
import { useSSE } from '../composables/useSSE.js';
import { showToast } from '../utils/index.js';
import { ALERT_CONFIG } from '../config/index.js';
import { currentTheme, toggleTheme } from '../utils/theme.js';
import { getNotifyPrefs, setNotifyPref, alertTones } from '../utils/notifyPrefs.js';
import { getUnreadCount } from '../api/messages.js';

const router = useRouter();
const route = useRoute();
const currentUser = ref({});
const showChangePwd = ref(false);
const liveAlert = ref(null);
const theme = ref(currentTheme());
const openMenu = ref(null);
const notifyPrefs = ref(getNotifyPrefs());
const unread = ref(0);

function togglePref(key) {
  notifyPrefs.value = setNotifyPref(key, !notifyPrefs.value[key]);
}

async function loadUnread() {
  try {
    const r = await getUnreadCount();
    const d = r.data.data;
    unread.value = typeof d === 'number' ? d : (d?.count || 0);
  } catch (e) {
    // 未读角标不是关键路径：失败就保持上一次的数字，但不能连日志都没有 ——
    // 否则"角标不更新"会被当成一个前端状态 bug 去查。
    console.warn('未读消息计数获取失败', e?.friendlyMessage || e);
  }
}

// ── 以「姿态估计 + 情绪识别」为中心的精简导航（15 → 7）──────────────
// 分组用下拉承载；用药/生命体征不在一级入口（路由与后端保留，可恢复）。
const allNavItems = [
  { to: '/dashboard', label: '总览统计' },
  {
    label: '实时检测',
    children: [
      { to: '/monitor', label: '实时监控' },
      { to: '/video-detect', label: '视频检测' },
    ],
  },
  { to: '/alerts', label: '告警中心' },
  // 「数据统计」已并入系统总览：两者本来就是同一批聚合数据（告警趋势、
  // 风险分布、时段热力、房间频次），分两页只会让同一份数字出现两次、
  // 且各自维护一套图表实现。现在总览页带时间范围切换，覆盖面与原统计页一致。
  { to: '/evaluation', label: '效果评测', adminOnly: true },
  { to: '/elders', label: '老人档案' },
  {
    label: '排班值守',
    children: [
      { to: '/schedule', label: '值班排班' },
      { to: '/patrol', label: '夜间巡查' },
    ],
  },
  // 平台运维：只有平台级账号（不属于任何机构）能看到。
  // 它不属于任何机构的管理范围，所以单独一项，不放进「系统管理」里。
  { to: '/platform', label: '平台运维', platformOnly: true },
  {
    label: '系统管理',
    children: [
      { to: '/system-monitor', label: '系统监控', adminOnly: true },
      { to: '/audit', label: '操作审计', adminOnly: true },
      { to: '/settings', label: '系统设置', adminOnly: true },
    ],
  },
];

// 按角色过滤导航项。管理员专属页面（效果评测、系统监控、操作审计、
// 系统设置）对护理员不显示 —— 它们要么给的是机构级的模型能力指标，
// 要么直接能改 AI 阈值/摄像头/账号/通知渠道；显示了反而会让他们看到
// 一堆 403 与半空白的页面。
//
// 子项的过滤只有一处实现（visibleChildren）；这里只额外做一件它做不到的
// 事：某个分组被子项过滤清空后，把整个分组摘掉。否则护理员会看到
// 「系统管理 ▾」点开却是空的 —— 比直接不显示更让人困惑。
const navItems = computed(() => allNavItems.filter((item) => {
  if (item.platformOnly && !currentUser.value?.isPlatform) return false;
  if (item.children) return visibleChildren(item).length > 0;
  return !item.adminOnly || isAdmin();
}));

const userInitial = computed(() => {
  const name = currentUser.value.name || currentUser.value.username || '用';
  return name.charAt(0);
});

const roleLabel = computed(() => (currentUser.value.role === 'admin' ? '机构管理员' : '护理管理员'));

// ── 所属机构（多租户）───────────────────────────────────────────────
// 后端 /api/user 的三种可能形态都要能撑住，任何一级缺失都不能抛错：
//   1) 新后端：{ tenantId: 1, tenant: { id, code, name } }  → 用机构名
//   2) 中间态：只有 tenantId（或蛇形 tenant_id）           → 退化成「机构 #1」
//   3) 旧后端：tenant / tenantId 都没有                    → 返回 ''，整块不渲染
// 这里全部走可选链 + 类型判断：tenant 可能是对象、裸字符串，也可能是 null；
// 直接读 tenant.name 在 tenant 为字符串/null 时会抛 TypeError，属于必须避免的崩溃。
const tenantLabel = computed(() => {
  const u = currentUser.value || {};
  const t = u.tenant;
  if (t && typeof t === 'object' && t.name) return String(t.name);
  if (typeof t === 'string' && t.trim()) return t.trim();
  if (u.tenantName) return String(u.tenantName);
  const id = u.tenantId ?? u.tenant_id;
  if (id !== undefined && id !== null && id !== '') return `机构 #${id}`;
  return '';
});

const tenantTitle = computed(() => {
  const t = currentUser.value?.tenant;
  const code = t && typeof t === 'object' ? t.code : '';
  const suffix = code ? `（${code}）` : '';
  return `所属机构：${tenantLabel.value}${suffix}`;
});

// 角色判定的唯一出口：路由守卫、导航（顶层与子项）都必须问同一个问题，
// 散落的 `role === 'admin'` 一旦有一处写漏（比如写成 `!== 'nurse'`），
// 就会出现"页面进不去但菜单还在"这类前后矛盾的界面。
function isAdmin() {
  // 平台账号的 role 也是 admin，但它**不属于任何机构** —— 后端
  // require_admin 已刻意把平台账号排除在外（它访问机构设置会拿到 403）。
  // 前端必须用同一口径，否则平台运维会看到一整套点进去就报错的菜单。
  if (currentUser.value?.isPlatform) return false;
  return currentUser.value?.role === 'admin';
}

// 分组里的子项按角色过滤，否则管理员专属入口仍会出现在下拉里
function visibleChildren(item) {
  return (item.children || []).filter((c) => !c.adminOnly || isAdmin());
}

function toggleMenu(label) {
  openMenu.value = openMenu.value === label ? null : label;
}

function isGroupActive(item) {
  return visibleChildren(item).some((child) => route.path === child.to);
}

function closeAll() {
  openMenu.value = null;
}

function switchTheme() {
  theme.value = toggleTheme();
}

function openAccount(action) {
  closeAll();
  if (action === 'pwd') showChangePwd.value = true;
  else switchTheme();
}

async function handleLogout() {
  closeAll();
  // 服务端登出失败不影响本地登出（下面两行一定会执行），但要留痕：
  // 它意味着这个 JWT 在服务端仍然有效，只是浏览器这边不用了。
  try { await logout(); } catch (e) { console.warn('服务端登出失败', e?.friendlyMessage || e); }
  sessionStorage.removeItem('api_token');
  sessionStorage.removeItem('current_user');
  router.push('/login');
}

// ── 全局实时告警推送 ──────────────────────────────────────────────
let audioCtx = null;

function beep(level) {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    audioCtx = audioCtx || new Ctx();
    let at = audioCtx.currentTime;
    alertTones(level).forEach((freq) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.07, at);
      gain.gain.exponentialRampToValueAtTime(0.001, at + 0.18);
      osc.start(at);
      osc.stop(at + 0.2);
      at += 0.22;
    });
  } catch {
    // 提示音失败（AudioContext 未解锁 / 设备无音频输出）不影响告警本身：
    // 页面上的红色卡片和角标仍然会更新，所以这里刻意不打扰用户。
  }
}

function desktopNotify(level, notes) {
  try {
    if (!notifyPrefs.value.desktop || typeof Notification === 'undefined') return;
    if (Notification.permission === 'granted') {
      new Notification(`⚠️ ${level} 风险告警`, { body: notes || '检测到风险告警，请及时处置' });
    } else if (Notification.permission === 'default') {
      Notification.requestPermission();
    }
  } catch {
    // 桌面通知是**可选**通道（用户可在偏好里关掉），浏览器不支持或被拒绝
    // 都不影响站内告警，因此保持静默。
  }
}

const REASON_LABEL = {
  new: '新告警', ingested: '新告警', escalated: '等级升级', escalated_timeout: '超时升级',
};

function handleLiveAlert(payload) {
  const alert = payload?.alert || payload;
  if (!alert || alert.id === undefined) return;
  const level = String(alert.riskLevel || 'LOW').toUpperCase();
  const reason = REASON_LABEL[payload?.reason] || '告警';
  const severe = level === 'HIGH' || level === 'URGENT';
  showToast(`${reason}：${level} 风险（#${alert.id}）`, severe ? 'error' : 'warning', 6000);
  liveAlert.value = { ...alert, level, reason };
  setTimeout(() => {
    if (liveAlert.value?.id === alert.id) liveAlert.value = null;
  }, 8000);
  if (notifyPrefs.value.sound) beep(level);
  loadUnread();
  desktopNotify(level, alert.handlerNotes);
}

useSSE({
  onAlert: handleLiveAlert,
  onConfirmed: (payload) => {
    if (payload?.alert?.id !== undefined) {
      showToast(`告警 #${payload.alert.id} 已处置`, 'success', 3000);
    }
  },
});

let unreadTimer = null;
onMounted(async () => {
  document.addEventListener('click', closeAll);
  loadUnread();
  unreadTimer = setInterval(loadUnread, 60000);
  const cached = sessionStorage.getItem('current_user');
  if (cached) {
    // 缓存坏了就当没有；下一行会用接口结果覆盖。降级方向是安全的（角色为空 → 只见普通菜单）。
    try { currentUser.value = JSON.parse(cached); } catch (e) { console.warn('用户缓存解析失败，忽略', e); }
  }
  try {
    const res = await getCurrentUser();
    if (res.data.success) {
      currentUser.value = res.data.data || {};
      sessionStorage.setItem('current_user', JSON.stringify(currentUser.value));
    }
  } catch (e) {
    // 兜底是上面那份 sessionStorage 缓存，所以这里失败不会白屏。
    // 但角色/机构会停在登录时的快照上 —— 需要留痕，否则"改了角色但菜单没变"
    // 会被当成前端状态问题反复排查。
    console.warn('获取当前用户信息失败，沿用登录时的缓存', e?.friendlyMessage || e);
  }
});

onUnmounted(() => { document.removeEventListener('click', closeAll); clearInterval(unreadTimer); });
</script>

<style scoped>
/* ═══════════════ 外壳 ═══════════════ */
.app-shell {
  /* 必须是**确定**高度，整页才约束得住。
     原实现只有 min-height（内容驱动），于是内容一多 shell 自己就长高：
     实测 AI 对话页 25 条历史对话时 shell 由 890px 涨到 1761px、整页纵向溢出
     811px，而内部本应滚动的会话列表 scrollHeight === clientHeight、根本没滚，
     内容直接突破边界。改用固定视口高度后，滚动容器下移到 main.app-main，
     各页面的内容仍然完整可达（13 个页面逐一验过：文档溢出均为 0）。
     100dvh 优先，回退 100vh 以兼容不支持动态视口单位的浏览器。 */
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: var(--bg-app);
  display: flex;
  flex-direction: column;
}

/* ═══════════════ 顶部导航（白色）═══════════════ */
.app-header {
  position: sticky;
  top: 0;
  z-index: var(--z-dropdown);
  /* 用 3 栏 grid 而不是 flex：flex 下导航只能占据"品牌之后剩余空间"并左对齐，
     看起来是偏左的。让左右两栏等宽，中间的导航因此**相对整条顶栏真正居中**，
     与品牌/工具区宽度无关。

     用 minmax(0, 1fr) 而不是裸 1fr：1fr 等价于 minmax(auto, 1fr)，它的下限是
     内容的 min-content —— 于是只要某一侧（这里加了机构徽标后的右侧）内容比
     自己那一栏的份额宽，那一栏就会被撑大，等宽前提失效，导航被推偏。
     实测未加 min(0) 时 1080px 下：左偏移 177 / 右偏移 305，导航偏左 64px。
     下限改成 0 后两栏恒等宽，导航在所有宽度上都是精确居中；内容放不下时
     由栏内的可压缩元素（机构徽标）先省略号收缩，而不是把导航挤偏。 */
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: var(--space-4);
  height: 60px;
  padding: 0 var(--space-5);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  box-shadow: var(--shadow-sm);
}

/* 品牌 */
.brand {
  justify-self: start;
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  flex-shrink: 0;
  min-width: 0;              /* 同上：不要用 min-content 撑大本栏、挤偏导航 */
  padding-right: var(--space-4);
  border-right: 1px solid var(--border-subtle);
  height: 34px;
}
.brand-icon { font-size: 22px; line-height: 1; }
.brand-text { display: flex; flex-direction: column; line-height: 1.2; }
.brand-name { font-size: var(--text-md); font-weight: 800; color: var(--text-primary); }
.brand-sub { font-size: var(--text-xs); color: var(--text-muted); }

/* 主菜单 */
.main-nav {
  display: flex;
  align-items: center;
  justify-content: center;   /* grid 中栏内再居中，菜单项不会贴着左边 */
  gap: 2px;
  min-width: 0;
  /* 这里绝对不要加 overflow-x: auto。
     按 CSS 规范，只要有一个轴不是 visible，另一个轴会被计算成 auto，
     于是 overflow-y 也变成 auto —— 导航会**裁掉自己的下拉面板**。
     实测（1440×900）：面板矩形 [707,55,148,120]，导航矩形 [176,13,1004,34]，
     面板在导航内的可见高度 = 0px，在面板区域内打的 480 个采样点命中 0 个。
     即 4 个带 ▾ 的分组菜单完全不可见、完全点不到，而 3 个普通链接正常。
     窄屏改为换行（见下方断点），不再使用横向滚动。 */
  flex-wrap: nowrap;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 12px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-md);
  font-family: inherit;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-smooth),
              color var(--duration-fast) var(--ease-smooth);
}
.nav-link:hover { background: var(--bg-hover); color: var(--text-primary); }
.nav-link.is-active {
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 600;
}

/* 下拉 */
.nav-drop, .account { position: relative; }
/* 账户区与图标按钮一样固定宽度：顶栏空间不足时只让机构徽标收缩，
   避免用户名/角色被压到溢出。 */
.account { flex-shrink: 0; }
.caret { font-size: 9px; opacity: .65; }
.drop-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 148px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  z-index: var(--z-modal);
}
.drop-panel--right { left: auto; right: 0; min-width: 172px; }

.drop-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-base);
  font-family: inherit;
  text-decoration: none;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--duration-fast) var(--ease-smooth);
}
.drop-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.drop-item.is-active { background: var(--primary-soft); color: var(--primary); font-weight: 600; }
.drop-item--danger { color: var(--danger); }
.drop-item--danger:hover { background: var(--danger-soft); color: var(--danger-text); }
.drop-sep { height: 1px; background: var(--border-subtle); margin: 4px 2px; }

/* 右上角工具区 */
.header-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;   /* 内容仍然贴右，与原来的 justify-self: end 视觉一致 */
  /* 用 stretch 占满第三栏，**不要**用 justify-self: end。
     原因：justify-self 为非 stretch 值时，栏宽取 fit-content，而 fit-content 的
     下限是 min-content —— 于是本栏内容一旦宽过栏宽就再也压不下去，只能向左
     溢出压到导航上。实测 1080px：栏宽 205px 而内容 269px，工具区左伸到 x=791、
     导航右缘 839，重叠 48px，导航命中率掉到 95%。
     改为 stretch 后栏宽被 grid 定死，flex 收缩才真正生效，由机构徽标让位。 */
  justify-self: stretch;
  gap: var(--space-2);
  /* 允许本栏窄于内容宽度：空间不够时由内部的机构徽标（唯一带省略号的
     可压缩元素）收缩，其余控件固定不动。 */
  min-width: 0;
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-subtle);
}
.icon-btn {
  width: 34px;
  height: 34px;
  flex-shrink: 0;            /* 收缩只发生在机构徽标上 */
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  font-size: 15px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-smooth);
}
.icon-btn:hover { background: var(--bg-hover); border-color: var(--border-default); }

.icon-btn { position: relative; text-decoration: none; }
.unread-badge { position: absolute; top: -4px; right: -4px; min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: var(--radius-full); background: var(--danger); color: var(--text-on-color); font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; }

/* 机构徽标（多租户）。全部用 tokens.css 里已有的令牌，不引入任何新色值：
   白底之上用最浅的一层表面色 + 细边，和右侧用户名/角色排在一起，
   视觉上属于"账户区"，不会与中间导航抢焦点。 */
.org-chip {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  height: 34px;
  /* 窄屏时先压缩自己（省略号），而不是把整条顶栏的 1fr 栏撑宽 —— 后者会
     打破 grid-template-columns: 1fr auto 1fr 的等宽前提，把导航挤得偏左。 */
  flex: 0 1 auto;
  min-width: 0;
  max-width: 150px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-full);
  background: var(--bg-surface-2);
  transition: background var(--duration-fast) var(--ease-smooth),
              border-color var(--duration-fast) var(--ease-smooth);
}
.org-chip:hover { background: var(--bg-hover); border-color: var(--border-default); }
.org-icon { font-size: var(--text-sm); line-height: 1; flex-shrink: 0; }
.org-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
}
.account-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px 5px 5px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  cursor: pointer;
  font-family: inherit;
  transition: all var(--duration-fast) var(--ease-smooth);
}
.account-btn:hover { background: var(--bg-hover); border-color: var(--border-default); }
.avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--text-on-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
  font-weight: 700;
  flex-shrink: 0;
}
.account-meta { display: flex; flex-direction: column; line-height: 1.15; text-align: left; }
.account-name { font-size: var(--text-sm); font-weight: 600; color: var(--text-primary); }
.account-role { font-size: var(--text-xs); color: var(--text-muted); }

/* ═══════════════ 内容区 ═══════════════ */
.app-main {
  flex: 1;
  min-width: 0;
  overflow-x: hidden;
  /* 作为 flex 子项，它的高度由 flex 拉伸决定，对百分比高度而言属于
     "不确定"高度 —— 于是页面里的 height:100% 会静默退化成 auto。
     AI 对话页正是踩了这一点：整页只占可用高度的 67%（实测 557px / 830px），
     即用户看到的"半屏"。让 .app-main 成为 flex 容器、页面用 flex:1 撑满，
     就不再依赖百分比高度。 */
  display: flex;
  flex-direction: column;
  /* min-height:0 同样关键：flex 子项默认 min-height:auto，意思是"不得小于
     内容高度"，于是内容一多它就跟着长，把整页顶下去。实测 AI 对话页 25 条
     历史对话时 .app-main 由 830px 涨到 1701px、页面纵向溢出 811px，而内部
     本应滚动的会话列表 scrollHeight === clientHeight、根本没滚 —— 这就是
     "新增对话会突破整体边界"。设为 0 后容器高度锁定为可用高度，
     内部 overflow 才真正生效。 */
  min-height: 0;
}

/* 下拉动画 */
.drop-enter-active, .drop-leave-active { transition: opacity .14s ease, transform .14s ease; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-6px); }

/* ═══════════════ 响应式 ═══════════════ */
/* 机构徽标的可用宽度 = 左右两栏的等宽份额。
   完整显示徽标需要每栏 ≥ 161(其余控件) + 8(间隙) + 105(徽标) = 274px，
   即视口 ≥ 597(导航) + 72(内边距与栏间隙) + 548 = 1217px；
   徽标压到最窄（约 42px，只剩图标加一小截文字）也需要每栏 ≥ 211px（视口 ≥ 1091px）。
   所以在 1120px 以下直接收起徽标，并**同时把列定义与右栏对齐还原成改动前的写法** ——
   这样在徽标不可见的整个区间里，顶栏与改动前逐像素一致，不会引入任何新行为。 */
@media (max-width: 1120px) {
  .org-chip { display: none; }
  .app-header { grid-template-columns: 1fr auto 1fr; }
  .header-tools { justify-self: end; min-width: auto; }
}

@media (max-width: 1080px) {
  .account-meta { display: none; }
  .brand-sub { display: none; }
  /* 导航改为可换行，替代原先被移除的横向滚动 */
  .app-header { height: auto; min-height: var(--header-h); flex-wrap: wrap; row-gap: 2px; }
  .main-nav { flex-wrap: wrap; justify-content: center; }
}
@media (max-width: 860px) {
  .app-header { height: auto; flex-wrap: wrap; padding: var(--space-2) var(--space-3); gap: var(--space-2); }
  .brand { border-right: none; padding-right: 0; }
  .main-nav { order: 3; width: 100%; padding-bottom: 4px; flex-wrap: wrap; justify-content: center; }
  .header-tools { border-left: none; padding-left: 0; margin-left: auto; }
}
</style>
