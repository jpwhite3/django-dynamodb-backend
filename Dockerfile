# Django DynamoDB Backend - Production Dockerfile

FROM python:3.15.0a8-slim as base

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

# --- Development stage ---

FROM base as development

USER root

COPY . /app/
RUN pip install -e ".[dev]"

RUN chown -R django:django /app

USER django

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]



# --- Test stage ---



FROM base as test

USER root

COPY . /app/
RUN pip install -e ".[dev]"

RUN chown -R django:django /app

USER root

CMD ["python", "-m", "pytest", "tests/"]



# --- Production stage ---

FROM base as production

USER root

COPY . /app/
RUN pip install .

RUN chown -R django:django /app

USER django

RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "django_dynamodb_backend.wsgi:application"]
