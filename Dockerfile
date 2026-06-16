# Use an official Python runtime
FROM python:3.11-slim

# Install system dependencies needed for voice (ffmpeg, opus)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run the bot
CMD ["python", "main.py"]
