FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    REDIS_HOST=redis \
    REDIS_PORT=6379

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    python3-dev \
    netcat-traditional \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p /app/static/fonts /app/logs /app/instance

# Create entrypoint script
RUN echo '#!/bin/sh\n\
echo "Waiting for PostgreSQL..."\n\
while ! nc -z $DB_HOST $DB_PORT; do\n\
  sleep 0.1\n\
done\n\
echo "PostgreSQL started"\n\
\n\
echo "Waiting for Redis..."\n\
while ! nc -z $REDIS_HOST $REDIS_PORT; do\n\
  sleep 0.1\n\
done\n\
echo "Redis started"\n\
\n\
# Apply database migrations\n\
python -c "from app import db; db.create_all()"\n\
\n\
# Start Gunicorn server\n\
gunicorn --bind 0.0.0.0:$PORT --workers=4 --threads=2 --timeout=120 wsgi:app\n' > /app/entrypoint.sh

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Set environment variables for the container
ENV PORT=8000 \
    DB_HOST=postgres \
    DB_PORT=5432

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"] 