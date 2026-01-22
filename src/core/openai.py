"""OpenAI client with timing, retry logic, and performance monitoring."""

import logging
import time
from functools import lru_cache, wraps
from typing import Any, Callable, TypeVar

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Type var for generic function wrapping
F = TypeVar("F", bound=Callable[..., Any])

# Retry configuration
MAX_RETRIES = 3
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 10

# Latency thresholds for logging (milliseconds)
SLOW_CALL_THRESHOLD_MS = 2000
VERY_SLOW_CALL_THRESHOLD_MS = 5000


class OpenAIMetrics:
    """Tracks OpenAI API call metrics for monitoring."""

    def __init__(self, max_samples: int = 500):
        self._samples: list[dict] = []
        self._max_samples = max_samples
        self._total_calls = 0
        self._total_errors = 0
        self._total_retries = 0

    def record_call(
        self,
        operation: str,
        latency_ms: float,
        model: str,
        tokens_used: int | None = None,
        error: str | None = None,
        retries: int = 0,
    ) -> None:
        """Record an API call."""
        self._total_calls += 1
        if error:
            self._total_errors += 1
        self._total_retries += retries

        sample = {
            "operation": operation,
            "latency_ms": round(latency_ms, 2),
            "model": model,
            "tokens_used": tokens_used,
            "error": error,
            "retries": retries,
            "timestamp": time.time(),
        }
        self._samples.append(sample)

        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples:]

    def get_stats(self) -> dict:
        """Get aggregated stats."""
        if not self._samples:
            return {
                "total_calls": self._total_calls,
                "total_errors": self._total_errors,
                "total_retries": self._total_retries,
                "error_rate": 0,
                "avg_latency_ms": 0,
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
            }

        latencies = sorted([s["latency_ms"] for s in self._samples])
        total = len(latencies)
        error_count = sum(1 for s in self._samples if s.get("error"))

        return {
            "total_calls": self._total_calls,
            "total_errors": self._total_errors,
            "total_retries": self._total_retries,
            "error_rate": round(error_count / total * 100, 2) if total > 0 else 0,
            "avg_latency_ms": round(sum(latencies) / total, 2),
            "p50_latency_ms": round(latencies[int(total * 0.5)], 2),
            "p95_latency_ms": round(latencies[int(total * 0.95)], 2),
            "p99_latency_ms": round(latencies[min(int(total * 0.99), total - 1)], 2),
            "recent_samples": len(self._samples),
        }

    def get_stats_by_operation(self) -> dict:
        """Get stats grouped by operation type."""
        from collections import defaultdict

        by_op: dict[str, list[dict]] = defaultdict(list)
        for sample in self._samples:
            by_op[sample["operation"]].append(sample)

        result = {}
        for op, samples in by_op.items():
            latencies = sorted([s["latency_ms"] for s in samples])
            total = len(latencies)
            error_count = sum(1 for s in samples if s.get("error"))

            result[op] = {
                "count": total,
                "error_count": error_count,
                "avg_ms": round(sum(latencies) / total, 2),
                "p95_ms": round(latencies[int(total * 0.95)], 2) if total > 1 else round(latencies[0], 2),
            }

        return result


# Global metrics instance
_openai_metrics: OpenAIMetrics | None = None


def get_openai_metrics() -> OpenAIMetrics:
    """Get or create the global OpenAI metrics instance."""
    global _openai_metrics
    if _openai_metrics is None:
        _openai_metrics = OpenAIMetrics()
    return _openai_metrics


class TimedOpenAIClient:
    """OpenAI client wrapper with timing, retry logic, and metrics.

    This wrapper adds:
    - Automatic retry with exponential backoff for transient errors
    - Latency logging for all API calls
    - Metrics collection for monitoring
    """

    def __init__(self, client: OpenAI):
        self._client = client
        self._metrics = get_openai_metrics()
        self._settings = get_settings()

    @property
    def chat(self) -> "TimedChatCompletions":
        """Get the timed chat completions interface."""
        return TimedChatCompletions(self._client.chat.completions, self._metrics, self._settings)

    @property
    def embeddings(self) -> "TimedEmbeddings":
        """Get the timed embeddings interface."""
        return TimedEmbeddings(self._client.embeddings, self._metrics, self._settings)

    # Pass through other attributes to the underlying client
    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class TimedChatCompletions:
    """Chat completions with timing and retry logic."""

    def __init__(self, completions: Any, metrics: OpenAIMetrics, settings: Any):
        self._completions = completions
        self._metrics = metrics
        self._settings = settings

    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
        reraise=True,
    )
    def _create_with_retry(self, **kwargs: Any) -> Any:
        """Create chat completion with retry logic."""
        return self._completions.create(**kwargs)

    def create(self, **kwargs: Any) -> Any:
        """Create a chat completion with timing and optional retry.

        Args:
            **kwargs: Arguments to pass to the OpenAI API.

        Returns:
            The chat completion response.
        """
        model = kwargs.get("model", "unknown")
        start_time = time.perf_counter()
        retries = 0
        error_msg = None
        tokens_used = None

        try:
            # Use retry wrapper
            response = self._create_with_retry(**kwargs)

            # Extract token usage if available
            if hasattr(response, "usage") and response.usage:
                tokens_used = response.usage.total_tokens

            return response

        except (APIConnectionError, APITimeoutError, RateLimitError) as e:
            # These are retryable errors - tenacity will have exhausted retries
            error_msg = f"{type(e).__name__}: {str(e)}"
            retries = MAX_RETRIES - 1  # We tried MAX_RETRIES times
            logger.error(
                "OpenAI chat completion failed after %d retries: %s",
                retries,
                error_msg,
            )
            raise

        except Exception as e:
            # Non-retryable errors
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error("OpenAI chat completion error: %s", error_msg)
            raise

        finally:
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            # Record metrics
            self._metrics.record_call(
                operation="chat.completions.create",
                latency_ms=latency_ms,
                model=model,
                tokens_used=tokens_used,
                error=error_msg,
                retries=retries,
            )

            # Log based on latency
            log_msg = (
                f"OpenAI chat completion: model={model}, "
                f"latency={latency_ms:.2f}ms, tokens={tokens_used or 'N/A'}"
            )

            if error_msg:
                logger.error(log_msg + f", error={error_msg}")
            elif latency_ms > VERY_SLOW_CALL_THRESHOLD_MS:
                logger.warning(f"VERY SLOW OpenAI call: {log_msg}")
            elif latency_ms > SLOW_CALL_THRESHOLD_MS:
                logger.warning(f"SLOW OpenAI call: {log_msg}")
            else:
                logger.info(log_msg)


class TimedEmbeddings:
    """Embeddings with timing and retry logic."""

    def __init__(self, embeddings: Any, metrics: OpenAIMetrics, settings: Any):
        self._embeddings = embeddings
        self._metrics = metrics
        self._settings = settings

    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=MIN_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
        reraise=True,
    )
    def _create_with_retry(self, **kwargs: Any) -> Any:
        """Create embedding with retry logic."""
        return self._embeddings.create(**kwargs)

    def create(self, **kwargs: Any) -> Any:
        """Create embeddings with timing and optional retry.

        Args:
            **kwargs: Arguments to pass to the OpenAI API.

        Returns:
            The embeddings response.
        """
        model = kwargs.get("model", "unknown")
        start_time = time.perf_counter()
        retries = 0
        error_msg = None
        tokens_used = None

        try:
            response = self._create_with_retry(**kwargs)

            if hasattr(response, "usage") and response.usage:
                tokens_used = response.usage.total_tokens

            return response

        except (APIConnectionError, APITimeoutError, RateLimitError) as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            retries = MAX_RETRIES - 1
            logger.error(
                "OpenAI embeddings failed after %d retries: %s",
                retries,
                error_msg,
            )
            raise

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error("OpenAI embeddings error: %s", error_msg)
            raise

        finally:
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            self._metrics.record_call(
                operation="embeddings.create",
                latency_ms=latency_ms,
                model=model,
                tokens_used=tokens_used,
                error=error_msg,
                retries=retries,
            )

            log_msg = (
                f"OpenAI embeddings: model={model}, "
                f"latency={latency_ms:.2f}ms, tokens={tokens_used or 'N/A'}"
            )

            if error_msg:
                logger.error(log_msg + f", error={error_msg}")
            elif latency_ms > SLOW_CALL_THRESHOLD_MS:
                logger.warning(f"SLOW OpenAI embeddings: {log_msg}")
            else:
                logger.debug(log_msg)


@lru_cache
def get_openai_client() -> TimedOpenAIClient:
    """Get cached OpenAI client singleton with timing and retry logic.

    Returns:
        TimedOpenAIClient: OpenAI client instance with performance monitoring.
    """
    settings = get_settings()
    raw_client = OpenAI(api_key=settings.openai_api_key)
    return TimedOpenAIClient(raw_client)
