<template>
  <div class="page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>🌙 夜间巡查记录</h1>
      <button @click="showScanModal = true" class="primary-btn">
        📱 扫码巡查
      </button>
    </div>

    <!-- 巡查任务：派发 → 执行 → 回写 -->
    <!-- 此前这里是"只有记录没有任务"：能看到谁巡过了，却看不到今晚还有哪几间房没巡，
         也无法把任务指派给具体的人。现在任务由后端按房间批量生成并自动指派给当班
         护理员，完成后回写一条巡查记录，形成可追溯的闭环。 -->
    <div class="task-section">
      <div class="task-head">
        <div>
          <h2>今晚巡查任务</h2>
          <span class="task-sub" v-if="tasks.length">
            待执行 {{ taskCounts.pending }} · 已完成 {{ taskCounts.done }} · 跳过 {{ taskCounts.skipped }}
          </span>
        </div>
        <div class="task-actions">
          <button class="ghost-btn" @click="loadTasks" :disabled="taskLoading">刷新</button>
          <button class="primary-btn" @click="doGenerate" :disabled="taskLoading">生成本夜任务</button>
        </div>
      </div>

      <div v-if="taskLoading" class="task-empty">加载中…</div>
      <div v-else-if="!tasks.length" class="task-empty">
        今晚还没有巡查任务。点「生成本夜任务」会按房间批量创建，并自动指派给当前在岗的护理员。
      </div>
      <div v-else class="task-list">
        <div v-for="t in taskPaged" :key="t.id" class="task-row" :class="{ done: t.status === 1 }">
          <div class="task-room">{{ t.roomNo }}房</div>
          <div class="task-info">
            <div class="task-elder">{{ t.elderName || '—' }}</div>
            <div class="task-window">{{ fmtWindow(t) }}</div>
          </div>
          <div class="task-assignee">{{ t.assigneeName || '未指派' }}</div>
          <span class="task-status" :class="'st-' + t.status">{{ statusLabel(t.status) }}</span>
          <div class="row-actions task-btns">
            <button v-if="t.status === 0" class="mini-btn ok" @click="doComplete(t, 1)">完成</button>
            <button v-if="t.status === 0" class="mini-btn" @click="doComplete(t, 2)">跳过</button>
            <span v-else class="task-note">{{ t.notes || '' }}</span>
          </div>
        </div>
        <!-- 分页必须在任务循环之外：此前被插进了 task-row 内部，
             于是每一行都渲染出一个分页控件（实测页面里出现 10 个）。 -->
        <Pagination
          v-model:page="taskPage" v-model:pageSize="taskPageSize"
          :total="taskTotal"
        />
      </div>
    </div>

    <!-- 待巡查提醒 -->
    <div v-if="pendingRooms.length > 0" class="alert-box warning">
      <span class="alert-icon">⚠️</span>
      <span>待巡查房间:{{ pendingRooms.map(r => r.roomNo).join(', ') }}</span>
    </div>

    <!-- 巡查统计 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.todayTotal }}</div>
        <div class="stat-label">今日巡查</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.completionRate }}%</div>
        <div class="stat-label">完成率</div>
        <!-- 必须带上分母。完成率的分母是「窗口已过、应该已完成」的任务，
             傍晚打开页面时夜里四轮还没到点，分母可能极小（实测 0/1）——
             单看一个 0% 会以为"巡查全都没做"，而事实是"还没轮到"。
             这里把两个口径都摊开，让人一眼看出数字是怎么来的。 -->
        <div class="stat-note">
          已到点 {{ stats.dueDone ?? 0 }}/{{ stats.dueTotal ?? 0 }} ·
          今日全部 {{ stats.taskDone ?? 0 }}/{{ stats.taskTotal ?? 0 }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.avgInterval }}分钟</div>
        <div class="stat-label">平均间隔</div>
        <div class="stat-note">最久 {{ stats.maxInterval ?? 0 }} 分钟没人巡查</div>
      </div>
    </div>

    <!-- 条件查询：房间号（location 就是房间号）+ 老人 + 巡查日期区间 -->
    <div class="toolbar">
      <input v-model="filters.keyword" class="toolbar-search"
        placeholder="房间号 / 备注关键词" @input="applyFilters(true)" />
      <select v-model="filters.elderId" class="toolbar-field" @change="applyFilters()">
        <option value="">全部老人</option>
        <option v-for="elder in elders" :key="elder.id" :value="elder.id">
          {{ elder.name }}（{{ elder.roomNo }}房）
        </option>
      </select>
      <span class="toolbar-label">巡查日期</span>
      <input v-model="filters.startDate" type="date" class="toolbar-field" @change="applyFilters()" />
      <span class="toolbar-label">至</span>
      <input v-model="filters.endDate" type="date" class="toolbar-field" @change="applyFilters()" />
      <button class="toolbar-reset" :disabled="!filterActive" @click="resetFilters">重置</button>
    </div>

    <!-- 桌面端表格。
         三态（加载 / 失败 / 空）此前一个都没有：表格 tbody 为空时页面
         只是"没有内容"，看的人分不清是"今天真没人巡查"还是"接口挂了"——
         而这两件事一个可以等、一个必须立刻去查。
         移动端卡片列表也用同一组状态（见下方 .mobile-cards）。 -->
    <div v-if="recLoading" class="list-state">加载中…</div>
    <div v-else-if="recError" class="load-error">{{ recError }}</div>
    <div v-else-if="!records.length" class="list-state">
      当前条件下没有巡查记录
    </div>
    <div v-else class="desktop-table">
      <div class="table-wrapper">
        <table class="tbl">
          <thead>
            <tr>
              <th>房间号</th>
              <th>老人姓名</th>
              <th>巡查时间</th>
              <th>巡查护士</th>
              <th>备注</th>
              <th>定位</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in records" :key="record.id">
              <td>{{ record.roomNo }}</td>
              <td>{{ record.elderName || '-' }}</td>
              <td>{{ formatTime(record.patrolTime) }}</td>
              <td>{{ record.nurseName }}</td>
              <td>{{ record.notes || '-' }}</td>
              <td>
                <span v-if="record.latitude" class="location-badge">
                  📍 已定位
                </span>
                <span v-else class="location-badge empty">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 分页放在 .desktop-table 之外：窄屏下表格是 display:none，
         分页留在里面手机上就翻不了页。 -->
    <Pagination
      v-model:page="recPage" v-model:pageSize="recPageSize"
      :total="recTotal" @change="loadRecords"
    />

    <!-- 移动端卡片（三态由上面统一处理，这里只在有数据时渲染） -->
    <div v-if="!recLoading && !recError && records.length" class="mobile-cards">
      <div v-for="record in records" :key="record.id" class="patrol-card">
        <div class="card-header">
          <div class="card-title">
            <span class="room-badge">{{ record.roomNo }}房</span>
            <span class="elder-name">{{ record.elderName || '未关联' }}</span>
          </div>
          <span v-if="record.latitude" class="location-tag">📍</span>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="label">巡查时间</span>
            <span class="value">{{ formatTime(record.patrolTime) }}</span>
          </div>
          <div class="info-row">
            <span class="label">巡查护士</span>
            <span class="value">{{ record.nurseName }}</span>
          </div>
          <div v-if="record.notes" class="info-row">
            <span class="label">备注</span>
            <span class="value notes">{{ record.notes }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 扫码巡查弹窗 -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showScanModal" class="modal-overlay" @click="closeModal">
          <div class="modal-content" @click.stop>
            <div class="modal-header">
              <h2>📱 扫码巡查</h2>
              <button class="close-btn" @click="closeModal">×</button>
            </div>
            <div class="modal-body">
              <p class="hint-text">请扫描床头二维码进行巡查记录</p>
              <input
                v-model="scanForm.qrCode"
                placeholder="输入二维码内容（测试用）"
                class="input-field"
                @keyup.enter="submitPatrol"
              />
              <textarea
                v-model="scanForm.notes"
                placeholder="巡查备注（选填）"
                class="textarea-field"
                rows="3"
              ></textarea>
            </div>
            <div class="modal-footer">
              <button @click="closeModal" class="btn-cancel">取消</button>
              <button @click="submitPatrol" class="btn-confirm">确认巡查</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Toast ref="toastRef" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { usePaging } from '../composables/usePaging.js';
import Pagination from '../components/Pagination.vue';
import { getPatrolList, createPatrol, getPendingRooms, getPatrolStats } from '../api/patrols';
import { getPatrolTasks, generatePatrolTasks, completePatrolTask } from '../api/schedules';
import { getElderList } from '../api/elders';
import Toast from '../components/Toast.vue';
import dayjs from 'dayjs';

const records = ref([]);
// 记录表的三态：加载中 / 失败 / 空。三者互斥，不能只靠"数组为空"来表达。
const recLoading = ref(false);
const recError = ref('');
const recPage = ref(1);
const recPageSize = ref(10);
const recTotal = ref(0);
const pendingRooms = ref([]);
const stats = ref({ todayTotal: 0, completionRate: 0, avgInterval: 0 });
const showScanModal = ref(false);
const tasks = ref([]);
const { page: taskPage, pageSize: taskPageSize, total: taskTotal, paged: taskPaged }
  = usePaging(tasks, 10);
const taskLoading = ref(false);
const taskCounts = computed(() => {
  const c = { pending: 0, done: 0, skipped: 0 };
  for (const t of tasks.value) {
    if (t.status === 0) c.pending++;
    else if (t.status === 1) c.done++;
    else c.skipped++;
  }
  return c;
});

const STATUS_TEXT = { 0: '待执行', 1: '已完成', 2: '已跳过', 3: '超时未巡' };
const statusLabel = (s) => STATUS_TEXT[s] ?? '未知';

// 后端返回的 windowStart/windowEnd 是 ISO 时间串，这里只显示时:分
function fmtWindow(t) {
  const f = (v) => (v ? String(v).replace('T', ' ').slice(11, 16) : '');
  return `${f(t.windowStart)}~${f(t.windowEnd)}`;
}

async function loadTasks() {
  taskLoading.value = true;
  try {
    const res = await getPatrolTasks({});
    if (res.data.success) tasks.value = res.data.data || [];
  } catch { toastRef.value?.show('加载巡查任务失败', 'error'); }
  finally { taskLoading.value = false; }
}

async function doGenerate() {
  taskLoading.value = true;
  try {
    const res = await generatePatrolTasks({});
    toastRef.value?.show(res.data.message || '已生成', 'success');
    await loadTasks();
  } catch (e) {
    toastRef.value?.show(e?.response?.data?.detail || '生成失败', 'error');
  } finally { taskLoading.value = false; }
}

async function doComplete(task, status) {
  try {
    const res = await completePatrolTask(task.id, { status });
    toastRef.value?.show(res.data.message || '已提交', 'success');
    await loadTasks();
    await loadData();          // 回写后刷新记录与统计
  } catch (e) {
    toastRef.value?.show(e?.response?.data?.detail || '提交失败', 'error');
  }
}
const toastRef = ref(null);
const elders = ref([]);
/**
 * 工具栏条件，键名与后端查询参数一一对应。
 * 注意默认值全为空：之前这里的日期默认"今天"，而请求传的参数名（date）后端
 * 根本不认 —— 看着像"默认只看今天"，实际是全量。要"只看今天"就显式选日期，
 * 默认不设条件，"重置"才能回到不带条件的总数。
 */
const filters = ref({ keyword: '', elderId: '', startDate: '', endDate: '' });

const scanForm = ref({
  qrCode: '',
  notes: ''
});

const showToast = (message, type = 'success') => {
  toastRef.value?.show(message, type);
};

/** 去掉空条件，避免把 keyword= 这类空值发到后端 */
const cleanParams = (o) => Object.fromEntries(
  Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined));
/** 「重置」只在任一条件非默认值时可用 */
const filterActive = computed(() =>
  !!(filters.value.keyword || filters.value.elderId
     || filters.value.startDate || filters.value.endDate));

/**
 * 条件变化 → 回到第 1 页再取数。
 * Pagination 只在换每页条数时自动回第 1 页；条件变化不在它的职责里，
 * 不回第 1 页就会停在越界页显示空白。搜索框逐字符触发，加 300ms 防抖。
 */
let filterTimer = null;
function applyFilters(debounced = false) {
  clearTimeout(filterTimer);
  const run = () => { recPage.value = 1; loadRecords(); };
  if (debounced) filterTimer = setTimeout(run, 300); else run();
}
function resetFilters() {
  clearTimeout(filterTimer);
  filters.value = { keyword: '', elderId: '', startDate: '', endDate: '' };
  recPage.value = 1;
  loadRecords();
}

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
    const [pendingRes, elderList] = await Promise.all([
      getPendingRooms(),
      fetchAllElders()
    ]);
    pendingRooms.value = pendingRes.data.data || [];
    elders.value = elderList;
  } catch (error) {
    console.error('加载失败:', error);
    showToast('数据加载失败', 'error');
  }
  await Promise.all([loadRecords(), loadStats()]);
};

const loadRecords = async () => {
  recLoading.value = true;
  try {
    // /patrols/ 是分页接口（142 条），原实现把分页对象当数组用。
    const res = await getPatrolList({
      ...cleanParams(filters.value),
      page: recPage.value, pageSize: recPageSize.value
    });
    const rec = res.data.data || {};
    records.value = Array.isArray(rec) ? rec : (rec.data || []);
    recTotal.value = Array.isArray(rec) ? rec.length : (rec.total || 0);
    recError.value = '';
  } catch (error) {
    console.error('加载巡查记录失败', error);
    // 行内也要说，不能只有 toast：toast 几秒就消失了，
    // 而这张"空表"会一直留在页面上让人以为真的没有记录。
    recError.value = `巡查记录加载失败：${error?.friendlyMessage || '未知错误'}`;
    showToast('数据加载失败', 'error');
  } finally {
    recLoading.value = false;
  }
};

const loadStats = async () => {
  try {
    const statsRes = await getPatrolStats();
    stats.value = statsRes.data.data || { todayTotal: 0, completionRate: 0, avgInterval: 0 };
  } catch (error) {
    console.error('加载统计失败:', error);
  }
};

const submitPatrol = async () => {
  if (!scanForm.value.qrCode) {
    showToast('请输入二维码内容', 'warning');
    return;
  }

  try {
    const patrol = {
      qrCode: scanForm.value.qrCode,
      notes: scanForm.value.notes,
      latitude: 39.9042,
      longitude: 116.4074
    };

    await createPatrol(patrol);
    showToast('巡查记录成功');
    closeModal();
    scanForm.value = { qrCode: '', notes: '' };
    loadData();
  } catch (error) {
    showToast('记录失败: ' + error.message, 'error');
  }
};

const closeModal = () => {
  showScanModal.value = false;
};

const formatTime = (time) => {
  return dayjs(time).format('MM-DD HH:mm');
};

onMounted(() => { loadData(); loadTasks(); });
</script>

<style scoped>


.header-section h1 {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.5px;
  text-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 30%, transparent);
}

.alert-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: color-mix(in srgb, var(--warning) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--warning) 30%, transparent);
  border-radius: 12px;
  margin-bottom: 32px;
  color: var(--warning-text);
  font-size: 14px;
  backdrop-filter: blur(8px);
  animation: fadeIn 0.5s ease 0.1s both;
}

.alert-icon {
  font-size: 20px;
}

.stat-note { margin-top: 4px; font-size: 11px; color: var(--text-muted); line-height: 1.5; text-align: center; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: var(--tint-1);
  backdrop-filter: blur(40px);
  border: 1px solid var(--tint-3);
  padding: 28px 24px;
  border-radius: var(--radius-md);
  text-align: center;
  transition: all 0.3s ease;
  animation: fadeIn 0.5s ease;
}

.stat-card:nth-child(1) { animation-delay: 0.1s; }
.stat-card:nth-child(2) { animation-delay: 0.2s; }
.stat-card:nth-child(3) { animation-delay: 0.3s; }

.stat-card:hover {
  background: var(--tint-2);
  border-color: color-mix(in srgb, var(--primary) 40%, transparent);
  transform: translateY(-4px);
}

.stat-value {
  font-size: 36px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--primary-hover), var(--violet-text));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 8px;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.desktop-table {
  display: block;
  animation: fadeIn 0.5s ease 0.4s both;
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

.location-badge {
  display: inline-block;
  padding: 6px 12px;
  background: color-mix(in srgb, var(--success) 15%, transparent);
  color: var(--success-text);
  border: 1px solid color-mix(in srgb, var(--success) 30%, transparent);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
}

.location-badge.empty {
  background: color-mix(in srgb, var(--neutral) 10%, transparent);
  color: var(--text-tertiary);
  border-color: color-mix(in srgb, var(--neutral) 20%, transparent);
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

.mobile-cards {
  display: none;
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
  max-width: 480px;
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

.hint-text {
  color: var(--text-tertiary);
  font-size: 14px;
  margin-bottom: 20px;
}

.input-field {
  width: 100%;
  padding: 12px 16px;
  background: var(--tint-2);
  border: 1px solid var(--tint-4);
  border-radius: 10px;
  color: var(--text-primary);
  font-size: 14px;
  margin-bottom: 16px;
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
  .patrol-container {
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

  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 24px;
  }

  .stat-card {
    padding: 16px 12px;
  }

  .stat-value {
    font-size: 24px;
  }

  .stat-label {
    font-size: 11px;
  }

  .primary-btn {
    width: 100%;
    padding: 14px;
    font-size: 16px;
  }

  .desktop-table {
    display: none;
  }

  .mobile-cards {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .patrol-card {
    background: var(--tint-1);
    backdrop-filter: blur(40px);
    border: 1px solid var(--tint-3);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.3s ease;
  }

  .patrol-card:active {
    background: var(--tint-2);
    transform: scale(0.98);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--tint-2);
  }

  .card-title {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .room-badge {
    padding: 6px 12px;
    background: color-mix(in srgb, var(--primary) 15%, transparent);
    color: var(--primary-hover);
    border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent);
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
  }

  .elder-name {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .location-tag {
    font-size: 16px;
  }

  .card-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }

  .info-row .label {
    font-size: 13px;
    color: var(--text-tertiary);
    flex-shrink: 0;
    min-width: 70px;
  }

  .info-row .value {
    font-size: 14px;
    color: var(--text-secondary);
    text-align: right;
    font-weight: 500;
  }

  .info-row .value.notes {
    text-align: left;
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

  .input-field,
  .textarea-field {
    font-size: 16px;
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

/* ── 巡查任务 ─────────────────────────────────────────────────────────── */
.task-section { background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md); padding: 16px 18px; margin-bottom: 18px; }
.task-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.task-head h2 { font-size: 16px; font-weight: 700; color: var(--text-primary); margin: 0; }
.task-sub { font-size: 12px; color: var(--text-tertiary); }
.task-actions { display: flex; gap: 8px; }
.ghost-btn { padding: 7px 14px; border-radius: 8px; border: 1px solid var(--border-default);
  background: transparent; color: var(--text-secondary); cursor: pointer; font-size: 13px; }
.task-empty { padding: 22px; text-align: center; color: var(--text-tertiary); font-size: 13px;
  background: var(--tint-1); border-radius: 8px; }
.task-list { max-height: 320px; overflow-y: auto; }
.task-row { display: grid; grid-template-columns: 76px 1fr 100px 76px 150px;
  align-items: center; gap: 10px; padding: 9px 10px; border-radius: 8px; font-size: 13px; }
.task-row:nth-child(odd) { background: var(--tint-1); }
.task-row.done { opacity: .6; }
.task-room { font-weight: 700; color: var(--text-primary); }
.task-elder { color: var(--text-secondary); }
.task-window { font-size: 11px; color: var(--text-muted); }
.task-assignee { color: var(--text-tertiary); }
.task-status { font-size: 11px; padding: 2px 8px; border-radius: 20px; text-align: center; }
/* 文字色一律用 --*-text（它本身随主题切换）。
   原来这里写死的是**亮色**主题的 text 色，暗色下对比度只有 3.3~3.6:1，
   实测不达标 —— 与"硬编码暗色值"是同一个毛病，方向相反。 */
.task-status.st-0 { background: color-mix(in srgb, var(--warning) 14%, transparent); color: var(--warning-text); }
.task-status.st-1 { background: color-mix(in srgb, var(--success) 14%, transparent); color: var(--success-text); }
.task-status.st-2 { background: color-mix(in srgb, var(--neutral) 14%, transparent); color: var(--text-tertiary); }
.task-status.st-3 { background: color-mix(in srgb, var(--danger) 14%, transparent); color: var(--danger-text); }
.task-btns { display: flex; gap: 6px; justify-content: flex-end; }
.mini-btn { padding: 4px 10px; border-radius: 6px; border: 1px solid var(--border-default);
  background: transparent; color: var(--text-secondary); cursor: pointer; font-size: 12px; }
.mini-btn.ok { border-color: color-mix(in srgb, var(--success) 40%, transparent); color: var(--success-text); }
.task-note { font-size: 11px; color: var(--text-muted); }
</style>