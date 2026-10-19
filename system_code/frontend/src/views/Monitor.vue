<template>
  <div class="page">

    <!-- ══ 页头 ══ -->
    <div class="page-header">
      <div class="header-left">
        <h1>实时监控</h1>
        <div class="status-chip" :class="isActive ? 'online' : 'offline'">
          <span class="dot"></span>{{ isActive ? '监控中' : '未开启' }}
        </div>
      </div>
      <span class="clock">{{ currentTime }}</span>
    </div>

    <!-- ══ 主布局 ══ -->
    <div class="monitor-layout grid-main-fixed">

      <!-- ── 左：视频区 ── -->
      <div class="video-section">

        <!-- 摄像头选择栏 -->
        <div class="cam-bar">
          <div class="cam-bar-inner">
            <div class="cam-chip local-chip" :class="{ active: activeSrc === 'local' }" @click="selectLocal">
              <span class="chip-icon">🖥️</span>
              <div class="chip-body">
                <div class="chip-name">本地摄像头</div>
                <div class="chip-sub">浏览器调用</div>
              </div>
              <span class="chip-dot" :class="activeSrc === 'local' && localActive ? 'on' : 'idle'"></span>
            </div>

            <div class="cam-divider"></div>

            <div v-if="camerasError" class="cam-empty cam-empty-error">{{ camerasError }}</div>
            <div v-else-if="!cameras.length" class="cam-empty">暂无已注册设备</div>
            <div v-for="cam in cameras" :key="cam.id"
              class="cam-chip"
              :class="{ active: activeSrc === cam.id, offline: cam.status !== 1 }"
              @click="selectCam(cam)">
              <span class="chip-icon">{{ typeIcon(cam.sourceType) }}</span>
              <div class="chip-body">
                <div class="chip-name">{{ cam.name }}</div>
                <div class="chip-sub">{{ cam.roomNo }}室 · {{ typeLabel(cam.sourceType) }}</div>
              </div>
              <span class="chip-dot" :class="cam.status === 1 ? 'on' : 'off'"></span>
            </div>
          </div>
        </div>

        <!-- 视频播放卡片 -->
        <div class="video-card">
          <div class="video-wrap stage" ref="videoWrapRef">

            <!-- 空状态 -->
            <div v-if="viewState === 'idle'" class="placeholder">
              <div class="ph-icon">📹</div>
              <div class="ph-title">请在上方选择摄像头</div>
              <div class="ph-sub">支持本地摄像头 / HLS / MJPEG / RTSP / MP4</div>
              <div class="ph-tip">
                <strong>机位提示</strong>：请优先使用侧视机位（与地面平行、略高）。
                实测天花板俯视机位下 76% 的画面帧无法提取人体关键点，跌倒只能判为"疑似"。
              </div>
              <div class="ph-tip">
                <strong>用手机当摄像头</strong>：macOS 的「连续互通相机」可把 iPhone 直接
                作为电脑摄像头使用 —— 在 iPhone 上开启「设置 → 通用 → 隔空播放与连续互通 →
                连续互通相机」，回到本页点「本地摄像头」，设备下拉框里就会出现
                “iPhone 的摄像头”。手机架在侧视位置即可当作真实监控机位检测。
              </div>
            </div>

            <!-- 权限请求中 -->
            <div v-else-if="viewState === 'local-requesting'" class="placeholder">
              <div class="ph-icon spin">⏳</div>
              <div class="ph-title">正在请求摄像头权限...</div>
              <div class="ph-sub">请在浏览器弹窗中点击「允许」</div>
            </div>

            <!-- 本地错误 -->
            <div v-else-if="viewState === 'local-error'" class="vid-error">
              <div class="ph-icon">⚠️</div>
              <div class="ph-title">{{ localError }}</div>
              <div class="ph-sub">请检查摄像头权限设置后重试</div>
              <button class="btn-retry" @click="startLocal">重试</button>
            </div>

            <!-- 流错误 -->
            <div v-else-if="viewState === 'stream-error'" class="vid-error">
              <div class="ph-icon">⚠️</div>
              <div class="ph-title">{{ streamError }}</div>
              <button class="btn-retry" @click="retry">重试</button>
            </div>

            <!-- RTSP 提示 -->
            <div v-else-if="viewState === 'rtsp'" class="rtsp-notice">
              <div class="ph-icon">📡</div>
              <div class="ph-title">RTSP 流已配置</div>
              <div class="ph-sub">浏览器不支持直接播放 RTSP，建议通过后端 FFmpeg 转码为 HLS 后播放。</div>
              <div class="rtsp-url">{{ currentUrl }}</div>
            </div>

            <!-- 本地 video -->
            <video
              ref="localVideoRef"
              v-show="viewState === 'local-active'"
              autoplay muted playsinline webkit-playsinline="true"
              class="video-el"
              @playing="onLocalPlaying"
              @error="onLocalVideoError"
            ></video>

            <!-- 流媒体 video -->
            <video
              ref="streamVideoRef"
              v-show="viewState === 'stream-active' && (currentType === 'hls' || currentType === 'mp4')"
              autoplay muted playsinline controls
              class="video-el"
              @error="onVideoError"
              @canplay="onStreamCanPlay"
            ></video>

            <!-- MJPEG -->
            <img
              ref="mjpegRef"
              v-show="viewState === 'stream-active' && currentType === 'mjpeg'"
              class="video-el"
              @error="onVideoError"
              @load="onMjpegLoad"
              alt="mjpeg"
            />

            <!-- YOLOv8 检测结果 canvas 叠加层 -->
            <canvas ref="canvasRef" class="det-canvas"></canvas>

            <!-- LIVE 标识 -->
            <div v-if="viewState === 'local-active' || viewState === 'stream-active'" class="live-badge">
              <span class="live-dot"></span>LIVE
            </div>
            <div v-else-if="viewState === 'rtsp'" class="live-badge">
              <span class="live-dot"></span>AI
            </div>

            <!-- 全屏 -->
            <button
              v-if="isFullscreenSupported && (viewState === 'local-active' || viewState === 'stream-active' || viewState === 'rtsp')"
              class="fullscreen-btn"
              @click="toggleFullscreen"
              title="全屏"
            >⛶</button>
          </div>

          <!-- 控制栏 -->
          <div class="ctrl-bar">
            <div class="ctrl-left">
              <span v-if="activeSrc === 'local'" class="cam-label">🖥️ 本地摄像头</span>
              <span v-else-if="currentCam" class="cam-label">{{ typeIcon(currentCam.sourceType) }} {{ currentCam.name }} · {{ currentCam.roomNo }}室</span>
              <span v-else class="cam-label cam-label--dim">选择摄像头开始监控</span>
            </div>
            <div class="ctrl-right">
              <select
                v-if="activeSrc === 'local' && localDevices.length > 1"
                v-model="localDeviceId"
                class="device-sel"
                @change="switchLocalDevice"
              >
                <option v-for="d in localDevices" :key="d.deviceId" :value="d.deviceId">
                  {{ d.label || '摄像头 ' + (localDevices.indexOf(d) + 1) }}
                </option>
              </select>
              <button v-if="activeSrc !== null" class="btn-stop" @click="stop">⏹ 停止</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 右：统计+告警 ── -->
      <div class="right-panel">
        <!-- 总览数字读不出来时每个格子都会显示「-」，光看数字分不清
             "今天真的是 0 条"还是"接口挂了"。所以在这里明说。 -->
        <div v-if="dashboardError" class="panel-empty panel-empty-error">{{ dashboardError }}</div>
        <div class="stats-grid">
          <div class="stat-card" v-for="s in statDefs" :key="s.key">
            <div class="stat-icon" :style="{ background: s.bg }">{{ s.icon }}</div>
            <div class="stat-info">
              <div class="stat-value" :style="{ color: s.color }">{{ dashboardData[s.key] ?? '-' }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </div>

        <!-- ══ 实时证据卡：与「告警中心」同一套证据语言 ══ -->
        <div class="evidence-card">
          <div class="ev-head">
            <span class="card-title">检测证据</span>
            <span v-if="detection" class="level-tag" :style="levelTagStyle">{{ detection.alertLevel }}</span>
          </div>

          <div v-if="!detection" class="ev-empty">等待检测结果…</div>

          <template v-else>
            <div class="ev-row">
              <span class="ev-k">姿态</span>
              <span class="ev-v">{{ postureLabel(detection.fallInfo?.postureType) }}</span>
            </div>
            <div class="ev-row">
              <span class="ev-k">证据来源</span>
              <span class="ev-v">{{ modeLabel(detection.fallInfo?.evidenceMode) }}</span>
            </div>
            <div class="ev-row">
              <span class="ev-k">跌倒状态</span>
              <span class="ev-v">{{ stateLabel(detection.fallInfo?.fallState) }}</span>
            </div>

            <div class="ev-metrics">
              <div class="ev-metric">
                <div class="ev-m-label">跌倒证据</div>
                <div class="ev-bar"><span :style="{ width: pctW(detection.fallScore), background: 'var(--level-high)' }"></span></div>
                <div class="ev-m-num">{{ fmt2(detection.fallScore) }}</div>
              </div>
              <div class="ev-metric">
                <div class="ev-m-label">痛苦证据</div>
                <div class="ev-bar"><span :style="{ width: pctW(detection.painScore), background: 'var(--level-medium)' }"></span></div>
                <div class="ev-m-num">{{ fmt2(detection.painScore) }}</div>
              </div>
            </div>

            <div class="ev-belief">
              <span class="ev-k">融合信念</span>
              <span class="ev-b">m(F) {{ fmt2(detection.fallInfo?.beliefFall) }}</span>
              <span class="ev-b">m(Θ) {{ fmt2(detection.fallInfo?.beliefUnknown) }}</span>
            </div>

            <p class="ev-note" v-if="detection.fallInfo?.reason">{{ detection.fallInfo.reason }}</p>
            <p class="ev-note muted">
              看不见脸时，痛苦记为「证据未知」，不会当作「无痛苦」。
            </p>
          </template>
        </div>

        <div class="alert-list-card">
          <div class="alert-list-header">
            <span class="card-title">🔔 最近告警</span>
            <router-link to="/alerts" class="view-all">查看全部 →</router-link>
          </div>
          <div v-if="alertsLoading" class="list-empty">加载中...</div>
          <div v-else-if="!recentAlerts.length" class="list-empty">暂无告警记录</div>
          <div v-else class="alert-items">
            <div v-for="alert in recentAlerts" :key="alert.id" class="alert-item">
              <div class="alert-meta">
                <span class="level-tag" :style="{ background: riskBg(alert.riskLevel), color: riskColor(alert.riskLevel) }">{{ alert.riskLevel }}</span>
                <span class="alert-elder">{{ alert.elderName || '未识别' }}</span>
                <span class="alert-room" v-if="alert.roomNo">{{ alert.roomNo }}室</span>
              </div>
              <div class="alert-info">
                <span class="alert-conf">{{ alert.confidence }}%</span>
                <span class="alert-time">{{ formatTime(alert.alertTime) }}</span>
              </div>
              <div class="alert-action">
                <button v-if="alert.status === 0" class="btn-confirm-mini" @click="openConfirm(alert)">确认</button>
                <span v-else class="confirmed-text">✓</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══ 告警确认弹窗 ══ -->
    <div v-if="confirmModal.show" class="modal-mask" @click.self="confirmModal.show = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>确认告警处置</h3>
          <button class="close-btn" @click="confirmModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-row">
            <span class="level-tag" :style="{ background: riskBg(confirmModal.alert?.riskLevel), color: riskColor(confirmModal.alert?.riskLevel) }">{{ confirmModal.alert?.riskLevel }}</span>
            <span class="detail-text">{{ confirmModal.alert?.elderName }} · {{ confirmModal.alert?.roomNo }}室 · {{ confirmModal.alert?.confidence }}%</span>
          </div>
          <div class="field-group">
            <label>处置备注 <span class="req">*</span></label>
            <textarea v-model="confirmModal.notes" placeholder="请填写处置说明…" maxlength="200" rows="4"></textarea>
            <div class="char-count">{{ confirmModal.notes.length }}/200</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="confirmModal.show = false">取消</button>
          <button class="btn-primary" @click="submitConfirm" :disabled="confirmModal.loading">
            {{ confirmModal.loading ? '提交中...' : '确认处置' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { getDashboard, getRecentAlerts, confirmAlert } from '../api/alerts.js';
import { getCameraList, heartbeatCamera } from '../api/cameras.js';
import { detectYOLO } from '../api/python.js';
import { testCameraInference } from '../api/yolo.js';
import { formatTime, riskColor, riskBg, showToast } from '../utils/index.js';
import { LEVELS, levelColor } from '../utils/levelColors.js';
// 骨架 / 人脸框 / 坐标映射 抽到共享模块，与视频检测页共用同一套实现
import { getVideoDisplayMapper, drawSkeleton as drawSkeletonBase,
         drawFaceBox as drawFaceBoxBase, personColor, headColor } from '../utils/overlay.js';
// 画布不认识 CSS 变量，需要运行时解析（见 utils/themeColors.js）
import { resolveVar } from '../utils/themeColors.js';

function isInferenceEnabled(cam = currentCam.value) {
  if (!cam) return true;
  let models = cam.yoloModels || [];
  if (typeof models === 'string') {
    try { models = JSON.parse(models); } catch { models = [models]; }
  }
  if (!Array.isArray(models)) models = [];
  return cam.yoloEnabled !== 0 && cam.yoloModel !== 'none' && !models.includes('none');
}

// ── 时钟 ──
const currentTime = ref('');
let clockTimer = null;
function updateClock() {
  currentTime.value = new Date().toLocaleString('zh-CN', { hour12: false });
}

// ── 数据 ──
const cameras = ref([]);
const dashboardData = ref({ todayTotal: 0, todayHigh: 0, pending: 0, elderCount: 0 });
const recentAlerts = ref([]);
const alertsLoading = ref(false);
const confirmModal = ref({ show: false, alert: null, notes: '', loading: false });

// 统计卡的色值只引用 token：原来写死的 4 个前景色里有 2 个
// （#fb923c #4ade80）在任何主题下都不是 token 值，也就是"无论切到哪个主题
// 都不会变"的颜色。bg 同理：它们是暗色主题下的语义色。
const statDefs = [
  { key: 'todayTotal', label: '今日告警', icon: '📋', color: 'var(--primary)', bg: 'var(--primary-soft)' },
  { key: 'todayHigh',  label: '今日紧急', icon: '🚨', color: 'var(--danger-text)', bg: 'var(--danger-soft)' },
  { key: 'pending',    label: '待处理',   icon: '⏳', color: 'var(--warning-text)', bg: 'var(--warning-soft)' },
  { key: 'elderCount', label: '在档老人', icon: '👴', color: 'var(--success-text)', bg: 'var(--success-soft)' },
];

function typeIcon(t) {
  return { local: '🖥️', hls: '📡', webrtc: '⚡', rtsp: '🔌', mjpeg: '📷', mp4: '🎬' }[t] || '📹';
}
function typeLabel(t) {
  return { local: '本地', hls: 'HLS', webrtc: 'WebRTC', rtsp: 'RTSP', mjpeg: 'MJPEG', mp4: 'MP4' }[t] || (t || '未知');
}

// ── 视图状态机 ──
const viewState = ref('idle');
const isActive = computed(() => viewState.value === 'local-active' || viewState.value === 'stream-active');

// ── DOM refs ──
const videoWrapRef   = ref(null);
const localVideoRef  = ref(null);
const streamVideoRef = ref(null);
const mjpegRef       = ref(null);
const canvasRef      = ref(null);

// ── 当前源 ──
const activeSrc    = ref(null);
const currentCam   = ref(null);
const currentType  = ref('');
const currentUrl   = ref('');
const streamError  = ref('');
const localError   = ref('');

// ── 本地摄像头 ──
const localDevices  = ref([]);
const localDeviceId = ref('');
const localActive   = ref(false);
let   localStream   = null;

// ══════════════════════════════════════════
// Canvas 真实 AI 检测叠加层
// 本地摄像头和可跨域读取的视频画面由前端截帧后调用后端；
// 已注册摄像头也可由后端按 streamUrl 抽帧推理。
// ══════════════════════════════════════════
let inferenceTimer = null;
let overlayFrame = null;
let inferenceBusy = false;
let streamSocket = null;
let frameSocket = null;
let wsFrameTimer = null;
// 在途帧上限 = 1。
//
// 实测（scripts/eval/bench_frame_stream.py）：吞吐被服务端串行处理卡在约
// 14 帧/秒，而往返延迟在途 1 是 52ms、在途 2 是 99ms、在途 3 是 150ms ——
// 吞吐几乎不变。**加深队列只买到延迟，买不到帧率。** 所以取 1。
const MAX_INFLIGHT = 1;
let inFlightFrames = 0;
let socketAwaitingResult = false;
let alertSyncAt = 0;
// 帧间隔下限。这里曾经是 300ms，成为整条链路的实际瓶颈：
//   后端实测单帧 80ms（→12.5 FPS 能力），前端 300ms 下限却把实际帧率
//   压到 ~2.6 FPS，用户感知就是"卡"。真正的节流由下面的自适应退避负责
//   （下一帧延迟 = max(本值, 本次往返耗时 × 1.2)），所以下限只需要
//   小到不成为瓶颈即可 —— 取 60ms，让后端成为限制项。
const inferenceIntervalMs = 60;
// 送往前端的帧边长与 JPEG 质量。姿态模型无论收到多大都会缩放到
// imgsz=640，所以超过该尺寸的部分不影响姿态精度；但人脸裁剪发生在
// 收到帧之后，边长过小会让表情分支的输入更糊。1280→960 是两者的折中。
const FRAME_MAX_SIDE = 960;
const FRAME_JPEG_QUALITY = 0.82;
const latestDetection = ref(null);
const detection = computed(() => latestDetection.value);

const POSTURE_LABEL = {
  fall_like: '横卧(跌倒样)', lying: '躺卧', sitting: '坐姿', standing: '站立',
  bending: '弯腰', resting: '静卧', unknown: '姿态不明', insufficient_body: '身体关键点不足',
  face_closeup: '人脸特写',
};
const MODE_LABEL = {
  pose_expression: '姿态 + 表情', pose_only: '仅姿态（未定位人脸）',
  expression_only: '仅表情（身体不足）', no_evidence: '无有效证据',
};
const STATE_LABEL = {
  normal: '正常', suspected_fall: '疑似跌倒', confirmed_fall: '已确认跌倒',
  occluded_after_fall: '跌倒后被遮挡', recovered: '已恢复', resting: '静卧',
};
// 等级配色不再在页面里重复定义 —— 唯一来源是 utils/levelColors.js
// （它只返回 var(--level-x)，色值本身在 tokens.css 里按主题定义）。
const LEVEL_COLOR = Object.fromEntries(LEVELS.map((l) => [l, levelColor(l)]));

const levelTagStyle = computed(() => ({
  background: LEVEL_COLOR[String(detection.value?.alertLevel || '').toUpperCase()] || 'var(--text-muted)',
  color: 'var(--text-on-color)',
}));

function postureLabel(v) { return POSTURE_LABEL[v] || '未知'; }
function modeLabel(v) { return MODE_LABEL[v] || '未知'; }
function stateLabel(v) { return STATE_LABEL[v] || '未知'; }
function fmt2(v) { return v === null || v === undefined ? '—' : Number(v).toFixed(2); }
function pctW(v) { const n = Math.max(0, Math.min(1, Number(v) || 0)); return `${(n * 100).toFixed(0)}%`; }
const inferenceError = ref('');

function wsBaseUrl() {
  const apiBase = import.meta.env.VITE_API_BASE_URL || window.location.origin;
  const base = apiBase.startsWith('http') ? apiBase : window.location.origin;
  return base.replace(/^http/, 'ws').replace(/\/$/, '') + '/api';
}

function handleStreamResult(payload) {
  if (!payload?.success) {
    inFlightFrames = Math.max(0, inFlightFrames - 1);
    if (payload?.message) inferenceError.value = payload.message;
    if (frameSocket && isInferenceEnabled()) sendFrameToSocket();
    return;
  }
  if (payload.event === 'connected') return;
  if (payload.event !== 'result' || !payload.data) return;
  inFlightFrames = Math.max(0, inFlightFrames - 1);
  // 收到一条就立刻补一条，把在途数顶满 —— 不再等 inferenceIntervalMs 定时器，
  // 速率自然贴着服务端上限走（实测服务端整条链路约 20 FPS）。
  if (frameSocket && isInferenceEnabled()) sendFrameToSocket();
  feedTracks(payload.data);
  latestDetection.value = payload.data;
  inferenceError.value = '';
  const riskLevel = String(payload.data?.prediction?.riskLevel || payload.data?.alertLevel || 'NORMAL').toUpperCase();
  const shouldSyncAlerts = payload.data?.alert || ['LOW', 'MEDIUM', 'HIGH', 'URGENT'].includes(riskLevel);
  const now = Date.now();
  if (shouldSyncAlerts && now - alertSyncAt > 2000) {
    alertSyncAt = now;
    loadAlerts();
    loadDashboard();
  }
  if (frameSocket && isInferenceEnabled()) {
    const latency = Number(payload.data.latencyMs || payload.data.latency_ms || 0);
    scheduleFrameSend(Math.max(inferenceIntervalMs, Math.round(latency * 1.2)));
  }
}

function drawModelOverlay() {
  if (!canvasRef.value) return;
  const canvas = canvasRef.value;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!isInferenceEnabled()) return;
  if (latestDetection.value) drawDetectionResult(ctx, canvas.width, canvas.height, latestDetection.value);
  else drawInferenceStatus(ctx, canvas.width, canvas.height);
}

// ══════════════ 骨架/人脸框的低延迟跟随 ══════════════
// 问题：画布上画的是**上一次推理结果**（约 150–180ms 前），却叠在**当前**视频帧上，
// 所以人一动，骨架就明显落在身后；同时每帧只更新一次（约 6 FPS），看起来是一跳一跳的。
//
// 解法两步：
//   1) One-Euro 滤波器：速度慢时强平滑（去抖动），速度快时自动放宽截止频率（低延迟）。
//      这是交互式跟踪里处理"抖动 vs 延迟"权衡的标准做法，优于固定系数的 EMA。
//   2) 速度外推：用相邻两次推理的位置差估计速度，在 60fps 的 rAF 上把骨架沿运动方向
//      前推，补偿推理延迟；外推量有上限并随时间衰减，避免过冲与"飘走"。
class OneEuroFilter {
  // 参数不是拍脑袋来的，是按"静止噪声不得大于原始测量"这一约束扫出来的：
  // 测试脚本模拟 6FPS 推理 + 60FPS 绘制，对每个参数组合测两项指标 ——
  //   (a) 匀速运动（40px/s，走路级）时绘制值相对真实轨迹的滞后；
  //   (b) 静止 + 关键点噪声 ±3px 时输出位置的标准差。
  // 结果（640 宽画面下的像素）：
  //   beta=0.02 → 滞后 2.3px，噪声 sd 1.38（最稳但跟不上）
  //   beta=0.20 → 滞后 0.7px，噪声 sd 1.78（比原始测量 1.73 还抖，不可接受）
  //   beta=0.12 → 滞后 0.93px，噪声 sd 1.66  ← 取此值
  // 它是在"抖动不比不滤波更差"的前提下滞后最低的一档；相比之下，
  // 不用跟随器时骨架每 160ms 要跳 6.4px。
  constructor(minCutoff = 0.8, beta = 0.12, dCutoff = 1.0) {
    this.minCutoff = minCutoff;
    this.beta = beta;
    this.dCutoff = dCutoff;
    this.xPrev = null;
    this.dxPrev = 0;
  }
  static _alpha(cutoff, dt) {
    const tau = 1 / (2 * Math.PI * cutoff);
    return 1 / (1 + tau / dt);
  }
  filter(x, dt) {
    if (this.xPrev === null) { this.xPrev = x; return x; }
    const d = Math.max(1e-4, dt);
    const dx = (x - this.xPrev) / d;
    const aD = OneEuroFilter._alpha(this.dCutoff, d);
    this.dxPrev = aD * dx + (1 - aD) * this.dxPrev;
    const cutoff = this.minCutoff + this.beta * Math.abs(this.dxPrev);
    const a = OneEuroFilter._alpha(cutoff, d);
    this.xPrev = a * x + (1 - a) * this.xPrev;
    return this.xPrev;
  }
  get velocity() { return this.dxPrev; }
  reset() { this.xPrev = null; this.dxPrev = 0; }
}

// 每个点两条轴各一个滤波器。source 坐标（未映射到画布）上做滤波，
// 这样换相机、改分辨率都不需要重建。
const KP_COUNT = 17;
function makeTrack() {
  return {
    fx: Array.from({ length: KP_COUNT }, () => new OneEuroFilter()),
    fy: Array.from({ length: KP_COUNT }, () => new OneEuroFilter()),
    out: Array.from({ length: KP_COUNT }, () => [0, 0]),
    has: Array.from({ length: KP_COUNT }, () => false),
    t: 0,
    period: 160,        // 观察到的推理间隔，用于限制外推时长
  };
}
const kpTracks = new Map();     // 按人体序号索引
const faceTrack = makeTrack();  // 人脸框复用同一套（4 个角）

function trackOf(map, key) {
  let t = map.get(key);
  if (!t) { t = makeTrack(); map.set(key, t); }
  return t;
}

// 收到新的推理结果时调用：更新滤波器并记录速度
function updateTrack(track, pts, nowMs) {
  const dt = track.t ? (nowMs - track.t) / 1000 : 0;
  if (track.t) track.period = Math.min(400, Math.max(60, nowMs - track.t));
  track.t = nowMs;
  for (let i = 0; i < KP_COUNT; i++) {
    const p = pts && pts[i];
    if (!Array.isArray(p) || !(p[0] > 0) || !(p[1] > 0)) { track.has[i] = false; continue; }
    track.out[i][0] = dt > 0 ? track.fx[i].filter(p[0], dt) : (track.fx[i].xPrev = p[0]);
    track.out[i][1] = dt > 0 ? track.fy[i].filter(p[1], dt) : (track.fy[i].xPrev = p[1]);
    track.has[i] = true;
  }
}

// 每个 rAF 帧调用：返回当前应当绘制的位置（滤波值 + 受限外推）
function sampleTrack(track, nowMs) {
  if (!track.t) return null;
  const ahead = Math.min(nowMs - track.t, track.period * 1.2) / 1000;
  const out = [];
  for (let i = 0; i < KP_COUNT; i++) {
    if (!track.has[i]) { out.push([0, 0]); continue; }
    // 外推量随时间衰减，避免推理结果迟到时骨架越飘越远
    const periodsAhead = track.period > 0 ? ahead / (track.period / 1000) : 0;
    const lead = ahead * Math.pow(0.85, periodsAhead);
    out.push([
      track.out[i][0] + track.fx[i].velocity * lead,
      track.out[i][1] + track.fy[i].velocity * lead,
    ]);
  }
  return out;
}

function resetTracks() {
  kpTracks.clear();
  faceTrack.t = 0;
  faceTrack.has.fill(false);
  faceTrack.fx.forEach(f => f.reset());
  faceTrack.fy.forEach(f => f.reset());
}

// 推理结果到达时喂给滤波器（人体骨架 + 人脸框）
function feedTracks(result) {
  const now = performance.now();
  const persons = Array.isArray(result.persons) && result.persons.length
    ? result.persons
    : [{ keypoints: result.keypoints }];
  persons.forEach((p, i) => {
    if (Array.isArray(p.keypoints) && p.keypoints.length) {
      updateTrack(trackOf(kpTracks, i), p.keypoints, now);
    }
  });
  const faces = Array.isArray(result.faces) && result.faces.length
    ? result.faces
    : (Array.isArray(result.faceBox) ? [{ faceBox: result.faceBox }] : []);
  if (faces.length) {
    // 人脸框几何统一用顶层的 result.faceBox —— 它是服务端做过跨方法 EMA 平滑的；
    // faces[0].faceBox 是 suoding 检测器的原始框，方法切换时会跳。
    const b = (Array.isArray(result.faceBox) ? result.faceBox
      : (faces[0].faceBox || faces[0].face_box));
    if (Array.isArray(b) && b.length === 4) {
      // 把一个矩形塞进 17 点的结构里，只用到前 4 个槽位
      const pts = [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]];
      updateTrack(faceTrack, pts, now);
    }
  }
}

function sampleFaceBox() {
  const s = sampleTrack(faceTrack, performance.now());
  if (!s || !faceTrack.has[0] || !faceTrack.has[2]) return null;
  return [s[0][0], s[0][1], s[2][0], s[2][1]];
}


function kptValid(p) { return Array.isArray(p) && p[0] > 0 && p[1] > 0; }

function drawSkeleton(ctx, map, keypoints, index = 0, person = {}) {
  // 用低延迟跟随后的位置替换原始测量点：滤波器去抖动，速度外推补偿推理延迟，
  // 使骨架在 60fps 的 rAF 上连续移动而不是每 ~160ms 跳一次。
  const followed = sampleTrack(trackOf(kpTracks, index), performance.now());
  if (followed) {
    keypoints = keypoints.map((p, i) => (kptValid(followed[i]) ? followed[i] : p));
  }
  const valid = keypoints.filter(p => Array.isArray(p) && p[0] > 0 && p[1] > 0);
  if (!valid.length) return;
  // 与 overlay.js 共用同一套"人的标识色"，不再各写一份（原来这两处的
  // 多人配色完全不同：一边是 #1d4ed8/#15803d/…，一边是 #60a5fa/#22c55e/…）
  const color = personColor(index);
  const bones = [[0,1],[0,2],[1,3],[2,4],[5,6],[5,7],[7,9],[6,8],[8,10],[5,11],[6,12],[11,12],[11,13],[13,15],[12,14],[14,16]];
  ctx.lineWidth = 2;
  ctx.strokeStyle = color;
  bones.forEach(([a, b]) => {
    const pa = keypoints[a], pb = keypoints[b];
    if (!pa || !pb || pa[0] <= 0 || pa[1] <= 0 || pb[0] <= 0 || pb[1] <= 0) return;
    const [ax, ay] = map.point(pa[0], pa[1]);
    const [bx, by] = map.point(pb[0], pb[1]);
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.stroke();
  });
  keypoints.forEach((p, idx) => {
    if (!Array.isArray(p) || p[0] <= 0 || p[1] <= 0) return;
    const [x, y] = map.point(p[0], p[1]);
    ctx.beginPath();
    ctx.arc(x, y, idx < 5 ? 3 : 4, 0, Math.PI * 2);
    ctx.fillStyle = idx < 5 ? headColor() : color;
    ctx.fill();
  });
  const info = person.fallInfo || person.fall_info || {};
  const bodyBox = info.bodyBox || info.body_box;
  if (Array.isArray(bodyBox) && bodyBox.length === 4) {
    const [x1, y1] = map.point(bodyBox[0], bodyBox[1]);
    const trackId = person.trackId ?? person.track_id ?? info.trackId ?? info.track_id;
    ctx.fillStyle = color;
    ctx.font = 'bold 11px Inter,sans-serif';
    ctx.fillText(trackId ? `PERSON #${trackId}` : `PERSON ${index + 1}`, x1 + 4, Math.max(14, y1 - 4));
  }
}

function drawFaceBox(ctx, map, face, index = 0) {
  let box = face.faceBox || face.face_box;
  if (!Array.isArray(box) || box.length !== 4) return;
  const followedBox = index === 0 ? sampleFaceBox() : null;
  drawFaceBoxBase(ctx, map, { ...face, faceBox: followedBox || box }, index);
}

function drawDetectionResult(ctx, w, h, result) {
  const srcW = Number(result.imageWidth || 0) || w;
  const srcH = Number(result.imageHeight || 0) || h;
  const map = getVideoDisplayMapper(srcW, srcH, w, h, 'cover');
  const persons = Array.isArray(result.persons) && result.persons.length
    ? result.persons
    : [{ keypoints: result.keypoints, fallInfo: result.fallInfo }];
  persons.forEach((person, index) => drawSkeleton(ctx, map, person.keypoints || [], index, person));

  const faces = Array.isArray(result.faces) && result.faces.length
    ? result.faces
    : (Array.isArray(result.faceBox) ? [{ faceBox: result.faceBox, expressions: result.expressions || [], method: result.faceMethod }] : []);
  faces.forEach((face, index) => drawFaceBox(ctx, map, face, index));

  // ── 左上角不再绘制信息面板 ──────────────────────────────────────────
  // 这里原本画了一个深色圆角框（边框色 = 告警等级色，NORMAL 时为绿色 #10b981），
  // 内含 6 行文字：D-S 融合风险 / 姿态·状态·跌倒分 / 证据·质量·情绪·痛苦 /
  // 信念 m(F)·m(Θ)·表情品质·对齐 / 表情 / 原因。
  // 这些内容右栏「当前检测结果」已经完整展示，重复显示既挤占画面，
  // 又让同一数值出现两处、可能不一致。现在视频区只保留画面本身的分析
  // 结果：骨架关键点与人脸框，以及仅在出错时于左下角的一句提示。
  if (inferenceError.value) {
    ctx.fillStyle = resolveVar('--danger-text');
    ctx.font = '12px Inter,sans-serif';
    ctx.fillText(inferenceError.value.slice(0, 48), 12, h - 14);
  }
}

function drawInferenceStatus(ctx, w, h) {
  // 等待结果期间同样不在画面上写字：右栏已显示「等待视频帧检测结果...」。
  // 仅在出错时于左下角提示一句，避免画面被文字遮挡。
  if (inferenceError.value) {
    ctx.fillStyle = resolveVar('--danger-text');
    ctx.font = '12px Inter,sans-serif';
    ctx.fillText(inferenceError.value.slice(0, 48), 12, h - 14);
  }
}

function getActiveVideoElement() {
  if (activeSrc.value === 'local') return localVideoRef.value;
  if (currentType.value === 'hls' || currentType.value === 'mp4') return streamVideoRef.value;
  return null;
}

// 复用同一个离屏 canvas：原先每帧都 document.createElement('canvas') 新建一个，
// 在高频推理下会持续制造可回收垃圾并触发 GC 停顿，表现为画面间歇性顿挫。
let captureCanvas = null;
let captureCtx = null;

function drawCaptureCanvas() {
  const video = getActiveVideoElement();
  if (!video || !video.videoWidth || !video.videoHeight) return null;
  try {
    if (!captureCanvas) {
      captureCanvas = document.createElement('canvas');
      captureCtx = captureCanvas.getContext('2d');
    }
    const c = captureCanvas;
    const ctx = captureCtx;
    const scale = Math.min(1, FRAME_MAX_SIDE / Math.max(video.videoWidth, video.videoHeight));
    const w = Math.max(1, Math.round(video.videoWidth * scale));
    const h = Math.max(1, Math.round(video.videoHeight * scale));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
    ctx.imageSmoothingEnabled = true;
    // 'high' 在每帧缩放到 640 的路径上收益极小，代价却明显；'medium' 足够。
    ctx.imageSmoothingQuality = 'medium';
    ctx.drawImage(video, 0, 0, w, h);
    return { canvas: c, video };
  } catch {
    return null;
  }
}

/**
 * 抓一帧 → [8 字节小端 float64 视频时间戳][JPEG]。
 *
 * 分辨率与 JPEG 质量与原来的 base64 路径**完全一致**，只是换传输：
 *   * 异步 toBlob 取代同步 toDataURL —— 后者会占住主线程，把 rAF 一起冻住；
 *   * 省掉 base64（体积 ×4/3）和 100KB 级 JSON 字符串的往返。
 * 时间戳随帧走，前端才能把结果按时间轴对齐回放。
 */
function captureFrameBinary() {
  const drawn = drawCaptureCanvas();
  if (!drawn) return Promise.resolve(null);
  const vt = drawn.video.currentTime;
  return new Promise((resolve) => {
    drawn.canvas.toBlob(async (blob) => {
      if (!blob) return resolve(null);
      try {
        const jpeg = new Uint8Array(await blob.arrayBuffer());
        const out = new Uint8Array(8 + jpeg.length);
        new DataView(out.buffer).setFloat64(0, vt, true);
        out.set(jpeg, 8);
        resolve(out);
      } catch {
        resolve(null);
      }
    }, 'image/jpeg', FRAME_JPEG_QUALITY);
  });
}

// HTTP 降级通道仍用 base64
function captureFrameBase64() {
  const drawn = drawCaptureCanvas();
  if (!drawn) return '';
  try {
    return drawn.canvas.toDataURL('image/jpeg', FRAME_JPEG_QUALITY);
  } catch {
    return '';
  }
}

async function runInferenceOnce() {
  if (!isInferenceEnabled() || inferenceBusy) return;
  inferenceBusy = true;
  const startedAt = performance.now();
  try {
    let res;
    const imageBase64 = captureFrameBase64();
    if (imageBase64) {
      res = await detectYOLO({ imageBase64, cameraId: currentCam.value?.id || null });
    } else if (currentCam.value?.id) {
      res = await testCameraInference(currentCam.value.id);
    } else {
      return;
    }
    if (res.data?.success) {
      const data = res.data.data;
      feedTracks(data);
      latestDetection.value = data;
      inferenceError.value = '';
      const riskLevel = String(data?.prediction?.riskLevel || data?.alertLevel || 'NORMAL').toUpperCase();
      const shouldSyncAlerts = data?.alert || ['LOW', 'MEDIUM', 'HIGH', 'URGENT'].includes(riskLevel);
      const now = Date.now();
      if (shouldSyncAlerts && now - alertSyncAt > 2000) {
        alertSyncAt = now;
        loadAlerts();
        loadDashboard();
      }
      drawModelOverlay();
    }
  } catch (e) {
    inferenceError.value = e.response?.data?.message || e.response?.data?.detail || 'AI 推理失败';
    drawModelOverlay();
  } finally {
    inferenceBusy = false;
    if (inferenceTimer && isInferenceEnabled()) {
      const elapsed = performance.now() - startedAt;
      const nextDelay = Math.max(inferenceIntervalMs, Math.round(elapsed * 1.2));
      inferenceTimer = setTimeout(runInferenceOnce, nextDelay);
    }
  }
}

function stopStreamSockets() {
  socketAwaitingResult = false;
  if (streamSocket) { streamSocket.close(); streamSocket = null; }
  if (frameSocket) { frameSocket.close(); frameSocket = null; }
  if (wsFrameTimer) { clearTimeout(wsFrameTimer); wsFrameTimer = null; }
}

function startCameraStreamSocket(cameraId) {
  stopStreamSockets();
  const token = sessionStorage.getItem('api_token') || '';
  if (!token || !cameraId) return false;
  streamSocket = new WebSocket(`${wsBaseUrl()}/yolo/cameras/${cameraId}/stream?token=${encodeURIComponent(token)}`);
  streamSocket.onmessage = (event) => {
    try { handleStreamResult(JSON.parse(event.data)); } catch (err) {
      console.warn('检测结果帧解析失败，已跳过该帧', err);
    }
  };
  streamSocket.onerror = () => { inferenceError.value = '摄像头 WebSocket 推理连接失败，已尝试前端抽帧降级'; };
  streamSocket.onclose = () => { streamSocket = null; };
  startOverlayLoop();
  return true;
}

function startFrameStreamSocket(cameraId = null) {
  const token = sessionStorage.getItem('api_token') || '';
  if (!token) return false;
  // ── 幂等保护 ────────────────────────────────────────────────────────
  // startLocal() 建一次帧流 socket，紧接着 <video> 的 playing 事件又走
  // onLocalPlaying() 建一次。第二次会先执行 stopStreamSockets()，把第一次
  // 那个**握手尚未完成**的 socket 关掉，浏览器报
  //   "WebSocket is closed before the connection is established"
  // 随后 onclose 触发 startInferenceLoop()，整条链路**静默降级到 HTTP 抽帧**，
  // 帧率白白损失一半以上。这里对"正在连接/已连接"的 socket 直接复用。
  if (frameSocket && (frameSocket.readyState === WebSocket.CONNECTING
                      || frameSocket.readyState === WebSocket.OPEN)) {
    return true;
  }
  stopStreamSockets();
  const query = new URLSearchParams({ token });
  if (cameraId) query.set('cameraId', cameraId);
  frameSocket = new WebSocket(`${wsBaseUrl()}/yolo/frame-stream?${query.toString()}`);
  frameSocket.onmessage = (event) => {
    try { handleStreamResult(JSON.parse(event.data)); } catch (err) {
      console.warn('检测结果帧解析失败，已跳过该帧', err);
    }
  };
  frameSocket.onerror = () => {
    inferenceError.value = '帧流 WebSocket 连接失败，已尝试 HTTP 抽帧降级';
    stopStreamSockets();
    startInferenceLoop();
  };
  frameSocket.onopen = () => {
    inFlightFrames = 0;
    for (let i = 0; i < MAX_INFLIGHT; i += 1) sendFrameToSocket();
  };
  frameSocket.onclose = () => {
    socketAwaitingResult = false;
    inFlightFrames = 0;
    frameSocket = null;
    if (wsFrameTimer) { clearTimeout(wsFrameTimer); wsFrameTimer = null; }
    if (isInferenceEnabled() && !inferenceTimer && !inferenceBusy) startInferenceLoop();
  };
  startOverlayLoop();
  return true;
}

function scheduleFrameSend(delay = inferenceIntervalMs) {
  if (wsFrameTimer) clearTimeout(wsFrameTimer);
  wsFrameTimer = setTimeout(sendFrameToSocket, delay);
}

function sendFrameToSocket() {
  if (!frameSocket || frameSocket.readyState !== WebSocket.OPEN) return;
  if (!isInferenceEnabled() || inFlightFrames >= MAX_INFLIGHT) return;
  inFlightFrames += 1;
  captureFrameBinary().then((buf) => {
    if (!buf) { inFlightFrames = Math.max(0, inFlightFrames - 1); scheduleFrameSend(100); return; }
    if (!frameSocket || frameSocket.readyState !== WebSocket.OPEN) {
      inFlightFrames = Math.max(0, inFlightFrames - 1);
      return;
    }
    try {
      frameSocket.send(buf);
    } catch {
      inFlightFrames = Math.max(0, inFlightFrames - 1);
    }
  });
}

function startOverlayLoop() {
  if (overlayFrame) return;
  const tick = () => {
    drawModelOverlay();
    overlayFrame = requestAnimationFrame(tick);
  };
  overlayFrame = requestAnimationFrame(tick);
}

function stopOverlayLoop() {
  if (overlayFrame) cancelAnimationFrame(overlayFrame);
  overlayFrame = null;
}

function startInferenceLoop() {
  stopInferenceLoop();
  if (!isInferenceEnabled()) return;
  startOverlayLoop();
  inferenceTimer = setTimeout(runInferenceOnce, 0);
}

function stopInferenceLoop() {
  if (inferenceTimer) { clearTimeout(inferenceTimer); inferenceTimer = null; }
  stopStreamSockets();
  resetTracks();
  stopOverlayLoop();
  inferenceBusy = false;
  latestDetection.value = null;
  inferenceError.value = '';
}

function clearOverlay() {
  if (canvasRef.value) {
    const ctx = canvasRef.value.getContext('2d');
    ctx?.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height);
  }
}

// ── 本地摄像头 ──
// 连续互通相机（用 iPhone 当摄像头）会在系统里动态出现/消失，
// 不监听 devicechange 的话，插上手机后列表里始终看不到它。
let lastDeviceKey = '';
function onDeviceChange() {
  scanDevices().then(() => {
    const key = localDevices.value.map(d => d.deviceId).join(',');
    if (key && key !== lastDeviceKey) {
      lastDeviceKey = key;
      if (activeSrc.value === 'local' && !localActive.value) {
        showToast(`检测到 ${localDevices.value.length} 个摄像头，可在下拉框中选择`, 'success');
      }
    }
  });
}

async function scanDevices() {
  if (!navigator.mediaDevices?.getUserMedia) return;
  try {
    // 这一次 getUserMedia 只是为了触发权限提示（拿到 label 必须授权过），
    // 拿到就立刻停掉。用户拒绝授权是**正常**路径，不是错误 —— 所以只记录不打扰。
    const tmp = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    tmp.getTracks().forEach(t => t.stop());
  } catch (e) {
    console.warn('摄像头授权未通过（本机设备名可能显示为通用名称）', e?.name);
  }
  try {
    const all = await navigator.mediaDevices.enumerateDevices();
    localDevices.value = all.filter(d => d.kind === 'videoinput');
    if (localDevices.value.length && !localDeviceId.value) {
      localDeviceId.value = localDevices.value[0].deviceId;
    }
  } catch (e) {
    console.error('枚举本机摄像头失败', e);
    showToast('无法读取本机摄像头列表，请检查浏览器权限', 'error');
  }
}

async function startLocal() {
  if (!navigator.mediaDevices?.getUserMedia) {
    localError.value = '浏览器不支持摄像头访问';
    viewState.value = 'local-error';
    return;
  }
  localError.value = '';
  localActive.value = false;
  viewState.value = 'local-requesting';
  if (!localDevices.value.length) await scanDevices();
  try {
    // 设备约束分两级回退。
    // 第一级带上分辨率偏好；若该设备不支持（Continuity 相机 / 外接采集卡常见
    // OverconstrainedError 或 NotFoundError），第二级退化为"该设备能给的都行"。
    // 另外去掉了 facingMode:'environment' —— 那是移动端后置摄像头的提示，
    // 在桌面浏览器上既无意义，又可能在部分设备上直接导致约束不满足。
    const preferred = localDeviceId.value
      ? { deviceId: { exact: localDeviceId.value }, width: { ideal: 1280 }, height: { ideal: 720 } }
      : { width: { ideal: 1280 }, height: { ideal: 720 } };
    let stream = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: preferred, audio: false });
    } catch (err) {
      const relaxable = ['OverconstrainedError', 'NotFoundError', 'NotReadableError'];
      if (!relaxable.includes(err?.name)) throw err;
      stream = await navigator.mediaDevices.getUserMedia({
        video: localDeviceId.value ? { deviceId: localDeviceId.value } : true,
        audio: false,
      });
    }
    localStream = stream;
    const videoEl = localVideoRef.value;
    if (!videoEl) { stopLocalStream(); viewState.value = 'idle'; return; }
    videoEl.srcObject = localStream;
    try { await videoEl.play(); } catch (e) { if (e.name !== 'AbortError') throw e; }
    localActive.value = true;
    viewState.value = 'local-active';
    await nextTick();
    syncCanvas();
    if (!startFrameStreamSocket(null)) startInferenceLoop();
    const all = await navigator.mediaDevices.enumerateDevices();
    localDevices.value = all.filter(d => d.kind === 'videoinput');
  } catch (e) {
    stopInferenceLoop();
    stopLocalStream();
    if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
      localError.value = '摄像头权限被拒绝：请通过 https:// 地址访问，或在浏览器地址栏允许摄像头权限';
    } else if (e.name === 'NotReadableError' || e.name === 'TrackStartError') {
      localError.value = '摄像头被其他应用占用，请关闭后重试';
    } else {
      localError.value = '无法打开摄像头：' + (e.message || e.name || '未知错误');
    }
    viewState.value = 'local-error';
  }
}

function stopLocalStream() {
  if (localStream) { localStream.getTracks().forEach(t => t.stop()); localStream = null; }
  if (localVideoRef.value) localVideoRef.value.srcObject = null;
  localActive.value = false;
}

function onLocalPlaying() {
  if (activeSrc.value === 'local') {
    localActive.value = true;
    viewState.value = 'local-active';
    syncCanvas();
    if (!frameSocket && !streamSocket && !startFrameStreamSocket(null)) startInferenceLoop();
  }
}

function onLocalVideoError(e) {
  if (activeSrc.value !== 'local') return;
  stopInferenceLoop();
  localError.value = '视频流渲染失败：' + (e.message || '未知错误');
  viewState.value = 'local-error';
}

function switchLocalDevice() { stopLocalStream(); startLocal(); }

async function selectLocal() {
  if (activeSrc.value === 'local') return;
  stop(false);
  activeSrc.value = 'local';
  currentType.value = 'local';
  currentCam.value = null;
  streamError.value = '';
  await startLocal();
}

// ── 流媒体摄像头 ──
function selectCam(cam) {
  if (cam.status !== 1) { showToast('该摄像头当前离线', 'warning'); return; }
  if (activeSrc.value === cam.id) return;
  stop(false);
  activeSrc.value = cam.id;
  currentCam.value = cam;
  currentType.value = cam.sourceType || 'rtsp';
  currentUrl.value = cam.streamUrl || '';
  streamError.value = '';
  if (currentType.value === 'local') { selectLocal(); return; }
  playStream(currentType.value, currentUrl.value);
}

function playStream(type, url) {
  if (currentCam.value?.id && startCameraStreamSocket(currentCam.value.id)) {
    if (type === 'rtsp') viewState.value = 'rtsp';
  }
  if (type === 'rtsp') { viewState.value = 'rtsp'; if (!streamSocket) startInferenceLoop(); return; }
  if (!url) { stopInferenceLoop(); streamError.value = '该摄像头未配置流地址'; viewState.value = 'stream-error'; return; }
  if (type === 'mjpeg') {
    viewState.value = 'stream-active';
    nextTick(() => {
      if (mjpegRef.value) mjpegRef.value.src = url + (url.includes('?') ? '&' : '?') + '_t=' + Date.now();
      syncCanvas(); if (!streamSocket) startInferenceLoop();
    });
    return;
  }
  viewState.value = 'stream-active';
  nextTick(() => {
    const v = streamVideoRef.value;
    if (!v) return;
    v.src = url; v.load();
    v.play().catch(err => {
      if (err.name !== 'AbortError') { stopInferenceLoop(); streamError.value = '视频加载失败，请检查地址是否可访问'; viewState.value = 'stream-error'; }
    });
    syncCanvas(); if (!streamSocket) startInferenceLoop();
  });
}

function onVideoError() { stopInferenceLoop(); streamError.value = '视频流加载失败，请检查地址或网络'; viewState.value = 'stream-error'; }
function onStreamCanPlay() { syncCanvas(); }
function onMjpegLoad() { syncCanvas(); }

function stop(resetSrc = true) {
  stopInferenceLoop();
  stopLocalStream();
  clearOverlay();
  if (streamVideoRef.value) { streamVideoRef.value.pause(); streamVideoRef.value.removeAttribute('src'); streamVideoRef.value.load(); }
  if (mjpegRef.value) mjpegRef.value.src = '';
  if (resetSrc) { activeSrc.value = null; currentCam.value = null; currentType.value = ''; currentUrl.value = ''; }
  streamError.value = ''; localError.value = '';
  viewState.value = 'idle';
}

function retry() {
  if (activeSrc.value === 'local') { startLocal(); return; }
  if (currentCam.value) selectCam(currentCam.value);
}

function syncCanvas() {
  if (!canvasRef.value || !videoWrapRef.value) return;
  const { clientWidth: w, clientHeight: h } = videoWrapRef.value;
  if (w > 0 && h > 0) { canvasRef.value.width = w; canvasRef.value.height = h; }
}

// 检测全屏 API 是否被权限策略允许
const isFullscreenSupported = !!(
  document.fullscreenEnabled ||
  document.webkitFullscreenEnabled
);

function toggleFullscreen() {
  const el = videoWrapRef.value;
  if (!el) return;
  const isFs = !!(document.fullscreenElement || document.webkitFullscreenElement);
  if (!isFs) {
    const req = el.requestFullscreen || el.webkitRequestFullscreen || el.mozRequestFullScreen;
    // 全屏请求可以被浏览器策略拒绝（非用户手势触发）——失败时只是没全屏，
    // 界面本身仍然正确，所以只记录不提示。
    if (req) req.call(el).catch((e) => console.warn('进入全屏被拒绝', e?.name));
  } else {
    const exit = document.exitFullscreen || document.webkitExitFullscreen || document.mozCancelFullScreen;
    if (exit) exit.call(document).catch((e) => console.warn('退出全屏失败', e?.name));
  }
}

// ── 数据加载 ──
// 三处原先都是空 catch：请求失败后页面照常渲染，而空态的文案是
// 「暂无已注册设备」—— 把"设备列表读不出来"说成了"机构里没有摄像头"。
// 这两个结论指向的行动完全相反（去查服务 vs 去装设备），所以必须分开。
const camerasError = ref('');
const dashboardError = ref('');

async function loadDashboard() {
  try {
    const r = await getDashboard();
    if (r.data.success) dashboardData.value = r.data.data;
    dashboardError.value = '';
  } catch (e) {
    console.error('加载总览数据失败', e);
    dashboardError.value = `总览数据加载失败：${e?.friendlyMessage || '未知错误'}`;
  }
}
async function loadAlerts() {
  alertsLoading.value = true;
  try { const r = await getRecentAlerts(10); if (r.data.success) recentAlerts.value = r.data.data; }
  catch (e) { console.error('加载最近告警失败', e); }
  finally { alertsLoading.value = false; }
}
async function loadCameras() {
  try {
    const r = await getCameraList({ page: 1, pageSize: 100 });
    // /cameras/ 现在返回 {data,total,page,pageSize}（与全站列表契约一致）
    if (r.data.success) cameras.value = r.data.data?.data || [];
    camerasError.value = '';
  } catch (e) {
    console.error('加载摄像头列表失败', e);
    camerasError.value = `设备列表加载失败：${e?.friendlyMessage || '未知错误'}`;
  }
}

function openConfirm(alert) { confirmModal.value = { show: true, alert, notes: '', loading: false }; }
async function submitConfirm() {
  if (!confirmModal.value.notes.trim()) { showToast('请填写处置备注', 'warning'); return; }
  confirmModal.value.loading = true;
  try {
    const r = await confirmAlert(confirmModal.value.alert.id, confirmModal.value.notes);
    if (r.data.success) { showToast('确认成功', 'success'); confirmModal.value.show = false; loadAlerts(); loadDashboard(); }
    else showToast(r.data.message || '操作失败', 'error');
  } catch { showToast('网络错误', 'error'); }
  finally { confirmModal.value.loading = false; }
}

// ── 生命周期 ──
let refreshTimer = null;
let heartbeatTimer = null;

async function sendHeartbeat() {
  if (currentCam.value?.id && viewState.value === 'stream-active') {
    try { await heartbeatCamera(currentCam.value.id); }
    catch (e) { console.warn('摄像头心跳上报失败（该设备会被判为离线）', e?.friendlyMessage || e); }
  }
}

onMounted(() => {
  navigator.mediaDevices?.addEventListener?.('devicechange', onDeviceChange);
  updateClock();
  clockTimer = setInterval(updateClock, 1000);
  loadDashboard(); loadAlerts(); loadCameras();
  refreshTimer = setInterval(() => { loadDashboard(); loadAlerts(); }, 15000);
  heartbeatTimer = setInterval(sendHeartbeat, 30000);
  window.addEventListener('resize', syncCanvas);
  document.addEventListener('fullscreenchange', syncCanvas);
  document.addEventListener('webkitfullscreenchange', syncCanvas);
  navigator.mediaDevices?.enumerateDevices().then(all => {
    const vids = all.filter(d => d.kind === 'videoinput');
    if (vids.length) { localDevices.value = vids; localDeviceId.value = vids[0].deviceId; }
  }).catch((e) => console.warn('枚举本机摄像头失败（可改用已注册的网络摄像头）', e?.name));
});
onUnmounted(() => {
  navigator.mediaDevices?.removeEventListener?.('devicechange', onDeviceChange);
  clearInterval(heartbeatTimer);
  clearInterval(clockTimer);
  clearInterval(refreshTimer);
  stop();
  window.removeEventListener('resize', syncCanvas);
  document.removeEventListener('fullscreenchange', syncCanvas);
  document.removeEventListener('webkitfullscreenchange', syncCanvas);
});
</script>

<style scoped>
/* 根容器/页头/栅格/表格等通用结构一律由 assets/styles/layout.css 提供，
   这里只保留本页特有的组件样式。原先此处重复定义了 .page-header 与 h1，
   且与全局版本不一致（margin-bottom 20px vs 令牌值）。 */
.header-left { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.status-chip { display: flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.status-chip.online  { background: color-mix(in srgb, var(--success) 15%, transparent); color: var(--success); border: 1px solid color-mix(in srgb, var(--success) 25%, transparent); }
.status-chip.offline { background: color-mix(in srgb, var(--neutral) 10%, transparent);  color: var(--text-tertiary); border: 1px solid color-mix(in srgb, var(--neutral) 18%, transparent); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; animation: blink 1.5s infinite; }
@keyframes blink { 0%,100%{opacity:1}50%{opacity:.3} }
.clock { font-size: 13px; color: var(--text-muted); font-variant-numeric: tabular-nums; }

/* ── 主布局 ── */
/* 用统一的 grid-main-side（7:3）替代原先写死的 860px+300px：
   固定像素在窄屏会溢出，比例栅格配合断点自动堆叠。 */
.monitor-layout { --side-w: 400px; }
.video-section { display: flex; flex-direction: column; gap: var(--space-3); min-width: 0; }

/* ── 摄像头选择栏 ── */
.cam-bar { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: var(--radius-md); padding: 12px; overflow-x: auto; }
.cam-bar::-webkit-scrollbar { height: 3px; }
.cam-bar::-webkit-scrollbar-thumb { background: var(--tint-4); border-radius: 2px; }
.cam-bar-inner { display: flex; align-items: center; gap: 8px; min-width: max-content; }
.cam-divider { width: 1px; height: 36px; background: var(--tint-3); margin: 0 4px; flex-shrink: 0; }
.cam-empty { font-size: 12px; color: var(--text-muted); white-space: nowrap; padding: 4px 8px; }
/* 加载失败不能用中性灰：它不是"没有数据"，是需要处理的服务异常 */
.cam-empty-error { color: var(--danger-text); white-space: normal; }
.panel-empty-error { color: var(--danger-text); padding: 8px 0; }

.cam-chip { display: flex; align-items: center; gap: 9px; padding: 8px 12px; border-radius: 10px; border: 1px solid var(--tint-3); background: var(--tint-1); cursor: pointer; transition: all .2s; user-select: none; flex-shrink: 0; }
.cam-chip:hover { border-color: color-mix(in srgb, var(--primary) 30%, transparent); background: color-mix(in srgb, var(--primary) 5%, transparent); }
.cam-chip.active { border-color: color-mix(in srgb, var(--primary) 60%, transparent); background: color-mix(in srgb, var(--primary) 12%, transparent); }
.cam-chip.offline { opacity: .45; cursor: not-allowed; }
.local-chip { border-style: dashed; }
.chip-icon { font-size: 18px; flex-shrink: 0; }
.chip-body { min-width: 0; }
.chip-name { font-size: 12px; font-weight: 700; color: var(--text-secondary); white-space: nowrap; }
.chip-sub  { font-size: 10px; color: var(--text-muted); margin-top: 1px; white-space: nowrap; }
.cam-chip.active .chip-name { color: var(--primary-hover); }
.chip-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; transition: background .3s; }
.chip-dot.on   { background: var(--success); box-shadow: 0 0 6px var(--success)70; animation: blink 2s infinite; }
.chip-dot.off  { background: var(--danger); }
.chip-dot.idle { background: var(--tint-5); }

/* ── 视频卡片 ── */
.video-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: var(--radius-md); overflow: hidden; }
/* .video-wrap 的底纹/圆角/内边由全局 .stage 提供（实时监控与视频检测共用），
   这里只约束本页的高度范围。 */
.video-wrap { min-height: 180px; max-height: 484px; }

.placeholder, .vid-error, .ph-tip { margin-top: var(--space-4); max-width: 460px; padding: 10px 14px; border-radius: var(--radius-md);
  background: var(--warning-soft); border: 1px solid var(--warning); font-size: var(--text-base);
  color: var(--text-secondary); line-height: 1.8; text-align: left; }
.ph-tip strong { color: var(--warning-text); }
.rtsp-notice { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 28px 20px; text-align: center; width: 100%; }
.ph-icon  { font-size: 48px; opacity: .4; }
.ph-icon.spin { animation: spin 2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.ph-title { font-size: 14px; font-weight: 700; color: var(--text-muted); }
.ph-sub   { font-size: 12px; color: var(--text-muted); max-width: 320px; line-height: 1.7; }
.vid-error .ph-title { color: var(--danger-text); }
.rtsp-url { font-size: 11px; color: var(--text-tertiary); background: var(--tint-2); border-radius: 6px; padding: 6px 12px; font-family: monospace; word-break: break-all; max-width: 360px; }
.btn-retry { padding: 7px 18px; border-radius: 8px; border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent); background: color-mix(in srgb, var(--danger) 10%, transparent); color: var(--danger-text); cursor: pointer; font-size: 12px; }
.btn-retry:hover { background: color-mix(in srgb, var(--danger) 20%, transparent); }

.video-el { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.det-canvas { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 10; }


/* 徽章 & 按钮 */
.live-badge { position: absolute; top: 10px; left: 10px; background: color-mix(in srgb, var(--danger) 88%, transparent); color: var(--text-on-color); font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 5px; display: flex; align-items: center; gap: 5px; z-index: 11; }
.live-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--text-on-color); animation: blink 1s infinite; }
.fullscreen-btn { position: absolute; top: 10px; right: 10px; width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--tint-5); background: var(--bg-overlay); color: var(--text-secondary); font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; z-index: 11; }
.fullscreen-btn:hover { background: var(--bg-overlay); }

/* 控制栏 */
.ctrl-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-top: 1px solid var(--tint-2); min-height: 48px; gap: 10px; }
.ctrl-left { display: flex; align-items: center; flex: 1; min-width: 0; overflow: hidden; }
.ctrl-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.cam-label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cam-label--dim { color: var(--text-muted); }
.device-sel { background: var(--tint-3); border: 1px solid var(--tint-4); border-radius: 7px; padding: 5px 10px; color: var(--text-secondary); font-size: 12px; outline: none; max-width: 180px; }
.btn-stop { padding: 6px 14px; border-radius: 7px; border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent); background: color-mix(in srgb, var(--danger) 8%, transparent); color: var(--danger-text); cursor: pointer; font-size: 12px; white-space: nowrap; }
.btn-stop:hover { background: color-mix(in srgb, var(--danger) 18%, transparent); }

/* ── 右侧面板 ── */
.right-panel { display: flex; flex-direction: column; gap: 14px; }
.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.stat-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: var(--radius-md); padding: 14px; display: flex; align-items: center; gap: 12px; transition: transform .2s; }
.stat-card:hover { transform: translateY(-2px); }
.stat-icon { width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 17px; flex-shrink: 0; }
.stat-value { font-size: 22px; font-weight: 800; line-height: 1; }
.stat-label { font-size: 10px; color: var(--text-tertiary); margin-top: 3px; }

.evidence-card { background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: var(--space-4); margin-bottom: var(--space-3); }
.ev-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.ev-head .card-title { font-size: var(--text-md); font-weight: 650; color: var(--text-primary); }
.ev-empty { font-size: var(--text-base); color: var(--text-muted); padding: var(--space-4) 0; text-align: center; }
.ev-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px dashed var(--border-subtle); font-size: var(--text-base); }
.ev-row:last-of-type { border-bottom: none; }
.ev-k { color: var(--text-muted); }
.ev-v { color: var(--text-primary); font-weight: 600; }
.ev-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); margin: var(--space-3) 0; }
.ev-m-label { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: 5px; }
.ev-bar { height: 5px; background: var(--tint-3); border-radius: var(--radius-full); overflow: hidden; }
.ev-bar span { display: block; height: 100%; border-radius: var(--radius-full); transition: width .2s; }
.ev-m-num { font-size: var(--text-sm); color: var(--text-tertiary); margin-top: 4px; font-variant-numeric: tabular-nums; }
.ev-belief { display: flex; align-items: center; gap: 8px; padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.ev-b { padding: 2px 8px; border-radius: var(--radius-sm); background: var(--bg-inset); border: 1px solid var(--border-subtle); font-size: var(--text-sm); color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.ev-note { font-size: var(--text-sm); color: var(--text-tertiary); line-height: 1.7; margin: var(--space-3) 0 0; }
.ev-note.muted { color: var(--text-muted); }
.alert-list-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 16px; overflow: hidden; }
.alert-list-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--tint-3); }
.card-title { font-size: 12px; font-weight: 700; color: var(--text-tertiary); }
.view-all { font-size: 11px; color: var(--primary); text-decoration: none; }
.list-empty { padding: 24px; text-align: center; font-size: 12px; color: var(--text-muted); }
.alert-items { max-height: 420px; overflow-y: auto; }
.alert-items::-webkit-scrollbar { width: 3px; }
.alert-items::-webkit-scrollbar-thumb { background: var(--tint-3); border-radius: 2px; }
.alert-item { display: flex; align-items: center; gap: 7px; padding: 9px 12px; border-bottom: 1px solid var(--tint-2); transition: background .15s; }
.alert-item:hover { background: var(--tint-1); }
.alert-item:last-child { border-bottom: none; }
.alert-meta { display: flex; align-items: center; gap: 5px; flex: 1; flex-wrap: wrap; min-width: 0; }
.level-tag { padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; white-space: nowrap; }
.alert-elder { font-size: 11px; color: var(--text-tertiary); }
.alert-room  { font-size: 10px; color: var(--text-muted); }
.alert-info  { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }
.alert-conf  { font-size: 11px; font-weight: 700; color: var(--text-secondary); }
.alert-time  { font-size: 10px; color: var(--text-muted); white-space: nowrap; }
.alert-action { flex-shrink: 0; }
.btn-confirm-mini { padding: 4px 8px; border-radius: 5px; border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent); background: color-mix(in srgb, var(--primary) 10%, transparent); color: var(--primary-hover); font-size: 10px; cursor: pointer; white-space: nowrap; }
.confirmed-text { font-size: 11px; color: var(--success); }

/* ── 弹窗 ── */
.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 16px; width: 440px; max-width: 95vw; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--tint-3); }
.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: none; border: none; color: var(--text-tertiary); font-size: 20px; cursor: pointer; }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
.detail-row { display: flex; align-items: center; gap: 10px; }
.detail-text { font-size: 13px; color: var(--text-tertiary); }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-group label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); }
.req { color: var(--danger); }
.field-group textarea { background: var(--tint-3); border: 1px solid var(--tint-4); border-radius: 8px; padding: 10px; color: var(--text-secondary); font-size: 13px; resize: none; outline: none; font-family: inherit; }
.field-group textarea:focus { border-color: color-mix(in srgb, var(--primary) 50%, transparent); }
.char-count { font-size: 11px; color: var(--text-muted); text-align: right; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 20px; border-top: 1px solid var(--tint-3); }
.btn-cancel { padding: 8px 20px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; }
.btn-primary { padding: 8px 20px; border-radius: 8px; border: none; background: var(--primary); color: var(--text-on-color); cursor: pointer; font-weight: 600; }
.btn-primary:hover { background: var(--primary-active); }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }

/* ══ 响应式 ══ */
@media (max-width: 1100px) {
  .monitor-layout { grid-template-columns: 1fr; }
  .right-panel { flex-direction: row; flex-wrap: wrap; gap: 12px; }
  .stats-grid { flex: 1; min-width: 280px; }
  .alert-list-card { flex: 1 1 100%; }
}
@media (max-width: 768px) {
  .page-monitor { padding: 12px 12px 0; }
  h1 { font-size: 17px; }
  .clock { font-size: 11px; }
  .video-wrap { aspect-ratio: 4/3; min-height: 160px; }
  .ctrl-bar { padding: 8px 12px; flex-wrap: wrap; min-height: 44px; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .stat-card { padding: 10px; gap: 8px; border-radius: var(--radius-md); }
  .stat-card:hover { transform: none; }
  .alert-items { max-height: 280px; }
  .modal-mask { align-items: flex-end; }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; }
  .modal-footer { flex-direction: column; gap: 8px; }
  .btn-cancel, .btn-primary { width: 100%; min-height: 48px; font-size: 15px; border-radius: 12px; }
}
</style>
