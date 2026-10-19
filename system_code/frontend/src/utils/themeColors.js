/**
 * 把 CSS 自定义属性解析成**真实色值**，给 Canvas 用。
 *
 * 背景：`utils/overlay.js`（骨架绘制）与 `Monitor.vue`/`VideoDetect.vue` 的画布
 * 里原来全是写死的十六进制色值，而且清一色是**深色**主题下的值。
 * 画布不认识 `var(--x)`，所以只能写死 —— 但"只能写死"不等于"应该写死"：
 * 视频舞台在亮色主题下是浅灰蓝（--bg-stage: #e8eef6），在暗色主题下是近黑
 * （--bg-stage: #0c1524）。同一组写死的颜色不可能在两种底色上都可读。
 *
 * 这里在**运行时**读一次计算值并缓存；主题切换（html[data-theme] 变化）时
 * 自动失效。每次绘制都调 getComputedStyle 会非常慢（画布是逐帧画的），
 * 所以缓存是必须的，不是优化。
 */
import { LEVELS } from './levelColors.js';

const cache = new Map();
let watched = false;

function invalidate() {
  cache.clear();
}

function ensureWatcher() {
  if (watched || typeof document === 'undefined') return;
  watched = true;
  // 主题通过 html[data-theme] 切换（见 utils/theme.js），监听属性变化即可。
  new MutationObserver(invalidate).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
}

/**
 * 读取一个 CSS 变量的计算值。
 * @param {string} name 变量名，带或不带 `--` 前缀都可以
 * @param {string} fallback 变量未定义时的兜底色值（返回透明色会导致画布上"什么都没有"）
 */
export function resolveVar(name, fallback = '#64748b') {
  if (typeof window === 'undefined' || typeof document === 'undefined') return fallback;
  const key = name.startsWith('--') ? name : `--${name}`;
  if (cache.has(key)) return cache.get(key);
  ensureWatcher();
  const value = getComputedStyle(document.documentElement).getPropertyValue(key).trim();
  // 未定义的变量拿到空字符串 —— 必须兜底，否则 fillStyle 被赋空值后
  // Canvas 会**静默保持上一次的颜色**，画出谁也看不懂的结果。
  const out = value || fallback;
  cache.set(key, out);
  return out;
}

/** 等级色 / 等级浅底色的画布版本。 */
export function levelCanvasColor(level) {
  const t = String(level ?? '').toUpperCase();
  if (!LEVELS.includes(t)) return resolveVar('--text-muted');
  return resolveVar(`--level-${t.toLowerCase()}`);
}

export function levelCanvasSoft(level) {
  const t = String(level ?? '').toUpperCase();
  if (!LEVELS.includes(t)) return resolveVar('--tint-2');
  return resolveVar(`--level-${t.toLowerCase()}-soft`);
}

/** 测试用：清掉缓存，强制下次读新的主题值。 */
export function resetThemeColorCache() {
  cache.clear();
}
