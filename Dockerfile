# Multi-stage / lightweight Debian-based container with LibreOffice & Tesseract
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TESSERACT_BIN=/usr/bin/tesseract \
    TESSERACT_LANG=vie+eng \
    TESSERACT_PSM=3 \
    OCR_DENSITY_THRESHOLD=50 \
    PORT=8000

# Install LibreOffice headless, Tesseract OCR with English and Vietnamese, and system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-core \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-vie \
    libmupdf-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY backend /app/backend
COPY frontend /app/frontend

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
