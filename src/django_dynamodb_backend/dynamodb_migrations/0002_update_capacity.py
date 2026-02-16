"""
DynamoDB migration for django_dynamodb_backend.

Created on 2024-08-26 12:05
"""

from django_dynamodb_backend.migrations_dynamo import (
    DynamoDBMigration,
    UpdateTableCapacity,
)
from django_dynamodb_backend.models import Choice, Question


class Migration(DynamoDBMigration):
    """Migration: 0002_update_capacity"""

    dependencies = [
        ("django_dynamodb_backend", "0001_initial_tables"),
    ]

    operations = [
        UpdateTableCapacity(model_class=Question, read_capacity=20, write_capacity=10),
        UpdateTableCapacity(model_class=Choice, read_capacity=25, write_capacity=15),
    ]
