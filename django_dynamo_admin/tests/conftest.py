"""
Test configuration and fixtures for Django DynamoDB tests.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import django
import pytest
from django.conf import settings
from django.test import TransactionTestCase
from moto import mock_aws

# Pytest markers
pytest_markers = {
    "unit": "Unit tests that don't require external dependencies",
    "integration": "Integration tests that may require external services",
    "performance": "Performance tests that measure execution time",
    "slow": "Tests that take more than 1 second to run",
    "admin": "Tests related to Django admin functionality",
    "models": "Tests related to model functionality",
    "backend": "Tests related to database backend",
    "compiler": "Tests related to SQL compiler",
}


# Configure Django for testing
def pytest_configure(config):
    """Configure Django settings and pytest markers."""
    # Register markers
    for marker, description in pytest_markers.items():
        config.addinivalue_line("markers", f"{marker}: {description}")

    # Only configure Django if not already configured (via DJANGO_SETTINGS_MODULE)
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.admin",
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "django.contrib.messages",
                "dynamodb_adapter",
            ],
            SECRET_KEY="test-secret-key",
            USE_TZ=True,
        )
        django.setup()


@pytest.fixture
def mock_dynamodb_env():
    """Fixture to provide mocked DynamoDB environment."""
    with mock_aws():
        yield


@pytest.fixture
def sample_question():
    """Fixture to provide a sample Question instance."""
    from datetime import datetime

    from django_dynamo_admin.dynamodb_adapter.models import Question

    return Question(
        question_text="What is your favorite color?", pub_date=datetime.now()
    )


@pytest.fixture
def sample_choice():
    """Fixture to provide a sample Choice instance."""
    from django_dynamo_admin.dynamodb_adapter.models import Choice

    return Choice(question_id="123", choice_text="Blue", votes=5)


@pytest.fixture
def mock_pynamodb_model():
    """Fixture to provide a mock PynamoDB model."""
    mock_model = MagicMock()
    mock_model.Meta.table_name = "test_table"
    mock_model.Meta.region = "us-east-1"
    return mock_model


@pytest.fixture
def database_wrapper():
    """Fixture to provide a DatabaseWrapper instance."""
    from django_dynamo_admin.django_dynamo_admin.database.base import DatabaseWrapper

    db_settings = {
        "ENGINE": "django_dynamo_admin.database",
        "NAME": "test_db",
        "REGION": "us-east-1",
        "LOCAL_ENDPOINT": "http://localhost:9000",
    }

    return DatabaseWrapper(db_settings, alias="test")


@pytest.fixture
def sql_compiler():
    """Fixture to provide a SQL compiler instance."""
    from django_dynamo_admin.django_dynamo_admin.database.compiler import SQLCompiler

    query = MagicMock()
    connection = MagicMock()

    return SQLCompiler(query, connection, "default")


class TestEnvironment:
    """Test environment helper class."""

    @staticmethod
    def ensure_dynamodb_local():
        """Ensure DynamoDB Local is available for testing."""
        # This could check if DynamoDB Local is running
        # and start it if needed
        pass

    @staticmethod
    def cleanup_test_tables():
        """Clean up any test tables."""
        # This could clean up DynamoDB Local tables after tests
        pass


# Test collection customization
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on file path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)

        # Add specific markers based on filename
        if "test_models" in str(item.fspath):
            item.add_marker(pytest.mark.models)
        elif "test_database_backend" in str(item.fspath):
            item.add_marker(pytest.mark.backend)
        elif "test_compiler" in str(item.fspath):
            item.add_marker(pytest.mark.compiler)
        elif "admin" in str(item.fspath):
            item.add_marker(pytest.mark.admin)


# Fixtures for performance testing
@pytest.fixture
def performance_timer():
    """Fixture to measure performance."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()
            return self.elapsed

        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

    return Timer()


# Custom assertions for testing
class DynamoDBAssertions:
    """Custom assertions for DynamoDB testing."""

    @staticmethod
    def assert_pynamodb_model_created(django_model):
        """Assert that a PynamoDB model was created for a Django model."""
        pynamodb_model = django_model._get_pynamodb_model()
        assert pynamodb_model is not None
        assert hasattr(pynamodb_model, "Meta")
        assert hasattr(pynamodb_model.Meta, "table_name")
        assert hasattr(pynamodb_model.Meta, "region")

    @staticmethod
    def assert_field_mapping_correct(django_field, expected_pynamodb_attr):
        """Assert that a Django field maps to the correct PynamoDB attribute."""
        from django_dynamo_admin.dynamodb_adapter.fields import FieldMapper

        actual_attr = FieldMapper.get_dynamodb_attribute(django_field)
        assert actual_attr == expected_pynamodb_attr

    @staticmethod
    def assert_queryset_filters_applied(queryset, expected_filter_count):
        """Assert that the correct number of filters are applied to a queryset."""
        assert len(queryset._dynamodb_scan_filters) == expected_filter_count

    @staticmethod
    def assert_performance_threshold(elapsed_time, threshold, operation_name):
        """Assert that an operation meets performance threshold."""
        assert (
            elapsed_time < threshold
        ), f"{operation_name} took {elapsed_time:.4f}s, expected < {threshold}s"


@pytest.fixture
def db_assertions():
    """Fixture to provide custom DynamoDB assertions."""
    return DynamoDBAssertions()


# Error handling fixtures
@pytest.fixture
def suppress_logging():
    """Fixture to suppress logging during tests."""
    import logging

    # Disable logging below CRITICAL level
    logging.disable(logging.CRITICAL)
    yield
    # Re-enable logging
    logging.disable(logging.NOTSET)


# Database state fixtures
@pytest.fixture
def clean_database():
    """Fixture to ensure clean database state."""
    # Setup: ensure clean state
    yield
    # Teardown: clean up any test data
    TestEnvironment.cleanup_test_tables()


# Mock fixtures
@pytest.fixture
def mock_boto3():
    """Fixture to mock boto3 for testing."""
    with patch("boto3.client") as mock_client, patch("boto3.resource") as mock_resource:

        # Configure mock returns
        mock_client.return_value = MagicMock()
        mock_resource.return_value = MagicMock()

        yield {"client": mock_client, "resource": mock_resource}
