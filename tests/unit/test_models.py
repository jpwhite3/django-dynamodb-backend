"""
Comprehensive unit tests for DynamoDB model integration.
"""

import unittest
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import (
    ImproperlyConfigured,
    MultipleObjectsReturned,
    ObjectDoesNotExist,
)
from django.db import models
from django.test import TestCase, override_settings
from pynamodb.attributes import (
    BinaryAttribute,
    BooleanAttribute,
    JSONAttribute,
    NumberAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
from pynamodb.models import Model as PynamoDBModel

from django_dynamodb_backend.fields import (
    DynamoDBFieldDescriptor,
    FieldMapper,
)
from django_dynamodb_backend.managers import (
    DynamoDBManager,
    DynamoDBQuerySet,
)
from django_dynamodb_backend.models import DynamoDBModel, DynamoDBModelMeta


class TestFieldMapping(TestCase):
    """Test field mapping between Django and PynamoDB."""

    def test_character_field_mappings(self):
        """Test character field type mappings."""
        test_cases = [
            (models.CharField(max_length=100), UnicodeAttribute),
            (models.TextField(), UnicodeAttribute),
            (models.EmailField(), UnicodeAttribute),
            (models.URLField(), UnicodeAttribute),
            (models.SlugField(), UnicodeAttribute),
            (models.UUIDField(), UnicodeAttribute),
        ]

        for django_field, expected_attr in test_cases:
            with self.subTest(field=type(django_field).__name__):
                result = FieldMapper.get_dynamodb_attribute(django_field)
                self.assertEqual(result, expected_attr)

    def test_numeric_field_mappings(self):
        """Test numeric field type mappings."""
        test_cases = [
            (models.IntegerField(), NumberAttribute),
            (models.BigIntegerField(), NumberAttribute),
            (models.SmallIntegerField(), NumberAttribute),
            (models.PositiveIntegerField(), NumberAttribute),
            (models.FloatField(), NumberAttribute),
            (models.DecimalField(max_digits=10, decimal_places=2), NumberAttribute),
            (models.AutoField(primary_key=True), UnicodeAttribute),
        ]

        for django_field, expected_attr in test_cases:
            with self.subTest(field=type(django_field).__name__):
                result = FieldMapper.get_dynamodb_attribute(django_field)
                self.assertEqual(result, expected_attr)

    def test_special_field_mappings(self):
        """Test special field type mappings."""
        test_cases = [
            (models.BooleanField(), BooleanAttribute),
            (models.DateTimeField(), UTCDateTimeAttribute),
            (models.DateField(), UnicodeAttribute),  # Stored as ISO string
            (models.TimeField(), UnicodeAttribute),  # Stored as time string
            (models.JSONField(), JSONAttribute),
            (models.BinaryField(), BinaryAttribute),
        ]

        for django_field, expected_attr in test_cases:
            with self.subTest(field=type(django_field).__name__):
                result = FieldMapper.get_dynamodb_attribute(django_field)
                self.assertEqual(result, expected_attr)

    def test_value_conversion_to_dynamodb(self):
        """Test converting Django values to DynamoDB format."""
        # UUID conversion
        test_uuid = uuid.uuid4()
        uuid_field = models.UUIDField()
        result = FieldMapper.convert_value_to_dynamodb(test_uuid, uuid_field)
        self.assertEqual(result, str(test_uuid))

        # Decimal conversion
        decimal_value = Decimal("123.45")
        decimal_field = models.DecimalField(max_digits=5, decimal_places=2)
        result = FieldMapper.convert_value_to_dynamodb(decimal_value, decimal_field)
        self.assertEqual(result, 123.45)

        # Date conversion
        test_date = date(2023, 12, 25)
        date_field = models.DateField()
        result = FieldMapper.convert_value_to_dynamodb(test_date, date_field)
        self.assertEqual(result, "2023-12-25")

        # Time conversion
        test_time = time(14, 30, 0)
        time_field = models.TimeField()
        result = FieldMapper.convert_value_to_dynamodb(test_time, time_field)
        self.assertEqual(result, "14:30:00")

        # Duration conversion
        test_duration = timedelta(hours=2, minutes=30)
        duration_field = models.DurationField()
        result = FieldMapper.convert_value_to_dynamodb(test_duration, duration_field)
        self.assertEqual(result, 9000.0)  # Total seconds

    def test_value_conversion_from_dynamodb(self):
        """Test converting DynamoDB values back to Django format."""
        # UUID conversion back
        uuid_str = str(uuid.uuid4())
        uuid_field = models.UUIDField()
        result = FieldMapper.convert_value_from_dynamodb(uuid_str, uuid_field)
        self.assertEqual(result, uuid.UUID(uuid_str))

        # Decimal conversion back
        decimal_field = models.DecimalField(max_digits=5, decimal_places=2)
        result = FieldMapper.convert_value_from_dynamodb(123.45, decimal_field)
        self.assertEqual(result, Decimal("123.45"))

        # Date conversion back
        date_field = models.DateField()
        result = FieldMapper.convert_value_from_dynamodb("2023-12-25", date_field)
        self.assertEqual(result, date(2023, 12, 25))

        # Duration conversion back
        duration_field = models.DurationField()
        result = FieldMapper.convert_value_from_dynamodb(9000.0, duration_field)
        self.assertEqual(result, timedelta(hours=2, minutes=30))


class TestDynamoDBModelMeta(TestCase):
    """Test the DynamoDB model metaclass."""

    def setUp(self):
        """Set up test models."""

        class TestModel(DynamoDBModel):
            name = models.CharField(primary_key=True, max_length=100)
            description = models.TextField()
            count = models.IntegerField(default=0)
            is_active = models.BooleanField(default=True)
            created_at = models.DateTimeField(auto_now_add=True)

            class Meta:
                app_label = "tests"

        self.TestModel = TestModel

    def test_pynamodb_model_creation(self):
        """Test that PynamoDB models are created correctly."""
        pynamodb_model = self.TestModel._get_pynamodb_model()

        # Check that it's a proper PynamoDB model
        self.assertTrue(issubclass(pynamodb_model, PynamoDBModel))
        self.assertEqual(pynamodb_model.__name__, "TestModelPynamoDBModel")

        # Check Meta attributes
        self.assertTrue(hasattr(pynamodb_model, "Meta"))
        self.assertEqual(pynamodb_model.Meta.table_name, "tests_testmodel")
        self.assertEqual(pynamodb_model.Meta.region, "us-east-1")

    def test_field_attribute_mapping(self):
        """Test that Django fields are properly mapped to PynamoDB attributes."""
        pynamodb_model = self.TestModel._get_pynamodb_model()

        # Check primary key
        self.assertTrue(hasattr(pynamodb_model, "name"))
        name_attr = pynamodb_model.name
        self.assertIsInstance(name_attr, UnicodeAttribute)
        self.assertTrue(name_attr.is_hash_key)

        # Check other fields
        self.assertTrue(hasattr(pynamodb_model, "description"))
        self.assertIsInstance(pynamodb_model.description, UnicodeAttribute)

        self.assertTrue(hasattr(pynamodb_model, "count"))
        self.assertIsInstance(pynamodb_model.count, NumberAttribute)

        self.assertTrue(hasattr(pynamodb_model, "is_active"))
        self.assertIsInstance(pynamodb_model.is_active, BooleanAttribute)

    def test_abstract_model_handling(self):
        """Test that abstract models don't create PynamoDB models."""

        class AbstractTestModel(DynamoDBModel):
            name = models.CharField(max_length=100)

            class Meta:
                abstract = True
                app_label = "tests"

        # Abstract models should not have _needs_pynamodb_model set to True
        # The metaclass returns early for abstract models
        needs_pynamodb = getattr(AbstractTestModel, "_needs_pynamodb_model", False)
        self.assertFalse(needs_pynamodb)

        # Abstract models should not have _pynamodb_model_class attribute
        # (or it should be None if inherited)
        pynamodb_class = getattr(AbstractTestModel, "_pynamodb_model_class", None)
        self.assertIsNone(pynamodb_class)


class TestDynamoDBModel(TestCase):
    """Test the DynamoDB model functionality."""

    def setUp(self):
        """Set up test model."""

        class TestModel(DynamoDBModel):
            name = models.CharField(primary_key=True, max_length=100)
            description = models.TextField()
            count = models.IntegerField(default=0)

            class Meta:
                app_label = "tests"

        self.TestModel = TestModel

    def test_model_instance_creation(self):
        """Test creating model instances."""
        instance = self.TestModel(name="test", description="Test description", count=5)

        # Check field values are stored correctly
        self.assertEqual(instance._field_values["name"], "test")
        self.assertEqual(instance._field_values["description"], "Test description")
        self.assertEqual(instance._field_values["count"], 5)

    def test_string_representation(self):
        """Test model string representation."""
        instance = self.TestModel(name="test_name", description="Test")
        self.assertEqual(str(instance), "test_name")  # Uses name field

    @patch("django_dynamodb_backend.models.PynamoDBModel.save")
    def test_save_method(self, mock_save):
        """Test model save functionality."""
        instance = self.TestModel(name="test", description="Test description")

        # Mock the PynamoDB instance
        mock_pynamodb_instance = MagicMock()
        with patch.object(
            instance, "_get_pynamodb_instance", return_value=mock_pynamodb_instance
        ):
            instance.save()

            # Check that PynamoDB save was called
            mock_pynamodb_instance.save.assert_called_once()

    @patch("django_dynamodb_backend.models.PynamoDBModel.delete")
    def test_delete_method(self, mock_delete):
        """Test model delete functionality."""
        instance = self.TestModel(name="test", description="Test description")

        # Mock the PynamoDB instance
        mock_pynamodb_instance = MagicMock()
        with patch.object(
            instance, "_get_pynamodb_instance", return_value=mock_pynamodb_instance
        ):
            instance.delete()

            # Check that PynamoDB delete was called
            mock_pynamodb_instance.delete.assert_called_once()

    def test_model_manager(self):
        """Test that models use DynamoDBManager."""
        self.assertIsInstance(self.TestModel.objects, DynamoDBManager)


class TestDynamoDBQuerySet(TestCase):
    """Test DynamoDB QuerySet functionality."""

    def setUp(self):
        """Set up test model and queryset."""

        class TestModel(DynamoDBModel):
            name = models.CharField(primary_key=True, max_length=100)
            count = models.IntegerField(default=0)
            is_active = models.BooleanField(default=True)

            class Meta:
                app_label = "tests"

        self.TestModel = TestModel
        self.queryset = DynamoDBQuerySet(model=TestModel)

    def test_filter_method(self):
        """Test queryset filtering."""
        filtered = self.queryset.filter(name="test", count=5)

        # Should create a new queryset with filters
        self.assertNotEqual(filtered, self.queryset)
        # Check total filters (could be in scan_filters or query_filters depending on optimization)
        total_filters = len(filtered._dynamodb_scan_filters) + len(
            filtered._dynamodb_query_filters
        )
        self.assertEqual(total_filters, 2)

    def test_exclude_method(self):
        """Test queryset exclusion."""
        excluded = self.queryset.exclude(is_active=False)

        # Should create a new queryset with exclusion filters
        self.assertNotEqual(excluded, self.queryset)
        self.assertEqual(len(excluded._dynamodb_scan_filters), 1)

    def test_chaining_filters(self):
        """Test chaining multiple filters."""
        chained = self.queryset.filter(count__gt=0).filter(is_active=True)

        # Should accumulate filters
        self.assertEqual(len(chained._dynamodb_scan_filters), 2)

    def test_slicing(self):
        """Test queryset slicing."""
        sliced = self.queryset[10:20]

        # Should set offset and limit
        self.assertEqual(sliced._offset_count, 10)
        self.assertEqual(sliced._limit_count, 10)

    def test_lookup_conversion(self):
        """Test Django lookup conversion to DynamoDB conditions."""
        # Test various lookup types
        lookups = [
            ("name", "exact", "test"),
            ("count", "gt", 5),
            ("count", "gte", 10),
            ("count", "lt", 100),
            ("count", "lte", 50),
            ("name", "contains", "substring"),
            ("name", "startswith", "prefix"),
            ("count", "in", [1, 2, 3]),
        ]

        for field_name, lookup_type, value in lookups:
            with self.subTest(lookup=f"{field_name}__{lookup_type}"):
                condition = self.queryset._convert_lookup(
                    field_name, lookup_type, value
                )
                self.assertIsNotNone(condition)


class TestDynamoDBManager(TestCase):
    """Test DynamoDB Manager functionality."""

    def setUp(self):
        """Set up test model."""

        class TestModel(DynamoDBModel):
            name = models.CharField(primary_key=True, max_length=100)
            description = models.TextField()

            class Meta:
                app_label = "tests"

        self.TestModel = TestModel
        self.manager = DynamoDBManager()
        self.manager.model = TestModel

    def test_get_queryset(self):
        """Test that manager returns DynamoDBQuerySet."""
        queryset = self.manager.get_queryset()
        self.assertIsInstance(queryset, DynamoDBQuerySet)
        self.assertEqual(queryset.model, self.TestModel)

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet.get")
    def test_get_method(self, mock_get):
        """Test manager get method."""
        mock_instance = MagicMock()
        mock_get.return_value = mock_instance

        result = self.manager.get(name="test")

        mock_get.assert_called_once_with(name="test")
        self.assertEqual(result, mock_instance)

    @patch.object(DynamoDBModel, "save")
    def test_create_method(self, mock_save):
        """Test manager create method."""
        result = self.manager.create(name="test", description="Test desc")

        # Should create instance and save it
        self.assertIsInstance(result, self.TestModel)
        mock_save.assert_called_once()

    @patch.object(DynamoDBModel, "_get_pynamodb_model")
    def test_bulk_create(self, mock_get_pynamodb_model):
        """Test bulk create functionality."""
        # Mock the PynamoDB model's batch_write context manager
        mock_pynamodb_model = MagicMock()
        mock_batch_writer = MagicMock()
        mock_batch_writer.__enter__ = MagicMock(return_value=mock_batch_writer)
        mock_batch_writer.__exit__ = MagicMock(return_value=False)
        mock_pynamodb_model.batch_write.return_value = mock_batch_writer
        mock_get_pynamodb_model.return_value = mock_pynamodb_model

        objects = [
            self.TestModel(name="test1", description="Desc 1"),
            self.TestModel(name="test2", description="Desc 2"),
        ]

        result = self.manager.bulk_create(objects)

        # Should call batch_write and save for each object
        mock_pynamodb_model.batch_write.assert_called_once()
        self.assertEqual(mock_batch_writer.save.call_count, 2)
        self.assertEqual(len(result), 2)


class TestFieldDescriptor(TestCase):
    """Test DynamoDB field descriptor functionality."""

    def test_descriptor_get_set(self):
        """Test field descriptor get and set operations."""
        field = models.CharField(max_length=100)
        descriptor = DynamoDBFieldDescriptor("test_field", field)

        # Create a mock instance
        instance = MagicMock()
        instance._field_values = {}
        instance._django_instance = MagicMock()

        # Test setting value
        descriptor.__set__(instance, "test_value")
        self.assertEqual(instance._field_values["test_field"], "test_value")

        # Test getting value
        result = descriptor.__get__(instance, None)
        self.assertEqual(result, "test_value")


class TestErrorHandling(TestCase):
    """Test error handling and edge cases."""

    def setUp(self):
        """Set up test model."""

        class TestModel(DynamoDBModel):
            name = models.CharField(primary_key=True, max_length=100)

            class Meta:
                app_label = "tests"

        self.TestModel = TestModel

    def test_improper_configuration_error(self):
        """Test error when PynamoDB model cannot be created."""

        # Create a model without proper setup
        class BadModel(models.Model):
            name = models.CharField(max_length=100)
            _pynamodb_model_class = None
            _needs_pynamodb_model = False

            class Meta:
                app_label = "tests"

            @classmethod
            def _get_pynamodb_model(cls):
                if cls._pynamodb_model_class is None:
                    raise ImproperlyConfigured(
                        f"No PynamoDB model created for {cls.__name__}"
                    )
                return cls._pynamodb_model_class

        with self.assertRaises(ImproperlyConfigured):
            BadModel._get_pynamodb_model()

    def test_null_value_handling(self):
        """Test handling of null values in field conversion."""
        char_field = models.CharField(max_length=100)

        # Test null conversion to DynamoDB
        result = FieldMapper.convert_value_to_dynamodb(None, char_field)
        self.assertIsNone(result)

        # Test null conversion from DynamoDB
        result = FieldMapper.convert_value_from_dynamodb(None, char_field)
        self.assertIsNone(result)

    def test_unsupported_lookup_handling(self):
        """Test handling of unsupported lookup types."""
        queryset = DynamoDBQuerySet(model=self.TestModel)

        # Test unsupported lookup
        condition = queryset._convert_lookup("name", "unsupported_lookup", "value")
        self.assertIsNone(condition)


if __name__ == "__main__":
    unittest.main()
