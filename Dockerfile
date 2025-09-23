# Multi-stage build for understand-first
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir build setuptools wheel
RUN pip install --no-cache-dir -e .

# Copy source code
COPY . .

# Build the package
RUN python -m build

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash understand-first

# Set working directory
WORKDIR /app

# Copy built package from builder stage
COPY --from=builder /app/dist/*.whl ./
RUN pip install --no-cache-dir *.whl

# Copy examples and assets
COPY examples/ ./examples/
COPY assets/ ./assets/

# Change ownership to non-root user
RUN chown -R understand-first:understand-first /app

# Switch to non-root user
USER understand-first

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose ports for web services
EXPOSE 8000 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD u doctor || exit 1

# Default command
ENTRYPOINT ["u"]
CMD ["--help"]
