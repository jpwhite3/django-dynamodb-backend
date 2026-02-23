"""
Integration tests for the DynamoDB session backend using moto.

Validates SessionStore CRUD, TTL expiration logic, and the
create_session_table helper.
"""

import time

import boto3
import pytest
from django.conf import settings
from moto import mock_aws

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_sessions_table():
    """Create the django_sessions table in mocked DynamoDB."""
    client = boto3.client(
        "dynamodb",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    client.create_table(
        TableName="django_sessions",
        KeySchema=[{"AttributeName": "session_key", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "session_key", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture()
def dynamo_sessions(monkeypatch):
    """Provide a mocked DynamoDB sessions table and patch settings."""
    with mock_aws():
        monkeypatch.setattr(
            settings,
            "DATABASES",
            {
                "default": {
                    "ENGINE": "django_dynamodb_backend.db",
                    "NAME": "test",
                    "OPTIONS": {
                        "region_name": "us-east-1",
                        "aws_access_key_id": "testing",
                        "aws_secret_access_key": "testing",
                    },
                }
            },
        )
        _create_sessions_table()
        yield


# ---------------------------------------------------------------------------
# SessionStore tests
# ---------------------------------------------------------------------------


class TestSessionStore:
    """Test SessionStore CRUD against mocked DynamoDB."""

    def _make_store(self, session_key=None):
        from django_dynamodb_backend.sessions import SessionStore

        store = SessionStore(session_key=session_key)
        # Reset cached connections so each test uses fresh moto resources
        store._dynamodb = None
        store._table = None
        return store

    def test_create_and_load(self, dynamo_sessions):
        store = self._make_store()
        store["color"] = "blue"
        store.create()
        key = store.session_key
        assert key is not None

        # Load from a new store instance
        store2 = self._make_store(session_key=key)
        data = store2.load()
        assert data.get("color") == "blue"

    def test_save_and_load(self, dynamo_sessions):
        store = self._make_store()
        store.create()
        key = store.session_key

        store["fruit"] = "apple"
        store.save()

        store2 = self._make_store(session_key=key)
        data = store2.load()
        assert data.get("fruit") == "apple"

    def test_exists(self, dynamo_sessions):
        store = self._make_store()
        store.create()
        key = store.session_key

        assert store.exists(key) is True
        assert store.exists("nonexistent-key") is False

    def test_delete(self, dynamo_sessions):
        store = self._make_store()
        store.create()
        key = store.session_key

        store.delete(key)
        assert store.exists(key) is False

    def test_load_nonexistent_returns_empty(self, dynamo_sessions):
        store = self._make_store(session_key="does-not-exist")
        data = store.load()
        assert data == {}

    def test_load_expired_returns_empty(self, dynamo_sessions):
        """A session with a past expiry should be treated as missing."""
        store = self._make_store()
        store.create()
        key = store.session_key

        # Manually set expire_date to the past
        from django_dynamodb_backend.sessions import get_dynamodb_resource

        table = get_dynamodb_resource().Table("django_sessions")
        table.update_item(
            Key={"session_key": key},
            UpdateExpression="SET expire_date = :ts",
            ExpressionAttributeValues={":ts": int(time.time()) - 3600},
        )

        store2 = self._make_store(session_key=key)
        data = store2.load()
        assert data == {}

    def test_save_overwrites_existing(self, dynamo_sessions):
        store = self._make_store()
        store["val"] = "first"
        store.create()
        key = store.session_key

        store["val"] = "second"
        store.save()

        store2 = self._make_store(session_key=key)
        data = store2.load()
        assert data.get("val") == "second"

    def test_clear_expired_is_noop(self, dynamo_sessions):
        """clear_expired should not raise (TTL handles cleanup)."""
        store = self._make_store()
        store.clear_expired()  # should not raise

    def test_delete_without_key_is_noop(self, dynamo_sessions):
        """Deleting when no session key is set should not raise."""
        store = self._make_store()
        store.delete()  # should not raise


# ---------------------------------------------------------------------------
# create_session_table helper
# ---------------------------------------------------------------------------


class TestCreateSessionTable:
    def test_creates_table(self, dynamo_sessions, monkeypatch):
        """create_session_table should create the table if it doesn't exist."""
        from django_dynamodb_backend.sessions import create_session_table

        # Delete the table so create_session_table has work to do
        client = boto3.client(
            "dynamodb",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        client.delete_table(TableName="django_sessions")

        result = create_session_table()
        assert result is True

        # Verify table exists
        desc = client.describe_table(TableName="django_sessions")
        assert desc["Table"]["TableName"] == "django_sessions"

    def test_idempotent(self, dynamo_sessions):
        """Calling create_session_table when table exists should succeed."""
        from django_dynamodb_backend.sessions import create_session_table

        assert create_session_table() is True
