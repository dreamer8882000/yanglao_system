<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal-box qr-modal">
      <div class="modal-header">
        <h3>🏥 床头二维码</h3>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>
      <div class="modal-body">
        <div class="qr-info">
          <div class="elder-name">{{ elder.name }}</div>
          <div class="elder-meta">{{ elder.roomNo }}室 · {{ elder.age }}岁</div>
        </div>
        <div class="qr-container">
          <canvas ref="qrCanvas"></canvas>
        </div>
        <div class="qr-tips">
          <div>👆 扫描此码完成巡查记录</div>
          <div class="tip-sub">护士扫码后自动记录巡查时间和位置</div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="downloadQR">下载二维码</button>
          <button class="btn-primary" @click="printQR">打印二维码</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import QRCode from 'qrcode';

const props = defineProps({
  elder: { type: Object, required: true }
});

defineEmits(['close']);

const qrCanvas = ref(null);

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, s => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[s]));
}

onMounted(async () => {
  if (!qrCanvas.value) return;
  
  const qrData = JSON.stringify({
    type: 'patrol',
    elderId: props.elder.id,
    elderName: props.elder.name,
    roomNo: props.elder.roomNo
  });
  
  await QRCode.toCanvas(qrCanvas.value, qrData, {
    width: 280,
    margin: 2,
    color: {
      dark: '#1e293b',
      light: '#ffffff'
    }
  });
});

function downloadQR() {
  if (!qrCanvas.value) return;
  const link = document.createElement('a');
  link.download = `巡查二维码-${props.elder.name}-${props.elder.roomNo}室.png`;
  link.href = qrCanvas.value.toDataURL();
  link.click();
}

function printQR() {
  if (!qrCanvas.value) return;
  const printWindow = window.open('', '_blank');
  if (!printWindow) return;
  printWindow.opener = null;
  printWindow.document.write(`
    <html>
      <head>
        <title>打印二维码 - ${esc(props.elder.name)}</title>
        <style>
          body { margin: 0; padding: 40px; text-align: center; font-family: sans-serif; }
          .info { margin-bottom: 20px; }
          .name { font-size: 24px; font-weight: bold; margin-bottom: 8px; }
          .meta { font-size: 16px; color: var(--text-tertiary); }
          canvas { display: block; margin: 20px auto; border: 1px solid var(--text-secondary); }
          .tips { margin-top: 20px; font-size: 14px; color: var(--text-tertiary); }
        </style>
      </head>
      <body>
        <div class="info">
          <div class="name">${esc(props.elder.name)}</div>
          <div class="meta">${esc(props.elder.roomNo)}室 · ${esc(props.elder.age)}岁</div>
        </div>
        <img src="${qrCanvas.value.toDataURL()}" />
        <div class="tips">护士扫描此码完成巡查记录</div>
      </body>
    </html>
  `);
  printWindow.document.close();
  setTimeout(() => {
    printWindow.print();
    printWindow.close();
  }, 250);
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: var(--bg-overlay);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.qr-modal {
  background: linear-gradient(135deg, var(--text-primary) 0%, var(--bg-surface-2) 100%);
  border: 1px solid var(--tint-4);
  border-radius: 16px;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 20px 60px color-mix(in srgb, var(--shadow-color) 50%, transparent);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--tint-3);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
}

.close-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--tint-4);
  background: var(--tint-2);
  color: var(--text-tertiary);
  border-radius: 8px;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: var(--tint-4);
  color: var(--text-primary);
}

.modal-body {
  padding: 24px;
}

.qr-info {
  text-align: center;
  margin-bottom: 20px;
}

.elder-name {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.elder-meta {
  font-size: 14px;
  color: var(--text-tertiary);
}

.qr-container {
  background: #ffffff;
  padding: 20px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px color-mix(in srgb, var(--shadow-color) 20%, transparent);
}

.qr-container canvas {
  display: block;
}

.qr-tips {
  text-align: center;
  margin-bottom: 24px;
}

.qr-tips > div:first-child {
  font-size: 15px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.tip-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.modal-actions {
  display: flex;
  gap: 12px;
}

.btn-secondary,
.btn-primary {
  flex: 1;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-secondary {
  background: var(--tint-3);
  color: var(--text-secondary);
  border: 1px solid var(--tint-4);
}

.btn-secondary:hover {
  background: var(--tint-4);
  color: var(--text-primary);
}

.btn-primary {
  background: linear-gradient(135deg, var(--primary), var(--violet));
  color: #ffffff;
}

.btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px color-mix(in srgb, var(--primary) 30%, transparent);
}

@media (max-width: 768px) {
  .qr-modal {
    max-width: 100%;
  }
  
  .qr-container {
    padding: 16px;
  }
  
  .modal-actions {
    flex-direction: column;
  }
}
</style>
