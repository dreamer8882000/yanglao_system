<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>💊 用药管理</h1>
        <div class="page-sub">老人用药计划与服药记录</div>
      </div>
    </div>

    <!-- 待服药提醒 -->
    <div v-if="pendingMeds.length > 0" class="pending-section">
      <div class="section-title">
        <span>⏰ 待服药提醒</span>
        <span class="count-badge">{{ pendingMeds.length }}条</span>
      </div>
      <div class="pending-grid">
        <div v-for="med in pendingMeds" :key="med.id" class="pending-card">
          <div class="pending-header">
            <span class="room-badge">{{ med.roomNo }}房</span>
            <span class="elder-name">{{ med.elderName }}</span>
          </div>
          <div class="med-detail">
            <div class="med-name">{{ med.medicationName }}</div>
            <div class="med-info">
              <span>{{ med.dosage }}</span>
              <span class="med-time">{{ formatTime(med.scheduleTime) }}</span>
            </div>
          </div>
          <button @click="confirmMed(med)" class="confirm-btn">
            ✓ 确认服药
          </button>
        </div>
      </div>
    </div>

    <!-- 用药列表：用药清单 / 服药记录
         两个列表各需要一套条件工具栏，若同时铺在页面上就是两排几乎一样的
         卡片底框上下叠着，视觉上互相打架；因此按页签切换，同一时刻只渲染一个
         （用全局 .panel-head + .seg 契约，不另造切换器样式）。 -->
    <div class="panel">
      <div class="panel-head">
        <h2 class="panel-title">📋 用药列表</h2>
        <div class="seg">
          <button class="seg-btn" :class="{ on: medTab === 'plans' }"
            @click="medTab = 'plans'">用药清单</button>
          <button class="seg-btn" :class="{ on: medTab === 'records' }"
            @click="medTab = 'records'">服药记录</button>
        </div>
      </div>

      <!-- ── 用药清单 ─────────────────────────────────────────────── -->
      <template v-if="medTab === 'plans'">
        <div class="toolbar">
          <input v-model="medFilters.keyword" class="toolbar-search"
            placeholder="药品名称 / 剂量 / 频次" @input="applyMedFilters(true)" />
          <select v-model="medFilters.elderId" class="toolbar-field" @change="applyMedFilters()">
            <option value="">全部老人</option>
            <option v-for="elder in elders" :key="elder.id" :value="elder.id">
              {{ elder.name }}（{{ elder.roomNo }}房）
            </option>
          </select>
          <select v-model="medFilters.status" class="toolbar-field" @change="applyMedFilters()">
            <option value="">全部状态</option>
            <option value="1">使用中</option>
            <option value="0">已停药</option>
          </select>
          <span class="toolbar-label">录入</span>
          <input v-model="medFilters.startDate" type="date" class="toolbar-field"
            @change="applyMedFilters()" />
          <span class="toolbar-label">至</span>
          <input v-model="medFilters.endDate" type="date" class="toolbar-field"
            @change="applyMedFilters()" />
          <button class="toolbar-reset" :disabled="!medFilterActive" @click="resetMedFilters">重置</button>
          <div class="toolbar-actions">
            <button class="btn-add" @click="showAddModal = true">+ 添加用药</button>
          </div>
        </div>

        <!-- 桌面端表格 -->
        <div class="table-card desktop-table">
          <table v-if="!loading && medications.length" class="tbl">
            <thead>
              <tr>
                <th>老人姓名</th>
                <th>房间号</th>
                <th>药品名称</th>
                <th>剂量</th>
                <th>频次</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="med in medications" :key="med.id">
                <td>{{ med.elderName }}</td>
                <td><span class="room-badge">{{ med.roomNo }}房</span></td>
                <td>{{ med.medicationName }}</td>
                <td>{{ med.dosage }}</td>
                <td>{{ med.frequency }}</td>
                <td>
                  <span class="status-chip" :class="med.status === 1 ? 'active' : 'inactive'">
                    {{ med.status === 1 ? '使用中' : '已停药' }}
                  </span>
                </td>
                <td>
                  <div class="row-actions">
                    <button @click="editMed(med)" class="btn-sm-action">编辑</button>
                    <button @click="deleteMed(med.id)" class="btn-sm-action danger">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="loading" class="table-state">加载中...</div>
          <div v-else class="table-state">
            <div style="font-size:40px;opacity:.3">💊</div>
            <div>暂无用药记录</div>
          </div>
        </div>

        <!-- 分页放在 .desktop-table 之外：
             1) 表格里的 v-if/v-else 链要求 v-else 紧跟 v-if，分页插在中间会让整条链失效；
             2) .desktop-table 在窄屏是 display:none —— 分页留在里面，手机上就没法翻页了。 -->
        <Pagination
          v-model:page="medPage" v-model:pageSize="medPageSize"
          :total="medTotal" @change="loadMedications"
        />

        <!-- 移动端卡片 -->
        <div class="mobile-list">
          <div v-if="loading" class="table-state">加载中...</div>
          <div v-else-if="!medications.length" class="table-state">
            <div style="font-size:40px;opacity:.3">💊</div>
            <div>暂无用药记录</div>
          </div>
          <div v-else>
            <div v-for="med in medications" :key="'m'+med.id" class="med-card">
              <div class="mc-header">
                <span class="room-badge">{{ med.roomNo }}房</span>
                <span class="mc-elder">{{ med.elderName }}</span>
                <span class="status-chip ml-auto" :class="med.status === 1 ? 'active' : 'inactive'">
                  {{ med.status === 1 ? '使用中' : '已停药' }}
                </span>
              </div>
              <div class="mc-body">
                <div class="mc-row"><span class="mc-label">药品</span><span>{{ med.medicationName }}</span></div>
                <div class="mc-row"><span class="mc-label">剂量</span><span>{{ med.dosage }}</span></div>
                <div class="mc-row"><span class="mc-label">频次</span><span>{{ med.frequency }}</span></div>
              </div>
              <div class="mc-actions">
                <button @click="editMed(med)" class="btn-sm-action">编辑</button>
                <button @click="deleteMed(med.id)" class="btn-sm-action danger">删除</button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ── 服药记录 ─────────────────────────────────────────────── -->
      <template v-else>
        <div class="toolbar">
          <input v-model="recFilters.keyword" class="toolbar-search"
            placeholder="老人姓名 / 备注" @input="applyRecFilters(true)" />
          <select v-model="recFilters.elderId" class="toolbar-field" @change="applyRecFilters()">
            <option value="">全部老人</option>
            <option v-for="elder in elders" :key="elder.id" :value="elder.id">
              {{ elder.name }}（{{ elder.roomNo }}房）
            </option>
          </select>
          <select v-model="recFilters.status" class="toolbar-field" @change="applyRecFilters()">
            <option value="">全部状态</option>
            <option value="0">待服药</option>
            <option value="1">已服药</option>
            <option value="2">已跳过</option>
          </select>
          <span class="toolbar-label">计划</span>
          <input v-model="recFilters.startDate" type="date" class="toolbar-field"
            @change="applyRecFilters()" />
          <span class="toolbar-label">至</span>
          <input v-model="recFilters.endDate" type="date" class="toolbar-field"
            @change="applyRecFilters()" />
          <button class="toolbar-reset" :disabled="!recFilterActive" @click="resetRecFilters">重置</button>
        </div>

        <div class="table-card">
          <table v-if="!recLoading && records.length" class="tbl">
            <thead>
              <tr>
                <th>老人姓名</th>
                <th>房间号</th>
                <th>药品名称</th>
                <th>计划服药时间</th>
                <th>实际服药时间</th>
                <th>状态</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in records" :key="rec.id">
                <td>{{ elderMap[rec.elderId]?.name || '-' }}</td>
                <td>
                  <span v-if="elderMap[rec.elderId]" class="room-badge">
                    {{ elderMap[rec.elderId].roomNo }}房
                  </span>
                  <span v-else>-</span>
                </td>
                <td>{{ medNameMap[rec.medicationId] || '-' }}</td>
                <td>{{ formatDateTime(rec.scheduledTime) }}</td>
                <td>{{ rec.actualTime ? formatDateTime(rec.actualTime) : '-' }}</td>
                <td>
                  <span class="status-chip" :class="rec.status === 1 ? 'active' : 'inactive'">
                    {{ REC_STATUS[rec.status] || '未知' }}
                  </span>
                </td>
                <td>{{ rec.notes || '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else-if="recLoading" class="table-state">加载中...</div>
          <div v-else class="table-state">
            <div style="font-size:40px;opacity:.3">🕒</div>
            <div>没有符合条件的服药记录</div>
          </div>
          <Pagination
            v-model:page="recPage" v-model:pageSize="recPageSize"
            :total="recTotal" @change="loadRecords"
          />
        </div>
      </template>
    </div>

    <!-- 添加/编辑用药弹窗 -->
    <div v-if="showAddModal" class="modal-mask" @click.self="closeModal">
      <div class="modal-box">
        <div class="modal-header">
          <h3>{{ editingMed ? '编辑用药' : '添加用药' }}</h3>
          <button class="close-btn" @click="closeModal">×</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="submitMed">
            <div class="form-group">
              <label>选择老人<span class="req">*</span></label>
              <select v-model="medForm.elderId" required class="field-input">
                <option value="">请选择</option>
                <option v-for="elder in elders" :key="elder.id" :value="elder.id">
                  {{ elder.name }} ({{ elder.roomNo }}房)
                </option>
              </select>
            </div>
            
            <div class="form-group">
              <label>药品名称<span class="req">*</span></label>
              <input
                v-model="medForm.medicationName"
                placeholder="如：阿司匹林"
                required
                class="field-input"
              />
            </div>

            <div class="form-group">
              <label>剂量<span class="req">*</span></label>
              <input
                v-model="medForm.dosage"
                placeholder="如：2片"
                required
                class="field-input"
              />
            </div>

            <div class="form-group">
              <label>频次<span class="req">*</span></label>
              <input
                v-model="medForm.frequency"
                placeholder="如：每日3次"
                required
                class="field-input"
              />
              <div class="field-hint">多个时间用英文逗号分隔</div>
            </div>

            <div class="form-group">
              <label>服药时间点<span class="req">*</span></label>
              <input
                v-model="medForm.timeSlots"
                placeholder="如：08:00,14:00,20:00"
                required
                class="field-input"
              />
              <div class="field-hint">多个时间用英文逗号分隔</div>
            </div>

            <div class="form-group">
              <label>备注</label>
              <textarea
                v-model="medForm.notes"
                placeholder="饭前服用、注意事项等"
                class="field-textarea"
                rows="3"
              ></textarea>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button type="button" @click="closeModal" class="btn-cancel">取消</button>
          <button @click="submitMed" class="btn-primary" :disabled="submitting">
            {{ submitting ? '提交中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 确认服药弹窗 -->
    <div v-if="confirmingMed" class="modal-mask" @click.self="confirmingMed = null">
      <div class="modal-box small">
        <div class="modal-header">
          <h3>确认服药</h3>
          <button class="close-btn" @click="confirmingMed = null">×</button>
        </div>
        <div class="modal-body">
          <div class="info-box">
            <div class="info-row"><span>老人</span><span>{{ confirmingMed.elderName }}</span></div>
            <div class="info-row"><span>药品</span><span>{{ confirmingMed.medicationName }}</span></div>
            <div class="info-row"><span>剂量</span><span>{{ confirmingMed.dosage }}</span></div>
          </div>
          <textarea
            v-model="confirmNotes"
            placeholder="服药备注（选填）"
            class="field-textarea"
            rows="3"
          ></textarea>
        </div>
        <div class="modal-footer">
          <button @click="confirmingMed = null" class="btn-cancel">取消</button>
          <button @click="submitConfirm" class="btn-primary" :disabled="confirming">
            {{ confirming ? '提交中...' : '确认' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import Pagination from '../components/Pagination.vue';
import {
  getMedicationList,
  getMedicationRecords,
  createMedication,
  updateMedication,
  deleteMedication,
  getPendingMedications,
  confirmMedication
} from '../api/medications';
import { getElderList } from '../api/elders';
import { showToast } from '../utils/index.js';
import dayjs from 'dayjs';

/** 服药记录状态：与后端 medication_records.status 一致（0 待服 / 1 已服 / 2 跳过） */
const REC_STATUS = { 0: '待服药', 1: '已服药', 2: '已跳过' };

/** 去掉空条件：不把 keyword= / elderId= 这类空值发到后端，URL 干净且语义明确 */
const cleanParams = (o) => Object.fromEntries(
  Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined));
const hasCondition = (o) => Object.values(o).some(
  (v) => v !== '' && v !== null && v !== undefined);

const medications = ref([]);
const medPage = ref(1);
const medPageSize = ref(10);
const medTotal = ref(0);
const pendingMeds = ref([]);
const elders = ref([]);
const showAddModal = ref(false);
const editingMed = ref(null);
const confirmingMed = ref(null);
const confirmNotes = ref('');
const loading = ref(false);
const submitting = ref(false);
const confirming = ref(false);

/** 当前展示的是哪个列表（同一时刻只渲染一个工具栏） */
const medTab = ref('plans');

/** 服药记录列表（服务端分页） */
const records = ref([]);
const recPage = ref(1);
const recPageSize = ref(10);
const recTotal = ref(0);
const recLoading = ref(false);
/** 记录表只带 elderId / medicationId，需要本地映射成姓名 */
const medNameMap = ref({});
const elderMap = computed(() => {
  const m = {};
  for (const e of elders.value) m[e.id] = e;
  return m;
});

/**
 * 工具栏条件。键名与后端查询参数一一对应（keyword / elderId / status /
 * startDate / endDate），不额外造中间层——中间层是上一版"筛选栏点了没反应"
 * 的成因之一（下拉里存的是本地状态，请求里传的却是另一套字段）。
 */
const medFilters = ref({ keyword: '', elderId: '', status: '', startDate: '', endDate: '' });
const recFilters = ref({ keyword: '', elderId: '', status: '', startDate: '', endDate: '' });
const medFilterActive = computed(() => hasCondition(medFilters.value));
const recFilterActive = computed(() => hasCondition(recFilters.value));

const medForm = ref({
  elderId: '',
  medicationName: '',
  dosage: '',
  frequency: '',
  timeSlots: '',
  durationDays: '',
  notes: ''
});


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
    const [elderList, pendingRes, allMedsRes] = await Promise.all([
      fetchAllElders(),
      getPendingMedications(),
      // 记录表只有 medicationId，取全量用药清单建一张 id→药名 的映射表
      getMedicationList({ page: 1, pageSize: 100 })
    ]);
    elders.value = elderList;
    pendingMeds.value = pendingRes.data.data || [];
    const map = {};
    for (const m of (allMedsRes.data.data?.data || [])) map[m.id] = m.medicationName;
    medNameMap.value = map;
    await Promise.all([loadMedications(), loadRecords()]);
  } catch {
    showToast('加载失败', 'error');
  }
};

const loadMedications = async () => {
  loading.value = true;
  try {
    // /medications/ 走的是分页接口，返回 { data:[...], total, page, pageSize }。
    // 原实现直接把 res.data.data（对象）赋给列表变量，列表内容因此是错的，
    // 而且永远只能看到第一页。这里取内层数组并接上分页状态。
    const res = await getMedicationList({
      ...cleanParams(medFilters.value),
      page: medPage.value, pageSize: medPageSize.value,
    });
    const d = res.data.data || {};
    medications.value = d.data || [];
    medTotal.value = d.total || 0;
  } catch {
    showToast('加载失败', 'error');
  } finally {
    loading.value = false;
  }
};

const loadRecords = async () => {
  recLoading.value = true;
  try {
    const res = await getMedicationRecords({
      ...cleanParams(recFilters.value),
      page: recPage.value, pageSize: recPageSize.value,
    });
    const d = res.data.data || {};
    records.value = d.data || [];
    recTotal.value = d.total || 0;
  } catch {
    showToast('加载失败', 'error');
  } finally {
    recLoading.value = false;
  }
};

/**
 * 条件变化 → 回到第 1 页再取数。
 *
 * 为什么必须显式回第 1 页：Pagination 组件只在"换每页条数"时自动回第 1 页，
 * 条件变化不在它的职责范围内。而第 3 页 + 新增筛选条件后结果可能只剩 1 页，
 * 不回第 1 页就会停在越界页，列表一片空白。
 *
 * 搜索框逐字符触发，加 300ms 防抖；下拉/日期是离散选择，立即生效。
 */
let medTimer = null;
let recTimer = null;
function applyMedFilters(debounced = false) {
  clearTimeout(medTimer);
  const run = () => { medPage.value = 1; loadMedications(); };
  if (debounced) medTimer = setTimeout(run, 300); else run();
}
function applyRecFilters(debounced = false) {
  clearTimeout(recTimer);
  const run = () => { recPage.value = 1; loadRecords(); };
  if (debounced) recTimer = setTimeout(run, 300); else run();
}
function resetMedFilters() {
  clearTimeout(medTimer);
  medFilters.value = { keyword: '', elderId: '', status: '', startDate: '', endDate: '' };
  medPage.value = 1;
  loadMedications();
}
function resetRecFilters() {
  clearTimeout(recTimer);
  recFilters.value = { keyword: '', elderId: '', status: '', startDate: '', endDate: '' };
  recPage.value = 1;
  loadRecords();
}

const submitMed = async () => {
  // 必须在**这里**校验，不能指望 required 属性。
  // <form> 在 .modal-body 里就闭合了，提交按钮在它外面的 .modal-footer，
  // 而且用的是 @click 不是 type="submit" —— 原生约束校验根本没有机会触发。
  // 结果是空表单能一路发到后端，被 422 拒掉后只弹一句"操作失败"，
  // 用户不知道到底哪一项不对。
  const missing = [
    ['elderId', '选择老人'], ['medicationName', '药品名称'], ['dosage', '剂量'],
    ['frequency', '频次'], ['timeSlots', '服药时间点'],
  ].filter(([k]) => !String(medForm.value[k] ?? '').trim()).map(([, label]) => label);
  if (missing.length) {
    showToast(`请填写：${missing.join('、')}`, 'warning');
    return;
  }
  if (submitting.value) return;   // 防重复提交
  submitting.value = true;
  try {
    const payload = {
      ...medForm.value,
      timeSlots: medForm.value.timeSlots.split(',').map(t => t.trim()).filter(Boolean)
    };
    
    if (editingMed.value) {
      await updateMedication(editingMed.value.id, payload);
      showToast('更新成功', 'success');
    } else {
      await createMedication(payload);
      showToast('添加成功', 'success');
    }
    closeModal();
    loadData();
  } catch (e) {
    showToast(`操作失败：${e?.friendlyMessage || '未知错误'}`, 'error');
  } finally {
    submitting.value = false;
  }
};

const editMed = (med) => {
  editingMed.value = med;
  medForm.value = {
    ...med,
    timeSlots: Array.isArray(med.timeSlots) 
      ? med.timeSlots.join(',') 
      : (med.timeSlots || '')
  };
  showAddModal.value = true;
};

const deleteMed = async (id) => {
  if (!window.confirm('确认删除该用药记录？')) return;
  try {
    await deleteMedication(id);
    showToast('删除成功', 'success');
    loadData();
  } catch {
    showToast('删除失败', 'error');
  }
};

const confirmMed = (med) => {
  confirmingMed.value = med;
  confirmNotes.value = '';
};

const submitConfirm = async () => {
  confirming.value = true;
  try {
    await confirmMedication(confirmingMed.value.recordId, {
      notes: confirmNotes.value
    });
    showToast('确认成功', 'success');
    confirmingMed.value = null;
    loadData();
  } catch {
    showToast('确认失败', 'error');
  } finally {
    confirming.value = false;
  }
};

const closeModal = () => {
  showAddModal.value = false;
  editingMed.value = null;
  medForm.value = {
    elderId: '',
    medicationName: '',
    frequency: '',
    timeSlots: '',
    durationDays: '',
    scheduleTime: '',
    notes: ''
  };
};
const formatTime = (time) => (time ? dayjs(time).format('HH:mm') : '');

/** 服药记录要看到日期，只给 HH:mm 会分不清是哪天 */
const formatDateTime = (time) => (time ? dayjs(time).format('MM-DD HH:mm') : '-');

onMounted(loadData);
</script>

<style scoped>
.page { padding: 24px; min-height: calc(100vh - var(--header-h)); background: var(--bg-app); }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; gap: 12px; }
h1 { font-size: 22px; font-weight: 800; color: var(--text-primary); letter-spacing: -.3px; }
.page-sub { font-size: 12px; color: var(--text-muted); margin-top: 3px; }
.btn-add { padding: 8px 18px; border-radius: 9px; border: none; background: linear-gradient(135deg, var(--primary), var(--primary-active)); color: var(--text-on-color); cursor: pointer; font-size: 13px; font-weight: 600; white-space: nowrap; flex-shrink: 0; transition: all .2s; box-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 30%, transparent); }
.btn-add:hover { box-shadow: 0 4px 16px color-mix(in srgb, var(--primary) 40%, transparent); transform: translateY(-1px); }

.pending-section { margin-bottom: 24px; background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 14px; padding: 18px; }
.section-title { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 700; color: var(--text-secondary); margin-bottom: 16px; }
.count-badge { padding: 2px 8px; border-radius: 20px; font-size: 11px; background: color-mix(in srgb, var(--warning) 12%, transparent); color: var(--warning-text); }

.pending-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.pending-card { background: color-mix(in srgb, var(--warning) 8%, transparent); border: 1px solid color-mix(in srgb, var(--warning) 25%, transparent); border-left: 3px solid var(--warning-text); padding: 14px; border-radius: 12px; transition: border-color .2s; }
.pending-card:hover { border-left-color: var(--warning); }
.pending-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid color-mix(in srgb, var(--warning) 15%, transparent); }
.elder-name { font-size: 14px; font-weight: 600; color: var(--warning-text); }
.room-badge { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; background: color-mix(in srgb, var(--violet) 12%, transparent); color: var(--violet-text); border: 1px solid color-mix(in srgb, var(--violet) 20%, transparent); }
.med-detail { margin-bottom: 12px; }
.med-name { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
.med-info { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-tertiary); }
.med-time { color: var(--warning-text); font-weight: 500; }
.confirm-btn { width: 100%; padding: 8px; border-radius: 8px; border: none; background: linear-gradient(135deg, var(--success), var(--success-text)); color: var(--text-on-color); cursor: pointer; font-size: 13px; font-weight: 600; transition: all .2s; }
.confirm-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px color-mix(in srgb, var(--success) 30%, transparent); }

/* 工具栏右侧主操作：与条件控件同高（契约里 .toolbar-search/.toolbar-field 统一 34px），
   否则一行里会出现"输入框 34、按钮 32"的高低差。 */
.toolbar-actions .btn-add { height: 34px; padding: 0 16px; }

/* 背景/边框/圆角由全局 .panel 系列提供（含 .table-card），此处只补横向滚动 */
.table-card { overflow-x: auto; }
/* 表格样式交给 .tbl 契约；本页只声明最小宽度（列多，靠外层容器横向滚动） */
.table-wrapper table { min-width: 800px; }
thead tr { border-bottom: 1px solid var(--tint-3); background: linear-gradient(to bottom, var(--tint-1), var(--tint-1)); }
/* 对齐/内边距/边框交给 .tbl 契约，这里只管本页特有的字号与字距 */
.tbl th { font-size: 11px; font-weight: 700; letter-spacing: .4px; text-transform: uppercase; }
.tbl td { font-size: 13px; }
tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: var(--tint-1); }
.status-chip { display: inline-flex; padding: 3px 9px; border-radius: 5px; font-size: 11px; font-weight: 600; }
.status-chip.active { background: color-mix(in srgb, var(--success) 12%, transparent); color: var(--success); }
.status-chip.inactive { background: color-mix(in srgb, var(--neutral) 10%, transparent); color: var(--text-tertiary); }
.btn-sm-action { padding: 4px 10px; border-radius: 6px; border: 1px solid color-mix(in srgb, var(--neutral) 25%, transparent); background: color-mix(in srgb, var(--neutral) 6%, transparent); color: var(--text-tertiary); cursor: pointer; font-size: 11px; white-space: nowrap; min-height: 30px; transition: all .15s; font-weight: 500; }
.btn-sm-action:hover { border-color: color-mix(in srgb, var(--neutral) 40%, transparent); color: var(--text-tertiary); background: color-mix(in srgb, var(--neutral) 10%, transparent); }
.btn-sm-action.danger { border-color: color-mix(in srgb, var(--danger) 25%, transparent); background: color-mix(in srgb, var(--danger) 7%, transparent); color: var(--danger-text); }
.btn-sm-action.danger:hover { background: color-mix(in srgb, var(--danger) 12%, transparent); }
.table-state { padding: 60px; text-align: center; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 10px; }
.mobile-list { display: none; }
.ml-auto { margin-left: auto; }

.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 16px; width: 560px; max-width: 95vw; max-height: 90vh; overflow-y: auto; box-shadow: 0 24px 64px color-mix(in srgb, var(--shadow-color) 60%, transparent); }
.modal-box.small { width: 420px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--tint-3); }
.modal-header h3 { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: var(--tint-2); border: 1px solid var(--tint-3); border-radius: 7px; color: var(--text-tertiary); font-size: 16px; cursor: pointer; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; transition: all .15s; }
.close-btn:hover { background: var(--tint-4); color: var(--text-tertiary); }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 11px; font-weight: 700; color: var(--text-tertiary); letter-spacing: .3px; text-transform: uppercase; }
.req { color: var(--danger); margin-left: 2px; }
.field-input, .field-textarea { background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: 8px; padding: 10px 14px; color: var(--text-secondary); font-size: 13px; outline: none; font-family: inherit; transition: border-color .2s; width: 100%; }
.field-input:focus, .field-textarea:focus { border-color: color-mix(in srgb, var(--primary) 40%, transparent); }
.field-textarea { resize: vertical; min-height: 80px; }
.field-hint { font-size: 11px; color: var(--text-muted); margin-top: -4px; }
.info-box { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 9px; }
.info-row { display: flex; gap: 12px; font-size: 12px; color: var(--text-tertiary); }
.info-row span:first-child { color: var(--text-muted); width: 52px; flex-shrink: 0; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--tint-3); }
.btn-cancel { padding: 8px 18px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 13px; transition: all .15s; }
.btn-cancel:hover { background: var(--tint-2); }
.btn-primary { padding: 8px 20px; border-radius: 8px; border: none; background: linear-gradient(135deg, var(--primary), var(--primary-active)); color: var(--text-on-color); cursor: pointer; font-weight: 600; font-size: 13px; transition: all .15s; box-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 30%, transparent); }
.btn-primary:hover:not(:disabled) { box-shadow: 0 4px 16px color-mix(in srgb, var(--primary) 40%, transparent); transform: translateY(-1px); }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }

@media (max-width: 768px) {
  .page { padding: 14px; }
  h1 { font-size: 19px; }
  .page-header { flex-wrap: wrap; gap: 8px; }
  .pending-grid { grid-template-columns: 1fr; }
  .desktop-table { display: none; }
  .mobile-list { display: block; }
  .med-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 12px; padding: 14px; margin-bottom: 10px; }
  .mc-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid var(--tint-2); }
  .mc-elder { font-size: 14px; font-weight: 600; color: var(--text-secondary); }
  .mc-body { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
  .mc-row { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-tertiary); }
  .mc-label { color: var(--text-muted); }
  .mc-actions { display: flex; gap: 8px; }
  .btn-sm-action { flex: 1; min-height: 44px; font-size: 13px; }
  .table-state { padding: 40px 16px; }
  .modal-mask { align-items: flex-end; }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; }
  .field-input, .field-textarea { font-size: 16px; padding: 12px; }
  .modal-footer { flex-direction: column; gap: 8px; padding: 12px 16px 20px; }
  .btn-cancel, .btn-primary { width: 100%; min-height: 48px; font-size: 15px; border-radius: 12px; justify-content: center; display: flex; align-items: center; }
}
</style>
