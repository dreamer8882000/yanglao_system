/**
 * 前端全局错误处理
 */

/**
 * 错误类型枚举
 */
export const ErrorType = {
  NETWORK: 'NETWORK_ERROR',
  API: 'API_ERROR',
  VALIDATION: 'VALIDATION_ERROR',
  PERMISSION: 'PERMISSION_ERROR',
  UNKNOWN: 'UNKNOWN_ERROR'
};

/**
 * 错误信息映射
 */
const errorMessages = {
  [ErrorType.NETWORK]: '网络连接失败，请检查网络后重试',
  [ErrorType.API]: 'API 接口异常',
  [ErrorType.VALIDATION]: '数据验证失败',
  [ErrorType.PERMISSION]: '权限不足，无法执行此操作',
  [ErrorType.UNKNOWN]: '未知错误，请稍后重试'
};

/**
 * 错误日志收集
 */
class ErrorLogger {
  constructor() {
    this.errors = [];
    this.maxSize = 100;
  }

  log(error, context = {}) {
    const entry = {
      message: error.message || String(error),
      stack: error.stack,
      type: this.detectErrorType(error),
      context,
      timestamp: new Date().toISOString(),
      url: window.location.href
    };

    this.errors.push(entry);
    
    // 保持队列大小
    if (this.errors.length > this.maxSize) {
      this.errors.shift();
    }

    // 开发环境打印详细信息
    if (import.meta.env.DEV) {
      console.error('🔴 Error:', entry);
    }

    return entry;
  }

  detectErrorType(error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      return ErrorType.NETWORK;
    }
    if (error.response) {
      return ErrorType.API;
    }
    if (error.name === 'ValidationError') {
      return ErrorType.VALIDATION;
    }
    if (error.status === 403 || error.status === 401) {
      return ErrorType.PERMISSION;
    }
    return ErrorType.UNKNOWN;
  }

  getRecentErrors(count = 10) {
    return this.errors.slice(-count);
  }

  clear() {
    this.errors = [];
  }

  export() {
    return JSON.stringify(this.errors, null, 2);
  }
}

export const errorLogger = new ErrorLogger();

/**
 * 统一错误处理函数
 */
export const handleError = (error, toast = null) => {
  const entry = errorLogger.log(error);
  
  // 显示用户友好的提示
  const message = errorMessages[entry.type] || error.message || errorMessages[ErrorType.UNKNOWN];
  
  if (toast) {
    toast.error(message);
  } else {
    console.error(message);
  }

  return entry;
};

/**
 * API 错误处理
 */
export const handleApiError = (error, toast = null) => {
  let message = '请求失败';
  
  if (error.response) {
    // HTTP 错误响应
    const status = error.response.status;
    const data = error.response.data;
    
    if (status === 401) {
      message = '登录已过期，请重新登录';
      // 触发登录跳转
      window.location.href = data?.redirectUrl || '/';
    } else if (status === 403) {
      message = '权限不足';
    } else if (status === 404) {
      message = '请求的资源不存在';
    } else if (status === 429) {
      message = '请求过于频繁，请稍后再试';
    } else if (status >= 500) {
      message = '服务器错误，请稍后重试';
    } else {
      message = data?.message || error.message || '请求失败';
    }
  } else if (error.request) {
    // 请求已发送但未收到响应
    message = '网络连接失败，请检查网络后重试';
  } else {
    // 其他错误
    message = error.message || '请求异常';
  }

  if (toast) {
    toast.error(message);
  }

  errorLogger.log(error, { type: 'api' });
  
  return message;
};

/**
 * 验证错误处理
 */
export const handleValidationError = (errors, toast = null) => {
  if (Array.isArray(errors)) {
    errors.forEach(err => {
      if (toast) {
        toast.warning(err);
      } else {
        console.warn('⚠️ Validation:', err);
      }
    });
  } else if (typeof errors === 'string') {
    if (toast) {
      toast.warning(errors);
    } else {
      console.warn('⚠️ Validation:', errors);
    }
  }
};

/**
 * Promise 错误捕获包装
 */
export const wrapAsync = (fn, toast = null) => {
  return async (...args) => {
    try {
      return await fn(...args);
    } catch (error) {
      handleError(error, toast);
      throw error;
    }
  };
};

/**
 * 组件错误边界辅助
 */
export const createErrorBoundary = (fallback) => {
  return {
    errorCaptured(err, instance, info) {
      handleError(err);
      return false; // 继续传播错误
    }
  };
};

export default {
  ErrorType,
  errorLogger,
  handleError,
  handleApiError,
  handleValidationError,
  wrapAsync,
  createErrorBoundary
};
