<template>
  <div class="page-agent">
    <div class="agent-layout">

      <!-- ══ 左侧面板 ══ -->
      <div class="side-panel">

        <!-- 新建会话按钮 -->
        <button class="new-chat-btn" @click="newSession">
          <span>＋</span> 新建对话
        </button>

        <!-- 会话列表 -->
        <div class="session-list">
          <div class="side-section-title">历史对话</div>
          <div v-if="!sessions.length" class="session-empty">暂无历史对话</div>
          <div
            v-for="s in sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === currentSessionId }"
            @click="switchSession(s.id)"
          >
            <div class="session-preview">{{ s.title }}</div>
            <div class="session-meta">{{ s.time }} · {{ s.count }}条</div>
            <button class="session-del" @click.stop="deleteSession(s.id)" title="删除">×</button>
          </div>
        </div>

        <!-- 能力列表 -->
        <div class="side-capabilities">
          <div class="side-section-title">能力</div>
          <div class="cap-grid">
            <div v-for="cap in capabilities" :key="cap.name" class="cap-chip">
              <span>{{ cap.icon }}</span> {{ cap.name }}
            </div>
          </div>
        </div>

        <!-- 统计 -->
        <div class="side-stats">
          <div class="stat-box">
            <div class="stat-num">{{ currentMessages.filter(m => m.role === 'user').length }}</div>
            <div class="stat-lbl">本次提问</div>
          </div>
          <div class="stat-box">
            <div class="stat-num">{{ toolCallCount }}</div>
            <div class="stat-lbl">工具调用</div>
          </div>
          <div class="stat-box">
            <div class="stat-num">{{ sessions.length }}</div>
            <div class="stat-lbl">历史会话</div>
          </div>
        </div>
      </div>

      <!-- ══ 右侧对话区 ══ -->
      <div class="chat-area">

        <!-- 顶栏 -->
        <div class="chat-topbar">
          <div class="topbar-left">
            <div class="topbar-dot" :class="thinking ? 'thinking' : 'ready'"></div>
            <span class="topbar-status">{{ thinking ? '思考中…' : '就绪' }}</span>
            <span v-if="currentMessages.length" class="ctx-badge">
              上下文 {{ Math.min(currentMessages.filter(m=>m.role==='user'||m.role==='assistant').length, 10) }}/10
            </span>
          </div>
          <div class="topbar-right">
            <button v-if="thinking && hasAbort" class="topbar-btn danger" @click="abortChat">⏹ 中止</button>
            <button class="topbar-btn" @click="clearChat">🗑 清空</button>
          </div>
        </div>

        <!-- 消息流 -->
        <div class="msg-stream" ref="msgStreamRef">

          <!-- 欢迎卡片 -->
          <div v-if="!currentMessages.length" class="welcome-card">
            <div class="welcome-icon">🤖</div>
            <div class="welcome-title">你好，我是护卫AI</div>
            <div class="welcome-sub">我已接入养老系统的所有数据源，可以帮你实时查询告警、老人状态、值班安排，还能协助处置紧急事件。</div>
            <div class="welcome-chips">
              <button
                v-for="q in quickPrompts.slice(0, 4)"
                :key="q.text"
                class="welcome-chip"
                :disabled="thinking"
                @click="sendQuick(q.text)"
              >{{ q.text }}</button>
            </div>
          </div>

          <!-- 消息列表 -->
          <template v-for="msg in currentMessages" :key="msg.id">

            <!-- 用户消息 -->
            <div v-if="msg.role === 'user'" class="row-user">
              <div class="bubble-user">{{ msg.content }}</div>
              <div class="avatar-user">{{ userInitial }}</div>
            </div>

            <!-- AI 消息 -->
            <div v-else-if="msg.role === 'assistant'" class="row-ai">
              <div class="avatar-ai">🤖</div>
              <div class="bubble-ai-wrap">
                <!-- 工具调用轨迹 -->
                <div v-if="msg.toolCalls?.length" class="tool-trace">
                  <div
                    v-for="tc in msg.toolCalls"
                    :key="tc.tool + '_' + tc.callIdx"
                    class="tc-row"
                    :class="tc.status"
                  >
                    <span class="tc-dot"></span>
                    <span class="tc-label">{{ tc.label }}</span>
                    <span class="tc-badge" :class="tc.status">
                      {{ tc.status === 'running' ? '执行中' : tc.status === 'done' ? '完成' : '失败' }}
                    </span>
                    <!-- 工具结果展开（仅内存中 tc.data 存在时显示） -->
                    <button
                      v-if="tc.status === 'done' && tc.data"
                      class="tc-expand-btn"
                      @click="toggleToolData(msg.id, tc.tool + '_' + tc.callIdx)"
                    >{{ expandedTools[msg.id + tc.tool + tc.callIdx] ? '收起' : '查看' }}</button>
                  </div>
                  <!-- 工具结果内容 -->
                  <template v-for="tc in msg.toolCalls" :key="'data-' + tc.tool + tc.callIdx">
                    <div v-if="expandedTools[msg.id + tc.tool + tc.callIdx] && tc.data" class="tool-data">
                      <pre>{{ JSON.stringify(tc.data, null, 2) }}</pre>
                    </div>
                  </template>
                </div>

                <!-- 正文 -->
                <div class="bubble-ai">
                  <div class="bubble-text" v-html="renderMd(msg.content)"></div>
                  <div v-if="msg.streaming" class="typing-cur">▋</div>
                  <div v-if="!msg.streaming && msg.content" class="bubble-footer">
                    <span class="bubble-ts">{{ msg.time }}</span>
                    <button class="copy-btn" :class="{ copied: copiedId === msg.id }" @click="handleCopy(msg)">
                      {{ copiedId === msg.id ? '✓ 已复制' : '复制' }}
                    </button>
                  </div>
                </div>

                <!-- 推荐追问 -->
                <div v-if="msg.suggests?.length && !msg.streaming" class="suggest-row">
                  <button
                    v-for="s in msg.suggests"
                    :key="s"
                    class="suggest-chip"
                    :disabled="thinking"
                    @click="sendQuick(s)"
                  >{{ s }}</button>
                </div>
              </div>
            </div>

            <!-- 错误消息 -->
            <div v-else-if="msg.role === 'error'" class="row-ai">
              <div class="avatar-ai">⚠️</div>
              <div class="bubble-error">{{ msg.content }}</div>
            </div>

          </template>

          <!-- 思考占位 -->
          <div v-if="thinking && !streamingMsg" class="row-ai">
            <div class="avatar-ai">🤖</div>
            <div class="bubble-ai">
              <div class="thinking-dots"><span></span><span></span><span></span></div>
            </div>
          </div>
        </div>

        <!-- 快捷提问栏 -->
        <div class="quick-bar">
          <button
            v-for="q in quickPrompts"
            :key="q.text"
            class="quick-chip"
            @click="sendQuick(q.text)"
            :disabled="thinking"
          >{{ q.icon }} {{ q.text }}</button>
        </div>

        <!-- 输入区 -->
        <div class="input-dock">
          <div class="input-wrap" :class="{ focused: inputFocused }">
            <textarea
              ref="inputRef"
              v-model="inputText"
              placeholder="向护卫AI提问，Enter 发送，Shift+Enter 换行…"
              rows="1"
              maxlength="500"
              @keydown.enter.exact.prevent="send"
              @keydown.shift.enter.exact="() => {}"
              @input="autoResize"
              @focus="inputFocused = true"
              @blur="inputFocused = false"
            ></textarea>
            <div class="input-toolbar">
              <span class="char-tip">{{ inputText.length }}/500</span>
              <button
                class="send-btn"
                :disabled="!inputText.trim() || thinking"
                @click="send"
              >{{ thinking ? '⏳' : '发送 ↑' }}</button>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, reactive } from 'vue';
import { chatStream } from '../api/agent.js';
import { showToast } from '../utils/index.js';

// ── 状态 ──────────────────────────────────────────────────────────────
const inputText    = ref('');
const thinking     = ref(false);
const inputFocused = ref(false);
const msgStreamRef = ref(null);
const inputRef     = ref(null);
const streamingMsg = ref(null);
const copiedId     = ref(null);
const expandedTools = reactive({});
// 用 ref 包装 abortFn，使模板响应式
const hasAbort     = ref(false);

let msgId   = 0;
let abortFn = null;

function setAbort(fn) {
  abortFn = fn;
  hasAbort.value = fn !== null;
}

// ── 用户信息 ──────────────────────────────────────────────────────────
const userInitial = computed(() => {
  // 不能裸 parse：sessionStorage 里的 current_user 出现过被写成 "[object Object]"
  // 的历史脏数据，那样 JSON.parse 会抛错、整个助手页渲染失败。
  // 同一份数据在 router 守卫里是有 try/catch 的，这里也必须有。
  try {
    const u = JSON.parse(sessionStorage.getItem('current_user') || '{}');
    if (!u || typeof u !== 'object') return '我';
    return String(u.name || u.username || '我').charAt(0);
  } catch {
    return '我';
  }
});

// ── 多会话管理（localStorage 持久化）────────────────────────────────
const STORAGE_KEY = 'agent_sessions_v2';

function loadSessions() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; }
}

function saveSessions() {
  try {
    // 剥离 tc.data（工具原始数据大），限制 20 条会话
    const slim = sessions.value.slice(0, 20).map(s => ({
      ...s,
      messages: s.messages.map(m => ({
        ...m,
        toolCalls: m.toolCalls?.map(tc => ({
          tool: tc.tool, label: tc.label, status: tc.status
        })) || [],
      }))
    }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(slim));
  } catch (e) {
    // 会话历史存不进本地只是"下次打开看不到记录"，不影响当前对话，
    // 因此只记录不弹提示 —— 但必须有痕迹，否则用户报"历史丢了"无从查起。
    console.warn('会话历史写入 localStorage 失败', e);
  }
}

const sessions = ref(loadSessions());
const currentSessionId = ref(sessions.value[0]?.id || null);

const currentMessages = computed(() => {
  const s = sessions.value.find(s => s.id === currentSessionId.value);
  return s?.messages || [];
});

const toolCallCount = computed(() =>
  currentMessages.value.reduce((sum, m) => sum + (m.toolCalls?.length || 0), 0)
);

function createSession(title = '新对话') {
  const id = Date.now().toString();
  const s = {
    id,
    title,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    count: 0,
    messages: [],
  };
  sessions.value.unshift(s);
  // 超出 20 条时裁剪
  if (sessions.value.length > 20) sessions.value = sessions.value.slice(0, 20);
  saveSessions();
  return id;
}

function newSession() {
  if (abortFn) { abortFn(); setAbort(null); }
  thinking.value = false;
  streamingMsg.value = null;
  currentSessionId.value = createSession();
}

function switchSession(id) {
  if (id === currentSessionId.value) return;
  if (abortFn) { abortFn(); setAbort(null); }
  thinking.value = false;
  streamingMsg.value = null;
  // 清空旧会话的展开状态
  Object.keys(expandedTools).forEach(k => delete expandedTools[k]);
  currentSessionId.value = id;
  nextTick(scrollBottom);
}

function deleteSession(id) {
  sessions.value = sessions.value.filter(s => s.id !== id);
  saveSessions();
  if (currentSessionId.value === id) {
    currentSessionId.value = sessions.value[0]?.id || null;
    if (!currentSessionId.value) {
      currentSessionId.value = createSession();
    }
  }
}

function pushMsg(msg) {
  const s = sessions.value.find(s => s.id === currentSessionId.value);
  if (!s) return;
  s.messages.push(msg);
  s.count = s.messages.filter(m => m.role === 'user').length;
  if (msg.role === 'user') {
    s.title = msg.content.slice(0, 20) + (msg.content.length > 20 ? '…' : '');
    s.time  = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  saveSessions();
}

// ── 静态数据 ──────────────────────────────────────────────────────────
const capabilities = [
  { icon: '🔔', name: '告警管理' },
  { icon: '👴', name: '老人档案' },
  { icon: '📅', name: '值班排班' },
  { icon: '📹', name: '摄像头' },
  { icon: '📊', name: '趋势统计' },
  { icon: '🏠', name: '系统概览' },
];

const quickPrompts = [
  { icon: '🔍', text: '今日系统情况如何？' },
  { icon: '🚨', text: '有哪些高风险未处理告警？' },
  { icon: '📅', text: '今天谁在值班？' },
  { icon: '📹', text: '当前哪些摄像头离线？' },
  { icon: '📊', text: '最近30天告警趋势？' },
  { icon: '👴', text: '查询101室老人信息' },
];

// ── 辅助函数 ──────────────────────────────────────────────────────────
function renderMd(text) {
  if (!text) return '';
  // 先转义，再解析 Markdown
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^#{1,3}\s+(.+)$/gm, '<b>$1</b>');

  // 把连续的列表项包裹进 <ul>
  html = html.replace(/((?:^[-•]\s+.+$\n?)+)/gm, (block) => {
    const items = block.trim().split('\n').map(line =>
      `<li>${line.replace(/^[-•]\s+/, '')}</li>`
    ).join('');
    return `<ul>${items}</ul>`;
  });

  html = html.replace(/\n/g, '<br>');
  return html;
}

function autoResize(e) {
  const el = e.target;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

async function scrollBottom() {
  await nextTick();
  if (msgStreamRef.value) msgStreamRef.value.scrollTop = msgStreamRef.value.scrollHeight;
}

async function handleCopy(msg) {
  // copiedId 必须只在**真的复制成功之后**才置位。
  // 原实现是 `try { writeText } catch {}` 之后无条件赋值 —— 剪贴板被浏览器
  // 拒绝（非安全上下文、无用户手势、权限被拒）时，界面照样弹出"已复制"
  // 并持续 2 秒，用户以为复制到了、实际粘贴出来什么都没有。
  try {
    await navigator.clipboard.writeText(msg.content);
  } catch (e) {
    console.error('复制失败', e);
    showToast('复制失败：浏览器拒绝了剪贴板访问，请手动选中文本复制', 'error');
    return;
  }
  copiedId.value = msg.id;
  setTimeout(() => { if (copiedId.value === msg.id) copiedId.value = null; }, 2000);
}

function toggleToolData(msgId, key) {
  const k = msgId + key;
  expandedTools[k] = !expandedTools[k];
}

// ── 对话逻辑 ──────────────────────────────────────────────────────────
function clearChat() {
  if (abortFn) { abortFn(); setAbort(null); }
  thinking.value    = false;
  streamingMsg.value = null;
  const s = sessions.value.find(s => s.id === currentSessionId.value);
  if (s) { s.messages = []; s.count = 0; saveSessions(); }
}

function abortChat() {
  if (abortFn) { abortFn(); setAbort(null); }
  if (streamingMsg.value) {
    streamingMsg.value.streaming = false;
    streamingMsg.value.content += '\n\n*[已中止]*';
    saveSessions();
  }
  thinking.value    = false;
  streamingMsg.value = null;
}

function sendQuick(text) {
  if (thinking.value) return;
  inputText.value = text;
  send();
}

async function send() {
  const text = inputText.value.trim();
  if (!text || thinking.value) return;
  inputText.value = '';
  if (inputRef.value) inputRef.value.style.height = 'auto';

  if (!currentSessionId.value) currentSessionId.value = createSession();

  const history = currentMessages.value
    .filter(m => m.role === 'user' || (m.role === 'assistant' && m.content))
    .slice(-10)
    .map(m => ({ role: m.role, content: m.content }));

  const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  const userMsg = { id: ++msgId, role: 'user', content: text, time: now };
  pushMsg(userMsg);
  await scrollBottom();

  thinking.value = true;
  const aiMsg = {
    id: ++msgId,
    role: 'assistant',
    content: '',
    toolCalls: [],
    suggests: [],
    streaming: true,
    time: '',
  };
  pushMsg(aiMsg);
  streamingMsg.value = aiMsg;

  const toolMap = {};

  setAbort(chatStream(text, history, {
    onText(chunk) {
      aiMsg.content += chunk;
      scrollBottom();
    },
    onToolCall(data) {
      const key = `${data.tool}_${data.callIdx}`;
      const tc = { tool: data.tool, label: data.label || data.tool, status: 'running', data: null, callIdx: data.callIdx };
      toolMap[key] = tc;
      aiMsg.toolCalls.push(tc);
      scrollBottom();
    },
    onToolResult(data) {
      const tc = toolMap[`${data.tool}_${data.callIdx}`];
      if (tc) tc.status = data.success ? 'done' : 'error';
    },
    onToolResultData(data) {
      const tc = toolMap[`${data.tool}_${data.callIdx}`];
      if (tc) tc.data = data.data;
    },
    onSuggest(list) {
      aiMsg.suggests = list;
      saveSessions();
      scrollBottom();
    },
    onDone() {
      aiMsg.streaming = false;
      aiMsg.time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      thinking.value = false;
      streamingMsg.value = null;
      setAbort(null);
      saveSessions();
      scrollBottom();
    },
    onError(e) {
      aiMsg.role = 'error';
      aiMsg.content = e.message || '请求失败，请稍后重试';
      aiMsg.streaming = false;
      thinking.value = false;
      streamingMsg.value = null;
      setAbort(null);
      saveSessions();
      scrollBottom();
    },
  }));
}

onMounted(() => {
  if (!currentSessionId.value || !sessions.value.find(s => s.id === currentSessionId.value)) {
    currentSessionId.value = createSession();
  }
  nextTick(() => inputRef.value?.focus());
});
</script>

<style scoped>
/* 保留 .page-agent 作为本页专用根节点：这一页需要撑满高度并内部滚动
   （左侧会话列表 / 右侧对话区各自滚），与其它按内容撑高的页面诉求不同。
   因此不套用全局 .page 的 padding+gap，但共用同一套颜色与字号令牌。 */
.page-agent { flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
/* grid-template-rows 必须显式约束为 minmax(0, 1fr)。
   默认值是 auto —— 网格行会被内容撑高：实测 25 条历史对话时侧栏长到 1701px、
   整页纵向溢出 811px，而 .session-list 的 scrollHeight === clientHeight，
   根本没在滚动，内容直接把页面顶下去（用户看到的"突破整体边界"）。
   minmax(0, 1fr) 让行高固定为容器高度、并允许收缩到小于内容，
   子元素的 overflow-y:auto 才真正生效。 */
.agent-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  grid-template-rows: minmax(0, 1fr);
  flex: 1 1 auto;
  min-height: 0;
}

/* ══ 左侧 ══ */
.side-panel {
  display: flex; flex-direction: column; gap: 0;
  border-right: 1px solid var(--tint-3);
  overflow-y: auto; padding: 16px 14px;
  background: var(--tint-1);
  min-height: 0;   /* 允许收缩到小于内容，否则 overflow-y 形同虚设 */
}
.side-panel::-webkit-scrollbar { width: 3px; }
.side-panel::-webkit-scrollbar-thumb { background: var(--tint-3); border-radius: 2px; }

.new-chat-btn {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%; padding: 10px; border-radius: 10px;
  border: 1px dashed color-mix(in srgb, var(--primary) 40%, transparent); background: color-mix(in srgb, var(--primary) 6%, transparent);
  color: var(--primary-hover); font-size: 13px; font-weight: 600; cursor: pointer;
  transition: all .15s; margin-bottom: 16px; flex-shrink: 0;
}
.new-chat-btn:hover { background: color-mix(in srgb, var(--primary) 14%, transparent); border-color: color-mix(in srgb, var(--primary) 70%, transparent); }

.side-section-title { font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: .8px; margin-bottom: 8px; }

.session-list { flex: 1; display: flex; flex-direction: column; gap: 0; min-height: 0; overflow-y: auto; }
.session-list::-webkit-scrollbar { width: 2px; }
.session-empty { font-size: 12px; color: var(--text-muted); padding: 8px 0; }

.session-item {
  position: relative; padding: 9px 10px; border-radius: 9px; cursor: pointer;
  border: 1px solid transparent; transition: all .15s; margin-bottom: 2px; flex-shrink: 0;
}
.session-item:hover { background: var(--tint-2); border-color: var(--tint-3); }
.session-item.active { background: color-mix(in srgb, var(--primary) 10%, transparent); border-color: color-mix(in srgb, var(--primary) 25%, transparent); }
.session-preview { font-size: 12px; color: var(--text-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 20px; }
.session-item.active .session-preview { color: var(--primary-hover); font-weight: 600; }
.session-meta { font-size: 10px; color: var(--text-muted); margin-top: 2px; }
.session-del {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  width: 18px; height: 18px; border-radius: 4px; border: none;
  background: transparent; color: var(--text-muted); cursor: pointer; font-size: 14px;
  display: none; align-items: center; justify-content: center;
}
.session-item:hover .session-del { display: flex; }
.session-del:hover { background: color-mix(in srgb, var(--danger) 15%, transparent); color: var(--danger-text); }

/* 能力区：不用 margin-top:auto，而是固定在底部区域 */
.side-capabilities {
  flex-shrink: 0;
  padding-top: 16px;
  border-top: 1px solid var(--tint-3);
  margin-top: 16px;
}
.cap-grid { display: flex; flex-wrap: wrap; gap: 5px; }
.cap-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 8px; border-radius: 6px;
  background: var(--tint-1); border: 1px solid var(--tint-3);
  font-size: 11px; color: var(--text-tertiary);
}

.side-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 14px; flex-shrink: 0; }
.stat-box { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 8px; padding: 8px 4px; text-align: center; }
.stat-num { font-size: 18px; font-weight: 800; color: var(--primary-hover); }
.stat-lbl { font-size: 9px; color: var(--text-muted); margin-top: 1px; }

/* ══ 对话区 ══ */
.chat-area { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }

.chat-topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 20px; border-bottom: 1px solid var(--tint-3); flex-shrink: 0;
}
.topbar-left { display: flex; align-items: center; gap: 8px; }
.topbar-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.topbar-dot.ready    { background: var(--success); }
.topbar-dot.thinking { background: var(--warning); animation: blink 1s infinite; }
@keyframes blink { 0%,100%{opacity:1}50%{opacity:.3} }
.topbar-status { font-size: 12px; color: var(--text-tertiary); }
.ctx-badge { padding: 2px 8px; border-radius: 10px; font-size: 10px; background: var(--tint-2); border: 1px solid var(--tint-3); color: var(--text-muted); }
.topbar-right { display: flex; align-items: center; gap: 6px; }
.topbar-btn {
  padding: 5px 12px; border-radius: 7px; border: 1px solid var(--tint-3);
  background: transparent; color: var(--text-muted); font-size: 12px; cursor: pointer; transition: all .15s;
}
.topbar-btn:hover { background: var(--tint-2); color: var(--text-tertiary); }
.topbar-btn.danger { border-color: color-mix(in srgb, var(--danger) 30%, transparent); color: var(--danger-text); }
.topbar-btn.danger:hover { background: color-mix(in srgb, var(--danger) 10%, transparent); }

/* 消息流 */
.msg-stream {
  flex: 1; overflow-y: auto; padding: 20px;
  display: flex; flex-direction: column; gap: 14px; min-height: 0;
}
.msg-stream::-webkit-scrollbar { width: 4px; }
.msg-stream::-webkit-scrollbar-thumb { background: var(--tint-3); border-radius: 2px; }

/* 欢迎卡片 */
.welcome-card {
  margin: auto; max-width: 460px;
  background: var(--tint-1); border: 1px solid var(--tint-3);
  border-radius: 20px; padding: 28px; text-align: center;
}
.welcome-icon { font-size: 44px; margin-bottom: 10px; }
.welcome-title { font-size: 18px; font-weight: 800; color: var(--text-primary); margin-bottom: 6px; }
.welcome-sub { font-size: 13px; color: var(--text-tertiary); line-height: 1.7; margin-bottom: 18px; }
.welcome-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.welcome-chip {
  padding: 7px 14px; border-radius: 20px;
  border: 1px solid color-mix(in srgb, var(--primary) 25%, transparent); background: color-mix(in srgb, var(--primary) 6%, transparent);
  color: var(--primary-hover); font-size: 12px; cursor: pointer; transition: all .15s;
}
.welcome-chip:hover:not(:disabled) { background: color-mix(in srgb, var(--primary) 15%, transparent); }
.welcome-chip:disabled { opacity: .4; cursor: not-allowed; }

/* 消息行 */
.row-user, .row-ai { display: flex; align-items: flex-start; gap: 10px; }
.row-user { justify-content: flex-end; }

.avatar-user {
  width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--violet), var(--primary));
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: var(--text-on-color);
}
.avatar-ai {
  width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
  background: color-mix(in srgb, var(--primary) 12%, transparent); border: 1px solid color-mix(in srgb, var(--primary) 20%, transparent);
  display: flex; align-items: center; justify-content: center; font-size: 15px;
}

.bubble-user {
  max-width: 70%; padding: 10px 15px; border-radius: 16px 4px 16px 16px;
  background: linear-gradient(135deg, var(--primary), var(--violet)); color: var(--text-on-color);
  font-size: 14px; line-height: 1.6; word-break: break-word;
}
.bubble-ai-wrap { max-width: 76%; display: flex; flex-direction: column; gap: 6px; }
.bubble-ai {
  padding: 12px 15px; border-radius: 4px 16px 16px 16px;
  background: var(--tint-2); border: 1px solid var(--tint-3);
  color: var(--text-secondary); font-size: 14px; line-height: 1.7; word-break: break-word;
}
.bubble-error {
  max-width: 76%; padding: 11px 15px; border-radius: 4px 16px 16px 16px;
  background: color-mix(in srgb, var(--danger) 8%, transparent); border: 1px solid color-mix(in srgb, var(--danger) 20%, transparent);
  color: var(--danger-text); font-size: 14px;
}

.bubble-text :deep(strong) { color: var(--text-primary); font-weight: 700; }
.bubble-text :deep(em) { color: var(--violet-text); }
.bubble-text :deep(code) { background: var(--tint-4); padding: 2px 6px; border-radius: 4px; font-size: 12px; font-family: monospace; }
.bubble-text :deep(b) { color: var(--text-primary); display: block; margin-top: 6px; margin-bottom: 2px; }
.bubble-text :deep(ul) { margin: 6px 0 6px 16px; padding: 0; list-style: disc; }
.bubble-text :deep(li) { margin-bottom: 3px; color: var(--text-secondary); }

.bubble-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; border-top: 1px solid var(--tint-2); padding-top: 6px; }
.bubble-ts { font-size: 10px; color: var(--text-muted); }
.copy-btn { font-size: 11px; color: var(--text-muted); background: transparent; border: 1px solid var(--tint-3); border-radius: 5px; padding: 2px 8px; cursor: pointer; transition: all .15s; }
.copy-btn:hover { color: var(--text-tertiary); border-color: var(--tint-5); }
.copy-btn.copied { color: var(--success); border-color: color-mix(in srgb, var(--success) 30%, transparent); }

/* 工具调用轨迹 */
.tool-trace { background: var(--bg-inset); border: 1px solid var(--tint-3); border-radius: 10px; padding: 8px 10px; display: flex; flex-direction: column; gap: 5px; }
.tc-row { display: flex; align-items: center; gap: 7px; font-size: 12px; }
.tc-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.tc-row.running .tc-dot { background: var(--warning); animation: blink 1s infinite; }
.tc-row.done    .tc-dot { background: var(--success); }
.tc-row.error   .tc-dot { background: var(--danger); }
.tc-label { flex: 1; color: var(--text-tertiary); }
.tc-badge { padding: 1px 7px; border-radius: 10px; font-size: 10px; font-weight: 600; }
.tc-badge.running { background: color-mix(in srgb, var(--warning) 12%, transparent); color: var(--warning); }
.tc-badge.done    { background: color-mix(in srgb, var(--success) 12%, transparent); color: var(--success); }
.tc-badge.error   { background: color-mix(in srgb, var(--danger) 12%, transparent); color: var(--danger-text); }
.tc-expand-btn { padding: 1px 8px; border-radius: 8px; font-size: 10px; border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent); background: color-mix(in srgb, var(--primary) 8%, transparent); color: var(--primary-hover); cursor: pointer; transition: all .15s; }
.tc-expand-btn:hover { background: color-mix(in srgb, var(--primary) 18%, transparent); }
.tool-data { background: var(--bg-inset); border: 1px solid var(--tint-3); border-radius: 8px; padding: 8px 10px; margin-top: 2px; }
.tool-data pre { font-size: 11px; color: var(--text-tertiary); font-family: monospace; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; margin: 0; }

/* 推荐追问 */
.suggest-row { display: flex; flex-wrap: wrap; gap: 6px; }
.suggest-chip {
  padding: 5px 12px; border-radius: 16px; font-size: 12px;
  border: 1px solid color-mix(in srgb, var(--violet) 25%, transparent); background: color-mix(in srgb, var(--violet) 6%, transparent);
  color: var(--violet-text); cursor: pointer; transition: all .15s;
}
.suggest-chip:hover:not(:disabled) { background: color-mix(in srgb, var(--violet) 15%, transparent); border-color: color-mix(in srgb, var(--violet) 50%, transparent); }
.suggest-chip:disabled { opacity: .4; cursor: not-allowed; }

/* 打字光标 */
.typing-cur { display: inline-block; width: 7px; height: 14px; background: var(--primary-hover); border-radius: 2px; animation: cur-blink .8s ease infinite; vertical-align: text-bottom; margin-left: 2px; }
@keyframes cur-blink { 0%,100%{opacity:1}50%{opacity:0} }

.thinking-dots { display: flex; gap: 5px; align-items: center; padding: 2px 0; }
.thinking-dots span { width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); animation: th-pulse 1.2s ease-in-out infinite; }
.thinking-dots span:nth-child(2) { animation-delay: .2s; }
.thinking-dots span:nth-child(3) { animation-delay: .4s; }
@keyframes th-pulse { 0%,80%,100%{opacity:.3;transform:scale(.8)} 40%{opacity:1;transform:scale(1)} }

/* 快捷提问栏 */
.quick-bar {
  display: flex; gap: 6px; padding: 8px 20px;
  overflow-x: auto; flex-shrink: 0;
  border-top: 1px solid var(--tint-2);
}
.quick-bar::-webkit-scrollbar { display: none; }
.quick-chip {
  white-space: nowrap; padding: 5px 12px; border-radius: 16px; font-size: 12px;
  border: 1px solid var(--tint-3); background: var(--tint-1);
  color: var(--text-tertiary); cursor: pointer; transition: all .15s; flex-shrink: 0;
}
.quick-chip:hover:not(:disabled) { border-color: color-mix(in srgb, var(--primary) 30%, transparent); color: var(--primary-hover); background: color-mix(in srgb, var(--primary) 7%, transparent); }
.quick-chip:disabled { opacity: .4; cursor: not-allowed; }

/* 输入区 */
.input-dock { padding: 12px 20px 18px; flex-shrink: 0; }
.input-wrap {
  background: var(--tint-2); border: 1px solid var(--tint-4);
  border-radius: 14px; overflow: hidden; transition: border-color .2s;
}
.input-wrap.focused { border-color: color-mix(in srgb, var(--primary) 45%, transparent); }
.input-wrap textarea {
  width: 100%; background: transparent; border: none; outline: none;
  padding: 12px 14px 6px; color: var(--text-secondary); font-size: 14px; line-height: 1.6;
  resize: none; font-family: inherit; box-sizing: border-box;
}
.input-wrap textarea::placeholder { color: var(--text-muted); }
.input-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 4px 10px 10px 14px; }
.char-tip { font-size: 11px; color: var(--text-muted); }
.send-btn {
  padding: 7px 18px; border-radius: 9px; border: none;
  background: linear-gradient(135deg, var(--primary), var(--violet));
  color: var(--text-on-color); font-size: 13px; font-weight: 600; cursor: pointer;
  transition: opacity .2s, transform .15s;
}
.send-btn:hover:not(:disabled) { opacity: .9; transform: scale(1.02); }
.send-btn:disabled { opacity: .4; cursor: not-allowed; }

/* 响应式 */
@media (max-width: 900px) {
  .agent-layout { grid-template-columns: 1fr; }
  .side-panel { display: none; }
}
</style>
