FROM python:3.10-slim

# 1. Install system dependencies + Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 2. Set the working directory to the root of the app
WORKDIR /app

# 3. Copy requirements and install
# We use the path relative to the root context
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the entire project
COPY . .

# 5. Set Environment Variables so Python can find your code
ENV PYTHONPATH=/app/backend
ENV PORT=10000

# 6. Run from the directory where main.py actually exists
WORKDIR /app/backend

# 7. Start command - no 'backend.' prefix needed if we are inside the folder
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]