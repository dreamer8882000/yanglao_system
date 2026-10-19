/**
 * 数据加载组合式函数
 */

import { ref } from 'vue';
import { showToast } from '../utils/toast';

export function useAsyncData(fetchFn, options = {}) {
  const {
    immediate = false,
    onSuccess = null,
    onError = null,
    defaultValue = null
  } = options;

  const data = ref(defaultValue);
  const loading = ref(false);
  const error = ref(null);

  const execute = async (...args) => {
    loading.value = true;
    error.value = null;

    try {
      const result = await fetchFn(...args);
      data.value = result;
      onSuccess?.(result);
      return result;
    } catch (err) {
      error.value = err;
      onError?.(err);
      showToast(err.message || '加载失败', 'error');
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const refresh = () => execute();

  const reset = () => {
    data.value = defaultValue;
    error.value = null;
    loading.value = false;
  };

  if (immediate) {
    execute();
  }

  return {
    data,
    loading,
    error,
    execute,
    refresh,
    reset
  };
}
