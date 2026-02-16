"""
Test settings that disable problematic Django systems for our DynamoDB tests.
"""

from django_dynamo_admin.settings import *

# Use SQLite for Django's built-in models (User, ContentType, etc.)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Don't migrate DynamoDB models using Django's migration system
MIGRATION_MODULES = {
    "dynamodb_adapter": None,
}

# Disable problematic Django apps for testing
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dynamodb_adapter",
    "tests",
]

# Test-specific settings
USE_TZ = True
TIME_ZONE = "UTC"

# DynamoDB settings for testing - use environment variable or default to localstack
import os

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
        "dynamodb_adapter": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
