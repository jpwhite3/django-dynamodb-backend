"""
Tests for SQL Compiler integration with enhanced QuerySet.
"""

import unittest
from unittest.mock import MagicMock, patch

from django.db import models
from django.db.models.sql import Query
from django.test import TestCase

from django_dynamodb_backend.db.compiler import SQLCompiler
from django_dynamodb_backend.models import DynamoDBModel


class TestSQLCompilerIntegration(TestCase):
    """Test SQL compiler integration with QuerySet."""

    def setUp(self):
        """Set up test environment."""

        # Create a test model inheriting from DynamoDBModel to avoid field clashes
        class CompilerTestModel(DynamoDBModel):
            test_name = models.CharField(primary_key=True, max_length=100)
            test_age = models.IntegerField()
            test_active = models.BooleanField(default=True)

            class Meta:
                app_label = "tests"

        self.TestModel = CompilerTestModel

        # Create a mock query and connection
        self.mock_query = MagicMock(spec=Query)
        self.mock_query.model = self.TestModel
        self.mock_connection = MagicMock()

        # Create compiler instance
        self.compiler = SQLCompiler(self.mock_query, self.mock_connection, "default")

    def test_compiler_initialization(self):
        """Test compiler initialization with QuerySet integration."""
        self.assertEqual(self.compiler.query, self.mock_query)
        self.assertEqual(self.compiler.connection, self.mock_connection)
        self.assertEqual(self.compiler.using, "default")

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_results_iter_basic(self, mock_queryset_class):
        """Test results_iter method creates and uses QuerySet."""
        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        # Set up query with no filters
        self.mock_query.where = None
        self.mock_query.order_by = None
        self.mock_query.low_mark = None
        self.mock_query.high_mark = None

        # Test results_iter
        results = list(self.compiler.results_iter())

        # Should create QuerySet
        mock_queryset_class.assert_called_once_with(
            model=self.TestModel, using="default"
        )

        self.assertEqual(results, [])

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_results_iter_with_filters(self, mock_queryset_class):
        """Test results_iter applies filters correctly."""
        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        # Mock WHERE clause
        mock_where = MagicMock()
        mock_where.children = []

        # Mock a filter child using test_name field
        mock_child = MagicMock()
        mock_child.lhs.target.name = "test_name"
        mock_child.lookup_name = "exact"
        mock_child.rhs = "test_value"
        mock_where.children = [mock_child]

        self.mock_query.where = mock_where
        self.mock_query.order_by = None
        self.mock_query.low_mark = None
        self.mock_query.high_mark = None

        # Test results_iter
        list(self.compiler.results_iter())

        # Should apply filters with test_name field
        mock_queryset.filter.assert_called_once_with(test_name="test_value")

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_results_iter_with_ordering(self, mock_queryset_class):
        """Test results_iter applies ordering correctly."""
        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.order_by.return_value = mock_queryset
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        # Mock ORDER BY clause
        mock_order_col = MagicMock()
        mock_order_col.col.target.name = "test_name"
        mock_order_col.descending = False

        self.mock_query.where = None
        self.mock_query.order_by = [mock_order_col]
        self.mock_query.low_mark = None
        self.mock_query.high_mark = None

        # Test results_iter
        list(self.compiler.results_iter())

        # Should apply ordering
        mock_queryset.order_by.assert_called_once_with("test_name")

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_results_iter_with_descending_order(self, mock_queryset_class):
        """Test results_iter handles descending order correctly."""
        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.order_by.return_value = mock_queryset
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        # Mock ORDER BY clause with descending
        mock_order_col = MagicMock()
        mock_order_col.col.target.name = "test_age"
        mock_order_col.descending = True

        self.mock_query.where = None
        self.mock_query.order_by = [mock_order_col]
        self.mock_query.low_mark = None
        self.mock_query.high_mark = None

        # Test results_iter
        list(self.compiler.results_iter())

        # Should apply descending ordering with test_age field
        mock_queryset.order_by.assert_called_once_with("-test_age")

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_results_iter_with_limits(self, mock_queryset_class):
        """Test results_iter applies limits (slicing) correctly."""
        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.__getitem__ = MagicMock(return_value=mock_queryset)
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        self.mock_query.where = None
        self.mock_query.order_by = None
        self.mock_query.low_mark = 10
        self.mock_query.high_mark = 20

        # Test results_iter
        list(self.compiler.results_iter())

        # Should apply slicing
        mock_queryset.__getitem__.assert_called_once_with(slice(10, 20))

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_results_iter_with_open_ended_limit(self, mock_queryset_class):
        """Test results_iter handles open-ended limits."""
        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.__getitem__ = MagicMock(return_value=mock_queryset)
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        self.mock_query.where = None
        self.mock_query.order_by = None
        self.mock_query.low_mark = 5
        self.mock_query.high_mark = None

        # Test results_iter
        list(self.compiler.results_iter())

        # Should apply open-ended slicing
        mock_queryset.__getitem__.assert_called_once_with(slice(5, None))

    def test_extract_filter_kwargs_empty(self):
        """Test _extract_filter_kwargs with no WHERE clause."""
        kwargs = self.compiler._extract_filter_kwargs(None)
        self.assertEqual(kwargs, {})

    def test_extract_filter_kwargs_with_filters(self):
        """Test _extract_filter_kwargs with actual filters."""
        # Mock WHERE node with children
        mock_where = MagicMock()

        # Mock filter child - exact lookup
        mock_child1 = MagicMock()
        mock_child1.lhs.target.name = "test_name"
        mock_child1.lookup_name = "exact"
        mock_child1.rhs = "John"

        # Mock filter child - range lookup
        mock_child2 = MagicMock()
        mock_child2.lhs.target.name = "test_age"
        mock_child2.lookup_name = "gte"
        mock_child2.rhs = 18

        mock_where.children = [mock_child1, mock_child2]

        kwargs = self.compiler._extract_filter_kwargs(mock_where)

        expected = {"test_name": "John", "test_age__gte": 18}
        self.assertEqual(kwargs, expected)

    def test_convert_result_to_row_with_select(self):
        """Test _convert_result_to_row with specific SELECT fields."""
        # Mock model instance with correct field names
        mock_instance = MagicMock()
        mock_instance.test_name = "John"
        mock_instance.test_age = 25

        # Mock query with select fields
        mock_col1 = MagicMock()
        mock_col1.target.name = "test_name"
        mock_col2 = MagicMock()
        mock_col2.target.name = "test_age"

        self.mock_query.select = [mock_col1, mock_col2]

        row = self.compiler._convert_result_to_row(mock_instance)

        self.assertEqual(row, ["John", 25])

    def test_convert_result_to_row_all_fields(self):
        """Test _convert_result_to_row with all model fields."""
        # Mock model instance with correct field names
        mock_instance = MagicMock()
        mock_instance.test_name = "John"
        mock_instance.test_age = 25
        mock_instance.test_active = True

        # Mock model fields matching CompilerTestModel
        mock_field1 = MagicMock()
        mock_field1.name = "test_name"
        mock_field2 = MagicMock()
        mock_field2.name = "test_age"
        mock_field3 = MagicMock()
        mock_field3.name = "test_active"

        self.mock_query.model._meta.fields = [mock_field1, mock_field2, mock_field3]
        self.mock_query.select = None

        row = self.compiler._convert_result_to_row(mock_instance)

        self.assertEqual(row, ["John", 25, True])

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_execute_sql_single_result(self, mock_queryset_class):
        """Test execute_sql with SINGLE result type."""
        from django.db.models.sql.constants import SINGLE

        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset

        # Mock results_iter to return test data
        self.compiler.results_iter = MagicMock(return_value=[["John", 25]])

        self.mock_query.model = self.TestModel

        result = self.compiler.execute_sql(result_type=SINGLE)

        self.assertEqual(result, ["John", 25])

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_execute_sql_multiple_results(self, mock_queryset_class):
        """Test execute_sql with multiple results."""
        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset

        # Mock results_iter to return test data
        test_results = [["John", 25], ["Jane", 30]]
        self.compiler.results_iter = MagicMock(return_value=test_results)

        self.mock_query.model = self.TestModel

        results = self.compiler.execute_sql()

        self.assertEqual(results, test_results)

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_execute_sql_no_results(self, mock_queryset_class):
        """Test execute_sql with no results."""
        from django.db.models.sql.constants import SINGLE

        # Set up mock QuerySet
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset

        # Mock results_iter to return empty
        self.compiler.results_iter = MagicMock(return_value=[])

        self.mock_query.model = self.TestModel

        # Test SINGLE result type
        result_single = self.compiler.execute_sql(result_type=SINGLE)
        self.assertIsNone(result_single)

        # Test multiple results type
        results_multiple = self.compiler.execute_sql()
        self.assertEqual(results_multiple, [])


class TestCompilerErrorHandling(TestCase):
    """Test error handling in compiler integration."""

    def setUp(self):
        """Set up test environment."""
        self.mock_query = MagicMock()
        self.mock_connection = MagicMock()
        self.compiler = SQLCompiler(self.mock_query, self.mock_connection, "default")

    def test_results_iter_no_model(self):
        """Test results_iter when query has no model."""
        self.mock_query.model = None

        results = list(self.compiler.results_iter())
        self.assertEqual(results, [])

    def test_results_iter_exception_handling(self):
        """Test results_iter handles exceptions gracefully."""
        # Set up to raise exception
        self.mock_query.model = MagicMock()

        with patch(
            "django_dynamodb_backend.managers.DynamoDBQuerySet",
            side_effect=Exception("Test error"),
        ):
            results = list(self.compiler.results_iter())
            self.assertEqual(results, [])

    def test_execute_sql_exception_handling(self):
        """Test execute_sql handles exceptions gracefully."""
        from django.db.models.sql.constants import SINGLE

        # Mock results_iter to raise exception
        self.compiler.results_iter = MagicMock(side_effect=Exception("Test error"))

        # Test SINGLE result type
        result_single = self.compiler.execute_sql(result_type=SINGLE)
        self.assertIsNone(result_single)

        # Test multiple results type
        results_multiple = self.compiler.execute_sql()
        self.assertEqual(results_multiple, [])

    def test_extract_filter_kwargs_exception_handling(self):
        """Test _extract_filter_kwargs handles malformed WHERE nodes."""
        # Mock malformed WHERE node that causes an exception during iteration
        mock_where = MagicMock()
        # Make children iteration raise an exception
        mock_where.children = MagicMock()
        mock_where.children.__iter__ = MagicMock(side_effect=TypeError("Not iterable"))

        # Should return empty dict due to exception handling
        kwargs = self.compiler._extract_filter_kwargs(mock_where)
        self.assertEqual(kwargs, {})

    def test_convert_result_to_row_exception_handling(self):
        """Test _convert_result_to_row handles exceptions."""
        # Mock instance where getattr raises an exception
        mock_instance = MagicMock()
        # Make getattr on the instance raise when accessing any field
        mock_instance.configure_mock(**{"test_name": property(lambda s: (_ for _ in ()).throw(AttributeError()))})

        # Mock query with select fields that will trigger the exception path
        mock_col = MagicMock()
        # Make target.name raise when accessed
        type(mock_col).target = property(lambda self: (_ for _ in ()).throw(AttributeError("No target")))
        self.mock_query.select = [mock_col]

        row = self.compiler._convert_result_to_row(mock_instance)
        self.assertEqual(row, [])


if __name__ == "__main__":
    unittest.main()
