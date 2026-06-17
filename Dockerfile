FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# ENTRYPOINT ka use karein taaki script crash ho toh pata chale
ENTRYPOINT ["python", "main.py"]
