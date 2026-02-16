"""
Comprehensive unit tests for DynamoDB database backend.
"""

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

import boto3
from botocore.exceptions import ClientError
from django.core.exceptions import ImproperlyConfigured
from django.db import utils
from django.test import TestCase, override_settings
from moto import mock_aws

from django_dynamodb_backend.db.base import (
    DatabaseWrapper,
    DynamoDBClient,
    DynamoDBCreation,
    DynamoDBCursor,
    DynamoDBFeatures,
    DynamoDBIntrospection,
    DynamoDBOperations,
    DynamoDBSchemaEditor,
    DynamoDBValidation,
    TableInfo,
)
from django_dynamodb_backend.db.compiler import (
    SQLAggregateCompiler,
    SQLCompiler,
    SQLDeleteCompiler,
    SQLInsertCompiler,
    SQLUpdateCompiler,
)


class TestDatabaseWrapper(TestCase):
    """Test DatabaseWrapper functionality."""

    def setUp(self):
        """Set up test database configuration."""
        self.db_settings = {
            "ENGINE": "django_dynamodb_backend.db",
            "NAME": "test_db",
            "REGION": "us-east-1",
            "LOCAL_ENDPOINT": "http://localhost:9000",
        }
        self.db_wrapper = DatabaseWrapper(self.db_settings, alias="test")

    def test_initialization(self):
        """Test database wrapper initialization."""
        self.assertEqual(self.db_wrapper.vendor, "dynamodb")
        self.assertEqual(self.db_wrapper.display_name, "DynamoDB")

        # Check that all required components are initialized
        self.assertIsInstance(self.db_wrapper.features, DynamoDBFeatures)
        self.assertIsInstance(self.db_wrapper.ops, DynamoDBOperations)
        self.assertIsInstance(self.db_wrapper.client, DynamoDBClient)
        self.assertIsInstance(self.db_wrapper.creation, DynamoDBCreation)
        self.assertIsInstance(self.db_wrapper.validation, DynamoDBValidation)
        self.assertIsInstance(self.db_wrapper.introspection, DynamoDBIntrospection)

    def test_get_connection_params(self):
        """Test connection parameter extraction."""
        params = self.db_wrapper.get_connection_params()

        expected_params = {
            "region_name": "us-east-1",
            "endpoint_url": "http://localhost:9000",
        }

        for key, value in expected_params.items():
            self.assertEqual(params[key], value)

    def test_get_connection_params_with_credentials(self):
        """Test connection parameters with AWS credentials."""
        db_settings = self.db_settings.copy()
        db_settings.update(
            {
                "ACCESS_KEY": "test_access_key",
                "SECRET_KEY": "test_secret_key",
                "SESSION_TOKEN": "test_session_token",
            }
        )

        db_wrapper = DatabaseWrapper(db_settings, alias="test")
        params = db_wrapper.get_connection_params()

        self.assertEqual(params["aws_access_key_id"], "test_access_key")
        self.assertEqual(params["aws_secret_access_key"], "test_secret_key")
        self.assertEqual(params["aws_session_token"], "test_session_token")

    @mock_aws
    def test_get_new_connection_success(self):
        """Test successful connection creation."""
        conn_params = {
            "region_name": "us-east-1",
            "endpoint_url": "http://localhost:9000",
        }

        connection = self.db_wrapper.get_new_connection(conn_params)

        from django_dynamodb_backend.db.base import (
            DynamoDBConnection,
        )

        self.assertIsInstance(connection, DynamoDBConnection)
        self.assertIsNotNone(connection.resource)
        self.assertIsNotNone(connection.client)

    def test_get_new_connection_failure(self):
        """Test connection creation failure."""
        # Invalid connection parameters
        conn_params = {
            "region_name": "invalid-region",
            "aws_access_key_id": "invalid_key",
            "aws_secret_access_key": "invalid_secret",
        }

        # Patch the connection pool's get_connection method
        with patch.object(
            self.db_wrapper._connection_pool,
            "get_connection",
            side_effect=Exception("Connection failed")
        ):
            with self.assertRaises(utils.DatabaseError):
                self.db_wrapper.get_new_connection(conn_params)

    def test_create_cursor(self):
        """Test cursor creation."""
        cursor = self.db_wrapper.create_cursor()
        self.assertIsInstance(cursor, DynamoDBCursor)

    def test_create_cursor_with_name(self):
        """Test cursor creation with name parameter."""
        cursor = self.db_wrapper.create_cursor(name="test_cursor")
        self.assertIsInstance(cursor, DynamoDBCursor)

    def test_is_usable_true(self):
        """Test connection usability check when connection is good."""
        # Set up a mock DynamoDBConnection object
        from django_dynamodb_backend.db.base import DynamoDBConnection

        mock_client = MagicMock()
        mock_resource = MagicMock()
        mock_client.describe_limits.return_value = {"AccountMaxReads": 40000}

        self.db_wrapper.connection = DynamoDBConnection(mock_resource, mock_client)

        self.assertTrue(self.db_wrapper.is_usable())

    def test_is_usable_false(self):
        """Test connection usability check when connection is bad."""
        # No connection
        self.db_wrapper.connection = None
        self.assertFalse(self.db_wrapper.is_usable())

        # Connection with error
        self.db_wrapper.connection = {"client": MagicMock(), "resource": MagicMock()}
        self.db_wrapper.connection["client"].describe_limits.side_effect = Exception(
            "Connection error"
        )

        self.assertFalse(self.db_wrapper.is_usable())

    def test_autocommit_methods(self):
        """Test autocommit-related methods."""
        # Should not raise errors (no-op for DynamoDB)
        self.db_wrapper._set_autocommit(True)
        self.db_wrapper._set_autocommit(False)

    def test_close_method(self):
        """Test connection closing."""
        self.db_wrapper.connection = {"test": "connection"}
        self.db_wrapper._close()
        self.assertIsNone(self.db_wrapper.connection)


class TestDynamoDBCursor(TestCase):
    """Test DynamoDB cursor functionality."""

    def setUp(self):
        """Set up test cursor."""
        self.db_wrapper = MagicMock()
        self.cursor = DynamoDBCursor(self.db_wrapper)

    def test_cursor_initialization(self):
        """Test cursor initialization."""
        self.assertEqual(self.cursor.db, self.db_wrapper)
        self.assertEqual(self.cursor.queries, [])

    def test_execute(self):
        """Test query execution (placeholder)."""
        result = self.cursor.execute("SELECT * FROM test", ["param1"])

        # Should store the query
        self.assertEqual(len(self.cursor.queries), 1)
        self.assertEqual(self.cursor.queries[0], ("SELECT * FROM test", ["param1"]))

    def test_fetch_methods(self):
        """Test fetch methods."""
        # All should return empty results for now
        self.assertIsNone(self.cursor.fetchone())
        self.assertEqual(self.cursor.fetchmany(), [])
        self.assertEqual(self.cursor.fetchall(), [])

    def test_close(self):
        """Test cursor close method."""
        # Should not raise errors
        self.cursor.close()


class TestDynamoDBOperations(TestCase):
    """Test database operations."""

    def setUp(self):
        """Set up test operations."""
        self.db_wrapper = MagicMock()
        self.ops = DynamoDBOperations(self.db_wrapper)

    def test_quote_name(self):
        """Test name quoting."""
        self.assertEqual(self.ops.quote_name("table_name"), "table_name")
        self.assertEqual(self.ops.quote_name("column name"), "column name")

    def test_sql_table_creation_suffix(self):
        """Test SQL table creation suffix."""
        self.assertEqual(self.ops.sql_table_creation_suffix(), "")

    def test_convert_values(self):
        """Test value conversion."""
        field = MagicMock()

        # Should return value as-is for basic types
        self.assertEqual(self.ops.convert_values("test", field), "test")
        self.assertEqual(self.ops.convert_values(123, field), 123)
        self.assertIsNone(self.ops.convert_values(None, field))

    def test_last_insert_id(self):
        """Test last insert ID."""
        cursor = MagicMock()
        result = self.ops.last_insert_id(cursor, "table", "pk")
        self.assertIsNone(result)  # DynamoDB doesn't use auto-increment IDs

    def test_max_name_length(self):
        """Test maximum name length."""
        self.assertEqual(self.ops.max_name_length(), 255)


class TestDynamoDBFeatures(TestCase):
    """Test database features."""

    def setUp(self):
        """Set up test features."""
        self.db_wrapper = MagicMock()
        self.features = DynamoDBFeatures(self.db_wrapper)

    def test_feature_flags(self):
        """Test DynamoDB feature flags."""
        # Features that DynamoDB doesn't support
        self.assertFalse(self.features.supports_transactions)
        self.assertFalse(self.features.supports_foreign_keys)
        self.assertFalse(self.features.supports_check_constraints)
        self.assertFalse(self.features.supports_partial_indexes)
        self.assertFalse(self.features.supports_over_clause)
        self.assertFalse(self.features.can_clone_databases)
        self.assertFalse(self.features.has_native_uuid_field)
        self.assertFalse(self.features.supports_explaining_query_execution)

        # Features that DynamoDB supports
        self.assertTrue(self.features.supports_json_field)
        self.assertTrue(self.features.supports_json_field_contains)
        self.assertTrue(self.features.supports_primitives_in_json_field)
        self.assertTrue(self.features.has_bulk_insert)
        self.assertTrue(self.features.supports_timezones)

    def test_select_for_update_properties(self):
        """Test select for update properties."""
        self.assertFalse(self.features.has_select_for_update)
        self.assertFalse(self.features.has_select_for_update_nowait)


class TestDynamoDBIntrospection(TestCase):
    """Test database introspection."""

    def setUp(self):
        """Set up test introspection."""
        self.db_wrapper = MagicMock()
        self.introspection = DynamoDBIntrospection(self.db_wrapper)

    def test_data_types_reverse(self):
        """Test reverse data type mapping."""
        expected_mappings = {
            "S": "CharField",
            "N": "IntegerField",
            "B": "BinaryField",
            "BOOL": "BooleanField",
            "M": "JSONField",
            "L": "JSONField",
        }

        for dynamo_type, django_field in expected_mappings.items():
            self.assertEqual(
                self.introspection.data_types_reverse[dynamo_type], django_field
            )

    @mock_aws
    def test_get_table_list_success(self):
        """Test successful table listing."""
        # Mock cursor and client
        cursor = MagicMock()
        mock_client = MagicMock()
        cursor.db.dynamodb_client = mock_client

        # Mock list_tables response
        mock_client.list_tables.return_value = {
            "TableNames": ["table1", "table2", "table3"]
        }

        result = self.introspection.get_table_list(cursor)

        self.assertEqual(len(result), 3)
        for i, table_info in enumerate(result, 1):
            self.assertIsInstance(table_info, TableInfo)
            self.assertEqual(table_info.name, f"table{i}")
            self.assertEqual(table_info.type, "t")

    def test_get_table_list_error(self):
        """Test table listing with error."""
        cursor = MagicMock()
        mock_client = MagicMock()
        cursor.db.dynamodb_client = mock_client

        # Mock error
        mock_client.list_tables.side_effect = Exception("Access denied")

        result = self.introspection.get_table_list(cursor)
        self.assertEqual(result, [])

    @mock_aws
    def test_get_table_description_success(self):
        """Test successful table description."""
        cursor = MagicMock()
        mock_client = MagicMock()
        cursor.db.dynamodb_client = mock_client

        # Mock describe_table response
        mock_client.describe_table.return_value = {
            "Table": {
                "AttributeDefinitions": [
                    {"AttributeName": "id", "AttributeType": "S"},
                    {"AttributeName": "name", "AttributeType": "S"},
                    {"AttributeName": "count", "AttributeType": "N"},
                ]
            }
        }

        result = self.introspection.get_table_description(cursor, "test_table")

        self.assertEqual(len(result), 3)

        # Check first column (id)
        self.assertEqual(result[0][0], "id")  # column name
        self.assertEqual(result[0][1], "S")  # data type

    def test_get_table_description_error(self):
        """Test table description with error."""
        cursor = MagicMock()
        mock_client = MagicMock()
        cursor.db.dynamodb_client = mock_client

        # Mock error
        mock_client.describe_table.side_effect = Exception("Table not found")

        result = self.introspection.get_table_description(cursor, "nonexistent_table")
        self.assertEqual(result, [])


class TestDynamoDBSchemaEditor(TestCase):
    """Test schema editor functionality."""

    def setUp(self):
        """Set up test schema editor."""
        self.db_wrapper = MagicMock()
        self.schema_editor = DynamoDBSchemaEditor(self.db_wrapper)

    def test_initialization(self):
        """Test schema editor initialization."""
        self.assertEqual(self.schema_editor.connection, self.db_wrapper)

    @mock_aws
    def test_create_model_success(self):
        """Test successful model/table creation."""
        # Mock model
        model = MagicMock()
        model._meta.db_table = "test_table"
        model._meta.pk = MagicMock()
        model._meta.pk.column = "id"

        # Mock client
        mock_client = MagicMock()
        self.schema_editor.connection.dynamodb_client = mock_client

        # Test creation
        self.schema_editor.create_model(model)

        # Verify create_table was called
        mock_client.create_table.assert_called_once()
        call_args = mock_client.create_table.call_args[1]
        self.assertEqual(call_args["TableName"], "test_table")
        self.assertEqual(call_args["BillingMode"], "PAY_PER_REQUEST")

    def test_create_model_no_primary_key(self):
        """Test model creation without primary key."""
        model = MagicMock()
        model.__name__ = "TestModel"  # Add __name__ for error message
        model._meta.db_table = "test_table"
        model._meta.pk = None

        with self.assertRaises(ImproperlyConfigured):
            self.schema_editor.create_model(model)

    @mock_aws
    def test_delete_model_success(self):
        """Test successful model/table deletion."""
        model = MagicMock()
        model._meta.db_table = "test_table"

        mock_client = MagicMock()
        self.schema_editor.connection.dynamodb_client = mock_client

        self.schema_editor.delete_model(model)

        mock_client.delete_table.assert_called_once_with(TableName="test_table")

    def test_add_field(self):
        """Test adding field (should be no-op for DynamoDB)."""
        model = MagicMock()
        field = MagicMock()

        # Should not raise error
        self.schema_editor.add_field(model, field)

    def test_remove_field(self):
        """Test removing field (should be no-op for DynamoDB)."""
        model = MagicMock()
        field = MagicMock()

        # Should not raise error
        self.schema_editor.remove_field(model, field)

    def test_alter_field(self):
        """Test altering field (should be no-op for DynamoDB)."""
        model = MagicMock()
        old_field = MagicMock()
        new_field = MagicMock()

        # Should not raise error
        self.schema_editor.alter_field(model, old_field, new_field)


class TestTableInfo(TestCase):
    """Test TableInfo helper class."""

    def test_table_info_creation(self):
        """Test TableInfo creation and attributes."""
        table_info = TableInfo("test_table", "t")

        self.assertEqual(table_info.name, "test_table")
        self.assertEqual(table_info.type, "t")

    def test_table_info_default_type(self):
        """Test TableInfo with default type."""
        table_info = TableInfo("test_table")

        self.assertEqual(table_info.name, "test_table")
        self.assertEqual(table_info.type, "t")


class TestDatabaseCreation(TestCase):
    """Test database creation functionality."""

    def setUp(self):
        """Set up test database creation."""
        self.db_wrapper = MagicMock()
        self.creation = DynamoDBCreation(self.db_wrapper)

    def test_create_test_db(self):
        """Test test database creation."""
        with patch.object(
            self.creation, "_get_test_db_name", return_value="test_db_name"
        ):
            result = self.creation.create_test_db()
            self.assertEqual(result, "test_db_name")

    def test_destroy_test_db(self):
        """Test test database destruction."""
        # Should not raise error
        self.creation.destroy_test_db("test_db_name")


class TestDynamoDBValidation(TestCase):
    """Test database validation."""

    def setUp(self):
        """Set up test validation."""
        self.db_wrapper = MagicMock()
        self.validation = DynamoDBValidation(self.db_wrapper)

    def test_check(self):
        """Test database check method."""
        issues = self.validation.check()
        self.assertEqual(issues, [])


class TestDynamoDBClient(TestCase):
    """Test database client."""

    def setUp(self):
        """Set up test client."""
        self.db_wrapper = MagicMock()
        self.client = DynamoDBClient(self.db_wrapper)

    def test_executable_name(self):
        """Test executable name."""
        self.assertEqual(self.client.executable_name, "aws")


if __name__ == "__main__":
    unittest.main()
