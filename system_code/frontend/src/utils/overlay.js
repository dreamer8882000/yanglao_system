/**
 * 视频叠加层绘制 —— 实时监控与视频检测**共用**。
 *
 * 为什么抽成模块：这两个页面此前各自维护一份几乎相同的骨架/人脸框绘制代码，
 * 导致同一个改动要改两处、且很容易只改一处。你提出的"两个页面背景要协调"
 * 正是这类问题的表现：一边是 #050d1a、另一边是 #020617，观感不一致。
 * 现在底色由 --bg-stage 令牌统一，绘制逻辑也收敛到这里。
 *
 * 关于对比度（换浅色底后的关键）：
 *   原先底是近黑色，骨架直接用亮色画就够了。改成浅色舞台后，亮色（尤其是
 *   头部关键点的黄色）在浅底上几乎看不见。而视频内容本身可能亮也可能
 *   暗，任何单一颜色都不可能同时适配。因此改为**先描一层深色轮廓、再画彩色**：
 *   深色描边在浅色舞台与亮画面提供对比，彩色本体在暗画面上依然醒目。
 *
 * 关于色值来源（本次修正）：
 *   这里原先写死的 5 个骨架色与轮廓色**全部是深色主题下的取值**，而视频舞台
 *   在亮色主题下是浅灰蓝（--bg-stage: #e8eef6）、在暗色主题下才是近黑
 *   （#0c1524）。同一组写死的颜色不可能在两种底色上都可读。
 *   现在改成**运行时解析 tokens.css 的变量**（画布不认识 var()，只能解析），
 *   见 utils/themeColors.js —— 带缓存在主题切换时自动失效。
 *
 *   注意这些 getter 是**函数**而不是常量：常量会在模块首次求值时就把颜色定死，
 *   之后再切主题也不会变（这正是原来那批写死色值的问题）。
 */

import { resolveVar } from './themeColors.js';

// 骨架连线（COCO 17 点）
export const BONES = [
  [0, 1], [0, 2], [1, 3], [2, 4], [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
];

// 多人时按序号轮换颜色。这 5 个是"人"的标识色（不是告警等级色），
// 取的是各主题里语义明确、彼此差异大的 5 个色相。
const PERSON_TOKENS = ['--primary', '--success', '--warning', '--danger', '--violet'];

export function personColors() {
  return PERSON_TOKENS.map((t) => resolveVar(t));
}

export function personColor(index) {
  const list = personColors();
  return list[index % list.length];
}

/** 头部关键点单独着色，便于快速识别朝向 */
export function headColor() {
  return resolveVar('--warning-text');
}

/** 轮廓色：浅色底与亮画面上靠它提供对比（跟随主题的反色） */
export function haloColor() {
  return resolveVar('--overlay-halo');
}

/**
 * 把源图坐标映射到画布坐标。
 * fit='cover' 用于 object-fit:cover 的视频，'contain' 用于留边的场景。
 */
export function getVideoDisplayMapper(srcW, srcH, canvasW, canvasH, fit = 'cover') {
  const sourceW = Number(srcW || 0) || canvasW;
  const sourceH = Number(srcH || 0) || canvasH;
  const scale = fit === 'contain'
    ? Math.min(canvasW / sourceW, canvasH / sourceH)
    : Math.max(canvasW / sourceW, canvasH / sourceH);
  const drawW = sourceW * scale;
  const drawH = sourceH * scale;
  const offsetX = (canvasW - drawW) / 2;
  const offsetY = (canvasH - drawH) / 2;
  return {
    scale, offsetX, offsetY,
    point(x, y) { return [offsetX + x * scale, offsetY + y * scale]; },
    box(box) {
      const [x1, y1] = this.point(box[0], box[1]);
      const [x2, y2] = this.point(box[2], box[3]);
      return [x1, y1, x2, y2];
    },
  };
}

function valid(p) {
  return Array.isArray(p) && p[0] > 0 && p[1] > 0;
}

/** 描一圈深色轮廓的线段 */
function haloLine(ctx, ax, ay, bx, by, color, width) {
  ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by);
  ctx.strokeStyle = haloColor(); ctx.lineWidth = width + 3; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by);
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
}

/** 带深色描边的圆点 */
function haloDot(ctx, x, y, r, color) {
  ctx.beginPath(); ctx.arc(x, y, r + 1.6, 0, Math.PI * 2);
  ctx.fillStyle = haloColor(); ctx.fill();
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = color; ctx.fill();
}

/** 带深色描边的文字 */
function haloText(ctx, text, x, y, color) {
  ctx.font = 'bold 11px Inter, sans-serif';
  ctx.lineWidth = 3; ctx.strokeStyle = haloColor();
  ctx.strokeText(text, x, y);
  ctx.fillStyle = color; ctx.fillText(text, x, y);
}

export function drawSkeleton(ctx, map, keypoints, index = 0, person = {}) {
  if (!Array.isArray(keypoints) || !keypoints.length) return;
  const color = personColor(index);

  BONES.forEach(([a, b]) => {
    const pa = keypoints[a], pb = keypoints[b];
    if (!valid(pa) || !valid(pb)) return;
    const [ax, ay] = map.point(pa[0], pa[1]);
    const [bx, by] = map.point(pb[0], pb[1]);
    haloLine(ctx, ax, ay, bx, by, color, 2);
  });

  keypoints.forEach((p, idx) => {
    if (!valid(p)) return;
    const [x, y] = map.point(p[0], p[1]);
    haloDot(ctx, x, y, idx < 5 ? 3 : 3.6, idx < 5 ? headColor() : color);
  });

  const info = person.fallInfo || person.fall_info || {};
  const bodyBox = info.bodyBox || info.body_box;
  if (Array.isArray(bodyBox) && bodyBox.length === 4) {
    const [x1, y1] = map.point(bodyBox[0], bodyBox[1]);
    const trackId = person.trackId ?? person.track_id ?? info.trackId ?? info.track_id;
    haloText(ctx, trackId ? `PERSON #${trackId}` : `PERSON ${index + 1}`,
             x1 + 4, Math.max(14, y1 - 4), color);
  }
}

export function drawFaceBox(ctx, map, face, index = 0) {
  const raw = face.faceBox || face.face_box;
  if (!Array.isArray(raw) || raw.length !== 4) return;
  const [x1, y1, x2, y2] = map.box(raw);
  const color = resolveVar('--violet-text');
  ctx.lineWidth = 4; ctx.strokeStyle = haloColor();
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  ctx.lineWidth = 2; ctx.strokeStyle = color;
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

  const expr = (face.expressions || [])[0];
  const label = expr
    ? `${expr.className || expr.class_name}:${Number(expr.confidence || 0).toFixed(2)}`
    : (face.method || 'FACE');
  haloText(ctx, `FACE ${index + 1} ${label}`, x1 + 4, Math.max(14, y1 - 4), color);
}

/**
 * 圆角矩形路径（不带填充/描边，由调用方决定）。
 * 兼容未实现 ctx.roundRect 的环境。
 */
export function roundRectPath(ctx, x, y, w, h, r) {
  if (typeof ctx.roundRect === 'function') {
    ctx.beginPath(); ctx.roundRect(x, y, w, h, r); return;
  }
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r); ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h); ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

/**
 * 画面内的信息面板 —— 浅色版，与整体浅色体系一致。
 * 原先这里是近黑的 rgba(8,15,28,.88)，在浅色舞台上像一块"贴上去的黑板"。
 * 现在用白色半透明 + 细边，边框色仍取告警等级色，风险仍然一眼可辨。
 */
export function drawInfoPanel(ctx, x, y, w, h, accent, title, lines) {
  roundRectPath(ctx, x, y, w, h, 8);
  // 面板底跟随主题：亮色下是近白半透明，暗色下必须是深色半透明，
  // 否则黑底上的白面板会把画面糊掉一大块。
  ctx.fillStyle = resolveVar('--bg-panel-overlay');
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = accent;
  ctx.stroke();

  ctx.font = 'bold 13px Inter, sans-serif';
  ctx.fillStyle = accent;
  ctx.fillText(title, x + 10, y + 22);

  ctx.font = '12px Inter, sans-serif';
  ctx.fillStyle = resolveVar('--text-secondary');
  lines.forEach((line, i) => {
    if (line) ctx.fillText(String(line).slice(0, 66), x + 10, y + 44 + i * 22);
  });
}
