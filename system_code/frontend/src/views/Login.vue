<template>
  <div class="login-root">
    <div class="bg-layer">
      <div class="blob blob1"></div>
      <div class="blob blob2"></div>
      <div class="blob blob3"></div>
    </div>

    <div class="login-card">
      <div class="card-logo">
        <div class="logo-icon">🏥</div>
        <div>
          <div class="logo-title">智慧养老监护系统</div>
          <div class="logo-sub">跌倒检测 · AI 智能告警</div>
        </div>
      </div>

      <div v-if="mode === 'login'" class="form-area">
        <h2 class="form-title">登录账号</h2>

        <div class="field">
          <label>账号</label>
          <div class="input-wrap">
            <span class="input-icon">👤</span>
            <input v-model="form.username" type="text" placeholder="请输入账号" @keyup.enter="submit" />
          </div>
        </div>

        <div class="field">
          <label>密码</label>
          <div class="input-wrap">
            <span class="input-icon">🔒</span>
            <input v-model="form.password" :type="showPwd ? 'text' : 'password'" placeholder="请输入密码" @keyup.enter="submit" />
            <span class="eye-btn" @click="showPwd = !showPwd">{{ showPwd ? '🙈' : '👁️' }}</span>
          </div>
        </div>

        <div class="field">
          <label>验证码</label>
          <div class="captcha-row">
            <div class="input-wrap captcha-input">
              <span class="input-icon">🔡</span>
              <input v-model="form.captchaCode" type="text" placeholder="4位验证码" maxlength="4" @keyup.enter="submit" />
            </div>
            <div class="captcha-box" @click="loadCaptcha" title="点击刷新">
              <div v-if="captchaLoading" class="captcha-loading">...</div>
              <div v-else-if="captchaError" class="captcha-failed">加载失败<br />点此重试</div>
              <img v-else :src="captchaImage" class="captcha-img" alt="验证码" />
            </div>
          </div>
        </div>

        <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

        <button class="btn-login" @click="submit" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>

        <div class="form-footer">
          <span class="link" @click="mode = 'init'">首次使用？初始化密码</span>
          <span class="link-divider">|</span>
          <span class="link" @click="mode = 'register'">没有账号？立即注册</span>
        </div>
      </div>

      <div v-else-if="mode === 'init'" class="form-area">
        <div class="back-row">
          <span class="link" @click="mode = 'login'">← 返回登录</span>
        </div>
        <h2 class="form-title">初始化密码</h2>
        <div class="tip-box">首次使用请在此设置账号密码，账号需已在系统中存在。</div>

        <div class="field">
          <label>账号</label>
          <div class="input-wrap">
            <span class="input-icon">👤</span>
            <input v-model="initForm.username" type="text" placeholder="请输入账号" />
          </div>
        </div>
        <div class="field">
          <label>设置密码</label>
          <div class="input-wrap">
            <span class="input-icon">🔒</span>
            <input v-model="initForm.password" type="password" placeholder="至少 6 位" />
          </div>
        </div>
        <div class="field">
          <label>确认密码</label>
          <div class="input-wrap">
            <span class="input-icon">🔒</span>
            <input v-model="initForm.confirm" type="password" placeholder="再次输入密码" />
          </div>
        </div>

        <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>
        <div v-if="successMsg" class="success-bar">{{ successMsg }}</div>

        <button class="btn-login" @click="submitInit" :disabled="loading">
          {{ loading ? '提交中...' : '确认设置' }}
        </button>
      </div>

      <div v-else-if="mode === 'register'" class="form-area">
        <div class="back-row">
          <span class="link" @click="mode = 'login'">← 返回登录</span>
        </div>
        <h2 class="form-title">注册账号</h2>
        <div class="tip-box">请填写完整信息注册账号，注册成功后可立即登录。</div>

        <div class="field">
          <label>账号 *</label>
          <div class="input-wrap">
            <span class="input-icon">👤</span>
            <input v-model="registerForm.username" type="text" placeholder="登录账号，3-20位字符" />
          </div>
        </div>
        <div class="field">
          <label>姓名 *</label>
          <div class="input-wrap">
            <span class="input-icon">👨</span>
            <input v-model="registerForm.name" type="text" placeholder="真实姓名" />
          </div>
        </div>
        <div class="field">
          <label>邮箱 *</label>
          <div class="input-wrap">
            <span class="input-icon">📧</span>
            <input v-model="registerForm.email" type="email" placeholder="邮箱地址" />
          </div>
        </div>
        <div class="field">
          <label>密码 *</label>
          <div class="input-wrap">
            <span class="input-icon">🔒</span>
            <input v-model="registerForm.password" type="password" placeholder="至少 6 位" />
          </div>
        </div>

        <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>
        <div v-if="successMsg" class="success-bar">{{ successMsg }}</div>

        <button class="btn-login" @click="submitRegister" :disabled="loading">
          {{ loading ? '注册中...' : '立即注册' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getCaptcha, login, initPassword, register } from '../api/auth.js';

const router = useRouter();
const mode = ref('login');
const showPwd = ref(false);
const loading = ref(false);
const captchaLoading = ref(false);
const captchaImage = ref('');
const captchaId = ref('');
const errorMsg = ref('');
const successMsg = ref('');

const form = ref({ username: '', password: '', captchaCode: '' });
const initForm = ref({ username: '', password: '', confirm: '' });
const registerForm = ref({ username: '', name: '', email: '', password: '' });

const captchaError = ref('');

async function loadCaptcha() {
  captchaLoading.value = true;
  try {
    const res = await getCaptcha();
    if (res.data.success) {
      captchaImage.value = res.data.data.image || '';
      captchaId.value = res.data.data.id;
    }
    captchaError.value = '';
  } catch (e) {
    // 验证码拿不到就等于**登不进去**，而界面上只是一张空白图 ——
    // 用户会以为是自己网络卡了，反复点击刷新。
    console.error('验证码加载失败', e);
    captchaError.value = '验证码加载失败，请点击图片重试';
  }
  captchaLoading.value = false;
}

async function submit() {
  errorMsg.value = '';
  if (!form.value.username.trim()) { errorMsg.value = '请输入账号'; return; }
  if (!form.value.password) { errorMsg.value = '请输入密码'; return; }
  if (!form.value.captchaCode) { errorMsg.value = '请输入验证码'; return; }
  loading.value = true;
  try {
    const res = await login({
      username: form.value.username.trim(),
      password: form.value.password,
      captchaId: captchaId.value,
      captchaCode: form.value.captchaCode.toLowerCase().trim(),
    });
    if (res.data.success) {
      sessionStorage.setItem('api_token', res.data.data.token);
      sessionStorage.setItem('current_user', JSON.stringify(res.data.data.user));
      router.push('/dashboard');
    } else {
      errorMsg.value = res.data.message || '登录失败';
      loadCaptcha();
    }
  } catch (e) {
    const respData = e.response?.data || {};
    const code = respData.code;
    if (code === 'NEED_INIT_PASSWORD') {
      initForm.value.username = form.value.username.trim();
      mode.value = 'init';
      errorMsg.value = '';
    } else {
      errorMsg.value = respData.message || '登录失败，请稍后重试';
      loadCaptcha();
    }
  }
  loading.value = false;
}

async function submitInit() {
  errorMsg.value = '';
  successMsg.value = '';
  if (!initForm.value.username.trim()) { errorMsg.value = '请输入账号'; return; }
  if (initForm.value.password.length < 6) { errorMsg.value = '密码至少 6 位'; return; }
  if (initForm.value.password !== initForm.value.confirm) { errorMsg.value = '两次密码不一致'; return; }
  loading.value = true;
  try {
    const res = await initPassword({ username: initForm.value.username.trim(), password: initForm.value.password });
    if (res.data.success) {
      successMsg.value = '密码设置成功，请登录！';
      setTimeout(() => { mode.value = 'login'; successMsg.value = ''; }, 1800);
    } else {
      errorMsg.value = res.data.message || '操作失败';
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.message || '操作失败';
  }
  loading.value = false;
}

async function submitRegister() {
  errorMsg.value = '';
  successMsg.value = '';
  
  if (!registerForm.value.username.trim()) { errorMsg.value = '请输入账号'; return; }
  if (registerForm.value.username.trim().length < 3 || registerForm.value.username.trim().length > 20) {
    errorMsg.value = '账号长度为 3-20 位'; return;
  }
  if (!registerForm.value.name.trim()) { errorMsg.value = '请输入姓名'; return; }
  if (!registerForm.value.email.trim()) { errorMsg.value = '请输入邮箱'; return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registerForm.value.email.trim())) {
    errorMsg.value = '邮箱格式不正确'; return;
  }
  if (registerForm.value.password.length < 6) { errorMsg.value = '密码至少 6 位'; return; }
  
  loading.value = true;
  try {
    const res = await register({
      username: registerForm.value.username.trim(),
      name: registerForm.value.name.trim(),
      email: registerForm.value.email.trim(),
      password: registerForm.value.password
    });
    if (res.data.success) {
      successMsg.value = '注册成功，即将跳转登录...';
      setTimeout(() => { 
        mode.value = 'login'; 
        successMsg.value = ''; 
        registerForm.value = { username: '', name: '', email: '', password: '' }; 
      }, 1800);
    } else {
      errorMsg.value = res.data.message || '注册失败';
    }
  } catch (e) {
    errorMsg.value = e.response?.data?.message || '注册失败，请稍后重试';
  }
  loading.value = false;
}

onMounted(() => {
  const token = sessionStorage.getItem('api_token');
  if (token) router.push('/dashboard');
  else loadCaptcha();
});
</script>

<style scoped>
.login-root {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-app);
  position: relative;
  overflow: hidden;
}
.bg-layer { position: absolute; inset: 0; pointer-events: none; }
.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.18;
  animation: blob-float 20s ease-in-out infinite;
}
@keyframes blob-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -30px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.9); }
}
.blob1 { width: 500px; height: 500px; background: var(--primary); top: -120px; left: -100px; }
.blob2 { width: 400px; height: 400px; background: var(--violet); bottom: -100px; right: -80px; animation-delay: -7s; }
.blob3 { width: 300px; height: 300px; background: var(--info); top: 40%; left: 40%; animation-delay: -14s; }

.login-card {
  position: relative;
  z-index: 1;
  width: 420px;
  max-width: 95vw;
  background: var(--tint-2);
  border: 1px solid var(--tint-4);
  border-radius: 24px;
  padding: 36px 36px 32px;
  backdrop-filter: blur(20px);
  box-shadow: 0 24px 80px color-mix(in srgb, var(--shadow-color) 50%, transparent);
}
.card-logo {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--tint-3);
}
@keyframes card-float { 
  0%, 100% { transform: translateY(0); } 
  50% { transform: translateY(-8px); } 
}
.logo-icon { font-size: 36px; }
.logo-title { font-size: 18px; font-weight: 800; color: var(--text-primary); letter-spacing: 0.5px; }
.logo-sub { font-size: 11px; color: var(--text-muted); margin-top: 3px; }

.form-title { font-size: 20px; font-weight: 700; color: var(--text-secondary); margin-bottom: 22px; }
.back-row { margin-bottom: 10px; }
.tip-box { background: color-mix(in srgb, var(--primary) 8%, transparent); border: 1px solid color-mix(in srgb, var(--primary) 20%, transparent); border-radius: 8px; padding: 10px 14px; font-size: 12px; color: var(--primary-hover); margin-bottom: 18px; line-height: 1.6; }

.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.field label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); }

.input-wrap {
  display: flex;
  align-items: center;
  background: var(--bg-surface-2);
  border: 1px solid var(--tint-3);
  border-radius: 10px;
  padding: 0 14px;
  transition: all .3s ease;
  position: relative;
}
.input-wrap:focus-within { 
  border-color: color-mix(in srgb, var(--primary) 40%, transparent);
  background: var(--bg-surface);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 8%, transparent);
}
.input-icon { font-size: 15px; margin-right: 8px; flex-shrink: 0; }
.input-wrap input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 14px;
  padding: 11px 0;
}
.input-wrap input::placeholder { color: var(--text-muted); }
.eye-btn { font-size: 16px; cursor: pointer; padding: 2px 4px; flex-shrink: 0; opacity: .7; }
.eye-btn:hover { opacity: 1; }

.captcha-row { display: flex; gap: 10px; align-items: stretch; }
.captcha-input { flex: 1; }
.captcha-box {
  width: 120px;
  height: 44px;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--tint-4);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-inset);
  transition: border-color .2s;
}
.captcha-box:hover { border-color: color-mix(in srgb, var(--primary) 40%, transparent); }
.captcha-loading { color: var(--text-muted); font-size: 13px; }
.captcha-failed {
  color: var(--danger-text); font-size: 11px; line-height: 1.4;
  text-align: center; cursor: pointer;
}
.captcha-img { width: 120px; height: 40px; display: block; object-fit: cover; }
.captcha-img { width: 120px; height: 40px; }

.error-bar {
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--danger) 25%, transparent);
  color: var(--danger-text);
  border-radius: 8px;
  padding: 9px 14px;
  font-size: 13px;
  margin-bottom: 14px;
}
.success-bar {
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--success) 25%, transparent);
  color: var(--success-text);
  border-radius: 8px;
  padding: 9px 14px;
  font-size: 13px;
  margin-bottom: 14px;
}

.btn-login {
  width: 100%;
  padding: 13px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, var(--primary), var(--violet));
  color: var(--text-on-color);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity .2s, transform .1s;
  margin-bottom: 14px;
  letter-spacing: 2px;
}
.btn-login:hover:not(:disabled) { opacity: .9; }
.btn-login:active:not(:disabled) { transform: scale(.98); }
.btn-login:disabled { opacity: .5; cursor: not-allowed; }

.form-footer { 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  gap: 8px; 
}
.link { 
  font-size: 12px; 
  color: var(--text-muted); 
  cursor: pointer; 
  transition: color .2s; 
  white-space: nowrap; 
}
.link:hover { color: var(--primary-hover); }
.link-divider { font-size: 12px; color: var(--text-muted); }

@media (max-width: 480px) {
  .login-card { padding: 28px 20px 24px; border-radius: 18px; }
  .login-title { font-size: 20px; }
  .input-wrap input { font-size: 16px; }
  .captcha-box { width: 100px; }
  .captcha-img { width: 100px; }
}
</style>
