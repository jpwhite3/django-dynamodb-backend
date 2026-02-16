"""
Comprehensive unit tests for DynamoDB SQL compiler.
"""

import unittest
from unittest.mock import MagicMock, patch

from django.db.models.sql.constants import MULTI, SINGLE
from django.test import TestCase

from django_dynamodb_backend.db.compiler import (
    SQLAggregateCompiler,
    SQLCompiler,
    SQLDeleteCompiler,
    SQLInsertCompiler,
    SQLUpdateCompiler,
)


class TestSQLCompiler(TestCase):
    """Test SQL compiler functionality."""

    def setUp(self):
        """Set up test compiler."""
        self.query = MagicMock()
        self.connection = MagicMock()
        self.using = "default"

        self.compiler = SQLCompiler(self.query, self.connection, self.using)

    def test_compiler_initialization(self):
        """Test compiler initialization."""
        self.assertEqual(self.compiler.query, self.query)
        self.assertEqual(self.compiler.connection, self.connection)
        self.assertEqual(self.compiler.using, self.using)
        self.assertIsNone(self.compiler.dynamodb_operation)
        self.assertIsNone(self.compiler.table_name)
        self.assertEqual(self.compiler.filter_expression, [])
        self.assertIsNone(self.compiler.projection_expression)

    def test_as_sql_basic(self):
        """Test basic SQL to DynamoDB conversion."""
        # Mock model for table name
        self.compiler.query.model = MagicMock()
        self.compiler.query.model._meta.db_table = "test_table"
        self.compiler.query.where = None
        self.compiler.query.select = None
        self.compiler.query.order_by = None

        result, params = self.compiler.as_sql()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["table_name"], "test_table")
        self.assertEqual(result["operation_type"], "scan")
        self.assertEqual(params, [])

    def test_analyze_query_with_model(self):
        """Test query analysis with model."""
        self.compiler.query.model = MagicMock()
        self.compiler.query.model._meta.db_table = "test_table"
        self.compiler.query.where = None

        self.compiler._analyze_query()

        self.assertEqual(self.compiler.table_name, "test_table")

    def test_analyze_filters(self):
        """Test filter analysis."""
        # Mock WHERE clause with children
        where_child = MagicMock()
        where_child.lhs.target.column = "name"
        where_child.lookup_name = "exact"
        where_child.rhs = "test_value"

        where_clause = MagicMock()
        where_clause.children = [where_child]

        self.compiler.query.where = where_clause

        self.compiler._analyze_filters()

        self.assertEqual(len(self.compiler.filter_expression), 1)
        filter_dict = self.compiler.filter_expression[0]
        self.assertEqual(filter_dict["field"], "name")
        self.assertEqual(filter_dict["operation"], "=")
        self.assertEqual(filter_dict["value"], "test_value")

    def test_convert_lookup_exact(self):
        """Test exact lookup conversion."""
        result = self.compiler._convert_lookup("name", "exact", "test")

        expected = {"field": "name", "operation": "=", "value": "test"}
        self.assertEqual(result, expected)

    def test_convert_lookup_comparison(self):
        """Test comparison lookup conversions."""
        test_cases = [
            ("gt", ">"),
            ("gte", ">="),
            ("lt", "<"),
            ("lte", "<="),
        ]

        for lookup_type, expected_op in test_cases:
            with self.subTest(lookup=lookup_type):
                result = self.compiler._convert_lookup("count", lookup_type, 10)
                self.assertEqual(result["operation"], expected_op)
                self.assertEqual(result["value"], 10)

    def test_convert_lookup_string_operations(self):
        """Test string operation lookup conversions."""
        test_cases = [
            ("contains", "contains"),
            ("startswith", "begins_with"),
        ]

        for lookup_type, expected_op in test_cases:
            with self.subTest(lookup=lookup_type):
                result = self.compiler._convert_lookup("name", lookup_type, "test")
                self.assertEqual(result["operation"], expected_op)
                self.assertEqual(result["value"], "test")

    def test_convert_lookup_unsupported(self):
        """Test unsupported lookup conversion."""
        result = self.compiler._convert_lookup("name", "unsupported", "value")
        self.assertIsNone(result)

    def test_analyze_select(self):
        """Test SELECT clause analysis."""
        # Mock select columns
        col1 = MagicMock()
        col1.target.column = "name"
        col2 = MagicMock()
        col2.target.column = "count"

        self.compiler.query.select = [col1, col2]

        self.compiler._analyze_select()

        self.assertEqual(self.compiler.projection_expression, ["name", "count"])

    def test_build_dynamodb_query_scan(self):
        """Test building DynamoDB scan query."""
        self.compiler.table_name = "test_table"
        self.compiler.filter_expression = [
            {"field": "name", "operation": "=", "value": "test"}
        ]
        self.compiler.projection_expression = ["name", "count"]

        result = self.compiler._build_dynamodb_query()

        expected = {
            "operation_type": "scan",
            "table_name": "test_table",
            "filters": [{"field": "name", "operation": "=", "value": "test"}],
            "projection": ["name", "count"],
        }
        self.assertEqual(result, expected)

    def test_can_use_query(self):
        """Test query vs scan determination."""
        # Currently always returns False
        result = self.compiler._can_use_query()
        self.assertFalse(result)

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_execute_sql_single(self, mock_queryset_class):
        """Test execute_sql with SINGLE result type."""
        # Set up mock QuerySet that returns no results
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        # Set up query with model but no WHERE clause
        self.query.model = MagicMock()
        self.query.where = None
        self.query.order_by = None
        self.query.low_mark = None
        self.query.high_mark = None

        result = self.compiler.execute_sql(result_type=SINGLE)
        self.assertIsNone(result)

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_execute_sql_multi(self, mock_queryset_class):
        """Test execute_sql with MULTI result type."""
        # Set up mock QuerySet that returns no results
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        # Set up query with model but no WHERE clause
        self.query.model = MagicMock()
        self.query.where = None
        self.query.order_by = None
        self.query.low_mark = None
        self.query.high_mark = None

        result = self.compiler.execute_sql(result_type=MULTI)
        self.assertEqual(result, [])

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet")
    def test_results_iter(self, mock_queryset_class):
        """Test results iterator."""
        # Set up mock QuerySet that returns no results
        mock_queryset = MagicMock()
        mock_queryset_class.return_value = mock_queryset
        mock_queryset.__iter__ = MagicMock(return_value=iter([]))

        # Set up query with model but no WHERE clause
        self.query.model = MagicMock()
        self.query.where = None
        self.query.order_by = None
        self.query.low_mark = None
        self.query.high_mark = None

        result = self.compiler.results_iter()
        self.assertEqual(list(result), [])


class TestSQLInsertCompiler(TestCase):
    """Test SQL INSERT compiler."""

    def setUp(self):
        """Set up test INSERT compiler."""
        self.query = MagicMock()
        self.connection = MagicMock()
        self.using = "default"

        self.compiler = SQLInsertCompiler(self.query, self.connection, self.using)

    def test_compiler_initialization(self):
        """Test INSERT compiler initialization."""
        self.assertEqual(self.compiler.query, self.query)
        self.assertEqual(self.compiler.connection, self.connection)
        self.assertEqual(self.compiler.using, self.using)

    def test_as_sql_basic(self):
        """Test basic INSERT to DynamoDB conversion."""
        # Mock query data
        self.compiler.query.model = MagicMock()
        self.compiler.query.model._meta.db_table = "test_table"

        # Mock fields and values
        field1 = MagicMock()
        field1.column = "name"
        field2 = MagicMock()
        field2.column = "count"

        self.compiler.query.fields = [field1, field2]
        self.compiler.query.objs = [["test_name", 42]]

        result, params = self.compiler.as_sql()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["operation_type"], "put_item")
        self.assertEqual(result["table_name"], "test_table")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["name"], "test_name")
        self.assertEqual(result["items"][0]["count"], 42)
        self.assertEqual(params, [])


class TestSQLUpdateCompiler(TestCase):
    """Test SQL UPDATE compiler."""

    def setUp(self):
        """Set up test UPDATE compiler."""
        self.query = MagicMock()
        self.connection = MagicMock()
        self.using = "default"

        self.compiler = SQLUpdateCompiler(self.query, self.connection, self.using)

    def test_compiler_initialization(self):
        """Test UPDATE compiler initialization."""
        self.assertEqual(self.compiler.query, self.query)
        self.assertEqual(self.compiler.connection, self.connection)
        self.assertEqual(self.compiler.using, self.using)

    def test_as_sql_basic(self):
        """Test basic UPDATE to DynamoDB conversion."""
        # Mock query data
        self.compiler.query.model = MagicMock()
        self.compiler.query.model._meta.db_table = "test_table"

        # Mock update values
        field = MagicMock()
        field.column = "count"
        model = MagicMock()

        self.compiler.query.values = [(field, model, 100)]
        self.compiler.query.where = MagicMock()  # Mock WHERE clause

        result, params = self.compiler.as_sql()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["operation_type"], "update_item")
        self.assertEqual(result["table_name"], "test_table")
        self.assertEqual(result["updates"]["count"], 100)
        self.assertEqual(params, [])


class TestSQLDeleteCompiler(TestCase):
    """Test SQL DELETE compiler."""

    def setUp(self):
        """Set up test DELETE compiler."""
        self.query = MagicMock()
        self.connection = MagicMock()
        self.using = "default"

        self.compiler = SQLDeleteCompiler(self.query, self.connection, self.using)

    def test_compiler_initialization(self):
        """Test DELETE compiler initialization."""
        self.assertEqual(self.compiler.query, self.query)
        self.assertEqual(self.compiler.connection, self.connection)
        self.assertEqual(self.compiler.using, self.using)

    def test_as_sql_basic(self):
        """Test basic DELETE to DynamoDB conversion."""
        # Mock query data
        self.compiler.query.model = MagicMock()
        self.compiler.query.model._meta.db_table = "test_table"
        self.compiler.query.where = MagicMock()  # Mock WHERE clause

        result, params = self.compiler.as_sql()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["operation_type"], "delete_item")
        self.assertEqual(result["table_name"], "test_table")
        self.assertEqual(params, [])


class TestSQLAggregateCompiler(TestCase):
    """Test SQL aggregate compiler."""

    def setUp(self):
        """Set up test aggregate compiler."""
        self.query = MagicMock()
        self.connection = MagicMock()
        self.using = "default"

        self.compiler = SQLAggregateCompiler(self.query, self.connection, self.using)

    def test_compiler_initialization(self):
        """Test aggregate compiler initialization."""
        self.assertEqual(self.compiler.query, self.query)
        self.assertEqual(self.compiler.connection, self.connection)
        self.assertEqual(self.compiler.using, self.using)

    def test_as_sql_unsupported(self):
        """Test aggregate operations (unsupported)."""
        result, params = self.compiler.as_sql()

        # Should return None for unsupported operations
        self.assertIsNone(result)
        self.assertEqual(params, [])


class TestCompilerEdgeCases(TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        """Set up test compiler."""
        self.query = MagicMock()
        self.connection = MagicMock()
        self.using = "default"
        self.compiler = SQLCompiler(self.query, self.connection, self.using)

    def test_as_sql_with_exception(self):
        """Test as_sql method when an exception occurs."""
        # Mock an exception during analysis
        with patch.object(
            self.compiler, "_analyze_query", side_effect=Exception("Test error")
        ):
            with self.assertRaises(Exception):
                self.compiler.as_sql()

    def test_analyze_query_no_model(self):
        """Test query analysis without model."""
        self.compiler.query.model = None
        self.compiler.query.where = None

        # Should not raise error
        self.compiler._analyze_query()
        self.assertIsNone(self.compiler.table_name)

    def test_analyze_filters_no_children(self):
        """Test filter analysis with no WHERE children."""
        where_clause = MagicMock()
        where_clause.children = []
        self.compiler.query.where = where_clause

        self.compiler._analyze_filters()

        self.assertEqual(self.compiler.filter_expression, [])

    def test_analyze_select_no_select(self):
        """Test SELECT analysis with no SELECT clause."""
        self.compiler.query.select = None

        self.compiler._analyze_select()

        self.assertIsNone(self.compiler.projection_expression)

    def test_build_dynamodb_query_minimal(self):
        """Test building DynamoDB query with minimal data."""
        self.compiler.table_name = "test_table"

        result = self.compiler._build_dynamodb_query()

        expected = {
            "operation_type": "scan",
            "table_name": "test_table",
            "filters": [],
            "projection": None,
        }
        self.assertEqual(result, expected)


class TestCompilerWithComplexQueries(TestCase):
    """Test compiler with complex query scenarios."""

    def setUp(self):
        """Set up test compiler."""
        self.query = MagicMock()
        self.connection = MagicMock()
        self.using = "default"
        self.compiler = SQLCompiler(self.query, self.connection, self.using)

    def test_multiple_filters(self):
        """Test query with multiple filters."""
        # Mock WHERE clause with multiple children
        child1 = MagicMock()
        child1.lhs.target.column = "name"
        child1.lookup_name = "exact"
        child1.rhs = "test"

        child2 = MagicMock()
        child2.lhs.target.column = "count"
        child2.lookup_name = "gt"
        child2.rhs = 10

        where_clause = MagicMock()
        where_clause.children = [child1, child2]

        self.compiler.query.where = where_clause

        self.compiler._analyze_filters()

        self.assertEqual(len(self.compiler.filter_expression), 2)

        # Check first filter
        self.assertEqual(self.compiler.filter_expression[0]["field"], "name")
        self.assertEqual(self.compiler.filter_expression[0]["operation"], "=")

        # Check second filter
        self.assertEqual(self.compiler.filter_expression[1]["field"], "count")
        self.assertEqual(self.compiler.filter_expression[1]["operation"], ">")

    def test_query_with_select_and_filters(self):
        """Test complex query with SELECT and WHERE clauses."""
        # Set up model
        self.compiler.query.model = MagicMock()
        self.compiler.query.model._meta.db_table = "complex_table"

        # Set up SELECT
        col = MagicMock()
        col.target.column = "selected_field"
        self.compiler.query.select = [col]

        # Set up WHERE
        where_child = MagicMock()
        where_child.lhs.target.column = "filter_field"
        where_child.lookup_name = "contains"
        where_child.rhs = "substring"

        where_clause = MagicMock()
        where_clause.children = [where_child]
        self.compiler.query.where = where_clause

        # Set up ORDER BY
        self.compiler.query.order_by = ["created_at"]

        result, params = self.compiler.as_sql()

        # Verify result structure
        self.assertEqual(result["table_name"], "complex_table")
        self.assertEqual(result["projection"], ["selected_field"])
        self.assertEqual(len(result["filters"]), 1)
        self.assertEqual(result["filters"][0]["field"], "filter_field")
        self.assertEqual(result["filters"][0]["operation"], "contains")


if __name__ == "__main__":
    unittest.main()
