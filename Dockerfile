# Use a slim, modern Python image
FROM python:3.11-slim

# Environment setup for immediate logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python modules
COPY *.py .

# Create data directory and define it as a volume for persistence
RUN mkdir -p /app/data
VOLUME /app/data

# Run safely (and wait a bit for the database to be initialized)
CMD ["sh", "-c", "sleep 5 && python monitor.py"]