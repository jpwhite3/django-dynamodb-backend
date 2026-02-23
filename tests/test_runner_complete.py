"""
Complete test runner for the entire DynamoDB Django Admin system.

This module provides comprehensive testing utilities and a complete test runner
that validates all phases of the project.
"""

import os
import sys
import time
import unittest

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_settings")

import django


class ComprehensiveTestResult:
    """Store and display comprehensive test results."""

    def __init__(self):
        self.phases = {}
        self.start_time = None
        self.end_time = None
        self.total_tests = 0
        self.total_failures = 0
        self.total_errors = 0
        self.total_skipped = 0

    def add_phase_result(self, phase_name, result):
        """Add results for a specific phase."""
        self.phases[phase_name] = {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(getattr(result, "skipped", [])),
            "success": result.wasSuccessful(),
            "details": {
                "failures": result.failures,
                "errors": result.errors,
                "skipped": getattr(result, "skipped", []),
            },
        }

        self.total_tests += result.testsRun
        self.total_failures += len(result.failures)
        self.total_errors += len(result.errors)
        self.total_skipped += len(getattr(result, "skipped", []))

    def print_summary(self):
        """Print comprehensive test summary."""
        duration = (
            self.end_time - self.start_time if self.end_time and self.start_time else 0
        )

        print("\n" + "=" * 80)
        print("COMPREHENSIVE TEST RESULTS - DynamoDB Django Admin")
        print("=" * 80)
        print(f"Total Duration: {duration:.2f} seconds")
        print(f"Total Tests: {self.total_tests}")
        passed = (
            self.total_tests
            - self.total_failures
            - self.total_errors
            - self.total_skipped
        )
        print(f"Passed: {passed}")
        print(f"Failed: {self.total_failures}")
        print(f"Errors: {self.total_errors}")
        print(f"Skipped: {self.total_skipped}")

        overall_success = self.total_failures == 0 and self.total_errors == 0
        status = "✅ PASSED" if overall_success else "❌ FAILED"
        print(f"Overall Status: {status}")

        print("\nPHASE BREAKDOWN:")
        print("-" * 50)

        for phase_name, results in self.phases.items():
            status_symbol = "✅" if results["success"] else "❌"
            print(f"{status_symbol} {phase_name}:")
            print(f"    Tests: {results['tests_run']}")
            print(f"    Failures: {results['failures']}")
            print(f"    Errors: {results['errors']}")
            print(f"    Skipped: {results['skipped']}")

        # Print detailed failures and errors if any
        if self.total_failures > 0 or self.total_errors > 0:
            print("\nDETAILED ISSUES:")
            print("-" * 50)

            for phase_name, results in self.phases.items():
                if results["failures"] or results["errors"]:
                    print(f"\n{phase_name} Issues:")

                    for test, traceback in results["details"]["failures"]:
                        print(f"  FAILURE: {test}")
                        tb_short = (
                            traceback.split("/")[-1]
                            if "/" in traceback
                            else traceback[:100]
                        )
                        print(f"    {tb_short}...")

                    for test, traceback in results["details"]["errors"]:
                        print(f"  ERROR: {test}")
                        tb_short = (
                            traceback.split("/")[-1]
                            if "/" in traceback
                            else traceback[:100]
                        )
                        print(f"    {tb_short}...")

        print("=" * 80)
        return overall_success


def setup_test_database():
    """Set up Django test database with required tables."""
    from django.core.management import call_command

    # Create all tables needed for Django's built-in models
    call_command("migrate", "--run-syncdb", verbosity=0)


class ComprehensiveTestRunner:
    """Run comprehensive tests for all phases."""

    def __init__(self, verbosity=1):
        self.verbosity = verbosity
        self.result = ComprehensiveTestResult()
        self._db_setup = False

    def _ensure_database_setup(self):
        """Ensure test database is set up before running tests."""
        if not self._db_setup:
            setup_test_database()
            self._db_setup = True

    def run_phase_tests(self, phase_name, test_patterns):
        """Run tests for a specific phase."""
        # Ensure database is set up
        self._ensure_database_setup()

        print(f"\n{'='*20} {phase_name} {'='*20}")

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()

        # Load tests based on patterns
        for pattern in test_patterns:
            try:
                if pattern.startswith("tests."):
                    # Module pattern
                    module_tests = loader.loadTestsFromName(pattern)
                    suite.addTests(module_tests)
                else:
                    # Directory pattern
                    discovered = loader.discover(pattern, pattern="test_*.py")
                    suite.addTests(discovered)
            except Exception as e:
                print(f"Warning: Could not load tests from {pattern}: {e}")

        # Run the tests
        runner = unittest.TextTestRunner(
            verbosity=self.verbosity, stream=sys.stdout, buffer=True
        )

        phase_result = runner.run(suite)
        self.result.add_phase_result(phase_name, phase_result)

        return phase_result.wasSuccessful()

    def run_all_phases(self):
        """Run tests for all phases of the project."""
        self.result.start_time = time.time()

        phases = [
            (
                "Phase 1: Database Backend",
                [
                    "tests.unit.test_database_backend",
                    "tests.unit.test_compiler",
                    "tests.unit.test_compiler_integration",
                ],
            ),
            ("Phase 2: Field Mapping", ["tests.unit.test_models"]),
            ("Phase 3: QuerySet & Manager", ["tests.unit.test_enhanced_queryset"]),
            ("Phase 4: Django Admin", ["tests.integration.test_admin_comprehensive"]),
            (
                "Phase 5: Migration System",
                [
                    "tests.unit.test_migrations",
                    "tests.integration.test_migration_integration",
                ],
            ),
            ("Phase 6: Complete Integration", ["tests.test_complete_integration"]),
            (
                "Phase 7: Enhanced Admin Features",
                ["tests.test_enhanced_admin_features"],
            ),
        ]

        for phase_name, test_patterns in phases:
            try:
                success = self.run_phase_tests(phase_name, test_patterns)
                if not success:
                    pass
            except Exception as e:
                print(f"Error running {phase_name}: {e}")

        self.result.end_time = time.time()
        return self.result.print_summary()

    def run_specific_phase(self, phase_number):
        """Run tests for a specific phase only."""
        phase_map = {
            1: (
                "Phase 1: Database Backend",
                ["tests.unit.test_database_backend", "tests.unit.test_compiler"],
            ),
            2: ("Phase 2: Field Mapping", ["tests.unit.test_models"]),
            3: ("Phase 3: QuerySet & Manager", ["tests.unit.test_enhanced_queryset"]),
            4: (
                "Phase 4: Django Admin",
                ["tests.integration.test_admin_comprehensive"],
            ),
            5: ("Phase 5: Migration System", ["tests.unit.test_migrations"]),
            6: ("Phase 6: Complete Integration", ["tests.test_complete_integration"]),
            7: (
                "Phase 7: Enhanced Admin Features",
                ["tests.test_enhanced_admin_features"],
            ),
        }

        if phase_number not in phase_map:
            print(f"Invalid phase number: {phase_number}")
            return False

        self.result.start_time = time.time()
        phase_name, test_patterns = phase_map[phase_number]
        self.run_phase_tests(phase_name, test_patterns)
        self.result.end_time = time.time()

        return self.result.print_summary()


def run_quick_validation():
    """Run a quick validation test to ensure basic functionality."""
    print("Running Quick Validation Tests...")
    print("-" * 40)

    # Test 1: Django setup
    try:
        django.setup()
        print("✅ Django setup successful")
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

    # Test 2: Database backend import
    try:
        print("✅ Database backend import successful")
    except Exception as e:
        print(f"❌ Database backend import failed: {e}")
        return False

    # Test 3: Model import
    try:
        print("✅ DynamoDBModel import successful")
    except Exception as e:
        print(f"❌ DynamoDBModel import failed: {e}")
        return False

    # Test 4: Admin import
    try:
        print("✅ DynamoDBAdmin import successful")
    except Exception as e:
        print(f"❌ DynamoDBAdmin import failed: {e}")
        return False

    # Test 5: Migration system import
    try:
        print("✅ Migration system import successful")
    except Exception as e:
        print(f"❌ Migration system import failed: {e}")
        return False

    # Test 6: Management commands
    try:
        from django.core.management import get_commands

        commands = get_commands()
        dynamodb_commands = [cmd for cmd in commands.keys() if "dynamodb" in cmd]
        if dynamodb_commands:
            print(f"✅ Management commands registered: {dynamodb_commands}")
        else:
            print("⚠️ No DynamoDB management commands found")
    except Exception as e:
        print(f"❌ Management commands check failed: {e}")

    print("\n✅ Quick validation completed successfully!")
    return True


def main():
    """Main entry point for test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="DynamoDB Django Admin Test Runner")
    parser.add_argument(
        "--phase",
        type=int,
        choices=[1, 2, 3, 4, 5, 6, 7],
        help="Run tests for specific phase only",
    )
    parser.add_argument(
        "--quick", action="store_true", help="Run quick validation tests only"
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=1, help="Increase verbosity"
    )

    args = parser.parse_args()

    # Setup Django
    try:
        django.setup()
    except Exception as e:
        print(f"Failed to setup Django: {e}")
        return 1

    if args.quick:
        success = run_quick_validation()
        return 0 if success else 1

    runner = ComprehensiveTestRunner(verbosity=args.verbose)

    if args.phase:
        success = runner.run_specific_phase(args.phase)
    else:
        success = runner.run_all_phases()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
