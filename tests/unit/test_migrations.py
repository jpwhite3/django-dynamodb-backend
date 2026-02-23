"""
Unit tests for DynamoDB migration system.
"""

import unittest
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from django_dynamodb_backend.migration_executor import (
    MigrationExecutor,
    MigrationGraph,
    MigrationLoader,
    MigrationNode,
)
from django_dynamodb_backend.migrations_dynamo import (
    CreateTable,
    DataMigration,
    DynamoDBMigration,
    DynamoDBOperation,
    RunPython,
    UpdateTableCapacity,
)
from django_dynamodb_backend.models import MyModel


class TestDynamoDBOperation(TestCase):
    """Test base DynamoDB operation functionality."""

    def setUp(self):
        self.operation = DynamoDBOperation(MyModel)

    def test_initialization(self):
        """Test operation initialization."""
        self.assertEqual(self.operation.model_class, MyModel)
        self.assertEqual(self.operation.model_name, "MyModel")

    def test_execute_not_implemented(self):
        """Test that base execute raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.operation.execute()

    def test_reverse_not_implemented(self):
        """Test that base reverse raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.operation.reverse()

    def test_describe(self):
        """Test operation description."""
        description = self.operation.describe()
        self.assertIn("DynamoDBOperation", description)
        self.assertIn("MyModel", description)


class TestCreateTable(TestCase):
    """Test CreateTable operation."""

    def setUp(self):
        self.operation = CreateTable(MyModel, read_capacity=10, write_capacity=5)

    def test_initialization(self):
        """Test CreateTable initialization."""
        self.assertEqual(self.operation.read_capacity, 10)
        self.assertEqual(self.operation.write_capacity, 5)

    @patch("django_dynamodb_backend.models.MyModel._get_pynamodb_model")
    def test_execute_table_exists(self, mock_get_model):
        """Test execute when table already exists."""
        mock_pynamodb_model = MagicMock()
        mock_pynamodb_model.exists.return_value = True
        mock_pynamodb_model.Meta.table_name = "test_table"
        mock_get_model.return_value = mock_pynamodb_model

        # Should not raise exception
        self.operation.execute()

        # Should not call create_table
        mock_pynamodb_model.create_table.assert_not_called()

    @patch("django_dynamodb_backend.models.MyModel._get_pynamodb_model")
    def test_execute_create_table(self, mock_get_model):
        """Test execute creates table when it doesn't exist."""
        mock_pynamodb_model = MagicMock()
        mock_pynamodb_model.exists.return_value = False
        mock_pynamodb_model.Meta.table_name = "test_table"
        mock_get_model.return_value = mock_pynamodb_model

        self.operation.execute()

        mock_pynamodb_model.create_table.assert_called_once_with(
            read_capacity_units=10, write_capacity_units=5, wait=True
        )

    @patch("django_dynamodb_backend.models.MyModel._get_pynamodb_model")
    def test_reverse_delete_table(self, mock_get_model):
        """Test reverse deletes table."""
        mock_pynamodb_model = MagicMock()
        mock_pynamodb_model.exists.return_value = True
        mock_pynamodb_model.Meta.table_name = "test_table"
        mock_get_model.return_value = mock_pynamodb_model

        self.operation.reverse()

        mock_pynamodb_model.delete_table.assert_called_once()

    def test_describe(self):
        """Test operation description."""
        description = self.operation.describe()
        self.assertIn("Create table for MyModel", description)
        self.assertIn("Read: 10", description)
        self.assertIn("Write: 5", description)


class TestUpdateTableCapacity(TestCase):
    """Test UpdateTableCapacity operation."""

    def setUp(self):
        self.operation = UpdateTableCapacity(
            MyModel, read_capacity=20, write_capacity=10
        )

    @patch("django_dynamodb_backend.models.MyModel._get_pynamodb_model")
    def test_execute_update_capacity(self, mock_get_model):
        """Test execute updates table capacity."""
        mock_pynamodb_model = MagicMock()
        mock_pynamodb_model.exists.return_value = True

        # Mock table description
        mock_pynamodb_model.describe_table.return_value = {
            "Table": {
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                }
            }
        }
        mock_get_model.return_value = mock_pynamodb_model

        self.operation.execute()

        mock_pynamodb_model.update_table.assert_called_once_with(
            read_capacity_units=20, write_capacity_units=10
        )

    @patch("django_dynamodb_backend.models.MyModel._get_pynamodb_model")
    def test_reverse_restore_capacity(self, mock_get_model):
        """Test reverse restores previous capacity."""
        mock_pynamodb_model = MagicMock()
        mock_pynamodb_model.exists.return_value = True

        # Set up old capacity
        self.operation._old_capacity = {"read_capacity": 5, "write_capacity": 3}
        mock_get_model.return_value = mock_pynamodb_model

        self.operation.reverse()

        mock_pynamodb_model.update_table.assert_called_once_with(
            read_capacity_units=5, write_capacity_units=3
        )


class TestRunPython(TestCase):
    """Test RunPython operation."""

    def test_execute_callable(self):
        """Test execute with callable function."""
        mock_func = MagicMock()
        operation = RunPython(mock_func)

        operation.execute()

        mock_func.assert_called_once()

    def test_execute_string_code_raises(self):
        """Test execute with string code raises TypeError (exec is disallowed)."""
        operation = RunPython("x = 1 + 1")

        with self.assertRaises(TypeError):
            operation.execute()

    def test_reverse_with_function(self):
        """Test reverse with reverse function."""
        mock_func = MagicMock()
        mock_reverse_func = MagicMock()
        operation = RunPython(mock_func, mock_reverse_func)

        operation.reverse()

        mock_reverse_func.assert_called_once()

    def test_reverse_without_function(self):
        """Test reverse without reverse function."""
        mock_func = MagicMock()
        operation = RunPython(mock_func)

        # Should not raise exception
        operation.reverse()


class TestDataMigration(TestCase):
    """Test DataMigration operation."""

    def setUp(self):
        self.mock_migration_func = MagicMock()
        self.mock_reverse_func = MagicMock()
        self.operation = DataMigration(
            MyModel, self.mock_migration_func, self.mock_reverse_func
        )

    @patch("django_dynamodb_backend.models.MyModel._get_pynamodb_model")
    def test_execute_data_migration(self, mock_get_model):
        """Test execute runs migration function on all items."""
        mock_pynamodb_model = MagicMock()
        mock_items = [MagicMock(), MagicMock(), MagicMock()]
        mock_pynamodb_model.scan.return_value = mock_items
        mock_get_model.return_value = mock_pynamodb_model

        self.operation.execute()

        # Should call migration function for each item
        self.assertEqual(self.mock_migration_func.call_count, 3)
        for item in mock_items:
            self.mock_migration_func.assert_any_call(item)

    @patch("django_dynamodb_backend.models.MyModel._get_pynamodb_model")
    def test_reverse_data_migration(self, mock_get_model):
        """Test reverse runs reverse function on all items."""
        mock_pynamodb_model = MagicMock()
        mock_items = [MagicMock(), MagicMock()]
        mock_pynamodb_model.scan.return_value = mock_items
        mock_get_model.return_value = mock_pynamodb_model

        self.operation.reverse()

        # Should call reverse function for each item
        self.assertEqual(self.mock_reverse_func.call_count, 2)
        for item in mock_items:
            self.mock_reverse_func.assert_any_call(item)


class TestDynamoDBMigration(TestCase):
    """Test DynamoDB migration base class."""

    def setUp(self):
        self.migration = DynamoDBMigration(name="test_migration", app_label="test_app")
        self.migration.operations = [MagicMock(), MagicMock()]

    @patch("django_dynamodb_backend.migrations_dynamo.DynamoDBMigrationState.exists")
    @patch(
        "django_dynamodb_backend.migrations_dynamo.DynamoDBMigrationState.create_table"
    )
    def test_apply(self, mock_create_table, mock_exists):
        """Test migration apply method."""
        mock_exists.return_value = True

        # Mock operations
        for operation in self.migration.operations:
            operation.describe.return_value = "Test operation"

        with patch.object(self.migration, "_record_migration") as mock_record:
            self.migration.apply()

            # Should execute all operations
            for operation in self.migration.operations:
                operation.execute.assert_called_once()

            # Should record migration
            mock_record.assert_called_once()

    def test_unapply(self):
        """Test migration unapply method."""
        # Mock operations
        for operation in self.migration.operations:
            operation.describe.return_value = "Test operation"

        with patch.object(self.migration, "_remove_migration_record") as mock_remove:
            self.migration.unapply()

            # Should reverse all operations in reverse order
            for operation in reversed(self.migration.operations):
                operation.reverse.assert_called_once()

            # Should remove migration record
            mock_remove.assert_called_once()

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        for operation in self.migration.operations:
            operation.describe.return_value = "Test operation"

        checksum1 = self.migration._calculate_checksum()
        checksum2 = self.migration._calculate_checksum()

        # Same migration should produce same checksum
        self.assertEqual(checksum1, checksum2)

        # Different migration should produce different checksum
        self.migration.name = "different_name"
        checksum3 = self.migration._calculate_checksum()
        self.assertNotEqual(checksum1, checksum3)

    @patch("django_dynamodb_backend.migrations_dynamo.DynamoDBMigrationState.exists")
    @patch("django_dynamodb_backend.migrations_dynamo.DynamoDBMigrationState.get")
    def test_is_applied_true(self, mock_get, mock_exists):
        """Test is_applied returns True when migration exists."""
        mock_exists.return_value = True
        mock_get.return_value = MagicMock()

        result = DynamoDBMigration.is_applied("test_migration", "test_app")

        self.assertTrue(result)
        mock_get.assert_called_once_with("test_app", "test_migration")

    @patch("django_dynamodb_backend.migrations_dynamo.DynamoDBMigrationState.exists")
    def test_is_applied_false_no_table(self, mock_exists):
        """Test is_applied returns False when migration state table doesn't exist."""
        mock_exists.return_value = False

        result = DynamoDBMigration.is_applied("test_migration", "test_app")

        self.assertFalse(result)


class TestMigrationNode(TestCase):
    """Test MigrationNode functionality."""

    def setUp(self):
        self.migration = MagicMock()
        self.migration.dependencies = [("other_app", "other_migration")]
        self.node = MigrationNode(self.migration, "test_app", "test_migration")

    def test_initialization(self):
        """Test node initialization."""
        self.assertEqual(self.node.migration, self.migration)
        self.assertEqual(self.node.app_label, "test_app")
        self.assertEqual(self.node.name, "test_migration")
        self.assertEqual(self.node.dependencies, [("other_app", "other_migration")])
        self.assertEqual(self.node.children, [])
        self.assertFalse(self.node.applied)

    def test_key_property(self):
        """Test key property."""
        self.assertEqual(self.node.key, ("test_app", "test_migration"))

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.node)
        self.assertIn("test_app.test_migration", repr_str)


class TestMigrationGraph(TestCase):
    """Test MigrationGraph functionality."""

    def setUp(self):
        self.graph = MigrationGraph()

        # Create test nodes
        self.migration1 = MagicMock()
        self.migration1.dependencies = []
        self.node1 = MigrationNode(self.migration1, "app1", "migration1")

        self.migration2 = MagicMock()
        self.migration2.dependencies = [("app1", "migration1")]
        self.node2 = MigrationNode(self.migration2, "app1", "migration2")

        self.migration3 = MagicMock()
        self.migration3.dependencies = [("app1", "migration2")]
        self.node3 = MigrationNode(self.migration3, "app1", "migration3")

    def test_add_node(self):
        """Test adding nodes to graph."""
        self.graph.add_node(self.node1)

        self.assertIn(("app1", "migration1"), self.graph.nodes)
        self.assertEqual(self.graph.nodes[("app1", "migration1")], self.node1)

    def test_validate_dependencies_valid(self):
        """Test dependency validation with valid dependencies."""
        self.graph.add_node(self.node1)
        self.graph.add_node(self.node2)

        # Should not raise exception
        self.graph.validate_dependencies()

    def test_validate_dependencies_invalid(self):
        """Test dependency validation with invalid dependencies."""
        self.graph.add_node(self.node2)  # Add node2 without node1

        with self.assertRaises(ImproperlyConfigured):
            self.graph.validate_dependencies()

    def test_get_migration_plan(self):
        """Test getting migration plan."""
        self.graph.add_node(self.node1)
        self.graph.add_node(self.node2)
        self.graph.add_node(self.node3)

        plan = self.graph.get_migration_plan([("app1", "migration3")])

        # Should return nodes in dependency order
        self.assertEqual(len(plan), 3)
        self.assertEqual(plan[0], self.node1)  # No dependencies
        self.assertEqual(plan[1], self.node2)  # Depends on node1
        self.assertEqual(plan[2], self.node3)  # Depends on node2


class TestMigrationLoader(TestCase):
    """Test MigrationLoader functionality."""

    def setUp(self):
        self.loader = MigrationLoader()

    @patch("django_dynamodb_backend.migration_executor.apps.get_app_configs")
    def test_load_disk(self, mock_get_app_configs):
        """Test loading migrations from disk."""
        mock_app_config = MagicMock()
        mock_app_config.label = "test_app"
        mock_get_app_configs.return_value = [mock_app_config]

        with patch.object(self.loader, "_load_migrations_for_app") as mock_load_app:
            with patch.object(
                self.loader, "_mark_applied_migrations"
            ) as mock_mark_applied:
                self.loader.load_disk()

                mock_load_app.assert_called_once_with("test_app")
                mock_mark_applied.assert_called_once()
                self.assertTrue(self.loader.loaded)

    def test_get_migration_plan_empty(self):
        """Test getting migration plan with no migrations."""
        with patch.object(self.loader, "load_disk"):
            plan = self.loader.get_migration_plan()
            self.assertEqual(plan, [])

    def test_get_applied_migrations(self):
        """Test getting applied migrations."""
        # Add mock nodes
        node1 = MagicMock()
        node1.key = ("app1", "migration1")
        node1.applied = True

        node2 = MagicMock()
        node2.key = ("app1", "migration2")
        node2.applied = False

        self.loader.graph.nodes = {
            ("app1", "migration1"): node1,
            ("app1", "migration2"): node2,
        }

        with patch.object(self.loader, "load_disk"):
            applied = self.loader.get_applied_migrations()
            self.assertEqual(applied, [("app1", "migration1")])

    def test_get_unapplied_migrations(self):
        """Test getting unapplied migrations."""
        # Add mock nodes
        node1 = MagicMock()
        node1.key = ("app1", "migration1")
        node1.applied = True

        node2 = MagicMock()
        node2.key = ("app1", "migration2")
        node2.applied = False

        self.loader.graph.nodes = {
            ("app1", "migration1"): node1,
            ("app1", "migration2"): node2,
        }

        with patch.object(self.loader, "load_disk"):
            unapplied = self.loader.get_unapplied_migrations()
            self.assertEqual(unapplied, [("app1", "migration2")])


class TestMigrationExecutor(TestCase):
    """Test MigrationExecutor functionality."""

    def setUp(self):
        self.executor = MigrationExecutor()

    def test_migrate_no_migrations(self):
        """Test migrate with no migrations to apply."""
        with patch.object(self.executor.loader, "get_migration_plan", return_value=[]):
            # Should not raise exception
            self.executor.migrate()

    def test_migrate_with_migrations(self):
        """Test migrate with migrations to apply."""
        mock_node = MagicMock()
        mock_node.app_label = "test_app"
        mock_node.name = "test_migration"
        mock_node.migration = MagicMock()

        with patch.object(
            self.executor.loader, "get_migration_plan", return_value=[mock_node]
        ):
            self.executor.migrate()

            mock_node.migration.apply.assert_called_once()
            self.assertTrue(mock_node.applied)

    def test_migrate_fake(self):
        """Test migrate with fake flag."""
        mock_node = MagicMock()
        mock_node.app_label = "test_app"
        mock_node.name = "test_migration"
        mock_node.migration = MagicMock()

        with patch.object(
            self.executor.loader, "get_migration_plan", return_value=[mock_node]
        ):
            self.executor.migrate(fake=True)

            # Should not call apply, but should call _record_migration
            mock_node.migration.apply.assert_not_called()
            mock_node.migration._record_migration.assert_called_once()

    def test_rollback(self):
        """Test rollback functionality."""
        mock_node = MagicMock()
        mock_node.app_label = "test_app"
        mock_node.name = "test_migration"
        mock_node.migration = MagicMock()

        with patch.object(
            self.executor.loader.graph, "get_unapply_plan", return_value=[mock_node]
        ):
            self.executor.rollback("test_app", "target_migration")

            mock_node.migration.unapply.assert_called_once()
            self.assertFalse(mock_node.applied)

    def test_show_migrations(self):
        """Test show migrations functionality."""
        # Mock nodes
        node1 = MagicMock()
        node1.app_label = "app1"
        node1.name = "migration1"
        node1.applied = True
        node1.dependencies = []

        node2 = MagicMock()
        node2.app_label = "app1"
        node2.name = "migration2"
        node2.applied = False
        node2.dependencies = [("app1", "migration1")]

        self.executor.loader.graph.nodes = {
            ("app1", "migration1"): node1,
            ("app1", "migration2"): node2,
        }

        with patch.object(self.executor.loader, "load_disk"):
            result = self.executor.show_migrations()

            self.assertIn("app1", result)
            self.assertEqual(len(result["app1"]), 2)

            # Check first migration
            mig1 = result["app1"][0]
            self.assertEqual(mig1["name"], "migration1")
            self.assertTrue(mig1["applied"])
            self.assertEqual(mig1["dependencies"], [])

            # Check second migration
            mig2 = result["app1"][1]
            self.assertEqual(mig2["name"], "migration2")
            self.assertFalse(mig2["applied"])
            self.assertEqual(mig2["dependencies"], [("app1", "migration1")])


if __name__ == "__main__":
    unittest.main()
