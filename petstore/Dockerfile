# Stage 1: Builder
FROM python:3.11-slim-buster AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim-buster AS runtime

WORKDIR /app

# Install runtime dependencies (e.g., curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels from builder stage
COPY --from=builder /wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

# Copy application code
COPY petstore/app ./app
COPY alembic ./alembic
COPY alembic.ini .

# Expose the port FastAPI runs on
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# Command to run the application
# Use gunicorn with uvicorn workers for production readiness
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]