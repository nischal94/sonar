FROM python:3.12-slim

# Create non-root user (UID 1000) early so subsequent dir creation can chown
# directly to it. Resolves Trivy DS-0002 (containers must specify USER).
RUN useradd --create-home --shell /bin/bash --uid 1000 sonar

# System deps for psycopg2-binary fallback, cryptography, etc. (still root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager) — into /bin (root-owned, world-readable)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Store the venv outside /app so the docker-compose volume mount
# (./backend:/app) does not clobber it at runtime.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Pre-create /app and /opt/venv with sonar ownership BEFORE dropping privileges,
# so `uv sync` can write to /opt/venv as the sonar user.
RUN mkdir -p /app /opt/venv && chown -R sonar:sonar /app /opt/venv

WORKDIR /app
USER sonar

# Copy only project metadata first for better layer caching
COPY --chown=sonar:sonar pyproject.toml ./

# Resolve and install all dependencies (including dev extras for pytest)
RUN uv sync --all-extras

# Make the venv binaries available without `uv run` prefix
ENV PATH="/opt/venv/bin:$PATH"

# Default command overridden by docker-compose per service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
