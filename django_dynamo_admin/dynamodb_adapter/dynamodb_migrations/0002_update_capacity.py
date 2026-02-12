"""
DynamoDB migration for dynamodb_adapter.

Created on 2024-08-26 12:05
"""

from dynamodb_adapter.migrations_dynamo import (CreateTable, DataMigration,
                                                DynamoDBMigration, RunPython,
                                                UpdateTableCapacity)
from dynamodb_adapter.models import Choice, Question


class Migration(DynamoDBMigration):
    """Migration: 0002_update_capacity"""

    dependencies = [
        ("dynamodb_adapter", "0001_initial_tables"),
    ]

    operations = [
        UpdateTableCapacity(model_class=Question, read_capacity=20, write_capacity=10),
        UpdateTableCapacity(model_class=Choice, read_capacity=25, write_capacity=15),
    ]
