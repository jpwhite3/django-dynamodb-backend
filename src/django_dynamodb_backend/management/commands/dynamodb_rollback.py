"""
Django management command for rolling back DynamoDB migrations.
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from ...migration_executor import MigrationExecutor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rollback DynamoDB migrations to a specific point"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            help="App label to rollback",
        )
        parser.add_argument(
            "migration_name",
            help="Migration name to rollback to",
        )
        parser.add_argument(
            "--plan",
            action="store_true",
            help="Show rollback plan without executing",
        )

    def handle(self, *args, **options):
        executor = MigrationExecutor()

        app_label = options["app_label"]
        migration_name = options["migration_name"]

        # Show rollback plan
        if options["plan"]:
            self._show_plan(executor, app_label, migration_name)
            return

        # Perform rollback
        try:
            executor.rollback(app_label=app_label, migration_name=migration_name)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully rolled back to {app_label}.{migration_name}"
                )
            )

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise CommandError(f"Rollback failed: {e}")

    def _show_plan(self, executor, app_label, migration_name):
        """Show rollback plan without executing."""
        executor.loader.load_disk()

        targets = [(app_label, migration_name)]
        plan = executor.loader.graph.get_unapply_plan(targets)

        if not plan:
            self.stdout.write("No migrations to rollback.")
            return

        self.stdout.write("DynamoDB Rollback Plan:")
        self.stdout.write("=" * 30)

        for node in plan:
            self.stdout.write(f"  {node.app_label}.{node.name} (unapply)")

            # Show operations (in reverse)
            for i, operation in enumerate(reversed(node.migration.operations)):
                self.stdout.write(f"    {i+1}. Reverse: {operation.describe()}")

        self.stdout.write(f"\nTotal migrations to rollback: {len(plan)}")
