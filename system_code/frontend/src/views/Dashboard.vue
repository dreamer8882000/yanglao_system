<template>
  <div class="page dash">
    <!-- ═══════ 页头（与全站一致：标题 + 副标题 + 右侧状态）═══════ -->
    <div class="page-header">
      <div class="page-header-left">
        <div>
          <h1>监护总览</h1>
          <p class="page-sub">
            待处置 {{ stats.pending || 0 }} 条 · 今日告警 {{ stats.todayTotal || 0 }} 条
            · 在档老人 {{ stats.elderCount || 0 }} 位
          </p>
        </div>
      </div>
      <div class="page-actions">
        <span class="chip">值班 {{ onDuty.length ? onDuty.map(d => d.name || d.userName).join('、') : '暂无排班' }}</span>
        <!-- 时间范围切换：原先在「数据统计」页，合并过来后趋势/分布/热力图共用它 -->
        <div class="seg">
          <button
            v-for="r in RANGES" :key="r.value"
            class="seg-btn" :class="{ on: range === r.value }"
            @click="setRange(r.value)"
          >{{ r.label }}</button>
        </div>
      </div>
    </div>

    <!-- ═══════ 顶部两个主卡（1:1，文字居中）═══════ -->
    <!-- 值班时唯一必须立刻知道的两个数字：有多少条等着处理、其中多少是紧急的。
         原先首屏铺了 8 张指标卡，重点被摊平；现在其余指标下移为等宽模块。 -->
    <div class="hero-grid">
      <div class="hero-card hero-pending" :class="{ active: (stats.pending || 0) > 0 }">
        <div class="hero-label">待处置告警</div>
        <div class="hero-value">{{ stats.pending || 0 }}</div>
        <div class="hero-foot">
          {{ (stats.pending || 0) > 0 ? '需要护理员跟进' : '队列已清空' }}
        </div>
      </div>
      <div class="hero-card hero-high" :class="{ active: (stats.todayHigh || 0) > 0 }">
        <div class="hero-label">今日高危</div>
        <div class="hero-value">{{ stats.todayHigh || 0 }}</div>
        <div class="hero-foot">
          今日告警 {{ stats.todayTotal || 0 }} 条 · 已处置 {{ handledToday }} 条
        </div>
      </div>
    </div>

    <!-- ═══════ 图表行（2:1）═══════ -->
    <div class="grid-1-1">
      <section class="panel">
        <div class="panel-head">
          <h2>告警趋势</h2>
          <span class="panel-sub">{{ rangeLabel }}</span>
        </div>
        <BarChart :data="trendBars" :height="176" />
      </section>
      <section class="panel">
        <div class="panel-head"><h2>风险等级占比</h2></div>
        <PieChart :items="riskDistribution" :size="140" :unit="rangeShort" />
      </section>
    </div>

    <!-- ═══════ 第二行（1:1）：时段热力 + 房间频次 ═══════ -->
    <!-- 这两张是原「数据统计」页里唯一不与总览重复的内容，也是最能指导
         实际排班的两张：什么时段高发、哪些房间反复报警。 -->
    <div class="grid-1-1">
      <section class="panel">
        <div class="panel-head">
          <h2>高发时段（星期 × 小时）</h2>
          <span class="panel-sub">{{ rangeLabel }}</span>
        </div>
        <Heatmap :data="hourlyHeat" />
      </section>
      <section class="panel">
        <div class="panel-head">
          <h2>房间告警频次</h2>
          <span class="panel-sub">Top {{ roomRank.length }}</span>
        </div>
        <BarList :items="roomRank" :show-share="false" sort="desc" />
      </section>
    </div>

    <!-- ═══════ 第三行（1:1）═══════ -->
    <div class="grid-1-1">
      <section class="panel">
        <div class="panel-head"><h2>处置状态</h2></div>
        <PieChart :items="statusDistribution" :size="140" unit="告警" />
      </section>
      <section class="panel">
        <div class="panel-head"><h2>摄像头在线</h2></div>
        <div class="stat-center">
          <div class="big-num" :class="cameraOnlineRate === 100 && cameras.length ? 'ok' : 'warn'">
            {{ onlineCameras }}<span class="big-sep">/</span>{{ cameras.length || 0 }}
          </div>
          <div class="big-sub">在线率 {{ cameraOnlineRate }}%</div>
        </div>
        <div class="rate-bar"><div class="rate-fill" :style="{ width: cameraOnlineRate + '%' }"></div></div>
        <p class="note">在线 = 最近 90 秒内上报过心跳，未接入的机位不计入</p>
      </section>
    </div>

    <!-- ═══════ 表格行（2:1）═══════ -->
    <div class="grid-1-1">
      <section class="panel">
        <div class="panel-head">
          <h2>告警处置队列</h2>
          <div class="seg">
            <button class="seg-btn" :class="{ on: tab === 'pending' }" @click="tab = 'pending'">
              待处理 {{ pendingAlerts.length }}
            </button>
            <button class="seg-btn" :class="{ on: tab === 'all' }" @click="tab = 'all'">
              最近 {{ recentAlerts.length }}
            </button>
          </div>
        </div>

        <div v-if="loadingAlerts" class="empty">加载中…</div>
        <div v-else-if="!queue.length" class="empty">暂无待处置告警，系统运行正常</div>

        <table v-else class="tbl">
          <thead>
            <tr>
              <th>等级</th>
              <th>位置</th>
              <th>老人</th>
              <th>等待</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in visibleQueue" :key="a.id">
              <td>
                <span class="lvl" :style="levelStyle(a.riskLevel)">{{ a.riskLevel }}</span>
              </td>
              <td>{{ a.roomNo ? a.roomNo + '室' : '—' }}</td>
              <td>{{ a.elderName || '未识别' }}</td>
              <td :class="{ overdue: elapsedMin(a) >= 10 && a.status === 0 }">{{ elapsedText(a) }}</td>
              <td>
                <template v-if="a.status === 0">
                  <button class="btn-xs" @click="openConfirm(a)">处置</button>
                  <button class="btn-xs ghost" @click="markFalse(a)">误报</button>
                </template>
                <span v-else class="done">{{ a.status === 2 ? '误报' : '已处置' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="queue.length > QUEUE_LIMIT" class="more">
          仅显示前 {{ QUEUE_LIMIT }} 条，共 {{ queue.length }} 条
          <router-link to="/alerts" class="more-link">查看全部 →</router-link>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>体征预警</h2>
          <span class="panel-sub">{{ vitalAlerts.length }} 条</span>
        </div>
        <div v-if="vitalError" class="load-error">{{ vitalError }}</div>
        <div v-else-if="!vitalAlerts.length" class="empty">各项体征均在配置范围内</div>
        <ul v-else class="vital-list">
          <li v-for="v in vitalAlerts.slice(0, 6)" :key="v.id" class="vital-item">
            <span class="lvl sm" :style="levelStyle(v.riskLevel)">{{ v.riskLevel }}</span>
            <span class="vital-who">{{ v.roomNo }}室 {{ v.elderName }}</span>
            <span class="vital-what">{{ vitalSummary(v) }}</span>
          </li>
        </ul>
      </section>
    </div>

    <!-- ═══════ 处置弹窗 ═══════ -->
    <div v-if="confirmModal.show" class="modal-mask" @click.self="confirmModal.show = false">
      <div class="modal">
        <h3>处置告警 #{{ confirmModal.alert?.id }}</h3>
        <p class="modal-sub">
          {{ confirmModal.alert?.roomNo }}室 {{ confirmModal.alert?.elderName || '未识别' }}
        </p>
        <textarea v-model="confirmModal.notes" placeholder="处置说明（可选）" rows="3"></textarea>
        <div class="modal-actions">
          <button class="btn-xs ghost" @click="confirmModal.show = false">取消</button>
          <button class="btn-xs" @click="submitConfirm" :disabled="confirmModal.loading">确认处置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { getDashboard, getRecentAlerts, confirmAlert, markAlertFalseAlarm, getStatistics } from '../api/alerts.js';
import { getOnDuty } from '../api/schedules.js';
import { getCameraList } from '../api/cameras.js';
import { getAlertTrends } from '../api/python.js';
import { useSSE } from '../composables/useSSE.js';
import { showToast } from '../utils/index.js';
import { LEVELS_DESC, levelColor } from '../utils/levelColors.js';
import request from '../api/request.js';
import BarChart from '../components/BarChart.vue';
import BarList from '../components/BarList.vue';
import Heatmap from '../components/Heatmap.vue';
import PieChart from '../components/PieChart.vue';

const stats = ref({});
const recentAlerts = ref([]);
const onDuty = ref([]);
const cameras = ref([]);
const trendItems = ref([]);
const statItems = ref([]);
const statRaw = ref({});
const vitalAlerts = ref([]);
// 加载失败时不能显示"一切正常"（见下面 loadAlerts 里的说明）
const vitalError = ref('');
const range = ref('7d');
const RANGES = [
  { value: '7d', label: '近 7 天', short: '近7天' },
  { value: '30d', label: '近 30 天', short: '近30天' },
  { value: '90d', label: '近 90 天', short: '近90天' },
];
const rangeLabel = computed(() => RANGES.find(r => r.value === range.value)?.label || '');
const rangeShort = computed(() => RANGES.find(r => r.value === range.value)?.short || '');

// 星期 × 小时 热力：后端返回 [{dw, hr, cnt}]，转成组件要的 "dw-hr" 字典
const hourlyHeat = computed(() => {
  const out = {};
  for (const it of statRaw.value.hourlyHeat || []) {
    out[`${Number(it.dw)}-${Number(it.hr)}`] = Number(it.cnt || it.count || 0);
  }
  return out;
});

// 房间告警频次
const roomRank = computed(() => (statRaw.value.roomRank || []).map((r, i) => ({
  key: r.roomNo || r.room_no || `#${i}`,
  label: (r.roomNo || r.room_no || '-') + '室',
  value: Number(r.cnt || r.count || 0),
  color: 'var(--primary)',
})));

function setRange(v) { range.value = v; loadAll(); }
const loadingAlerts = ref(false);
const tab = ref('pending');
const confirmModal = ref({ show: false, alert: null, notes: '', loading: false });

// 页面上"先看最严重的"，所以用降序（共享常量，避免每页各写一份顺序）。
// 必须先于 LEVEL_COLOR：后者要遍历它（const 有 TDZ，顺序反了会直接抛错）。
const LEVELS = LEVELS_DESC;
// 等级配色不再在页面里重复定义 —— 唯一来源是 utils/levelColors.js
// （它只返回 var(--level-x)，色值本身在 tokens.css 里按主题定义）。
const LEVEL_COLOR = Object.fromEntries(LEVELS.map((l) => [l, levelColor(l)]));
const VITAL_LABEL = {
  systolic_pressure: '收缩压', diastolic_pressure: '舒张压', heart_rate: '心率',
  temperature: '体温', blood_glucose: '血糖', spo2: '血氧',
};

const RANGE_DAYS = { '7d': 7, '30d': 30, '90d': 90 };
const QUEUE_LIMIT = 6;
const pendingAlerts = computed(() => recentAlerts.value.filter((a) => a.status === 0));
const queue = computed(() => (tab.value === 'pending' ? pendingAlerts.value : recentAlerts.value));
const visibleQueue = computed(() => queue.value.slice(0, QUEUE_LIMIT));
const handledToday = computed(() => recentAlerts.value.filter((a) => a.status === 1).length);
const onlineCameras = computed(() => cameras.value.filter((c) => c.status === 1).length);
const cameraOnlineRate = computed(() =>
  cameras.value.length ? Math.round((onlineCameras.value / cameras.value.length) * 100) : 0);

// 近 7 天趋势 → 堆叠柱。按日期聚合、缺项补 0，否则柱子会错位。
const trendBars = computed(() => {
  const byDate = new Map();
  for (const it of trendItems.value) {
    const key = String(it.date || '').slice(5);
    if (!byDate.has(key)) byDate.set(key, {});
    byDate.get(key)[String(it.riskLevel || '').toUpperCase()] = Number(it.count) || 0;
  }
  return [...byDate.entries()].map(([label, counts]) => ({
    label,
    segments: LEVELS.map((lv) => ({ key: lv, label: lv, value: counts[lv] || 0, color: LEVEL_COLOR[lv] })),
  }));
});

const riskDistribution = computed(() => {
  const agg = {};
  for (const it of statItems.value) {
    const lv = String(it.riskLevel || '').toUpperCase();
    agg[lv] = (agg[lv] || 0) + (Number(it.count) || 0);
  }
  return LEVELS.filter((lv) => agg[lv]).map((lv) => ({
    key: lv, label: lv, value: agg[lv], color: LEVEL_COLOR[lv],
  }));
});

const statusDistribution = computed(() => {
  const agg = { 0: 0, 1: 0, 2: 0 };
  for (const it of statItems.value) {
    const st = Number(it.status);
    if (agg[st] !== undefined) agg[st] += Number(it.count) || 0;
  }
  return [
    { key: 'pending', label: '待处理', value: agg[0], color: 'var(--level-medium)' },
    { key: 'done', label: '已处理', value: agg[1], color: 'var(--level-normal)' },
    { key: 'false', label: '误报', value: agg[2], color: 'var(--text-muted)' },
  ];
});

function levelStyle(level) {
  return { background: LEVEL_COLOR[String(level || '').toUpperCase()] || 'var(--text-muted)',
           color: 'var(--text-on-color)' };
}
function vitalSummary(v) {
  const b = (v.breachedRules || [])[0];
  if (!b) return '—';
  return `${VITAL_LABEL[b.vitalType] || b.vitalType} ${b.value} ${b.direction === 'low' ? '偏低' : '偏高'}`;
}
function elapsedMin(a) {
  if (!a.alertTime || a.status !== 0) return 0;
  return Math.max(0, Math.floor((Date.now() - new Date(a.alertTime).getTime()) / 60000));
}
function elapsedText(a) {
  if (a.status !== 0) return a.status === 2 ? '误报' : '已处置';
  const m = elapsedMin(a);
  return m < 1 ? '刚刚' : m < 60 ? `${m} 分钟` : `${Math.floor(m / 60)} 小时`;
}

function openConfirm(alert) { confirmModal.value = { show: true, alert, notes: '', loading: false }; }

async function submitConfirm() {
  confirmModal.value.loading = true;
  try {
    await confirmAlert(confirmModal.value.alert.id, confirmModal.value.notes);
    showToast('已处置', 'success');
    confirmModal.value.show = false;
    await loadAll();
  } catch (e) { showToast('处置失败', 'error'); }
  confirmModal.value.loading = false;
}

async function markFalse(alert) {
  try {
    await markAlertFalseAlarm(alert.id, '护士标注：误报');
    showToast(`告警 #${alert.id} 已标记为误报`, 'success');
    await loadAll();
  } catch (e) { showToast('标记失败', 'error'); }
}

async function loadAll() {
  loadingAlerts.value = true;
  const [dashRes, alertRes, dutyRes, camRes, trendRes, statRes, vitalRes] = await Promise.allSettled([
    getDashboard(), getRecentAlerts(20), getOnDuty(), getCameraList(),
    getAlertTrends(RANGE_DAYS[range.value] || 7), getStatistics({ range: range.value }),
    request.get('/vital-signs/alerts'),
  ]);
  if (dashRes.status === 'fulfilled') stats.value = dashRes.value.data.data || {};
  if (alertRes.status === 'fulfilled') recentAlerts.value = alertRes.value.data.data || [];
  if (dutyRes.status === 'fulfilled') {
    const d = dutyRes.value.data.data;
    onDuty.value = Array.isArray(d) ? d : (d?.data || []);
  }
  if (camRes.status === 'fulfilled') {
    const c = camRes.value.data.data;
    cameras.value = Array.isArray(c) ? c : (c?.data || []);
  }
  if (trendRes.status === 'fulfilled') {
    const t = trendRes.value.data.data;
    trendItems.value = Array.isArray(t) ? t : (t?.items || []);
  }
  if (statRes.status === 'fulfilled') {
    const t = statRes.value.data.data || {};
    statRaw.value = t;
    statItems.value = Array.isArray(t) ? t : (t.items || t.levelDist || []);
  }
  if (vitalRes.status === 'fulfilled') {
    const t = vitalRes.value.data.data;
    vitalAlerts.value = Array.isArray(t) ? t : (t?.data || []);
  } else {
    // 这一路失败时 vitalAlerts 保持为空，而空态文案是
    // 「各项体征均在配置范围内」—— 把一个**故障**说成了一个**健康结论**。
    // 这是本页最容易被误读的一条信息：值班的人看到这句话就不去看了。
    console.error('加载体征预警失败', vitalRes.reason);
    vitalError.value = `体征预警加载失败：${vitalRes.reason?.friendlyMessage || '未知错误'}`;
  }
  loadingAlerts.value = false;
}

// 实时推送：新告警 / 升级 / 处置 立刻反映到队列
useSSE({
  onAlert: (payload) => {
    const a = payload?.alert;
    if (!a) return;
    const i = recentAlerts.value.findIndex((x) => x.id === a.id);
    if (i >= 0) recentAlerts.value[i] = { ...recentAlerts.value[i], ...a };
    else {
      recentAlerts.value.unshift({ ...a });
      recentAlerts.value = recentAlerts.value.slice(0, 20);
      stats.value.pending = (stats.value.pending || 0) + 1;
    }
  },
  onConfirmed: (payload) => {
    const a = payload?.alert;
    if (!a) return;
    const i = recentAlerts.value.findIndex((x) => x.id === a.id);
    if (i >= 0) recentAlerts.value[i] = { ...recentAlerts.value[i], ...a };
  },
});

let timer = null;
onMounted(() => { loadAll(); timer = setInterval(loadAll, 30000); });
onUnmounted(() => clearInterval(timer));
</script>

<style scoped>
.dash { display: flex; flex-direction: column; gap: 16px; }

/* ══════ 顶部两个主卡（1:1，文字居中）══════ */
.hero-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.hero-card {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 4px; padding: var(--space-5); border-radius: var(--radius-md); text-align: center;
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-top: 3px solid var(--tint-4);
}
.hero-card.hero-pending.active { border-top-color: var(--level-medium); }
.hero-card.hero-high.active { border-top-color: var(--level-high); }
.hero-label { font-size: 13px; color: var(--text-tertiary); font-weight: 600; }
.hero-value {
  font-size: 44px; font-weight: 800; line-height: 1.05; color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.hero-pending.active .hero-value { color: var(--level-medium); }
.hero-high.active .hero-value { color: var(--level-high); }
.hero-foot { font-size: 12px; color: var(--text-muted); }

/* ══════ 等宽模块行 ══════ */
.grid-2-1 { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 16px; }
.grid-1-1 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
@media (max-width: 1080px) {
  .grid-2-1, .grid-1-1, .hero-grid { grid-template-columns: 1fr; }
}

/* ══════ 面板：标题与内容均居中 ══════ */
.panel {
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md); padding: var(--space-4) var(--space-5); min-width: 0;
  display: flex; flex-direction: column;
}
.panel-head {
  display: flex; align-items: center; justify-content: center;
  gap: 10px; position: relative; margin-bottom: 12px;
}
.panel-head h2 {
  font-size: 14px; font-weight: 700; color: var(--text-primary);
  margin: 0; text-align: center;
}
/* 右侧附属信息绝对定位，保证标题**始终相对面板居中**，不会被右侧文字挤偏。
   注意必须限定在 .panel-head 内：写成未限定的 `.seg` 会把页头里的时间范围
   按钮也变成绝对定位，实测它跑到页面中部（y=462）压在饼图上、完全点不到。 */
.panel-head > .panel-sub,
.panel-head > .seg { position: absolute; right: 0; top: 50%; transform: translateY(-50%); }
.panel-sub { font-size: 12px; color: var(--text-muted); }

.stat-center { display: flex; flex-direction: column; align-items: center; gap: 2px; margin-bottom: 12px; }
.big-num {
  font-size: 34px; font-weight: 800; color: var(--text-primary);
  font-variant-numeric: tabular-nums; line-height: 1.1;
}
.big-num.ok { color: var(--level-normal); }
.big-num.warn { color: var(--level-medium); }
.big-sep { color: var(--text-muted); font-weight: 600; margin: 0 2px; }
.big-sub { font-size: 12px; color: var(--text-muted); text-align: center; }

.rate-bar { height: 10px; border-radius: 5px; background: var(--tint-2); overflow: hidden; }
.rate-fill { height: 100%; background: var(--level-normal); border-radius: 5px; transition: width .35s ease; }
.note { font-size: 11px; color: var(--text-muted); text-align: center; margin: 10px 0 0; line-height: 1.6; }

/* ══════ 表格（文字居中）══════ */
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th {
  text-align: center; font-weight: 600; color: var(--text-tertiary);
  font-size: 12px; padding: 8px 6px; border-bottom: 1px solid var(--border-subtle);
}
.tbl td { text-align: center; padding: 9px 6px; border-bottom: 1px solid var(--tint-2); color: var(--text-secondary); }
.tbl tr:last-child td { border-bottom: none; }
.tbl tr:hover td { background: var(--tint-1); }
.overdue { color: var(--level-high); font-weight: 700; }
.lvl {
  display: inline-block; padding: 2px 8px; border-radius: 20px;
  font-size: 11px; font-weight: 700; min-width: 54px; text-align: center;
}
.lvl.sm { min-width: 48px; }
.done { font-size: 12px; color: var(--text-muted); }
.btn-xs {
  padding: 4px 10px; margin: 0 2px; border-radius: 6px; cursor: pointer;
  font-size: 12px; border: 1px solid var(--primary);
  background: var(--primary-soft, color-mix(in srgb, var(--primary) 12%, transparent)); color: var(--primary);
}
.btn-xs.ghost { border-color: var(--border-default); background: transparent; color: var(--text-tertiary); }
.empty { padding: 26px; text-align: center; color: var(--text-muted); font-size: 13px; }
.more {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  padding: 12px; font-size: 12px; color: var(--text-muted);
  border-top: 1px solid var(--border-subtle); margin-top: 6px;
}
.more-link { color: var(--primary); font-weight: 600; text-decoration: none; }
.more-link:hover { text-decoration: underline; }

.seg { display: flex; gap: 4px; }
.seg-btn {
  padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 12px;
  border: 1px solid var(--border-default); background: transparent; color: var(--text-tertiary);
}
.seg-btn.on {
  border-color: var(--primary); color: var(--primary);
  background: var(--primary-soft, color-mix(in srgb, var(--primary) 12%, transparent)); font-weight: 600;
}

/* ══════ 体征预警（居中）══════ */
.vital-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 9px; }
.vital-item { display: grid; grid-template-columns: auto 1fr; gap: 8px; align-items: center; text-align: center; }
.vital-who { font-size: 13px; color: var(--text-secondary); }
.vital-what { grid-column: 1 / -1; font-size: 11px; color: var(--text-muted); }

/* ══════ 弹窗 ══════ */
.modal-mask {
  position: fixed; inset: 0; z-index: var(--z-modal, 300);
  background: var(--bg-overlay); display: flex; align-items: center; justify-content: center;
}
.modal {
  width: min(420px, 92vw); background: var(--bg-surface); border-radius: 14px;
  padding: 22px; text-align: center; box-shadow: var(--shadow-lg, 0 12px 32px color-mix(in srgb, var(--shadow-color) 20%, transparent));
}
.modal h3 { margin: 0 0 4px; font-size: 16px; color: var(--text-primary); }
.modal-sub { margin: 0 0 14px; font-size: 13px; color: var(--text-tertiary); }
.modal textarea {
  width: 100%; box-sizing: border-box; padding: 10px; border-radius: 8px;
  border: 1px solid var(--border-default); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px; font-family: inherit; resize: vertical;
}
.modal-actions { display: flex; justify-content: center; gap: 10px; margin-top: 14px; }
</style>
