"""
Django management command for creating the DynamoDB sessions table.
"""

from django.core.management.base import BaseCommand

from ...sessions import create_session_table


class Command(BaseCommand):
    help = "Create the DynamoDB sessions table with TTL enabled"

    def handle(self, *args, **options):
        self.stdout.write("Creating DynamoDB sessions table...")

        try:
            create_session_table()
            self.stdout.write(
                self.style.SUCCESS("DynamoDB sessions table created successfully")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create sessions table: {e}"))
            raise
