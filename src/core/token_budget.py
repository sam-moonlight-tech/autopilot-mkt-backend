"""In-memory token budget tracker for OpenAI usage limits."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class TokenBudgetConfig:
    """Configuration for token budgets."""

    daily_limit_anonymous: int = 75000  # Tokens per day for anonymous sessions
    daily_limit_authenticated: int = 250000  # Tokens per day for authenticated users
    cleanup_interval_seconds: int = 3600  # Cleanup expired entries every hour

    @classmethod
    def from_settings(cls) -> "TokenBudgetConfig":
        """Create config from application settings."""
        from src.core.config import get_settings
        settings = get_settings()
        return cls(
            daily_limit_anonymous=settings.token_budget_anonymous_daily,
            daily_limit_authenticated=settings.token_budget_authenticated_daily,
        )


@dataclass
class TokenUsageRecord:
    """Record of token usage for a user/session."""

    tokens_used: int = 0
    day_start: float = field(default_factory=lambda: TokenUsageRecord._get_day_start())

    @staticmethod
    def _get_day_start() -> float:
        """Get timestamp of start of current UTC day."""
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start.timestamp()

    def reset_if_new_day(self) -> bool:
        """Reset usage if a new day has started.

        Returns:
            bool: True if reset occurred.
        """
        current_day_start = self._get_day_start()
        if current_day_start > self.day_start:
            self.tokens_used = 0
            self.day_start = current_day_start
            return True
        return False

    def add_tokens(self, tokens: int) -> None:
        """Record token usage."""
        self.reset_if_new_day()
        self.tokens_used += tokens

    def get_remaining(self, limit: int) -> int:
        """Get remaining tokens for the day."""
        self.reset_if_new_day()
        return max(0, limit - self.tokens_used)

    def can_use(self, tokens: int, limit: int) -> bool:
        """Check if the requested tokens are within budget."""
        self.reset_if_new_day()
        return (self.tokens_used + tokens) <= limit


class TokenBudgetError(Exception):
    """Raised when token budget is exceeded."""

    def __init__(self, message: str, tokens_used: int, daily_limit: int):
        super().__init__(message)
        self.message = message
        self.tokens_used = tokens_used
        self.daily_limit = daily_limit
        self.retry_after = self._seconds_until_reset()

    @staticmethod
    def _seconds_until_reset() -> int:
        """Calculate seconds until the next UTC day."""
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Add one day
        tomorrow = tomorrow.replace(day=tomorrow.day + 1) if tomorrow.day < 28 else \
            tomorrow.replace(month=tomorrow.month + 1 if tomorrow.month < 12 else 1, day=1)
        return int((tomorrow - now).total_seconds())


class InMemoryTokenBudgetStorage:
    """Async-safe in-memory token budget storage with automatic cleanup."""

    def __init__(self, config: TokenBudgetConfig | None = None) -> None:
        self.config = config or TokenBudgetConfig()
        self._storage: dict[str, TokenUsageRecord] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Token budget cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Token budget cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup stale entries."""
        while True:
            await asyncio.sleep(self.config.cleanup_interval_seconds)
            count = await self.cleanup()
            if count > 0:
                logger.debug("Token budget cleaned up %d stale entries", count)

    async def check_budget(
        self,
        key: str,
        estimated_tokens: int,
        is_authenticated: bool,
    ) -> tuple[bool, int, int]:
        """Check if token budget allows the request.

        Args:
            key: Unique identifier (user_id or session_id).
            estimated_tokens: Estimated tokens for the request.
            is_authenticated: Whether this is an authenticated user.

        Returns:
            Tuple of (allowed, remaining_tokens, daily_limit).
        """
        limit = (
            self.config.daily_limit_authenticated
            if is_authenticated
            else self.config.daily_limit_anonymous
        )

        async with self._lock:
            if key not in self._storage:
                self._storage[key] = TokenUsageRecord()

            record = self._storage[key]
            record.reset_if_new_day()

            remaining = record.get_remaining(limit)
            allowed = record.can_use(estimated_tokens, limit)

            return (allowed, remaining, limit)

    async def record_usage(
        self,
        key: str,
        tokens_used: int,
    ) -> tuple[int, int]:
        """Record token usage after an API call.

        Args:
            key: Unique identifier (user_id or session_id).
            tokens_used: Actual tokens consumed.

        Returns:
            Tuple of (total_used_today, remaining_estimate).
        """
        async with self._lock:
            if key not in self._storage:
                self._storage[key] = TokenUsageRecord()

            record = self._storage[key]
            record.add_tokens(tokens_used)

            return (record.tokens_used, 0)  # Remaining calculated later with limit

    async def cleanup(self) -> int:
        """Remove entries from previous days."""
        current_day_start = TokenUsageRecord._get_day_start()
        removed = 0

        async with self._lock:
            keys_to_remove = []
            for key, record in self._storage.items():
                if record.day_start < current_day_start:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._storage[key]
                removed += 1

        return removed

    async def get_stats(self) -> dict:
        """Get storage statistics for monitoring."""
        async with self._lock:
            total_tokens = sum(r.tokens_used for r in self._storage.values())
            return {
                "active_trackers": len(self._storage),
                "total_tokens_today": total_tokens,
                "config": {
                    "daily_limit_anonymous": self.config.daily_limit_anonymous,
                    "daily_limit_authenticated": self.config.daily_limit_authenticated,
                },
            }

    async def get_usage(self, key: str, is_authenticated: bool) -> dict:
        """Get usage stats for a specific key."""
        limit = (
            self.config.daily_limit_authenticated
            if is_authenticated
            else self.config.daily_limit_anonymous
        )

        async with self._lock:
            if key not in self._storage:
                return {
                    "tokens_used": 0,
                    "daily_limit": limit,
                    "remaining": limit,
                    "percentage_used": 0,
                }

            record = self._storage[key]
            record.reset_if_new_day()

            return {
                "tokens_used": record.tokens_used,
                "daily_limit": limit,
                "remaining": record.get_remaining(limit),
                "percentage_used": int((record.tokens_used / limit) * 100),
            }


# Global singleton instance
_token_budget: InMemoryTokenBudgetStorage | None = None


def get_token_budget() -> InMemoryTokenBudgetStorage:
    """Get or create the global token budget instance."""
    global _token_budget
    if _token_budget is None:
        _token_budget = InMemoryTokenBudgetStorage(TokenBudgetConfig.from_settings())
    return _token_budget


async def init_token_budget() -> InMemoryTokenBudgetStorage:
    """Initialize token budget with cleanup task. Call at app startup."""
    budget = get_token_budget()
    await budget.start_cleanup_task()
    return budget


async def shutdown_token_budget() -> None:
    """Shutdown token budget cleanup task. Call at app shutdown."""
    global _token_budget
    if _token_budget:
        await _token_budget.stop_cleanup_task()
