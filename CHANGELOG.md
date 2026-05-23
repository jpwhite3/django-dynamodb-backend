# Changelog

All notable changes to Django DynamoDB Backend will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No changes yet._

## [1.0.0] - 2026-05-23

First stable release on PyPI. Functionally identical to `1.0.0rc1`; the only
delta is a PyPI-focused README rewrite (no emoji, no mermaid, real
`pip install` instructions) and the relocation of displaced sections into
`docs/ARCHITECTURE.md` and `docs/DEMO.md`.

### Changed
- Rewrote `README.md` for PyPI: removed all emoji and the mermaid architecture
  diagram (which PyPI's renderer does not execute), replaced the
  `git clone ... pip install -e .` instructions with
  `pip install django-dynamodb-backend`, dropped contributor-only sections,
  and made every doc/CONTRIBUTING/LICENSE link an absolute GitHub URL so they
  resolve from pypi.org.
- Added a PyPI version badge to the README.

### Added
- `docs/ARCHITECTURE.md` — component diagram and repository layout previously
  in the README.
- `docs/DEMO.md` — `make demo` Docker walkthrough and the no-Docker local
  setup previously in the README's Quick Start section.

## [1.0.0rc1] - 2026-05-23

First release candidate published to PyPI under the new `django-dynamodb-backend`
package name.

### Added
- **🚀 DynamoDB-Only Mode**: Run Django 100% on DynamoDB without any relational database
- **DynamoDB Sessions** (`django_dynamodb_backend.sessions`)
  - `SessionStore` class implementing Django's session backend API
  - Automatic TTL-based session expiration using DynamoDB TTL feature
  - Compressed session data with base64 encoding
  - Management command: `dynamodb_create_session_table`
- **DynamoDB Authentication** (`django_dynamodb_backend.contrib.auth_dynamo`)
  - `DynamoUser` model with UUID primary key
  - GSIs for O(1) username and email lookups
  - `DynamoUserManager` with `create_user()` and `create_superuser()`
  - `DynamoAuthBackend` for username/password authentication
  - Django Admin integration with user management forms
  - Permission system using comma-separated permission strings
  - Management command: `dynamodb_create_user_table [--create-admin]`
- **Demo improvements**
  - `make demo` now runs entirely on DynamoDB (no Redis or SQLite)
  - Automatic creation of sessions and users tables
  - Admin user seeded automatically (admin/admin123)

### Changed
- **BREAKING**: Restructured project as pip-installable package with `src/` layout
- **BREAKING**: Renamed package from `django_dynamo_admin.dynamodb_adapter` to `django_dynamodb_backend`
- **BREAKING**: Changed database engine path from `django_dynamo_admin.database` to `django_dynamodb_backend.db`
- Demo no longer requires Redis (sessions moved to DynamoDB)
- Demo no longer requires SQLite (auth moved to DynamoDB)
- Docker Compose updated to make Redis optional (profile: `with-redis`)
- Moved tests to root `tests/` directory
- Moved demo project to `examples/demo_project/`
- Added modern `pyproject.toml` configuration
- Simplified `setup.py` to minimal shim for backward compatibility
- Updated Python version requirement to 3.11+ (supports 3.11, 3.12, 3.13, and 3.14)
- Simplified project documentation
- Updated `docs/DJANGO_COMPATIBILITY.md` with DynamoDB-only deployment guide
- Added `docs/MIGRATION_TUTORIAL.md` - step-by-step guide for migrating existing Django projects
- Updated all documentation for DynamoDB-only mode

### Migration Guide
Update your imports:
```python
# Before
from django_dynamo_admin.dynamodb_adapter.models import DynamoDBModel
from django_dynamo_admin.dynamodb_adapter.admin import DynamoDBAdmin
INSTALLED_APPS = ['django_dynamo_admin.dynamodb_adapter']
DATABASES = {'default': {'ENGINE': 'django_dynamo_admin.database'}}

# After
from django_dynamodb_backend.models import DynamoDBModel
from django_dynamodb_backend.admin import DynamoDBAdmin
INSTALLED_APPS = ['django_dynamodb_backend']
DATABASES = {'default': {'ENGINE': 'django_dynamodb_backend.db'}}
```

### Fixed
- CI/CD pipeline now passes all checks (linting, formatting, security scan)
- Fixed black/isort formatting across all files
- Fixed flake8 errors (missing imports)
- Fixed app configuration for proper Django integration

### Removed
- Removed codecov integration
- Removed internal planning and development documentation
- Cleaned up unnecessary configuration files
- Removed old `django_dynamo_admin/` nested directory structure

## [1.0.0] - 2024-08-27

### Initial Release

First release of Django DynamoDB Backend, providing Django Admin integration with Amazon DynamoDB.

### Added

#### Core Framework
- Django database backend for DynamoDB (`django_dynamodb_backend.db`)
- Django-style models via `DynamoDBModel` base class with PynamoDB bridge
- Custom QuerySet (`DynamoDBQuerySet`) and Manager (`DynamoDBManager`) with filter, exclude, Q objects, aggregation support
- DynamoDB-specific migration system with `CreateTable`, `UpdateTableCapacity`, `DataMigration`, `RunPython` operations
- Django Admin integration via `DynamoDBAdmin` base class

#### Admin Features
- Tabular and stacked inlines with DynamoDB batch operations
- Bulk actions (delete, CSV export) with DynamoDB optimizations
- DynamoDB-optimized list filters (boolean, date range, numeric range, text search)
- Token-based pagination for DynamoDB's `LastEvaluatedKey` pattern
- Autocomplete support for large datasets
- GSI monitoring and optimization recommendations

#### Management Commands
- `dynamodb_makemigrations` — create DynamoDB migration files
- `dynamodb_migrate` — apply DynamoDB migrations
- `dynamodb_rollback` — rollback migrations
- `dynamodb_showmigrations` — show migration status
- `dynamodb_create_session_table` — create sessions table with TTL
- `dynamodb_create_user_table` — create users table with GSIs
- `dynamodb_performance` — performance monitoring

#### Compatibility
- **Django**: 5.2+
- **Python**: 3.11+
- **Deployment**: Docker, AWS Lambda (via Mangum), EC2, ECS/Fargate

---

**Note**: This project follows semantic versioning.
