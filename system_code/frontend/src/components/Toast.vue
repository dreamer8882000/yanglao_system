<template>
  <Transition name="toast">
    <div v-if="visible" :class="['toast', `toast-${type}`]">
      <div class="toast-icon">
        <svg v-if="type === 'success'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 6L9 17l-5-5"/>
        </svg>
        <svg v-else-if="type === 'error'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 18L18 6M6 6l12 12"/>
        </svg>
        <svg v-else-if="type === 'warning'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <div class="toast-message">{{ message }}</div>
    </div>
  </Transition>
</template>

<script setup>
import { ref } from 'vue';

const visible = ref(false);
const message = ref('');
const type = ref('success');
let timer = null;

const show = (msg, msgType = 'success', duration = 3000) => {
  message.value = msg;
  type.value = msgType;
  visible.value = true;

  if (timer) {
    clearTimeout(timer);
  }

  timer = setTimeout(() => {
    visible.value = false;
    timer = null;
  }, duration);
};

defineExpose({ show });
</script>

<style scoped>
.toast {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  background: var(--tint-5);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  box-shadow: 0 8px 32px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  max-width: 90%;
  min-width: 280px;
  font-size: 15px;
  font-weight: 500;
  animation: slideDown 0.3s ease-out;
}

.toast-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
}

.toast-icon svg {
  width: 100%;
  height: 100%;
}

.toast-message {
  flex: 1;
  color: var(--bg-surface-2);
  line-height: 1.5;
}

.toast-success {
  border-left: 4px solid var(--success);
}

.toast-success .toast-icon {
  color: var(--success);
}

.toast-error {
  border-left: 4px solid var(--danger);
}

.toast-error .toast-icon {
  color: var(--danger);
}

.toast-warning {
  border-left: 4px solid var(--warning);
}

.toast-warning .toast-icon {
  color: var(--warning);
}

.toast-info {
  border-left: 4px solid var(--primary);
}

.toast-info .toast-icon {
  color: var(--primary);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

@media (max-width: 768px) {
  .toast {
    top: 60px;
    min-width: auto;
    width: calc(100% - 32px);
    font-size: 14px;
    padding: 12px 16px;
  }

  .toast-icon {
    width: 20px;
    height: 20px;
  }
}
</style>
