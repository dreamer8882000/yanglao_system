/**
 * 告警等级的**唯一**配色来源。
 *
 * 为什么需要这个文件：等级配色此前有 4 套互相矛盾的定义散在各处 ——
 *   utils/index.js  riskColor  {URGENT:'#7c3aed', HIGH:'#ef4444', MEDIUM:'#f97316', LOW:'#3b82f6'}
 *   Dashboard.vue / Monitor.vue / Evaluation.vue  三份逐字相同的 LEVEL_COLOR（用 token，这份是对的）
 *   VideoDetect.vue  {NORMAL:'#10b981', LOW:'#84cc16', MEDIUM:'#f59e0b', HIGH:'#ef4444', URGENT:'#b91c1c'}
 *   Alerts.vue       .alert-card.lvl-medium { border-left: 3px solid #f97316 }
 * 结果：同一个 LOW 在告警中心显示蓝色、在总览显示绿色；同一个 MEDIUM 有 4 个色值。
 *
 * 现在全部走 tokens.css 的 --level-*：
 *   值本身只在 tokens.css 定义一次（亮/暗各一份），主题切换自动跟随；
 *   这里导出的只是"等级名 → var(--level-x)"的映射，不含任何色值。
 *
 * 注意：返回的是 CSS 变量字符串，只能用于 DOM 样式（Vue 的 :style、<style>）。
 * Canvas 画布不认识 CSS 变量，需要用 utils/themeColors.js 里的 resolveVar()
 * 把变量解析成真实色值。
 */

export const LEVELS = ['NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'URGENT'];

/** 严重度**降序**（紧急在最前）。用于"先看最严重的"这类列表与堆叠图。 */
export const LEVELS_DESC = ['URGENT', 'HIGH', 'MEDIUM', 'LOW', 'NORMAL'];

/** 等级名 → token 名。键统一大写；未识别的等级一律回落到中性灰。 */
const TOKEN = {
  NORMAL: 'normal',
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  URGENT: 'urgent',
};

function tokenOf(level) {
  return TOKEN[String(level ?? '').toUpperCase()] || null;
}

/** 等级主色（用于实心背景、圆点、图表填充、在浅底上的文字）。 */
export function levelColor(level) {
  const t = tokenOf(level);
  return t ? `var(--level-${t})` : 'var(--text-muted)';
}

/** 等级浅底色（用于分级条、等级胶囊的大面积底色）。 */
export function levelSoft(level) {
  const t = tokenOf(level);
  return t ? `var(--level-${t}-soft)` : 'var(--tint-2)';
}

/** 等级 → 中文标签。与后端 services/notify_channels.py 的 LEVEL_LABEL 保持一致。 */
export const LEVEL_LABEL = {
  NORMAL: '正常',
  LOW: '低危',
  MEDIUM: '中危',
  HIGH: '高危',
  URGENT: '紧急',
};
