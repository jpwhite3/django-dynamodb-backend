"""
Django management command for creating DynamoDB migration files.
"""

import logging
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create DynamoDB migration files"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            help="App label to create migration for",
        )
        parser.add_argument(
            "--name",
            help="Custom migration name",
        )
        parser.add_argument(
            "--empty",
            action="store_true",
            help="Create an empty migration",
        )
        parser.add_argument(
            "--create-table",
            help="Create table operation for specified model",
        )
        parser.add_argument(
            "--data-migration",
            action="store_true",
            help="Create a data migration template",
        )

    def handle(self, *args, **options):
        app_label = options["app_label"]

        # Validate app exists
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            raise CommandError(f"No installed app with label '{app_label}'.")

        # Create migrations directory if it doesn't exist
        migrations_dir = Path(app_config.path) / "dynamodb_migrations"
        migrations_dir.mkdir(exist_ok=True)

        # Create __init__.py if it doesn't exist
        init_file = migrations_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")

        # Generate migration name
        migration_name = self._get_migration_name(migrations_dir, options)

        # Generate migration content
        content = self._generate_migration_content(options, app_label, migration_name)

        # Write migration file
        migration_file = migrations_dir / f"{migration_name}.py"
        migration_file.write_text(content)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created DynamoDB migration: {app_label}/dynamodb_migrations/{migration_name}.py"
            )
        )

    def _get_migration_name(self, migrations_dir: Path, options: dict) -> str:
        """Generate a migration name."""
        if options.get("name"):
            base_name = options["name"]
        elif options.get("create_table"):
            base_name = f"create_{options['create_table'].lower()}_table"
        elif options.get("data_migration"):
            base_name = "data_migration"
        elif options.get("empty"):
            base_name = "empty"
        else:
            base_name = "auto_migration"

        # Get next sequence number
        existing_files = list(migrations_dir.glob("*.py"))
        sequence_numbers = []

        for file_path in existing_files:
            if file_path.name.startswith("__"):
                continue

            try:
                # Extract sequence number (e.g., 0001 from 0001_initial.py)
                parts = file_path.stem.split("_", 1)
                if parts[0].isdigit():
                    sequence_numbers.append(int(parts[0]))
            except (ValueError, IndexError):
                continue

        next_number = max(sequence_numbers, default=0) + 1
        return f"{next_number:04d}_{base_name}"

    def _generate_migration_content(
        self, options: dict, app_label: str, migration_name: str
    ) -> str:
        """Generate migration file content."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Base template
        content = f'''"""
DynamoDB migration for {app_label}.

Created on {timestamp}
"""
from django_dynamodb_backend.migrations_dynamo import (
    DynamoDBMigration, CreateTable, UpdateTableCapacity, RunPython, DataMigration
)
from django_dynamodb_backend.models import '''

        # Add model imports based on the operation
        if options.get("create_table"):
            model_name = options["create_table"]
            content += f"{model_name}\n"
        else:
            # Import all models from the app
            try:
                app_config = apps.get_app_config(app_label)
                models_module = f"{app_config.name}.models"
                exec(f"import {models_module}")
                content += "# Import your models here\n"
            except Exception:
                content += "# Import your models here\n"

        content += f"""

class Migration(DynamoDBMigration):
    \"\"\"Migration: {migration_name}\"\"\"
    
    dependencies = [
        # Add dependencies here, e.g.:
        # ('app_label', 'previous_migration_name'),
    ]
    
    operations = [
"""

        # Add operations based on options
        if options.get("create_table"):
            model_name = options["create_table"]
            content += f"""        CreateTable(
            model_class={model_name},
            read_capacity=5,
            write_capacity=5
        ),
"""
        elif options.get("data_migration"):
            content += """        DataMigration(
            model_class=YourModel,  # Replace with your model
            migration_func=migrate_data_forward,
            reverse_func=migrate_data_reverse
        ),
"""
        elif options.get("empty"):
            content += "        # Add your operations here\n"
        else:
            content += "        # Auto-generated operations will be added here\n"

        content += "    ]\n"

        # Add helper functions for data migrations
        if options.get("data_migration"):
            content += """

def migrate_data_forward(item):
    \"\"\"Forward data migration function.\"\"\"
    # Modify the item as needed
    # item.save()
    pass

def migrate_data_reverse(item):
    \"\"\"Reverse data migration function.\"\"\"
    # Reverse the changes made in migrate_data_forward
    # item.save() 
    pass
"""

        return content
