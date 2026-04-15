# Multi-stage build for understand-first (wheel-only runtime)
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml README.md ./
COPY cli ./cli/

RUN python -m pip install --upgrade pip build setuptools wheel \
    && python -m pip install --no-cache-dir -e . \
    && python -m build

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash understand-first

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /app/dist/*.whl ./
RUN python -m pip install --no-cache-dir ./*.whl && rm -f ./*.whl

COPY examples/ ./examples/
COPY assets/ ./assets/

RUN chown -R understand-first:understand-first /app

USER understand-first

EXPOSE 8000 50051

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD u doctor || exit 1

ENTRYPOINT ["u"]
CMD ["--help"]
