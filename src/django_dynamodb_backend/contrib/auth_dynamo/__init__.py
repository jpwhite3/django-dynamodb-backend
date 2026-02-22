"""
DynamoDB-based authentication for Django.

This package provides a complete authentication system using DynamoDB,
eliminating the need for a relational database for user management.

Usage:
    In settings.py:
        INSTALLED_APPS = [
            ...
            'django_dynamodb_backend.contrib.auth_dynamo',
            ...
        ]
        AUTH_USER_MODEL = 'auth_dynamo.DynamoUser'
        AUTHENTICATION_BACKENDS = [
            'django_dynamodb_backend.contrib.auth_dynamo.backends.DynamoAuthBackend',
        ]
"""

default_app_config = "django_dynamodb_backend.contrib.auth_dynamo.apps.AuthDynamoConfig"


def setup_user_manager():
    """
    Wire up the DynamoUserManager to the DynamoUser model.

    This is called during app initialization.
    """
    from .managers import DynamoUserManager
    from .models import DynamoUser

    manager = DynamoUserManager()
    manager.model = DynamoUser
    DynamoUser.objects = manager
    DynamoUser._default_manager = manager


# Setup manager when module is imported
try:
    setup_user_manager()
except Exception:
    # Ignore errors during initial import (before Django is fully configured)
    pass
