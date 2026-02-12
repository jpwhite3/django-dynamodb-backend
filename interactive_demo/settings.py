# Interactive Demo Settings for Django DynamoDB Admin
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings for demo
SECRET_KEY = "django-dynamo-admin-demo-key-change-in-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # DynamoDB integration
    "dynamodb_adapter",
    # Interactive demo applications
    "interactive_demo.apps.blog",
    "interactive_demo.apps.ecommerce",
    "interactive_demo.apps.social",
    "interactive_demo.apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "interactive_demo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "interactive_demo" / "templates"],
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

WSGI_APPLICATION = "interactive_demo.wsgi.application"

# DynamoDB Database Configuration
DATABASES = {
    "default": {
        "ENGINE": "django_dynamo_admin.database.base",
        "NAME": "interactive_demo",
        "OPTIONS": {
            "region_name": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "endpoint_url": os.environ.get(
                "DYNAMODB_ENDPOINT", "http://localhost:8000"
            ),
            "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "dummy"),
            "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "dummy"),
            "connection_pool_size": 10,
            "enable_query_cache": True,
            "cache_ttl": 300,
        },
    }
}

# Cache configuration using Redis
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "django_dynamo_demo",
        "TIMEOUT": 300,
    }
}

# Session configuration
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "interactive_demo" / "static",
]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DynamoDB specific settings
DYNAMODB_SETTINGS = {
    "TABLE_PREFIX": "demo_",
    "DEFAULT_READ_CAPACITY": 5,
    "DEFAULT_WRITE_CAPACITY": 5,
    "ENABLE_POINT_IN_TIME_RECOVERY": False,
    "ENABLE_STREAM": True,
    "STREAM_VIEW_TYPE": "NEW_AND_OLD_IMAGES",
    "GSI_SETTINGS": {
        "DEFAULT_READ_CAPACITY": 2,
        "DEFAULT_WRITE_CAPACITY": 2,
    },
}

# Enhanced Admin Configuration
DJANGO_DYNAMODB_ADMIN = {
    "ENABLE_PERFORMANCE_MONITORING": True,
    "ENABLE_COST_ESTIMATION": True,
    "ENABLE_GSI_OPTIMIZATION": True,
    "ENABLE_QUERY_CACHING": True,
    "CONNECTION_POOL_SIZE": 10,
    "PAGINATION_PER_PAGE": 50,
    "MAX_INLINE_ITEMS": 15,
    "ENABLE_AUDIT_LOGGING": True,
    "ADMIN_THEME": "enhanced",
}

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "demo.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "dynamodb_adapter": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "interactive_demo": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Create logs directory
(BASE_DIR / "logs").mkdir(exist_ok=True)

# Demo-specific settings
DEMO_SETTINGS = {
    "GENERATE_SAMPLE_DATA": True,
    "SAMPLE_DATA_SIZE": {
        "blog_posts": 100,
        "users": 50,
        "products": 200,
        "orders": 300,
        "social_posts": 500,
        "comments": 1000,
        "analytics_events": 2000,
    },
    "ENABLE_REAL_TIME_FEATURES": True,
    "SIMULATE_TRAFFIC": True,
}

# Performance monitoring
PERFORMANCE_MONITORING = {
    "TRACK_QUERY_PERFORMANCE": True,
    "TRACK_ADMIN_ACTIONS": True,
    "GENERATE_PERFORMANCE_REPORTS": True,
    "ALERT_SLOW_QUERIES": True,
    "SLOW_QUERY_THRESHOLD": 1.0,  # seconds
}
