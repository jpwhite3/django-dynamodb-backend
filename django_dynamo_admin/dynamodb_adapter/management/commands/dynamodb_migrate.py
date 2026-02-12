"""
Django management command for applying DynamoDB migrations.
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...migration_executor import MigrationExecutor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Apply DynamoDB migrations"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            nargs="?",
            help="App label to migrate (optional)",
        )
        parser.add_argument(
            "migration_name",
            nargs="?",
            help="Migration name to migrate to (optional)",
        )
        parser.add_argument(
            "--fake",
            action="store_true",
            help="Mark migrations as applied without actually running them",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Show migration status for all apps",
        )
        parser.add_argument(
            "--plan",
            action="store_true",
            help="Show migration plan without executing",
        )

    def handle(self, *args, **options):
        executor = MigrationExecutor()

        # Show migration status
        if options["list"]:
            return self._show_migrations(executor)

        # Show migration plan
        if options["plan"]:
            return self._show_plan(executor, options)

        # Apply migrations
        try:
            app_label = options.get("app_label")
            migration_name = options.get("migration_name")
            fake = options.get("fake", False)

            if migration_name and not app_label:
                raise CommandError(
                    "You must specify app_label when specifying migration_name"
                )

            executor.migrate(
                app_label=app_label, migration_name=migration_name, fake=fake
            )

            self.stdout.write(
                self.style.SUCCESS("DynamoDB migrations applied successfully")
            )

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise CommandError(f"Migration failed: {e}")

    def _show_migrations(self, executor):
        """Show migration status for all apps."""
        migrations = executor.show_migrations()

        if not migrations:
            self.stdout.write("No DynamoDB migrations found.")
            return

        self.stdout.write("DynamoDB Migration Status:")
        self.stdout.write("=" * 50)

        for app_label, app_migrations in migrations.items():
            self.stdout.write(f"\n{app_label}:")

            for migration in app_migrations:
                status = "[X]" if migration["applied"] else "[ ]"
                deps = (
                    f" (depends on: {', '.join([f'{dep[0]}.{dep[1]}' for dep in migration['dependencies']])})"
                    if migration["dependencies"]
                    else ""
                )

                self.stdout.write(f"  {status} {migration['name']}{deps}")

    def _show_plan(self, executor, options):
        """Show migration plan without executing."""
        app_label = options.get("app_label")
        migration_name = options.get("migration_name")

        plan = executor.loader.get_migration_plan(app_label, migration_name)

        if not plan:
            self.stdout.write("No migrations to apply.")
            return

        self.stdout.write("DynamoDB Migration Plan:")
        self.stdout.write("=" * 30)

        for node in plan:
            self.stdout.write(f"  {node.app_label}.{node.name}")

            # Show operations
            for i, operation in enumerate(node.migration.operations):
                self.stdout.write(f"    {i+1}. {operation.describe()}")

        self.stdout.write(f"\nTotal migrations: {len(plan)}")
