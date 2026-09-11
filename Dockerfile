# syntax=docker/dockerfile:1

# ---- Builder: install dependencies into an isolated venv ----
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /src
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only metadata first for better layer caching, then the package.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

# ---- Runtime: slim, non-root ----
FROM python:3.12-slim AS runtime

# Build metadata for /version (injected by CI via --build-arg).
ARG APP_VERSION=dev
ARG APP_COMMIT=unknown
ARG APP_BUILD_TIME=unknown

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HTTP_PORT=8080 \
    APP_VERSION=${APP_VERSION} \
    APP_COMMIT=${APP_COMMIT} \
    APP_BUILD_TIME=${APP_BUILD_TIME}

# Non-root user.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY app ./app

USER app
EXPOSE 8080

# Liveness check hitting /healthz via stdlib (no curl needed).
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os,sys,urllib.request; p=os.environ.get('HTTP_PORT','8080'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=3).status==200 else 1)"]

CMD ["python", "-m", "app"]
