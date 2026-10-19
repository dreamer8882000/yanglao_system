"""Per-account / per-IP login throttling.

The login endpoint had **no failure limit at all**, so credentials could be
brute-forced without bound — and the documented defaults are weak
(``admin/123456``). This guard locks a (username, IP) pair after N failures
inside a rolling window.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


@dataclass
class _Attempt:
    failures: int = 0
    first_at: float = 0.0
    locked_until: float = 0.0


class LoginGuard:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 600,
                 lockout_seconds: int = 600) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.window = max(1, int(window_seconds))
        self.lockout = max(1, int(lockout_seconds))
        self._lock = Lock()
        self._attempts: dict[str, _Attempt] = {}

    @staticmethod
    def _key(username: str | None, ip: str | None) -> str:
        return f'{(username or "").strip().lower()}|{ip or "-"}'

    def remaining_lockout(self, username: str | None, ip: str | None,
                          now: float | None = None) -> float:
        """Seconds the caller is still blocked for (0.0 when allowed)."""
        now = time.time() if now is None else now
        with self._lock:
            attempt = self._attempts.get(self._key(username, ip))
            if attempt and attempt.locked_until > now:
                return attempt.locked_until - now
            return 0.0

    def record_failure(self, username: str | None, ip: str | None,
                       now: float | None = None) -> float:
        """Count one failure; returns the new lockout duration (0 if not locked)."""
        now = time.time() if now is None else now
        with self._lock:
            key = self._key(username, ip)
            attempt = self._attempts.get(key) or _Attempt()
            if attempt.first_at and now - attempt.first_at > self.window:
                attempt = _Attempt()          # rolling window expired
            if not attempt.first_at:
                attempt.first_at = now
            attempt.failures += 1
            if attempt.failures >= self.max_attempts:
                attempt.locked_until = now + self.lockout
                attempt.failures = 0          # restart counting after lockout
                attempt.first_at = 0.0
            self._attempts[key] = attempt
            return max(0.0, attempt.locked_until - now)

    def reset(self, username: str | None, ip: str | None) -> None:
        with self._lock:
            self._attempts.pop(self._key(username, ip), None)

    def cleanup(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            stale = [
                key for key, attempt in self._attempts.items()
                if attempt.locked_until <= now
                and (not attempt.first_at or now - attempt.first_at > self.window)
            ]
            for key in stale:
                self._attempts.pop(key, None)

    @property
    def tracked(self) -> int:
        with self._lock:
            return len(self._attempts)


guard = LoginGuard()
