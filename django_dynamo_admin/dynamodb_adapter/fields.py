"""
DynamoDB field mappings and utilities for Django-DynamoDB integration.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from django.db import models
from pynamodb.attributes import (
    BinaryAttribute,
    BooleanAttribute,
    JSONAttribute,
    ListAttribute,
    MapAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)


class FieldMapper:
    """Maps Django field types to PynamoDB attributes."""

    FIELD_MAPPING = {
        # Character fields
        models.CharField: UnicodeAttribute,
        models.TextField: UnicodeAttribute,
        models.EmailField: UnicodeAttribute,
        models.URLField: UnicodeAttribute,
        models.SlugField: UnicodeAttribute,
        models.UUIDField: UnicodeAttribute,
        models.FileField: UnicodeAttribute,
        models.FilePathField: UnicodeAttribute,
        models.IPAddressField: UnicodeAttribute,
        models.GenericIPAddressField: UnicodeAttribute,
        # Numeric fields
        models.IntegerField: NumberAttribute,
        models.BigIntegerField: NumberAttribute,
        models.SmallIntegerField: NumberAttribute,
        models.PositiveIntegerField: NumberAttribute,
        models.PositiveSmallIntegerField: NumberAttribute,
        models.FloatField: NumberAttribute,
        models.DecimalField: NumberAttribute,
        models.DurationField: NumberAttribute,
        # Auto fields
        models.AutoField: UnicodeAttribute,
        models.BigAutoField: UnicodeAttribute,
        # Boolean field
        models.BooleanField: BooleanAttribute,
        # Date/time fields
        models.DateTimeField: UTCDateTimeAttribute,
        models.DateField: UnicodeAttribute,  # Store as ISO string
        models.TimeField: UnicodeAttribute,  # Store as time string
        # Binary field
        models.BinaryField: BinaryAttribute,
        # JSON field
        models.JSONField: JSONAttribute,
    }

    @classmethod
    def get_dynamodb_attribute(cls, django_field):
        """Get the corresponding PynamoDB attribute for a Django field."""
        field_class = type(django_field)
        return cls.FIELD_MAPPING.get(field_class, UnicodeAttribute)

    @classmethod
    def convert_value_to_dynamodb(cls, value, django_field):
        """Convert a Django field value to DynamoDB format."""
        if value is None:
            return None

        field_class = type(django_field)

        # Handle special conversions
        if field_class == models.UUIDField:
            return str(value) if value else None
        elif field_class == models.DecimalField:
            return float(value) if value else None
        elif field_class in (models.DateField, models.TimeField):
            return value.isoformat() if value else None
        elif field_class == models.DateTimeField:
            return value
        elif field_class == models.DurationField:
            return value.total_seconds() if value else None
        elif field_class == models.JSONField:
            return value
        elif field_class in (models.AutoField, models.BigAutoField):
            return str(value) if value else None

        return value

    @classmethod
    def convert_value_from_dynamodb(cls, value, django_field):
        """Convert a DynamoDB value back to Django format."""
        if value is None:
            return None

        field_class = type(django_field)

        # Handle special conversions
        if field_class == models.UUIDField:
            return uuid.UUID(value) if value else None
        elif field_class == models.DecimalField:
            return Decimal(str(value)) if value else None
        elif field_class == models.DateField:
            from datetime import date

            return date.fromisoformat(value) if value else None
        elif field_class == models.TimeField:
            from datetime import time

            return time.fromisoformat(value) if value else None
        elif field_class == models.DateTimeField:
            return value  # UTCDateTimeAttribute handles this
        elif field_class == models.DurationField:
            from datetime import timedelta

            return timedelta(seconds=value) if value else None
        elif field_class in (models.AutoField, models.BigAutoField):
            return int(value) if value and value.isdigit() else value

        return value


class DynamoDBFieldDescriptor:
    """Descriptor that handles field access for DynamoDB models."""

    def __init__(self, field_name, django_field):
        self.field_name = field_name
        self.django_field = django_field

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance._field_values.get(self.field_name)

    def __set__(self, instance, value):
        # Convert and store the value
        converted_value = FieldMapper.convert_value_to_dynamodb(
            value, self.django_field
        )
        instance._field_values[self.field_name] = converted_value

        # Also update the Django field
        setattr(instance._django_instance, self.field_name, value)
