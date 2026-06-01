FROM python:3.10-slim

# 1. Install system-level binaries required for Pytesseract, Pdf2image, and Docling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    libglib2.0-0 \
    libgomp1 \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy requirements first (better caching layer)
COPY backend/requirements.txt .

# 3. Upgrade pip and install requirements (including docling)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Copy everything else
COPY . .

# 5. Set the PYTHONPATH so Python can find your modules seamlessly
ENV PYTHONPATH=/app/backend
ENV PORT=8001

# 6. Move into the backend folder where main.py resides
WORKDIR /app/backend

# 7. Start the API app with your specific company production port
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4", "--log-level", "debug"]