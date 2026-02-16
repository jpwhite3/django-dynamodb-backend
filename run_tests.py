import os
import sys
import django
from django.conf import settings
import pytest

def main():
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
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
                "dynamodb_adapter",
                "tests",
            ],
            MIGRATION_MODULES = {
                "dynamodb_adapter": None,
            },
            USE_TZ = True,
            TIME_ZONE = "UTC",
            DYNAMODB_REGION = "us-east-1",
            DYNAMODB_LOCAL_ENDPOINT = "http://localhost:4566",
        )
    django.setup()
    sys.exit(pytest.main(sys.argv[1:]))

if __name__ == '__main__':
    main()
