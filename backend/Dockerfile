FROM python:3.10-slim

# 1. Install system dependencies + Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy requirements first (better caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy everything
COPY . .

# 4. Set the PYTHONPATH so Python can find your modules
ENV PYTHONPATH=/app/backend
ENV PORT=10000

# 5. Move into the backend folder
WORKDIR /app/backend

# 6. Start with a very detailed command to catch errors
# We use 'main:app' because we are INSIDE the backend folder
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000", "--log-level", "debug"]