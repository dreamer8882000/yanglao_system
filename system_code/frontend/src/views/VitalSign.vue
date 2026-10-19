<template>
  <div class="page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h1>❤️ 生命体征</h1>
        <div class="header-sub">老人健康数据监测与预警</div>
      </div>
      <button @click="showAddModal = true" class="primary-btn">
        + 录入体征
      </button>
    </div>

    <!-- 异常预警 -->
    <div v-if="alerts.length > 0" class="alerts-section">
      <div class="section-title">
        <span>⚠️ 异常预警</span>
        <span class="count-badge">{{ alerts.length }}</span>
      </div>
      <div class="alerts-grid">
        <div v-for="alert in alerts" :key="alert.id" class="alert-card">
          <div class="alert-icon">🚨</div>
          <div class="alert-content">
            <div class="alert-elder">{{ alert.elderName }} ({{ alert.roomNo }}房)</div>
            <div class="alert-detail">{{ alert.alertMessage }}</div>
            <div class="alert-time">{{ formatDateTime(alert.recordTime) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 条件查询：关键词 + 老人 + 记录日期区间
         老人下拉同时驱动下面的体征趋势图（趋势接口按 elderId 取数），
         因此它留在这里而不是沉到表格上方 —— 用户先选人，再看趋势和明细。 -->
    <div class="toolbar">
      <input v-model="filters.keyword" class="toolbar-search"
        placeholder="备注关键词" @input="applyFilters(true)" />
      <select v-model="filters.elderId" class="toolbar-field" @change="onElderChange">
        <option value="">全部老人</option>
        <option v-for="elder in elders" :key="elder.id" :value="elder.id">
          {{ elder.name }}（{{ elder.roomNo }}房）
        </option>
      </select>
      <span class="toolbar-label">记录日期</span>
      <input v-model="filters.startDate" type="date" class="toolbar-field" @change="applyFilters()" />
      <span class="toolbar-label">至</span>
      <input v-model="filters.endDate" type="date" class="toolbar-field" @change="applyFilters()" />
      <span class="toolbar-label">趋势</span>
      <select v-model="filters.days" class="toolbar-field" @change="loadTrend">
        <option value="7">近7天</option>
        <option value="14">近14天</option>
        <option value="30">近30天</option>
      </select>
      <button class="toolbar-reset" :disabled="!filterActive" @click="resetFilters">重置</button>
    </div>

    <!-- 趋势图表 -->
    <div v-if="filters.elderId && trendData" class="chart-section">
      <div class="section-title">
        <span>📈 体征趋势</span>
      </div>
      <div class="charts-grid">
        <div class="chart-card">
          <h3>血压趋势</h3>
          <div class="chart-placeholder">
            <canvas ref="bpChart"></canvas>
          </div>
        </div>
        <div class="chart-card">
          <h3>血糖趋势</h3>
          <div class="chart-placeholder">
            <canvas ref="bgChart"></canvas>
          </div>
        </div>
        <div class="chart-card">
          <h3>心率趋势</h3>
          <div class="chart-placeholder">
            <canvas ref="hrChart"></canvas>
          </div>
        </div>
        <div class="chart-card">
          <h3>体温趋势</h3>
          <div class="chart-placeholder">
            <canvas ref="tempChart"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- 体征记录列表 -->
    <div class="list-section">
      <div class="section-title">
        <span>📋 体征记录</span>
      </div>
      <div v-if="recLoading" class="list-state">加载中…</div>
      <div v-else-if="recError" class="load-error">{{ recError }}</div>
      <div v-else-if="!records.length" class="list-state">当前条件下没有体征记录</div>
      <div v-else class="desktop-table">
        <div class="table-wrapper">
          <table class="tbl">
            <thead>
              <tr>
                <th>老人姓名</th>
                <th>房间号</th>
                <th>血压</th>
                <th>心率</th>
                <th>血糖</th>
                <th>体温</th>
                <th>记录时间</th>
                <th>记录人</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in records" :key="record.id">
                <td>{{ record.elderName }}</td>
                <td>{{ record.roomNo }}</td>
                <td>
                  <span :class="getStatusClass(record.bloodPressure, 'bp')">
                    {{ record.bloodPressure || '-' }}
                  </span>
                </td>
                <td>
                  <span :class="getStatusClass(record.heartRate, 'hr')">
                    {{ record.heartRate || '-' }}
                  </span>
                </td>
                <td>
                  <span :class="getStatusClass(record.bloodGlucose, 'bg')">
                    {{ record.bloodGlucose || '-' }}
                  </span>
                </td>
                <td>
                  <span :class="getStatusClass(record.temperature, 'temp')">
                    {{ record.temperature || '-' }}
                  </span>
                </td>
                <td>{{ formatDateTime(record.recordTime) }}</td>
                <td>{{ record.recorderName }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 分页放在 .desktop-table 之外：窄屏下表格是 display:none，
           分页留在里面手机上就翻不了页。 -->
      <Pagination
        v-model:page="vitalPage" v-model:pageSize="vitalPageSize"
        :total="vitalTotal" @change="loadRecords"
      />

      <!-- 移动端卡片（三态由上面统一处理） -->
      <div v-if="!recLoading && !recError && records.length" class="mobile-cards">
        <div v-for="record in records" :key="record.id" class="vital-card">
          <div class="card-header">
            <div class="elder-info">
              <span class="elder-name">{{ record.elderName }}</span>
              <span class="room-badge">{{ record.roomNo }}房</span>
            </div>
            <div class="record-time">{{ formatDateTime(record.recordTime) }}</div>
          </div>
          <div class="card-body">
            <div class="vital-item" v-if="record.bloodPressure">
              <span class="vital-label">血压</span>
              <span class="vital-value" :class="getStatusClass(record.bloodPressure, 'bp')">
                {{ record.bloodPressure }} mmHg
              </span>
            </div>
            <div class="vital-item" v-if="record.heartRate">
              <span class="vital-label">心率</span>
              <span class="vital-value" :class="getStatusClass(record.heartRate, 'hr')">
                {{ record.heartRate }} 次/分
              </span>
            </div>
            <div class="vital-item" v-if="record.bloodGlucose">
              <span class="vital-label">血糖</span>
              <span class="vital-value" :class="getStatusClass(record.bloodGlucose, 'bg')">
                {{ record.bloodGlucose }} mmol/L
              </span>
            </div>
            <div class="vital-item" v-if="record.temperature">
              <span class="vital-label">体温</span>
              <span class="vital-value" :class="getStatusClass(record.temperature, 'temp')">
                {{ record.temperature }} ℃
              </span>
            </div>
          </div>
          <div class="card-footer">
            <span class="recorder">记录人:{{ record.recorderName }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加体征弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showAddModal" class="modal-overlay" @click="closeModal">
          <div class="modal-content" @click.stop>
            <div class="modal-header">
              <h2>📝 录入体征数据</h2>
              <button class="close-btn" @click="closeModal">×</button>
            </div>
            <div class="modal-body">
              <form @submit.prevent="submitVital">
                <div class="form-group">
                  <label>选择老人 *</label>
                  <select v-model="vitalForm.elderId" required class="input-field">
                    <option value="">请选择</option>
                    <option v-for="elder in elders" :key="elder.id" :value="elder.id">
                      {{ elder.name }} ({{ elder.roomNo }}房)
                    </option>
                  </select>
                </div>

                <div class="form-row">
                  <div class="form-group">
                    <label>血压（mmHg）</label>
                    <input
                      v-model="vitalForm.bloodPressure"
                      placeholder="如:120/80"
                      class="input-field"
                    />
                  </div>

                  <div class="form-group">
                    <label>心率（次/分）</label>
                    <input
                      v-model.number="vitalForm.heartRate"
                      type="number"
                      placeholder="如:75"
                      class="input-field"
                    />
                  </div>
                </div>

                <div class="form-row">
                  <div class="form-group">
                    <label>血糖（mmol/L）</label>
                    <input
                      v-model.number="vitalForm.bloodGlucose"
                      type="number"
                      step="0.1"
                      placeholder="如:5.6"
                      class="input-field"
                    />
                  </div>

                  <div class="form-group">
                    <label>体温（℃）</label>
                    <input
                      v-model.number="vitalForm.temperature"
                      type="number"
                      step="0.1"
                      placeholder="如:36.5"
                      class="input-field"
                    />
                  </div>
                </div>

                <div class="form-group">
                  <label>备注</label>
                  <textarea
                    v-model="vitalForm.notes"
                    placeholder="其他观察记录"
                    class="textarea-field"
                  ></textarea>
                </div>

                <div class="modal-footer">
                  <button type="button" @click="closeModal" class="btn-cancel">取消</button>
                  <button type="submit" class="btn-confirm">保存</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Toast ref="toastRef" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue';
import Pagination from '../components/Pagination.vue';
import {
  getVitalSignList,
  createVitalSign,
  getVitalTrend,
  getVitalAlerts
} from '../api/vitalSigns';
import { getElderList } from '../api/elders';
import Toast from '../components/Toast.vue';
import dayjs from 'dayjs';

const records = ref([]);
const vitalPage = ref(1);
const vitalPageSize = ref(10);
const vitalTotal = ref(0);
// 体征记录表的三态：加载中 / 失败 / 空。三者互斥 ——
// 只用"数组为空"表达的话，"接口挂了"会显示成"这段时间没有记录"。
const recLoading = ref(false);
const recError = ref('');
const alerts = ref([]);
const elders = ref([]);
const trendData = ref(null);
const showAddModal = ref(false);
const toastRef = ref(null);

const bpChart = ref(null);
const bgChart = ref(null);
const hrChart = ref(null);
const tempChart = ref(null);

const filters = ref({
  keyword: '',
  elderId: '',
  startDate: '',
  endDate: '',
  days: 7
});

/** 去掉空条件：空字符串会被后端当作"没有条件"，但传上去只会让 URL 变脏 */
const cleanParams = (o) => Object.fromEntries(
  Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined));
/** 重置按钮的可用性：任一条件非默认值（days 是趋势窗口，不算列表条件） */
const filterActive = computed(() =>
  !!(filters.value.keyword || filters.value.elderId
     || filters.value.startDate || filters.value.endDate));

/**
 * 条件变化 → 回到第 1 页再取数。
 * Pagination 组件只在换每页条数时自动回第 1 页；条件变化不在它的职责里，
 * 不回第 1 页就会停在越界页显示空白。搜索框逐字符触发，加 300ms 防抖。
 */
let filterTimer = null;
function applyFilters(debounced = false) {
  clearTimeout(filterTimer);
  const run = () => { vitalPage.value = 1; loadRecords(); };
  if (debounced) filterTimer = setTimeout(run, 300); else run();
}
function onElderChange() {
  applyFilters();
  loadTrend();          // 趋势图跟的是同一位老人
}
function resetFilters() {
  clearTimeout(filterTimer);
  filters.value = { keyword: '', elderId: '', startDate: '', endDate: '', days: filters.value.days };
  vitalPage.value = 1;
  loadRecords();
  loadTrend();
}

const vitalForm = ref({
  elderId: '',
  bloodPressure: '',
  heartRate: null,
  bloodGlucose: null,
  temperature: null,
  notes: ''
});

const showToast = (message, type = 'success') => {
  toastRef.value?.show(message, type);
};

/**
 * 取全部在册老人（供工具栏的「全部老人」下拉使用）。
 *
 * 为什么不发一次请求就完事：/elders/ 是分页接口（本机构 154 位），pageSize 上限
 * 100，且按 id DESC 返回 —— 只取第一页只能拿到 id 最大的那 100 位，而**有体征/
 * 巡查/用药数据的前几位老人（id 1~10）恰好落在第二页**。下拉里根本选不到他们，
 * 这个条件查询就是个摆设。所以这里把分页翻完再合并。
 */
async function fetchAllElders() {
  const PAGE = 100;
  const first = await getElderList({ status: 1, page: 1, pageSize: PAGE });
  const d = first.data.data || {};
  let list = Array.isArray(d.data) ? d.data : [];
  const total = Number(d.total) || list.length;
  for (let p = 2; p <= Math.ceil(total / PAGE); p++) {
    const r = await getElderList({ status: 1, page: p, pageSize: PAGE });
    list = list.concat(r.data.data?.data || []);
  }
  return list;
}

const loadData = async () => {
  try {
    const [elderList, alertsRes] = await Promise.all([
      fetchAllElders(),
      getVitalAlerts({ days: 7 })
    ]);
    elders.value = elderList;
    alerts.value = alertsRes.data.data || [];
  } catch (error) {
    console.error('加载失败:', error);
    showToast('数据加载失败', 'error');
  }
  loadRecords();
  loadTrend();
};

const loadRecords = async () => {
  recLoading.value = true;
  try {
    // 同 /vital-signs/ 是分页接口，原实现把分页对象当数组用，
    // 结果只能看到第一页（实测 34 条只显示 20 条）。
    const res = await getVitalSignList({
      ...cleanParams(filters.value),
      page: vitalPage.value, pageSize: vitalPageSize.value
    });
    const rec = res.data.data || {};
    records.value = Array.isArray(rec) ? rec : (rec.data || []);
    vitalTotal.value = Array.isArray(rec) ? rec.length : (rec.total || 0);
    recError.value = '';
  } catch (error) {
    console.error('加载体征记录失败', error);
    recError.value = `体征记录加载失败：${error?.friendlyMessage || '未知错误'}`;
    showToast('数据加载失败', 'error');
  } finally {
    recLoading.value = false;
  }
};

const loadTrend = async () => {
  if (!filters.value.elderId) {
    trendData.value = null;
    return;
  }

  try {
    const res = await getVitalTrend({
      elderId: filters.value.elderId,
      days: filters.value.days
    });
    trendData.value = res.data.data;
    
    await nextTick();
    renderCharts();
  } catch (error) {
    console.error('加载趋势失败:', error);
  }
};

const renderCharts = () => {
  if (!trendData.value) return;
  const { dates, bloodPressure, heartRate, bloodGlucose, temperature } = trendData.value;
  console.log('Chart data:', { dates, bloodPressure, heartRate, bloodGlucose, temperature });
};

const submitVital = async () => {
  try {
    await createVitalSign(vitalForm.value);
    showToast('体征录入成功');
    closeModal();
    loadData();
  } catch (error) {
    console.error('录入失败:', error);
    showToast('录入失败: ' + error.message, 'error');
  }
};

const closeModal = () => {
  showAddModal.value = false;
  vitalForm.value = {
    elderId: '',
    bloodPressure: '',
    heartRate: null,
    bloodGlucose: null,
    temperature: null,
    notes: ''
  };
};

const getStatusClass = (value, type) => {
  if (!value) return '';
  
  if (type === 'hr') {
    const hr = parseInt(value);
    if (hr < 60 || hr > 100) return 'abnormal';
  } else if (type === 'temp') {
    const temp = parseFloat(value);
    if (temp < 36 || temp > 37.5) return 'abnormal';
  }
  
  return 'normal';
};

const formatDateTime = (time) => {
  return dayjs(time).format('MM-DD HH:mm');
};

onMounted(loadData);
</script>

<style scoped>


.header-section h1 {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.5px;
  text-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 30%, transparent);
  margin-bottom: 8px;
}

.header-sub {
  font-size: 14px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.count-badge {
  padding: 4px 12px;
  background: color-mix(in srgb, var(--danger) 15%, transparent);
  color: var(--danger-text);
  border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent);
  border-radius: 12px;
  font-size: 13px;
  font-weight: 700;
}

.alerts-section {
  margin-bottom: 40px;
  animation: fadeIn 0.5s ease 0.1s both;
}

.alerts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 20px;
}

.alert-card {
  background: color-mix(in srgb, var(--danger) 8%, transparent);
  backdrop-filter: blur(20px);
  border: 1px solid color-mix(in srgb, var(--danger) 25%, transparent);
  border-left: 4px solid var(--danger);
  padding: 20px;
  border-radius: 12px;
  display: flex;
  gap: 18px;
  transition: all 0.3s ease;
}

.alert-card:hover {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  border-color: color-mix(in srgb, var(--danger) 35%, transparent);
  transform: translateY(-2px);
}

.alert-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-elder {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.alert-detail {
  font-size: 14px;
  color: var(--danger-text);
  margin-bottom: 6px;
  line-height: 1.5;
}

.alert-time {
  font-size: 13px;
  color: var(--text-tertiary);
}

.chart-section {
  margin-bottom: 40px;
  animation: fadeIn 0.5s ease 0.3s both;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 20px;
}

.chart-card {
  background: var(--tint-1);
  backdrop-filter: blur(40px);
  border: 1px solid var(--tint-3);
  padding: 24px;
  border-radius: var(--radius-md);
  transition: all 0.3s ease;
}

.chart-card:hover {
  background: var(--tint-2);
  border-color: color-mix(in srgb, var(--primary) 30%, transparent);
  transform: translateY(-2px);
}

.chart-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.chart-placeholder {
  height: 220px;
  background: var(--tint-1);
  border: 1px dashed var(--tint-4);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-size: 14px;
}

.list-section {
  animation: fadeIn 0.5s ease 0.4s both;
}

.desktop-table {
  display: block;
}

.table-wrapper {
  background: var(--tint-1);
  backdrop-filter: blur(40px);
  border: 1px solid var(--tint-3);
  border-radius: 12px;
  overflow: hidden;
}

/* 表格的宽度/边框/对齐/内边距由 layout.css 的 .tbl 契约负责（全站统一居中）。
   这里原先整段写了 table/th/td 并把 th 设成 text-align: left，
   特异性与 .tbl th 相同、页面样式又排在契约之后 —— 于是本页把
   "全站文字居中"推翻了（实测 th 计算值是 left）。 */
.tbl th { letter-spacing: 0.5px; }

tbody tr {
  transition: background 0.2s ease;
}

tbody tr:hover {
  background: color-mix(in srgb, var(--primary) 5%, transparent);
}

.list-state {
  padding: var(--space-6);
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

.normal {
  color: var(--success-text);
  font-weight: 600;
}

.abnormal {
  padding: 4px 10px;
  background: color-mix(in srgb, var(--danger) 15%, transparent);
  color: var(--danger-text);
  border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent);
  border-radius: 6px;
  font-weight: 600;
  display: inline-block;
}

.mobile-cards {
  display: none;
}

.primary-btn {
  padding: 12px 24px;
  background: linear-gradient(135deg, var(--primary), var(--violet));
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--primary) 30%, transparent);
}

.primary-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px color-mix(in srgb, var(--primary) 40%, transparent);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--bg-overlay);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.modal-content {
  background: var(--bg-surface);
  border: 1px solid var(--tint-4);
  border-radius: 16px;
  width: 100%;
  max-width: 580px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px color-mix(in srgb, var(--shadow-color) 50%, transparent);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid var(--tint-3);
}

.modal-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--tint-4);
  background: var(--tint-1);
  color: var(--text-tertiary);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.close-btn:hover {
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-color: color-mix(in srgb, var(--danger) 30%, transparent);
  color: var(--danger-text);
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.form-group {
  margin-bottom: 24px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}

.input-field {
  width: 100%;
  padding: 12px 16px;
  background: var(--tint-2);
  border: 1px solid var(--tint-4);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 14px;
  transition: all 0.3s ease;
  box-sizing: border-box;
}

.input-field::placeholder {
  color: var(--text-tertiary);
}

.input-field:focus {
  outline: none;
  border-color: color-mix(in srgb, var(--primary) 50%, transparent);
  background: var(--tint-3);
}

.textarea-field {
  width: 100%;
  padding: 12px 16px;
  background: var(--tint-2);
  border: 1px solid var(--tint-4);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 14px;
  resize: vertical;
  font-family: inherit;
  transition: all 0.3s ease;
  box-sizing: border-box;
  min-height: 80px;
}

.textarea-field::placeholder {
  color: var(--text-tertiary);
}

.textarea-field:focus {
  outline: none;
  border-color: color-mix(in srgb, var(--primary) 50%, transparent);
  background: var(--tint-3);
}

.modal-footer {
  display: flex;
  gap: 16px;
  padding: 20px 24px;
  border-top: 1px solid var(--tint-3);
}

.btn-cancel,
.btn-confirm {
  flex: 1;
  padding: 12px 24px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  border: none;
}

.btn-cancel {
  background: var(--tint-2);
  color: var(--text-tertiary);
  border: 1px solid var(--tint-4);
}

.btn-cancel:hover {
  background: var(--tint-3);
}

.btn-confirm {
  background: linear-gradient(135deg, var(--primary), var(--violet));
  color: white;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--primary) 30%, transparent);
}

.btn-confirm:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px color-mix(in srgb, var(--primary) 40%, transparent);
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-content {
  transform: scale(0.95) translateY(20px);
}

.modal-leave-to .modal-content {
  transform: scale(0.95) translateY(20px);
}

@media (max-width: 768px) {
  .vital-container {
    padding: 16px;
  }

  .header-section {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
    margin-bottom: 24px;
  }

  .header-section h1 {
    font-size: 24px;
  }

  .header-sub {
    font-size: 13px;
  }

  .primary-btn {
    width: 100%;
    padding: 14px;
    font-size: 16px;
  }

  .alerts-section {
    margin-bottom: 32px;
  }

  .alerts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .alert-card {
    padding: 16px;
    gap: 14px;
  }

  .chart-section {
    margin-bottom: 32px;
  }

  .charts-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .chart-card {
    padding: 20px;
  }

  .chart-placeholder {
    height: 180px;
  }

  .desktop-table {
    display: none;
  }

  .mobile-cards {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .vital-card {
    background: var(--tint-1);
    backdrop-filter: blur(40px);
    border: 1px solid var(--tint-3);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.3s ease;
  }

  .vital-card:active {
    background: var(--tint-2);
    transform: scale(0.98);
  }

  .card-header {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--tint-2);
  }

  .elder-info {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .elder-name {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .room-badge {
    padding: 4px 10px;
    background: color-mix(in srgb, var(--primary) 15%, transparent);
    color: var(--primary-hover);
    border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent);
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
  }

  .record-time {
    font-size: 13px;
    color: var(--text-tertiary);
  }

  .card-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }

  .vital-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px;
    background: var(--tint-1);
    border: 1px solid var(--tint-2);
    border-radius: 10px;
  }

  .vital-label {
    font-size: 12px;
    color: var(--text-tertiary);
  }

  .vital-value {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-secondary);
  }

  .vital-value.normal {
    color: var(--success-text);
  }

  .vital-value.abnormal {
    color: var(--danger-text);
  }

  .card-footer {
    padding-top: 12px;
    border-top: 1px solid var(--tint-2);
  }

  .recorder {
    font-size: 13px;
    color: var(--text-tertiary);
  }

  .modal-overlay {
    align-items: flex-end;
    padding: 0;
  }

  .modal-content {
    max-width: 100%;
    border-radius: 20px 20px 0 0;
    max-height: 85vh;
  }

  .modal-body {
    padding: 20px;
  }

  .form-row {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .input-field {
    font-size: 16px;
    padding: 14px 16px;
  }

  .textarea-field {
    font-size: 16px;
    padding: 14px 16px;
  }

  .modal-footer {
    flex-direction: column-reverse;
    gap: 12px;
  }

  .btn-cancel,
  .btn-confirm {
    width: 100%;
    padding: 14px;
    font-size: 16px;
  }

  .modal-enter-from .modal-content,
  .modal-leave-to .modal-content {
    transform: translateY(100%);
  }
}
</style>