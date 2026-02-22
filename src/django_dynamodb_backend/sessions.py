"""
DynamoDB Session Backend for Django.

This module provides a session backend that stores sessions in DynamoDB,
eliminating the need for a relational database for session storage.

Usage:
    In settings.py:
        SESSION_ENGINE = "django_dynamodb_backend.sessions"

Table Schema:
    - session_key (String, Hash Key): The session identifier
    - session_data (String): Base64-encoded, compressed session data
    - expire_date (Number): Unix timestamp for expiration (TTL attribute)
"""

import base64
import logging
import time
import zlib
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.contrib.sessions.backends.base import CreateError, SessionBase

logger = logging.getLogger(__name__)

# Table configuration
DYNAMODB_SESSION_TABLE_NAME = getattr(
    settings, "DYNAMODB_SESSION_TABLE_NAME", "django_sessions"
)
DYNAMODB_SESSION_TTL_ATTRIBUTE = "expire_date"


def get_dynamodb_client():
    """Get a boto3 DynamoDB client configured from Django settings."""
    import boto3

    db_settings = getattr(settings, "DATABASES", {}).get("default", {})
    options = db_settings.get("OPTIONS", {})

    client_kwargs = {
        "region_name": options.get("region_name", "us-east-1"),
    }

    # Support local endpoint for development
    endpoint_url = options.get("endpoint_url")
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url

    # AWS credentials (optional - can use IAM roles)
    if options.get("aws_access_key_id"):
        client_kwargs["aws_access_key_id"] = options["aws_access_key_id"]
    if options.get("aws_secret_access_key"):
        client_kwargs["aws_secret_access_key"] = options["aws_secret_access_key"]

    return boto3.client("dynamodb", **client_kwargs)


def get_dynamodb_resource():
    """Get a boto3 DynamoDB resource configured from Django settings."""
    import boto3

    db_settings = getattr(settings, "DATABASES", {}).get("default", {})
    options = db_settings.get("OPTIONS", {})

    resource_kwargs = {
        "region_name": options.get("region_name", "us-east-1"),
    }

    endpoint_url = options.get("endpoint_url")
    if endpoint_url:
        resource_kwargs["endpoint_url"] = endpoint_url

    if options.get("aws_access_key_id"):
        resource_kwargs["aws_access_key_id"] = options["aws_access_key_id"]
    if options.get("aws_secret_access_key"):
        resource_kwargs["aws_secret_access_key"] = options["aws_secret_access_key"]

    return boto3.resource("dynamodb", **resource_kwargs)


class SessionStore(SessionBase):
    """
    DynamoDB-backed session store.

    Implements Django's session interface using DynamoDB as the storage backend.
    Sessions are automatically expired using DynamoDB's TTL feature.
    """

    def __init__(self, session_key=None):
        super().__init__(session_key)
        self._dynamodb = None
        self._table = None

    @property
    def dynamodb(self):
        """Lazy initialization of DynamoDB resource."""
        if self._dynamodb is None:
            self._dynamodb = get_dynamodb_resource()
        return self._dynamodb

    @property
    def table(self):
        """Get the DynamoDB sessions table."""
        if self._table is None:
            self._table = self.dynamodb.Table(DYNAMODB_SESSION_TABLE_NAME)
        return self._table

    def _encode_data(self, session_dict):
        """Encode session data for storage."""
        # Use Django's built-in encoding, then compress
        serialized = self.encode(session_dict)
        compressed = zlib.compress(serialized.encode("utf-8"))
        return base64.b64encode(compressed).decode("ascii")

    def _decode_data(self, data):
        """Decode session data from storage."""
        try:
            compressed = base64.b64decode(data.encode("ascii"))
            serialized = zlib.decompress(compressed).decode("utf-8")
            return self.decode(serialized)
        except Exception as e:
            logger.warning(f"Failed to decode session data: {e}")
            return {}

    def _get_expiry_timestamp(self):
        """Get the expiry timestamp as Unix epoch seconds."""
        expiry_age = self.get_expiry_age()
        expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expiry_age)
        return int(expiry_time.timestamp())

    def load(self):
        """Load session data from DynamoDB."""
        try:
            response = self.table.get_item(
                Key={"session_key": self._get_or_create_session_key()},
                ConsistentRead=True,  # Ensure we get the latest data
            )

            item = response.get("Item")
            if not item:
                self._session_key = None
                return {}

            # Check if session has expired (belt and suspenders with TTL)
            expire_date = item.get("expire_date", 0)
            if expire_date < time.time():
                self._session_key = None
                return {}

            # Decode and return session data
            session_data = item.get("session_data", "")
            return self._decode_data(session_data)

        except Exception as e:
            logger.error(f"Error loading session: {e}")
            self._session_key = None
            return {}

    def exists(self, session_key):
        """Check if a session key exists in DynamoDB."""
        try:
            response = self.table.get_item(
                Key={"session_key": session_key},
                ProjectionExpression="session_key, expire_date",
            )

            item = response.get("Item")
            if not item:
                return False

            # Check expiry
            expire_date = item.get("expire_date", 0)
            return expire_date >= time.time()

        except Exception as e:
            logger.error(f"Error checking session existence: {e}")
            return False

    def create(self):
        """Create a new session in DynamoDB."""
        while True:
            self._session_key = self._get_new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        """Save session data to DynamoDB."""
        if self.session_key is None:
            return self.create()

        session_key = self._get_or_create_session_key()
        session_data = self._encode_data(self._get_session(no_load=must_create))
        expire_date = self._get_expiry_timestamp()

        try:
            item = {
                "session_key": session_key,
                "session_data": session_data,
                "expire_date": expire_date,
            }

            if must_create:
                # Use conditional write to ensure we don't overwrite existing session
                self.table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(session_key)",
                )
            else:
                self.table.put_item(Item=item)

        except self.dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            if must_create:
                raise CreateError()
            raise
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            raise

    def delete(self, session_key=None):
        """Delete a session from DynamoDB."""
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key

        try:
            self.table.delete_item(Key={"session_key": session_key})
        except Exception as e:
            logger.error(f"Error deleting session: {e}")

    def clear_expired(self):
        """
        Clear expired sessions.

        Note: With DynamoDB TTL enabled, this is handled automatically.
        This method is provided for compatibility but is essentially a no-op.
        """
        logger.info("clear_expired called - DynamoDB TTL handles automatic expiration")

    @classmethod
    def clear_expired_sessions(cls):
        """Class method to clear expired sessions (no-op with TTL)."""
        logger.info("DynamoDB TTL automatically handles session expiration")


def create_session_table():
    """
    Create the DynamoDB sessions table with TTL enabled.

    This function should be called during deployment/migration.
    """
    client = get_dynamodb_client()

    try:
        # Check if table exists
        client.describe_table(TableName=DYNAMODB_SESSION_TABLE_NAME)
        logger.info(f"Session table {DYNAMODB_SESSION_TABLE_NAME} already exists")
        return True
    except client.exceptions.ResourceNotFoundException:
        pass

    # Create table
    logger.info(f"Creating session table: {DYNAMODB_SESSION_TABLE_NAME}")

    try:
        client.create_table(
            TableName=DYNAMODB_SESSION_TABLE_NAME,
            KeySchema=[
                {"AttributeName": "session_key", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "session_key", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",  # On-demand for cost efficiency
        )

        # Wait for table to be active
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=DYNAMODB_SESSION_TABLE_NAME)

        # Enable TTL
        client.update_time_to_live(
            TableName=DYNAMODB_SESSION_TABLE_NAME,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": DYNAMODB_SESSION_TTL_ATTRIBUTE,
            },
        )

        logger.info(f"Session table {DYNAMODB_SESSION_TABLE_NAME} created with TTL")
        return True

    except Exception as e:
        logger.error(f"Error creating session table: {e}")
        raise
