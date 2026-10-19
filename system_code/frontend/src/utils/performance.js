/**
 * 前端性能优化工具
 */

import { debounce as _debounce, throttle as _throttle } from 'lodash-es';

/**
 * 防抖函数（高频输入场景）
 * @param {Function} fn 
 * @param {Number} delay 延迟时间（ms）
 */
export const debounce = (fn, delay = 300) => {
  return _debounce(fn, delay, { leading: false, trailing: true });
};

/**
 * 节流函数（高频事件场景）
 * @param {Function} fn 
 * @param {Number} interval 间隔时间（ms）
 */
export const throttle = (fn, interval = 200) => {
  return _throttle(fn, interval, { leading: true, trailing: true });
};

/**
 * 请求防抖（防止重复提交）
 */
export class RequestLock {
  constructor() {
    this.locks = new Map();
  }

  async run(key, fn) {
    if (this.locks.has(key)) {
      throw new Error('请勿重复提交');
    }
    
    this.locks.set(key, true);
    try {
      return await fn();
    } finally {
      this.locks.delete(key);
    }
  }
}

/**
 * 图片懒加载
 */
export const lazyLoadImage = (img, src) => {
  if (!img || !src) return;
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        img.src = src;
        observer.unobserve(img);
      }
    });
  });
  
  observer.observe(img);
};

/**
 * 长列表虚拟滚动辅助函数
 */
export const calculateVisibleRange = (scrollTop, itemHeight, containerHeight, totalItems) => {
  const start = Math.floor(scrollTop / itemHeight);
  const visibleCount = Math.ceil(containerHeight / itemHeight);
  const end = Math.min(start + visibleCount + 1, totalItems);
  
  return { start, end, visibleCount };
};

/**
 * 内存优化：大对象释放
 */
export const releaseMemory = (obj) => {
  if (!obj || typeof obj !== 'object') return;
  
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      delete obj[key];
    }
  }
};

/**
 * 性能监控：测量函数执行时间
 */
export const measurePerformance = async (name, fn) => {
  const start = performance.now();
  try {
    const result = await fn();
    const duration = performance.now() - start;
    console.log(`⏱️ [${name}] 执行时间: ${duration.toFixed(2)}ms`);
    return result;
  } catch (error) {
    const duration = performance.now() - start;
    console.error(`❌ [${name}] 执行失败 (${duration.toFixed(2)}ms):`, error);
    throw error;
  }
};

/**
 * 批量处理（分批执行，避免阻塞主线程）
 */
export const batchProcess = async (items, batchSize, processor) => {
  const results = [];
  
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    const batchResults = await Promise.all(batch.map(processor));
    results.push(...batchResults);
    
    // 让出主线程，避免长时间阻塞
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  
  return results;
};

export default {
  debounce,
  throttle,
  RequestLock,
  lazyLoadImage,
  calculateVisibleRange,
  releaseMemory,
  measurePerformance,
  batchProcess
};
