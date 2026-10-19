<template>
  <div v-if="!isAgentPage" class="agent-root">

    <!-- 悬浮气泡按钮 -->
    <button
      class="agent-fab"
      :class="{ open: isOpen, thinking }"
      @click="toggle"
      title="护卫AI · 智能助手"
    >
      <span class="fab-icon">{{ thinking ? '⏳' : isOpen ? '×' : '🤖' }}</span>
      <span v-if="unread > 0 && !isOpen" class="fab-badge">{{ unread }}</span>
      <span class="fab-ring"></span>
    </button>

    <!-- 快捷面板 -->
    <transition name="panel-slide">
      <div v-if="isOpen" class="agent-panel" @click.stop>
        <div class="panel-header">
          <div class="header-left">
            <div class="ai-avatar">🤖</div>
            <div>
              <div class="ai-name">护卫AI</div>
              <div class="ai-status">
                <span class="status-dot" :class="thinking ? 'thinking' : 'online'"></span>
                {{ thinking ? '思考中…' : '随时待命' }}
              </div>
            </div>
          </div>
          <div class="header-right">
            <button class="icon-btn" @click="goFullPage" title="完整对话页">⛶</button>
            <button class="icon-btn" @click="clearMessages" title="清空对话">🗑</button>
            <button class="icon-btn" @click="isOpen = false" title="关闭">×</button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="panel-messages" ref="msgListRef">
          <div v-if="!messages.length" class="welcome-block">
            <div class="welcome-title">你好，我是护卫AI 👋</div>
            <div class="welcome-sub">可以帮你查询告警、老人状态、值班排班等</div>
            <div class="quick-btns">
              <button v-for="q in quickQuestions" :key="q" class="quick-btn" @click="send(q)">{{ q }}</button>
            </div>
          </div>

          <div v-for="(msg, i) in messages" :key="i" class="msg-row" :class="msg.role">
            <div class="msg-bubble">
              <div v-if="msg.toolSteps && msg.toolSteps.length" class="tool-steps">
                <div v-for="(step, si) in msg.toolSteps" :key="si" class="tool-step" :class="{ done: step.done, error: step.error }">
                  <span class="step-icon">{{ step.done ? (step.error ? '❌' : '✅') : '⏳' }}</span>
                  <span class="step-label">{{ step.label }}</span>
                </div>
              </div>
              <div class="msg-text" v-html="renderText(msg.content)"></div>
              <div v-if="msg.streaming" class="cursor-blink">▋</div>
            </div>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="panel-input">
          <textarea
            ref="inputRef"
            v-model="inputText"
            placeholder="输入消息，Enter 发送…"
            rows="1"
            class="input-area"
            @keydown.enter.prevent="onEnter"
            @input="autoResize"
          ></textarea>
          <button class="send-btn" :disabled="!inputText.trim() || thinking" @click="send()">
            {{ thinking ? '…' : '↑' }}
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { chatStream } from '../api/agent.js';

const router    = useRouter();
const isOpen    = ref(false);
const thinking  = ref(false);
const unread    = ref(0);
const inputText = ref('');
const messages  = ref([]);
const msgListRef = ref(null);
const inputRef   = ref(null);

const route = useRoute();
const isAgentPage = computed(() => route.path === '/agent');

// 历史记录（仅 role+content，不带 toolSteps）
const history = ref([]);

let abortFn = null;

const quickQuestions = [
  '今天系统情况怎样？',
  '有哪些未处理的告警？',
  '今日谁在值班？',
  '摄像头有没有离线？',
];

function toggle() {
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    unread.value = 0;
    nextTick(() => { inputRef.value?.focus(); scrollBottom(); });
  }
}

function goFullPage() {
  isOpen.value = false;
  router.push('/agent');
}

function clearMessages() {
  messages.value = [];
  history.value  = [];
}

function scrollBottom() {
  nextTick(() => {
    if (msgListRef.value) msgListRef.value.scrollTop = msgListRef.value.scrollHeight;
  });
}

function autoResize(e) {
  const el = e.target;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

function onEnter(e) {
  if (e.shiftKey) return;
  send();
}

function renderText(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

async function send(preset) {
  const text = (preset || inputText.value).trim();
  if (!text || thinking.value) return;
  inputText.value = '';

  messages.value.push({ role: 'user', content: text });
  history.value.push({ role: 'user', content: text });
  scrollBottom();

  const aiMsg = { role: 'assistant', content: '', toolSteps: [], streaming: true };
  messages.value.push(aiMsg);
  thinking.value = true;
  scrollBottom();

  const toolMap = {};

  abortFn = chatStream(text, history.value.slice(-10), {
    onText(chunk) {
      aiMsg.content += chunk;
      scrollBottom();
    },
    onToolCall(data) {
      const key = `${data.tool}_${data.callIdx}`;
      const step = { tool: data.tool, label: data.label || data.tool, done: false, error: false };
      toolMap[key] = step;
      aiMsg.toolSteps.push(step);
      scrollBottom();
    },
    onToolResult(data) {
      const step = toolMap[`${data.tool}_${data.callIdx}`];
      if (step) { step.done = true; step.error = !data.success; }
      scrollBottom();
    },
    onDone(content) {
      if (!aiMsg.content && content) aiMsg.content = content;
      aiMsg.streaming = false;
      thinking.value  = false;
      history.value.push({ role: 'assistant', content: aiMsg.content });
      if (!isOpen.value) unread.value++;
      scrollBottom();
    },
    onError(e) {
      aiMsg.content  = '请求失败：' + (e.message || '未知错误');
      aiMsg.streaming = false;
      thinking.value  = false;
      scrollBottom();
    },
  });
}

onUnmounted(() => { abortFn?.(); });
</script>

<style scoped>
/* ── 悬浮气泡 ── */
.agent-root { position: fixed; bottom: 28px; right: 28px; z-index: 2000; }

.agent-fab {
  width: 52px; height: 52px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--violet));
  border: none; cursor: pointer; color: var(--text-on-color);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 20px color-mix(in srgb, var(--primary) 45%, transparent);
  transition: transform .2s, box-shadow .2s;
  position: relative; overflow: visible;
}
.agent-fab:hover { transform: scale(1.1); box-shadow: 0 6px 28px color-mix(in srgb, var(--primary) 60%, transparent); }
.agent-fab.open  { transform: scale(1.05); }
.agent-fab.thinking .fab-icon { animation: spin 1.2s linear infinite; }

@keyframes spin { to { transform: rotate(360deg); } }

.fab-icon { font-size: 22px; }
.fab-badge {
  position: absolute; top: -3px; right: -3px;
  background: var(--danger); color: var(--text-on-color);
  font-size: 10px; font-weight: 700;
  min-width: 18px; height: 18px; padding: 0 4px;
  border-radius: 9px; display: flex; align-items: center; justify-content: center;
  border: 2px solid var(--text-primary);
}
.fab-ring {
  position: absolute; inset: -6px;
  border-radius: 50%; border: 2px solid color-mix(in srgb, var(--primary) 30%, transparent);
  animation: ring-pulse 2.5s infinite;
}
@keyframes ring-pulse { 0%,100%{opacity:.4;transform:scale(1)} 50%{opacity:0;transform:scale(1.3)} }

/* ── 面板 ── */
.agent-panel {
  position: absolute; bottom: 66px; right: 0;
  width: 360px; max-height: 520px;
  background: var(--bg-surface);
  border: 1px solid var(--tint-4);
  border-radius: 18px;
  box-shadow: 0 24px 60px color-mix(in srgb, var(--shadow-color) 60%, transparent), 0 0 0 1px color-mix(in srgb, var(--primary) 8%, transparent);
  display: flex; flex-direction: column; overflow: hidden;
}

/* 面板进入动画 */
.panel-slide-enter-active { transition: all .25s cubic-bezier(.34,1.56,.64,1); }
.panel-slide-leave-active { transition: all .18s ease-in; }
.panel-slide-enter-from  { opacity: 0; transform: translateY(16px) scale(.96); }
.panel-slide-leave-to    { opacity: 0; transform: translateY(10px) scale(.97); }

/* 头部 */
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--tint-3);
  background: var(--tint-1);
}
.header-left  { display: flex; align-items: center; gap: 10px; }
.header-right { display: flex; align-items: center; gap: 2px; }
.ai-avatar { width: 34px; height: 34px; background: linear-gradient(135deg, var(--primary), var(--violet)); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 17px; }
.ai-name   { font-size: 13px; font-weight: 700; color: var(--text-primary); }
.ai-status { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--text-tertiary); margin-top: 2px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; }
.status-dot.online   { background: var(--success); box-shadow: 0 0 5px var(--success)80; animation: blink 2s infinite; }
.status-dot.thinking { background: var(--warning); animation: blink .8s infinite; }
@keyframes blink { 0%,100%{opacity:1}50%{opacity:.3} }
.icon-btn { width: 30px; height: 30px; border-radius: 7px; border: none; background: transparent; color: var(--text-muted); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 14px; transition: background .15s; }
.icon-btn:hover { background: var(--tint-3); color: var(--text-tertiary); }

/* 消息列表 */
.panel-messages {
  flex: 1; overflow-y: auto; padding: 14px 14px 8px;
  display: flex; flex-direction: column; gap: 10px;
  scroll-behavior: smooth;
}
.panel-messages::-webkit-scrollbar { width: 3px; }
.panel-messages::-webkit-scrollbar-thumb { background: var(--tint-3); border-radius: 2px; }

.welcome-block { text-align: center; padding: 12px 0; }
.welcome-title { font-size: 14px; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px; }
.welcome-sub   { font-size: 12px; color: var(--text-muted); margin-bottom: 14px; }
.quick-btns    { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.quick-btn {
  padding: 6px 12px; border-radius: 20px; font-size: 12px;
  border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent); background: color-mix(in srgb, var(--primary) 8%, transparent);
  color: var(--primary-hover); cursor: pointer; transition: all .15s;
}
.quick-btn:hover { background: color-mix(in srgb, var(--primary) 16%, transparent); border-color: color-mix(in srgb, var(--primary) 50%, transparent); }

.msg-row       { display: flex; }
.msg-row.user  { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }

.msg-bubble {
  max-width: 86%; padding: 10px 13px; border-radius: 14px;
  font-size: 13px; line-height: 1.65; word-break: break-word;
}
.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, var(--primary), var(--primary-active));
  color: var(--text-on-color); border-bottom-right-radius: 4px;
}
.msg-row.assistant .msg-bubble {
  background: var(--tint-3);
  border: 1px solid var(--tint-3);
  color: var(--text-secondary); border-bottom-left-radius: 4px;
}

.tool-steps { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid var(--tint-3); }
.tool-step  { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-tertiary); }
.tool-step.done  { color: var(--success); }
.tool-step.error { color: var(--danger-text); }
.step-icon  { font-size: 11px; }

.msg-text :deep(strong) { color: var(--text-primary); }
.msg-text :deep(code)   { background: var(--tint-4); padding: 1px 5px; border-radius: 4px; font-size: 11px; }
.cursor-blink { display: inline-block; animation: blink .8s infinite; margin-left: 2px; color: var(--primary); }

/* 输入区 */
.panel-input {
  display: flex; align-items: flex-end; gap: 8px;
  padding: 10px 12px; border-top: 1px solid var(--tint-3);
  background: var(--tint-1);
}
.input-area {
  flex: 1; background: var(--tint-3); border: 1px solid var(--tint-4);
  border-radius: 10px; padding: 8px 10px; color: var(--text-secondary); font-size: 13px;
  resize: none; outline: none; font-family: inherit; line-height: 1.5;
  min-height: 36px; max-height: 100px; overflow-y: auto;
}
.input-area:focus { border-color: color-mix(in srgb, var(--primary) 50%, transparent); }
.input-area::placeholder { color: var(--text-muted); }
.send-btn {
  width: 36px; height: 36px; border-radius: 9px; border: none; flex-shrink: 0;
  background: linear-gradient(135deg, var(--primary), var(--violet));
  color: var(--text-on-color); font-size: 16px; cursor: pointer; transition: opacity .2s;
  display: flex; align-items: center; justify-content: center;
}
.send-btn:disabled { opacity: .35; cursor: not-allowed; }

/* 移动端适配 */
@media (max-width: 480px) {
  .agent-root  { bottom: 80px; right: 16px; }
  .agent-panel { width: calc(100vw - 32px); right: 0; }
}
</style>
