/**
 * 告警通知偏好（用户可控，持久化）。
 * 此前开关写死在 config 里，护士无法按自己的值班环境调整。
 */
const KEY = 'alert_notify_prefs';
const DEFAULTS = { sound: true, desktop: true };

export function getNotifyPrefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '{}');
    return { ...DEFAULTS, ...raw };
  } catch {
    return { ...DEFAULTS };
  }
}

export function setNotifyPref(key, value) {
  const next = { ...getNotifyPrefs(), [key]: !!value };
  // localStorage 可能因隐私模式或配额写不进去。这不影响本次会话的通知行为
  // （内存里的 next 已经返回给调用方），所以不打扰用户，但留一条日志。
  try { localStorage.setItem(KEY, JSON.stringify(next)); }
  catch (e) { console.warn('通知偏好写入 localStorage 失败（本次会话内仍生效）', e); }
  return next;
}

/** 分级音效：等级越高越急促、音调越高 */
const TONES = {
  URGENT: [880, 1180, 880],
  HIGH: [784, 1046],
  MEDIUM: [660],
  LOW: [523],
};

export function alertTones(level) {
  return TONES[String(level || '').toUpperCase()] || TONES.LOW;
}
