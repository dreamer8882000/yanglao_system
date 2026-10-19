<template>
  <div class="page">
    <div class="page-header">
      <div class="page-header-left">
        <h1>平台运维</h1>
        <p class="page-sub">
          跨机构只读视图。这里能看到每一家机构的规模与安全事件，
          但<b>看不到老人个人信息</b> —— 运营方需要的是"这家机构还在用、规模多大"，
          而不是"谁住在哪"。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn-xs" @click="loadAll" :disabled="loading">
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </div>

    <div v-if="loadError" class="load-error">{{ loadError }}</div>

    <!-- 总览 -->
    <div class="panel">
      <div class="panel-head"><h2>平台总览</h2></div>
      <div class="stat-grid">
        <div class="stat-cell" v-for="c in overviewCards" :key="c.label">
          <div class="stat-num" :class="c.tone">{{ c.value }}</div>
          <div class="stat-cap">{{ c.label }}</div>
        </div>
      </div>
      <p v-if="overview && overview.orphanAuditCount > 0" class="panel-note orphan-note">
        其中 <b>{{ overview.orphanAuditCount }}</b> 条审计**不属于任何机构**
        （登录失败时用户名不存在，无从判断归属）。这类记录在机构自己的审计页里
        永远看不到 —— 而"有人在反复猜密码"恰恰是平台层必须看的东西。
      </p>
    </div>

    <!-- 机构清单 -->
    <div class="panel">
      <div class="panel-head">
        <h2>机构清单</h2>
        <span class="panel-sub">共 {{ tenants.length }} 家</span>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>机构</th><th>编码</th><th>联系人</th><th>账号</th>
              <th>在住老人</th><th>摄像头</th><th>告警总数</th><th>待处置</th>
              <th>最近告警</th><th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in tenants" :key="t.id">
              <td>{{ t.name }}</td>
              <td class="mono">{{ t.code }}</td>
              <td>{{ t.contact || '—' }}</td>
              <td>{{ t.userCount }}</td>
              <td>{{ t.elderCount }}</td>
              <td>{{ t.cameraCount }}</td>
              <td>{{ t.alertCount }}</td>
              <td :class="{ warn: t.pendingCount > 0 }">{{ t.pendingCount }}</td>
              <td>{{ t.lastAlertAt ? formatTime(t.lastAlertAt) : '—' }}</td>
              <td>
                <span class="badge" :class="t.status === 1 ? 'on' : 'off'">
                  {{ t.status === 1 ? '启用' : '停用' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!tenants.length" class="empty">暂无机构</div>
    </div>

    <!-- 安全事件 -->
    <div class="panel">
      <div class="panel-head">
        <h2>安全事件（登录失败 / 限流）</h2>
        <span class="panel-sub">{{ security.length }} 组</span>
      </div>
      <div class="toolbar">
        <span class="toolbar-label">统计窗口</span>
        <select class="toolbar-field" v-model.number="hours" @change="loadSecurity">
          <option :value="6">近 6 小时</option>
          <option :value="24">近 24 小时</option>
          <option :value="168">近 7 天</option>
        </select>
        <span class="toolbar-label">
          按「账号 + IP」聚合：逐条列流水没有可操作性，
          一眼看出"同一个来源试了多少次"才是能立刻处理的信号。
        </span>
      </div>
      <div v-if="security.length" class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>风险</th><th>账号</th><th>来源 IP</th>
              <th>失败次数</th><th>被限流</th><th>其中命中真实账号</th>
              <th>首次</th><th>最近</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in security" :key="s.username + s.ip">
              <td>
                <span class="risk-tag" :class="'r-' + s.risk">{{ RISK_LABEL[s.risk] }}</span>
              </td>
              <td class="mono">{{ s.username }}</td>
              <td class="mono">{{ s.ip }}</td>
              <td :class="{ warn: s.failed > 0 }">{{ s.failed }}</td>
              <td>{{ s.locked }}</td>
              <td :title="s.knownAccount > 0 ? '对方猜对了用户名，只差密码' : '用户名不存在，属乱猜'">
                {{ s.knownAccount }}
              </td>
              <td>{{ formatTime(s.firstAt) }}</td>
              <td>{{ formatTime(s.lastAt) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty">该时间窗口内没有登录失败记录</div>
    </div>

    <!-- 跨机构审计 -->
    <div class="panel">
      <div class="panel-head">
        <h2>跨机构审计</h2>
        <span class="panel-sub">共 {{ auditTotal }} 条</span>
      </div>
      <div class="toolbar">
        <input class="toolbar-search" v-model="auditFilters.keyword"
               placeholder="搜索操作 / 账号 / 资源" @input="onAuditSearch" />
        <select class="toolbar-field" v-model="auditFilters.tenantId" @change="resetAuditPage">
          <option value="">全部机构</option>
          <option value="orphan">仅无归属（平台层可见）</option>
          <option v-for="t in tenants" :key="t.id" :value="String(t.id)">{{ t.name }}</option>
        </select>
        <button class="toolbar-reset" :disabled="!auditFilterActive" @click="resetAuditFilters">
          重置
        </button>
      </div>
      <div v-if="auditLoading" class="empty">加载中…</div>
      <div v-else-if="auditError" class="load-error">{{ auditError }}</div>
      <template v-else>
        <div v-if="auditRows.length" class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>时间</th><th>机构</th><th>账号</th><th>操作</th>
                <th>资源</th><th>IP</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in auditRows" :key="r.id">
                <td>{{ formatTime(r.createdAt) }}</td>
                <td>
                  <span v-if="r.tenantName">{{ r.tenantName }}</span>
                  <span v-else class="orphan">无归属</span>
                </td>
                <td class="mono">{{ r.username || '—' }}</td>
                <td>{{ r.action }}</td>
                <td>{{ r.resourceType }}<span v-if="r.resourceId"> #{{ r.resourceId }}</span></td>
                <td class="mono">{{ r.ip || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty">没有符合条件的审计记录</div>
        <Pagination
          v-model:page="auditPagination.page" v-model:pageSize="auditPagination.pageSize"
          :total="auditTotal" @change="loadAudit"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import Pagination from '../components/Pagination.vue';
import { getPlatformOverview, getPlatformTenants, getPlatformSecurity,
         getPlatformAudit } from '../api/platform.js';
import { formatTime } from '../utils/index.js';

const loading = ref(false);
const loadError = ref('');
const overview = ref(null);
const tenants = ref([]);
const security = ref([]);
const hours = ref(24);

const auditRows = ref([]);
const auditTotal = ref(0);
const auditLoading = ref(true);
const auditError = ref('');
const auditPagination = reactive({ page: 1, pageSize: 20 });
const auditFilters = reactive({ keyword: '', tenantId: '' });
const auditFilterActive = computed(() =>
  Boolean(auditFilters.keyword) || auditFilters.tenantId !== '');

const RISK_LABEL = { high: '高', medium: '中', low: '低' };

const overviewCards = computed(() => {
  const o = overview.value || {};
  return [
    { label: '机构数', value: o.tenantCount ?? '—', tone: '' },
    { label: '启用中', value: o.activeTenantCount ?? '—', tone: 'ok' },
    { label: '账号数', value: o.userCount ?? '—', tone: '' },
    { label: '在住老人', value: o.elderCount ?? '—', tone: '' },
    { label: '摄像头', value: o.cameraCount ?? '—', tone: '' },
    { label: '告警总数', value: o.alertCount ?? '—', tone: '' },
    // 近 24h 登录失败单列：它不是"业务数字"，而是唯一能反映"有人在试探"的指标
    { label: '24h 登录失败', value: o.failedLogin24h ?? '—',
      tone: (o.failedLogin24h || 0) > 50 ? 'warn' : '' },
  ];
});

async function loadOverview() {
  try {
    const res = await getOverviewOnce();
    if (res.data.success) overview.value = res.data.data;
  } catch (e) {
    console.error('加载平台总览失败', e);
    loadError.value = `平台总览加载失败：${e?.friendlyMessage || '未知错误'}`;
  }
}
async function getOverviewOnce() { return getPlatformOverview(); }

async function loadTenants() {
  try {
    const res = await getPlatformTenants();
    if (res.data.success) tenants.value = res.data.data || [];
  } catch (e) {
    console.error('加载机构清单失败', e);
    loadError.value = `机构清单加载失败：${e?.friendlyMessage || '未知错误'}`;
  }
}

async function loadSecurity() {
  try {
    const res = await getPlatformSecurity(hours.value);
    if (res.data.success) security.value = res.data.data || [];
  } catch (e) {
    console.error('加载安全事件失败', e);
    loadError.value = `安全事件加载失败：${e?.friendlyMessage || '未知错误'}`;
  }
}

async function loadAudit() {
  auditLoading.value = true;
  try {
    const params = {
      page: auditPagination.page,
      pageSize: auditPagination.pageSize,
      keyword: auditFilters.keyword,
    };
    if (auditFilters.tenantId === 'orphan') params.onlyOrphans = true;
    else if (auditFilters.tenantId) params.tenantId = auditFilters.tenantId;
    const res = await getPlatformAudit(params);
    if (res.data.success) {
      auditRows.value = res.data.data.data || [];
      auditTotal.value = res.data.data.total || 0;
    }
    auditError.value = '';
  } catch (e) {
    console.error('加载跨机构审计失败', e);
    auditError.value = `审计加载失败：${e?.friendlyMessage || '未知错误'}`;
  } finally {
    auditLoading.value = false;
  }
}

let auditTimer = null;
function onAuditSearch() {
  clearTimeout(auditTimer);
  auditTimer = setTimeout(resetAuditPage, 300);
}
function resetAuditPage() {
  auditPagination.page = 1;
  loadAudit();
}
function resetAuditFilters() {
  auditFilters.keyword = '';
  auditFilters.tenantId = '';
  resetAuditPage();
}

async function loadAll() {
  loading.value = true;
  loadError.value = '';
  try {
    await Promise.all([loadOverview(), loadTenants(), loadSecurity(), loadAudit()]);
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);
</script>

<style scoped>
/* 统计格子：这里用等宽栅格而不是 .grid-*，因为它是"一排数字"，
   宽度一致比比例协调更重要（数字列参差不齐很难扫读） */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: var(--space-3);
}
.stat-cell {
  background: var(--bg-surface-2, var(--tint-1));
  border: 1px solid var(--tint-3);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-2);
  text-align: center;
  min-width: 0;
}
.stat-num { font-size: 20px; font-weight: 800; color: var(--text-primary); line-height: 1.2; }
.stat-num.ok { color: var(--success-text); }
.stat-num.warn { color: var(--warning-text); }
.stat-cap { font-size: 11px; color: var(--text-muted); margin-top: 4px; white-space: nowrap; }

@media (max-width: 1180px) { .stat-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
@media (max-width: 780px) { .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

.orphan-note { color: var(--text-secondary); text-align: start; }
.orphan-note b { color: var(--warning-text); }
.mono { font-family: var(--font-mono, ui-monospace, Menlo, monospace); font-size: 12px; }
.orphan { color: var(--warning-text); font-weight: 600; }
.warn { color: var(--warning-text); font-weight: 700; }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: var(--radius-full, 999px);
  font-size: 11px; font-weight: 600;
}
.badge.on { background: var(--success-soft); color: var(--success-text); }
.badge.off { background: var(--tint-2); color: var(--text-muted); }
.risk-tag {
  display: inline-block; min-width: 22px; padding: 1px 7px;
  border-radius: var(--radius-full, 999px); font-size: 11px; font-weight: 700;
}
.r-high { background: var(--danger-soft); color: var(--danger-text); }
.r-medium { background: var(--warning-soft); color: var(--warning-text); }
.r-low { background: var(--tint-2); color: var(--text-muted); }
</style>
