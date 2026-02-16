import os
import sys

import django
import pytest
from django.conf import settings


def main():
    # Add src directory to path for package imports
    base_dir = os.path.abspath(os.path.dirname(__file__))
    src_dir = os.path.join(base_dir, "src")
    sys.path.insert(0, base_dir)
    sys.path.insert(0, src_dir)
    
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.admin",
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "django.contrib.messages",
                "django.contrib.staticfiles",
                "django_dynamodb_backend",
                "tests",
            ],
            MIGRATION_MODULES={
                "django_dynamodb_backend": None,
            },
            USE_TZ=True,
            TIME_ZONE="UTC",
            SECRET_KEY="test-secret-key",
            DYNAMODB_REGION="us-east-1",
            DYNAMODB_LOCAL_ENDPOINT="http://localhost:4566",
        )
    django.setup()
    
    # Default to running tests directory if no args provided
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/"]
    sys.exit(pytest.main(args))


if __name__ == "__main__":
    main()
