# Django DynamoDB Admin - Production Dockerfile

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user
RUN groupadd --gid 1000 django \
    && useradd --uid 1000 --gid django --shell /bin/bash --create-home django

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Change ownership to django user
RUN chown -R django:django /app

# Switch to non-root user
USER django

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/admin/ || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "django_dynamo_admin.wsgi:application"]

# Development stage
FROM base as development

# Switch back to root for development dependencies
USER root

# Install development dependencies
COPY requirements-dev.txt /app/
RUN pip install --no-cache-dir -r requirements-dev.txt

# Install DynamoDB Local for development
RUN curl -o dynamodb_local_latest.tar.gz https://s3.us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.tar.gz \
    && tar -xzf dynamodb_local_latest.tar.gz \
    && rm dynamodb_local_latest.tar.gz

# Switch back to django user
USER django

# Override command for development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Production stage (default)
FROM base as production

# Production optimizations
ENV DJANGO_SETTINGS_MODULE=django_dynamo_admin.settings.production

# Ensure proper permissions
USER django

# Production command with gunicorn
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--worker-connections", "1000", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--timeout", "30", \
     "--keep-alive", "2", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "django_dynamo_admin.wsgi:application"]