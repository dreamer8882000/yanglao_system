import { onMounted, onUnmounted } from 'vue';
import { ref } from 'vue';

const MAX_RETRIES = 8;

export function useSSE({ onAlert, onConfirmed, onError } = {}) {
  let es = null;
  let reconnectTimer = null;
  let retries = 0;
  const status = ref('disconnected');

  function connect() {
    if (retries >= MAX_RETRIES) {
      onError?.();
      return;
    }

    const token = sessionStorage.getItem('api_token') || '';
    if (!token) return;

    const base = (import.meta.env.VITE_API_BASE_URL || '') + '/api';
    es = new EventSource(`${base}/alerts/stream?token=${encodeURIComponent(token)}`);

    es.addEventListener('connected', () => { retries = 0; status.value = 'connected'; });

    es.addEventListener('alert', (e) => {
      try { onAlert?.(JSON.parse(e.data)); } catch (err) {
        // 静默丢弃一个畸形的推送帧，表现是"告警没弹出来"——而且不留任何痕迹。
        // SSE 的排查成本本来就高（长连接、没有请求日志），至少要留下原始载荷。
        console.error('SSE alert 事件解析失败', err, e.data);
      }
    });

    es.addEventListener('confirmed', (e) => {
      try { onConfirmed?.(JSON.parse(e.data)); } catch (err) {
        console.error('SSE confirmed 事件解析失败', err, e.data);
      }
    });

    es.addEventListener('ping', () => {});

    es.onerror = () => {
      es?.close();
      es = null;
      status.value = 'disconnected';
      onError?.();
      if (retries < MAX_RETRIES) {
        const delay = Math.min(2000 * Math.pow(1.5, retries++), 30000);
        reconnectTimer = setTimeout(connect, delay);
      }
    };
  }

  function disconnect() {
    clearTimeout(reconnectTimer);
    es?.close();
    es = null;
    status.value = 'disconnected';
    retries = MAX_RETRIES; // 阻止后续重连
  }

  onMounted(connect);
  onUnmounted(disconnect);
  return { disconnect, status };
}
