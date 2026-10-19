import { ref } from 'vue';

export function useThrottle(fn, delay = 300) {
  const isThrottled = ref(false);

  function throttledFn(...args) {
    if (isThrottled.value) {
      return;
    }

    fn.apply(this, args);
    isThrottled.value = true;

    setTimeout(() => {
      isThrottled.value = false;
    }, delay);
  }

  return {
    throttledFn,
    isThrottled,
  };
}

export function useClickThrottle(delay = 500) {
  const clicking = ref(false);

  async function handleClick(fn) {
    if (clicking.value) return;

    clicking.value = true;
    try {
      await fn();
    } finally {
      setTimeout(() => {
        clicking.value = false;
      }, delay);
    }
  }

  return {
    clicking,
    handleClick,
  };
}
