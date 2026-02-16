"""
DynamoDB migration for django_dynamodb_backend.

Created on 2024-08-26 12:10
"""

from django_dynamodb_backend.migrations_dynamo import (
    DataMigration,
    DynamoDBMigration,
)
from django_dynamodb_backend.models import Question


def add_is_published_field(item):
    """Forward data migration function."""
    # Add is_published field to existing questions
    if not hasattr(item, "is_published"):
        item.is_published = True
        item.save()


def remove_is_published_field(item):
    """Reverse data migration function."""
    # Remove is_published field
    if hasattr(item, "is_published"):
        delattr(item, "is_published")
        item.save()


class Migration(DynamoDBMigration):
    """Migration: 0003_data_migration"""

    dependencies = [
        ("django_dynamodb_backend", "0002_update_capacity"),
    ]

    operations = [
        DataMigration(
            model_class=Question,
            migration_func=add_is_published_field,
            reverse_func=remove_is_published_field,
        ),
    ]
