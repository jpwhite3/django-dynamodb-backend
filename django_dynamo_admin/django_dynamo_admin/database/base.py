import logging
import threading
import time
from queue import Empty, Queue

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import (DatabaseError, IntegrityError, OperationalError,
                       ProgrammingError, utils)
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.base.client import BaseDatabaseClient
from django.db.backends.base.creation import BaseDatabaseCreation
from django.db.backends.base.features import BaseDatabaseFeatures
from django.db.backends.base.introspection import BaseDatabaseIntrospection
from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.base.validation import BaseDatabaseValidation

logger = logging.getLogger(__name__)


class DynamoDBConnectionPool:
    """
    Connection pool for DynamoDB resources to improve performance.
    """

    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()

    def get_connection(self, db_settings):
        """Get a connection from pool or create new one."""
        try:
            # Try to get existing connection from pool
            connection = self.pool.get_nowait()
            logger.debug("Retrieved connection from pool")
            return connection
        except Empty:
            # No available connection, create new one if under limit
            with self.lock:
                if self.active_connections < self.max_connections:
                    connection = self._create_connection(db_settings)
                    self.active_connections += 1
                    logger.debug(
                        f"Created new connection, active: {self.active_connections}"
                    )
                    return connection
                else:
                    # Wait for available connection
                    logger.debug("Pool full, waiting for available connection")
                    return self.pool.get(timeout=30)

    def return_connection(self, connection):
        """Return connection to pool."""
        try:
            self.pool.put_nowait(connection)
            logger.debug("Returned connection to pool")
        except:
            # Pool full, close the connection
            with self.lock:
                self.active_connections -= 1
            logger.debug(
                f"Pool full, closed connection, active: {self.active_connections}"
            )

    def _create_connection(self, db_settings):
        """Create new DynamoDB connection."""
        try:
            session = boto3.Session(
                aws_access_key_id=db_settings.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=db_settings.get("AWS_SECRET_ACCESS_KEY"),
                region_name=db_settings.get("AWS_REGION", "us-east-1"),
            )

            resource = session.resource("dynamodb")
            client = session.client("dynamodb")

            return DynamoDBConnection(resource, client)
        except Exception as e:
            logger.error(f"Failed to create DynamoDB connection: {e}")
            raise DatabaseError(f"Cannot connect to DynamoDB: {e}")


class DynamoDBConnection:
    """
    Wrapper for DynamoDB connection to provide Django-compatible interface.
    """

    def __init__(self, resource, client):
        self.resource = resource
        self.client = client
        self.last_used = time.time()

    def commit(self):
        """Commit transaction (no-op for DynamoDB)."""
        pass

    def rollback(self):
        """Rollback transaction (no-op for DynamoDB)."""
        pass

    def close(self):
        """Close connection (no-op for DynamoDB)."""
        pass

    def is_stale(self, max_age=3600):
        """Check if connection is stale."""
        return time.time() - self.last_used > max_age

    def refresh(self):
        """Update last used timestamp."""
        self.last_used = time.time()


class DynamoDBQueryCache:
    """
    Advanced caching system for DynamoDB queries.
    """

    def __init__(self):
        self.default_timeout = getattr(
            settings, "DYNAMODB_CACHE_TIMEOUT", 300
        )  # 5 minutes

    def get_cache_key(self, operation, table_name, params):
        """Generate cache key for query."""
        import hashlib

        key_data = (
            f"{operation}:{table_name}:{str(sorted(params.items()) if params else '')}"
        )
        return f"dynamodb:{hashlib.md5(key_data.encode()).hexdigest()}"

    def get_cached_result(self, operation, table_name, params):
        """Get cached query result."""
        if not getattr(settings, "DYNAMODB_ENABLE_CACHE", True):
            return None

        cache_key = self.get_cache_key(operation, table_name, params)
        cached_result = cache.get(cache_key)

        if cached_result:
            logger.debug(f"Cache hit for key: {cache_key}")
            return cached_result

        logger.debug(f"Cache miss for key: {cache_key}")
        return None

    def cache_result(self, operation, table_name, params, result, timeout=None):
        """Cache query result."""
        if not getattr(settings, "DYNAMODB_ENABLE_CACHE", True):
            return

        cache_key = self.get_cache_key(operation, table_name, params)
        timeout = timeout or self.default_timeout

        # Don't cache empty results or errors
        if result and not isinstance(result, Exception):
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached result for key: {cache_key}")

    def invalidate_table_cache(self, table_name):
        """Invalidate all cached results for a table."""
        # This is a simplified approach - in production you might want
        # to use cache tags or a more sophisticated invalidation strategy
        logger.info(f"Cache invalidation requested for table: {table_name}")
        # Note: Django's default cache doesn't support pattern-based deletion
        # You might want to use Redis or implement a custom cache backend


# Helper classes for introspection
class TableInfo:
    """Table information for DynamoDB introspection."""

    def __init__(self, name, type="t"):
        self.name = name
        self.type = type


# DynamoDB error classes
class Database:
    """Fake database module for DynamoDB."""

    class Error(Exception):
        pass

    class InterfaceError(Error):
        pass

    class DatabaseError(Error):
        pass

    class DataError(DatabaseError):
        pass

    class OperationalError(DatabaseError):
        pass

    class IntegrityError(DatabaseError):
        pass

    class InternalError(DatabaseError):
        pass

    class ProgrammingError(DatabaseError):
        pass

    class NotSupportedError(DatabaseError):
        pass


class DatabaseWrapper(BaseDatabaseWrapper):
    """
    Django database backend for DynamoDB using boto3.
    """

    vendor = "dynamodb"
    display_name = "DynamoDB"
    Database = Database

    # Required class attributes
    client_class = None
    creation_class = None
    features_class = None
    introspection_class = None
    ops_class = None
    validation_class = None
    schema_editor_class = None

    # DynamoDB doesn't use traditional SQL data types
    data_types = {
        "AutoField": "S",
        "BigAutoField": "S",
        "BinaryField": "B",
        "BooleanField": "BOOL",
        "CharField": "S",
        "DateField": "S",
        "DateTimeField": "S",
        "DecimalField": "N",
        "DurationField": "N",
        "EmailField": "S",
        "FileField": "S",
        "FilePathField": "S",
        "FloatField": "N",
        "IntegerField": "N",
        "BigIntegerField": "N",
        "IPAddressField": "S",
        "GenericIPAddressField": "S",
        "JSONField": "M",
        "PositiveIntegerField": "N",
        "PositiveSmallIntegerField": "N",
        "SlugField": "S",
        "SmallIntegerField": "N",
        "TextField": "S",
        "TimeField": "S",
        "URLField": "S",
        "UUIDField": "S",
    }

    operators = {
        "exact": "=",
        "iexact": "=",
        "contains": "contains",
        "icontains": "contains",
        "in": "IN",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "startswith": "begins_with",
        "istartswith": "begins_with",
        "endswith": "ends_with",
        "iendswith": "ends_with",
    }

    def __init__(self, settings_dict, alias=None):
        # Set class attributes before calling super()
        self.client_class = DynamoDBClient
        self.creation_class = DynamoDBCreation
        self.features_class = DynamoDBFeatures
        self.introspection_class = DynamoDBIntrospection
        self.ops_class = DynamoDBOperations
        self.validation_class = DynamoDBValidation

        super().__init__(settings_dict, alias)

        # Set the SchemaEditorClass after initialization
        self.SchemaEditorClass = DynamoDBSchemaEditor

        # Initialize connection pool and query cache
        max_connections = getattr(settings, "DYNAMODB_MAX_CONNECTIONS", 10)
        self._connection_pool = DynamoDBConnectionPool(max_connections)
        self._query_cache = DynamoDBQueryCache()

        # DynamoDB connection will be established lazily
        self._dynamodb_resource = None
        self._dynamodb_client = None

    def get_connection_params(self):
        """Extract connection parameters from settings."""
        settings_dict = self.settings_dict
        params = {}

        # AWS credentials
        if "ACCESS_KEY" in settings_dict:
            params["aws_access_key_id"] = settings_dict["ACCESS_KEY"]
        if "SECRET_KEY" in settings_dict:
            params["aws_secret_access_key"] = settings_dict["SECRET_KEY"]
        if "SESSION_TOKEN" in settings_dict:
            params["aws_session_token"] = settings_dict["SESSION_TOKEN"]

        # AWS region
        params["region_name"] = settings_dict.get("REGION", "us-east-1")

        # Local endpoint for development (DynamoDB Local)
        if "LOCAL_ENDPOINT" in settings_dict:
            params["endpoint_url"] = settings_dict["LOCAL_ENDPOINT"]

        return params

    def get_new_connection(self, conn_params):
        """Get a connection from the pool."""
        try:
            return self._connection_pool.get_connection(self.settings_dict)
        except Exception as e:
            raise utils.DatabaseError(f"Error getting connection: {e}")

    def init_connection_state(self):
        """Initialize connection state."""
        pass

    def create_cursor(self, name=None):
        """Create a cursor for database operations."""
        return DynamoDBCursor(self)

    def is_usable(self):
        """Check if the connection is usable."""
        try:
            if self.connection:
                self.connection.client.describe_limits()
                return True
        except Exception:
            pass
        return False

    @property
    def dynamodb_resource(self):
        """Get the DynamoDB resource."""
        self.ensure_connection()
        return self.connection.resource

    @property
    def dynamodb_client(self):
        """Get the DynamoDB client."""
        self.ensure_connection()
        return self.connection.client

    def _set_autocommit(self, autocommit):
        """Set autocommit mode (no-op for DynamoDB)."""
        pass

    def _close(self):
        """Return connection to pool."""
        if self.connection:
            self._connection_pool.return_connection(self.connection)
            self.connection = None

    def get_cached_query_result(self, operation, table_name, params):
        """Get cached query result if available."""
        return self._query_cache.get_cached_result(operation, table_name, params)

    def cache_query_result(self, operation, table_name, params, result, timeout=None):
        """Cache query result."""
        return self._query_cache.cache_result(
            operation, table_name, params, result, timeout
        )

    def invalidate_table_cache(self, table_name):
        """Invalidate cached results for a table."""
        return self._query_cache.invalidate_table_cache(table_name)


class DynamoDBCursor:
    """
    Cursor for DynamoDB operations.
    """

    def __init__(self, db):
        self.db = db
        self.queries = []

    def execute(self, sql, params=None):
        """Execute a query (converted to DynamoDB operations)."""
        # This is where SQL would be translated to DynamoDB operations
        # For now, this is a placeholder
        self.queries.append((sql, params))
        return []

    def fetchone(self):
        """Fetch one result."""
        return None

    def fetchmany(self, size=None):
        """Fetch multiple results."""
        return []

    def fetchall(self):
        """Fetch all results."""
        return []

    def close(self):
        """Close the cursor."""
        pass


class DynamoDBOperations(BaseDatabaseOperations):
    """
    Database operations for DynamoDB.
    """

    compiler_module = "django_dynamo_admin.database.compiler"

    def quote_name(self, name):
        """Quote table/column names."""
        return name

    def sql_table_creation_suffix(self):
        """Return SQL suffix for table creation."""
        return ""

    def convert_values(self, value, field):
        """Convert Python values to DynamoDB format."""
        if value is None:
            return None
        return value

    def last_insert_id(self, cursor, table_name, pk_name):
        """Return the last insert ID."""
        return None

    def max_name_length(self):
        """Maximum length for table/column names."""
        return 255

    def sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
        """
        Return a list of SQL statements required to remove all data from
        the given database tables (without actually removing the tables
        themselves) and reset primary key sequences.

        For DynamoDB, this would translate to truncating tables.
        """
        if not tables:
            return []

        # In DynamoDB, we would need to scan and delete all items
        # For now, return placeholder operations
        flush_statements = []
        for table in tables:
            flush_statements.append(
                {"operation_type": "truncate_table", "table_name": table}
            )

        return flush_statements


class DynamoDBFeatures(BaseDatabaseFeatures):
    """
    Features supported by DynamoDB backend.
    """

    # DynamoDB doesn't support traditional SQL features
    supports_transactions = False
    supports_foreign_keys = False
    supports_check_constraints = False
    supports_column_check_constraints = False
    supports_partial_indexes = False
    supports_functional_indexes = False
    supports_over_clause = False
    supports_frame_range_offsets = False
    supports_aggregate_filter_clause = False
    supports_json_field = True
    supports_json_field_contains = True
    supports_primitives_in_json_field = True
    supports_temporal_subtraction = False
    supports_regex_backreferencing = False
    supports_date_lookup_using_string = True
    supports_timezones = True
    can_clone_databases = False
    can_defer_constraint_checks = False
    has_real_datatype = False
    supports_subqueries_in_group_by = False
    supports_bitwise_or = False
    has_native_uuid_field = False
    has_native_duration_field = False
    can_distinct_on_fields = False
    supports_ignore_conflicts = False
    supports_update_conflicts = False
    can_return_columns_from_insert = False
    can_return_rows_from_bulk_insert = False
    has_bulk_insert = True
    supports_explaining_query_execution = False
    supports_temporal_subtraction = False
    supports_select_intersection = False
    supports_select_difference = False
    can_rollback_ddl = False

    @property
    def has_select_for_update(self):
        return False

    @property
    def has_select_for_update_nowait(self):
        return False


class DynamoDBValidation(BaseDatabaseValidation):
    """
    Database validation for DynamoDB.
    """

    def check(self, **kwargs):
        """Perform database checks."""
        issues = []
        return issues


class DynamoDBClient(BaseDatabaseClient):
    """
    Database client for DynamoDB.
    """

    executable_name = "aws"


class DynamoDBCreation(BaseDatabaseCreation):
    """
    Database creation for DynamoDB.
    """

    def create_test_db(
        self, verbosity=1, autoclobber=False, serialize=True, keepdb=False
    ):
        """Create test database."""
        # For DynamoDB, we just use a test prefix for table names
        test_database_name = self._get_test_db_name()
        return test_database_name

    def destroy_test_db(
        self, old_database_name, verbosity=1, keepdb=False, serialize=True
    ):
        """Destroy test database."""
        # Clean up test tables
        pass


class DynamoDBIntrospection(BaseDatabaseIntrospection):
    """
    Database introspection for DynamoDB.
    """

    data_types_reverse = {
        "S": "CharField",
        "N": "IntegerField",
        "B": "BinaryField",
        "SS": "TextField",
        "NS": "TextField",
        "BS": "TextField",
        "M": "JSONField",
        "L": "JSONField",
        "NULL": "CharField",
        "BOOL": "BooleanField",
    }

    def get_table_list(self, cursor):
        """Return list of table names."""
        try:
            client = cursor.db.dynamodb_client
            response = client.list_tables()
            return [TableInfo(table) for table in response["TableNames"]]
        except Exception as e:
            logger.error(f"Error listing DynamoDB tables: {e}")
            return []

    def get_table_description(self, cursor, table_name):
        """Return description of table columns."""
        try:
            client = cursor.db.dynamodb_client
            response = client.describe_table(TableName=table_name)
            table_description = response["Table"]

            columns = []
            for attr in table_description.get("AttributeDefinitions", []):
                column_info = (
                    attr["AttributeName"],  # column name
                    attr["AttributeType"],  # data type
                    None,  # display size
                    None,  # internal size
                    None,  # precision
                    None,  # scale
                    True,  # nullable
                    None,  # default
                    False,  # auto increment
                    False,  # primary key (handled separately)
                    False,  # unique
                )
                columns.append(column_info)
            return columns
        except Exception as e:
            logger.error(f"Error describing DynamoDB table {table_name}: {e}")
            return []


class DynamoDBSchemaEditor(BaseDatabaseSchemaEditor):
    """
    Schema editor for DynamoDB.
    """

    def __init__(self, connection, collect_sql=False, atomic=True):
        super().__init__(connection, collect_sql, atomic)

    def create_model(self, model):
        """Create a DynamoDB table for the model."""
        table_name = model._meta.db_table

        # Get the primary key field
        pk_field = model._meta.pk
        if not pk_field:
            raise ImproperlyConfigured(
                f"Model {model.__name__} has no primary key field"
            )

        # Build table schema
        key_schema = [{"AttributeName": pk_field.column, "KeyType": "HASH"}]

        attribute_definitions = [
            {
                "AttributeName": pk_field.column,
                "AttributeType": "S",  # Default to string for now
            }
        ]

        # Create table
        try:
            self.connection.dynamodb_client.create_table(
                TableName=table_name,
                KeySchema=key_schema,
                AttributeDefinitions=attribute_definitions,
                BillingMode="PAY_PER_REQUEST",  # On-demand billing
            )
            logger.info(f"Created DynamoDB table: {table_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceInUseException":
                raise utils.DatabaseError(f"Error creating table {table_name}: {e}")

    def delete_model(self, model):
        """Delete a DynamoDB table."""
        table_name = model._meta.db_table
        try:
            self.connection.dynamodb_client.delete_table(TableName=table_name)
            logger.info(f"Deleted DynamoDB table: {table_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise utils.DatabaseError(f"Error deleting table {table_name}: {e}")

    def add_field(self, model, field):
        """Add a field to the model (DynamoDB is schemaless for non-key attributes)."""
        pass

    def remove_field(self, model, field):
        """Remove a field from the model (DynamoDB is schemaless for non-key attributes)."""
        pass

    def alter_field(self, model, old_field, new_field, strict=False):
        """Alter a field (limited support in DynamoDB)."""
        pass
