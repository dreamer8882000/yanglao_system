import dayjs from 'dayjs';
import { levelColor, levelSoft } from './levelColors.js';
export { showConfirm, confirmWarning, confirmDanger } from './confirm.js';

export function formatTime(val) {
  if (!val) return '-';
  return dayjs(val).format('MM-DD HH:mm');
}

export function formatDate(val) {
  if (!val) return '-';
  return dayjs(val).format('YYYY-MM-DD');
}

export function genderLabel(gender) {
  return gender === 2 ? '女' : '男';
}

/**
 * 等级色（文字/前景）。保留这两个函数名是因为调用点很多（告警中心、监控、
 * 老人档案共 8 处），但实现已经收敛到 utils/levelColors.js —— 它只返回
 * `var(--level-x)`，具体色值在 tokens.css 里按主题定义。
 *
 * 旧实现在这里又写了一套字面量，而且和 token 里的**不一样**：
 * LOW 是蓝的（token 是绿的）、MEDIUM 是 #f97316（token 是 #d97706 琥珀）、
 * 而且缺 NORMAL（于是"正常"落到灰色）。同一个等级在不同页面因此显示不同颜色。
 */
export function riskColor(level) {
  return levelColor(level);
}

export function riskBg(level) {
  return levelSoft(level);
}

export function showToast(message, type = 'info') {
  const existing = document.querySelector('.mali-toast-container');
  const container = existing || (() => {
    const c = document.createElement('div');
    c.className = 'mali-toast-container';
    const isMobile = window.innerWidth <= 768;
    Object.assign(c.style, {
      position: 'fixed',
      zIndex: '9999',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      pointerEvents: 'none',
      ...(isMobile
        ? { top: '70px', left: '50%', transform: 'translateX(-50%)', alignItems: 'center', width: 'calc(100% - 32px)' }
        : { top: '20px', right: '20px', alignItems: 'flex-end' }),
    });
    document.body.appendChild(c);
    return c;
  })();

  // 提示卡的底色/文字色改为跟随主题（原来写死 #131e2f / #e2e8f0，
  // 于是亮色主题下也会弹出一张深色卡片）。同时语义色改用 token，
  // 否则在亮色卡片上用的是暗色主题的色值。
  const colors = { success: 'var(--success-text)', error: 'var(--danger-text)',
                   warning: 'var(--warning-text)', info: 'var(--primary)' };
  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  const iconBg = {
    success: 'var(--success-soft)', error: 'var(--danger-soft)',
    warning: 'var(--warning-soft)', info: 'var(--primary-soft)',
  };

  const safeMessage = String(message).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');

  if (!document.querySelector('#mali-toast-style')) {
    const style = document.createElement('style');
    style.id = 'mali-toast-style';
    style.textContent = `
      @keyframes toastIn { 
        from { opacity:0; transform:translateY(-10px) scale(0.95); } 
        to { opacity:1; transform:translateY(0) scale(1); } 
      }
    `;
    document.head.appendChild(style);
  }

  const toast = document.createElement('div');
  Object.assign(toast.style, {
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border-default)',
    backdropFilter: 'blur(12px)',
    color: 'var(--text-primary)',
    padding: '14px 18px',
    borderRadius: 'var(--radius-lg)',
    fontSize: '13px',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    minWidth: '220px',
    maxWidth: '360px',
    // 外阴影走 --shadow-lg；原来这里还有一圈 `${colors[type]}20` 的 8 位十六进制
    // 透明度拼接 —— 色值现在可能是 var(...)，拼字符串会直接拼出非法颜色值，
    // 所以改用 border 表达同一条语义色描边。
    boxShadow: 'var(--shadow-lg)',
    borderColor: colors[type],
    pointerEvents: 'auto',
    animation: 'toastIn .3s cubic-bezier(0.34, 1.56, 0.64, 1)',
    opacity: '1',
    transition: 'all .3s ease',
    fontWeight: '500',
    lineHeight: '1.4',
  });

  toast.innerHTML = `
    <div style="width:28px;height:28px;border-radius:50%;background:${iconBg[type]};display:flex;align-items:center;justify-content:center;font-size:14px;color:${colors[type]};font-weight:700;flex-shrink:0;">${icons[type]}</div>
    <span style="flex:1;min-width:0;">${safeMessage}</span>
  `;

  container.appendChild(toast);

  let timer;
  const startTimer = () => {
    timer = setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(() => { 
        toast.remove(); 
        if (!container.children.length) container.remove(); 
      }, 300);
    }, 3500);
  };

  toast.addEventListener('mouseenter', () => clearTimeout(timer));
  toast.addEventListener('mouseleave', startTimer);
  toast.addEventListener('click', () => {
    clearTimeout(timer);
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 200);
  });

  startTimer();
}
