<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>视频检测</h1>
        <p class="page-sub">上传本地视频，沿用摄像头同一套姿态估计、情绪识别和 D-S 融合检测逻辑。</p>
      </div>
      <div class="status-chip" :class="detecting ? 'online' : 'offline'">
        <span class="dot"></span>{{ detecting ? '检测中' : '未检测' }}
      </div>
    </div>

    <div class="detect-layout grid-main-fixed">
      <section class="video-panel">
        <div class="upload-card" :class="{ hasVideo: videoUrl }">
          <input ref="fileInputRef" type="file" accept="video/*" hidden @change="onFileChange" />
          <button class="upload-btn" @click="fileInputRef?.click()">选择视频</button>
          <div class="upload-info">
            <div class="file-name">{{ selectedFile?.name || '未选择视频' }}</div>
            <div class="file-tip">支持浏览器可播放的 mp4 / mov / webm 等格式，视频不会整体上传到后端。</div>
          </div>
        </div>

        <div class="video-card">
          <div class="video-wrap stage" ref="videoWrapRef">
            <div v-if="!videoUrl" class="placeholder">
              <div class="ph-icon">🎬</div>
              <div class="ph-title">请先选择一个本地视频</div>
              <div class="ph-sub">系统会从视频当前画面抽帧并调用真实 AI 检测接口</div>
            </div>
            <video
              v-show="videoUrl"
              ref="videoRef"
              :src="videoUrl"
              class="video-el"
              controls
              playsinline
              @loadedmetadata="onVideoReady"
              @play="onVideoPlay"
              @pause="onVideoPause"
              @ended="stopDetection"
            ></video>
            <canvas ref="canvasRef" class="det-canvas"></canvas>
          </div>

          <div class="ctrl-bar">
            <div class="ctrl-left">
              <span class="cam-label">{{ selectedFile?.name || '本地视频检测' }}</span>
              <span v-if="latestDetection" class="risk-pill" :style="{ color: riskColor(currentRisk), background: riskBg(currentRisk) }">{{ currentRisk }}</span>
            </div>
            <div class="ctrl-right">
              <label class="interval-label">
                间隔
                <select v-model.number="intervalMs" :disabled="detecting">
                  <option :value="0">不限速（最跟手）</option>
                  <option :value="33">≈30 帧/秒</option>
                  <option :value="100">10 帧/秒</option>
                  <option :value="200">5 帧/秒</option>
                  <option :value="1000">1 帧/秒（省负载）</option>
                </select>
              </label>
              <button class="btn-primary" :disabled="!videoUrl || detecting" @click="startDetection">开始检测</button>
              <button class="btn-secondary" :disabled="!detecting" @click="pauseDetection">暂停检测</button>
              <button class="btn-stop" :disabled="!videoUrl" @click="clearVideo">清空</button>
            </div>
          </div>
        </div>
      </section>

      <aside class="result-panel">
        <div class="result-card">
          <div class="card-title">当前检测结果</div>
          <div v-if="inferenceError" class="error-box">{{ inferenceError }}</div>
          <div v-else-if="!latestDetection" class="empty-box">等待视频帧检测结果...</div>
          <div v-else class="result-grid">
            <div class="metric">
              <span>风险等级</span>
              <strong :style="{ color: riskColor(currentRisk) }">{{ currentRisk }}</strong>
            </div>
            <div class="metric">
              <span>姿态状态</span>
              <strong>{{ postureText }}</strong>
            </div>
            <div class="metric">
              <span>跌倒评分</span>
              <strong>{{ pct(latestDetection.fallScore) }}</strong>
            </div>
            <div class="metric">
              <span>痛苦评分</span>
              <strong>{{ pct(latestDetection.painScore) }}</strong>
            </div>
            <div class="metric wide">
              <span>表情</span>
              <strong>{{ expressionText }}</strong>
            </div>
          </div>
        </div>

        <div class="result-card history-card">
          <!-- 这一栏是**实时流**：检测过程中每帧都会往前面插一条。
               分页在这里没有意义 —— 每来一帧页码就失效，而且用户真正关心的
               只有"最新几帧"。改为固定保留最近 N 条（见 pushHistory 里的上限），
               列表内部滚动即可。
               （此前 <Pagination> 还被写在了 v-for 里面，于是 12 条历史
                 渲染出了 12 条分页条。） -->
          <div class="card-title">
            最近检测帧
            <span class="card-sub">最新 {{ HISTORY_LIMIT }} 帧 · 实时滚动</span>
          </div>
          <div v-if="!history.length" class="empty-box">暂无记录</div>
          <div v-else class="history-list">
            <div v-for="item in history" :key="item.id" class="history-item">
              <div class="history-top">
                <span class="time">{{ item.time }}</span>
                <span class="risk-pill" :style="{ color: riskColor(item.risk), background: riskBg(item.risk) }">{{ item.risk }}</span>
              </div>
              <div class="history-main">{{ item.posture }} · 跌倒 {{ item.fall }} · 痛苦 {{ item.pain }}</div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { detectYOLO } from '../api/python.js';
import { riskBg, riskColor, showToast } from '../utils/index.js';
import { resolveVar } from '../utils/themeColors.js';
// 与实时监控页共用同一套骨架/人脸框绘制与坐标映射
import { getVideoDisplayMapper, drawSkeleton, drawFaceBox, drawInfoPanel }
  from '../utils/overlay.js';

const fileInputRef = ref(null);
const videoWrapRef = ref(null);
const videoRef = ref(null);
const canvasRef = ref(null);
const selectedFile = ref(null);
const videoUrl = ref('');
const latestDetection = ref(null);
const inferenceError = ref('');
const detecting = ref(false);
// 发送间隔。原来是 500ms（每秒只发 2 帧），而叠加层画的是**上一次**检测结果，
// 于是骨架框每秒只跳 2 次，看起来完全跟不上人。
//
// 发送间隔。0 = 不限速（只受"在途帧数"约束，跑满服务端能力）。
//
// 原来是 500ms（每秒只发 2 帧），而叠加层画的是**上一次**检测结果，
// 于是骨架框每秒只跳 2 次，看起来完全跟不上人。
// 后端实测：整条 process_frame 中位 48ms（约 20 FPS），时序跌倒模型只占 2.2ms ——
// 算力有充足余量，定时器限速纯属浪费。现在默认不限速。
const intervalMs = ref(0);
// 在途帧上限 = 1。
//
// 实测（scripts/eval/bench_frame_stream.py）：吞吐被服务端卡在约 14 帧/秒，
// 在途 1 的往返延迟中位 52ms、在途 2 是 99ms、在途 3 是 150ms —— 而吞吐
// 14.2 / 14.3 / 14.2 几乎不变。**加深队列只买到延迟，买不到帧率**，
// 因为在途再深，服务端仍是一帧一帧串行处理。
// 所以取 1：同样流畅，延迟减半，告警也更快。
const MAX_INFLIGHT = 1;
// 呈现延迟（毫秒）。画面按"视频时间 - 该延迟"取结果来画。
//
// 这是解决"跟不跟得上"的关键：一个结果描述的是它**发出时**那一帧的内容，
// 回来时人早已移动，把它贴到当前画面上必然滞后一个往返延迟。反过来，
// 让画面晚 250ms 呈现（录制视频完全无所谓），结果就总是**先于**画面到位，
// 骨架便永远画在它真正属于的那一帧上 —— 既没有滞后，也不需要"猜"未来位置。
const PRESENT_DELAY_MS = 250;
// 结果缓冲：按视频时间戳索引，用于在 60fps 的 rAF 上做时间插值
let frameBuffer = [];
let lastDrawT = -1;
const HISTORY_LIMIT = 12;
const history = ref([]);
let detectionTimer = null;
let overlayFrame = null;
let frameSocket = null;
let inFlight = 0;
let inferenceBusy = false;
let historySeq = 0;
let lastDetectionAt = 0;

const fallInfo = computed(() => latestDetection.value?.fallInfo || {});
const currentRisk = computed(() => String(latestDetection.value?.prediction?.riskLevel || latestDetection.value?.alertLevel || 'NORMAL').toUpperCase());
// 姿态状态只保留二分类：跌倒 / 正常（正常包含站立、坐下、弯腰等安全姿态）。
// 服务端已把时序模型判定为倒地时的 postureType 纠正成 lying，这里据此映射。
const postureText = computed(() => {
  const info = fallInfo.value;
  const posture = info.postureType || info.posture_type || info.status || 'unknown';
  return (posture === 'fall_like' || posture === 'lying') ? '跌倒' : '正常';
});
const expressionText = computed(() => {
  const expressions = latestDetection.value?.expressions || [];
  if (!expressions.length) return '暂无稳定表情';
  return expressions.map(e => `${e.className || e.class_name}:${Number(e.confidence || 0).toFixed(2)}`).join(' | ');
});

function pct(value) {
  return `${(Number(value || 0) * 100).toFixed(0)}%`;
}

function onFileChange(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  clearDetectionState();
  selectedFile.value = file;
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value);
  videoUrl.value = URL.createObjectURL(file);
  nextTick(syncCanvas);
}

function onVideoReady() {
  syncCanvas();
  drawOverlay();
}

function onVideoPlay() {
  if (detecting.value) return;
}

function onVideoPause() {
  if (detecting.value && videoRef.value?.ended) stopDetection();
}

function syncCanvas() {
  const video = videoRef.value;
  const canvas = canvasRef.value;
  const wrap = videoWrapRef.value;
  if (!canvas || !wrap) return;
  const rect = wrap.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(rect.width));
  canvas.height = Math.max(1, Math.round(rect.height));
  if (video?.videoWidth && video?.videoHeight) {
    drawOverlay();
  }
}

function frameCanvas() {
  const video = videoRef.value;
  if (!video || !video.videoWidth || !video.videoHeight) return null;
  const c = document.createElement('canvas');
  // 发送分辨率与质量与改动前**完全一致**（960 / q0.75），只换传输方式，
  // 所以送进模型的像素不变，精度不受任何影响。
  const maxSide = 960;
  const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight));
  c.width = Math.max(1, Math.round(video.videoWidth * scale));
  c.height = Math.max(1, Math.round(video.videoHeight * scale));
  const ctx = c.getContext('2d');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(video, 0, 0, c.width, c.height);
  return c;
}

/**
 * 抓一帧，编码成 [8 字节小端 float64 视频时间戳][JPEG 字节]。
 *
 * 用异步 toBlob 而不是同步 toDataURL：toDataURL 在 960×540 上要占住主线程
 * 十几到几十毫秒，期间 rAF 停摆 —— 画面和骨架一起卡，这是"跟随慢"里最直观的
 * 一部分。toBlob 把编码交出去，主线程不被堵。同时省掉 base64（体积 ×4/3）
 * 和 JSON 包装。
 */
function captureFrameBinary() {
  const video = videoRef.value;
  const c = frameCanvas();
  if (!video || !c) return Promise.resolve(null);
  const vt = video.currentTime;
  return new Promise((resolve) => {
    c.toBlob(async (blob) => {
      if (!blob) return resolve(null);
      try {
        const jpeg = new Uint8Array(await blob.arrayBuffer());
        const out = new Uint8Array(8 + jpeg.length);
        new DataView(out.buffer).setFloat64(0, vt, true);
        out.set(jpeg, 8);
        resolve(out);
      } catch (e) {
        resolve(null);
      }
    }, 'image/jpeg', 0.75);
  });
}

// HTTP 降级通道仍用 base64（那个接口吃 JSON）
function captureFrameBase64() {
  const c = frameCanvas();
  return c ? c.toDataURL('image/jpeg', 0.75) : '';
}

function pushFrameResult(vt, data) {
  frameBuffer.push({ vt, data });
  frameBuffer.sort((a, b) => a.vt - b.vt);
  const cutoff = vt - 2;
  while (frameBuffer.length && frameBuffer[0].vt < cutoff) frameBuffer.shift();
}

function lerpArray(a, b, k) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return b ?? a;
  return a.map((v, i) => {
    if (Array.isArray(v)) return lerpArray(v, b[i], k);
    return (typeof v === 'number' && typeof b[i] === 'number') ? v + (b[i] - v) * k : b[i];
  });
}

/** 相邻两条结果之间线性插值 —— 骨架在 60fps 上连续移动，而不是每 50ms 跳一次。 */
function interpResult(a, b, k) {
  const out = { ...b };
  if (Array.isArray(a.keypoints) && Array.isArray(b.keypoints)) {
    out.keypoints = lerpArray(a.keypoints, b.keypoints, k);
  }
  if (Array.isArray(a.faceBox) && Array.isArray(b.faceBox)) {
    out.faceBox = lerpArray(a.faceBox, b.faceBox, k);
  }
  if (Array.isArray(a.persons) && Array.isArray(b.persons) && a.persons.length === b.persons.length) {
    out.persons = b.persons.map((p, i) => (
      Array.isArray(a.persons[i]?.keypoints) && Array.isArray(p?.keypoints)
        ? { ...p, keypoints: lerpArray(a.persons[i].keypoints, p.keypoints, k) }
        : p));
  }
  if (Array.isArray(a.faces) && Array.isArray(b.faces) && a.faces.length === b.faces.length) {
    out.faces = b.faces.map((f, i) => (
      Array.isArray(a.faces[i]?.faceBox) && Array.isArray(f?.faceBox)
        ? { ...f, faceBox: lerpArray(a.faces[i].faceBox, f.faceBox, k) }
        : f));
  }
  return out;
}

/** 取"视频第 t 秒"对应的结果（落在两条之间就插值）。 */
function pickFrameResult(t) {
  if (!frameBuffer.length) return null;
  if (frameBuffer.length === 1 || t <= frameBuffer[0].vt) return frameBuffer[0].data;
  const last = frameBuffer[frameBuffer.length - 1];
  if (t >= last.vt) return last.data;
  for (let i = frameBuffer.length - 2; i >= 0; i -= 1) {
    const a = frameBuffer[i];
    const b = frameBuffer[i + 1];
    if (t >= a.vt && t <= b.vt) {
      const k = b.vt > a.vt ? (t - a.vt) / (b.vt - a.vt) : 0;
      return interpResult(a.data, b.data, k);
    }
  }
  return last.data;
}

function wsBaseUrl() {
  const apiBase = import.meta.env.VITE_API_BASE_URL || window.location.origin;
  const base = apiBase.startsWith('http') ? apiBase : window.location.origin;
  return base.replace(/^http/, 'ws').replace(/\/$/, '') + '/api';
}

function handleSocketMessage(payload) {
  if (!payload?.success) {
    inFlight = Math.max(0, inFlight - 1);
    if (payload?.message) inferenceError.value = payload.message;
    if (detecting.value) sendFrameToSocket();
    return;
  }
  if (payload.event === 'connected') return;
  if (payload.event !== 'result' || !payload.data) return;
  inFlight = Math.max(0, inFlight - 1);
  const data = payload.data;
  // vt = 服务端回传的"这一帧取自视频第几秒"。有这个数才能把结果按时间轴对齐，
  // 而不是把它当成"最新状态"贴到已经走远的画面上。
  const vt = Number(data.vt);
  pushFrameResult(Number.isFinite(vt) ? vt : (videoRef.value?.currentTime || 0), data);
  latestDetection.value = data;      // 侧栏与历史列表用最新一条
  inferenceError.value = '';
  appendHistory(data, vt);
  // 立刻补一帧，把在途数顶满 —— 不再等 intervalMs 定时器。
  // 队列深度由 MAX_INFLIGHT 限住，所以补得越快只是越贴近服务端上限，不会堆积。
  if (detecting.value) sendFrameToSocket();
}

function closeFrameSocket() {
  inFlight = 0;
  if (frameSocket) { frameSocket.close(); frameSocket = null; }
}

function startFrameSocket() {
  closeFrameSocket();
  const token = sessionStorage.getItem('api_token') || '';
  if (!token) return false;
  frameSocket = new WebSocket(`${wsBaseUrl()}/yolo/frame-stream?token=${encodeURIComponent(token)}`);
  frameSocket.onmessage = (event) => {
    try { handleSocketMessage(JSON.parse(event.data)); } catch (err) {
      console.warn('检测结果帧解析失败，已跳过该帧', err);
    }
  };
  frameSocket.onerror = () => {
    inferenceError.value = '视频 WebSocket 连接失败，已尝试 HTTP 降级';
    closeFrameSocket();
    if (detecting.value) detectionTimer = setTimeout(runDetectionOnce, 0);
  };
  frameSocket.onopen = () => {
    inFlight = 0;
    frameBuffer = [];
    for (let i = 0; i < MAX_INFLIGHT; i += 1) sendFrameToSocket();
  };
  frameSocket.onclose = () => {
    inFlight = 0;
    frameSocket = null;
    if (detecting.value && !inferenceBusy) detectionTimer = setTimeout(runDetectionOnce, 0);
  };
  return true;
}

function sendFrameToSocket() {
  if (!detecting.value) return;
  const video = videoRef.value;
  if (!video || video.paused || video.ended) { pauseDetection(); return; }
  if (!frameSocket || frameSocket.readyState !== WebSocket.OPEN) {
    detectionTimer = setTimeout(runDetectionOnce, 0);
    return;
  }
  // 在途上限 = 队列深度上限 = 延迟上限。到顶就等回包时再补，不做无谓的堆帧。
  if (inFlight >= MAX_INFLIGHT) return;
  // intervalMs = 0 表示不限速；> 0 时作为可选的人工限速（省电/降负载）
  const now = Date.now();
  if (intervalMs.value > 0 && lastDetectionAt && now - lastDetectionAt < intervalMs.value) {
    clearTimeout(detectionTimer);
    detectionTimer = setTimeout(sendFrameToSocket, intervalMs.value - (now - lastDetectionAt));
    return;
  }
  inFlight += 1;
  lastDetectionAt = now;
  captureFrameBinary().then((buf) => {
    if (!buf || !detecting.value) { inFlight = Math.max(0, inFlight - 1); return; }
    if (!frameSocket || frameSocket.readyState !== WebSocket.OPEN) {
      inFlight = Math.max(0, inFlight - 1);
      return;
    }
    try {
      frameSocket.send(buf);
    } catch (e) {
      inFlight = Math.max(0, inFlight - 1);
    }
  });
}

function startOverlayLoop() {
  if (overlayFrame) return;
  const tick = () => {
    drawOverlay();
    overlayFrame = requestAnimationFrame(tick);
  };
  overlayFrame = requestAnimationFrame(tick);
}

function stopOverlayLoop() {
  if (overlayFrame) cancelAnimationFrame(overlayFrame);
  overlayFrame = null;
}

async function startDetection() {
  if (!videoUrl.value || detecting.value) return;
  detecting.value = true;
  inferenceError.value = '';
  lastDetectionAt = 0;
  inFlight = 0;
  frameBuffer = [];
  lastDrawT = -1;
  startOverlayLoop();
  if (videoRef.value?.paused) {
    try {
      await videoRef.value.play();
    } catch (e) {
      // 自动播放被策略拦下（没有用户手势）时画面是黑的，而界面上
      // 一切"正常"——用户只会以为视频流断了。明确提示他点一下播放。
      console.warn('视频自动播放被浏览器拒绝', e?.name);
      showToast('浏览器阻止了自动播放，请点击画面开始播放', 'warning');
    }
  }
  if (!startFrameSocket()) detectionTimer = setTimeout(runDetectionOnce, 0);
}

function pauseDetection() {
  detecting.value = false;
  frameBuffer = [];
  lastDrawT = -1;
  if (detectionTimer) { clearTimeout(detectionTimer); detectionTimer = null; }
  closeFrameSocket();
  stopOverlayLoop();
}

function stopDetection() {
  pauseDetection();
}

function clearVideo() {
  pauseDetection();
  if (videoRef.value) {
    videoRef.value.pause();
    videoRef.value.removeAttribute('src');
    videoRef.value.load();
  }
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value);
  videoUrl.value = '';
  selectedFile.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
  clearDetectionState();
  clearCanvas();
}

function clearDetectionState() {
  latestDetection.value = null;
  inferenceError.value = '';
  history.value = [];
  historySeq = 0;
}

async function runDetectionOnce() {
  if (!detecting.value || inferenceBusy) return;
  const video = videoRef.value;
  if (!video || video.paused || video.ended) { pauseDetection(); return; }
  const now = Date.now();
  if (lastDetectionAt && now - lastDetectionAt < intervalMs.value) {
    detectionTimer = setTimeout(runDetectionOnce, intervalMs.value - (now - lastDetectionAt));
    return;
  }
  const imageBase64 = captureFrameBase64();
  if (!imageBase64) {
    detectionTimer = setTimeout(runDetectionOnce, 100);
    return;
  }
  inferenceBusy = true;
  const startedAt = performance.now();
  try {
    lastDetectionAt = Date.now();
    const res = await detectYOLO({ imageBase64 });
    if (res.data?.success) {
      latestDetection.value = res.data.data;
      inferenceError.value = '';
      appendHistory(res.data.data);
      drawOverlay();
    }
  } catch (e) {
    inferenceError.value = e.response?.data?.message || e.response?.data?.detail || '视频帧检测失败';
    drawOverlay();
  } finally {
    inferenceBusy = false;
    if (detecting.value) {
      const elapsed = performance.now() - startedAt;
      const nextDelay = Math.max(intervalMs.value, Math.round(elapsed * 1.2));
      detectionTimer = setTimeout(runDetectionOnce, nextDelay);
    }
  }
}

function appendHistory(data, vt) {
  const info = data.fallInfo || {};
  const risk = String(data?.prediction?.riskLevel || data?.alertLevel || 'NORMAL').toUpperCase();
  const rawPosture = info.postureType || info.posture_type || info.status || 'unknown';
  history.value.unshift({
    id: ++historySeq,
    time: formatVideoTime(Number.isFinite(Number(vt)) ? Number(vt) : (videoRef.value?.currentTime || 0)),
    risk,
    posture: (rawPosture === 'fall_like' || rawPosture === 'lying') ? '跌倒' : '正常',
    fall: pct(data.fallScore),
    pain: pct(data.painScore),
  });
  if (history.value.length > HISTORY_LIMIT) history.value.pop();
}

function formatVideoTime(seconds) {
  const s = Math.floor(seconds || 0);
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function drawOverlay() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const video = videoRef.value;
  let result = latestDetection.value;
  if (detecting.value && video && frameBuffer.length) {
    const t = video.currentTime - PRESENT_DELAY_MS / 1000;
    // 拖动进度条/循环播放会让时间倒跳，此时旧结果全部作废，否则会画出不属于
    // 当前画面的骨架（看起来就是"骨架乱飘"）。
    if (lastDrawT >= 0 && t < lastDrawT - 0.3) frameBuffer = [];
    lastDrawT = t;
    result = pickFrameResult(t) || result;
  }
  if (result) drawDetectionResult(ctx, canvas.width, canvas.height, result);
  else drawStatus(ctx, canvas.width, canvas.height);
}

function clearCanvas() {
  const canvas = canvasRef.value;
  const ctx = canvas?.getContext('2d');
  if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
}




function drawDetectionResult(ctx, w, h, result) {
  // 画布不认识 CSS 变量，所以这里必须解析成真实色值（utils/themeColors.js 带缓存，
  // 并在主题切换时失效）。原来这里写死了第 5 套等级配色，其中 LOW 是黄绿色
  // （#84cc16），与告警中心的蓝、总览的绿都不一样。
  // 简化后这里只画骨架 + 人脸框，不再需要风险色。
  const srcW = Number(result.imageWidth || 0) || w;
  const srcH = Number(result.imageHeight || 0) || h;
  const map = getVideoDisplayMapper(srcW, srcH, w, h, 'contain');
  const persons = Array.isArray(result.persons) && result.persons.length
    ? result.persons
    : [{ keypoints: result.keypoints, fallInfo: result.fallInfo }];
  persons.forEach((person, index) => drawSkeleton(ctx, map, person.keypoints || [], index, person));

  const faces = Array.isArray(result.faces) && result.faces.length
    ? result.faces
    : (Array.isArray(result.faceBox) ? [{ faceBox: result.faceBox, expressions: result.expressions || [], method: result.faceMethod }] : []);
  // 人脸框几何统一用顶层的 result.faceBox —— 它是服务端做过**跨方法 EMA 平滑**的。
  // result.faces[].faceBox 是 suoding 检测器的原始框，没经过平滑：方法一在
  // suoding(keypoint 原始)↔keypoint(平滑)之间切换，框就跟着跳。所以这里强制
  // 用平滑后的框覆盖，表情标签仍从 faces[] 里取。
  if (faces.length && Array.isArray(result.faceBox)) {
    faces[0] = { ...faces[0], faceBox: result.faceBox };
  }
  faces.forEach((face, index) => drawFaceBox(ctx, map, face, index));

  // 简化：视频上只保留骨架 + 人脸框 + 顶部的风险色带（risk 已在底部控制栏与右侧面板展示）。
  // 原来左上角还有一块信息面板（D-S 融合风险/姿态/状态/证据/信念/原因），
  // 对使用者而言信息过载，已去掉。
}

function drawStatus(ctx, w, h) {
  drawInfoPanel(ctx, 10, 10, Math.min(360, w - 20), 70,
    // 画布不能直接吃 var()，用运行时解析（原来写死的 #dc2626 正是亮色 --danger 的值）
    inferenceError.value ? resolveVar('--danger') : resolveVar('--primary'),
    '上传视频检测',
    [(inferenceError.value || '等待开始检测...')]);
}


onMounted(() => {
  window.addEventListener('resize', syncCanvas);
  document.addEventListener('fullscreenchange', syncCanvas);
  document.addEventListener('webkitfullscreenchange', syncCanvas);
});

onUnmounted(() => {
  pauseDetection();
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value);
  window.removeEventListener('resize', syncCanvas);
  document.removeEventListener('fullscreenchange', syncCanvas);
  document.removeEventListener('webkitfullscreenchange', syncCanvas);
});
</script>

<style scoped>

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 13px;
  border: 1px solid var(--tint-3);
  background: var(--bg-elevated);
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--tint-4);
}

.status-chip.online .dot { background: var(--level-normal); box-shadow: 0 0 10px var(--level-normal); }
.status-chip.offline .dot { background: var(--tint-4); }

/* 列定义交给契约（.grid-main-fixed）；这里只声明侧栏宽度，
   不再整段覆盖 grid-template-columns —— 那样会让同名的类在不同页面表现不同。 */
.detect-layout { --side-w: 360px; }

.video-panel,
.result-panel {
  min-width: 0;
}

.upload-card,
.video-card,
.result-card {
  border: 1px solid var(--tint-3);
  background: var(--bg-surface);
  border-radius: 18px;
  box-shadow: var(--shadow-lg);
}

.upload-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  margin-bottom: 14px;
}

.upload-btn,
.btn-primary,
.btn-secondary,
.btn-stop {
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  color: var(--text-on-color);
  cursor: pointer;
  font-weight: 700;
}

.upload-btn,
.btn-primary { background: linear-gradient(135deg, var(--primary-active), var(--level-urgent)); }
.btn-secondary { background: var(--tint-3); border: 1px solid var(--border-strong); }
.btn-stop { background: color-mix(in srgb, var(--danger) 12%, transparent); border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent); }
button:disabled { opacity: .45; cursor: not-allowed; }

.upload-info { min-width: 0; }
.file-name { font-weight: 800; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-tip { color: var(--text-tertiary); font-size: 13px; margin-top: 4px; }

.video-card { overflow: hidden; }

.video-el,
.det-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.video-el {
  /* contain：视频检测要看到完整画面（不像监控那样裁切），
     留边部分用舞台底色而不是纯黑，与 .stage 保持一致。 */
  object-fit: contain;
  background: transparent;
}

.det-canvas {
  pointer-events: none;
  z-index: 2;
}

.placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-tertiary);
  z-index: 1;
}

.ph-icon { font-size: 46px; margin-bottom: 10px; }
.ph-title { color: var(--text-secondary); font-size: 18px; font-weight: 800; }
.ph-sub { margin-top: 6px; font-size: 13px; }

.ctrl-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border-top: 1px solid var(--tint-3);
}

.ctrl-left,
.ctrl-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cam-label { color: var(--text-secondary); font-weight: 700; }
.interval-label { display: inline-flex; align-items: center; gap: 6px; color: var(--text-tertiary); font-size: 13px; }
.interval-label select {
  background: var(--bg-surface);
  color: var(--text-secondary);
  border: 1px solid var(--tint-4);
  border-radius: 10px;
  padding: 8px;
}

.result-panel { display: flex; flex-direction: column; gap: 14px; }
.result-card { padding: 16px; }
.card-title { font-weight: 900; color: var(--text-primary); margin-bottom: 12px; }
.empty-box,
.error-box {
  border-radius: 14px;
  padding: 18px;
  text-align: center;
  color: var(--text-tertiary);
  background: var(--tint-1);
}
.error-box { color: var(--danger-text); }

.result-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.metric {
  padding: 12px;
  border-radius: 14px;
  background: var(--tint-1);
  border: 1px solid var(--tint-3);
}
.metric.wide { grid-column: 1 / -1; }
.metric span { display: block; color: var(--text-tertiary); font-size: 12px; margin-bottom: 6px; }
.metric strong { color: var(--text-primary); font-size: 14px; word-break: break-word; }

.risk-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 900;
}

.history-card { flex: 1; min-height: 0; }
.card-sub { margin-left: 8px; font-size: 11px; font-weight: 400; color: var(--text-muted); }
.history-list { display: flex; flex-direction: column; gap: 10px; max-height: 520px; overflow: auto; padding-right: 4px; }
.history-item {
  padding: 12px;
  border-radius: 14px;
  background: var(--tint-1);
  border: 1px solid var(--tint-3);
}
.history-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.time { color: var(--primary); font-weight: 800; }
.history-main { color: var(--text-secondary); font-size: 13px; margin-bottom: 5px; }

@media (max-width: 1180px) {
  .detect-layout { grid-template-columns: 1fr; }
  .result-panel { display: grid; grid-template-columns: 1fr 1fr; }
}

@media (max-width: 760px) {
  .page-video-detect { padding: 16px; }
  .page-header,
  .upload-card,
  .ctrl-bar { align-items: stretch; flex-direction: column; }
  .result-panel { display: flex; }
  .ctrl-right { width: 100%; }
  .btn-primary,
  .btn-secondary,
  .btn-stop { flex: 1; }
}
</style>
