FROM python:3.11-slim

# System dependencies install karein
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements install karein
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baaki files copy karein
COPY . .

# Bot start karne ki command
CMD ["python", "-u", "main.py"]
