# Pinned so a rebuild gets the same interpreter; bump deliberately.
FROM python:3.11.16-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

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

# Python's own HTTP client, so the image needs no curl and no apt layer: one
# tool fewer for anyone who gets a shell in the container. A non-2xx answer
# or no answer raises, which exits non-zero.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/health', timeout=4)"]

CMD ["python", "app.py"]
