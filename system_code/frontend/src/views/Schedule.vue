<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>值班排班</h1>
        <div class="page-sub">管理护理人员排班计划</div>
      </div>
    </div>

    <!-- 工具栏（全局契约 .toolbar）：周切换是本页的主控件，放最左；
         人员与班次筛选跟在后面；作用于列表的操作靠右。
         与原实现的区别：这些控件原先散在页头里，而全站其它列表页都已统一到
         工具栏 —— 这一页是唯一没跟上的。 -->
    <div class="toolbar">
      <button class="toolbar-field" @click="changeWeek(-1)">‹ 上周</button>
      <button class="toolbar-field week-now" :class="{ on: weekOffset === 0 }" @click="goCurrentWeek">
        本周
      </button>
      <button class="toolbar-field" @click="changeWeek(1)">下周 ›</button>
      <span class="toolbar-label week-label">{{ weekLabel }}</span>

      <select v-model="filterUser" class="toolbar-field">
        <option value="">全部人员</option>
        <!-- 键名两种都要认：/duty/overview 的 nurses 用 `id`，
             而按本周排班兜底生成时用的是 `userId`。
             只写 n.userId 会让 value 变成字符串 "undefined" —— 下拉看着正常，
             选中后过滤条件变成一个永远匹配不上的值，结果是"筛出来一个人都没有"。 -->
        <option v-for="n in nurseOptions" :key="optionId(n)" :value="String(optionId(n))">
          {{ n.name || ('用户#' + optionId(n)) }}
        </option>
      </select>
      <select v-model="filterShift" class="toolbar-field">
        <option value="">全部班次</option>
        <option v-for="t in shiftTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
      </select>
      <button class="toolbar-reset" :disabled="!hasFilter" @click="resetFilters">重置</button>
      <div class="toolbar-actions">
        <button v-if="isAdmin" class="btn-add" @click="openAdd">+ 新增排班</button>
      </div>
    </div>

    <!-- 当前值班面板 -->
    <div class="on-duty-bar" v-if="onDuty.length || todaySchedules.length">
      <span class="duty-label">🟢 当前值班</span>
      <div class="duty-chips">
        <span v-for="s in onDuty" :key="s.id" class="duty-chip">
          {{ s.userName }} <span class="duty-shift">{{ shiftLabel(s.shiftType) }}</span>
        </span>
        <span v-if="!onDuty.length" class="no-duty">暂无人员值班</span>
      </div>
    </div>

    <!-- 桌面端周视图 -->
    <div class="panel desk-panel">
      <div class="panel-head">
        <h2>本周排班表</h2>
        <span class="panel-sub">{{ groupedSchedules.length }} 人 · {{ allSchedules.length }} 个班次</span>
      </div>
      <div v-if="loading" class="panel-empty">加载中…</div>
      <div v-else-if="!filteredSchedules.length" class="panel-empty">本周暂无排班记录</div>
      <div class="week-grid desktop-grid" v-else>
      <div class="week-header">
        <div class="week-th time-col">姓名</div>
        <div v-for="day in weekDays" :key="day.date" class="week-th" :class="{ today: day.isToday }">
          <div class="day-name">{{ day.label }}</div>
          <div class="day-date">{{ day.dateShort }}</div>
        </div>
      </div>
      <div v-if="!groupedSchedules.length" class="empty-week">本周暂无排班记录</div>
      <div v-for="person in groupedSchedules" :key="person.userId" class="week-row">
        <div class="week-td time-col person-col">
          <div class="person-avatar">{{ person.name?.charAt(0) || '?' }}</div>
          <span class="person-name">{{ person.name }}</span>
        </div>
        <div v-for="day in weekDays" :key="day.date" class="week-td"
          :class="{ today: day.isToday,
                    'drop-ok': isAdmin && dropTarget && dropTarget.userId === person.userId && dropTarget.date === day.date,
                    'is-dragging': dragging && dragging.userId === person.userId && dragging.date === day.date }"
          @dragover.prevent="isAdmin && onDragOver(person, day)"
          @dragleave="onDragLeave(person, day)"
          @drop.prevent="isAdmin && onDrop(person, day)">
          <div v-for="s in getSchedulesForDay(person.schedules, day.date)" :key="s.id"
            class="schedule-chip" :class="'type-' + s.shiftType"
            :draggable="isAdmin"
            @dragstart="onDragStart(s, person, day)"
            @dragend="onDragEnd"
            :title="isAdmin ? '拖动可调整日期与人员' : ''">
            <span class="chip-time">{{ s.startTime?.slice(0,5) }}~{{ s.endTime?.slice(0,5) }}</span>
            <span class="chip-label">{{ shiftLabel(s.shiftType) }}</span>
            <button v-if="isAdmin" class="chip-del" @click.stop="deleteSchedule(s)" title="删除">×</button>
          </div>
          <!-- 空单元格：拖拽时提示可放置 -->
          <div v-if="isAdmin && !getSchedulesForDay(person.schedules, day.date).length
                     && dropTarget && dropTarget.userId === person.userId && dropTarget.date === day.date"
               class="drop-hint">放到这里</div>
        </div>
      </div>
      </div>
    </div>

    <!-- 移动端列表 -->
    <div class="mobile-list" v-if="!loading">
      <div v-if="!allSchedules.length" class="empty-week">本周暂无排班记录</div>
      <div v-for="s in allSchedules" :key="s.id" class="schedule-card" :class="'type-' + s.shiftType">
        <div class="sc-top">
          <div class="sc-avatar">{{ s.userName?.charAt(0) || '?' }}</div>
          <div class="sc-info">
            <div class="sc-name">{{ s.userName }}</div>
            <div class="sc-date">{{ s.shiftDate }} · {{ shiftLabel(s.shiftType) }}</div>
          </div>
          <span class="sc-time">{{ s.startTime?.slice(0,5) }}~{{ s.endTime?.slice(0,5) }}</span>
        </div>
        <div class="sc-foot" v-if="isAdmin || s.note">
          <span class="sc-note" v-if="s.note">{{ s.note }}</span>
          <button v-if="isAdmin" class="btn-del-sm" @click="deleteSchedule(s)">删除</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>

    <!-- 新增弹框 -->
    <div v-if="modal.show" class="modal-mask" @click.self="modal.show = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>新增排班</h3>
          <button class="close-btn" @click="modal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="field-group">
            <label>护理人员 <span class="req">*</span></label>
            <select v-model="form.userId">
              <option value="">请选择</option>
              <option v-for="u in userList" :key="u.id" :value="u.id">{{ u.name || u.username }}</option>
            </select>
          </div>
          <div class="field-group">
            <label>日期 <span class="req">*</span></label>
            <input type="date" v-model="form.shiftDate" />
            <span v-if="hasConflict" class="warning-text">⚠️ 该时间段已有排班，可能存在冲突</span>
          </div>
          <div class="field-group">
            <label>班次类型</label>
            <div class="shift-types">
              <button v-for="t in shiftTypes" :key="t.value"
                class="shift-btn" :class="{ active: form.shiftType === t.value }"
                type="button" @click="selectShiftType(t.value)">
                {{ t.icon }} {{ t.label }}
              </button>
            </div>
          </div>
          <div class="field-row">
            <div class="field-group">
              <label>开始时间</label>
              <input type="time" v-model="form.startTime" />
            </div>
            <div class="field-group">
              <label>结束时间</label>
              <input type="time" v-model="form.endTime" />
            </div>
          </div>
          <div class="field-group">
            <label>备注</label>
            <input v-model="form.note" placeholder="可选" maxlength="100" />
          </div>
          <div v-if="modal.error" class="form-error">{{ modal.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="modal.show = false">取消</button>
          <button class="btn-primary" @click="submitAdd" :disabled="modal.loading">
            {{ modal.loading ? '提交中...' : '创建排班' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { getDutyOverview, getOnDuty, createSchedule, deleteSchedule as deleteApi,
         moveSchedule } from '../api/schedules.js';
import { getUserList } from '../api/users.js';
import { useKeyboard } from '../composables/useKeyboard.js';
import { showToast } from '../utils/index.js';

const loading = ref(false);

// ── 拖拽调班 ───────────────────────────────────────────────────────────────
// 为什么用 HTML5 原生拖拽而不是引第三方库：这里只有"把一个人某天的班拖到
// 另一天/另一个人"这一种交互，原生 dragstart/dragover/drop 足够，且不增加
// 依赖。冲突判定不放在前端"猜"，而是**由后端裁决** —— 前端只负责把目标
// (日期, 人员) 提交上去，后端返回 409 时把原因原样展示给用户，避免前后端
// 两套规则不一致。
const workload = ref({});       // 本周每人已排班次，用于均衡提示
const patrolTasks = ref([]);    // 本周巡查任务
const dragging = ref(null);     // { id, userId, date, shiftType }
const dropTarget = ref(null);   // { userId, date }
const moving = ref(false);

function onDragStart(schedule, person, day) {
  dragging.value = { id: schedule.id, userId: person.userId, date: day.date,
                     shiftType: schedule.shiftType };
  dropTarget.value = null;
}

function onDragEnd() {
  dragging.value = null;
  dropTarget.value = null;
}

function onDragOver(person, day) {
  if (!dragging.value) return;
  dropTarget.value = { userId: person.userId, date: day.date };
}

function onDragLeave(person, day) {
  const t = dropTarget.value;
  if (t && t.userId === person.userId && t.date === day.date) dropTarget.value = null;
}

async function onDrop(person, day) {
  const src = dragging.value;
  dropTarget.value = null;
  if (!src || moving.value) return;
  // 原地放下：什么都不做
  if (src.userId === person.userId && src.date === day.date) { dragging.value = null; return; }

  moving.value = true;
  try {
    await moveSchedule(src.id, { userId: person.userId, shiftDate: day.date });
    showToast('已调整排班', 'success');
    // 重新拉取而不是本地改数组：调班可能把班次挪到别的周，本地改会与服务端
    // 不一致，也会漏掉后端重算的负载统计与巡查任务。
    await loadSchedules();
    await loadOnDuty();
  } catch (e) {
    // 409 = 目标位置与既有排班冲突，后端已给出可读原因
    const msg = e?.response?.data?.detail || e?.response?.data?.message || '调整失败';
    showToast(msg, 'error');
  } finally {
    moving.value = false;
    dragging.value = null;
  }
}
const weekOffset = ref(0);
const schedules = ref([]);
const onDuty = ref([]);
const todaySchedules = ref([]);
const userList = ref([]);
const startDate = ref('');
const endDate = ref('');
const modal = ref({ show: false, loading: false, error: '' });
const form = ref({ userId: '', shiftDate: '', shiftType: 'day', startTime: '08:00', endTime: '20:00', note: '' });

// ESC 关闭弹窗
useKeyboard({ escape: () => { if (modal.value.show) modal.value.show = false; } });

const isAdmin = computed(() => {
  try { return JSON.parse(sessionStorage.getItem('current_user') || '{}').role === 'admin'; } catch { return false; }
});

const shiftTypes = [
  { value: 'day', icon: '☀️', label: '白班' },
  { value: 'night', icon: '🌙', label: '夜班' },
  { value: 'full', icon: '🕐', label: '全天' },
];
const shiftDefaults = {
  day: { start: '08:00', end: '20:00' },
  night: { start: '20:00', end: '08:00' },
  full: { start: '00:00', end: '23:59' },
};

function shiftLabel(type) {
  return { day: '白班', night: '夜班', full: '全天' }[type] || type;
}

function selectShiftType(val) {
  form.value.shiftType = val;
  form.value.startTime = shiftDefaults[val]?.start || '08:00';
  form.value.endTime = shiftDefaults[val]?.end || '20:00';
}

const weekLabel = computed(() => {
  if (!startDate.value || !endDate.value) return '本周';
  return `${startDate.value} ~ ${endDate.value}`;
});

const weekDays = computed(() => {
  if (!startDate.value) return [];
  const today = new Date().toISOString().slice(0, 10);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startDate.value);
    d.setDate(d.getDate() + i);
    const date = d.toISOString().slice(0, 10);
    const weekNames = ['日', '一', '二', '三', '四', '五', '六'];
    return {
      date,
      label: '周' + weekNames[d.getDay()],
      dateShort: `${d.getMonth() + 1}/${d.getDate()}`,
      isToday: date === today,
    };
  });
});

// ── 筛选 ────────────────────────────────────────────────────────────────
// 一周的排班量很小（实测 27 条 / 若干人），所以**在客户端筛**就够了：
// 服务端分页对"看一周网格"这件事没有意义，而多一次请求只会让切周更慢。
const filterUser = ref('');
const filterShift = ref('');
const hasFilter = computed(() => Boolean(filterUser.value) || Boolean(filterShift.value));

const filteredSchedules = computed(() => schedules.value.filter(s => {
  if (filterUser.value && String(s.userId) !== String(filterUser.value)) return false;
  if (filterShift.value && s.shiftType !== filterShift.value) return false;
  return true;
}));

// 人员下拉的可选项：优先用后端返回的护士列表；后端没给时退化为
// "本周实际有排班的人" —— 否则筛选项会是空的，看起来像坏了。
// 两种来源的键名不同（`id` vs `userId`），所以统一走 optionId 取值。
function optionId(n) { return n?.userId ?? n?.id ?? ''; }

const nurseOptions = computed(() => {
  if (userList.value.length) return userList.value;
  const seen = new Map();
  schedules.value.forEach(s => {
    if (s.userId != null && !seen.has(s.userId)) seen.set(s.userId, { userId: s.userId, name: s.userName });
  });
  return Array.from(seen.values());
});

function resetFilters() {
  filterUser.value = '';
  filterShift.value = '';
}

/** 回到本周。加了它之后，"翻了几周之后想回来"不必连点若干次 —— 原实现只有
 *  上周/下周两个按钮，且没有任何方式知道当前偏移了几周。 */
function goCurrentWeek() {
  if (weekOffset.value === 0) return;
  weekOffset.value = 0;
  loadSchedules();
}

const allSchedules = computed(() =>
  [...filteredSchedules.value].sort((a, b) => a.shiftDate?.localeCompare(b.shiftDate))
);

const groupedSchedules = computed(() => {
  const map = new Map();
  filteredSchedules.value.forEach(s => {
    if (!map.has(s.userId)) {
      map.set(s.userId, { userId: s.userId, name: s.userName, schedules: [] });
    }
    map.get(s.userId).schedules.push(s);
  });
  return Array.from(map.values());
});

function getSchedulesForDay(personSchedules, date) {
  return personSchedules.filter(s => s.shiftDate === date);
}
// 检测时间冲突
const hasConflict = computed(() => {
  if (!form.value.userId || !form.value.shiftDate) return false;
  
  return schedules.value.some(s => {
    if (s.userId !== form.value.userId || s.shiftDate !== form.value.shiftDate) return false;
    
    const formStart = form.value.startTime;
    const formEnd = form.value.endTime;
    const scheduleStart = s.startTime?.slice(0, 5);
    const scheduleEnd = s.endTime?.slice(0, 5);
    
    return !(formEnd <= scheduleStart || formStart >= scheduleEnd);
  });
});


// 一周的周一（后端以周一为起点，前端必须用同一口径，否则"上周/下周"会错位）
function weekStartOf(offset) {
  const d = new Date();
  const dow = (d.getDay() + 6) % 7;          // 周一=0
  d.setDate(d.getDate() - dow + offset * 7);
  return d.toISOString().slice(0, 10);
}

async function loadSchedules() {
  loading.value = true;
  try {
    // 原实现读的是 res.data.data.schedules，而 /schedules/ 走的是通用 CRUD
    // 分页接口，返回 { data: { data: [...], total, ... } } —— 字段对不上，
    // 于是 schedules 永远是空数组，页面长期显示"本周暂无排班记录"。
    // 改用专为排班值守设计的 /duty/overview，其结构与此页需求一致，
    // 并顺带带回护理员列表、周负载与巡查任务。
    const res = await getDutyOverview(weekStartOf(weekOffset.value));
    if (res.data.success) {
      const d = res.data.data;
      schedules.value = d.schedules || [];
      startDate.value = d.weekStart || '';
      endDate.value = d.weekEnd || '';
      if (d.nurses?.length) userList.value = d.nurses;
      workload.value = d.workload || {};
      patrolTasks.value = d.tasks || [];
    }
  } catch { showToast('加载排班失败', 'error'); }
  finally { loading.value = false; }
}

async function loadOnDuty() {
  try {
    const res = await getOnDuty();
    if (res.data.success) {
      onDuty.value = res.data.data.onDuty || [];
      todaySchedules.value = res.data.data.today || [];
    }
  } catch (e) {
    // "今天没人值班"和"值班信息读不出来"是两件事：前者要立刻安排人，
    // 后者要去查服务。静默失败会把第一个结论伪装成第二个。
    console.error('加载当日在岗失败', e);
    showToast(`当日在岗信息加载失败：${e?.friendlyMessage || '未知错误'}`, 'error');
  }
}

async function loadUsers() {
  try {
    const res = await getUserList();
    if (res.data.success) userList.value = res.data.data || [];
  } catch (e) {
    // 护士列表拿来填「人员」筛选下拉；失败后下拉是空的，用户会以为
    // 机构里没有护士，而不是"这个接口挂了"。
    console.error('加载人员列表失败', e);
    showToast(`人员列表加载失败：${e?.friendlyMessage || '未知错误'}`, 'error');
  }
}

function changeWeek(delta) {
  weekOffset.value += delta;
  loadSchedules();
}

function openAdd() {
  form.value = { userId: '', shiftDate: new Date().toISOString().slice(0, 10), shiftType: 'day', startTime: '08:00', endTime: '20:00', note: '' };
  modal.value = { show: true, loading: false, error: '' };
}

async function submitAdd() {
  modal.value.error = '';
  if (!form.value.userId) { modal.value.error = '请选择护理人员'; return; }
  if (!form.value.shiftDate) { modal.value.error = '请选择日期'; return; }
  modal.value.loading = true;
  try {
    const payload = {
      userId: form.value.userId,
      shiftDate: form.value.shiftDate,
      shiftType: form.value.shiftType,
      startTime: form.value.startTime + ':00',
      endTime: form.value.endTime + ':00',
      note: form.value.note || null,
    };
    const res = await createSchedule(payload);
    if (res.data.success) {
      showToast('排班创建成功', 'success');
      modal.value.show = false;
      loadSchedules();
    } else {
      modal.value.error = res.data.message || '创建失败';
    }
  } catch (e) {
    modal.value.error = e.response?.data?.message || '创建失败';
  } finally {
    modal.value.loading = false;
  }
}

function deleteSchedule(s) {
  if (!window.confirm(`确认删除 ${s.userName} 在 ${s.shiftDate} 的 ${shiftLabel(s.shiftType)} 排班？`)) {
    return;
  }
  executeDelete(s.id);
}

async function executeDelete(scheduleId) {
  try {
    const res = await deleteApi(scheduleId);
    if (res.data.success) {
      showToast('已删除', 'success');
      loadSchedules();
    } else showToast(res.data.message || '删除失败', 'error');
  } catch { showToast('删除失败', 'error'); }
}

onMounted(() => { loadSchedules(); loadOnDuty(); loadUsers(); });
</script>

<style scoped>
.page { padding: 24px; min-height: calc(100vh - var(--header-h)); }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; gap: 12px; flex-wrap: wrap; }
h1 { font-size: 22px; font-weight: 800; color: var(--text-primary); letter-spacing: -.3px; }
.page-sub { font-size: 12px; color: var(--text-muted); margin-top: 3px; }
/* 工具栏里的"上周/本周/下周"是按钮，但用了 .toolbar-field 的尺寸 —— 
   按钮与下拉在同一条工具栏里必须等高，否则一眼就看出参差。 */
.toolbar-field { cursor: pointer; }
.week-now.on { border-color: var(--primary); color: var(--primary); font-weight: 600; }
.week-label { white-space: nowrap; font-variant-numeric: tabular-nums; }
.header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.week-btn { padding: 7px 14px; border-radius: 8px; border: 1px solid var(--tint-4); background: var(--tint-1); color: var(--text-tertiary); cursor: pointer; font-size: 12px; transition: all .15s; font-weight: 500; }
.week-btn:hover { background: var(--tint-3); color: var(--text-secondary); }
.week-label { font-size: 12px; color: var(--text-tertiary); white-space: nowrap; min-width: 160px; text-align: center; }
.btn-add { padding: 8px 16px; border-radius: 9px; border: none; background: linear-gradient(135deg, var(--primary), var(--primary-active)); color: var(--text-on-color); cursor: pointer; font-size: 12px; font-weight: 600; white-space: nowrap; box-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 30%, transparent); transition: all .15s; }
.btn-add:hover { box-shadow: 0 4px 14px color-mix(in srgb, var(--primary) 40%, transparent); transform: translateY(-1px); }
.on-duty-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; padding: 11px 16px; background: color-mix(in srgb, var(--success) 4%, transparent); border: 1px solid color-mix(in srgb, var(--success) 13%, transparent); border-radius: 12px; flex-wrap: wrap; }
.duty-label { font-size: 11px; font-weight: 700; color: var(--success); white-space: nowrap; text-transform: uppercase; letter-spacing: .3px; }
.duty-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.duty-chip { padding: 3px 10px; border-radius: 20px; background: color-mix(in srgb, var(--success) 10%, transparent); color: var(--success-text); font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 5px; border: 1px solid color-mix(in srgb, var(--success) 15%, transparent); }
.duty-shift { font-size: 10px; color: var(--success); opacity: .8; }
.no-duty { font-size: 12px; color: var(--text-muted); }
/* 周视图的最小列宽：8 列（姓名 + 7 天）如果随时间宽度无限压缩，实测在 800px 时
   每天只剩 87px，班次胶囊被挤成一条竖线。给它一个下限 —— 装不下时**横向滚动**，
   而不是继续压扁。滚动比"把内容压到看不清"要好，也比直接丢掉周视图（换成卡片
   列表）保留了"一周七天"的心智模型。 */
.week-grid { background: var(--tint-1); border-radius: var(--radius-md); overflow-x: auto; }
/* 最小总宽 = 姓名列 140px + 7 天 × 110px = 910px。
   110px 是"班次胶囊折成两行但仍清晰可读"的下限；低于它胶囊会挤成一条竖线
   （实测 800px 视口下每天只剩 87px）。 */
.week-header, .week-row { min-width: 910px; }
.week-header { display: grid; grid-template-columns: 140px repeat(7, 1fr); border-bottom: 1px solid var(--tint-3); background: var(--tint-1); }
.week-th { padding: 12px 8px; font-size: 11px; font-weight: 700; color: var(--text-muted); text-align: center; }
.week-th.today .day-name { color: var(--primary-hover); }
.day-name { font-size: 12px; font-weight: 700; margin-bottom: 2px; }
.day-date { font-size: 10px; opacity: .6; }
.week-row { display: grid; grid-template-columns: 140px repeat(7, 1fr); border-bottom: 1px solid var(--tint-1); min-height: 60px; }
.week-row:last-child { border-bottom: none; }
.week-td { padding: 8px 6px; display: flex; flex-direction: column; gap: 4px; }
.week-td.today { background: color-mix(in srgb, var(--primary) 3%, transparent); }
.time-col { display: flex; align-items: center; gap: 8px; padding: 8px 14px; }
.person-avatar { width: 28px; height: 28px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--violet)); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: var(--text-on-color); flex-shrink: 0; }
.person-name { font-size: 12px; color: var(--text-tertiary); font-weight: 600; }
.schedule-chip { display: flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 6px; font-size: 11px; position: relative; }
.schedule-chip.type-day { background: color-mix(in srgb, var(--primary) 10%, transparent); color: var(--primary-hover); border: 1px solid color-mix(in srgb, var(--primary) 18%, transparent); }
.schedule-chip.type-night { background: color-mix(in srgb, var(--violet) 10%, transparent); color: var(--violet-text); border: 1px solid color-mix(in srgb, var(--violet) 18%, transparent); }
.schedule-chip.type-full { background: color-mix(in srgb, var(--success) 8%, transparent); color: var(--success-text); border: 1px solid color-mix(in srgb, var(--success) 13%, transparent); }
.chip-time { font-size: 10px; opacity: .75; }
.chip-label { font-weight: 600; font-size: 11px; }
.chip-del { background: none; border: none; color: inherit; cursor: pointer; font-size: 12px; opacity: .4; padding: 0; margin-left: 2px; line-height: 1; transition: opacity .15s; }
.chip-del:hover { opacity: 1; }
.empty-week { padding: 48px; text-align: center; color: var(--text-muted); font-size: 13px; }
.loading-state { padding: 48px; text-align: center; color: var(--text-muted); }
.mobile-list { display: none; }
.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 16px; width: 440px; max-width: 95vw; max-height: 90vh; overflow-y: auto; box-shadow: 0 24px 64px color-mix(in srgb, var(--shadow-color) 60%, transparent); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--tint-3); position: sticky; top: 0; background: var(--bg-surface-2); z-index: 1; }
.modal-header h3 { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: var(--tint-2); border: 1px solid var(--tint-3); border-radius: 7px; color: var(--text-tertiary); font-size: 16px; cursor: pointer; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; transition: all .15s; }
.close-btn:hover { background: var(--tint-4); color: var(--text-tertiary); }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-group label { font-size: 11px; font-weight: 700; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: .3px; }
.req { color: var(--danger); }
.field-group input, .field-group select { background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: 8px; padding: 9px 12px; color: var(--text-secondary); font-size: 13px; outline: none; width: 100%; box-sizing: border-box; transition: border-color .2s; }
.warning-text {
  font-size: 11px;
  color: var(--warning);
  display: flex;
  align-items: center;
  gap: 4px;
}
.field-group input:focus, .field-group select:focus { border-color: color-mix(in srgb, var(--primary) 40%, transparent); }
.field-group select { padding-right: 32px; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2364748b'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.shift-types { display: flex; gap: 8px; }
.shift-btn { flex: 1; padding: 9px 8px; border-radius: 8px; border: 1px solid var(--tint-4); background: var(--tint-1); color: var(--text-tertiary); cursor: pointer; font-size: 12px; transition: all .18s; }
.shift-btn:hover { border-color: var(--tint-5); color: var(--text-tertiary); }
.shift-btn.active { border-color: color-mix(in srgb, var(--primary) 45%, transparent); background: color-mix(in srgb, var(--primary) 10%, transparent); color: var(--primary-hover); font-weight: 600; }
.form-error { font-size: 12px; color: var(--danger-text); background: color-mix(in srgb, var(--danger) 8%, transparent); border: 1px solid color-mix(in srgb, var(--danger) 18%, transparent); border-radius: 6px; padding: 8px 12px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--tint-3); position: sticky; bottom: 0; background: var(--bg-surface-2); }
.btn-cancel { padding: 8px 18px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 13px; transition: all .15s; }
.btn-cancel:hover { background: var(--tint-2); }
.btn-primary { padding: 8px 20px; border-radius: 8px; border: none; background: linear-gradient(135deg, var(--primary), var(--primary-active)); color: var(--text-on-color); cursor: pointer; font-weight: 600; font-size: 13px; box-shadow: 0 2px 8px color-mix(in srgb, var(--primary) 30%, transparent); transition: all .15s; }
.btn-primary:hover:not(:disabled) { box-shadow: 0 4px 14px color-mix(in srgb, var(--primary) 40%, transparent); }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }

@media (max-width: 720px) {
  .page { padding: 14px; padding-bottom: 80px; }
  h1 { font-size: 19px; }
  .page-header { flex-wrap: wrap; gap: 8px; }
  .header-actions { width: 100%; justify-content: space-between; }
  .week-label { font-size: 11px; min-width: 0; }
  .week-btn { padding: 6px 10px; font-size: 12px; }
  .desktop-grid { display: none; }
  .mobile-list { display: block; }
  .schedule-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: var(--radius-md); padding: 14px; margin-bottom: 10px; }
  .schedule-card.type-day { border-left: 3px solid var(--primary); }
  .schedule-card.type-night { border-left: 3px solid var(--violet); }
  .schedule-card.type-full { border-left: 3px solid var(--success); }
  .sc-top { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .sc-avatar { width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg,var(--primary),var(--violet)); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; color: var(--text-on-color); flex-shrink: 0; }
  .sc-info { flex: 1; min-width: 0; }
  .sc-name { font-size: 14px; font-weight: 700; color: var(--text-primary); }
  .sc-date { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; }
  .sc-time { font-size: 12px; color: var(--text-tertiary); white-space: nowrap; }
  .sc-foot { display: flex; align-items: center; justify-content: space-between; }
  .sc-note { font-size: 12px; color: var(--text-muted); }
  .btn-del-sm { padding: 5px 12px; border-radius: 6px; border: 1px solid color-mix(in srgb, var(--danger) 25%, transparent); background: transparent; color: var(--danger-text); cursor: pointer; font-size: 12px; min-height: 36px; transition: all .15s; }
  .btn-del-sm:hover { background: color-mix(in srgb, var(--danger) 8%, transparent); }
  .on-duty-bar { flex-direction: column; align-items: flex-start; }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; max-height: 92vh; background: var(--bg-surface-2); }
  .modal-mask { align-items: flex-end; }
  .field-row { grid-template-columns: 1fr 1fr; }
  .shift-types { gap: 6px; }
  .shift-btn { font-size: 11px; padding: 8px 4px; min-height: 44px; flex: 1; }
  .modal-footer { flex-direction: column; gap: 8px; }
  .btn-cancel, .btn-primary { width: 100%; min-height: 48px; font-size: 15px; border-radius: 12px; }
}

/* ── 拖拽调班 ─────────────────────────────────────────────────────────── */
.schedule-chip[draggable="true"] { cursor: grab; }
.schedule-chip[draggable="true"]:active { cursor: grabbing; }
.week-td.is-dragging { opacity: .45; }
.week-td.drop-ok {
  background: color-mix(in srgb, var(--primary) 10%, transparent);
  outline: 2px dashed var(--primary);
  outline-offset: -3px;
  border-radius: 8px;
}
.drop-hint {
  font-size: 11px; color: var(--primary);
  display: flex; align-items: center; justify-content: center;
  height: 100%; min-height: 34px; opacity: .85;
}
</style>
