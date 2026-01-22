"""Request latency logging middleware for performance monitoring."""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Thresholds for log levels (in milliseconds)
SLOW_REQUEST_THRESHOLD_MS = 1000  # Log as warning above 1s
VERY_SLOW_REQUEST_THRESHOLD_MS = 3000  # Log as error above 3s


async def latency_logging_middleware(request: Request, call_next: Callable) -> Response:
    """Middleware to log request latency and track performance.

    Logs timing information for every request, with elevated log levels
    for slow requests to help identify performance issues.

    Args:
        request: The incoming request.
        call_next: The next middleware/handler in the chain.

    Returns:
        Response: The response from the handler.
    """
    start_time = time.perf_counter()

    # Extract useful request info
    method = request.method
    path = request.url.path

    # Skip health checks from detailed logging (too noisy)
    is_health_check = path in ("/health", "/ready", "/live")

    response = None
    error_occurred = False

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        error_occurred = True
        raise
    finally:
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        # Build log context
        status_code = response.status_code if response else 500

        log_data = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "error": error_occurred,
        }

        # Add query params for non-health endpoints
        if not is_health_check and request.query_params:
            log_data["query_params"] = str(request.query_params)

        # Format log message
        log_msg = (
            f"{method} {path} - {status_code} - {latency_ms:.2f}ms"
        )

        # Choose log level based on latency and status
        if is_health_check:
            # Debug level for health checks
            if latency_ms > 100:  # Only log slow health checks
                logger.debug(log_msg, extra=log_data)
        elif error_occurred or status_code >= 500:
            logger.error(log_msg, extra=log_data)
        elif latency_ms > VERY_SLOW_REQUEST_THRESHOLD_MS:
            logger.error(
                f"VERY SLOW REQUEST: {log_msg}",
                extra=log_data,
            )
        elif latency_ms > SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                f"SLOW REQUEST: {log_msg}",
                extra=log_data,
            )
        elif status_code >= 400:
            logger.warning(log_msg, extra=log_data)
        else:
            logger.info(log_msg, extra=log_data)


class LatencyStats:
    """Simple in-memory stats tracker for request latencies.

    Useful for the /health endpoint to report average latencies.
    """

    def __init__(self, max_samples: int = 1000):
        self._samples: list[tuple[str, float]] = []  # (path, latency_ms)
        self._max_samples = max_samples

    def record(self, path: str, latency_ms: float) -> None:
        """Record a latency sample."""
        self._samples.append((path, latency_ms))
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples:]

    def get_stats(self) -> dict:
        """Get aggregated stats."""
        if not self._samples:
            return {
                "total_requests": 0,
                "avg_latency_ms": 0,
                "p50_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
            }

        latencies = sorted([s[1] for s in self._samples])
        total = len(latencies)

        return {
            "total_requests": total,
            "avg_latency_ms": round(sum(latencies) / total, 2),
            "p50_latency_ms": round(latencies[int(total * 0.5)], 2),
            "p95_latency_ms": round(latencies[int(total * 0.95)], 2),
            "p99_latency_ms": round(latencies[min(int(total * 0.99), total - 1)], 2),
        }

    def get_stats_by_path(self) -> dict:
        """Get stats grouped by path."""
        from collections import defaultdict

        by_path: dict[str, list[float]] = defaultdict(list)
        for path, latency in self._samples:
            # Normalize paths with IDs
            normalized = self._normalize_path(path)
            by_path[normalized].append(latency)

        result = {}
        for path, latencies in by_path.items():
            sorted_latencies = sorted(latencies)
            total = len(sorted_latencies)
            result[path] = {
                "count": total,
                "avg_ms": round(sum(sorted_latencies) / total, 2),
                "p95_ms": round(sorted_latencies[int(total * 0.95)], 2) if total > 1 else round(sorted_latencies[0], 2),
            }

        return result

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize path by replacing UUIDs with placeholders."""
        import re
        # Replace UUIDs with {id}
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        return re.sub(uuid_pattern, '{id}', path, flags=re.IGNORECASE)


# Global stats instance
_latency_stats: LatencyStats | None = None


def get_latency_stats() -> LatencyStats:
    """Get or create the global latency stats instance."""
    global _latency_stats
    if _latency_stats is None:
        _latency_stats = LatencyStats()
    return _latency_stats


async def latency_logging_with_stats_middleware(
    request: Request, call_next: Callable
) -> Response:
    """Enhanced middleware that also records stats for monitoring.

    Use this instead of latency_logging_middleware if you want
    to expose stats via the health endpoint.
    """
    start_time = time.perf_counter()

    method = request.method
    path = request.url.path
    is_health_check = path in ("/health", "/ready", "/live")

    response = None
    error_occurred = False

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        error_occurred = True
        raise
    finally:
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        # Record stats (skip health checks)
        if not is_health_check:
            get_latency_stats().record(path, latency_ms)

        status_code = response.status_code if response else 500

        log_msg = f"{method} {path} - {status_code} - {latency_ms:.2f}ms"

        if is_health_check:
            if latency_ms > 100:
                logger.debug(log_msg)
        elif error_occurred or status_code >= 500:
            logger.error(log_msg)
        elif latency_ms > VERY_SLOW_REQUEST_THRESHOLD_MS:
            logger.error(f"VERY SLOW REQUEST: {log_msg}")
        elif latency_ms > SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(f"SLOW REQUEST: {log_msg}")
        elif status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
