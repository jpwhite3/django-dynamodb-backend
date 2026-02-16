# Django DynamoDB Backend

A Django database backend and admin integration for Amazon DynamoDB. Provides Django Admin compatibility with DynamoDB-specific optimizations.

[![CI](https://github.com/jpwhite3/django-dynamodb-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/jpwhite3/django-dynamodb-backend/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django 4.2+](https://img.shields.io/badge/django-4.2+-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Django Admin Integration**: Full admin interface support with DynamoDB
- **Custom Database Backend**: Django-compatible database backend for DynamoDB
- **Migration System**: DynamoDB-specific migration framework
- **Query Optimization**: Intelligent GSI selection and query optimization
- **Batch Operations**: Automatic chunking for DynamoDB batch limits

## Requirements

- Python 3.11+
- Django 4.2+
- boto3
- pynamodb

## Installation

```bash
# Clone the repository
git clone https://github.com/jpwhite3/django-dynamodb-backend.git
cd django-dynamodb-backend

# Install with pipenv
pipenv install

# Or install with pip
pip install -e .
```

## Quick Start

### 1. Configure Django Settings

```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_dynamo_admin.dynamodb_adapter',
]

# DynamoDB settings
DYNAMODB_REGION = 'us-east-1'
DYNAMODB_LOCAL_ENDPOINT = 'http://localhost:4566'  # For local development
```

### 2. Configure AWS Credentials

```bash
# Using environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"

# Or use AWS CLI
aws configure
```

### 3. Define Models

```python
# models.py
from django_dynamo_admin.dynamodb_adapter.models import DynamoDBModel

class BlogPost(DynamoDBModel):
    slug = models.CharField(max_length=100, primary_key=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.CharField(max_length=100)
    published = models.BooleanField(default=False)
```

### 4. Create Admin Interface

```python
# admin.py
from django.contrib import admin
from django_dynamo_admin.dynamodb_adapter.admin import DynamoDBAdmin
from .models import BlogPost

@admin.register(BlogPost)
class BlogPostAdmin(DynamoDBAdmin):
    list_display = ['title', 'author', 'published']
    list_filter = ['published']
    search_fields = ['title', 'author']
```

## Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/jpwhite3/django-dynamodb-backend.git
cd django-dynamodb-backend

# Install dependencies
pipenv install --dev

# Run linting
pipenv run flake8 .
pipenv run black --check .
pipenv run isort --check-only .

# Run tests
pipenv run pytest django_dynamo_admin/tests/unit
```

### Using Docker for Local DynamoDB

```bash
# Start local DynamoDB with docker-compose
docker-compose up -d

# DynamoDB Local will be available at http://localhost:4566
```

## Project Structure

```
django-dynamodb-backend/
├── django_dynamo_admin/           # Main package
│   ├── dynamodb_adapter/          # DynamoDB Django integration
│   │   ├── admin.py               # Django Admin integration
│   │   ├── models.py              # DynamoDB model base classes
│   │   ├── fields.py              # Field type mapping
│   │   └── managers.py            # QuerySet implementation
│   ├── django_dynamo_admin/       # Django project settings
│   │   └── database/              # Custom database backend
│   └── tests/                     # Test suite
├── examples/                      # Example code
├── docs/                          # Documentation
└── interactive_demo/              # Demo application
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Development workflow
git checkout -b feature/your-feature
# Make changes
pipenv run black .
pipenv run isort .
pipenv run flake8 .
git commit -m "feat: your feature description"
git push origin feature/your-feature
# Create pull request
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- [GitHub Repository](https://github.com/jpwhite3/django-dynamodb-backend)
- [Issue Tracker](https://github.com/jpwhite3/django-dynamodb-backend/issues)
