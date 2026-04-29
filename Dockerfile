FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# curl is used by HEALTHCHECK only. No build tools, no ML runtime libs.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --only-binary=:all: blocks any source-build fallback so a missing wheel
# fails fast instead of triggering a C/C++ compile.
# en-core-web-sm is a model archive (no compile) — explicit allow.
RUN pip install --upgrade pip && \
    pip install \
        --only-binary=:all: \
        --no-binary=en-core-web-sm \
        -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

CMD ["python", "app.py"]
