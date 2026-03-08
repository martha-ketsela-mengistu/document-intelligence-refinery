# ── Stage 1: Dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install system build dependencies needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager used for this project)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first (for Docker layer caching)
COPY pyproject.toml uv.lock ./

# Install all dependencies into a virtual environment inside /app/.venv
RUN uv sync --frozen --no-dev --no-install-project


# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime system libraries (OpenCV, poppler-utils for PDF rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Make the venv's Python the default for this image
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application source code
COPY src/ ./src/
COPY main.py ./
COPY rubric/ ./rubric/

# Create runtime directories (will be overridden by volume mounts in production)
RUN mkdir -p data/uploads .refinery/profiles .refinery/pageindex

# Expose the FastAPI server port
EXPOSE 8000

# Health check — hits the /files endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/files || exit 1

# Default command: start the FastAPI server
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000"]
