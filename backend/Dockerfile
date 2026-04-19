FROM python:3.14-slim

# System deps for psycopg2-binary fallback, cryptography, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Store the venv outside /app so the docker-compose volume mount
# (./backend:/app) does not clobber it at runtime
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Copy only project metadata first for better layer caching
COPY pyproject.toml ./

# Resolve and install all dependencies (including dev extras for pytest)
RUN uv sync --all-extras

# Make the venv binaries available without `uv run` prefix
ENV PATH="/opt/venv/bin:$PATH"

# Default command overridden by docker-compose per service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
