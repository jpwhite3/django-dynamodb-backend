# Django DynamoDB Backend

A Django database backend and admin integration for Amazon DynamoDB. Run Django **100% on DynamoDB** — no PostgreSQL, MySQL, or SQLite required.

[![CI](https://github.com/jpwhite3/django-dynamodb-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/jpwhite3/django-dynamodb-backend/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-dynamodb-backend.svg)](https://pypi.org/project/django-dynamodb-backend/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2+](https://img.shields.io/badge/django-5.2+-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **100% DynamoDB**: Run Django without any relational database — sessions, users, and admin all on DynamoDB.
- **DynamoDB authentication**: Full user auth system with username/email GSIs, password hashing, and permissions.
- **DynamoDB sessions**: Session backend with automatic TTL-based expiration.
- **Django Admin**: Complete admin interface support with DynamoDB-specific optimizations.
- **Django ORM compatible**: Familiar QuerySet API, `Q` objects, aggregations, and more.
- **Migration system**: DynamoDB-specific table and index management.
- **Cost optimized**: Pay-per-request billing, fits within the AWS free tier for development.
- **Serverless ready**: Suitable for AWS Lambda deployments.

## Requirements

- Python 3.11+
- Django 5.2+
- `boto3`, `pynamodb` (installed automatically)

## Installation

```bash
pip install django-dynamodb-backend
```

This is currently a release candidate. If `pip` is selecting an older final release, pass `--pre`:

```bash
pip install --pre django-dynamodb-backend
```

## Configuration

### DynamoDB-only mode (recommended)

Run Django entirely on DynamoDB — ideal for serverless deployments:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",           # Required for admin
    "django.contrib.contenttypes",
    "django.contrib.sessions",       # Required for session middleware
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_dynamodb_backend",
    "django_dynamodb_backend.contrib.auth_dynamo",  # DynamoDB users
]

DATABASES = {
    "default": {
        "ENGINE": "django_dynamodb_backend.db",
        "NAME": "my_app",
        "OPTIONS": {
            "region_name": "us-east-1",
            # For local development against DynamoDB Local / LocalStack:
            # "endpoint_url": "http://localhost:8000",
            # "aws_access_key_id": "test",
            # "aws_secret_access_key": "test",
        },
    }
}

# Sessions stored in DynamoDB with TTL
SESSION_ENGINE = "django_dynamodb_backend.sessions"
DYNAMODB_SESSION_TABLE_NAME = "django_sessions"

# Authentication backed by DynamoDB with GSIs on username and email
AUTH_USER_MODEL = "auth_dynamo.DynamoUser"
DYNAMODB_USER_TABLE_NAME = "django_users"
AUTHENTICATION_BACKENDS = [
    "django_dynamodb_backend.contrib.auth_dynamo.backends.DynamoAuthBackend",
]
```

### Create tables

```bash
# Sessions table (with TTL)
python manage.py dynamodb_create_session_table

# Users table (with GSIs); optionally seed an admin user
python manage.py dynamodb_create_user_table --create-admin

# Or create a superuser interactively (like Django's createsuperuser)
python manage.py dynamodb_createsuperuser

# Your app's tables
python manage.py dynamodb_migrate
```

### Hybrid mode

Use DynamoDB for your application models while keeping PostgreSQL/SQLite for Django's built-in apps:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_dynamodb_backend",
]

DATABASES = {
    "default": {
        "ENGINE": "django_dynamodb_backend.db",
        "NAME": "my_app",
        "OPTIONS": {"region_name": "us-east-1"},
    }
}
```

## Defining models

```python
from django.db import models
from django_dynamodb_backend.models import DynamoDBModel


class BlogPost(DynamoDBModel):
    id = models.CharField(primary_key=True, max_length=36)
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.CharField(max_length=100)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blog_posts"

    def __str__(self):
        return self.title
```

## Admin integration

```python
from django.contrib import admin
from django_dynamodb_backend.admin import DynamoDBAdmin
from .models import BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(DynamoDBAdmin):
    list_display = ["title", "author", "published", "created_at"]
    list_filter = ["published", "author"]
    search_fields = ["title", "content"]
```

## Management commands

| Command                                       | Description                              |
| --------------------------------------------- | ---------------------------------------- |
| `dynamodb_create_session_table`               | Create the sessions table with TTL       |
| `dynamodb_create_user_table`                  | Create the users table with GSIs         |
| `dynamodb_create_user_table --create-admin`   | Also create an admin user                |
| `dynamodb_createsuperuser`                    | Create a superuser interactively         |
| `dynamodb_migrate`                            | Apply DynamoDB migrations                |
| `dynamodb_makemigrations`                     | Create new migrations                    |
| `dynamodb_showmigrations`                     | Show migration status                    |
| `dynamodb_rollback`                           | Roll back migrations                     |
| `dynamodb_performance`                        | Monitor DynamoDB performance metrics     |

## DynamoDB table schemas

### Sessions table (`django_sessions`)

- **Partition key**: `session_key` (String)
- **TTL attribute**: `expire_date` (Unix timestamp)
- **Billing**: Pay-per-request

### Users table (`django_users`)

- **Partition key**: `id` (String, UUID)
- **GSI `username-index`**: lookup by username
- **GSI `email-index`**: lookup by email
- **Billing**: Pay-per-request

## Documentation

Full documentation lives in the [`docs/`](https://github.com/jpwhite3/django-dynamodb-backend/tree/main/docs) directory on GitHub:

| Document                                                                                                       | Description                                                |
| -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Documentation Index](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/INDEX.md)             | Map of all docs and reading paths                          |
| [Architecture](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/ARCHITECTURE.md)             | How the pieces fit together                                |
| [Migration Tutorial](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/MIGRATION_TUTORIAL.md) | Step-by-step guide to migrate existing Django projects     |
| [Django Compatibility](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/DJANGO_COMPATIBILITY.md) | Supported ORM features and limitations                   |
| [API Reference](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/API_REFERENCE.md)           | Complete API documentation                                 |
| [Deployment Guide](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/DEPLOYMENT_GUIDE.md)     | Production and AWS Lambda deployment                       |
| [Feature Walkthrough](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/FEATURE_WALKTHROUGH.md) | Detailed feature guide with examples                     |
| [Demo](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/docs/DEMO.md)                             | Run the bundled demo project locally                       |

## Contributing

Contributions welcome — see [CONTRIBUTING.md](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/CONTRIBUTING.md) for development setup, testing, and the pull request workflow.

## License

MIT — see [LICENSE](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/LICENSE).

## Links

- [GitHub repository](https://github.com/jpwhite3/django-dynamodb-backend)
- [PyPI package](https://pypi.org/project/django-dynamodb-backend/)
- [Issue tracker](https://github.com/jpwhite3/django-dynamodb-backend/issues)
- [Changelog](https://github.com/jpwhite3/django-dynamodb-backend/blob/main/CHANGELOG.md)
