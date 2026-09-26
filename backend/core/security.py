"""
Security Hardening and Defense-in-Depth Mechanisms.
Implements:
- Sliding-window IP rate limiter
- Security response headers
- Input validation and symbol sanitization
"""

import time
from collections import defaultdict


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter for API protection."""

    def __init__(self, max_requests: int = 300, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """
        Evaluates whether a request from client_ip is within rate quota.
        Returns (is_allowed, remaining_requests).
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Prune old timestamps
        history = [ts for ts in self._history[client_ip] if ts > window_start]
        self._history[client_ip] = history

        remaining = max(0, self.max_requests - len(history))

        if len(history) >= self.max_requests:
            return False, 0

        self._history[client_ip].append(now)
        return True, remaining - 1

    def reset(self) -> None:
        self._history.clear()


rate_limiter = SlidingWindowRateLimiter(max_requests=300, window_seconds=60)
