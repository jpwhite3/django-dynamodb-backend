"""
DynamoDB User Model for Django Authentication.

Provides a User model stored entirely in DynamoDB, compatible with Django's
authentication system and admin interface.
"""

import hashlib
import logging
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models

from ...models import DynamoDBModel

logger = logging.getLogger(__name__)

# Table configuration
DYNAMODB_USER_TABLE_NAME = getattr(settings, "DYNAMODB_USER_TABLE_NAME", "django_users")


class DynamoUser(DynamoDBModel):
    """
    DynamoDB-backed User model compatible with Django's auth system.

    This model implements the necessary interface for Django authentication
    while storing all data in DynamoDB. It supports:
    - Username/email-based authentication
    - Password hashing using Django's password hashers
    - Permissions stored as string sets
    - Staff/superuser flags for admin access
    """

    # Primary key - using UUIDField for unique identification
    id = models.CharField(primary_key=True, max_length=36)

    # Core authentication fields
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=254, blank=True)
    password = models.CharField(max_length=128)

    # Personal info
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    # Status flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # Permissions stored as comma-separated strings
    # Format: "app_label:model:codename,app_label:model:codename,..."
    user_permissions = models.TextField(blank=True, default="")

    # Groups stored as comma-separated strings
    groups = models.TextField(blank=True, default="")

    # Custom manager will be set from managers.py
    objects = None  # Placeholder - set in __init__.py

    # Required by Django auth
    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        app_label = "auth_dynamo"
        db_table = DYNAMODB_USER_TABLE_NAME
        verbose_name = "user"
        verbose_name_plural = "users"

    def __init__(self, *args, **kwargs):
        # Generate ID if not provided
        if "id" not in kwargs and not args:
            kwargs["id"] = str(uuid.uuid4())

        # Handle password hashing for new users
        raw_password = kwargs.pop("_raw_password", None)
        super().__init__(*args, **kwargs)

        if raw_password:
            self.set_password(raw_password)

    def __str__(self):
        return self.username

    # ========================================
    # Password Management
    # ========================================

    def set_password(self, raw_password):
        """Hash and set the password."""
        self.password = make_password(raw_password)
        self._field_values["password"] = self.password

    def check_password(self, raw_password):
        """Check if the provided password matches."""

        def setter(raw_password):
            self.set_password(raw_password)
            self.save(update_fields=["password"])

        return check_password(raw_password, self.password, setter)

    def set_unusable_password(self):
        """Set a value that will never be a valid password hash."""
        self.password = make_password(None)
        self._field_values["password"] = self.password

    def has_usable_password(self):
        """Check if the user has a usable password."""
        return self.password is not None and not self.password.startswith("!")

    # ========================================
    # Permissions
    # ========================================

    def get_all_permissions(self, obj=None):
        """Return all permissions the user has."""
        if self.is_superuser:
            # Superusers have all permissions
            return {"*"}

        perms = set()

        # Add user's direct permissions
        if self.user_permissions:
            perms.update(
                p.strip() for p in self.user_permissions.split(",") if p.strip()
            )

        # Add permissions from groups
        # (Would need group model implementation for full support)

        return perms

    def has_perm(self, perm, obj=None):
        """Check if user has a specific permission."""
        if not self.is_active:
            return False

        if self.is_superuser:
            return True

        # Check direct permissions
        all_perms = self.get_all_permissions(obj)
        if "*" in all_perms:
            return True

        # Check exact permission
        if perm in all_perms:
            return True

        # Check app-level wildcard (e.g., "polls:*")
        app_label = perm.split(":")[0] if ":" in perm else perm.split(".")[0]
        if f"{app_label}:*" in all_perms:
            return True

        return False

    def has_perms(self, perm_list, obj=None):
        """Check if user has all specified permissions."""
        return all(self.has_perm(perm, obj) for perm in perm_list)

    def has_module_perms(self, app_label):
        """Check if user has any permission in the given app."""
        if not self.is_active:
            return False

        if self.is_superuser:
            return True

        all_perms = self.get_all_permissions()

        # Check for wildcard
        if "*" in all_perms or f"{app_label}:*" in all_perms:
            return True

        # Check for any permission in this app
        for perm in all_perms:
            if perm.startswith(f"{app_label}:") or perm.startswith(f"{app_label}."):
                return True

        return False

    def add_permission(self, perm):
        """Add a permission to the user."""
        perms = set(p.strip() for p in self.user_permissions.split(",") if p.strip())
        perms.add(perm)
        self.user_permissions = ",".join(sorted(perms))
        self._field_values["user_permissions"] = self.user_permissions

    def remove_permission(self, perm):
        """Remove a permission from the user."""
        perms = set(p.strip() for p in self.user_permissions.split(",") if p.strip())
        perms.discard(perm)
        self.user_permissions = ",".join(sorted(perms))
        self._field_values["user_permissions"] = self.user_permissions

    def clear_permissions(self):
        """Remove all permissions from the user."""
        self.user_permissions = ""
        self._field_values["user_permissions"] = ""

    # ========================================
    # Groups (simplified implementation)
    # ========================================

    def get_group_names(self):
        """Get list of group names the user belongs to."""
        if not self.groups:
            return []
        return [g.strip() for g in self.groups.split(",") if g.strip()]

    def add_to_group(self, group_name):
        """Add user to a group."""
        group_list = self.get_group_names()
        if group_name not in group_list:
            group_list.append(group_name)
            self.groups = ",".join(sorted(group_list))
            self._field_values["groups"] = self.groups

    def remove_from_group(self, group_name):
        """Remove user from a group."""
        group_list = self.get_group_names()
        if group_name in group_list:
            group_list.remove(group_name)
            self.groups = ",".join(sorted(group_list))
            self._field_values["groups"] = self.groups

    # ========================================
    # Django Auth Interface
    # ========================================

    @property
    def is_anonymous(self):
        """Always return False for authenticated users."""
        return False

    @property
    def is_authenticated(self):
        """Always return True for authenticated users."""
        return True

    def get_username(self):
        """Return the username."""
        return self.username

    def get_full_name(self):
        """Return the full name."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.username

    def get_short_name(self):
        """Return the short name (first name)."""
        return self.first_name or self.username

    def natural_key(self):
        """Return the natural key for serialization."""
        return (self.username,)

    # ========================================
    # Session support
    # ========================================

    def get_session_auth_hash(self):
        """Return HMAC of the password field for session auth."""
        key_salt = "django_dynamodb_backend.contrib.auth_dynamo.models.DynamoUser"
        return hashlib.sha256(f"{key_salt}{self.password}".encode()).hexdigest()


class AnonymousUser:
    """
    AnonymousUser for unauthenticated requests.

    Mimics Django's AnonymousUser for compatibility.
    """

    id = None
    pk = None
    username = ""
    is_staff = False
    is_active = False
    is_superuser = False

    def __str__(self):
        return "AnonymousUser"

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __hash__(self):
        return 1

    @property
    def is_anonymous(self):
        return True

    @property
    def is_authenticated(self):
        return False

    def save(self):
        raise NotImplementedError("Cannot save AnonymousUser")

    def delete(self):
        raise NotImplementedError("Cannot delete AnonymousUser")

    def set_password(self, raw_password):
        raise NotImplementedError("Cannot set password for AnonymousUser")

    def check_password(self, raw_password):
        raise NotImplementedError("Cannot check password for AnonymousUser")

    def get_all_permissions(self, obj=None):
        return set()

    def has_perm(self, perm, obj=None):
        return False

    def has_perms(self, perm_list, obj=None):
        return False

    def has_module_perms(self, app_label):
        return False

    def get_username(self):
        return ""


def create_user_table():
    """
    Create the DynamoDB users table with GSIs.

    This function should be called during deployment/migration.
    """
    from ...sessions import get_dynamodb_client

    client = get_dynamodb_client()

    try:
        # Check if table exists
        client.describe_table(TableName=DYNAMODB_USER_TABLE_NAME)
        logger.info(f"User table {DYNAMODB_USER_TABLE_NAME} already exists")
        return True
    except client.exceptions.ResourceNotFoundException:
        pass

    # Create table with GSIs for username and email lookups
    logger.info(f"Creating user table: {DYNAMODB_USER_TABLE_NAME}")

    try:
        client.create_table(
            TableName=DYNAMODB_USER_TABLE_NAME,
            KeySchema=[
                {"AttributeName": "id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "username", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "username-index",
                    "KeySchema": [
                        {"AttributeName": "username", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "email-index",
                    "KeySchema": [
                        {"AttributeName": "email", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Wait for table to be active
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=DYNAMODB_USER_TABLE_NAME)

        logger.info(f"User table {DYNAMODB_USER_TABLE_NAME} created with GSIs")
        return True

    except Exception as e:
        logger.error(f"Error creating user table: {e}")
        raise
