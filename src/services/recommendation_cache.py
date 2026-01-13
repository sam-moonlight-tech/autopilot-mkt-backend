"""In-memory TTL cache for robot recommendations."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from hashlib import sha256
from threading import Lock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.roi import RecommendationsResponse

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached recommendation entry with expiration."""

    value: Any
    expires_at: float

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() > self.expires_at


@dataclass
class RecommendationCacheConfig:
    """Configuration for recommendation caching."""

    max_size: int = 500  # Maximum cached entries
    ttl_seconds: int = 3600  # 1 hour default
    cleanup_interval_seconds: int = 600  # Cleanup every 10 minutes

    @classmethod
    def from_settings(cls) -> "RecommendationCacheConfig":
        """Create config from application settings."""
        from src.core.config import get_settings
        settings = get_settings()
        return cls(
            max_size=settings.recommendation_cache_size,
            ttl_seconds=settings.recommendation_cache_ttl,
        )


class RecommendationCache:
    """Thread-safe in-memory cache for robot recommendations with TTL."""

    def __init__(self, config: RecommendationCacheConfig | None = None) -> None:
        """Initialize the recommendation cache.

        Args:
            config: Optional cache configuration.
        """
        self.config = config or RecommendationCacheConfig()
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Recommendation cache cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Recommendation cache cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup expired entries."""
        while True:
            await asyncio.sleep(self.config.cleanup_interval_seconds)
            count = self.cleanup()
            if count > 0:
                logger.debug("Recommendation cache cleaned up %d expired entries", count)

    def _generate_key(self, answers: dict) -> str:
        """Generate a deterministic cache key from discovery answers.

        Args:
            answers: Dictionary of discovery answers.

        Returns:
            A hash string suitable for use as a cache key.
        """
        # Extract just the values for consistent hashing
        simplified = {}
        for k, v in sorted(answers.items()):
            if isinstance(v, dict):
                simplified[k] = v.get("value", "")
            else:
                simplified[k] = str(v) if v else ""

        # Create deterministic JSON string
        json_str = json.dumps(simplified, sort_keys=True)
        return sha256(json_str.encode()).hexdigest()[:16]

    def get(self, answers: dict) -> "RecommendationsResponse | None":
        """Get cached recommendations if available and not expired.

        Args:
            answers: Discovery answers to look up.

        Returns:
            Cached RecommendationsResponse or None if not found/expired.
        """
        key = self._generate_key(answers)

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                logger.debug("Cache miss for key %s", key)
                return None

            if entry.is_expired():
                logger.debug("Cache expired for key %s", key)
                del self._cache[key]
                return None

            logger.debug("Cache hit for key %s", key)
            return entry.value

    def set(self, answers: dict, response: "RecommendationsResponse") -> None:
        """Cache recommendations with TTL.

        Args:
            answers: Discovery answers (used as key).
            response: RecommendationsResponse to cache.
        """
        key = self._generate_key(answers)
        expires_at = time.time() + self.config.ttl_seconds

        with self._lock:
            # Evict oldest entries if cache is full
            if len(self._cache) >= self.config.max_size:
                self._evict_oldest()

            self._cache[key] = CacheEntry(value=response, expires_at=expires_at)
            logger.debug("Cached recommendations for key %s (expires in %ds)", key, self.config.ttl_seconds)

    def _evict_oldest(self) -> None:
        """Evict oldest entries to make room. Must be called with lock held."""
        # First remove any expired entries
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]

        # If still at capacity, remove oldest 10%
        if len(self._cache) >= self.config.max_size:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].expires_at
            )
            to_remove = max(1, len(self._cache) // 10)
            for key, _ in sorted_entries[:to_remove]:
                del self._cache[key]
            logger.debug("Evicted %d entries from recommendation cache", to_remove)

    def cleanup(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared.
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info("Cleared %d entries from recommendation cache", count)
            return count

    def get_stats(self) -> dict:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache stats.
        """
        with self._lock:
            valid_count = sum(1 for v in self._cache.values() if not v.is_expired())
            return {
                "total_entries": len(self._cache),
                "valid_entries": valid_count,
                "expired_entries": len(self._cache) - valid_count,
                "max_size": self.config.max_size,
                "ttl_seconds": self.config.ttl_seconds,
            }


# Global singleton instance
_recommendation_cache: RecommendationCache | None = None


def get_recommendation_cache() -> RecommendationCache:
    """Get or create the global recommendation cache instance."""
    global _recommendation_cache
    if _recommendation_cache is None:
        _recommendation_cache = RecommendationCache(RecommendationCacheConfig.from_settings())
    return _recommendation_cache


async def init_recommendation_cache() -> RecommendationCache:
    """Initialize recommendation cache with cleanup task. Call at app startup."""
    cache = get_recommendation_cache()
    await cache.start_cleanup_task()
    return cache


async def shutdown_recommendation_cache() -> None:
    """Shutdown recommendation cache cleanup task. Call at app shutdown."""
    global _recommendation_cache
    if _recommendation_cache:
        await _recommendation_cache.stop_cleanup_task()
