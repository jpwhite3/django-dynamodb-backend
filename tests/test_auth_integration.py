"""
Integration tests for DynamoDB auth (managers + backends) using moto.

These tests exercise actual DynamoDB operations via moto's mock_aws,
validating the real code paths that the contract-only compat tests don't cover.
"""

import boto3
import pytest
from moto import mock_aws

from django.conf import settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _create_users_table():
    """Create the django_users table in mocked DynamoDB."""
    client = boto3.client(
        "dynamodb",
        region_name="us-east-1",
        endpoint_url=None,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    client.create_table(
        TableName="django_users",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "username", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "username-index",
                "KeySchema": [{"AttributeName": "username", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture()
def dynamo_users_table(monkeypatch):
    """Provide a mocked DynamoDB users table and patch settings."""
    with mock_aws():
        # Patch DATABASES so get_dynamodb_resource() talks to moto
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
        _create_users_table()
        yield


# ---------------------------------------------------------------------------
# DynamoUserManager tests
# ---------------------------------------------------------------------------


class TestDynamoUserManager:
    """Test DynamoUserManager against mocked DynamoDB."""

    def _get_manager(self):
        from django_dynamodb_backend.contrib.auth_dynamo.managers import DynamoUserManager
        from django_dynamodb_backend.contrib.auth_dynamo.models import DynamoUser

        mgr = DynamoUserManager()
        mgr.model = DynamoUser
        return mgr

    def test_create_user(self, dynamo_users_table):
        mgr = self._get_manager()
        user = mgr.create_user("alice", email="alice@example.com", password="pw123456")
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.check_password("pw123456")
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_superuser(self, dynamo_users_table):
        mgr = self._get_manager()
        user = mgr.create_superuser("admin", email="a@b.com", password="admin123")
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_create_user_duplicate_username_raises(self, dynamo_users_table):
        mgr = self._get_manager()
        mgr.create_user("bob", password="pw123456")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_user("bob", password="other")

    def test_get_by_pk(self, dynamo_users_table):
        mgr = self._get_manager()
        created = mgr.create_user("carol", password="pw123456")
        fetched = mgr.get(pk=created.id)
        assert fetched.username == "carol"

    def test_get_by_username(self, dynamo_users_table):
        mgr = self._get_manager()
        mgr.create_user("dave", password="pw123456")
        fetched = mgr.get(username="dave")
        assert fetched.username == "dave"

    def test_get_by_email(self, dynamo_users_table):
        mgr = self._get_manager()
        mgr.create_user("eve", email="eve@example.com", password="pw123456")
        fetched = mgr.get(email="eve@example.com")
        assert fetched.username == "eve"

    def test_get_nonexistent_raises(self, dynamo_users_table):
        from django_dynamodb_backend.contrib.auth_dynamo.models import DynamoUser

        mgr = self._get_manager()
        with pytest.raises(DynamoUser.DoesNotExist):
            mgr.get(username="ghost")

    def test_exists(self, dynamo_users_table):
        mgr = self._get_manager()
        assert mgr.exists(username="nobody") is False
        mgr.create_user("nobody", password="pw123456")
        assert mgr.exists(username="nobody") is True

    def test_create_user_without_password(self, dynamo_users_table):
        mgr = self._get_manager()
        user = mgr.create_user("nopass")
        assert not user.has_usable_password()


# ---------------------------------------------------------------------------
# DynamoAuthBackend tests
# ---------------------------------------------------------------------------


class TestDynamoAuthBackend:
    """Test authenticate() and get_user() against mocked DynamoDB."""

    def _setup(self):
        from django_dynamodb_backend.contrib.auth_dynamo.backends import DynamoAuthBackend
        from django_dynamodb_backend.contrib.auth_dynamo.managers import DynamoUserManager
        from django_dynamodb_backend.contrib.auth_dynamo.models import DynamoUser

        mgr = DynamoUserManager()
        mgr.model = DynamoUser
        return DynamoAuthBackend(), mgr

    def test_authenticate_success(self, dynamo_users_table):
        backend, mgr = self._setup()
        mgr.create_user("frank", password="secret99")
        user = backend.authenticate(None, username="frank", password="secret99")
        assert user is not None
        assert user.username == "frank"

    def test_authenticate_wrong_password(self, dynamo_users_table):
        backend, mgr = self._setup()
        mgr.create_user("grace", password="correct")
        user = backend.authenticate(None, username="grace", password="wrong")
        assert user is None

    def test_authenticate_nonexistent_user(self, dynamo_users_table):
        backend, _ = self._setup()
        user = backend.authenticate(None, username="ghost", password="nope")
        assert user is None

    def test_get_user(self, dynamo_users_table):
        backend, mgr = self._setup()
        created = mgr.create_user("hank", password="pw123456")
        fetched = backend.get_user(created.id)
        assert fetched is not None
        assert fetched.username == "hank"

    def test_get_user_nonexistent(self, dynamo_users_table):
        backend, _ = self._setup()
        assert backend.get_user("nonexistent-id") is None
