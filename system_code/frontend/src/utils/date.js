/**
 * 日期格式化工具
 * 基于 dayjs
 */

import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

/**
 * 格式化日期
 */
export const formatDate = (date, format = 'YYYY-MM-DD HH:mm:ss') => {
  if (!date) return '';
  return dayjs(date).format(format);
};

/**
 * 格式化为日期（不含时间）
 */
export const formatDateOnly = (date) => {
  return formatDate(date, 'YYYY-MM-DD');
};

/**
 * 格式化为时间（不含日期）
 */
export const formatTimeOnly = (date) => {
  return formatDate(date, 'HH:mm:ss');
};

/**
 * 格式化为相对时间
 */
export const formatRelative = (date) => {
  if (!date) return '';
  return dayjs(date).fromNow();
};

/**
 * 格式化为中文日期
 */
export const formatChinese = (date) => {
  if (!date) return '';
  return dayjs(date).format('YYYY年MM月DD日 HH:mm');
};

/**
 * 计算年龄
 */
export const calculateAge = (birthDate) => {
  if (!birthDate) return 0;
  return dayjs().diff(dayjs(birthDate), 'year');
};

/**
 * 计算日期差（天数）
 */
export const daysDiff = (date1, date2 = new Date()) => {
  return dayjs(date2).diff(dayjs(date1), 'day');
};

/**
 * 判断是否为今天
 */
export const isToday = (date) => {
  return dayjs(date).isSame(dayjs(), 'day');
};

/**
 * 判断是否为本周
 */
export const isThisWeek = (date) => {
  return dayjs(date).isSame(dayjs(), 'week');
};

/**
 * 判断是否为本月
 */
export const isThisMonth = (date) => {
  return dayjs(date).isSame(dayjs(), 'month');
};

/**
 * 获取日期范围
 */
export const getDateRange = (type) => {
  const now = dayjs();
  
  switch (type) {
    case 'today':
      return {
        start: now.startOf('day').format('YYYY-MM-DD HH:mm:ss'),
        end: now.endOf('day').format('YYYY-MM-DD HH:mm:ss')
      };
    
    case 'week':
      return {
        start: now.startOf('week').format('YYYY-MM-DD HH:mm:ss'),
        end: now.endOf('week').format('YYYY-MM-DD HH:mm:ss')
      };
    
    case 'month':
      return {
        start: now.startOf('month').format('YYYY-MM-DD HH:mm:ss'),
        end: now.endOf('month').format('YYYY-MM-DD HH:mm:ss')
      };
    
    case '7days':
      return {
        start: now.subtract(7, 'day').format('YYYY-MM-DD HH:mm:ss'),
        end: now.format('YYYY-MM-DD HH:mm:ss')
      };
    
    case '30days':
      return {
        start: now.subtract(30, 'day').format('YYYY-MM-DD HH:mm:ss'),
        end: now.format('YYYY-MM-DD HH:mm:ss')
      };
    
    default:
      return { start: '', end: '' };
  }
};

/**
 * 智能格式化日期
 * 根据时间远近自动选择格式
 */
export const formatSmart = (date) => {
  if (!date) return '';
  
  const d = dayjs(date);
  const now = dayjs();
  const diffMinutes = now.diff(d, 'minute');
  const diffHours = now.diff(d, 'hour');
  const diffDays = now.diff(d, 'day');

  // 1 分钟内
  if (diffMinutes < 1) {
    return '刚刚';
  }
  
  // 1 小时内
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }
  
  // 今天
  if (isToday(date)) {
    return `今天 ${d.format('HH:mm')}`;
  }
  
  // 昨天
  if (diffDays === 1) {
    return `昨天 ${d.format('HH:mm')}`;
  }
  
  // 本周
  if (isThisWeek(date)) {
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${weekdays[d.day()]} ${d.format('HH:mm')}`;
  }
  
  // 本年
  if (d.year() === now.year()) {
    return d.format('MM-DD HH:mm');
  }
  
  // 其他
  return d.format('YYYY-MM-DD');
};

/**
 * 验证日期格式
 */
export const isValidDate = (date) => {
  return dayjs(date).isValid();
};

/**
 * 获取星期几
 */
export const getWeekday = (date) => {
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  return weekdays[dayjs(date).day()];
};

/**
 * 格式化时长（秒）
 */
export const formatDuration = (seconds) => {
  if (!seconds || seconds < 0) return '0秒';
  
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  const parts = [];
  if (days > 0) parts.push(`${days}天`);
  if (hours > 0) parts.push(`${hours}小时`);
  if (minutes > 0) parts.push(`${minutes}分钟`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}秒`);
  
  return parts.join('');
};

/**
 * 解析日期范围字符串
 */
export const parseDateRange = (range) => {
  const [start, end] = range.split(' - ');
  return {
    start: dayjs(start).startOf('day').format('YYYY-MM-DD HH:mm:ss'),
    end: dayjs(end).endOf('day').format('YYYY-MM-DD HH:mm:ss')
  };
};

export default {
  formatDate,
  formatDateOnly,
  formatTimeOnly,
  formatRelative,
  formatChinese,
  formatSmart,
  calculateAge,
  daysDiff,
  isToday,
  isThisWeek,
  isThisMonth,
  getDateRange,
  isValidDate,
  getWeekday,
  formatDuration,
  parseDateRange
};
