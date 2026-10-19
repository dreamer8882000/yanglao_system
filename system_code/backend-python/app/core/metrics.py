"""In-process request metrics for the /monitor/performance dashboard.

The frontend SystemMonitor page calls ``GET /api/monitor/performance`` and reads
``cpu / memory / database / performance / requests / system``. That endpoint did
not exist (404). These counters are process-local and reset on restart, which is
the right granularity for an operational dashboard.
"""
import time
from collections import deque
from threading import Lock

PROCESS_START = time.time()


class RequestMetrics:
    def __init__(self, window: int = 500) -> None:
        self._lock = Lock()
        self._total = 0
        self._success = 0
        self._error = 0
        self._latencies: deque[float] = deque(maxlen=window)

    def record(self, status_code: int, elapsed_ms: float) -> None:
        with self._lock:
            self._total += 1
            if status_code >= 400:
                self._error += 1
            else:
                self._success += 1
            self._latencies.append(elapsed_ms)

    def snapshot(self) -> dict:
        with self._lock:
            latencies = list(self._latencies)
            avg = sum(latencies) / len(latencies) if latencies else 0.0
            return {
                'total': self._total,
                'success': self._success,
                'error': self._error,
                'avgResponseTime': round(avg, 2),
                'sampleSize': len(latencies),
            }


metrics = RequestMetrics()
