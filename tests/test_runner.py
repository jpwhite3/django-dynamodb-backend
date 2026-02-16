"""
Comprehensive test runner for Django DynamoDB integration.
"""

import os
import sys
import time
import unittest

import django
from django.conf import settings

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Django settings for testing
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            "default": {
                "ENGINE": "django_dynamodb_backend.db",
                "NAME": "test_dynamodb",
                "REGION": "us-east-1",
                "LOCAL_ENDPOINT": "http://localhost:9000",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "django_dynamodb_backend",
            "tests",
        ],
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ],
        ROOT_URLCONF="tests.urls",
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.debug",
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            },
        ],
        SECRET_KEY="django-insecure-test-key-for-testing-only",
        USE_I18N=True,
        USE_L10N=True,
        USE_TZ=True,
        STATIC_URL="/static/",
        LOGGING={
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                },
            },
            "loggers": {
                "django_dynamodb_backend": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        },
    )

django.setup()


class DynamoDBTestResult(unittest.TextTestResult):
    """Custom test result class with enhanced reporting."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_times = {}
        self.start_time = None
        self.performance_metrics = []

    def startTest(self, test):
        super().startTest(test)
        self.start_time = time.time()

    def stopTest(self, test):
        super().stopTest(test)
        if self.start_time:
            test_time = time.time() - self.start_time
            self.test_times[str(test)] = test_time

            # Track slow tests
            if test_time > 1.0:  # Tests taking more than 1 second
                self.performance_metrics.append(
                    {"test": str(test), "time": test_time, "status": "SLOW"}
                )

    def addSuccess(self, test):
        super().addSuccess(test)
        test_time = self.test_times.get(str(test), 0)
        if test_time > 0.5:  # Mark as slow success
            self.stream.write("s")
        else:
            self.stream.write(".")

    def printErrors(self):
        super().printErrors()

        # Print performance summary
        if self.performance_metrics:
            self.stream.write("\n" + "=" * 70 + "\n")
            self.stream.write("PERFORMANCE SUMMARY\n")
            self.stream.write("=" * 70 + "\n")

            for metric in self.performance_metrics:
                self.stream.write(f"SLOW: {metric['test']} ({metric['time']:.3f}s)\n")

        # Print timing summary
        if self.test_times:
            self.stream.write("\n" + "=" * 70 + "\n")
            self.stream.write("TIMING SUMMARY\n")
            self.stream.write("=" * 70 + "\n")

            sorted_times = sorted(
                self.test_times.items(), key=lambda x: x[1], reverse=True
            )
            for test_name, test_time in sorted_times[:10]:  # Top 10 slowest
                self.stream.write(f"{test_time:.3f}s - {test_name}\n")


class DynamoDBTestRunner:
    """Custom test runner for DynamoDB integration tests."""

    def __init__(self, verbosity=2, interactive=True, debug=False, **kwargs):
        self.verbosity = verbosity
        self.interactive = interactive
        self.debug = debug
        self.kwargs = kwargs

    def run_tests(self, test_labels=None, extra_tests=None, **kwargs):
        """Run the test suite."""
        if test_labels is None:
            test_labels = ["tests"]

        print("=" * 80)
        print("DJANGO DYNAMODB INTEGRATION TEST SUITE")
        print("=" * 80)
        print()

        # Discover and run tests
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()

        # Load unit tests
        print("Loading unit tests...")
        try:
            unit_tests = loader.discover("tests.unit", pattern="test_*.py")
            suite.addTest(unit_tests)
            print(f"✓ Loaded unit tests: {unit_tests.countTestCases()} tests")
        except Exception as e:
            print(f"✗ Error loading unit tests: {e}")

        # Load integration tests
        print("Loading integration tests...")
        try:
            integration_tests = loader.discover(
                "tests.integration", pattern="test_*.py"
            )
            suite.addTest(integration_tests)
            print(
                f"✓ Loaded integration tests: {integration_tests.countTestCases()} tests"
            )
        except Exception as e:
            print(f"✗ Error loading integration tests: {e}")

        # Load performance tests (optional)
        if "--performance" in sys.argv:
            print("Loading performance tests...")
            try:
                performance_tests = loader.discover(
                    "tests.performance", pattern="test_*.py"
                )
                suite.addTest(performance_tests)
                print(
                    f"✓ Loaded performance tests: {performance_tests.countTestCases()} tests"
                )
            except Exception as e:
                print(f"✗ Error loading performance tests: {e}")

        print(f"\nTotal tests to run: {suite.countTestCases()}")
        print("-" * 80)

        # Run tests with custom result class
        runner = unittest.TextTestRunner(
            verbosity=self.verbosity,
            resultclass=DynamoDBTestResult,
            stream=sys.stdout,
            descriptions=True,
            failfast="--failfast" in sys.argv,
        )

        start_time = time.time()
        result = runner.run(suite)
        end_time = time.time()

        # Print summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Skipped: {len(result.skipped)}")
        print(f"Total time: {end_time - start_time:.2f}s")

        if result.wasSuccessful():
            print("\n🎉 ALL TESTS PASSED!")
            return 0
        else:
            print(f"\n❌ {len(result.failures) + len(result.errors)} TEST(S) FAILED")
            return 1


def run_specific_test_suite(suite_name):
    """Run a specific test suite."""
    loader = unittest.TestLoader()

    suite_map = {
        "unit": "tests.unit",
        "integration": "tests.integration",
        "performance": "tests.performance",
        "models": "tests.unit.test_models",
        "backend": "tests.unit.test_database_backend",
        "compiler": "tests.unit.test_compiler",
        "admin": "tests.integration.test_admin_integration",
    }

    if suite_name not in suite_map:
        print(f"Unknown test suite: {suite_name}")
        print(f"Available suites: {', '.join(suite_map.keys())}")
        return 1

    try:
        if suite_name in ["unit", "integration", "performance"]:
            suite = loader.discover(suite_map[suite_name], pattern="test_*.py")
        else:
            suite = loader.loadTestsFromName(suite_map[suite_name])

        runner = unittest.TextTestRunner(verbosity=2, resultclass=DynamoDBTestResult)
        result = runner.run(suite)

        return 0 if result.wasSuccessful() else 1

    except Exception as e:
        print(f"Error running test suite '{suite_name}': {e}")
        return 1


def main():
    """Main test runner entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Django DynamoDB Test Runner")
    parser.add_argument(
        "--suite",
        help="Run specific test suite",
        choices=[
            "unit",
            "integration",
            "performance",
            "models",
            "backend",
            "compiler",
            "admin",
        ],
    )
    parser.add_argument(
        "--performance", action="store_true", help="Include performance tests"
    )
    parser.add_argument("--failfast", action="store_true", help="Stop on first failure")
    parser.add_argument(
        "--verbosity", "-v", type=int, default=2, help="Verbosity level (0-3)"
    )

    args, unknown = parser.parse_known_args()

    if args.suite:
        return run_specific_test_suite(args.suite)
    else:
        runner = DynamoDBTestRunner(verbosity=args.verbosity)
        return runner.run_tests()


if __name__ == "__main__":
    sys.exit(main())
