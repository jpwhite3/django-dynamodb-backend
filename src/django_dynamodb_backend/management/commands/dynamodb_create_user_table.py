"""
Django management command for creating the DynamoDB users table.
"""

from django.core.management.base import BaseCommand

from ...contrib.auth_dynamo.models import create_user_table


class Command(BaseCommand):
    help = "Create the DynamoDB users table with GSIs for username and email lookups"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-admin",
            action="store_true",
            help="Also create an admin superuser (admin/admin123)",
        )
        parser.add_argument(
            "--admin-username",
            default="admin",
            help="Username for the admin superuser (default: admin)",
        )
        parser.add_argument(
            "--admin-password",
            default="admin123",
            help="Password for the admin superuser (default: admin123)",
        )
        parser.add_argument(
            "--admin-email",
            default="admin@example.com",
            help="Email for the admin superuser (default: admin@example.com)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Creating DynamoDB users table...")

        try:
            create_user_table()
            self.stdout.write(
                self.style.SUCCESS("DynamoDB users table created successfully")
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create users table: {e}"))
            raise

        if options["create_admin"]:
            self._create_admin_user(
                options["admin_username"],
                options["admin_password"],
                options["admin_email"],
            )

    def _create_admin_user(self, username, password, email):
        """Create an admin superuser if it doesn't exist."""
        self.stdout.write(f"Creating admin superuser '{username}'...")

        try:
            from ...contrib.auth_dynamo.managers import DynamoUserManager
            from ...contrib.auth_dynamo.models import DynamoUser

            manager = DynamoUserManager()
            manager.model = DynamoUser

            # Check if admin already exists
            if manager.exists(username=username):
                self.stdout.write(
                    self.style.WARNING(
                        f"User '{username}' already exists, skipping creation"
                    )
                )
                return

            # Create superuser
            user = manager.create_superuser(
                username=username,
                email=email,
                password=password,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Admin superuser '{username}' created successfully (ID: {user.id})"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to create admin user: {e}"))
            raise
