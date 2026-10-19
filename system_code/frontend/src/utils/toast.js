/**
 * Toast 提示工具
 */

let toastContainer = null;
let toastId = 0;

function ensureContainer() {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    toastContainer.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 999999;
      pointer-events: none;
    `;
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

function createToastElement(message, type = 'info') {
  const toast = document.createElement('div');
  const id = `toast-${toastId++}`;
  toast.id = id;
  
  const icons = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ'
  };

  const colors = {
    success: '#10b981',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6'
  };

  toast.style.cssText = `
    background: white;
    color: #1e293b;
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 10px;
    box-shadow: var(--shadow-md);
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 280px;
    max-width: 400px;
    pointer-events: auto;
    animation: slideIn 0.3s ease-out;
    border-left: 4px solid ${colors[type] || colors.info};
  `;

  toast.innerHTML = `
    <span style="
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: ${colors[type] || colors.info};
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      flex-shrink: 0;
    ">${icons[type] || icons.info}</span>
    <span style="flex: 1; font-size: 14px; line-height: 1.5;">${message}</span>
  `;

  // 添加动画样式
  if (!document.getElementById('toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
      @keyframes slideIn {
        from {
          transform: translateX(100%);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
      @keyframes slideOut {
        from {
          transform: translateX(0);
          opacity: 1;
        }
        to {
          transform: translateX(100%);
          opacity: 0;
        }
      }
    `;
    document.head.appendChild(style);
  }

  return toast;
}

export function showToast(message, type = 'info', duration = 3000) {
  const container = ensureContainer();
  const toast = createToastElement(message, type);
  
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, duration);
}

export function showSuccess(message, duration) {
  showToast(message, 'success', duration);
}

export function showError(message, duration) {
  showToast(message, 'error', duration);
}

export function showWarning(message, duration) {
  showToast(message, 'warning', duration);
}

export function showInfo(message, duration) {
  showToast(message, 'info', duration);
}
