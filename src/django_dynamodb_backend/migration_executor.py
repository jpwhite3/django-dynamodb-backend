"""
DynamoDB migration discovery and execution system.

This module handles finding, loading, and executing DynamoDB migrations.
"""

import importlib
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from .migrations_dynamo import DynamoDBMigration

logger = logging.getLogger(__name__)


class MigrationNode:
    """Represents a single migration with its dependencies."""

    def __init__(self, migration: DynamoDBMigration, app_label: str, name: str):
        self.migration = migration
        self.app_label = app_label
        self.name = name
        self.dependencies = getattr(migration, "dependencies", [])
        self.children = []
        self.applied = False

    @property
    def key(self) -> Tuple[str, str]:
        """Return the migration key (app_label, name)."""
        return (self.app_label, self.name)

    def __repr__(self):
        return f"<MigrationNode: {self.app_label}.{self.name}>"


class MigrationGraph:
    """Graph of migration dependencies."""

    def __init__(self):
        self.nodes = {}  # {(app_label, name): MigrationNode}
        self.dependencies = defaultdict(set)  # {(app_label, name): set of dependencies}

    def add_node(self, node: MigrationNode):
        """Add a migration node to the graph."""
        self.nodes[node.key] = node

        # Add dependencies
        for dep_app, dep_name in node.dependencies:
            self.dependencies[node.key].add((dep_app, dep_name))

    def validate_dependencies(self):
        """Validate that all dependencies exist."""
        for node_key, deps in self.dependencies.items():
            for dep_key in deps:
                if dep_key not in self.nodes:
                    app_label, name = node_key
                    dep_app, dep_name = dep_key
                    raise ImproperlyConfigured(
                        f"Migration {app_label}.{name} depends on {dep_app}.{dep_name}, "
                        f"which does not exist."
                    )

    def get_migration_plan(
        self, targets: List[Tuple[str, str]] = None
    ) -> List[MigrationNode]:
        """
        Get an ordered list of migrations to apply.

        Args:
            targets: List of (app_label, name) tuples to migrate to.
                    If None, migrates to the latest migrations for all apps.

        Returns:
            List of MigrationNode objects in dependency order.
        """
        if targets is None:
            # Get all leaf nodes (migrations with no children)
            targets = []
            for node in self.nodes.values():
                if not any(
                    node.key in self.dependencies[other_key]
                    for other_key in self.nodes.keys()
                ):
                    targets.append(node.key)

        # Topological sort to get correct order
        plan = []
        visited = set()
        temp_visited = set()

        def visit(node_key):
            if node_key in temp_visited:
                raise ImproperlyConfigured(
                    f"Circular dependency detected involving {node_key}"
                )

            if node_key in visited:
                return

            temp_visited.add(node_key)

            # Visit all dependencies first
            for dep_key in self.dependencies.get(node_key, []):
                visit(dep_key)

            temp_visited.remove(node_key)
            visited.add(node_key)

            if node_key in self.nodes:
                plan.append(self.nodes[node_key])

        # Visit all target migrations and their dependencies
        for target_key in targets:
            if target_key in self.nodes:
                visit(target_key)

        return plan

    def get_unapply_plan(self, targets: List[Tuple[str, str]]) -> List[MigrationNode]:
        """
        Get an ordered list of migrations to unapply (rollback).

        Args:
            targets: List of (app_label, name) tuples to rollback to.

        Returns:
            List of MigrationNode objects in reverse dependency order.
        """
        # Get all currently applied migrations that need to be unapplied
        to_unapply = []

        for node in self.nodes.values():
            if node.applied:
                # Check if this migration should be unapplied
                should_unapply = False

                for target_key in targets:
                    if node.key == target_key:
                        should_unapply = False
                        break
                    # If this migration depends on the target, it should be unapplied
                    if self._depends_on(node.key, target_key):
                        should_unapply = True
                        break

                if should_unapply:
                    to_unapply.append(node)

        # Return in reverse dependency order
        return list(
            reversed(self.get_migration_plan([node.key for node in to_unapply]))
        )

    def _depends_on(
        self, node_key: Tuple[str, str], target_key: Tuple[str, str]
    ) -> bool:
        """Check if node_key depends on target_key (directly or indirectly)."""
        visited = set()

        def has_dependency(current_key):
            if current_key in visited:
                return False
            visited.add(current_key)

            if current_key == target_key:
                return True

            for dep_key in self.dependencies.get(current_key, []):
                if has_dependency(dep_key):
                    return True

            return False

        return has_dependency(node_key)


class MigrationLoader:
    """Load and discover DynamoDB migrations."""

    def __init__(self):
        self.graph = MigrationGraph()
        self.loaded = False
        self._migration_modules = {}

    def load_disk(self):
        """Load migrations from disk."""
        if self.loaded:
            return

        # Clear existing data
        self.graph = MigrationGraph()

        # Load migrations for each app
        for app_config in apps.get_app_configs():
            self._load_migrations_for_app(app_config.label)

        # Validate the migration graph
        self.graph.validate_dependencies()

        # Mark applied migrations
        self._mark_applied_migrations()

        self.loaded = True
        logger.info("Loaded DynamoDB migrations from disk")

    def _load_migrations_for_app(self, app_label: str):
        """Load migrations for a specific app."""
        try:
            # Look for dynamodb_migrations directory in app
            app_config = apps.get_app_config(app_label)
            migrations_dir = Path(app_config.path) / "dynamodb_migrations"

            if not migrations_dir.exists():
                logger.debug(f"No DynamoDB migrations directory found for {app_label}")
                return

            logger.info(f"Found DynamoDB migrations directory: {migrations_dir}")

            # Import individual migration files
            for migration_file in migrations_dir.glob("*.py"):
                if migration_file.name.startswith("__"):
                    continue

                migration_name = migration_file.stem
                full_module_name = (
                    f"{app_config.name}.dynamodb_migrations.{migration_name}"
                )

                logger.info(f"Trying to import migration: {full_module_name}")

                try:
                    migration_module = importlib.import_module(full_module_name)
                    self._process_migration_module(
                        migration_module, app_label, migration_name
                    )
                except ImportError as e:
                    logger.warning(
                        f"Could not import migration {full_module_name}: {e}"
                    )
                    continue
                except Exception as e:
                    logger.error(f"Error processing migration {full_module_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error loading migrations for {app_label}: {e}")

    def _process_migration_module(
        self, module, app_label: str, migration_name: str = None
    ):
        """Process a migration module and extract Migration classes."""
        logger.info(
            f"Processing migration module for {app_label}, migration_name={migration_name}"
        )
        logger.info(
            f"Module attributes: {[attr for attr in dir(module) if not attr.startswith('_')]}"
        )

        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            if (
                isinstance(attr, type)
                and issubclass(attr, DynamoDBMigration)
                and attr != DynamoDBMigration
            ):

                logger.info(f"Found migration class: {attr_name}")

                # Use provided name or derive from class name
                name = migration_name or attr_name.lower()

                # Create migration instance
                migration_instance = attr(name=name, app_label=app_label)

                # Create node and add to graph
                node = MigrationNode(migration_instance, app_label, name)
                self.graph.add_node(node)

                logger.info(f"Loaded migration: {app_label}.{name}")
                break
        else:
            logger.warning(
                f"No migration class found in module for {app_label}.{migration_name}"
            )

    def _mark_applied_migrations(self):
        """Mark which migrations have already been applied."""
        for node in self.graph.nodes.values():
            node.applied = DynamoDBMigration.is_applied(node.name, node.app_label)

    def get_migration_plan(
        self, app_label: str = None, migration_name: str = None
    ) -> List[MigrationNode]:
        """Get the migration plan for applying migrations."""
        self.load_disk()

        targets = []
        if app_label and migration_name:
            targets = [(app_label, migration_name)]
        elif app_label:
            # Get latest migration for the app
            app_migrations = [
                node
                for node in self.graph.nodes.values()
                if node.app_label == app_label
            ]
            if app_migrations:
                # Find leaf nodes for this app
                for node in app_migrations:
                    is_leaf = True
                    for other_node in app_migrations:
                        if node.key in self.graph.dependencies.get(
                            other_node.key, set()
                        ):
                            is_leaf = False
                            break
                    if is_leaf:
                        targets.append(node.key)

        plan = self.graph.get_migration_plan(targets if targets else None)

        # Filter out already applied migrations
        return [node for node in plan if not node.applied]

    def get_applied_migrations(self) -> List[Tuple[str, str]]:
        """Get list of applied migrations."""
        self.load_disk()
        return [node.key for node in self.graph.nodes.values() if node.applied]

    def get_unapplied_migrations(self) -> List[Tuple[str, str]]:
        """Get list of unapplied migrations."""
        self.load_disk()
        return [node.key for node in self.graph.nodes.values() if not node.applied]


class MigrationExecutor:
    """Execute DynamoDB migrations."""

    def __init__(self):
        self.loader = MigrationLoader()

    def migrate(
        self, app_label: str = None, migration_name: str = None, fake: bool = False
    ):
        """
        Apply migrations.

        Args:
            app_label: Specific app to migrate (optional)
            migration_name: Specific migration to migrate to (optional)
            fake: Mark migrations as applied without actually running them
        """
        logger.info(f"Starting DynamoDB migration process")

        # Get migration plan
        plan = self.loader.get_migration_plan(app_label, migration_name)

        if not plan:
            logger.info("No migrations to apply")
            return

        logger.info(f"Applying {len(plan)} migrations:")
        for node in plan:
            logger.info(f"  {node.app_label}.{node.name}")

        # Apply migrations
        for node in plan:
            logger.info(f"Applying migration: {node.app_label}.{node.name}")

            if fake:
                logger.info("  Faking migration (marking as applied without execution)")
                node.migration._record_migration()
            else:
                try:
                    node.migration.apply()
                    node.applied = True
                except Exception as e:
                    logger.error(
                        f"Error applying migration {node.app_label}.{node.name}: {e}"
                    )
                    raise

        logger.info("DynamoDB migration process completed successfully")

    def rollback(self, app_label: str, migration_name: str):
        """
        Rollback to a specific migration.

        Args:
            app_label: App label
            migration_name: Migration name to rollback to
        """
        logger.info(f"Starting DynamoDB rollback to {app_label}.{migration_name}")

        # Get rollback plan
        targets = [(app_label, migration_name)]
        plan = self.loader.graph.get_unapply_plan(targets)

        if not plan:
            logger.info("No migrations to rollback")
            return

        logger.info(f"Rolling back {len(plan)} migrations:")
        for node in plan:
            logger.info(f"  {node.app_label}.{node.name}")

        # Unapply migrations
        for node in plan:
            logger.info(f"Unapplying migration: {node.app_label}.{node.name}")

            try:
                node.migration.unapply()
                node.applied = False
            except Exception as e:
                logger.error(
                    f"Error unapplying migration {node.app_label}.{node.name}: {e}"
                )
                raise

        logger.info("DynamoDB rollback completed successfully")

    def show_migrations(self) -> Dict[str, List[Dict[str, Any]]]:
        """Show migration status for all apps."""
        self.loader.load_disk()

        result = defaultdict(list)

        for node in self.loader.graph.nodes.values():
            result[node.app_label].append(
                {
                    "name": node.name,
                    "applied": node.applied,
                    "dependencies": node.dependencies,
                }
            )

        # Sort migrations by name within each app
        for app_label in result:
            result[app_label].sort(key=lambda x: x["name"])

        return dict(result)
