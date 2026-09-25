FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# curl is used by the container health check.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Fail fast instead of triggering a C/C++ source build when a wheel is missing.
RUN pip install --upgrade pip && \
    pip install --only-binary=:all: -r requirements.txt

COPY . .

# Run as an unprivileged user. Only runtime/data, which holds the SQLite
# database and its backups and is bind-mounted by compose.yaml, is writable.
RUN groupadd --system --gid 10001 winengine \
    && useradd --system --uid 10001 --gid winengine --home-dir /app --shell /usr/sbin/nologin winengine \
    && mkdir -p /app/runtime/data \
    && chown -R winengine:winengine /app/runtime
USER winengine

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

CMD ["python", "app.py"]
