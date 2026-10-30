# syntax=docker/dockerfile:1
# CloudLens backend (FastAPI + APScheduler)
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

ARG INSTALL_CLOUD_SDKS=true

# Core dependencies (small). The pip cache mount keeps already-downloaded wheels between
# builds, so a network hiccup only re-downloads what is missing on the next attempt.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
 && pip install -r requirements.txt

# Cloud SDKs (large: boto3, Azure, Google) in a separate layer, so a failure here
# does not throw away the core layer. Skip with INSTALL_CLOUD_SDKS=false in .env (mock mode).
COPY requirements-cloud.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$INSTALL_CLOUD_SDKS" = "true" ]; then pip install -r requirements-cloud.txt; fi

COPY app ./app

# run as an unprivileged user
RUN useradd --create-home --uid 10001 cloudlens
USER cloudlens

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# One worker on purpose: APScheduler runs inside the process, more workers would duplicate jobs.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
