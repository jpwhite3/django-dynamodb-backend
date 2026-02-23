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
