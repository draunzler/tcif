FROM python:3.12-slim

WORKDIR /app

# Install ffmpeg (needed by yt-dlp for some video processing)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY static/ ./static/

# Create data directory for game rotation state
RUN mkdir -p /app/data

# Expose port for web dashboard
EXPOSE 8000

# Set Python path to find the app module
ENV PYTHONPATH=/app

# Ensure logs are not buffered (important for Docker logs)
ENV PYTHONUNBUFFERED=1

# Run the main application (web server + scheduler)
CMD ["python3", "-m", "app.main"]
