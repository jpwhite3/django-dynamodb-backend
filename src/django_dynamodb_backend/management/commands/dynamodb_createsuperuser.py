"""
Django management command for creating a DynamoDB superuser.

Mirrors Django's ``createsuperuser`` but writes to DynamoDB.
"""

import getpass

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a superuser in DynamoDB (similar to Django's createsuperuser)"

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Username for the superuser")
        parser.add_argument("--email", default="", help="Email for the superuser")
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Read all values from the command line (requires --username and --password)",
        )
        parser.add_argument(
            "--password",
            help="Password (only used with --noinput; interactive mode prompts securely)",
        )

    def handle(self, *args, **options):
        from ...contrib.auth_dynamo.managers import DynamoUserManager
        from ...contrib.auth_dynamo.models import DynamoUser

        manager = DynamoUserManager()
        manager.model = DynamoUser

        if options["no_input"]:
            username = options.get("username")
            password = options.get("password")
            if not username or not password:
                raise CommandError(
                    "--username and --password are required with --noinput"
                )
            email = options.get("email") or ""
        else:
            username = options.get("username") or input("Username: ")
            email = options.get("email") or input("Email address (optional): ")
            password = getpass.getpass("Password: ")
            password2 = getpass.getpass("Password (again): ")
            if password != password2:
                raise CommandError("Passwords do not match.")

        if not username:
            raise CommandError("Username cannot be blank.")

        if manager.exists(username=username):
            raise CommandError(f"User '{username}' already exists.")

        user = manager.create_superuser(
            username=username,
            email=email or None,
            password=password,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Superuser '{username}' created successfully (ID: {user.id})"
            )
        )
