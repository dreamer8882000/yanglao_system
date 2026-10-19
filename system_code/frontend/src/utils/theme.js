/**
 * 主题切换：亮色为产品默认，可切深色并持久化。
 * tokens.css 中 :root 即亮色，[data-theme="dark"] 覆盖为深色。
 */
const KEY = 'ui_theme';
const LIGHT = 'light';
const DARK = 'dark';

export function currentTheme() {
  // 读不到偏好（隐私模式/被禁用）→ 回落到亮色，主题是纯外观，不值得打扰用户。
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === DARK || saved === LIGHT) return saved;
  } catch (e) { console.warn('主题偏好读取失败，使用默认亮色', e); }
  return LIGHT; // 亮色为主
}

export function applyTheme(theme) {
  const value = theme === DARK ? DARK : LIGHT;
  document.documentElement.setAttribute('data-theme', value);
  document.documentElement.style.colorScheme = value;
  try {
    localStorage.setItem(KEY, value);
  } catch {
    // 存不下就只在本次会话生效，界面已经是切换后的主题 —— 无需打扰用户。
  }
  return value;
}

export function toggleTheme() {
  return applyTheme(currentTheme() === DARK ? LIGHT : DARK);
}
