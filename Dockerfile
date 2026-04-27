FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

# Runtime shared libraries only (no compilers).
# libgomp1: OpenMP runtime required by torch / scikit-learn at import time.
# curl: used by HEALTHCHECK and is a tiny addition.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --only-binary=:all: blocks any source-build fallback so a missing wheel
# fails fast instead of silently triggering a C/C++ compile.
# spacy's en_core_web_sm is a model archive (no compilation) and is the
# single sdist we tolerate, hence the explicit allow.
RUN pip install --upgrade pip && \
    pip install \
        --only-binary=:all: \
        --no-binary=en-core-web-sm \
        -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

CMD ["python", "app.py"]
