<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal-box">
      <div class="modal-header">
        <h3>修改密码</h3>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>
      <div class="modal-body">
        <div class="field">
          <label>旧密码</label>
          <div class="input-wrap">
            <input v-model="form.oldPassword" :type="show.old ? 'text' : 'password'" placeholder="请输入当前密码" />
            <span class="eye" @click="show.old = !show.old">{{ show.old ? '🙈' : '👁️' }}</span>
          </div>
        </div>
        <div class="field">
          <label>新密码</label>
          <div class="input-wrap">
            <input v-model="form.newPassword" :type="show.new ? 'text' : 'password'" placeholder="至少 6 位" />
            <span class="eye" @click="show.new = !show.new">{{ show.new ? '🙈' : '👁️' }}</span>
          </div>
          <div class="pwd-strength">
            <div class="strength-bar" :class="strengthClass"></div>
            <span class="strength-label">{{ strengthLabel }}</span>
          </div>
        </div>
        <div class="field">
          <label>确认新密码</label>
          <div class="input-wrap">
            <input v-model="form.confirm" :type="show.confirm ? 'text' : 'password'" placeholder="再次输入新密码" />
            <span class="eye" @click="show.confirm = !show.confirm">{{ show.confirm ? '🙈' : '👁️' }}</span>
          </div>
        </div>
        <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>
        <div v-if="successMsg" class="success-bar">{{ successMsg }}</div>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-primary" @click="submit" :disabled="loading">{{ loading ? '提交中...' : '确认修改' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { changePassword } from '../api/auth.js';

const emit = defineEmits(['close']);
const loading = ref(false);
const errorMsg = ref('');
const successMsg = ref('');
const form = ref({ oldPassword: '', newPassword: '', confirm: '' });
const router = useRouter();
const show = ref({ old: false, new: false, confirm: false });

const strength = computed(() => {
  const p = form.value.newPassword;
  if (!p) return 0;
  let score = 0;
  if (p.length >= 6) score++;
  if (p.length >= 10) score++;
  if (/[A-Z]/.test(p)) score++;
  if (/[0-9]/.test(p)) score++;
  if (/[^A-Za-z0-9]/.test(p)) score++;
  return Math.min(score, 4);
});

const strengthClass = computed(() => ['', 'weak', 'fair', 'good', 'strong'][strength.value]);
const strengthLabel = computed(() => ['', '弱', '一般', '良好', '强'][strength.value]);

async function submit() {
  errorMsg.value = '';
  successMsg.value = '';
  if (!form.value.oldPassword) { errorMsg.value = '请输入旧密码'; return; }
  if (form.value.newPassword.length < 6) { errorMsg.value = '新密码至少 6 位'; return; }
  if (form.value.newPassword !== form.value.confirm) { errorMsg.value = '两次密码不一致'; return; }
  loading.value = true;
  try {
    const res = await changePassword({ oldPassword: form.value.oldPassword, newPassword: form.value.newPassword, confirmPassword: form.value.confirm });
    if (res.data.success) {
      successMsg.value = '密码修改成功，请重新登录';
      setTimeout(() => {
        sessionStorage.removeItem('api_token');
        sessionStorage.removeItem('current_user');
        router.push('/login');
      }, 1500);
    } else {
      errorMsg.value = res.data.message || '修改失败';
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.message || '操作失败';
  }
  loading.value = false;
}
</script>

<style scoped>
.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 18px; width: 400px; max-width: 95vw; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 18px 22px; border-bottom: 1px solid var(--tint-3); }
.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: none; border: none; color: var(--text-tertiary); font-size: 22px; cursor: pointer; line-height: 1; }
.modal-body { padding: 22px; display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); }
.input-wrap { display: flex; align-items: center; background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: 10px; padding: 0 12px; }
.input-wrap:focus-within { border-color: color-mix(in srgb, var(--primary) 50%, transparent); }
.input-wrap input { flex: 1; background: transparent; border: none; outline: none; color: var(--text-secondary); font-size: 14px; padding: 10px 0; }
.input-wrap input::placeholder { color: var(--text-muted); }
.eye { font-size: 15px; cursor: pointer; opacity: .7; flex-shrink: 0; }
.eye:hover { opacity: 1; }
.pwd-strength { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.strength-bar { height: 4px; flex: 1; border-radius: 4px; background: var(--tint-3); transition: background .3s; }
.strength-bar.weak { background: var(--danger); }
.strength-bar.fair { background: var(--level-medium); }
.strength-bar.good { background: var(--warning-text); }
.strength-bar.strong { background: var(--success); }
.strength-label { font-size: 11px; color: var(--text-tertiary); width: 28px; }
.error-bar { background: color-mix(in srgb, var(--danger) 10%, transparent); border: 1px solid color-mix(in srgb, var(--danger) 20%, transparent); color: var(--danger-text); border-radius: 8px; padding: 8px 12px; font-size: 13px; }
.success-bar { background: color-mix(in srgb, var(--success) 10%, transparent); border: 1px solid color-mix(in srgb, var(--success) 20%, transparent); color: var(--success-text); border-radius: 8px; padding: 8px 12px; font-size: 13px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 22px; border-top: 1px solid var(--tint-3); }
.btn-cancel { padding: 8px 20px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; }
.btn-primary { padding: 8px 20px; border-radius: 8px; border: none; background: linear-gradient(135deg, var(--primary), var(--violet)); color: var(--text-on-color); font-weight: 600; cursor: pointer; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
@media (max-width: 768px) {
  .modal-mask { align-items: flex-end; }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; }
  .modal-footer { flex-direction: column; gap: 8px; }
  .btn-cancel, .btn-primary { width: 100%; min-height: 48px; font-size: 15px; border-radius: 12px; }
  .input-wrap input { font-size: 16px; padding: 12px 0; }
}
</style>
