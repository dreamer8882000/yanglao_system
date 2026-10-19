import request from './request.js';

export const getAgentTools = () => request.get('/agent/tools');

export function chatStream(message, history, callbacks = {}) {
  const token = sessionStorage.getItem('api_token');
  const base  = import.meta.env.VITE_API_BASE_URL || '';
  const ctrl  = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${base}/api/agent/chat`, {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
          'original-url':  window.location.href,
        },
        body:   JSON.stringify({ message, history }),
        signal: ctrl.signal,
      });

      if (!res.ok) {
        const txt = await res.text();
        callbacks.onError?.(new Error(`HTTP ${res.status}: ${txt.slice(0, 200)}`));
        return;
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        const blocks = buf.split('\n\n');
        buf = blocks.pop();

        for (const block of blocks) {
          let eventType = 'text';
          let dataStr   = '';

          for (const line of block.split('\n')) {
            if (line.startsWith('event: '))     eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) dataStr   = line.slice(6).trim();
          }

          if (!dataStr) continue;
          let parsed;
          try { parsed = JSON.parse(dataStr); } catch { continue; }

          if      (eventType === 'text')             callbacks.onText?.(parsed.text || '');
          else if (eventType === 'tool_call')        callbacks.onToolCall?.({ tool: parsed.tool, label: parsed.label, args: parsed.args, callIdx: parsed.callIdx ?? 0 });
          else if (eventType === 'tool_result')      callbacks.onToolResult?.({ tool: parsed.tool, success: parsed.success, error: parsed.error, callIdx: parsed.callIdx ?? 0 });
          else if (eventType === 'tool_result_data') callbacks.onToolResultData?.({ tool: parsed.tool, data: parsed.data, callIdx: parsed.callIdx ?? 0 });
          else if (eventType === 'suggest')          callbacks.onSuggest?.(parsed.list || []);
          else if (eventType === 'done')             callbacks.onDone?.(parsed.content || '');
          else if (eventType === 'error')            callbacks.onError?.(new Error(parsed.message));
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') callbacks.onError?.(e);
    }
  })();

  return () => ctrl.abort();
}
