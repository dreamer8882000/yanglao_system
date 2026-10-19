<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>操作审计</h1>
        <div class="page-sub">记录所有管理操作，满足合规审查要求</div>
      </div>
    </div>

    <!-- 工具栏（全局契约 .toolbar）。审计是合规场景，"谁在什么时候做了什么"
         往往要按操作人或动作去查，所以关键词是这里最常用的一个条件。 -->
    <div class="toolbar">
      <input v-model="filters.keyword" class="toolbar-search"
             placeholder="搜索操作人 / 动作 / 资源…" @input="onKeywordInput" />
      <input v-model="filters.startDate" type="date" class="toolbar-field" @change="resetPage" />
      <span class="toolbar-label">至</span>
      <input v-model="filters.endDate" type="date" class="toolbar-field" @change="resetPage" />
      <select v-model="filters.resourceType" class="toolbar-field" @change="resetPage">
        <option value="">全部资源</option>
        <option value="alert">告警</option>
        <option value="elder">老人档案</option>
        <option value="camera">摄像头</option>
        <option value="setting">系统配置</option>
        <option value="schedule">排班</option>
      </select>
      <button class="toolbar-reset" :disabled="!hasFilter" @click="reset">重置</button>
    </div>

    <!-- 桌面端表格 -->
    <div class="table-card desktop-table">
      <table v-if="!loading && logs.length" class="tbl">
        <thead>
          <tr>
            <th>操作时间</th><th>操作人</th><th>操作描述</th>
            <th>资源类型</th><th>资源 ID</th><th>IP 地址</th><th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logs" :key="log.id">
            <td class="time-cell">{{ formatTime(log.createdAt) }}</td>
            <td><span class="user-tag">{{ log.username || '-' }}</span></td>
            <td class="action-cell">{{ log.action }}</td>
            <td><span class="res-badge" :class="'res-' + log.resourceType">{{ resLabel(log.resourceType) }}</span></td>
            <td class="id-cell">{{ log.resourceId || '-' }}</td>
            <td class="ip-cell">{{ log.ip || '-' }}</td>
            <td><button v-if="log.detail" class="btn-detail" @click="openDetail(log)">查看</button></td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="table-state">加载中...</div>
      <div v-else-if="loadError" class="load-error">{{ loadError }}</div>
      <div v-else class="table-state">
        <div style="font-size:40px;opacity:.3">📋</div>
        <div>暂无审计记录</div>
      </div>
    </div>

    <!-- 移动端卡片 -->
    <div class="mobile-list">
      <div v-if="loading" class="table-state">加载中...</div>
      <div v-else-if="loadError" class="load-error">{{ loadError }}</div>
      <div v-else-if="!logs.length" class="table-state">
        <div style="font-size:40px;opacity:.3">📋</div>
        <div>暂无审计记录</div>
      </div>
      <div v-else>
        <div v-for="log in logs" :key="'m'+log.id" class="log-card">
          <div class="lc-top">
            <span class="user-tag">{{ log.username || '-' }}</span>
            <span class="res-badge" :class="'res-' + log.resourceType">{{ resLabel(log.resourceType) }}</span>
            <span class="lc-time">{{ formatTime(log.createdAt) }}</span>
          </div>
          <div class="lc-action">{{ log.action }}</div>
          <div class="lc-foot">
            <span class="lc-meta">IP: {{ log.ip || '-' }}</span>
            <button v-if="log.detail" class="btn-detail" @click="openDetail(log)">查看详情</button>
          </div>
        </div>
      </div>
    </div>

    <Pagination
      v-model:page="pagination.page"
      v-model:pageSize="pagination.pageSize"
      :total="pagination.total"
      @change="loadLogs"
    />

    <div v-if="detailModal.show" class="modal-mask" @click.self="detailModal.show = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>操作详情</h3>
          <button class="close-btn" @click="detailModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-meta">
            <div class="dmeta-item"><span class="dmeta-label">操作人</span><span>{{ detailModal.log?.username }}</span></div>
            <div class="dmeta-item"><span class="dmeta-label">操作时间</span><span>{{ formatTime(detailModal.log?.createdAt) }}</span></div>
            <div class="dmeta-item"><span class="dmeta-label">操作</span><span>{{ detailModal.log?.action }}</span></div>
          </div>
          <pre class="detail-json">{{ detailModal.detail }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import Pagination from '../components/Pagination.vue';
import { getAuditList } from '../api/audit.js';
import { formatTime } from '../utils/index.js';

function applyPagination(data, ref_) {
  // 后端分页接口返回的是 { data:[...], total, page, pageSize }，**没有** pagination
  // 子对象。三个页面此前都在读 data.pagination，读到的是 undefined —— 于是
  // pagination.total 恒为 0，分页控件从未渲染出来过。这里统一按顶层字段取值。
  const d = data || {};
  const size = Number(d.pageSize) || ref_.value.pageSize || 20;
  const total = Number(d.total) || 0;
  ref_.value = {
    page: Number(d.page) || 1,
    pageSize: size,
    total,
    totalPages: Math.max(1, Math.ceil(total / Math.max(1, size))),
  };
}

const logs = ref([]);
const loading = ref(false);
const loadError = ref('');
const pagination = ref({ page: 1, pageSize: 30, total: 0, totalPages: 1 });
const filters = ref({ startDate: '', endDate: '', resourceType: '', keyword: '' });

// 关键词防抖：审计是数据量最大的表（近 300 条且会持续增长），
// 逐字触发等于每敲一个字做一次全表 LIKE。
let keywordTimer = null;
function onKeywordInput() {
  clearTimeout(keywordTimer);
  keywordTimer = setTimeout(() => { pagination.value.page = 1; loadLogs(); }, 300);
}
const hasFilter = computed(() => Object.values(filters.value).some((v) => v !== ''));
function resetPage() { pagination.value.page = 1; loadLogs(); }
const detailModal = ref({ show: false, log: null, detail: '' });

const resLabels = { alert: '告警', elder: '老人档案', camera: '摄像头', setting: '系统配置', schedule: '排班' };
function resLabel(type) { return resLabels[type] || type || '其他'; }

async function loadLogs() {
  loading.value = true;
  try {
    const res = await getAuditList({ page: pagination.value.page,
                                     pageSize: pagination.value.pageSize, ...filters.value });
    if (res.data.success) {
      logs.value = res.data.data.data || [];
      applyPagination(res.data.data, pagination);
    }
    loadError.value = '';
  } catch (e) {
    // 审计日志读不出来时，空表不能报成"这段时间没有任何操作"——
    // 那正好是审计页最不该给出的错误结论。
    console.error('加载审计日志失败', e);
    loadError.value = `审计日志加载失败：${e?.friendlyMessage || '未知错误'}`;
  } finally { loading.value = false; }
}

function reset() { filters.value = { startDate: '', endDate: '', resourceType: '', keyword: '' }; pagination.value.page = 1; loadLogs(); }
function openDetail(log) {
  let detail = log.detail;
  try { detail = JSON.stringify(JSON.parse(log.detail), null, 2); }
  catch (e) {
    // detail 是 TEXT 列，历史数据里可能是非 JSON 的纯字符串。
    // 保留原文而不是显示空白：审计详情"看不到"比"格式不好看"严重得多。
    console.warn('审计详情不是合法 JSON，按原文展示', e);
  }
  detailModal.value = { show: true, log, detail };
}

onMounted(loadLogs);
</script>

<style scoped>
.page { padding: 24px; min-height: calc(100vh - var(--header-h)); }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
h1 { font-size: 22px; font-weight: 800; color: var(--text-primary); }
.page-sub { font-size: 13px; color: var(--text-muted); margin-top: 3px; }
.btn-reset { padding: 7px 14px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 13px; }
/* 背景/边框/圆角由全局 .panel 系列提供（含 .table-card），此处只补横向滚动 */
.table-card { overflow-x: auto; }
/* 表格样式交给 .tbl 契约；本页只声明最小宽度（列多，靠外层容器横向滚动） */
.table-wrapper table { min-width: 800px; }
thead tr { border-bottom: 1px solid var(--tint-3); }
/* 对齐/内边距/边框交给 .tbl 契约，这里只管本页特有的字号 */
.tbl th { font-size: 12px; }
.tbl td { font-size: 12px; }
tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: var(--tint-1); }
.time-cell { white-space: nowrap; color: var(--text-tertiary); }
.user-tag { background: color-mix(in srgb, var(--primary) 10%, transparent); color: var(--primary-hover); padding: 2px 8px; border-radius: 5px; font-weight: 600; font-size: 11px; }
.action-cell { color: var(--text-secondary); }
.res-badge { padding: 2px 8px; border-radius: 5px; font-size: 11px; font-weight: 600; }
.res-alert { background: color-mix(in srgb, var(--danger) 12%, transparent); color: var(--danger-text); }
.res-elder { background: color-mix(in srgb, var(--success) 10%, transparent); color: var(--success-text); }
.res-camera { background: color-mix(in srgb, var(--violet) 10%, transparent); color: var(--violet-text); }
.res-setting { background: color-mix(in srgb, var(--warning) 10%, transparent); color: var(--warning); }
.res-schedule { background: color-mix(in srgb, var(--info) 10%, transparent); color: var(--info); }
.id-cell { font-size: 11px; color: var(--text-muted); }
.ip-cell { font-size: 11px; color: var(--text-muted); }
.btn-detail { padding: 3px 10px; border-radius: 5px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 11px; }
.table-state { padding: 60px; text-align: center; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 10px; }
.mobile-list { display: none; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 22px; }
.page-btn { padding: 6px 14px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 13px; }
.page-btn:disabled { opacity: .4; cursor: not-allowed; }
.page-info { font-size: 13px; color: var(--text-tertiary); }
.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 16px; width: 500px; max-width: 95vw; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--tint-3); }
.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: none; border: none; color: var(--text-tertiary); font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; }
.detail-meta { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.dmeta-item { display: flex; gap: 12px; font-size: 13px; }
.dmeta-label { color: var(--text-muted); width: 60px; flex-shrink: 0; }
.detail-json { background: var(--bg-inset); border-radius: 8px; padding: 14px; font-size: 12px; color: var(--text-tertiary); overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }

@media (max-width: 768px) {
  .page { padding: 14px; }
  h1 { font-size: 18px; }
  .desktop-table { display: none; }
  .mobile-list { display: block; }
  .log-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 12px; padding: 14px; margin-bottom: 10px; }
  .lc-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
  .lc-time { font-size: 11px; color: var(--text-muted); margin-left: auto; }
  .lc-action { font-size: 13px; color: var(--text-secondary); margin-bottom: 8px; line-height: 1.5; }
  .lc-foot { display: flex; align-items: center; justify-content: space-between; }
  .lc-meta { font-size: 11px; color: var(--text-muted); }
  .btn-detail { padding: 6px 14px; font-size: 12px; min-height: 36px; }
  .table-state { padding: 40px 16px; }
  .pagination { gap: 8px; flex-wrap: wrap; }
  .page-btn { padding: 8px 14px; min-height: 44px; }
  .page-info { font-size: 12px; }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; }
  .modal-mask { align-items: flex-end; }
}
</style>
