"""
Django management command for showing DynamoDB migration status.
"""

import logging

from django.core.management.base import BaseCommand

from ...migration_executor import MigrationExecutor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Show DynamoDB migration status"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            nargs="?",
            help="App label to show migrations for (optional)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed migration information",
        )
        parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (table or json)",
        )

    def handle(self, *args, **options):
        executor = MigrationExecutor()
        migrations = executor.show_migrations()

        app_label = options.get("app_label")
        verbose = options.get("verbose", False)
        output_format = options.get("format", "table")

        # Filter by app if specified
        if app_label:
            if app_label not in migrations:
                self.stdout.write(
                    f"No DynamoDB migrations found for app '{app_label}'."
                )
                return
            migrations = {app_label: migrations[app_label]}

        if not migrations:
            self.stdout.write("No DynamoDB migrations found.")
            return

        if output_format == "json":
            self._output_json(migrations)
        else:
            self._output_table(migrations, verbose)

    def _output_table(self, migrations, verbose=False):
        """Output migrations in table format."""
        self.stdout.write("DynamoDB Migration Status:")
        self.stdout.write("=" * 70)

        for app_label, app_migrations in migrations.items():
            self.stdout.write(f"\n{self.style.HTTP_INFO(app_label)}:")

            if not app_migrations:
                self.stdout.write("  (no migrations)")
                continue

            for migration in app_migrations:
                # Status indicator
                if migration["applied"]:
                    status = self.style.SUCCESS("[X]")
                else:
                    status = self.style.WARNING("[ ]")

                # Migration name
                name = migration["name"]

                self.stdout.write(f"  {status} {name}")

                # Show dependencies if verbose
                if verbose and migration["dependencies"]:
                    deps = [f"{dep[0]}.{dep[1]}" for dep in migration["dependencies"]]
                    self.stdout.write(f"      Dependencies: {', '.join(deps)}")

    def _output_json(self, migrations):
        """Output migrations in JSON format."""
        import json

        # Convert to JSON-serializable format
        json_data = {}
        for app_label, app_migrations in migrations.items():
            json_data[app_label] = []
            for migration in app_migrations:
                json_data[app_label].append(
                    {
                        "name": migration["name"],
                        "applied": migration["applied"],
                        "dependencies": [
                            {"app": dep[0], "migration": dep[1]}
                            for dep in migration["dependencies"]
                        ],
                    }
                )

        self.stdout.write(json.dumps(json_data, indent=2))
