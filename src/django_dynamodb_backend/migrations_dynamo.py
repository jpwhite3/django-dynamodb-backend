"""
DynamoDB-specific migration system for Django.

This module provides a migration framework specifically designed for DynamoDB tables,
handling table creation, modification, and schema evolution patterns.
"""

import hashlib
import logging
from typing import Type

from django.conf import settings
from django.db import models
from django.utils import timezone
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
from pynamodb.exceptions import DoesNotExist, TableError
from pynamodb.models import Model as PynamoDBModel

logger = logging.getLogger(__name__)


class DynamoDBMigrationState(PynamoDBModel):
    """Track DynamoDB migration state in a dedicated table."""

    class Meta:
        table_name = "django_dynamodb_migrations"
        region = getattr(settings, "DYNAMODB_REGION", "us-east-1")
        if hasattr(settings, "DATABASES") and settings.DATABASES.get("default", {}).get(
            "LOCAL_ENDPOINT"
        ):
            host = settings.DATABASES["default"]["LOCAL_ENDPOINT"]

    app_name = UnicodeAttribute(hash_key=True)
    migration_name = UnicodeAttribute(range_key=True)
    applied_at = UTCDateTimeAttribute()
    checksum = UnicodeAttribute()


class DynamoDBOperation:
    """Base class for DynamoDB migration operations."""

    def __init__(self, model_class: Type[models.Model]):
        self.model_class = model_class
        self.model_name = model_class.__name__

    def execute(self, **kwargs):
        """Execute the migration operation."""
        raise NotImplementedError("Subclasses must implement execute()")

    def reverse(self, **kwargs):
        """Reverse the migration operation."""
        raise NotImplementedError("Subclasses must implement reverse()")

    def describe(self) -> str:
        """Return a description of the operation."""
        return f"{self.__class__.__name__} on {self.model_name}"


class CreateTable(DynamoDBOperation):
    """Create a DynamoDB table for a Django model."""

    def __init__(
        self,
        model_class: Type[models.Model],
        read_capacity: int = 5,
        write_capacity: int = 5,
    ):
        super().__init__(model_class)
        self.read_capacity = read_capacity
        self.write_capacity = write_capacity

    def execute(self, **kwargs):
        """Create the DynamoDB table."""
        try:
            # Get the PynamoDB model class
            pynamodb_model = self.model_class._get_pynamodb_model()

            # Check if table already exists
            if pynamodb_model.exists():
                logger.info(
                    f"Table {pynamodb_model.Meta.table_name} already exists, skipping creation"
                )
                return

            # Create the table
            logger.info(f"Creating DynamoDB table: {pynamodb_model.Meta.table_name}")
            pynamodb_model.create_table(
                read_capacity_units=self.read_capacity,
                write_capacity_units=self.write_capacity,
                wait=True,
            )

            logger.info(f"Successfully created table: {pynamodb_model.Meta.table_name}")

        except Exception as e:
            logger.error(f"Error creating table for {self.model_name}: {e}")
            raise

    def reverse(self, **kwargs):
        """Delete the DynamoDB table."""
        try:
            pynamodb_model = self.model_class._get_pynamodb_model()

            if not pynamodb_model.exists():
                logger.info(
                    f"Table {pynamodb_model.Meta.table_name} does not exist, skipping deletion"
                )
                return

            logger.info(f"Deleting DynamoDB table: {pynamodb_model.Meta.table_name}")
            pynamodb_model.delete_table()

            logger.info(f"Successfully deleted table: {pynamodb_model.Meta.table_name}")

        except Exception as e:
            logger.error(f"Error deleting table for {self.model_name}: {e}")
            raise

    def describe(self) -> str:
        return (
            f"Create table for {self.model_name} "
            f"(Read: {self.read_capacity}, Write: {self.write_capacity})"
        )


class UpdateTableCapacity(DynamoDBOperation):
    """Update read/write capacity for a DynamoDB table."""

    def __init__(
        self,
        model_class: Type[models.Model],
        read_capacity: int = None,
        write_capacity: int = None,
    ):
        super().__init__(model_class)
        self.read_capacity = read_capacity
        self.write_capacity = write_capacity
        self._old_capacity = {}

    def execute(self, **kwargs):
        """Update the table capacity."""
        try:
            pynamodb_model = self.model_class._get_pynamodb_model()

            if not pynamodb_model.exists():
                raise TableError(
                    f"Table {pynamodb_model.Meta.table_name} does not exist"
                )

            # Store current capacity for reversal
            table_description = pynamodb_model.describe_table()
            provisioned_throughput = table_description["Table"]["ProvisionedThroughput"]
            self._old_capacity = {
                "read_capacity": provisioned_throughput["ReadCapacityUnits"],
                "write_capacity": provisioned_throughput["WriteCapacityUnits"],
            }

            # Update capacity
            update_kwargs = {}
            if self.read_capacity is not None:
                update_kwargs["read_capacity_units"] = self.read_capacity
            if self.write_capacity is not None:
                update_kwargs["write_capacity_units"] = self.write_capacity

            if update_kwargs:
                logger.info(
                    f"Updating capacity for table: {pynamodb_model.Meta.table_name}"
                )
                pynamodb_model.update_table(**update_kwargs)
                logger.info(f"Successfully updated table capacity")

        except Exception as e:
            logger.error(f"Error updating table capacity for {self.model_name}: {e}")
            raise

    def reverse(self, **kwargs):
        """Restore the previous table capacity."""
        try:
            if not self._old_capacity:
                logger.warning(
                    "No previous capacity information available for reversal"
                )
                return

            pynamodb_model = self.model_class._get_pynamodb_model()

            logger.info(
                f"Restoring capacity for table: {pynamodb_model.Meta.table_name}"
            )
            pynamodb_model.update_table(
                read_capacity_units=self._old_capacity["read_capacity"],
                write_capacity_units=self._old_capacity["write_capacity"],
            )

            logger.info(f"Successfully restored table capacity")

        except Exception as e:
            logger.error(f"Error restoring table capacity for {self.model_name}: {e}")
            raise

    def describe(self) -> str:
        capacity_info = []
        if self.read_capacity is not None:
            capacity_info.append(f"Read: {self.read_capacity}")
        if self.write_capacity is not None:
            capacity_info.append(f"Write: {self.write_capacity}")
        return f"Update capacity for {self.model_name} ({', '.join(capacity_info)})"


class RunPython(DynamoDBOperation):
    """Execute custom Python code during migration."""

    def __init__(self, code_func, reverse_code_func=None):
        self.code_func = code_func
        self.reverse_code_func = reverse_code_func
        super().__init__(models.Model)  # Dummy model class

    def execute(self, **kwargs):
        """Execute the custom code."""
        try:
            logger.info("Executing custom Python code in migration")
            if callable(self.code_func):
                self.code_func()
            else:
                exec(self.code_func)
            logger.info("Successfully executed custom Python code")
        except Exception as e:
            logger.error(f"Error executing custom Python code: {e}")
            raise

    def reverse(self, **kwargs):
        """Execute the reverse custom code."""
        try:
            if self.reverse_code_func:
                logger.info("Executing reverse Python code in migration")
                if callable(self.reverse_code_func):
                    self.reverse_code_func()
                else:
                    exec(self.reverse_code_func)
                logger.info("Successfully executed reverse Python code")
        except Exception as e:
            logger.error(f"Error executing reverse Python code: {e}")
            raise

    def describe(self) -> str:
        return "Execute custom Python code"


class DataMigration(DynamoDBOperation):
    """Migrate data between different schemas or formats."""

    def __init__(
        self, model_class: Type[models.Model], migration_func, reverse_func=None
    ):
        super().__init__(model_class)
        self.migration_func = migration_func
        self.reverse_func = reverse_func

    def execute(self, **kwargs):
        """Execute the data migration."""
        try:
            logger.info(f"Starting data migration for {self.model_name}")

            # Get all items in the table
            pynamodb_model = self.model_class._get_pynamodb_model()

            for item in pynamodb_model.scan():
                # Apply migration function to each item
                if self.migration_func:
                    self.migration_func(item)

            logger.info(f"Successfully completed data migration for {self.model_name}")

        except Exception as e:
            logger.error(f"Error in data migration for {self.model_name}: {e}")
            raise

    def reverse(self, **kwargs):
        """Reverse the data migration."""
        try:
            if not self.reverse_func:
                logger.warning(
                    f"No reverse function provided for data migration on {self.model_name}"
                )
                return

            logger.info(f"Starting reverse data migration for {self.model_name}")

            pynamodb_model = self.model_class._get_pynamodb_model()

            for item in pynamodb_model.scan():
                self.reverse_func(item)

            logger.info(
                f"Successfully completed reverse data migration for {self.model_name}"
            )

        except Exception as e:
            logger.error(f"Error in reverse data migration for {self.model_name}: {e}")
            raise

    def describe(self) -> str:
        return f"Data migration for {self.model_name}"


class DynamoDBMigration:
    """
    Base class for DynamoDB migrations.

    Similar to Django's Migration class but designed for DynamoDB operations.
    """

    # Migration metadata
    dependencies = []
    operations = []

    def __init__(self, name: str, app_label: str):
        self.name = name
        self.app_label = app_label

    def apply(self, **kwargs):
        """Apply the migration by executing all operations."""
        logger.info(f"Applying migration {self.app_label}.{self.name}")

        for operation in self.operations:
            logger.info(f"  Executing: {operation.describe()}")
            operation.execute(**kwargs)

        # Record the migration as applied
        self._record_migration()

        logger.info(f"Successfully applied migration {self.app_label}.{self.name}")

    def unapply(self, **kwargs):
        """Unapply the migration by reversing all operations."""
        logger.info(f"Unapplying migration {self.app_label}.{self.name}")

        # Reverse operations in reverse order
        for operation in reversed(self.operations):
            logger.info(f"  Reversing: {operation.describe()}")
            operation.reverse(**kwargs)

        # Remove the migration record
        self._remove_migration_record()

        logger.info(f"Successfully unapplied migration {self.app_label}.{self.name}")

    def _record_migration(self):
        """Record this migration as applied."""
        try:
            # Ensure the migration state table exists
            if not DynamoDBMigrationState.exists():
                DynamoDBMigrationState.create_table(wait=True)

            # Calculate checksum of migration content
            checksum = self._calculate_checksum()

            # Save migration record
            migration_record = DynamoDBMigrationState(
                app_name=self.app_label,
                migration_name=self.name,
                applied_at=timezone.now(),
                checksum=checksum,
            )
            migration_record.save()

        except Exception as e:
            logger.error(f"Error recording migration {self.app_label}.{self.name}: {e}")
            raise

    def _remove_migration_record(self):
        """Remove the migration record."""
        try:
            migration_record = DynamoDBMigrationState.get(self.app_label, self.name)
            migration_record.delete()
        except DoesNotExist:
            logger.warning(f"Migration record {self.app_label}.{self.name} not found")
        except Exception as e:
            logger.error(
                f"Error removing migration record {self.app_label}.{self.name}: {e}"
            )
            raise

    def _calculate_checksum(self) -> str:
        """Calculate a checksum for the migration content."""
        content = f"{self.app_label}.{self.name}:{len(self.operations)}"
        for operation in self.operations:
            content += f":{operation.describe()}"
        return hashlib.md5(content.encode()).hexdigest()

    @classmethod
    def is_applied(cls, name: str, app_label: str) -> bool:
        """Check if a migration has been applied."""
        try:
            if not DynamoDBMigrationState.exists():
                return False

            DynamoDBMigrationState.get(app_label, name)
            return True
        except DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error checking migration status {app_label}.{name}: {e}")
            return False
