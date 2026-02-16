"""
DynamoDB migration for django_dynamodb_backend.

Created on 2025-08-26 23:39
"""

from django_dynamodb_backend.migrations_dynamo import (
    DynamoDBMigration,
)

# Import your models here, e.g.:
# from django_dynamodb_backend.models import MyModel


class Migration(DynamoDBMigration):
    """Migration: 0004_test_migration"""

    dependencies = [
        # Add dependencies here, e.g.:
        # ('app_label', 'previous_migration_name'),
    ]

    operations = [
        # Add your operations here
    ]
