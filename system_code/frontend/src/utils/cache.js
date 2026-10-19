/**
 * 前端缓存管理工具
 * 基于 localStorage 和 sessionStorage
 */

/**
 * 缓存类型
 */
export const StorageType = {
  LOCAL: 'localStorage',
  SESSION: 'sessionStorage'
};

/**
 * 缓存管理器
 */
class CacheManager {
  constructor(type = StorageType.LOCAL, prefix = 'elderly_') {
    this.storage = window[type];
    this.prefix = prefix;
  }

  /**
   * 生成完整的 key
   */
  _getKey(key) {
    return `${this.prefix}${key}`;
  }

  /**
   * 设置缓存
   */
  set(key, value, ttl = null) {
    try {
      const data = {
        value,
        expireAt: ttl ? Date.now() + ttl : null
      };
      this.storage.setItem(this._getKey(key), JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('缓存写入失败:', error);
      return false;
    }
  }

  /**
   * 获取缓存
   */
  get(key, defaultValue = null) {
    try {
      const raw = this.storage.getItem(this._getKey(key));
      if (!raw) return defaultValue;

      const data = JSON.parse(raw);
      
      // 检查是否过期
      if (data.expireAt && Date.now() > data.expireAt) {
        this.remove(key);
        return defaultValue;
      }

      return data.value;
    } catch (error) {
      console.error('缓存读取失败:', error);
      return defaultValue;
    }
  }

  /**
   * 删除缓存
   */
  remove(key) {
    try {
      this.storage.removeItem(this._getKey(key));
      return true;
    } catch (error) {
      console.error('缓存删除失败:', error);
      return false;
    }
  }

  /**
   * 清空所有缓存
   */
  clear() {
    try {
      const keys = [];
      for (let i = 0; i < this.storage.length; i++) {
        const key = this.storage.key(i);
        if (key.startsWith(this.prefix)) {
          keys.push(key);
        }
      }
      keys.forEach(key => this.storage.removeItem(key));
      return true;
    } catch (error) {
      console.error('缓存清空失败:', error);
      return false;
    }
  }

  /**
   * 检查缓存是否存在
   */
  has(key) {
    return this.get(key) !== null;
  }

  /**
   * 获取所有缓存的 key
   */
  keys() {
    const keys = [];
    try {
      for (let i = 0; i < this.storage.length; i++) {
        const key = this.storage.key(i);
        if (key.startsWith(this.prefix)) {
          keys.push(key.replace(this.prefix, ''));
        }
      }
    } catch (error) {
      console.error('获取缓存 keys 失败:', error);
    }
    return keys;
  }

  /**
   * 获取缓存大小（字节）
   */
  size() {
    let total = 0;
    try {
      for (let i = 0; i < this.storage.length; i++) {
        const key = this.storage.key(i);
        if (key.startsWith(this.prefix)) {
          const value = this.storage.getItem(key);
          total += key.length + value.length;
        }
      }
    } catch (error) {
      console.error('计算缓存大小失败:', error);
    }
    return total;
  }
}

/**
 * 全局缓存实例
 */
export const localCache = new CacheManager(StorageType.LOCAL);
export const sessionCache = new CacheManager(StorageType.SESSION);

/**
 * 用户数据缓存
 */
export const userCache = {
  set(user) {
    sessionCache.set('user', user);
  },
  
  get() {
    return sessionCache.get('user');
  },
  
  clear() {
    sessionCache.remove('user');
  }
};

/**
 * Token 缓存
 */
export const tokenCache = {
  set(token, remember = false) {
    const cache = remember ? localCache : sessionCache;
    cache.set('token', token);
  },
  
  get() {
    return sessionCache.get('token') || localCache.get('token');
  },
  
  clear() {
    sessionCache.remove('token');
    localCache.remove('token');
  }
};

/**
 * 页面状态缓存
 */
export const pageStateCache = {
  set(page, state, ttl = 5 * 60 * 1000) {
    sessionCache.set(`page_${page}`, state, ttl);
  },
  
  get(page) {
    return sessionCache.get(`page_${page}`);
  },
  
  clear(page) {
    sessionCache.remove(`page_${page}`);
  }
};

/**
 * 表单草稿缓存
 */
export const draftCache = {
  save(formId, data) {
    localCache.set(`draft_${formId}`, data, 24 * 60 * 60 * 1000); // 保留 24 小时
  },
  
  load(formId) {
    return localCache.get(`draft_${formId}`);
  },
  
  clear(formId) {
    localCache.remove(`draft_${formId}`);
  }
};

/**
 * 清理过期缓存
 */
export const cleanupExpiredCache = () => {
  const keys = localCache.keys();
  keys.forEach(key => {
    localCache.get(key); // get 方法内部会自动清理过期项
  });
};

// 定期清理过期缓存（每小时）
if (typeof window !== 'undefined') {
  setInterval(cleanupExpiredCache, 60 * 60 * 1000);
}

export default {
  StorageType,
  CacheManager,
  localCache,
  sessionCache,
  userCache,
  tokenCache,
  pageStateCache,
  draftCache,
  cleanupExpiredCache
};
