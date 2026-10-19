/**
 * 全局确认对话框工具
 */
import { createApp } from 'vue';
import ConfirmDialog from '../components/ConfirmDialog.vue';

/**
 * 显示确认对话框
 */
export function showConfirm(options) {
  return new Promise((resolve) => {
    const container = document.createElement('div');
    document.body.appendChild(container);

    const app = createApp(ConfirmDialog, {
      ...options,
      show: true,
      onConfirm: () => {
        cleanup();
        resolve(true);
      },
      onCancel: () => {
        cleanup();
        resolve(false);
      },
    });

    const instance = app.mount(container);

    function cleanup() {
      setTimeout(() => {
        app.unmount();
        document.body.removeChild(container);
      }, 300);
    }
  });
}

/**
 * 快捷方法：警告确认
 */
export function confirmWarning(message, title = '确认操作') {
  return showConfirm({
    title,
    message,
    type: 'warning',
    confirmText: '确认',
    cancelText: '取消',
  });
}

/**
 * 快捷方法：危险操作确认
 */
export function confirmDanger(message, title = '危险操作') {
  return showConfirm({
    title,
    message,
    type: 'danger',
    confirmText: '确认删除',
    cancelText: '取消',
  });
}
