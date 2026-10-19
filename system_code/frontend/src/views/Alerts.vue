<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>告警记录</h1>
        <div class="page-sub">查询与管理历史告警事件</div>
      </div>
    </div>

    <!-- 工具栏：条件在左、对列表的操作在右（全局契约 .toolbar，见 layout.css 第 9 节） -->
    <div class="toolbar">
      <input v-model="filters.keyword" class="toolbar-search"
             placeholder="搜索老人 / 房间 / 摄像头 / 表情…" @input="onKeywordInput" />
      <select v-model="filters.riskLevel" class="toolbar-field" @change="resetPage">
        <option value="">全部等级</option>
        <option value="URGENT">URGENT 紧急</option>
        <option value="HIGH">HIGH 高风险</option>
        <option value="MEDIUM">MEDIUM 中危</option>
        <option value="LOW">LOW 低危</option>
      </select>
      <select v-model="filters.status" class="toolbar-field" @change="resetPage">
        <option value="">全部状态</option>
        <option value="0">待处理</option>
        <option value="1">已处理</option>
        <option value="2">误报</option>
      </select>
      <!-- 身份筛选单独成一个条件：多人同房产生的那批"不知道是谁"的告警
           必须人工指定当事人，是最需要被单独捞出来处理的一批。
           混在几十条里只能靠翻页去找。 -->
      <select v-model="filters.identity" class="toolbar-field" @change="resetPage">
        <option value="">全部身份</option>
        <option value="ambiguous">⚠ 待确认当事人</option>
        <option value="unmatched">未匹配到老人</option>
        <option value="room_single">房间唯一在册</option>
        <option value="manual">人工已确认</option>
      </select>
      <input v-model="filters.startDate" type="date" class="toolbar-field" @change="resetPage" />
      <span class="toolbar-label">至</span>
      <input v-model="filters.endDate" type="date" class="toolbar-field" @change="resetPage" />
      <button class="toolbar-reset" :disabled="!hasFilter" @click="resetFilters">重置</button>
      <div class="toolbar-actions">
        <button v-if="isAdmin" class="btn-xs" @click="exportAlerts">导出 CSV</button>
        <button class="btn-xs" :disabled="!selectedIds.length" @click="batchConfirm">
          批量确认{{ selectedIds.length ? `(${selectedIds.length})` : '' }}
        </button>
      </div>
    </div>

    <!-- 桌面端表格 -->
    <div class="table-card desktop-table">
      <table v-if="!loading && alerts.length" class="tbl">
        <thead>
          <tr>
            <th>风险等级</th><th>关联老人</th><th>房间</th>
            <th>姿态证据</th><th>表情证据</th>
            <th>告警时间</th><th>状态</th><th>处理人</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="alert in alerts" :key="alert.id">
            <td><span class="level-tag" :style="{ background: riskBg(alert.riskLevel), color: riskColor(alert.riskLevel) }">{{ alert.riskLevel }}</span></td>
            <!-- 关联老人：多人同房时系统**不会**猜一个（identityMethod='ambiguous'），
                 这里必须把"不知道是谁"显式说出来。此前的实现是按 id 取第一位，
                 界面显示得像确定无疑，护士根本无从察觉可能挂错了人。 -->
            <td class="identity-cell">
              <template v-if="alert.identityMethod === 'ambiguous'">
                <button class="id-ambiguous" :title="candidateTitle(alert)" @click="openTimeline(alert)">
                  ⚠ 待确认
                </button>
                <span class="id-hint">{{ (alert.identityCandidates || []).length }} 人同房</span>
              </template>
              <template v-else-if="alert.identityMethod === 'unmatched'">
                <span class="id-unmatched" title="该房间没有在册老人，或老人已出院">未匹配</span>
              </template>
              <template v-else>
                <span>{{ alert.elderName || '-' }}</span>
                <span v-if="alert.identityMethod === 'manual'" class="id-manual" title="当事人由护理员指定">人工确认</span>
              </template>
            </td>
            <td>{{ alert.roomNo ? alert.roomNo + '室' : '-' }}</td>
            <!-- AI 证据列：把"凭什么报警"直接摆在列表里。
                 此前只有等级与置信度，护理员必须先点开抽屉才知道发生了什么，
                 无法在扫一眼时判断该不该立刻过去。 -->
            <td class="ev-cell">
              <span class="ev-pill" :class="'pt-' + (alert.postureType || 'unknown')">
                {{ postureLabel(alert.postureType) }}
              </span>
              <span v-if="alert.torsoAngle != null" class="ev-dim">
                躯干 {{ Number(alert.torsoAngle).toFixed(0) }}°
              </span>
              <span v-if="alert.rapidDescent" class="ev-flag">下坠</span>
            </td>
            <td class="ev-cell">
              <template v-if="alert.faceAvailable">
                <span class="ev-pill expr">{{ emotionLabel(alert.expressionTop) }}</span>
                <span v-if="alert.expressionConfidence != null" class="ev-dim">
                  {{ (Number(alert.expressionConfidence) * 100).toFixed(0) }}%
                </span>
              </template>
              <span v-else class="ev-unknown" title="未定位到人脸：痛苦记为“证据未知”，不等于“无痛苦”">
                证据未知
              </span>
            </td>
            <td class="time-cell">{{ formatTime(alert.alertTime) }}</td>
            <td><span class="status-chip" :class="statusClass(alert.status)">{{ statusText(alert.status) }}</span></td>
            <td>{{ alert.handlerName || '-' }}</td>
            <td class="action-col">
              <!-- 统一用 .row-actions：不换行 + 等宽，让每一行的按钮列对得齐。
                   否则"已处理"的行只有 1 个按钮、"待处理"的行有 3 个，
                   表格右缘会被撑得参差不齐。 -->
              <div class="row-actions">
                <button class="btn-sm-action" @click="openTimeline(alert)">时间线</button>
                <button v-if="alert.status === 0" class="btn-sm-action confirm" @click="openConfirm(alert)">确认</button>
                <button v-if="alert.status === 0" class="btn-sm-action reject" @click="markFalseAlarm(alert)">误报</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="table-state">加载中...</div>
      <div v-else-if="loadError" class="load-error">{{ loadError }}</div>
      <div v-else class="table-state">
        <div style="font-size:40px;opacity:.3">📋</div>
        <div>暂无告警记录</div>
      </div>
    </div>

    <!-- 移动端卡片 -->
    <div class="mobile-list">
      <div v-if="loading" class="table-state">加载中...</div>
      <div v-else-if="loadError" class="load-error">{{ loadError }}</div>
      <div v-else-if="!alerts.length" class="table-state">
        <div style="font-size:40px;opacity:.3">📋</div>
        <div>暂无告警记录</div>
      </div>
      <div v-else>
        <div v-for="alert in alerts" :key="'m'+alert.id" class="alert-card" :class="'lvl-' + alert.riskLevel?.toLowerCase()">
          <div class="ac-top">
            <span class="level-tag" :style="{ background: riskBg(alert.riskLevel), color: riskColor(alert.riskLevel) }">{{ alert.riskLevel }}</span>
            <span class="ac-elder">{{ alert.elderName || '未识别' }}</span>
            <span v-if="alert.roomNo" class="ac-room">{{ alert.roomNo }}室</span>
            <span class="status-chip ml-auto" :class="alert.status === 1 ? 'done' : 'pending'">{{ alert.status === 1 ? '已处理' : '待处理' }}</span>
          </div>
          <div class="ac-mid">
            <span class="ac-conf">置信度 {{ alert.confidence }}%</span>
            <span class="ac-time">{{ formatTime(alert.alertTime) }}</span>
          </div>
          <div class="ac-actions">
            <button class="btn-sm-action" @click="openTimeline(alert)">查看时间线</button>
            <button v-if="alert.status === 0" class="btn-sm-action confirm" @click="openConfirm(alert)">确认处置</button>
            <button v-if="alert.status === 0" class="btn-sm-action reject" @click="markFalseAlarm(alert)">误报</button>
          </div>
        </div>
      </div>
    </div>

    <Pagination
      v-model:page="pagination.page"
      v-model:pageSize="pagination.pageSize"
      :total="pagination.total"
      @change="loadAlerts"
    />

    <!-- 确认弹框 -->
    <div v-if="confirmModal.show" class="modal-mask" @click.self="confirmModal.show = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>确认告警处置</h3>
          <button class="close-btn" @click="confirmModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-row">
            <span class="level-tag" :style="{ background: riskBg(confirmModal.alert?.riskLevel), color: riskColor(confirmModal.alert?.riskLevel) }">{{ confirmModal.alert?.riskLevel }}</span>
            <span class="detail-text">{{ confirmModal.alert?.elderName }} · {{ confirmModal.alert?.roomNo }}室 · {{ confirmModal.alert?.confidence }}%</span>
          </div>
          <div class="field-group">
            <label>处置备注 <span class="req">*</span></label>
            <textarea v-model="confirmModal.notes" placeholder="请填写处置说明…" maxlength="200" rows="4"></textarea>
            <div class="char-count">{{ confirmModal.notes.length }}/200</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="confirmModal.show = false">取消</button>
          <button class="btn-primary" @click="submitConfirm" :disabled="confirmModal.loading">
            {{ confirmModal.loading ? '提交中...' : '确认处置' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 时间线抽屉 -->
    <transition name="drawer">
      <div v-if="timelineDrawer.show" class="drawer-mask" @click.self="timelineDrawer.show = false">
        <div class="drawer">
          <div class="drawer-header">
            <div>
              <h3>事件时间线</h3>
              <div class="drawer-sub">
                <span class="level-tag sm" :style="{ background: riskBg(timelineDrawer.alert?.riskLevel), color: riskColor(timelineDrawer.alert?.riskLevel) }">{{ timelineDrawer.alert?.riskLevel }}</span>
                {{ timelineDrawer.alert?.elderName || '未识别' }} · {{ timelineDrawer.alert?.roomNo }}室
              </div>
            </div>
            <button class="close-btn" @click="timelineDrawer.show = false">×</button>
          </div>
          <div class="drawer-body">
            <!-- 身份判定：摆在整个证据链最前面。
                 理由：证据再充分，如果不知道"是谁"，护士也无法行动 ——
                 身份是这条告警可被执行的前提，而不是事后补充的元数据。 -->
            <div v-if="drawerAlert" class="identity-block"
                 :class="{ warn: drawerAlert.identityMethod === 'ambiguous' }">
              <div class="id-title">
                当事人判定
                <span class="id-method" :class="'im-' + (drawerAlert.identityMethod || 'unknown')">
                  {{ identityLabel(drawerAlert.identityMethod) }}
                </span>
              </div>

              <template v-if="drawerAlert.identityMethod === 'ambiguous'">
                <div class="id-warn-text">
                  该房间有 {{ (drawerAlert.identityCandidates || []).length }} 位在册老人，
                  系统无法判定是哪一位，<b>请确认当事人</b>：
                </div>
                <div class="id-candidates">
                  <button v-for="c in drawerAlert.identityCandidates" :key="c.id"
                          class="id-cand" :class="{ active: identityPicking === c.id }"
                          :disabled="identitySaving"
                          @click="submitIdentity(c)">
                    <span class="id-bed">{{ c.bedNo }} 床</span>
                    <span class="id-name">{{ c.name }}</span>
                  </button>
                </div>
              </template>
              <template v-else>
                <div class="db-grid">
                  <div class="db-item"><span class="db-k">老人</span>
                    <span class="db-v">{{ drawerAlert.elderName || '—' }}</span></div>
                  <div class="db-item"><span class="db-k">房间 / 床位</span>
                    <span class="db-v">{{ drawerAlert.roomNo ? drawerAlert.roomNo + '室' : '—' }}</span></div>
                  <div class="db-item"><span class="db-k">判定置信度</span>
                    <span class="db-v">{{ identityConf(drawerAlert) }}</span></div>
                </div>
                <div v-if="drawerAlert.identityMethod === 'unmatched'" class="id-warn-text">
                  该房间没有在册老人（空房或老人已出院）。这类告警指向的可能是
                  <b>非在册人员</b>，请人工核实，不要直接按误报处理。
                </div>
              </template>
            </div>

            <!-- 多模态证据链：把论文第三创新点（D-S 融合）呈现给用户 -->
            <div class="evidence-block">
              <div class="ev-title">多模态证据链</div>
              <div class="ev-grid">
                <div class="ev-item">
                  <div class="ev-label">姿态证据</div>
                  <div class="ev-value">{{ evidence.postureLabel }}</div>
                  <div class="ev-bar"><span :style="{ width: pctWidth(evidence.fallScore), background: 'var(--level-high)' }"></span></div>
                  <div class="ev-num">跌倒分 {{ fmtNum(evidence.fallScore) }}</div>
                </div>
                <div class="ev-item">
                  <div class="ev-label">表情证据</div>
                  <div class="ev-value">{{ evidence.modeLabel }}</div>
                  <div class="ev-bar"><span :style="{ width: pctWidth(evidence.painScore), background: 'var(--level-medium)' }"></span></div>
                  <div class="ev-num">痛苦分 {{ fmtNum(evidence.painScore) }}</div>
                </div>
              </div>
              <!-- 姿态明细：几何判据的输入量。护理员据此判断"判得准不准"，
                   效果评测据此回答"哪类几何特征在误报"。 -->
              <div v-if="drawerAlert" class="detail-block">
                <div class="db-title">姿态细节</div>
                <div class="db-grid">
                  <div class="db-item"><span class="db-k">躯干倾角</span>
                    <span class="db-v">{{ num(drawerAlert.torsoAngle, '°') }}</span></div>
                  <div class="db-item"><span class="db-k">膝髋高度比</span>
                    <span class="db-v">{{ num(drawerAlert.kneeHipRatio, '', 2) }}</span></div>
                  <div class="db-item"><span class="db-k">姿态质量</span>
                    <span class="db-v">{{ num(drawerAlert.poseQuality, '', 3) }}</span></div>
                  <div class="db-item"><span class="db-k">身体关键点</span>
                    <span class="db-v">{{ drawerAlert.bodyKeypoints ?? '—' }} / 17</span></div>
                  <div class="db-item"><span class="db-k">快速下坠</span>
                    <span class="db-v">{{ drawerAlert.rapidDescent ? '是' : '否' }}</span></div>
                  <div class="db-item"><span class="db-k">跌倒状态</span>
                    <span class="db-v">{{ drawerAlert.fallState || '—' }}</span></div>
                </div>
              </div>

              <div v-if="drawerAlert" class="detail-block">
                <div class="db-title">表情细节</div>
                <div class="db-grid">
                  <div class="db-item"><span class="db-k">主导表情</span>
                    <span class="db-v">{{ drawerAlert.faceAvailable ? emotionLabel(drawerAlert.expressionTop) : '—' }}</span></div>
                  <div class="db-item"><span class="db-k">置信度</span>
                    <span class="db-v">{{ drawerAlert.expressionConfidence != null
                        ? (Number(drawerAlert.expressionConfidence) * 100).toFixed(0) + '%' : '—' }}</span></div>
                  <div class="db-item"><span class="db-k">表情质量</span>
                    <span class="db-v">{{ num(drawerAlert.exprQuality, '', 3) }}</span></div>
                  <div class="db-item"><span class="db-k">人脸定位</span>
                    <span class="db-v">{{ drawerAlert.faceAvailable ? (drawerAlert.faceMethod || '已定位') : '未定位' }}</span></div>
                </div>
              </div>

              <div v-if="drawerAlert" class="detail-block">
                <div class="db-title">D-S 融合</div>
                <div class="db-grid">
                  <div class="db-item"><span class="db-k">m(F) 跌倒信念</span>
                    <span class="db-v">{{ num(drawerAlert.beliefFall, '', 3) }}</span></div>
                  <div class="db-item"><span class="db-k">m(Θ) 不确定</span>
                    <span class="db-v">{{ num(drawerAlert.beliefUnknown, '', 3) }}</span></div>
                  <div class="db-item"><span class="db-k">人体跟踪号</span>
                    <span class="db-v">{{ drawerAlert.trackId ?? '—' }}</span></div>
                  <div class="db-item"><span class="db-k">综合置信度</span>
                    <span class="db-v">{{ drawerAlert.confidence }}%</span></div>
                </div>
              </div>

              <div class="ev-foot">
                融合结论：以姿态判定"是否摔倒"，以表情判定"是否痛苦"。两轴相互独立——
                看不见脸时痛苦记为<strong>证据未知</strong>，而不是"无痛苦"。
              </div>
            </div>

            <div class="timeline">
              <div v-for="(ev, i) in timelineEvents" :key="i" class="tl-item" :class="{ done: ev.done }">
                <div class="tl-dot" :class="{ active: ev.done, pending: !ev.done }"></div>
                <div class="tl-line" v-if="i < timelineEvents.length - 1"></div>
                <div class="tl-content">
                  <div class="tl-title">{{ ev.title }}</div>
                  <div class="tl-time" v-if="ev.time">{{ ev.time }}</div>
                  <div class="tl-desc" v-if="ev.desc">{{ ev.desc }}</div>
                  <div class="tl-pending" v-if="!ev.done">等待中...</div>
                </div>
              </div>
            </div>
            <div class="tl-meta">
              <div class="meta-row"><span class="meta-label">置信度</span><span>{{ timelineDrawer.alert?.confidence }}%</span></div>
              <div class="meta-row"><span class="meta-label">摄像头</span><span>{{ timelineDrawer.alert?.cameraName || '-' }}</span></div>
              <div class="meta-row" v-if="timelineDrawer.alert?.handlerNotes"><span class="meta-label">备注</span><span>{{ timelineDrawer.alert?.handlerNotes }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { getAlertList, confirmAlert, confirmAlertIdentity, markAlertFalseAlarm,
         exportAlerts as exportApi, batchConfirmAlerts } from '../api/alerts.js';
import { formatTime, riskColor, riskBg, showToast } from '../utils/index.js';
import Pagination from '../components/Pagination.vue';

const isAdmin = computed(() => { try { return JSON.parse(sessionStorage.getItem('current_user') || '{}').role === 'admin'; } catch { return false; } });

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

const alerts = ref([]);
const loading = ref(false);
const loadError = ref('');
const pagination = ref({ page: 1, pageSize: 20, total: 0, totalPages: 1 });
const filters = ref({ startDate: '', endDate: '', riskLevel: '', status: '',
                      keyword: '', identity: '' });
// 批量确认：勾选的行 id
const selectedIds = ref([]);
const confirmModal = ref({ show: false, alert: null, notes: '', loading: false });
const timelineDrawer = ref({ show: false, alert: null });
// 身份确认：正在提交的候选 id（用于禁用按钮，避免连点产生两条写入）
const identityPicking = ref(null);
const identitySaving = ref(false);

const timelineEvents = computed(() => {
  const a = timelineDrawer.value.alert;
  if (!a) return [];
  const fmt = (v) => v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : null;
  return [
    { title: '检测触发', done: true, time: fmt(a.alertTime), desc: `AI 检测到跌倒事件，置信度 ${a.confidence}%` },
    { title: '派单通知', done: true, time: fmt(a.alertTime), desc: '已向当前值班人员发送告警通知' },
    { title: '护士到场处置', done: a.status === 1, time: a.status === 1 ? fmt(a.handledAt) : null, desc: a.status === 1 ? `处置人：${a.handlerName || '-'}` : null },
    { title: '处置完成', done: a.status === 1, time: a.status === 1 ? fmt(a.handledAt) : null, desc: a.status === 1 ? (a.handlerNotes || '已确认处置') : null },
  ];
});

async function loadAlerts() {
  loading.value = true;
  try {
    const res = await getAlertList({ page: pagination.value.page,
                                     pageSize: pagination.value.pageSize, ...filters.value });
    if (res.data.success) {
      alerts.value = res.data.data.data;
      applyPagination(res.data.data, pagination);
    }
    loadError.value = '';
  } catch (e) {
    // 空 catch 时"接口挂了"与"告警为 0 条"在界面上长得一样 —— 而这两件事
    // 对值班人员的意义截然相反（一个是系统故障，一个是平安无事）。
    console.error('加载告警列表失败', e);
    loadError.value = `告警列表加载失败：${e?.friendlyMessage || '未知错误'}`;
  } finally { loading.value = false; }
}

// 关键词防抖：告警列表数据量最大，逐字触发会让每次输入都打一次全表检索
let keywordTimer = null;
function onKeywordInput() {
  clearTimeout(keywordTimer);
  keywordTimer = setTimeout(() => { pagination.value.page = 1; loadAlerts(); }, 300);
}

const hasFilter = computed(() => Object.values(filters.value).some((v) => v !== ''));

function resetFilters() {
  filters.value = { startDate: '', endDate: '', riskLevel: '', status: '',
                    keyword: '', identity: '' };
  selectedIds.value = [];
  pagination.value.page = 1;
  loadAlerts();
}
function resetPage() { pagination.value.page = 1; selectedIds.value = []; loadAlerts(); }

async function batchConfirm() {
  if (!selectedIds.value.length) return;
  try {
    const res = await batchConfirmAlerts(selectedIds.value, '批量处置');
    if (res.data.success) {
      showToast(res.data.message || '已批量处置', 'success');
      selectedIds.value = [];
      loadAlerts();
    } else {
      showToast(res.data.message || '批量处置失败', 'error');
    }
  } catch {
    showToast('批量处置失败', 'error');
  }
}
const POSTURE_LABEL = {
  fall_like: '横卧（跌倒样）', lying: '躺卧', sitting: '坐姿', standing: '站立',
  bending: '弯腰', resting: '静卧', unknown: '姿态不明', insufficient_body: '身体关键点不足',
};
const MODE_LABEL = {
  pose_expression: '姿态+表情（双模态）', pose_only: '仅姿态（未定位人脸）',
  expression_only: '仅表情（身体不足）', no_evidence: '无有效证据',
};

// 八类表情（与模型输出一致：EXPRESSION_NAMES）
const EMOTION_LABEL = {
  Anger: '愤怒', Contempt: '轻蔑', Disgust: '厌恶', Fear: '恐惧',
  Happy: '高兴', Neutral: '平静', Sad: '悲伤', Surprise: '惊讶',
};

const STATUS_TEXT = { 0: '待处理', 1: '已处理', 2: '误报' };
const STATUS_CLASS = { 0: 'pending', 1: 'done', 2: 'rejected' };

// 抽屉里正在查看的告警
const drawerAlert = computed(() => timelineDrawer.value.alert || null);
function num(v, unit = '', digits = 1) {
  if (v === null || v === undefined || v === '') return '—';
  return Number(v).toFixed(digits) + unit;
}

function postureLabel(v) { return POSTURE_LABEL[v] || '姿态不明'; }

// 身份判定方式的展示名。用户看到的是"系统凭什么认为是他"，
// 而不是一个内部枚举值。
const IDENTITY_LABEL = {
  room_single: '房间唯一在册老人',
  ambiguous: '多人同房·待确认',
  unmatched: '房间无在册老人',
  manual: '护理员已确认',
  bed_zone: '床位区域判定',
  face_verified: '人脸核验',
  no_camera: '无摄像头来源',
};
function identityLabel(v) { return IDENTITY_LABEL[v] || '未知方式'; }

function candidateTitle(alert) {
  const names = (alert.identityCandidates || []).map((c) => `${c.bedNo}床 ${c.name}`);
  return names.length ? `候选：${names.join('、')}` : '该房间有多位在册老人';
}

function identityConf(alert) {
  const v = alert?.identityConfidence;
  if (v == null) return '—';
  return (Number(v) * 100).toFixed(0) + '%';
}
function emotionLabel(v) { return v ? (EMOTION_LABEL[v] || v) : '—'; }



const evidence = computed(() => {
  const a = timelineDrawer.value.alert || {};
  return {
    postureLabel: POSTURE_LABEL[a.postureType] || '未知',
    modeLabel: MODE_LABEL[a.evidenceMode] || '未知',
    fallScore: a.fallScore ?? 0,
    painScore: a.painScore ?? 0,
  };
});

function pctWidth(v) {
  const n = Math.max(0, Math.min(1, Number(v) || 0));
  return `${(n * 100).toFixed(0)}%`;
}

function fmtNum(v) {
  if (v === null || v === undefined || v === '') return '—';
  return Number(v).toFixed(2);
}

function statusText(status) { return STATUS_TEXT[status] ?? '未知'; }
function statusClass(status) { return STATUS_CLASS[status] ?? 'pending'; }

async function markFalseAlarm(alert) {
  try {
    await markAlertFalseAlarm(alert.id, '护士标注：误报');
    showToast(`告警 #${alert.id} 已标记为误报`, 'success');
    await loadAlerts();
  } catch (e) {
    showToast(e.response?.data?.message || '标记失败', 'error');
  }
}

function openConfirm(alert) { confirmModal.value = { show: true, alert, notes: '', loading: false }; }
function openTimeline(alert) {
  timelineDrawer.value = { show: true, alert };
  identityPicking.value = null;
}

/** 护理员从候选床位里指定当事人。
 *
 * 为什么必须有这个动作：多人同房时系统**故意不给答案**。如果只提示
 * "不确定"而不提供确认入口，那些告警就永远没有当事人 —— 老人的健康趋势、
 * 按体态/表情统计的误报率都会把它们算成"未知"，统计随之下沉。
 * 护理员是现场唯一能判断的人，她的判断要落回库里。
 */
async function submitIdentity(candidate) {
  const alert = timelineDrawer.value.alert;
  if (!alert || identitySaving.value) return;
  identityPicking.value = candidate.id;
  identitySaving.value = true;
  try {
    const res = await confirmAlertIdentity(alert.id, candidate.id);
    if (res.data.success) {
      const { elderId, elderName } = res.data.data;
      // 就地更新：抽屉与列表行都要立刻反映"已经知道是谁了"
      timelineDrawer.value.alert = {
        ...alert, elderId, elderName, identityMethod: 'manual', identityConfidence: 1,
      };
      const row = alerts.value.find((a) => a.id === alert.id);
      if (row) Object.assign(row, { elderId, elderName, identityMethod: 'manual', identityConfidence: 1 });
      showToast(res.data.message || '已确认当事人', 'success');
      loadAlerts();
    } else {
      showToast(res.data.message || '确认失败', 'error');
    }
  } catch (e) {
    showToast(e.response?.data?.detail || '确认失败', 'error');
  } finally {
    identitySaving.value = false;
    identityPicking.value = null;
  }
}

async function submitConfirm() {
  if (!confirmModal.value.notes.trim()) { showToast('请填写处置备注', 'warning'); return; }
  confirmModal.value.loading = true;
  try {
    const res = await confirmAlert(confirmModal.value.alert.id, confirmModal.value.notes);
    if (res.data.success) { showToast('确认成功', 'success'); confirmModal.value.show = false; loadAlerts(); }
    else showToast(res.data.message || '操作失败', 'error');
  } catch { showToast('网络错误', 'error'); }
  finally { confirmModal.value.loading = false; }
}

async function exportAlerts() {
  try {
    const res = await exportApi(filters.value);
    const url = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = url; a.download = `告警记录_${Date.now()}.csv`;
    a.click(); URL.revokeObjectURL(url);
    showToast('导出成功', 'success');
  } catch { showToast('导出失败，请确认您有管理员权限', 'error'); }
}

onMounted(loadAlerts);
</script>

<style scoped>
.page { padding: 24px; min-height: calc(100vh - var(--header-h)); }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; gap: 12px; }
h1 { font-size: 22px; font-weight: 800; color: var(--text-primary); letter-spacing: -.3px; }
.page-sub { font-size: 12px; color: var(--text-muted); margin-top: 3px; }
.btn-export { padding: 8px 16px; border-radius: 9px; border: 1px solid var(--tint-4); background: var(--tint-1); color: var(--text-tertiary); cursor: pointer; font-size: 12px; white-space: nowrap; font-weight: 500; transition: all .2s; flex-shrink: 0; }
.btn-export:hover { background: var(--tint-3); color: var(--text-secondary); }
.filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; padding: 12px 16px; background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 12px; }
.filter-input, .filter-select { background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: 8px; padding: 7px 12px; color: var(--text-secondary); font-size: 13px; outline: none; transition: border-color .2s; }
.filter-input:focus, .filter-select:focus { border-color: color-mix(in srgb, var(--primary) 40%, transparent); }
.filter-select { padding-right: 28px; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2364748b'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 10px center; }
.filter-sep { color: var(--text-muted); font-size: 13px; }
.btn-reset { padding: 7px 14px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 13px; transition: all .2s; }
.btn-reset:hover { background: var(--tint-2); color: var(--text-tertiary); }
/* 背景/边框/圆角由全局 .panel 系列提供（含 .table-card），此处只补横向滚动 */
.table-card { overflow-x: auto; }
/* 表格的宽度/边框/居中对齐由 layout.css 的 .tbl 契约负责。
   这里**只**声明本页需要的最小宽度：列多，窄屏下靠外层 .table-wrapper 横向滚动。
   原先这里还写了 `th { text-align: left }`，特异性与 `.tbl th` 相同、
   而页面样式排在契约之后，于是"全站文字居中"这条被本页悄悄推翻了。 */
.table-wrapper table { min-width: 700px; }
thead tr { border-bottom: 1px solid var(--tint-3); background: linear-gradient(to bottom, var(--tint-1), var(--tint-1)); }
/* 只保留本页**特有的**视觉细节（字号/字重/字距）；对齐、内边距、边框
   交给 .tbl 契约。整段写 th/td 会把契约里的 text-align: center 推翻。 */
.tbl th { font-size: 11px; font-weight: 700; letter-spacing: .4px; text-transform: uppercase; }
.tbl td { font-size: 13px; }
tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: var(--tint-1); }
.level-tag { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.level-tag.sm { font-size: 10px; padding: 1px 7px; }
.conf-cell { font-weight: 700; color: var(--text-secondary); }
.time-cell { white-space: nowrap; }
.status-chip { padding: 3px 9px; border-radius: 5px; font-size: 11px; font-weight: 600; }
.status-chip.done { background: color-mix(in srgb, var(--success) 12%, transparent); color: var(--success); }
.status-chip.pending { background: color-mix(in srgb, var(--warning) 12%, transparent); color: var(--warning); }
.status-chip.rejected { background: var(--tint-3); color: var(--text-tertiary); }
.btn-sm-action.reject { border-color: var(--border-default); color: var(--text-tertiary); }
.btn-sm-action.reject:hover { background: var(--tint-2); color: var(--text-secondary); }
/* 操作列：右对齐，让每行按钮的右缘落在同一条竖线上。
   原来是 `display: flex` —— td 变成 flex 容器会脱离表格的列宽计算，
   而且按钮宽度不同时右缘参差不齐（待处理的行 3 个按钮、已处理的行只有 1 个）。
   对齐交给 td 的 text-align + 内部 .row-actions 的 inline-flex。 */
.action-col { text-align: right; white-space: nowrap; }
.btn-sm-action { padding: 4px 10px; border-radius: 6px; border: 1px solid color-mix(in srgb, var(--neutral) 25%, transparent); background: color-mix(in srgb, var(--neutral) 6%, transparent); color: var(--text-tertiary); cursor: pointer; font-size: 11px; white-space: nowrap; min-height: 30px; transition: all .15s; font-weight: 500; display: inline-flex; align-items: center; justify-content: center; }
.btn-sm-action:hover { border-color: color-mix(in srgb, var(--neutral) 40%, transparent); color: var(--text-tertiary); background: color-mix(in srgb, var(--neutral) 10%, transparent); }
.btn-sm-action.confirm { border-color: color-mix(in srgb, var(--primary) 25%, transparent); background: color-mix(in srgb, var(--primary) 7%, transparent); color: var(--primary-hover); }
.btn-sm-action.confirm:hover { background: color-mix(in srgb, var(--primary) 12%, transparent); }
.table-state { padding: 60px; text-align: center; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 10px; }
.mobile-list { display: none; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 20px; }
.page-btn { padding: 7px 16px; border-radius: 8px; border: 1px solid var(--tint-4); background: var(--tint-1); color: var(--text-tertiary); cursor: pointer; font-size: 13px; transition: all .15s; }
.page-btn:hover:not(:disabled) { background: var(--tint-3); color: var(--text-secondary); }
.page-btn:disabled { opacity: .35; cursor: not-allowed; }
.page-info { font-size: 12px; color: var(--text-tertiary); }
.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 16px; width: 440px; max-width: 95vw; box-shadow: 0 24px 64px color-mix(in srgb, var(--shadow-color) 60%, transparent); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--tint-3); }
.modal-header h3 { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: var(--tint-2); border: 1px solid var(--tint-3); border-radius: 7px; color: var(--text-tertiary); font-size: 16px; cursor: pointer; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; transition: all .15s; }
.close-btn:hover { background: var(--tint-4); color: var(--text-tertiary); }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
.detail-row { display: flex; align-items: center; gap: 10px; }
.detail-text { font-size: 13px; color: var(--text-tertiary); }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-group label { font-size: 11px; font-weight: 700; color: var(--text-tertiary); letter-spacing: .3px; text-transform: uppercase; }
.req { color: var(--danger); }
.field-group textarea { background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: 8px; padding: 10px; color: var(--text-secondary); font-size: 13px; resize: none; outline: none; font-family: inherit; transition: border-color .2s; }
.field-group textarea:focus { border-color: color-mix(in srgb, var(--primary) 40%, transparent); }
.char-count { font-size: 11px; color: var(--text-muted); text-align: right; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--tint-3); }
.btn-cancel { padding: 8px 18px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 13px; transition: all .15s; }
.btn-cancel:hover { background: var(--tint-2); }
.btn-primary { padding: 8px 20px; border-radius: 8px; border: none; background: linear-gradient(135deg, var(--primary), var(--primary-active)); color: var(--text-on-color); cursor: pointer; font-weight: 600; font-size: 13px; transition: all .15s; box-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 30%, transparent); }
.btn-primary:hover:not(:disabled) { box-shadow: 0 4px 16px color-mix(in srgb, var(--primary) 40%, transparent); transform: translateY(-1px); }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
/* ── 身份判定 ─────────────────────────────────────────────────────────
   只有一套配色：不确定 = 警示黄，其余一律中性。身份"确定"不是值得庆贺的
   状态，它只是常态；把常态也染上颜色会让真正需要注意的那一行失去对比度。 */
.identity-cell { white-space: nowrap; }
.id-ambiguous {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 9px; border-radius: var(--radius-full, 999px);
  border: 1px solid var(--level-medium); background: var(--level-medium-soft, color-mix(in srgb, var(--warning) 12%, transparent));
  color: var(--level-medium); font-size: 12px; font-weight: 600; cursor: pointer;
}
.id-ambiguous:hover { background: var(--level-medium-soft, color-mix(in srgb, var(--warning) 20%, transparent)); }
.id-hint { margin-left: 6px; font-size: 12px; color: var(--text-muted); }
.id-unmatched { font-size: 12px; color: var(--text-muted); }
.id-manual {
  margin-left: 6px; padding: 1px 6px; border-radius: var(--radius-sm, 4px);
  background: var(--tint-2); color: var(--text-tertiary); font-size: 11px;
}

.identity-block {
  margin-bottom: 14px; padding: 12px 14px;
  border: 1px solid var(--tint-4); border-radius: var(--radius-md);
  background: var(--bg-surface-2, var(--tint-1));
}
.identity-block.warn { border-color: var(--level-medium); background: var(--level-medium-soft, color-mix(in srgb, var(--warning) 8%, transparent)); }
.id-title {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 10px;
}
.id-method {
  padding: 2px 8px; border-radius: var(--radius-full, 999px);
  font-size: 11px; font-weight: 500;
  background: var(--tint-2); color: var(--text-tertiary);
}
.id-method.im-ambiguous { background: var(--level-medium); color: var(--text-on-color); }
.id-method.im-manual { background: var(--primary); color: var(--text-on-color); }
.id-warn-text {
  text-align: center; font-size: 12px; line-height: 1.7;
  color: var(--text-secondary); margin-bottom: 10px;
}
.id-candidates { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.id-cand {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  min-width: 84px; padding: 8px 14px; cursor: pointer;
  border: 1px solid var(--border-default); border-radius: var(--radius-md);
  background: var(--bg-surface); color: var(--text-primary);
  transition: all var(--duration-fast, .15s) var(--ease-smooth, ease);
}
.id-cand:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.id-cand:disabled { opacity: .5; cursor: not-allowed; }
.id-cand.active { border-color: var(--primary); background: var(--primary-soft, color-mix(in srgb, var(--primary) 12%, transparent)); }
.id-bed { font-size: 11px; color: var(--text-muted); }
.id-name { font-size: 13px; font-weight: 600; }

.drawer-mask { position: fixed; inset: 0; background: var(--bg-overlay); z-index: 1000; display: flex; justify-content: flex-end; }
.drawer { width: 420px; max-width: 95vw; background: var(--bg-surface); border-left: 1px solid var(--tint-4); display: flex; flex-direction: column; height: 100vh; box-shadow: -8px 0 32px color-mix(in srgb, var(--shadow-color) 40%, transparent); }
.drawer-header { padding: 20px; border-bottom: 1px solid var(--tint-3); display: flex; align-items: flex-start; justify-content: space-between; flex-shrink: 0; }
.drawer-header h3 { font-size: 15px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
.drawer-sub { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-tertiary); }
.drawer-body { flex: 1; overflow-y: auto; padding: 24px; }
.drawer-body::-webkit-scrollbar { width: 3px; }
.drawer-body::-webkit-scrollbar-thumb { background: var(--tint-3); border-radius: 2px; }
.evidence-block { background: var(--bg-inset); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: var(--space-4); margin-bottom: var(--space-4); }
.ev-title { font-size: var(--text-base); font-weight: 650; color: var(--text-primary); margin-bottom: var(--space-3); }
.ev-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.ev-label { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: 4px; }
.ev-value { font-size: var(--text-md); font-weight: 600; color: var(--text-primary); margin-bottom: 6px; }
.ev-bar { height: 5px; background: var(--tint-3); border-radius: var(--radius-full); overflow: hidden; }
.ev-bar span { display: block; height: 100%; border-radius: var(--radius-full); }
.ev-num { font-size: var(--text-sm); color: var(--text-tertiary); margin-top: 5px; font-variant-numeric: tabular-nums; }
.ev-foot { font-size: var(--text-sm); color: var(--text-muted); line-height: 1.7; margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.ev-foot strong { color: var(--primary); }
.timeline { display: flex; flex-direction: column; margin-bottom: 28px; }
.tl-item { display: grid; grid-template-columns: 18px 1fr; grid-template-rows: auto 1fr; gap: 0 14px; }
.tl-dot { width: 16px; height: 16px; border-radius: 50%; border: 2px solid; grid-row: 1; grid-column: 1; margin-top: 2px; z-index: 1; }
.tl-dot.active { border-color: var(--success); background: var(--success); box-shadow: 0 0 8px var(--success)60; }
.tl-dot.pending { border-color: var(--text-muted); background: var(--bg-inset); }
.tl-line { grid-row: 2; grid-column: 1; width: 2px; background: var(--tint-3); margin: 4px auto 0; min-height: 28px; }
.tl-content { grid-column: 2; grid-row: 1 / 3; padding-bottom: 20px; }
.tl-title { font-size: 13px; font-weight: 700; color: var(--text-secondary); }
.tl-time { font-size: 11px; color: var(--text-muted); margin-top: 3px; }
.tl-desc { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; line-height: 1.5; }
.tl-pending { font-size: 12px; color: var(--text-muted); margin-top: 4px; font-style: italic; }
.tl-item.done .tl-title { color: var(--success); }
.tl-meta { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 9px; }
.meta-row { display: flex; gap: 12px; font-size: 12px; }
.meta-label { color: var(--text-muted); width: 52px; flex-shrink: 0; }
.drawer-enter-active, .drawer-leave-active { transition: transform .3s ease; }
.drawer-enter-from, .drawer-leave-to { transform: translateX(100%); }
.ml-auto { margin-left: auto; }

@media (max-width: 768px) {
  .page { padding: 14px; }
  h1 { font-size: 19px; }
  .page-header { flex-wrap: wrap; gap: 8px; }
  .filter-bar { gap: 6px; padding: 10px 12px; }
  .filter-input, .filter-select { font-size: 12px; padding: 7px 10px; flex: 1 1 130px; min-width: 0; }
  .filter-sep { display: none; }
  .desktop-table { display: none; }
  .mobile-list { display: block; }
  .alert-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 12px; padding: 14px; margin-bottom: 10px; }
  /* 等级色条一律走 --level-*（此前 high 用 --danger、medium 用 var(--warning)、
     low 用 --primary，三个不同来源，且 medium 的 var(--warning) 两个主题里都不是 token 值） */
  .alert-card.lvl-high { border-left: 3px solid var(--level-high); }
  .alert-card.lvl-medium { border-left: 3px solid var(--level-medium); }
  .alert-card.lvl-low { border-left: 3px solid var(--level-low); }
  .alert-card.lvl-normal { border-left: 3px solid var(--level-normal); }
  .alert-card.lvl-urgent { border-left: 3px solid var(--level-urgent); }
  .ac-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
  .ac-elder { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
  .ac-room { font-size: 12px; color: var(--text-tertiary); }
  .ac-mid { display: flex; gap: 12px; margin-bottom: 10px; font-size: 12px; color: var(--text-muted); }
  .ac-conf { font-weight: 600; color: var(--text-tertiary); }
  .ac-actions { display: flex; gap: 8px; }
  .btn-sm-action { flex: 1; min-height: 44px; font-size: 13px; }
  .table-state { padding: 40px 16px; }
  .pagination { gap: 8px; flex-wrap: wrap; justify-content: center; }
  .page-btn { padding: 8px 14px; font-size: 13px; min-height: 44px; }
  .page-info { font-size: 12px; width: 100%; text-align: center; order: -1; }
  .modal-mask { align-items: flex-end; }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; }
  .field-group textarea { font-size: 16px; padding: 12px; }
  .modal-footer { flex-direction: column; gap: 8px; padding: 12px 16px 20px; }
  .btn-cancel, .btn-primary { width: 100%; min-height: 48px; font-size: 15px; border-radius: 12px; justify-content: center; display: flex; align-items: center; }
  .drawer { width: 100% !important; max-width: 100% !important; border-left: none; border-top: 1px solid var(--tint-4); border-radius: 20px 20px 0 0; height: 88vh; }
  .drawer-mask { flex-direction: column; justify-content: flex-end; }
  .drawer-enter-from, .drawer-leave-to { transform: translateY(100%); }
}

/* ══════ AI 证据列 ══════ */
.ev-cell { white-space: nowrap; }
.ev-pill {
  display: inline-block; padding: 2px 7px; border-radius: 20px;
  font-size: 11px; font-weight: 600;
  background: var(--tint-2); color: var(--text-secondary);
  border: 1px solid var(--tint-3);
}
/* 姿态标签按类型着色，扫一眼就能区分"横卧/坐姿/弯腰" */
.ev-pill.pt-fall_like { background: color-mix(in srgb, var(--danger) 12%, transparent); color: var(--danger-text); border-color: color-mix(in srgb, var(--danger) 28%, transparent); }
.ev-pill.pt-lying     { background: color-mix(in srgb, var(--warning) 14%, transparent); color: var(--warning-text); border-color: color-mix(in srgb, var(--warning) 30%, transparent); }
.ev-pill.pt-sitting,
.ev-pill.pt-standing,
.ev-pill.pt-bending   { background: var(--tint-1); color: var(--text-tertiary); }
.ev-pill.expr { background: color-mix(in srgb, var(--violet-text) 10%, transparent); color: var(--violet-text); border-color: color-mix(in srgb, var(--violet-text) 22%, transparent); }
.ev-dim { font-size: 11px; color: var(--text-muted); margin-left: 5px; font-variant-numeric: tabular-nums; }
.ev-flag {
  display: inline-block; margin-left: 5px; padding: 1px 6px; border-radius: 4px;
  font-size: 10px; font-weight: 700;
  background: color-mix(in srgb, var(--danger) 14%, transparent); color: var(--danger-text);
}
.ev-unknown { font-size: 11px; color: var(--text-muted); font-style: italic; }

/* ══════ 抽屉里的明细块 ══════ */
.detail-block { margin-top: 14px; }
.db-title {
  font-size: 12px; font-weight: 700; color: var(--text-secondary);
  margin-bottom: 8px; text-align: center;
  padding-bottom: 6px; border-bottom: 1px solid var(--border-subtle);
}
.db-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 14px; }
.db-item {
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px; font-size: 12px;
}
.db-k { color: var(--text-muted); }
.db-v {
  color: var(--text-primary); font-weight: 600;
  font-variant-numeric: tabular-nums; text-align: right;
}
</style>
