# ============================================================
# DogovorAI — Docker Image
# Base: python:3.11-slim (Debian Bookworm)
# ============================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory inside container
WORKDIR /app

# ------------------------------------------------------------
# System dependencies
#   - tesseract-ocr      → required by pytesseract (OCR)
#   - tesseract-ocr-rus  → Russian language pack for Tesseract
#   - libpq-dev          → required by psycopg2 (PostgreSQL driver)
#   - libgl1             → required by PyMuPDF (PDF processing)
#   - libglib2.0-0       → required by PyMuPDF
#   - curl               → used for Docker HEALTHCHECK
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Python dependencies
# Copy requirements first to leverage Docker layer caching —
# this layer is only rebuilt when requirements.txt changes.
# ------------------------------------------------------------
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------
# Application source code
# ------------------------------------------------------------
COPY . .

# Create runtime directories (uploaded files, processed docs)
RUN mkdir -p /app/media /app/processed_documents

# Expose the application port
EXPOSE 8000

# ------------------------------------------------------------
# Healthcheck — Docker will mark container unhealthy if /health
# returns non-200 status for 3 consecutive checks.
# ------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ------------------------------------------------------------
# Start the FastAPI application
# --workers 2 is safe for most VPS (1 core = 2 workers)
# ------------------------------------------------------------
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
