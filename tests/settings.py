"""
Test settings for Django DynamoDB tests.
Self-contained - does not import from other settings.
"""

import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent

# Security settings
SECRET_KEY = "test-secret-key-for-ci-only"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Use SQLite for Django's built-in models (User, ContentType, etc.)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Don't migrate DynamoDB models using Django's migration system
MIGRATION_MODULES = {
    "django_dynamodb_backend": None,
}

# Installed apps for testing
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_dynamodb_backend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Test-specific settings
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
USE_I18N = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DynamoDB settings for testing - use environment variable or default to localstack
DYNAMODB_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
DYNAMODB_LOCAL_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:4566")

# Logging for tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django_dynamodb_backend": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
