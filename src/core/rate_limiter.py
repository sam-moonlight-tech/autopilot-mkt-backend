"""In-memory rate limiter for anonymous session users."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests_anonymous: int = 15  # Maximum requests for anonymous users
    max_requests_authenticated: int = 100  # Maximum requests for authenticated users
    window_seconds: int = 60  # Time window in seconds
    cleanup_interval_seconds: int = 300  # Cleanup expired entries every 5 minutes

    @classmethod
    def from_settings(cls) -> "RateLimitConfig":
        """Create config from application settings."""
        from src.core.config import get_settings
        settings = get_settings()
        return cls(
            max_requests_anonymous=settings.rate_limit_anonymous_requests,
            max_requests_authenticated=settings.rate_limit_authenticated_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )


@dataclass
class RequestRecord:
    """Record of requests for a session."""

    timestamps: list[float] = field(default_factory=list)

    def prune_old(self, window_seconds: int) -> None:
        """Remove timestamps older than the window."""
        cutoff = time.time() - window_seconds
        self.timestamps = [ts for ts in self.timestamps if ts > cutoff]

    def add_request(self) -> None:
        """Record a new request."""
        self.timestamps.append(time.time())

    def count_in_window(self, window_seconds: int) -> int:
        """Count requests within the time window."""
        cutoff = time.time() - window_seconds
        return sum(1 for ts in self.timestamps if ts > cutoff)

    def seconds_until_available(self, window_seconds: int, max_requests: int) -> int:
        """Calculate seconds until a new request slot is available."""
        if len(self.timestamps) < max_requests:
            return 0

        # Sort timestamps and find when the oldest will expire
        sorted_ts = sorted(self.timestamps)
        oldest_in_window = sorted_ts[-max_requests]
        return max(0, int(oldest_in_window + window_seconds - time.time()) + 1)


class InMemoryRateLimitStorage:
    """Thread-safe in-memory rate limit storage with automatic cleanup."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self._storage: dict[str, RequestRecord] = defaultdict(RequestRecord)
        self._lock = Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Rate limiter cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Rate limiter cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup expired entries."""
        while True:
            await asyncio.sleep(self.config.cleanup_interval_seconds)
            count = await self.cleanup()
            if count > 0:
                logger.debug("Rate limiter cleaned up %d expired entries", count)

    async def check_and_increment(
        self,
        key: str,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> tuple[bool, int, int]:
        """Check rate limit and increment if allowed.

        Args:
            key: Unique identifier (session_id).
            max_requests: Override max requests (uses config default).
            window_seconds: Override window (uses config default).

        Returns:
            Tuple of (allowed, remaining_requests, retry_after_seconds).
        """
        max_req = max_requests or self.config.max_requests
        window = window_seconds or self.config.window_seconds

        with self._lock:
            record = self._storage[key]
            record.prune_old(window)

            current_count = record.count_in_window(window)

            if current_count >= max_req:
                # Rate limited
                retry_after = record.seconds_until_available(window, max_req)
                return (False, 0, retry_after)

            # Allowed - record the request
            record.add_request()
            remaining = max_req - current_count - 1
            return (True, remaining, 0)

    async def cleanup(self) -> int:
        """Remove sessions with no recent requests."""
        window = self.config.window_seconds
        removed = 0

        with self._lock:
            keys_to_remove = []
            for key, record in self._storage.items():
                record.prune_old(window)
                if not record.timestamps:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._storage[key]
                removed += 1

        return removed

    def get_stats(self) -> dict:
        """Get storage statistics for monitoring."""
        with self._lock:
            return {
                "active_sessions": len(self._storage),
                "config": {
                    "max_requests_anonymous": self.config.max_requests_anonymous,
                    "max_requests_authenticated": self.config.max_requests_authenticated,
                    "window_seconds": self.config.window_seconds,
                },
            }


# Global singleton instance
_rate_limiter: InMemoryRateLimitStorage | None = None


def get_rate_limiter() -> InMemoryRateLimitStorage:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = InMemoryRateLimitStorage()
    return _rate_limiter


async def init_rate_limiter() -> InMemoryRateLimitStorage:
    """Initialize rate limiter with cleanup task. Call at app startup."""
    limiter = get_rate_limiter()
    await limiter.start_cleanup_task()
    return limiter


async def shutdown_rate_limiter() -> None:
    """Shutdown rate limiter cleanup task. Call at app shutdown."""
    global _rate_limiter
    if _rate_limiter:
        await _rate_limiter.stop_cleanup_task()
