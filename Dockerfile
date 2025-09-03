# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

# Prevents Python from writing .pyc files and buffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies for building and runtime (psycopg, pyaudio, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    portaudio19-dev \
    libasound2-dev \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy dependency files first
COPY requirements.txt ./

# Install Python dependencies
# Pre-built wheels will use AVX-512 when NPY_USE_AVX512=1 is set
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose app port
EXPOSE 8000

# Default environment
ENV HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=info

# CPU optimization environment variables for c7i instances
# Enable AVX-512 optimizations for NumPy and scientific computing
ENV NPY_USE_AVX512=1 \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    NUMEXPR_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2

# Start the server with uvicorn directly (no autoreload in container)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
