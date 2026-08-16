# Use official Python 3.12 slim Linux base image
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer outputs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Install Tesseract OCR binary and required language packs:
# English (eng), Hindi (hin), Gujarati (guj), Marathi (mar), Bengali (ben), Telugu (tel), Urdu (urd)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-guj \
    tesseract-ocr-mar \
    tesseract-ocr-ben \
    tesseract-ocr-tel \
    tesseract-ocr-urd \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose port
EXPOSE 5000

# Start Flask web server using Gunicorn production WSGI with dynamic Render PORT support
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT:-5000} api.index:app"]

