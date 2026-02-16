# Contributing to Django DynamoDB Backend

We welcome contributions! This document provides guidelines for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.11+
- Django 5.2+
- pipenv
- Docker (for local DynamoDB)

### Development Setup

1. **Fork and Clone**

```bash
git clone https://github.com/YOUR-USERNAME/django-dynamodb-backend.git
cd django-dynamodb-backend
```

2. **Install Dependencies**

```bash
pipenv install --dev
```

3. **Run Tests**

```bash
pipenv run pytest tests/
```

## Development Workflow

### Code Style

We use automated formatting tools:

```bash
# Format code
pipenv run black .
pipenv run isort .

# Check formatting
pipenv run black --check .
pipenv run isort --check-only .

# Lint
pipenv run flake8 .
```

### Making Changes

1. Create a feature branch:
```bash
git checkout -b feature/your-feature
```

2. Make your changes and ensure tests pass

3. Format your code:
```bash
pipenv run black .
pipenv run isort .
```

4. Commit with a descriptive message:
```bash
git commit -m "feat: add your feature description"
```

5. Push and create a pull request:
```bash
git push origin feature/your-feature
```

### Commit Message Format

We follow conventional commits:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test changes
- `ci:` - CI/CD changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

## Testing

### Running Tests

```bash
# Run all tests
pipenv run pytest tests/

# Run unit tests only
pipenv run pytest tests/unit/

# Run with coverage
pipenv run pytest --cov=src/django_dynamodb_backend

# Run specific test file
pipenv run pytest tests/unit/test_models.py
```

### Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
└── performance/    # Performance tests
```

## Pull Request Guidelines

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all CI checks pass
4. Keep changes focused and atomic
5. Write clear commit messages

## Questions?

Open an issue for questions or discussion.
