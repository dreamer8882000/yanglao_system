<template>
  <transition name="confirm-fade">
    <div v-if="show" class="confirm-mask" @click.self="cancel">
      <div class="confirm-box" :class="type">
        <div class="confirm-icon">{{ iconMap[type] }}</div>
        <div class="confirm-title">{{ title }}</div>
        <div v-if="message" class="confirm-message">{{ message }}</div>
        <div class="confirm-actions">
          <button class="confirm-btn btn-cancel" @click="cancel">{{ cancelText }}</button>
          <button class="confirm-btn btn-confirm" :class="type" @click="confirm" :disabled="loading">
            {{ loading ? '处理中...' : confirmText }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>

defineProps({
  show: { type: Boolean, default: false },
  type: { type: String, default: 'warning' },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  loading: { type: Boolean, default: false },
});

const emit = defineEmits(['confirm', 'cancel']);

const iconMap = {
  info: 'ℹ️',
  success: '✅',
  warning: '⚠️',
  danger: '🚨',
};

function confirm() {
  emit('confirm');
}

function cancel() {
  emit('cancel');
}
</script>

<style scoped>
.confirm-mask {
  position: fixed;
  inset: 0;
  background: var(--bg-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(4px);
}

.confirm-box {
  background: var(--bg-surface-2);
  border: 1px solid var(--tint-4);
  border-radius: 16px;
  padding: 24px;
  min-width: 320px;
  max-width: 420px;
  box-shadow: 0 24px 64px color-mix(in srgb, var(--shadow-color) 60%, transparent);
  animation: confirm-bounce 0.3s ease;
}

@keyframes confirm-bounce {
  0% {
    opacity: 0;
    transform: scale(0.9) translateY(-10px);
  }
  60% {
    transform: scale(1.02) translateY(0);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.confirm-icon {
  font-size: 48px;
  text-align: center;
  margin-bottom: 16px;
}

.confirm-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  text-align: center;
  margin-bottom: 8px;
}

.confirm-message {
  font-size: 14px;
  color: var(--text-tertiary);
  text-align: center;
  margin-bottom: 24px;
  line-height: 1.6;
}

.confirm-actions {
  display: flex;
  gap: 10px;
}

.confirm-btn {
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  background: var(--tint-2);
  color: var(--text-tertiary);
  border: 1px solid var(--tint-4);
}

.btn-cancel:hover {
  background: var(--tint-4);
  color: var(--text-secondary);
}

.btn-confirm {
  color: var(--text-on-color);
}

.btn-confirm.info {
  background: linear-gradient(135deg, var(--primary), var(--primary-active));
  box-shadow: 0 4px 12px color-mix(in srgb, var(--primary) 30%, transparent);
}

.btn-confirm.success {
  background: linear-gradient(135deg, var(--success), var(--success-text));
  box-shadow: 0 4px 12px color-mix(in srgb, var(--success) 30%, transparent);
}

.btn-confirm.warning {
  background: linear-gradient(135deg, var(--warning), var(--warning-text));
  box-shadow: 0 4px 12px color-mix(in srgb, var(--warning) 30%, transparent);
}

.btn-confirm.danger {
  background: linear-gradient(135deg, var(--danger), var(--danger-text));
  box-shadow: 0 4px 12px color-mix(in srgb, var(--danger) 30%, transparent);
}

.btn-confirm:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px color-mix(in srgb, var(--shadow-color) 40%, transparent);
}

.btn-confirm:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.2s;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}

@media (max-width: 480px) {
  .confirm-box {
    min-width: 0;
    max-width: 90vw;
    padding: 20px;
  }

  .confirm-actions {
    flex-direction: column;
  }

  .confirm-btn {
    width: 100%;
    padding: 14px 20px;
  }
}
</style>
