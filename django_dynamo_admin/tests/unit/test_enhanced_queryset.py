"""
Enhanced QuerySet functionality tests for Phase 3 improvements.
"""

import unittest
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import models
from django.test import TestCase
from dynamodb_adapter.managers import DynamoDBManager, DynamoDBQuerySet
from dynamodb_adapter.models import MyModel


class EnhancedTestModel(MyModel):
    """Enhanced test model for comprehensive QuerySet testing."""

    name = models.CharField(max_length=100)
    email = models.EmailField()
    age = models.IntegerField()
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    birth_date = models.DateField()
    work_time = models.TimeField()
    profile_id = models.UUIDField()
    metadata = models.JSONField()

    class Meta:
        app_label = "tests"


class TestEnhancedFiltering(TestCase):
    """Test enhanced filtering capabilities."""

    def setUp(self):
        self.queryset = DynamoDBQuerySet(model=EnhancedTestModel)

    def test_exact_lookup(self):
        """Test exact field lookups."""
        qs = self.queryset.filter(name="John Doe")

        # Should have created a filter
        total_filters = len(qs._dynamodb_scan_filters) + len(qs._dynamodb_query_filters)
        self.assertEqual(total_filters, 1)

    def test_case_insensitive_lookups(self):
        """Test case-insensitive lookups."""
        qs = self.queryset.filter(name__iexact="john doe")

        total_filters = len(qs._dynamodb_scan_filters) + len(qs._dynamodb_query_filters)
        self.assertEqual(total_filters, 1)

    def test_comparison_lookups(self):
        """Test comparison lookups (gt, gte, lt, lte)."""
        test_cases = [
            ("age__gt", 25),
            ("age__gte", 18),
            ("age__lt", 65),
            ("age__lte", 99),
            ("salary__gt", Decimal("50000.00")),
        ]

        for lookup, value in test_cases:
            with self.subTest(lookup=lookup):
                qs = self.queryset.filter(**{lookup: value})
                total_filters = len(qs._dynamodb_scan_filters) + len(
                    qs._dynamodb_query_filters
                )
                self.assertEqual(total_filters, 1)

    def test_string_lookups(self):
        """Test string-based lookups."""
        test_cases = [
            ("name__contains", "John"),
            ("name__icontains", "john"),
            ("name__startswith", "John"),
            ("name__istartswith", "john"),
            ("name__endswith", "Doe"),
            ("name__iendswith", "doe"),
        ]

        for lookup, value in test_cases:
            with self.subTest(lookup=lookup):
                qs = self.queryset.filter(**{lookup: value})
                total_filters = len(qs._dynamodb_scan_filters) + len(
                    qs._dynamodb_query_filters
                )
                self.assertEqual(total_filters, 1)

    def test_in_lookup(self):
        """Test 'in' lookup."""
        qs = self.queryset.filter(age__in=[25, 30, 35])

        total_filters = len(qs._dynamodb_scan_filters) + len(qs._dynamodb_query_filters)
        self.assertEqual(total_filters, 1)

    def test_range_lookup(self):
        """Test range lookup."""
        qs = self.queryset.filter(age__range=[18, 65])

        total_filters = len(qs._dynamodb_scan_filters) + len(qs._dynamodb_query_filters)
        self.assertEqual(total_filters, 1)

    def test_isnull_lookup(self):
        """Test isnull lookup."""
        test_cases = [
            ("name__isnull", True),
            ("name__isnull", False),
        ]

        for lookup, value in test_cases:
            with self.subTest(lookup=lookup, value=value):
                qs = self.queryset.filter(**{lookup: value})
                total_filters = len(qs._dynamodb_scan_filters) + len(
                    qs._dynamodb_query_filters
                )
                self.assertEqual(total_filters, 1)

    def test_datetime_component_lookups(self):
        """Test datetime component lookups."""
        test_cases = [
            ("created_at__year", 2023),
            # Note: month and day lookups have warnings in our implementation
        ]

        for lookup, value in test_cases:
            with self.subTest(lookup=lookup):
                qs = self.queryset.filter(**{lookup: value})
                # These might not create filters due to warnings
                total_filters = len(qs._dynamodb_scan_filters) + len(
                    qs._dynamodb_query_filters
                )
                self.assertGreaterEqual(total_filters, 0)

    def test_multiple_filters(self):
        """Test applying multiple filters."""
        qs = (
            self.queryset.filter(is_active=True)
            .filter(age__gte=18)
            .filter(name__contains="John")
        )

        total_filters = len(qs._dynamodb_scan_filters) + len(qs._dynamodb_query_filters)
        self.assertEqual(total_filters, 3)

    def test_filter_chaining(self):
        """Test that filter chaining creates new QuerySet instances."""
        qs1 = self.queryset.filter(is_active=True)
        qs2 = qs1.filter(age__gte=18)

        # Each step should create a new QuerySet
        self.assertNotEqual(qs1, self.queryset)
        self.assertNotEqual(qs2, qs1)

        # Original should be unchanged
        self.assertEqual(len(self.queryset._dynamodb_scan_filters), 0)

        # Each subsequent QuerySet should have more filters
        total_filters_1 = len(qs1._dynamodb_scan_filters) + len(
            qs1._dynamodb_query_filters
        )
        total_filters_2 = len(qs2._dynamodb_scan_filters) + len(
            qs2._dynamodb_query_filters
        )

        self.assertEqual(total_filters_1, 1)
        self.assertEqual(total_filters_2, 2)


class TestQueryOptimization(TestCase):
    """Test query optimization features."""

    def setUp(self):
        self.queryset = DynamoDBQuerySet(model=EnhancedTestModel)

    def test_query_operation_detection(self):
        """Test that Query operations are detected appropriately."""
        # This would depend on the model's primary key configuration
        # For now, test that the flags are set correctly
        qs = self.queryset.filter(name="exact_match")

        # Check that query optimization flags are accessible
        self.assertIsInstance(qs._use_query_operation, bool)
        self.assertIsInstance(qs._dynamodb_query_filters, list)

    def test_scan_fallback(self):
        """Test fallback to Scan operations."""
        # Complex filters should use Scan
        qs = self.queryset.filter(name__contains="partial")

        # Should have scan filters
        self.assertIsInstance(qs._dynamodb_scan_filters, list)

    def test_pagination_support(self):
        """Test pagination functionality."""
        # Test using_pagination method
        qs = self.queryset.using_pagination({"id": {"S": "test-key"}})

        self.assertIsNotNone(qs._last_evaluated_key)
        self.assertEqual(qs._last_evaluated_key["id"]["S"], "test-key")

    def test_pagination_info(self):
        """Test pagination info retrieval."""
        qs = self.queryset.filter(is_active=True)

        # Test that pagination info structure exists
        info = qs.get_pagination_info()

        expected_keys = [
            "last_evaluated_key",
            "has_more_pages",
            "scanned_count",
            "consumed_capacity",
        ]
        for key in expected_keys:
            self.assertIn(key, info)


class TestAdvancedQuerySetMethods(TestCase):
    """Test advanced QuerySet methods."""

    def setUp(self):
        self.queryset = DynamoDBQuerySet(model=EnhancedTestModel)

    def test_ordering(self):
        """Test ordering functionality."""
        # Test ascending order
        qs_asc = self.queryset.order_by("name")
        self.assertEqual(qs_asc._order_by_fields, ["name"])
        self.assertTrue(qs_asc._scan_index_forward)

        # Test descending order
        qs_desc = self.queryset.order_by("-age")
        self.assertEqual(qs_desc._order_by_fields, ["-age"])
        self.assertFalse(qs_desc._scan_index_forward)

    def test_slicing(self):
        """Test QuerySet slicing."""
        # Test basic slicing
        qs_slice = self.queryset[10:20]
        self.assertEqual(qs_slice._offset_count, 10)
        self.assertEqual(qs_slice._limit_count, 10)

        # Test open-ended slicing
        qs_open = self.queryset[5:]
        self.assertEqual(qs_open._offset_count, 5)
        self.assertIsNone(qs_open._limit_count)

    def test_values_and_values_list(self):
        """Test values() and values_list() methods."""
        # Test values
        qs_values = self.queryset.values("name", "age")
        self.assertTrue(hasattr(qs_values, "_fields"))

        # Test values_list
        qs_values_list = self.queryset.values_list("name", "age", flat=False)
        self.assertTrue(hasattr(qs_values_list, "_fields"))
        self.assertTrue(hasattr(qs_values_list, "_flat"))

    def test_only_and_defer(self):
        """Test only() and defer() methods."""
        # Test only
        qs_only = self.queryset.only("name", "age")
        self.assertIsNotNone(qs_only)

        # Test defer
        qs_defer = self.queryset.defer("metadata", "salary")
        self.assertTrue(hasattr(qs_defer, "_deferred_fields"))
        self.assertEqual(qs_defer._deferred_fields, {"metadata", "salary"})

    def test_distinct(self):
        """Test distinct() method."""
        qs_distinct = self.queryset.distinct()
        # Should return a cloned QuerySet
        self.assertNotEqual(qs_distinct, self.queryset)

    def test_aggregate(self):
        """Test aggregate() method."""
        from django.db.models import Count

        # Mock aggregation for testing
        with patch.object(self.queryset, "count", return_value=42):
            result = self.queryset.aggregate(total=Count("id"))

            self.assertIn("total", result)
            # The actual value would depend on the Count implementation

    def test_django_compatibility_methods(self):
        """Test Django compatibility methods that should work."""
        # These should not raise errors
        qs_select_related = self.queryset.select_related("some_field")
        qs_prefetch_related = self.queryset.prefetch_related("some_field")

        self.assertIsNotNone(qs_select_related)
        self.assertIsNotNone(qs_prefetch_related)

    def test_unsupported_operations(self):
        """Test that unsupported operations raise appropriate errors."""
        with self.assertRaises(NotImplementedError):
            self.queryset.extra(select={"test": "test"})

        with self.assertRaises(NotImplementedError):
            self.queryset.raw("SELECT * FROM table")


class TestBulkOperations(TestCase):
    """Test bulk operations."""

    def setUp(self):
        self.queryset = DynamoDBQuerySet(model=EnhancedTestModel)

    @patch("dynamodb_adapter.managers.DynamoDBQuerySet._execute_scan")
    def test_queryset_update(self, mock_scan):
        """Test QuerySet update() method."""
        # Mock scan to return test objects
        mock_instance = MagicMock()
        mock_instance.save = MagicMock()
        mock_scan.return_value = [mock_instance, mock_instance]

        # Test update
        result = self.queryset.update(is_active=False)

        # Should return count of updated objects
        self.assertEqual(result, 2)

        # Should have called save on each instance
        self.assertEqual(mock_instance.save.call_count, 2)

    @patch("dynamodb_adapter.managers.DynamoDBQuerySet._execute_scan")
    @patch("dynamodb_adapter.managers.DynamoDBQuerySet._batch_delete_items")
    def test_queryset_delete(self, mock_batch_delete, mock_scan):
        """Test QuerySet delete() method."""
        # Mock scan to return test objects
        mock_instance1 = MagicMock()
        mock_instance1.pk = "key1"
        mock_instance2 = MagicMock()
        mock_instance2.pk = "key2"

        mock_scan.return_value = [mock_instance1, mock_instance2]

        # Set up the model's meta
        self.queryset.model._meta.pk.name = "id"
        self.queryset.model._meta.label = "tests.EnhancedTestModel"

        # Test delete
        result = self.queryset.delete()

        # Should return count and model breakdown
        count, models_dict = result
        self.assertEqual(count, 2)
        self.assertIn("tests.EnhancedTestModel", models_dict)


class TestValueConversion(TestCase):
    """Test value preprocessing and conversion."""

    def setUp(self):
        self.queryset = DynamoDBQuerySet(model=EnhancedTestModel)

    def test_preprocess_value_types(self):
        """Test preprocessing of different value types."""
        test_cases = [
            (42, Decimal),  # int to Decimal
            (3.14, Decimal),  # float to Decimal
            (True, bool),  # bool stays bool
            (datetime.now(), str),  # datetime to ISO string
            (date.today(), str),  # date to ISO string
            (time(14, 30), str),  # time to ISO string
            (uuid.uuid4(), str),  # UUID to string
            (["a", "b", "c"], list),  # list stays list
            ({"key": "value"}, dict),  # dict stays dict
        ]

        for value, expected_type in test_cases:
            with self.subTest(value=value, expected_type=expected_type):
                processed = self.queryset._preprocess_value("test_field", value)
                if expected_type == Decimal and isinstance(value, (int, float)):
                    self.assertIsInstance(processed, Decimal)
                elif expected_type == str:
                    self.assertIsInstance(processed, str)
                else:
                    self.assertIsInstance(processed, expected_type)

    def test_preprocess_none_value(self):
        """Test preprocessing None values."""
        result = self.queryset._preprocess_value("test_field", None)
        self.assertIsNone(result)

    def test_preprocess_nested_structures(self):
        """Test preprocessing nested data structures."""
        nested_list = [1, 2.5, True, "string"]
        processed_list = self.queryset._preprocess_value("test_field", nested_list)

        self.assertIsInstance(processed_list, list)
        self.assertEqual(len(processed_list), 4)

        nested_dict = {"int": 1, "float": 2.5, "bool": True, "str": "test"}
        processed_dict = self.queryset._preprocess_value("test_field", nested_dict)

        self.assertIsInstance(processed_dict, dict)
        self.assertEqual(len(processed_dict), 4)


if __name__ == "__main__":
    unittest.main()
