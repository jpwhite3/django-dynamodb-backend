"""
Performance tests for DynamoDB Django integration.
"""

import statistics
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from django.test import TestCase

from django_dynamodb_backend.managers import (
    DynamoDBQuerySet,
)
from django_dynamodb_backend.models import MyModel, Question


class TestModelCreationPerformance(TestCase):
    """Test performance of model creation and PynamoDB integration."""

    def test_pynamodb_model_creation_time(self):
        """Test time taken to create PynamoDB models from Django models."""
        start_time = time.time()

        # Create multiple test models
        class TestModel1(MyModel):
            name = "test1"

            class Meta:
                app_label = "performance_tests"

        class TestModel2(MyModel):
            name = "test2"

            class Meta:
                app_label = "performance_tests"

        class TestModel3(MyModel):
            name = "test3"

            class Meta:
                app_label = "performance_tests"

        # Force PynamoDB model creation
        models = [TestModel1, TestModel2, TestModel3]
        for model in models:
            pynamodb_model = model._get_pynamodb_model()
            self.assertIsNotNone(pynamodb_model)

        end_time = time.time()
        creation_time = end_time - start_time

        # Should create models quickly (less than 1 second for 3 models)
        self.assertLess(
            creation_time,
            1.0,
            f"Model creation took {creation_time:.3f}s, expected < 1.0s",
        )

        print(f"PynamoDB model creation time for 3 models: {creation_time:.3f}s")

    def test_model_instance_creation_performance(self):
        """Test performance of creating model instances."""
        times = []
        num_iterations = 100

        for i in range(num_iterations):
            start_time = time.time()

            Question(
                question_text=f"Test question {i}", pub_date=datetime.now()
            )

            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)
        max_time = max(times)

        # Should create instances quickly
        self.assertLess(
            avg_time,
            0.01,  # Less than 10ms on average
            f"Average instance creation time: {avg_time:.4f}s",
        )
        self.assertLess(
            max_time,
            0.1,  # Less than 100ms maximum
            f"Maximum instance creation time: {max_time:.4f}s",
        )

        print(
            f"Model instance creation - Average: {avg_time:.4f}s, Max: {max_time:.4f}s"
        )


class TestQuerySetPerformance(TestCase):
    """Test performance of QuerySet operations."""

    def setUp(self):
        """Set up test environment."""
        self.queryset = DynamoDBQuerySet(model=Question)

    def test_filter_chain_performance(self):
        """Test performance of chaining multiple filters."""
        start_time = time.time()

        # Chain multiple filters
        filtered_queryset = (
            self.queryset.filter(question_text__contains="test")
            .filter(pub_date__gte=datetime.now())
            .exclude(id="exclude_me")
            .filter(question_text__startswith="What")
        )

        end_time = time.time()
        filter_time = end_time - start_time

        # Filter chaining should be fast (it's just object manipulation)
        self.assertLess(
            filter_time,
            0.1,
            f"Filter chaining took {filter_time:.4f}s, expected < 0.1s",
        )

        # Verify filters were applied
        self.assertEqual(len(filtered_queryset._dynamodb_scan_filters), 4)

        print(f"Filter chain performance: {filter_time:.4f}s")

    def test_lookup_conversion_performance(self):
        """Test performance of lookup conversion."""
        lookups = [
            ("name", "exact", "test"),
            ("count", "gt", 10),
            ("name", "contains", "substring"),
            ("date_field", "gte", datetime.now()),
            ("id", "in", [1, 2, 3, 4, 5]),
        ]

        times = []

        for field, lookup, value in lookups:
            start_time = time.time()

            self.queryset._convert_lookup(field, lookup, value)

            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)
        max_time = max(times)

        # Lookup conversion should be very fast
        self.assertLess(
            avg_time,
            0.001,  # Less than 1ms on average
            f"Average lookup conversion time: {avg_time:.6f}s",
        )

        print(f"Lookup conversion - Average: {avg_time:.6f}s, Max: {max_time:.6f}s")


class TestFieldMappingPerformance(TestCase):
    """Test performance of field mapping operations."""

    def test_field_mapping_performance(self):
        """Test performance of field type mapping."""
        from django.db import models

        from django_dynamodb_backend.fields import FieldMapper

        # Test various field types
        field_types = [
            models.CharField(max_length=100),
            models.IntegerField(),
            models.BooleanField(),
            models.DateTimeField(),
            models.JSONField(),
            models.TextField(),
            models.FloatField(),
            models.UUIDField(),
        ]

        times = []

        for field in field_types:
            start_time = time.time()

            # Get DynamoDB attribute type
            attr_type = FieldMapper.get_dynamodb_attribute(field)

            end_time = time.time()
            times.append(end_time - start_time)

            self.assertIsNotNone(attr_type)

        avg_time = statistics.mean(times)
        total_time = sum(times)

        # Field mapping should be extremely fast
        self.assertLess(
            avg_time,
            0.0001,  # Less than 0.1ms on average
            f"Average field mapping time: {avg_time:.6f}s",
        )

        print(f"Field mapping - Total: {total_time:.6f}s, Average: {avg_time:.6f}s")

    def test_value_conversion_performance(self):
        """Test performance of value conversion."""
        import uuid
        from datetime import date
        from datetime import time as dt_time
        from decimal import Decimal

        from django.db import models

        from django_dynamodb_backend.fields import FieldMapper

        # Test conversion for various types
        test_cases = [
            (models.CharField(max_length=100), "test string"),
            (models.IntegerField(), 12345),
            (models.BooleanField(), True),
            (models.DateField(), date(2023, 12, 25)),
            (models.TimeField(), dt_time(14, 30, 0)),
            (models.UUIDField(), uuid.uuid4()),
            (models.DecimalField(max_digits=10, decimal_places=2), Decimal("123.45")),
        ]

        conversion_times = []
        back_conversion_times = []

        for field, value in test_cases:
            # Test conversion to DynamoDB
            start_time = time.time()
            dynamodb_value = FieldMapper.convert_value_to_dynamodb(value, field)
            end_time = time.time()
            conversion_times.append(end_time - start_time)

            # Test conversion back from DynamoDB
            start_time = time.time()
            FieldMapper.convert_value_from_dynamodb(dynamodb_value, field)
            end_time = time.time()
            back_conversion_times.append(end_time - start_time)

        avg_conversion = statistics.mean(conversion_times)
        avg_back_conversion = statistics.mean(back_conversion_times)

        # Both conversions should be fast
        self.assertLess(
            avg_conversion,
            0.001,
            f"Average to-DynamoDB conversion: {avg_conversion:.6f}s",
        )
        self.assertLess(
            avg_back_conversion,
            0.001,
            f"Average from-DynamoDB conversion: {avg_back_conversion:.6f}s",
        )

        print(
            f"Value conversion - To DynamoDB: {avg_conversion:.6f}s, "
            f"From DynamoDB: {avg_back_conversion:.6f}s"
        )


class TestDatabaseBackendPerformance(TestCase):
    """Test performance of database backend operations."""

    def setUp(self):
        """Set up database backend."""
        from django_dynamodb_backend.db.base import (
            DatabaseWrapper,
        )

        self.db_settings = {
            "ENGINE": "django_dynamodb_backend.db",
            "NAME": "test_db",
            "REGION": "us-east-1",
            "LOCAL_ENDPOINT": "http://localhost:9000",
        }
        self.db_wrapper = DatabaseWrapper(self.db_settings, alias="test")

    def test_connection_parameter_extraction_performance(self):
        """Test performance of connection parameter extraction."""
        times = []
        num_iterations = 1000

        for _ in range(num_iterations):
            start_time = time.time()
            self.db_wrapper.get_connection_params()
            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)

        # Should be very fast
        self.assertLess(
            avg_time, 0.0001, f"Connection parameter extraction: {avg_time:.6f}s"
        )

        print(f"Connection parameter extraction: {avg_time:.6f}s")

    def test_cursor_creation_performance(self):
        """Test performance of cursor creation."""
        times = []
        num_iterations = 1000

        for _ in range(num_iterations):
            start_time = time.time()
            cursor = self.db_wrapper.create_cursor()
            end_time = time.time()
            times.append(end_time - start_time)
            cursor.close()  # Clean up

        avg_time = statistics.mean(times)

        # Should be very fast
        self.assertLess(avg_time, 0.001, f"Cursor creation: {avg_time:.6f}s")

        print(f"Cursor creation: {avg_time:.6f}s")


class TestCompilerPerformance(TestCase):
    """Test performance of SQL compiler operations."""

    def setUp(self):
        """Set up compiler."""
        from django_dynamodb_backend.db.compiler import (
            SQLCompiler,
        )

        self.query = MagicMock()
        self.connection = MagicMock()
        self.compiler = SQLCompiler(self.query, self.connection, "default")

    def test_query_analysis_performance(self):
        """Test performance of query analysis."""
        # Set up mock query
        self.compiler.query.model = MagicMock()
        self.compiler.query.model._meta.db_table = "test_table"
        self.compiler.query.where = None
        self.compiler.query.select = None
        self.compiler.query.order_by = None

        times = []
        num_iterations = 1000

        for _ in range(num_iterations):
            start_time = time.time()
            self.compiler._analyze_query()
            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)

        # Should be fast
        self.assertLess(avg_time, 0.001, f"Query analysis: {avg_time:.6f}s")

        print(f"Query analysis: {avg_time:.6f}s")

    def test_dynamodb_query_building_performance(self):
        """Test performance of DynamoDB query building."""
        self.compiler.table_name = "test_table"
        self.compiler.filter_expression = [
            {"field": "name", "operation": "=", "value": "test"},
            {"field": "count", "operation": ">", "value": 10},
        ]
        self.compiler.projection_expression = ["name", "count", "description"]

        times = []
        num_iterations = 1000

        for _ in range(num_iterations):
            start_time = time.time()
            self.compiler._build_dynamodb_query()
            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)

        # Should be very fast
        self.assertLess(avg_time, 0.0001, f"DynamoDB query building: {avg_time:.6f}s")

        print(f"DynamoDB query building: {avg_time:.6f}s")


class TestMemoryUsage(TestCase):
    """Test memory usage of various operations."""

    def test_model_creation_memory(self):
        """Test memory usage during model creation."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create multiple models
        models = []
        for i in range(100):
            question = Question(question_text=f"Question {i}", pub_date=datetime.now())
            models.append(question)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 10MB for 100 models)
        self.assertLess(
            memory_increase,
            10 * 1024 * 1024,
            f"Memory increase: {memory_increase / 1024 / 1024:.2f}MB",
        )

        print(f"Memory usage for 100 models: {memory_increase / 1024:.2f}KB")

    def test_queryset_memory_usage(self):
        """Test memory usage of QuerySet operations."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create and chain many QuerySet operations
        queryset = Question.objects.all()
        for i in range(50):
            queryset = queryset.filter(question_text__contains=f"test{i}")

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be minimal for QuerySet chaining
        self.assertLess(
            memory_increase,
            5 * 1024 * 1024,
            f"QuerySet memory increase: {memory_increase / 1024 / 1024:.2f}MB",
        )

        print(f"QuerySet chaining memory usage: {memory_increase / 1024:.2f}KB")


class TestConcurrencyPerformance(TestCase):
    """Test performance under concurrent operations."""

    def test_concurrent_model_creation(self):
        """Test concurrent model creation performance."""
        import queue
        import threading

        results = queue.Queue()
        num_threads = 10
        models_per_thread = 10

        def create_models():
            thread_start = time.time()
            for i in range(models_per_thread):
                question = Question(
                    question_text=f"Concurrent question {threading.current_thread().ident}_{i}",
                    pub_date=datetime.now(),
                )
                # Simulate some processing
                _ = str(question)
            thread_end = time.time()
            results.put(thread_end - thread_start)

        # Start concurrent threads
        threads = []
        overall_start = time.time()

        for _ in range(num_threads):
            thread = threading.Thread(target=create_models)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        overall_end = time.time()

        # Collect results
        thread_times = []
        while not results.empty():
            thread_times.append(results.get())

        avg_thread_time = statistics.mean(thread_times)
        total_time = overall_end - overall_start

        print(
            f"Concurrent creation - Total time: {total_time:.3f}s, "
            f"Average thread time: {avg_thread_time:.3f}s"
        )

        # Should complete reasonably quickly
        self.assertLess(total_time, 5.0, f"Concurrent operation took {total_time:.3f}s")


if __name__ == "__main__":
    # Run with verbose output to see performance metrics
    unittest.main(verbosity=2)
