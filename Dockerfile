# ── Stage 1: builder ──────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build deps (lxml needs gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Install Playwright system deps + browsers
RUN pip install --no-cache-dir playwright==1.52.0 \
    && playwright install chromium \
    && playwright install-deps chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY app/ ./app/
COPY static/ ./static/

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Graceful shutdown via SIGTERM (uvicorn default)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

