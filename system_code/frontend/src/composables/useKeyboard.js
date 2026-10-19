import { onMounted, onUnmounted } from 'vue';

export function useKeyboard(handlers) {
  const handleKeydown = (event) => {
    if (handlers.escape && event.key === 'Escape') {
      handlers.escape(event);
    }
    if (handlers.enter && event.key === 'Enter' && !event.shiftKey) {
      handlers.enter(event);
    }
    if (handlers.ctrlEnter && event.key === 'Enter' && event.ctrlKey) {
      handlers.ctrlEnter(event);
    }
  };

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown);
  });

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown);
  });

  return {
    handleKeydown,
  };
}

export function useEscapeKey(callback) {
  useKeyboard({
    escape: callback,
  });
}

export function useEnterKey(callback) {
  useKeyboard({
    enter: callback,
  });
}
