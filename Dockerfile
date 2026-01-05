# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
# Build wheels with dependencies included
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install (including all dependencies)
COPY --from=builder /app/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache --find-links /wheels --no-index -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY pyproject.toml .

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment defaults
ENV APP_ENV=production \
    DEBUG=false \
    HOST=0.0.0.0 \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose port (Cloud Run will set PORT env var automatically)
EXPOSE 8080

# Health check (uses PORT env var, defaults to 8080)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run the application (Cloud Run sets PORT automatically)
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}
