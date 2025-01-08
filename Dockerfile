# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        # WeasyPrint dependencies
        python3-cffi \
        python3-brotli \
        libpango-1.0-0 \
        libharfbuzz0b \
        libpangoft2-1.0-0 \
        libffi-dev \
        shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.prod.txt .
RUN pip install --no-cache-dir -r requirements.prod.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create superuser and run gunicorn
RUN echo "from django.contrib.auth.models import User; User.objects.create_superuser('molesza', 'treasurer@eshowera.co.za', 'amandhla151081') if not User.objects.filter(username='molesza').exists() else None" | python manage.py shell

CMD gunicorn membership_comparison.wsgi:application --bind 0.0.0.0:8000
