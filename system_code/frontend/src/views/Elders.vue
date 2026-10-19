<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>老人档案</h1>
        <div class="page-sub">管理在院老人基本信息</div>
      </div>
    </div>

    <!-- 工具栏：条件查询在左，作用于列表的操作在右。
         新增按钮原来放在页头右上；统一挪进工具栏之后，
         全站七个列表页都是「左边筛条件、右边管列表」同一套布局，
         页头右侧只留给**与列表无关**的页面级操作。 -->
    <div class="toolbar">
      <input v-model="keyword" class="toolbar-search"
             placeholder="搜索姓名或房间号…" @input="onSearchInput" />
      <select v-model="statusFilter" class="toolbar-field" @change="onFilter">
        <option value="">全部状态</option>
        <option value="1">在档</option>
        <option value="0">已离院</option>
      </select>
      <button class="toolbar-reset" :disabled="!hasFilter" @click="resetFilters">重置</button>
      <div class="toolbar-actions">
        <button class="btn-primary" @click="openCreate">+ 新增老人</button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else-if="loadError" class="load-error">{{ loadError }}</div>
    <div v-else-if="!elders.length" class="empty-state">
      <div class="empty-icon">👴</div>
      <div>暂无老人档案</div>
    </div>
    <div v-else class="elder-grid">
      <div v-for="elder in elders" :key="elder.id" class="elder-card" @click="openDetail(elder)">
        <div class="card-header">
          <div class="elder-avatar">
            <img v-if="elder.avatar" :src="elder.avatar" class="avatar-img" />
            <span v-else>{{ elder.name?.charAt(0) }}</span>
          </div>
          <div class="elder-basic">
            <div class="elder-name">{{ elder.name }}</div>
            <div class="elder-meta">{{ genderLabel(elder.gender) }} · {{ elder.age }}岁 · {{ elder.roomNo }}室</div>
          </div>
          <span class="status-badge" :class="elder.status === 1 ? 'active' : 'archived'">
            {{ elder.status === 1 ? '在档' : '已离院' }}
          </span>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">入院日期</span>
            <span class="info-val">{{ formatDate(elder.admissionDate) }}</span>
          </div>
          <div class="info-row" v-if="elder.contactName">
            <span class="info-label">紧急联系人</span>
            <span class="info-val">{{ elder.contactName }}</span>
          </div>
          <div class="info-row" v-if="elder.healthNotes">
            <span class="info-label">健康备注</span>
            <span class="info-val notes">{{ elder.healthNotes }}</span>
          </div>
        </div>
        <div class="card-actions" @click.stop>
          <button class="btn-sm" @click="openEdit(elder)">编辑</button>
          <button class="btn-sm qr" @click="openQRCode(elder)">🏥 二维码</button>
          <button v-if="elder.status === 1" class="btn-sm danger" @click="archiveElder(elder)">停档</button>
        </div>
      </div>
    </div>

    <Pagination
      v-model:page="pagination.page"
      v-model:pageSize="pagination.pageSize"
      :total="pagination.total"
      @change="loadElders"
    />

    <!-- 详情弹窗 -->
    <div v-if="detailModal.show" class="modal-mask" @click.self="detailModal.show = false">
      <div class="modal-box detail-modal">
        <div class="modal-header">
          <h3>老人详情</h3>
          <button class="close-btn" @click="detailModal.show = false">×</button>
        </div>
        <div class="modal-body" v-if="detailModal.elder">
          <div class="detail-top">
            <div class="detail-avatar">
              <img v-if="detailModal.elder.avatar" :src="detailModal.elder.avatar" class="detail-avatar-img" />
              <span v-else>{{ detailModal.elder.name?.charAt(0) }}</span>
            </div>
            <div>
              <div class="detail-name">{{ detailModal.elder.name }}</div>
              <div class="detail-sub">{{ genderLabel(detailModal.elder.gender) }} · {{ detailModal.elder.age }}岁 · {{ detailModal.elder.roomNo }}室</div>
            </div>
          </div>
          <div class="detail-grid">
            <div class="ditem"><span class="dlabel">入院日期</span><span>{{ formatDate(detailModal.elder.admissionDate) }}</span></div>
            <div class="ditem"><span class="dlabel">紧急联系</span><span>{{ detailModal.elder.contactName || '-' }}</span></div>
            <div class="ditem"><span class="dlabel">联系电话</span><span>{{ detailModal.elder.contactPhone || '-' }}</span></div>
            <div class="ditem full"><span class="dlabel">健康备注</span><span>{{ detailModal.elder.healthNotes || '-' }}</span></div>
          </div>
          <div class="history-section">
            <div class="section-title">📋 历史告警记录（最近20条）</div>
            <div v-if="!detailModal.elder.alertHistory?.length" class="empty-sub">暂无告警记录</div>
            <div v-else class="history-list">
              <div v-for="a in detailModal.elder.alertHistory" :key="a.id" class="history-item">
                <span class="level-tag" :style="{ background: riskBg(a.riskLevel), color: riskColor(a.riskLevel) }">{{ a.riskLevel }}</span>
                <span class="h-conf">{{ a.confidence }}%</span>
                <span class="h-time">{{ formatTime(a.alertTime) }}</span>
                <span class="h-status" :class="a.status === 1 ? 'done' : 'pending'">{{ a.status === 1 ? '已处理' : '待处理' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="formModal.show" class="modal-mask" @click.self="formModal.show = false">
      <div class="modal-box form-modal">
        <div class="modal-header">
          <h3>{{ formModal.isEdit ? '编辑老人档案' : '新增老人档案' }}</h3>
          <button class="close-btn" @click="formModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <!-- 头像上传区 -->
          <div class="avatar-upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="onAvatarDrop">
            <img v-if="avatarPreview || formData.avatar" :src="avatarPreview || formData.avatar" class="avatar-preview" />
            <div v-else class="avatar-placeholder">
              <span class="avatar-plus">📷</span>
              <span class="avatar-hint">点击上传照片</span>
            </div>
            <div v-if="uploading" class="avatar-uploading">上传中...</div>
          </div>
          <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onAvatarChange" />

          <div class="form-grid">
            <div class="field-group">
              <label>姓名 <span class="req">*</span></label>
              <input v-model="formData.name" placeholder="请输入姓名" />
            </div>
            <div class="field-group">
              <label>性别 <span class="req">*</span></label>
              <select v-model="formData.gender">
                <option :value="1">男</option>
                <option :value="2">女</option>
              </select>
            </div>
            <div class="field-group">
              <label>年龄 <span class="req">*</span></label>
              <input v-model="formData.age" type="number" min="1" max="150" placeholder="请输入年龄" />
            </div>
            <div class="field-group">
              <label>房间号 <span class="req">*</span></label>
              <input v-model="formData.roomNo" placeholder="如：101" />
            </div>
            <div class="field-group">
              <label>入院日期 <span class="req">*</span></label>
              <input v-model="formData.admissionDate" type="date" />
            </div>
            <div class="field-group">
              <label>紧急联系人</label>
              <input v-model="formData.emergencyContact" placeholder="如：张明（儿子）" />
            </div>
            <div class="field-group">
              <label>紧急联系电话</label>
              <input v-model="formData.emergencyPhone" placeholder="如：138xxxx0001" />
            </div>
            <div class="field-group full">
              <label>健康状况备注</label>
              <textarea v-model="formData.healthNotes" placeholder="如：高血压，需定期测量血压" rows="3"></textarea>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="formModal.show = false">取消</button>
          <button class="btn-primary" @click="submitForm" :disabled="formModal.loading || uploading">
            {{ formModal.loading ? '提交中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 二维码弹窗 -->
    <QRCodeModal v-if="qrModal.show" :elder="qrModal.elder" @close="qrModal.show = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import Pagination from '../components/Pagination.vue';
import { getElderList, getElderDetail, createElder, updateElder, archiveElder as archiveApi, uploadElderAvatar } from '../api/elders.js';
import { genderLabel, formatDate, formatTime, riskColor, riskBg, showToast } from '../utils/index.js';
import QRCodeModal from '../components/QRCodeModal.vue';
import { debounce } from 'lodash-es';

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

const elders = ref([]);
const loading = ref(false);
// 列表加载失败时的行内提示：空态文案是「暂无老人档案」，
// 不能让它把"档案列表读不出来"说成"机构里没有老人"。
const loadError = ref('');
const keyword = ref('');
const statusFilter = ref('1');
const pagination = ref({ page: 1, pageSize: 20, total: 0, totalPages: 1 });
const detailModal = ref({ show: false, elder: null });
const formModal = ref({ show: false, isEdit: false, loading: false });
const formData = ref({});
const avatarPreview = ref('');
const uploading = ref(false);
const fileInput = ref(null);
const qrModal = ref({ show: false, elder: null });
let pendingAvatarFile = null;

const loadElders = debounce(async () => {
  loading.value = true;
  try {
    const res = await getElderList({ page: pagination.value.page,
                                     pageSize: pagination.value.pageSize,
                                     keyword: keyword.value, status: statusFilter.value });
    if (res.data.success) {
      elders.value = res.data.data.data;
      applyPagination(res.data.data, pagination);
    }
    loadError.value = '';
  } catch (e) {
    console.error('加载老人档案失败', e);
    loadError.value = `档案列表加载失败：${e?.friendlyMessage || '未知错误'}`;
  }
  finally { loading.value = false; }
}, 300);

// 防抖：原实现 @input 直接发请求，输入"张国强"要打 3 次接口，
// 而且返回顺序不保证 —— 慢的那次后到就会覆盖快的那次，列表闪回旧结果。
let searchTimer = null;
function onSearchInput() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { pagination.value.page = 1; loadElders(); }, 300);
}
function onFilter() { pagination.value.page = 1; loadElders(); }

// 状态默认是 '1'（在档），那是**默认值而不是筛选条件** —— 若把它算进去，
// 页面一打开「重置」就是可用态，但点了并不会改变任何东西，按钮就在说谎。
const hasFilter = computed(() => Boolean(keyword.value) || (statusFilter.value !== '' && statusFilter.value !== '1'));
function resetFilters() {
  keyword.value = '';
  statusFilter.value = '1';   // 回到默认的「在档」，而不是「全部」
  pagination.value.page = 1;
  loadElders();
}

async function openDetail(elder) {
  try {
    const res = await getElderDetail(elder.id);
    if (res.data.success) detailModal.value = { show: true, elder: res.data.data };
  } catch (e) {
    // 点「详情」没有任何反应是最让人困惑的失败形态：用户会以为是自己没点中。
    console.error('加载老人详情失败', e);
    showToast(`档案详情加载失败：${e?.friendlyMessage || '未知错误'}`, 'error');
  }
}

function openCreate() {
  formData.value = { name: '', gender: 1, age: '', roomNo: '', admissionDate: '', emergencyContact: '', emergencyPhone: '', healthNotes: '' };
  avatarPreview.value = '';
  pendingAvatarFile = null;
  formModal.value = { show: true, isEdit: false, loading: false };
}

function openEdit(elder) {
  formData.value = { name: elder.name, gender: elder.gender, age: elder.age, roomNo: elder.roomNo, admissionDate: elder.admissionDate?.split('T')[0] || '', emergencyContact: elder.contactName || '', emergencyPhone: elder.contactPhone || '', healthNotes: elder.healthNotes || '', avatar: elder.avatar || '', id: elder.id };
  avatarPreview.value = '';
  pendingAvatarFile = null;
  formModal.value = { show: true, isEdit: true, loading: false };
}

function triggerFileInput() {
  fileInput.value?.click();
}

function onAvatarDrop(e) {
  const file = e.dataTransfer?.files?.[0];
  if (file && file.type.startsWith('image/')) setAvatarFile(file);
}

function onAvatarChange(e) {
  const file = e.target.files?.[0];
  if (file) setAvatarFile(file);
}

function setAvatarFile(file) {
  if (file.size > 5 * 1024 * 1024) { showToast('图片不能超过 5MB', 'warning'); return; }
  pendingAvatarFile = file;
  const reader = new FileReader();
  reader.onload = e => { avatarPreview.value = e.target.result; };
  reader.readAsDataURL(file);
}

async function submitForm() {
  formModal.value.loading = true;
  try {
    let res;
    if (formModal.value.isEdit) {
      res = await updateElder(formData.value.id, formData.value);
    } else {
      res = await createElder(formData.value);
      if (res.data.success) pagination.value.page = 1;
    }
    if (!res.data.success) { showToast(res.data.message || '操作失败', 'error'); return; }
    const elderId = res.data.data?.id || formData.value.id;
    if (pendingAvatarFile && elderId) {
      uploading.value = true;
      try {
        await uploadElderAvatar(elderId, pendingAvatarFile);
      } catch { showToast('照片上传失败，档案已保存', 'warning'); }
      finally { uploading.value = false; }
    }
    showToast(formModal.value.isEdit ? '更新成功' : '创建成功', 'success');
    formModal.value.show = false;
    loadElders();
  } catch (e) { showToast(e.response?.data?.message || '网络错误', 'error'); }
  finally { formModal.value.loading = false; }
}

async function archiveElder(elder) {
  if (!confirm(`确认将【${elder.name}】停档？`)) return;
  try {
    const res = await archiveApi(elder.id);
    if (res.data.success) { showToast('停档成功', 'success'); loadElders(); }
    else showToast(res.data.message, 'error');
  } catch (e) {
    // 用户已经在原生 confirm 上点过一次"确认"，失败后**必须有反馈**：
    // 原来的空 catch 让卡片继续显示"在档"，用户会以为点漏了，反复点。
    console.error('停档失败', e);
    showToast(`停档失败：${e?.friendlyMessage || '未知错误'}`, 'error');
  }
}

function openQRCode(elder) {
  qrModal.value = { show: true, elder };
}


onMounted(loadElders);
</script>

<style scoped>
.page { padding: 24px; min-height: calc(100vh - var(--header-h)); }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
h1 { font-size: 22px; font-weight: 800; color: var(--text-primary); }
.page-sub { font-size: 13px; color: var(--text-muted); margin-top: 3px; }
.btn-primary { padding: 9px 20px; border-radius: 10px; border: none; background: var(--primary); color: var(--text-on-color); cursor: pointer; font-weight: 600; font-size: 13px; white-space: nowrap; }
.btn-primary:hover { background: var(--primary-active); }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.field-group select { padding-right: 32px; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2364748b'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; }
.loading-state, .empty-state { text-align: center; padding: 60px; color: var(--text-muted); }
.empty-icon { font-size: 48px; margin-bottom: 12px; opacity: .4; }
.elder-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.elder-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 16px; overflow: hidden; cursor: pointer; transition: transform .2s, border-color .2s; }
.elder-card:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--primary) 30%, transparent); }
.card-header { display: flex; align-items: center; gap: 12px; padding: 16px 16px 10px; }
.elder-avatar { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--violet)); display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; color: var(--text-on-color); flex-shrink: 0; overflow: hidden; }
.avatar-img { width: 100%; height: 100%; object-fit: cover; }
.elder-name { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.elder-meta { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; }
.status-badge { margin-left: auto; padding: 3px 9px; border-radius: 6px; font-size: 11px; font-weight: 600; white-space: nowrap; }
.status-badge.active { background: color-mix(in srgb, var(--success) 12%, transparent); color: var(--success); }
.status-badge.archived { background: color-mix(in srgb, var(--neutral) 12%, transparent); color: var(--text-tertiary); }
.card-body { padding: 0 16px 10px; display: flex; flex-direction: column; gap: 5px; }
.info-row { display: flex; gap: 8px; font-size: 12px; }
.info-label { color: var(--text-muted); width: 64px; flex-shrink: 0; }
.info-val { color: var(--text-tertiary); }
.info-val.notes { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.card-actions { display: flex; gap: 8px; padding: 10px 16px; border-top: 1px solid var(--tint-2); }
.btn-sm { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 12px; min-height: 32px; }
.btn-sm:hover { background: var(--tint-3); }
.btn-sm.danger { border-color: color-mix(in srgb, var(--danger) 30%, transparent); color: var(--danger-text); }
.btn-sm.danger:hover { background: color-mix(in srgb, var(--danger) 8%, transparent); }
.btn-sm.qr { border-color: color-mix(in srgb, var(--primary) 30%, transparent); color: var(--primary-hover); }
.pagination { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 24px; }
.page-btn { width: 36px; height: 36px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 16px; }
.page-btn:disabled { opacity: .4; cursor: not-allowed; }
.page-info { font-size: 13px; color: var(--text-tertiary); }
.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 16px; max-width: 95vw; max-height: 90vh; overflow-y: auto; }
.detail-modal { width: 520px; }
.form-modal { width: 600px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--tint-3); position: sticky; top: 0; background: var(--bg-surface-2); z-index: 1; }
.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: none; border: none; color: var(--text-tertiary); font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; }
.avatar-upload-area { position: relative; width: 80px; height: 80px; border-radius: 50%; border: 2px dashed color-mix(in srgb, var(--primary) 40%, transparent); display: flex; align-items: center; justify-content: center; cursor: pointer; margin: 0 auto 20px; overflow: hidden; background: color-mix(in srgb, var(--primary) 5%, transparent); transition: border-color .2s; }
.avatar-upload-area:hover { border-color: color-mix(in srgb, var(--primary) 80%, transparent); }
.avatar-preview { width: 100%; height: 100%; object-fit: cover; }
.avatar-placeholder { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.avatar-plus { font-size: 22px; }
.avatar-hint { font-size: 9px; color: var(--text-muted); white-space: nowrap; }
.avatar-uploading { position: absolute; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; font-size: 11px; color: var(--text-on-color); }
.detail-top { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.detail-avatar { width: 56px; height: 56px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--violet)); display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; color: var(--text-on-color); overflow: hidden; flex-shrink: 0; }
.detail-avatar-img { width: 100%; height: 100%; object-fit: cover; }
.detail-name { font-size: 18px; font-weight: 800; color: var(--text-primary); }
.detail-sub { font-size: 13px; color: var(--text-tertiary); margin-top: 4px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
.ditem { display: flex; flex-direction: column; gap: 3px; background: var(--tint-1); border-radius: 10px; padding: 10px 14px; }
.ditem.full { grid-column: 1/-1; }
.dlabel { font-size: 11px; color: var(--text-muted); }
.ditem span:last-child { font-size: 13px; color: var(--text-tertiary); }
.section-title { font-size: 13px; font-weight: 700; color: var(--text-tertiary); margin-bottom: 10px; }
.empty-sub { font-size: 12px; color: var(--text-muted); padding: 16px 0; }
.history-list { display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto; }
.history-item { display: flex; align-items: center; gap: 8px; padding: 7px 12px; background: var(--tint-1); border-radius: 8px; }
.level-tag { padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 700; }
.h-conf { font-size: 12px; color: var(--text-tertiary); }
.h-time { font-size: 11px; color: var(--text-muted); margin-left: auto; }
.h-status { font-size: 11px; padding: 2px 7px; border-radius: 4px; }
.h-status.done { background: color-mix(in srgb, var(--success) 12%, transparent); color: var(--success); }
.h-status.pending { background: color-mix(in srgb, var(--warning) 12%, transparent); color: var(--warning); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-group.full { grid-column: 1/-1; }
.field-group label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); }
.req { color: var(--danger); }
.field-group input, .field-group select, .field-group textarea { background: var(--tint-3); border: 1px solid var(--tint-4); border-radius: 8px; padding: 9px 12px; color: var(--text-secondary); font-size: 13px; outline: none; font-family: inherit; }
.field-group input:focus, .field-group select:focus, .field-group textarea:focus { border-color: color-mix(in srgb, var(--primary) 50%, transparent); }
.field-group textarea { resize: none; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 20px; border-top: 1px solid var(--tint-3); }
.btn-cancel { padding: 8px 20px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; }
@media (max-width: 768px) {
  .page { padding: 14px; }
  h1 { font-size: 18px; }
  .page-header { flex-wrap: wrap; gap: 8px; }
  .btn-primary { font-size: 12px; padding: 8px 14px; }
  .elder-grid { grid-template-columns: 1fr; gap: 10px; }
  .elder-card:hover { transform: none; }
  .btn-sm { min-height: 44px; font-size: 13px; flex: 1; text-align: center; }
  .detail-grid, .form-grid { grid-template-columns: 1fr; }
  .field-group.full { grid-column: 1; }
  .field-group input, .field-group select, .field-group textarea { padding: 12px; font-size: 16px; }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; max-height: 92vh; }
  .modal-mask { align-items: flex-end; }
  .detail-modal, .form-modal { width: 100%; }
}
</style>
