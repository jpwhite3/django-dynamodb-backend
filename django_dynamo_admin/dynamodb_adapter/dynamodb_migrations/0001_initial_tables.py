"""
DynamoDB migration for dynamodb_adapter.

Created on 2024-08-26 12:00
"""

from dynamodb_adapter.migrations_dynamo import (
    CreateTable,
    DataMigration,
    DynamoDBMigration,
    RunPython,
    UpdateTableCapacity,
)
from dynamodb_adapter.models import Choice, MyModel, Question


class Migration(DynamoDBMigration):
    """Migration: 0001_initial_tables"""

    dependencies = [
        # No dependencies for initial migration
    ]

    operations = [
        CreateTable(model_class=MyModel, read_capacity=5, write_capacity=5),
        CreateTable(model_class=Question, read_capacity=10, write_capacity=5),
        CreateTable(model_class=Choice, read_capacity=15, write_capacity=10),
    ]
